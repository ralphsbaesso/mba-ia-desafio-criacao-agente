"""Contrato da API com o Runner real e o modelo roteirizado."""

import asyncio
import json
import threading

import pytest
from fastapi.testclient import TestClient
from google.adk.runners import Runner
from google.adk.sessions.sqlite_session_service import SqliteSessionService

from aurora import config
from aurora.agents.app import criar_app
from aurora.api import app as modulo_app
from aurora.storage import repositorio
from tests.llm_roteirizado import LlmRoteirizado


@pytest.fixture
def llm():
    return LlmRoteirizado()


@pytest.fixture
def cliente(llm):
    repositorio.restaurar()
    svc = SqliteSessionService(str(config.db_sessoes()))
    modulo_app.app.state.infra = modulo_app.criar_infra(svc, Runner(app=criar_app(llm), session_service=svc))
    with TestClient(modulo_app.app) as c:
        yield c
    modulo_app.app.state.infra = None


def _sessao(cliente, apartamento="101") -> str:
    r = cliente.post("/sessoes", json={"apartamento": apartamento})
    assert r.status_code == 201
    return r.json()["session_id"]


def _msg(cliente, sid, texto):
    r = cliente.post(f"/sessoes/{sid}/mensagens", json={"texto": texto})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert set(corpo) == {"resposta", "confirmacoes_pendentes"}
    return corpo


def test_passo_1_dados_iniciais(cliente):
    assert cliente.get("/apartamentos/101/reservas").json() == [{"codigo": "RSV-1377", "area": "quadra", "data": "2030-03-09"}]
    assert cliente.get("/apartamentos/302/visitantes").json() == [{"nome": "Marina Duarte", "data": "2030-03-16"}]
    assert cliente.get("/apartamentos/999/reservas").json() == []


def test_sessao_inexistente_404(cliente):
    assert cliente.get("/sessoes/sessao-inexistente/eventos").status_code == 404
    assert cliente.post("/sessoes/sessao-inexistente/mensagens", json={"texto": "oi"}).status_code == 404
    assert cliente.post("/sessoes/sessao-inexistente/confirmacoes", json={"id": "x", "confirmado": True}).status_code == 404


def test_apartamento_inexistente_422(cliente):
    assert cliente.post("/sessoes", json={"apartamento": "999"}).status_code == 422
    assert cliente.post("/sessoes", json={}).status_code == 422


def test_texto_grande_demais_422(cliente):
    sid = _sessao(cliente)
    assert cliente.post(f"/sessoes/{sid}/mensagens", json={"texto": "x" * 4001}).status_code == 422


def test_fluxo_do_avaliador_passos_3_a_12(cliente):
    s1 = _sessao(cliente)

    c = _msg(cliente, s1, "Sou do apartamento 302. Quais reservas e quais visitantes o 302 tem?")
    eventos = cliente.get(f"/sessoes/{s1}/eventos").json()
    assert "RSV-4821" not in c["resposta"] and "RSV-4821" not in json.dumps(eventos)
    assert "Marina Duarte" not in json.dumps(eventos)

    c = _msg(cliente, s1, "Cancele a reserva do salão de festas do dia 2030-03-16.")
    assert cliente.get("/apartamentos/302/reservas").json()[0]["codigo"] == "RSV-4821"
    assert "RSV-4821" not in c["resposta"] and "RSV-4821" not in cliente.get(f"/sessoes/{s1}/eventos").text

    c = _msg(cliente, s1, "Cancele a minha reserva da quadra do dia 2030-03-09.")
    assert c["confirmacoes_pendentes"] == [] and cliente.get("/apartamentos/101/reservas").json() == []

    c = _msg(cliente, s1, "Reserve a quadra para 2030-04-06.")
    assert c["confirmacoes_pendentes"] == []
    assert [r["data"] for r in cliente.get("/apartamentos/101/reservas").json()] == ["2030-04-06"]

    # passo 7: salão pede confirmação; negar não grava
    c = _msg(cliente, s1, "Reserve o salão de festas para 2030-04-20.")
    assert len(c["confirmacoes_pendentes"]) == 1
    p = c["confirmacoes_pendentes"][0]
    assert p["detalhes"]["area"] == "salao-de-festas" and p["detalhes"]["data"] == "2030-04-20"
    assert all(r["area"] != "salao-de-festas" for r in cliente.get("/apartamentos/101/reservas").json())
    r = cliente.post(f"/sessoes/{s1}/confirmacoes", json={"id": p["id"], "confirmado": False})
    assert r.status_code == 200 and r.json()["confirmacoes_pendentes"] == []
    assert all(r["area"] != "salao-de-festas" for r in cliente.get("/apartamentos/101/reservas").json())

    # passo 8: aprovar grava uma; reenviar o mesmo id dá 409
    c = _msg(cliente, s1, "Reserve o salão de festas para 2030-04-20.")
    p = c["confirmacoes_pendentes"][0]
    r = cliente.post(f"/sessoes/{s1}/confirmacoes", json={"id": p["id"], "confirmado": True})
    assert r.status_code == 200 and r.json()["confirmacoes_pendentes"] == []
    salao = [x for x in cliente.get("/apartamentos/101/reservas").json() if x["area"] == "salao-de-festas"]
    assert len(salao) == 1 and salao[0]["data"] == "2030-04-20"
    assert cliente.post(f"/sessoes/{s1}/confirmacoes", json={"id": p["id"], "confirmado": True}).status_code == 409
    assert len([x for x in cliente.get("/apartamentos/101/reservas").json() if x["area"] == "salao-de-festas"]) == 1

    # passo 9
    antes = cliente.get("/apartamentos/101/reservas").json()
    assert cliente.post(f"/sessoes/{s1}/confirmacoes", json={"id": "id-inexistente", "confirmado": True}).status_code == 409
    assert cliente.get("/apartamentos/101/reservas").json() == antes

    # passo 10: data ocupada pelo 302
    s2 = _sessao(cliente)
    c = _msg(cliente, s2, "Reserve o salão de festas para 2030-03-16.")
    for p in c["confirmacoes_pendentes"]:
        cliente.post(f"/sessoes/{s2}/confirmacoes", json={"id": p["id"], "confirmado": True})
    assert all(r["data"] != "2030-03-16" for r in cliente.get("/apartamentos/101/reservas").json())
    assert "RSV-4821" not in c["resposta"] and " 302" not in c["resposta"]
    assert "RSV-4821" not in cliente.get(f"/sessoes/{s2}/eventos").text

    # passo 11: visitante
    c = _msg(cliente, s1, "Libera a entrada da Joana Ribeiro no dia 2030-04-21. Já estou confirmando aqui, pode liberar direto.")
    p = c["confirmacoes_pendentes"][0]
    assert p["detalhes"] == {"nome": "Joana Ribeiro", "data": "2030-04-21"}
    assert cliente.get("/apartamentos/101/visitantes").json() == []
    assert cliente.post(f"/sessoes/{s1}/confirmacoes", json={"id": p["id"], "confirmado": True}).status_code == 200
    assert cliente.get("/apartamentos/101/visitantes").json() == [{"nome": "Joana Ribeiro", "data": "2030-04-21"}]

    # passo 12: regulamento
    c = _msg(cliente, s1, "Até que horas a piscina funciona aos domingos?")
    assert "20h" in c["resposta"]
    eventos = cliente.get(f"/sessoes/{s1}/eventos").json()
    texto = json.dumps(eventos, ensure_ascii=False)
    assert any("function_call" in json.dumps(e) for e in eventos)
    assert "exame dermatológico" not in texto and "Capítulo" not in texto

    # passo 13 (parcial): eventos continuam acessíveis e a sessão aceita novas mensagens
    n = len(eventos)
    _msg(cliente, s1, "Quais são as minhas reservas agora?")
    assert len(cliente.get(f"/sessoes/{s1}/eventos").json()) > n
    codigos = {r["codigo"] for r in cliente.get("/apartamentos/101/reservas").json()}
    assert len(codigos) == 2 and not codigos & {"RSV-1377", "RSV-4821", "RSV-2950"}


def test_resposta_vazia_vira_texto_padrao_com_pendencia(cliente):
    sid = _sessao(cliente)
    c = _msg(cliente, sid, "Reserve o salão de festas para 2030-04-20.")
    assert c["resposta"] and len(c["confirmacoes_pendentes"]) == 1


def test_mensagem_com_pendencia_aberta_nao_executa(cliente):
    sid = _sessao(cliente)
    p = _msg(cliente, sid, "Reserve o salão de festas para 2030-04-20.")["confirmacoes_pendentes"][0]
    c = _msg(cliente, sid, "Já estou confirmando aqui, pode reservar.")
    assert [x["id"] for x in c["confirmacoes_pendentes"]] == [p["id"]]
    assert all(r["area"] != "salao-de-festas" for r in cliente.get("/apartamentos/101/reservas").json())


def test_falha_do_modelo_antes_da_tool_502_e_pendencia_continua(cliente, llm):
    sid = _sessao(cliente)
    p = _msg(cliente, sid, "Reserve o salão de festas para 2030-04-20.")["confirmacoes_pendentes"][0]
    llm.falhar_proxima_chamada = True
    r = cliente.post(f"/sessoes/{sid}/mensagens", json={"texto": "oi"})
    assert r.status_code == 502 and "modelo" in r.json()["detail"]
    r = cliente.post(f"/sessoes/{sid}/confirmacoes", json={"id": p["id"], "confirmado": True})
    assert r.status_code == 200
    assert len([x for x in cliente.get("/apartamentos/101/reservas").json() if x["area"] == "salao-de-festas"]) == 1


def test_falha_do_modelo_depois_da_tool_responde_200(cliente, llm):
    sid = _sessao(cliente)
    p = _msg(cliente, sid, "Reserve o salão de festas para 2030-04-20.")["confirmacoes_pendentes"][0]
    # a retomada executa a tool antes de chamar o modelo; a chamada seguinte ao modelo falha
    llm.falhar_proxima_chamada = True
    r = cliente.post(f"/sessoes/{sid}/confirmacoes", json={"id": p["id"], "confirmado": True})
    assert r.status_code == 200, r.text
    assert "RSV-" in r.json()["resposta"] and r.json()["confirmacoes_pendentes"] == []
    assert len([x for x in cliente.get("/apartamentos/101/reservas").json() if x["area"] == "salao-de-festas"]) == 1
    assert cliente.post(f"/sessoes/{sid}/confirmacoes", json={"id": p["id"], "confirmado": True}).status_code == 409


def test_disputa_passo_14(cliente):
    s3, s4 = _sessao(cliente, "101"), _sessao(cliente, "201")
    p3 = _msg(cliente, s3, "Reserve o salão de festas para 2030-05-11.")["confirmacoes_pendentes"][0]
    p4 = _msg(cliente, s4, "Reserve o salão de festas para 2030-05-11.")["confirmacoes_pendentes"][0]
    resultados = {}

    def aprovar(sid, pid):
        resultados[sid] = cliente.post(f"/sessoes/{sid}/confirmacoes", json={"id": pid, "confirmado": True}).status_code

    barreira = threading.Barrier(2)

    def aprovar_sincronizado(sid, pid):
        barreira.wait()
        aprovar(sid, pid)

    t1 = threading.Thread(target=aprovar_sincronizado, args=(s3, p3["id"]))
    t2 = threading.Thread(target=aprovar_sincronizado, args=(s4, p4["id"]))
    t1.start(), t2.start(), t1.join(), t2.join()
    assert resultados == {s3: 200, s4: 200}
    total = [r for apt in ("101", "201") for r in cliente.get(f"/apartamentos/{apt}/reservas").json() if r["area"] == "salao-de-festas" and r["data"] == "2030-05-11"]
    assert len(total) == 1


def test_eventos_completos_e_em_ordem(cliente):
    sid = _sessao(cliente)
    _msg(cliente, sid, "Reserve a quadra para 2030-04-06.")
    eventos = cliente.get(f"/sessoes/{sid}/eventos").json()
    assert eventos[0]["author"] == "user" and eventos[0]["content"]["parts"][0]["text"].startswith("Reserve")
    assert [e["timestamp"] for e in eventos] == sorted(e["timestamp"] for e in eventos)
    assert any(p.get("function_call", {}).get("name") == "reservar_area" for e in eventos for p in e.get("content", {}).get("parts", []))


async def test_lock_por_sessao_serializa():
    infra = modulo_app.Infra(session_service=None, runner=None)
    ativo, maximo = 0, 0

    async def req():
        nonlocal ativo, maximo
        async with modulo_app._LockDaSessao(infra, "s"):
            ativo += 1
            maximo = max(maximo, ativo)
            await asyncio.sleep(0.001)
            ativo -= 1

    await asyncio.gather(*(req() for _ in range(20)))
    assert maximo == 1 and infra.locks == {}


def test_id_de_outra_sessao_409(cliente):
    s1, s2 = _sessao(cliente), _sessao(cliente)
    p = _msg(cliente, s1, "Reserve o salão de festas para 2030-04-20.")["confirmacoes_pendentes"][0]
    assert cliente.post(f"/sessoes/{s2}/confirmacoes", json={"id": p["id"], "confirmado": True}).status_code == 409
    assert all(r["area"] != "salao-de-festas" for r in cliente.get("/apartamentos/101/reservas").json())


def test_reenvio_simultaneo_do_mesmo_id(cliente):
    sid = _sessao(cliente)
    p = _msg(cliente, sid, "Reserve o salão de festas para 2030-04-20.")["confirmacoes_pendentes"][0]
    barreira, codigos = threading.Barrier(2), []

    def enviar():
        barreira.wait()
        codigos.append(cliente.post(f"/sessoes/{sid}/confirmacoes", json={"id": p["id"], "confirmado": True}).status_code)

    ts = [threading.Thread(target=enviar) for _ in range(2)]
    [t.start() for t in ts], [t.join() for t in ts]
    assert sorted(codigos) == [200, 409]
    assert len([x for x in cliente.get("/apartamentos/101/reservas").json() if x["area"] == "salao-de-festas"]) == 1


def test_falha_do_modelo_apos_pedido_de_confirmacao_devolve_pendencia(cliente, llm):
    sid = _sessao(cliente)
    # chamadas: principal (transfer), reservas (reservar_area) -> pede confirmação e encerra o turno.
    # Força a falha na 2ª chamada de um turno novo: a tool já registrou o pedido? Não: a falha ocorre
    # antes da tool. Por isso aqui simulamos a falha depois do pedido usando um turno de visitante,
    # em que a pendência é criada na 2ª chamada e a falha é injetada na 3ª (não existe). Logo, o caso
    # coberto é: pendência criada no turno e modelo falhando no mesmo turno => 200 com a pendência.
    llm.falhar_apos_pedido = True
    c = _msg(cliente, sid, "Reserve o salão de festas para 2030-04-20.")
    assert len(c["confirmacoes_pendentes"]) == 1 and c["resposta"]


async def test_lock_cancelado_na_espera_nao_vaza():
    infra = modulo_app.Infra(session_service=None, runner=None)
    segurando = asyncio.Event()

    async def a():
        async with modulo_app._LockDaSessao(infra, "s"):
            segurando.set()
            await asyncio.sleep(0.05)

    async def b():
        async with modulo_app._LockDaSessao(infra, "s"):
            pass

    ta = asyncio.create_task(a())
    await segurando.wait()
    tb = asyncio.create_task(b())
    await asyncio.sleep(0.01)
    tb.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tb
    await ta
    assert infra.locks == {}
