"""Pendências de confirmação derivadas dos eventos da sessão.

Uma tool que precisa de aprovação chama ``request_confirmation``; o ADK grava
um evento do agente com uma ``function_call`` ``adk_request_confirmation``.
A pendência fica aberta até existir, depois dela, uma resposta do ``user``
com o mesmo id e, depois dessa resposta, a ``function_response`` da tool
original (a tool rodou, confirmada ou rejeitada). O placeholder gravado junto
com o pedido não conta. Como tudo vem dos eventos persistidos, o cálculo
sobrevive a reinícios e não depende de estado em memória.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from google.genai import types

NOME_PEDIDO = "adk_request_confirmation"


@dataclass(frozen=True)
class Pendencia:
    id: str
    acao: str
    detalhes: dict[str, Any]

    def como_dict(self) -> dict[str, Any]:
        return {"id": self.id, "acao": self.acao, "detalhes": self.detalhes}


def _chamadas(event: Any) -> list[types.FunctionCall]:
    return event.get_function_calls() if event.content else []


def _respostas(event: Any) -> list[types.FunctionResponse]:
    return event.get_function_responses() if event.content else []


def _montar(fc: types.FunctionCall) -> Pendencia:
    args = fc.args or {}
    original = args.get("originalFunctionCall") or {}
    confirmacao = args.get("toolConfirmation") or {}
    payload = confirmacao.get("payload")
    if isinstance(payload, dict) and payload:
        detalhes = dict(payload)
        acao = str(detalhes.pop("acao", original.get("name") or "acao"))
    else:
        acao = str(original.get("name") or "acao")
        detalhes = dict(original.get("args") or {})
    return Pendencia(id=fc.id or "", acao=acao, detalhes=detalhes)


def pendentes(events: Iterable[Any]) -> list[Pendencia]:
    """Lista, em ordem cronológica, as confirmações ainda não resolvidas."""
    eventos = list(events)
    pedidos: dict[str, tuple[int, types.FunctionCall, str | None]] = {}
    for i, ev in enumerate(eventos):
        for fc in _chamadas(ev):
            if fc.name == NOME_PEDIDO and fc.id:
                original_id = ((fc.args or {}).get("originalFunctionCall") or {}).get("id")
                pedidos[fc.id] = (i, fc, original_id)

    abertas: list[Pendencia] = []
    for pedido_id, (pos, fc, original_id) in sorted(pedidos.items(), key=lambda kv: kv[1][0]):
        pos_resposta_usuario: int | None = None
        for j in range(pos + 1, len(eventos)):
            ev = eventos[j]
            if ev.author == "user" and any(fr.id == pedido_id for fr in _respostas(ev)):
                pos_resposta_usuario = j
                break
        if pos_resposta_usuario is None:
            abertas.append(_montar(fc))
            continue
        executada = original_id is not None and any(
            fr.id == original_id
            for j in range(pos_resposta_usuario + 1, len(eventos))
            if eventos[j].author != "user"
            for fr in _respostas(eventos[j])
        )
        if not executada:
            abertas.append(_montar(fc))
    return abertas


def ids_pendentes(events: Iterable[Any]) -> set[str]:
    return {p.id for p in pendentes(events)}


def existe_pendencia_igual(events: Iterable[Any], acao: str, detalhes: dict[str, Any]) -> bool:
    return any(p.acao == acao and p.detalhes == detalhes for p in pendentes(events))


def resposta_do_usuario(pedido_id: str, confirmado: bool) -> types.Content:
    """Mensagem que devolve ao Runner a decisão do morador sobre uma pendência."""
    return types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=pedido_id,
                    name=NOME_PEDIDO,
                    response={"confirmed": confirmado},
                )
            )
        ],
    )
