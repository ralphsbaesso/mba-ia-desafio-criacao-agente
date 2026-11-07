import pytest

from aurora.agents import tools
from aurora.storage import repositorio
from tests.fakes import ToolContextFalso, evento_pedido_confirmacao, evento_resposta


@pytest.fixture(autouse=True)
def banco():
    repositorio.restaurar()


def test_nenhuma_tool_aceita_apartamento():
    import inspect

    for f in tools.TOOLS_RESERVAS + tools.TOOLS_VISITANTES:
        assert "apartamento" not in inspect.signature(f).parameters
        assert "tool_context" in inspect.signature(f).parameters


def test_sem_apartamento_na_sessao_nada_executa():
    ctx = ToolContextFalso(apartamento=None)
    assert tools.listar_minhas_reservas(ctx) == {"erro": "Sessão sem apartamento."}
    assert "erro" in tools.reservar_area("quadra", "2030-04-06", ctx)
    assert "erro" in tools.autorizar_visitante("Joana Ribeiro", "2030-04-21", ctx)
    assert repositorio.listar_reservas("101") == [{"codigo": "RSV-1377", "area": "quadra", "data": "2030-03-09"}]


def test_listar_so_do_proprio_apartamento():
    r = tools.listar_minhas_reservas(ToolContextFalso("101"))
    assert r == {"reservas": [{"codigo": "RSV-1377", "area": "quadra", "data": "2030-03-09", "nome_area": "Quadra poliesportiva"}]}
    assert tools.listar_meus_visitantes(ToolContextFalso("101")) == {"visitantes": []}
    assert tools.listar_meus_visitantes(ToolContextFalso("302")) == {"visitantes": [{"nome": "Marina Duarte", "data": "2030-03-16"}]}


def test_disponibilidade_nao_revela_dono():
    r = tools.verificar_disponibilidade("Salão de festas", "2030-03-16", ToolContextFalso("101"))
    assert r == {"area": "salao-de-festas", "nome_area": "Salão de festas", "data": "2030-03-16", "disponivel": False, "taxa": 150.0}
    assert "302" not in str(r) and "RSV" not in str(r)


@pytest.mark.parametrize("data", ["20300406", "2030-W16-7", "06/04/2030", "2030-02-30", "2030-04-06 x", "２０３０-04-06"])
def test_data_nao_canonica_recusada(data):
    ctx = ToolContextFalso("101")
    assert tools.reservar_area("quadra", data, ctx) == {"erro": tools.ERRO_DATA}
    assert ctx.pedidos == []


def test_area_desconhecida():
    r = tools.reservar_area("piscina", "2030-04-06", ToolContextFalso("101"))
    assert "Área desconhecida" in r["erro"] and "salao-de-festas" in r["erro"]


def test_quadra_sem_taxa_reserva_direto():
    ctx = ToolContextFalso("101")
    r = tools.reservar_area("quadra", "2030-04-06", ctx)
    assert r["ok"] and r["codigo"].startswith("RSV-") and ctx.pedidos == []
    assert not ctx.actions.skip_summarization
    assert {x["data"] for x in repositorio.listar_reservas("101")} == {"2030-03-09", "2030-04-06"}


def test_salao_pede_confirmacao_e_nao_grava():
    ctx = ToolContextFalso("101")
    r = tools.reservar_area("Salão de festas", "2030-04-20", ctx)
    assert r["status"] == "aguardando_confirmacao" and r["repetida"] is False
    assert ctx.pedidos[0]["payload"] == {"acao": "reservar_area", "area": "salao-de-festas", "nome_area": "Salão de festas", "data": "2030-04-20", "taxa": 150.0}
    assert ctx.actions.skip_summarization is True
    assert len(repositorio.listar_reservas("101")) == 1


def test_salao_negado_nao_grava():
    r = tools.reservar_area("salao-de-festas", "2030-04-20", ToolContextFalso("101", confirmed=False))
    assert r["ok"] is False and len(repositorio.listar_reservas("101")) == 1


def test_salao_confirmado_grava_uma_vez():
    ctx = ToolContextFalso("101", confirmed=True)
    r = tools.reservar_area("salao-de-festas", "2030-04-20", ctx)
    assert r["ok"] and r["codigo"].startswith("RSV-") and ctx.pedidos == []
    assert [x for x in repositorio.listar_reservas("101") if x["area"] == "salao-de-festas"] == [{"codigo": r["codigo"], "area": "salao-de-festas", "data": "2030-04-20"}]


def test_data_ocupada_por_outro_recusa_sem_confirmacao():
    ctx = ToolContextFalso("101")
    r = tools.reservar_area("salao-de-festas", "2030-03-16", ctx)
    assert r == {"ok": False, "motivo": tools.MOTIVO_OCUPADA, "area": "salao-de-festas", "data": "2030-03-16"}
    assert ctx.pedidos == [] and "302" not in str(r)


def test_reserva_propria_repetida_nao_pede_confirmacao():
    ctx = ToolContextFalso("302")
    r = tools.reservar_area("salao-de-festas", "2030-03-16", ctx)
    assert r["ok"] and r["ja_existia"] and r["codigo"] == "RSV-4821" and ctx.pedidos == []


def test_pendencia_igual_na_sessao_nao_duplica():
    eventos = [
        evento_resposta("reservas", "reservar_area", {"status": "aguardando_confirmacao"}, "o1"),
        evento_pedido_confirmacao("reservas", "p1", "o1", "reservar_area", {}, {"acao": "reservar_area", "area": "salao-de-festas", "nome_area": "Salão de festas", "data": "2030-04-20", "taxa": 150.0}),
    ]
    ctx = ToolContextFalso("101", events=eventos)
    r = tools.reservar_area("salao-de-festas", "2030-04-20", ctx)
    assert r["status"] == "aguardando_confirmacao" and r["repetida"] is True
    assert ctx.pedidos == [] and ctx.actions.skip_summarization is True


def test_pendencia_igual_na_mesma_invocacao_nao_duplica():
    ctx = ToolContextFalso("101")
    tools.autorizar_visitante("Joana Ribeiro", "2030-04-21", ctx)
    ctx.function_call_id = "fc-2"
    r = tools.autorizar_visitante("Joana Ribeiro", "2030-04-21", ctx)
    assert r["repetida"] is True and len(ctx.pedidos) == 1


def test_cancelar_so_as_proprias():
    ctx = ToolContextFalso("101")
    r = tools.cancelar_reserva(area="salão de festas", data="2030-03-16", tool_context=ctx)
    assert r == {"ok": False, "motivo": "Não encontrei essa reserva entre as suas."}
    assert "RSV-4821" not in str(r)
    assert [x["codigo"] for x in repositorio.listar_reservas("302")] == ["RSV-4821"]
    r = tools.cancelar_reserva(area="quadra", data="2030-03-09", tool_context=ctx)
    assert r["ok"] and r["cancelada"]["codigo"] == "RSV-1377" and ctx.pedidos == []
    assert repositorio.listar_reservas("101") == []


def test_cancelar_por_codigo_de_outro_apartamento():
    r = tools.cancelar_reserva(codigo="rsv-4821", tool_context=ToolContextFalso("101"))
    assert r["ok"] is False and [x["codigo"] for x in repositorio.listar_reservas("302")] == ["RSV-4821"]


def test_cancelar_exige_chave_completa():
    tools.reservar_area("quadra", "2030-04-06", ToolContextFalso("101"))
    ctx = ToolContextFalso("101")
    assert tools.cancelar_reserva(tool_context=ctx)["ok"] is False
    assert tools.cancelar_reserva(area="quadra", tool_context=ctx)["ok"] is False
    assert len(repositorio.listar_reservas("101")) == 2


def test_visitante_sempre_pede_confirmacao():
    ctx = ToolContextFalso("101")
    r = tools.autorizar_visitante("Joana  Ribeiro", "2030-04-21", ctx)
    assert r["status"] == "aguardando_confirmacao"
    assert ctx.pedidos[0]["payload"] == {"acao": "autorizar_visitante", "nome": "Joana Ribeiro", "data": "2030-04-21"}
    assert repositorio.listar_visitantes("101") == []


def test_visitante_negado_e_confirmado():
    assert tools.autorizar_visitante("Joana Ribeiro", "2030-04-21", ToolContextFalso("101", confirmed=False))["ok"] is False
    assert repositorio.listar_visitantes("101") == []
    r = tools.autorizar_visitante("Joana Ribeiro", "2030-04-21", ToolContextFalso("101", confirmed=True))
    assert r == {"ok": True, "nome": "Joana Ribeiro", "data": "2030-04-21"}
    tools.autorizar_visitante("Joana Ribeiro", "2030-04-21", ToolContextFalso("101", confirmed=True))
    assert repositorio.listar_visitantes("101") == [{"nome": "Joana Ribeiro", "data": "2030-04-21"}]


@pytest.mark.parametrize("nome", ["", "J", "x" * 81, "Joana\x00Ribeiro"])
def test_nome_invalido(nome):
    ctx = ToolContextFalso("101")
    assert "erro" in tools.autorizar_visitante(nome, "2030-04-21", ctx) and ctx.pedidos == []


@pytest.mark.parametrize(
    "chamada",
    [
        lambda ctx: tools.reservar_area(123, 20300420, ctx),
        lambda ctx: tools.reservar_area(["quadra"], "2030-04-06", ctx),
        lambda ctx: tools.autorizar_visitante(["x"], 1, ctx),
        lambda ctx: tools.autorizar_visitante(None, None, ctx),
        lambda ctx: tools.cancelar_reserva(codigo=123, tool_context=ctx),
        lambda ctx: tools.verificar_disponibilidade({"a": 1}, "2030-04-06", ctx),
    ],
)
def test_tipos_errados_nao_derrubam_o_turno(chamada):
    ctx = ToolContextFalso("101")
    r = chamada(ctx)
    assert "erro" in r or r.get("ok") is False
    assert ctx.pedidos == []
    assert repositorio.listar_reservas("101") == [{"codigo": "RSV-1377", "area": "quadra", "data": "2030-03-09"}]
