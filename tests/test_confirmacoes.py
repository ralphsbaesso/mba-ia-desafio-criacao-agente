from aurora import confirmacoes
from tests.fakes import evento_pedido_confirmacao, evento_resposta

PAYLOAD = {"acao": "reservar_area", "area": "salao-de-festas", "data": "2030-04-20", "taxa": 150.0}


def _pedido(pedido_id="p1", original_id="o1"):
    return [
        evento_resposta("reservas", "reservar_area", {"status": "aguardando_confirmacao"}, original_id),
        evento_pedido_confirmacao("reservas", pedido_id, original_id, "reservar_area", {"area": "salao-de-festas", "data": "2030-04-20"}, PAYLOAD),
    ]


def test_pedido_sem_resposta_fica_pendente():
    p = confirmacoes.pendentes(_pedido())
    assert [x.como_dict() for x in p] == [
        {"id": "p1", "acao": "reservar_area", "detalhes": {"area": "salao-de-festas", "data": "2030-04-20", "taxa": 150.0}}
    ]


def test_placeholder_antes_da_resposta_nao_fecha():
    eventos = _pedido()
    assert confirmacoes.ids_pendentes(eventos) == {"p1"}


def test_respondido_sem_execucao_da_tool_continua_pendente():
    eventos = _pedido() + [evento_resposta("user", "adk_request_confirmation", {"confirmed": True}, "p1")]
    assert confirmacoes.ids_pendentes(eventos) == {"p1"}


def test_respondido_e_executado_fecha():
    eventos = _pedido() + [
        evento_resposta("user", "adk_request_confirmation", {"confirmed": True}, "p1"),
        evento_resposta("reservas", "reservar_area", {"ok": True, "codigo": "RSV-AAAAAA"}, "o1"),
    ]
    assert confirmacoes.pendentes(eventos) == []


def test_negado_e_executado_fecha():
    eventos = _pedido() + [
        evento_resposta("user", "adk_request_confirmation", {"confirmed": False}, "p1"),
        evento_resposta("reservas", "reservar_area", {"ok": False}, "o1"),
    ]
    assert confirmacoes.pendentes(eventos) == []


def test_dois_pedidos_em_ordem():
    eventos = _pedido("p1", "o1") + _pedido("p2", "o2") + [
        evento_resposta("user", "adk_request_confirmation", {"confirmed": True}, "p1"),
        evento_resposta("reservas", "reservar_area", {"ok": True}, "o1"),
    ]
    assert [p.id for p in confirmacoes.pendentes(eventos)] == ["p2"]


def test_fallback_sem_payload_usa_chamada_original():
    ev = evento_pedido_confirmacao("visitantes", "p9", "o9", "autorizar_visitante", {"nome": "Joana", "data": "2030-04-21"}, None)
    p = confirmacoes.pendentes([ev])[0]
    assert p.acao == "autorizar_visitante" and p.detalhes == {"nome": "Joana", "data": "2030-04-21"}


def test_existe_pendencia_igual():
    eventos = _pedido()
    assert confirmacoes.existe_pendencia_igual(eventos, "reservar_area", {"area": "salao-de-festas", "data": "2030-04-20", "taxa": 150.0})
    assert not confirmacoes.existe_pendencia_igual(eventos, "reservar_area", {"area": "quadra", "data": "2030-04-20", "taxa": 0})


def test_resposta_do_usuario():
    c = confirmacoes.resposta_do_usuario("p1", True)
    fr = c.parts[0].function_response
    assert c.role == "user" and fr.id == "p1" and fr.name == "adk_request_confirmation" and fr.response == {"confirmed": True}
