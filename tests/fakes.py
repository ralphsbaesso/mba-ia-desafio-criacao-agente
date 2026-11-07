"""Dublês leves usados nos testes unitários."""

from __future__ import annotations

from types import SimpleNamespace

from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.tools.tool_confirmation import ToolConfirmation
from google.genai import types


class ToolContextFalso:
    """Imita a parte do ToolContext que as tools usam."""

    def __init__(self, apartamento: str | None = "101", confirmed: bool | None = None, events=None):
        self.state = {} if apartamento is None else {"apartamento": apartamento}
        self.actions = EventActions()
        self.tool_confirmation = None if confirmed is None else ToolConfirmation(confirmed=confirmed)
        self.function_call_id = "fc-1"
        self.session = SimpleNamespace(events=list(events or []))
        self.pedidos: list[dict] = []

    def request_confirmation(self, *, hint: str | None = None, payload=None) -> None:
        self.actions.requested_tool_confirmations[self.function_call_id] = ToolConfirmation(
            hint=hint or "", payload=payload
        )
        self.pedidos.append({"hint": hint, "payload": payload})


def evento_chamada(author: str, nome: str, args: dict, fc_id: str) -> Event:
    return Event(
        author=author,
        invocation_id="inv",
        content=types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(id=fc_id, name=nome, args=args))]),
    )


def evento_resposta(author: str, nome: str, resposta: dict, fc_id: str) -> Event:
    return Event(
        author=author,
        invocation_id="inv",
        content=types.Content(
            role="user" if author == "user" else "model",
            parts=[types.Part(function_response=types.FunctionResponse(id=fc_id, name=nome, response=resposta))],
        ),
    )


def evento_pedido_confirmacao(author: str, pedido_id: str, original_id: str, original_nome: str, original_args: dict, payload: dict) -> Event:
    return evento_chamada(
        author,
        "adk_request_confirmation",
        {
            "originalFunctionCall": {"id": original_id, "name": original_nome, "args": original_args},
            "toolConfirmation": {"hint": "x", "confirmed": False, "payload": payload},
        },
        pedido_id,
    )
