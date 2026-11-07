import sqlite3
import threading

import pytest

from aurora import config
from aurora.storage import db, repositorio


@pytest.fixture
def banco():
    repositorio.restaurar()


def test_restaurar_em_clone_limpo_carrega_dados_iniciais(dados_em_tmp):
    assert not dados_em_tmp.exists()
    repositorio.restaurar()
    assert [r["codigo"] for r in repositorio.listar_reservas("101")] == ["RSV-1377"]
    assert repositorio.listar_visitantes("302") == [{"nome": "Marina Duarte", "data": "2030-03-16"}]


def test_inicializar_duas_vezes_nao_recarrega_seed(banco):
    repositorio.cancelar_reserva("101", codigo="RSV-1377")
    db.inicializar()
    db.inicializar()
    assert repositorio.listar_reservas("101") == []


def test_restaurar_volta_ao_estado_inicial(banco):
    repositorio.criar_reserva("101", "quadra", "2030-04-06")
    repositorio.cancelar_reserva("101", codigo="RSV-1377")
    repositorio.restaurar()
    assert [r["codigo"] for r in repositorio.listar_reservas("101")] == ["RSV-1377"]


def test_restaurar_tolera_sessoes_db_sem_tabelas(banco):
    config.db_sessoes().write_bytes(b"")
    repositorio.restaurar()
    conn = sqlite3.connect(config.db_sessoes())
    conn.executescript("CREATE TABLE sessions (id TEXT); CREATE TABLE events (id TEXT); INSERT INTO sessions VALUES ('a'); INSERT INTO events VALUES ('b');")
    conn.close()
    repositorio.restaurar()
    conn = sqlite3.connect(config.db_sessoes())
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
    conn.close()


def test_criar_reserva_e_disponibilidade(banco):
    assert repositorio.data_disponivel("quadra", "2030-04-06")
    r = repositorio.criar_reserva("101", "quadra", "2030-04-06")
    assert r.ok and r.codigo.startswith("RSV-") and len(r.codigo) == 10
    assert not repositorio.data_disponivel("quadra", "2030-04-06")
    assert repositorio.situacao_data("101", "quadra", "2030-04-06") == ("propria", r.codigo)
    assert repositorio.situacao_data("201", "quadra", "2030-04-06") == ("outra", None)
    assert repositorio.situacao_data("201", "quadra", "2030-04-07") == ("livre", None)


def test_data_ocupada_por_outro_apartamento(banco):
    r = repositorio.criar_reserva("101", "salao-de-festas", "2030-03-16")
    assert r == repositorio.Resultado(ok=False, motivo="ocupada")
    assert [x["codigo"] for x in repositorio.listar_reservas("302")] == ["RSV-4821"]


def test_reserva_propria_repetida_e_idempotente(banco):
    r1 = repositorio.criar_reserva("101", "quadra", "2030-04-06")
    r2 = repositorio.criar_reserva("101", "quadra", "2030-04-06")
    assert r2.ok and r2.ja_existia and r2.codigo == r1.codigo
    assert len(repositorio.listar_reservas("101")) == 2


def test_colisao_de_codigo_nao_vira_ocupada(banco, monkeypatch):
    codigos = iter(["RSV-1377", "RSV-NOVO01"])
    monkeypatch.setattr(repositorio, "gerar_codigo", lambda: next(codigos))
    r = repositorio.criar_reserva("101", "quadra", "2030-04-06")
    assert r.ok and r.codigo == "RSV-NOVO01"


def test_codigo_cancelado_nunca_se_repete(banco, monkeypatch):
    assert repositorio.cancelar_reserva("101", codigo="RSV-1377")["codigo"] == "RSV-1377"
    codigos = iter(["RSV-1377", "RSV-OUTRO1"])
    monkeypatch.setattr(repositorio, "gerar_codigo", lambda: next(codigos))
    r = repositorio.criar_reserva("101", "quadra", "2030-03-09")
    assert r.codigo == "RSV-OUTRO1"


def test_cancelar_so_do_proprio_apartamento(banco):
    assert repositorio.cancelar_reserva("101", codigo="RSV-4821") is None
    assert repositorio.cancelar_reserva("101", area="salao-de-festas", data="2030-03-16") is None
    assert [x["codigo"] for x in repositorio.listar_reservas("302")] == ["RSV-4821"]
    assert repositorio.cancelar_reserva("101", area="quadra", data="2030-03-09")["codigo"] == "RSV-1377"
    assert repositorio.listar_reservas("101") == []


def test_cancelar_exige_chave_completa(banco):
    repositorio.criar_reserva("101", "quadra", "2030-04-06")
    with pytest.raises(ValueError):
        repositorio.cancelar_reserva("101")
    with pytest.raises(ValueError):
        repositorio.cancelar_reserva("101", area="quadra")
    with pytest.raises(ValueError):
        repositorio.cancelar_reserva("101", data="2030-03-09")
    assert len(repositorio.listar_reservas("101")) == 2


def test_visitantes_sem_duplicata(banco):
    repositorio.autorizar_visitante("101", "Joana Ribeiro", "2030-04-21")
    repositorio.autorizar_visitante("101", "joana ribeiro", "2030-04-21")
    assert repositorio.listar_visitantes("101") == [{"nome": "Joana Ribeiro", "data": "2030-04-21"}]


def test_sessoes(banco):
    repositorio.registrar_sessao("s1", "101")
    assert repositorio.apartamento_da_sessao("s1") == "101"
    assert repositorio.apartamento_da_sessao("nao-existe") is None


@pytest.mark.parametrize("data", ["20300406", "2030-13-45", "2031-02-31", "2030-4-6"])
def test_data_invalida_rejeitada(banco, data):
    with pytest.raises(ValueError):
        repositorio.criar_reserva("101", "quadra", data)
    with pytest.raises(ValueError):
        repositorio.autorizar_visitante("101", "Alguém", data)


def test_area_desconhecida_rejeitada(banco):
    with pytest.raises(ValueError):
        repositorio.criar_reserva("101", "piscina", "2030-04-06")


def test_banco_rejeita_data_inexistente_direto(banco):
    with db.conectar() as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO reservas (codigo, apartamento, area, data) VALUES ('X', '101', 'quadra', '2030-02-31')")


def test_visitante_com_acento_nao_duplica(banco):
    repositorio.autorizar_visitante("101", "José  Álvares", "2030-04-21")
    repositorio.autorizar_visitante("101", "JOSE ALVARES", "2030-04-21")
    assert repositorio.listar_visitantes("101") == [{"nome": "José  Álvares", "data": "2030-04-21"}]


def test_cancelar_por_codigo_minusculo(banco):
    assert repositorio.cancelar_reserva("101", codigo="rsv-1377")["codigo"] == "RSV-1377"


async def test_restaurar_limpa_sessoes_reais_do_adk(banco):
    from google.adk.sessions.sqlite_session_service import SqliteSessionService

    servico = SqliteSessionService(str(config.db_sessoes()))
    s = await servico.create_session(app_name="aurora", user_id="101", state={"apartamento": "101"})
    assert await servico.get_session(app_name="aurora", user_id="101", session_id=s.id) is not None
    repositorio.restaurar()
    assert await servico.get_session(app_name="aurora", user_id="101", session_id=s.id) is None
    s2 = await servico.create_session(app_name="aurora", user_id="101")
    assert await servico.get_session(app_name="aurora", user_id="101", session_id=s2.id) is not None


def test_concorrencia_uma_unica_reserva(banco):
    resultados = []
    barreira = threading.Barrier(10)

    def tenta(apt):
        barreira.wait()
        resultados.append(repositorio.criar_reserva(apt, "salao-de-festas", "2030-05-11"))

    threads = [threading.Thread(target=tenta, args=(f"ap{i}",)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(1 for r in resultados if r.ok) == 1
    assert sum(1 for r in resultados if r.motivo == "ocupada") == 9
