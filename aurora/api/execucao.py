"""Execução de um turno do assistente e montagem da resposta da API."""

from __future__ import annotations

import logging
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions.base_session_service import BaseSessionService
from google.genai import types

from aurora import confirmacoes
from aurora.api.schemas import Pendencia, RespostaMensagem

log = logging.getLogger("aurora.api")

TOOLS_DE_ESCRITA = {"reservar_area", "cancelar_reserva", "autorizar_visitante"}
TEXTO_AGUARDANDO = "Seu pedido aguarda confirmação pelo aplicativo."


class FalhaDoModelo(Exception):
    """O modelo falhou e nenhuma ação foi executada neste turno."""


def _texto(event: Any) -> str:
    if not event.content or not event.content.parts:
        return ""
    return "".join(p.text or "" for p in event.content.parts if p.text and not getattr(p, "thought", False))


def _resposta_da_tool(fr: types.FunctionResponse) -> str:
    r = fr.response or {}
    if r.get("erro"):
        return str(r["erro"])
    if r.get("status") == "aguardando_confirmacao":
        return TEXTO_AGUARDANDO
    if fr.name == "reservar_area":
        if r.get("ok"):
            return f"Reserva confirmada: {r.get('nome_area', r.get('area'))} em {r.get('data')}, código {r.get('codigo')}."
        return f"Reserva não realizada. {r.get('motivo', '')}".strip()
    if fr.name == "cancelar_reserva":
        if r.get("ok"):
            c = r.get("cancelada") or {}
            return f"Reserva {c.get('codigo')} cancelada."
        return f"Cancelamento não realizado. {r.get('motivo', '')}".strip()
    if fr.name == "autorizar_visitante":
        if r.get("ok"):
            return f"Entrada de {r.get('nome')} autorizada para {r.get('data')}."
        return f"Autorização não realizada. {r.get('motivo', '')}".strip()
    return ""


def _efeitos_apos(eventos: list[Any], a_partir_de: int) -> list[str]:
    """Textos das tools de escrita que rodaram (sem placeholder) depois do índice dado."""
    textos = []
    for ev in eventos[a_partir_de:]:
        if ev.author == "user" or not ev.content:
            continue
        for fr in ev.get_function_responses():
            if fr.name in TOOLS_DE_ESCRITA and (fr.response or {}).get("status") != "aguardando_confirmacao":
                textos.append(_resposta_da_tool(fr))
    return [t for t in textos if t]


async def executar(
    runner: Runner,
    session_service: BaseSessionService,
    apartamento: str,
    session_id: str,
    new_message: types.Content,
) -> RespostaMensagem:
    """Roda um turno. Lança FalhaDoModelo só se o modelo falhou sem nenhuma ação executada."""
    app_name = runner.app_name
    antes = await session_service.get_session(app_name=app_name, user_id=apartamento, session_id=session_id)
    n_antes = len(antes.events) if antes else 0
    pendentes_antes = confirmacoes.ids_pendentes(antes.events) if antes else set()

    resposta = ""
    erro: Exception | None = None
    try:
        async for event in runner.run_async(user_id=apartamento, session_id=session_id, new_message=new_message):
            if event.is_final_response():
                texto = _texto(event)
                if texto:
                    resposta = texto
    except Exception as e:  # noqa: BLE001 - qualquer falha do modelo/rede é tratada abaixo
        erro = e
        log.warning("Falha na execução do turno da sessão %s: %s", session_id, e)

    sessao = await session_service.get_session(app_name=app_name, user_id=apartamento, session_id=session_id)
    eventos = list(sessao.events) if sessao else []
    pendencias = confirmacoes.pendentes(eventos)

    pendencia_nova = bool({p.id for p in pendencias} - pendentes_antes)
    if erro is not None:
        efeitos = _efeitos_apos(eventos, n_antes)
        if efeitos:
            resposta = " ".join(efeitos)
        elif pendencia_nova:
            resposta = TEXTO_AGUARDANDO  # o pedido de confirmação já foi gravado
        else:
            raise FalhaDoModelo(str(erro)) from erro
    elif not resposta:
        resposta = TEXTO_AGUARDANDO if pendencia_nova else " ".join(_efeitos_apos(eventos, n_antes))

    return RespostaMensagem(
        resposta=resposta,
        confirmacoes_pendentes=[Pendencia(**p.como_dict()) for p in pendencias],
    )
