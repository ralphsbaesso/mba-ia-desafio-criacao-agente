"""Tools de reservas e visitantes.

Garantia 2: nenhuma tool recebe o apartamento como parâmetro. Ele vem sempre
de ``tool_context.state["apartamento"]``, gravado pela API na criação da
sessão. Garantia 1: cobrança (área com taxa) e liberação de acesso
(visitante) só executam com ``tool_context.tool_confirmation.confirmed``,
que o ADK preenche apenas quando a resposta chega pela rota de confirmações.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any

from google.adk.tools.tool_context import ToolContext

from aurora import confirmacoes
from aurora.storage import dados_iniciais, repositorio

ERRO_DATA = "Use a data no formato AAAA-MM-DD."
MOTIVO_OCUPADA = "A data já está reservada para essa área."


class EntradaInvalida(Exception):
    pass


def _texto(valor: Any) -> str:
    """Argumentos vêm do modelo e podem chegar com tipo errado (número, lista, None)."""
    if valor is None:
        return ""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        valor = str(valor)
    if not isinstance(valor, str):
        raise EntradaInvalida("Valor inválido: informe um texto.")
    return valor


def _sem_acentos(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in base if not unicodedata.combining(c)).casefold().strip()


def normalizar_data(texto: str) -> str:
    texto = _texto(texto).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto, re.ASCII):
        raise EntradaInvalida(ERRO_DATA)
    try:
        return date.fromisoformat(texto).isoformat()
    except ValueError:
        raise EntradaInvalida(ERRO_DATA) from None


def normalizar_area(texto: str) -> dict:
    chave = _sem_acentos(_texto(texto))
    for area in dados_iniciais.areas():
        if chave in (area["id"], _sem_acentos(area["nome"])):
            return area
    ids = ", ".join(a["id"] for a in dados_iniciais.areas())
    raise EntradaInvalida(f"Área desconhecida. Use uma destas: {ids}.")


def normalizar_nome(texto: str) -> str:
    nome = " ".join(unicodedata.normalize("NFC", _texto(texto)).split())
    if not 2 <= len(nome) <= 80 or any(unicodedata.category(c).startswith("C") for c in nome):
        raise EntradaInvalida("Informe o nome completo do visitante (2 a 80 caracteres).")
    return nome


def _apartamento(tool_context: ToolContext) -> str:
    apartamento = tool_context.state.get("apartamento")
    if not apartamento:
        raise EntradaInvalida("Sessão sem apartamento.")
    return str(apartamento)


def _pedir_confirmacao(tool_context: ToolContext, acao: str, detalhes: dict[str, Any]) -> dict[str, Any]:
    """Abre a pendência (ou reaproveita uma igual) e encerra o turno sem executar nada."""
    tool_context.actions.skip_summarization = True
    repetida = _ja_pedida(tool_context, acao, detalhes)
    if not repetida:
        tool_context.request_confirmation(
            hint=f"Confirme a ação {acao} pelo aplicativo.",
            payload={"acao": acao, **detalhes},
        )
    return {"status": "aguardando_confirmacao", "repetida": repetida, **detalhes}


def _ja_pedida(tool_context: ToolContext, acao: str, detalhes: dict[str, Any]) -> bool:
    for pedido in tool_context.actions.requested_tool_confirmations.values():
        payload = pedido.payload or {}
        if isinstance(payload, dict) and payload.get("acao") == acao and {
            k: v for k, v in payload.items() if k != "acao"
        } == detalhes:
            return True
    return confirmacoes.existe_pendencia_igual(tool_context.session.events, acao, detalhes)


def _confirmado(tool_context: ToolContext) -> bool | None:
    """None: ainda não pediu; True/False: resposta do morador pela rota de confirmações."""
    conf = tool_context.tool_confirmation
    return None if conf is None else bool(conf.confirmed)


def listar_minhas_reservas(tool_context: ToolContext) -> dict:
    """Lista as reservas ativas do apartamento do morador desta sessão."""
    try:
        apartamento = _apartamento(tool_context)
    except EntradaInvalida as e:
        return {"erro": str(e)}
    reservas = []
    for r in repositorio.listar_reservas(apartamento):
        area = dados_iniciais.area_por_id(r["area"]) or {}
        reservas.append({**r, "nome_area": area.get("nome", r["area"])})
    return {"reservas": reservas}


def verificar_disponibilidade(area: str, data: str, tool_context: ToolContext) -> dict:
    """Informa se uma área comum está livre em uma data (AAAA-MM-DD) e qual é a taxa.

    Args:
        area: id ou nome da área (salao-de-festas, churrasqueira, quadra).
        data: data desejada no formato AAAA-MM-DD.
    """
    try:
        _apartamento(tool_context)
        a = normalizar_area(area)
        d = normalizar_data(data)
    except EntradaInvalida as e:
        return {"erro": str(e)}
    return {
        "area": a["id"],
        "nome_area": a["nome"],
        "data": d,
        "disponivel": repositorio.data_disponivel(a["id"], d),
        "taxa": a["taxa"],
    }


def reservar_area(area: str, data: str, tool_context: ToolContext) -> dict:
    """Reserva uma área comum para o apartamento do morador em uma data (AAAA-MM-DD).

    Área com taxa gera cobrança e fica pendente até o morador confirmar pelo aplicativo.

    Args:
        area: id ou nome da área (salao-de-festas, churrasqueira, quadra).
        data: data desejada no formato AAAA-MM-DD.
    """
    try:
        apartamento = _apartamento(tool_context)
        a = normalizar_area(area)
        d = normalizar_data(data)
    except EntradaInvalida as e:
        return {"erro": str(e)}

    situacao, codigo = repositorio.situacao_data(apartamento, a["id"], d)
    if situacao == "outra":
        return {"ok": False, "motivo": MOTIVO_OCUPADA, "area": a["id"], "data": d}
    if situacao == "propria":
        return {"ok": True, "ja_existia": True, "codigo": codigo, "area": a["id"], "nome_area": a["nome"], "data": d}

    detalhes = {"area": a["id"], "nome_area": a["nome"], "data": d, "taxa": a["taxa"]}
    if a["taxa"] > 0:
        confirmado = _confirmado(tool_context)
        if confirmado is None:
            return _pedir_confirmacao(tool_context, "reservar_area", detalhes)
        if not confirmado:
            return {"ok": False, "motivo": "Reserva não confirmada pelo morador.", **detalhes}

    resultado = repositorio.criar_reserva(apartamento, a["id"], d)
    if not resultado.ok:
        return {"ok": False, "motivo": MOTIVO_OCUPADA, "area": a["id"], "data": d}
    return {"ok": True, "codigo": resultado.codigo, "ja_existia": resultado.ja_existia, **detalhes}


def cancelar_reserva(codigo: str = "", area: str = "", data: str = "", tool_context: ToolContext = None) -> dict:
    """Cancela uma reserva do próprio apartamento, pelo código ou pela área e data.

    Args:
        codigo: código da reserva (ex.: RSV-1377). Opcional se área e data forem informadas.
        area: id ou nome da área. Use junto com data.
        data: data da reserva no formato AAAA-MM-DD. Use junto com área.
    """
    try:
        apartamento = _apartamento(tool_context)
        codigo = _texto(codigo).strip().upper()
        if codigo:
            cancelada = repositorio.cancelar_reserva(apartamento, codigo=codigo)
        elif area and data:
            a = normalizar_area(area)
            d = normalizar_data(data)
            cancelada = repositorio.cancelar_reserva(apartamento, area=a["id"], data=d)
        else:
            return {"ok": False, "motivo": "Informe o código da reserva ou a área e a data."}
    except EntradaInvalida as e:
        return {"erro": str(e)}
    if cancelada is None:
        return {"ok": False, "motivo": "Não encontrei essa reserva entre as suas."}
    return {"ok": True, "cancelada": cancelada}


def listar_meus_visitantes(tool_context: ToolContext) -> dict:
    """Lista os visitantes autorizados pelo apartamento do morador desta sessão."""
    try:
        apartamento = _apartamento(tool_context)
    except EntradaInvalida as e:
        return {"erro": str(e)}
    return {"visitantes": repositorio.listar_visitantes(apartamento)}


def autorizar_visitante(nome: str, data: str, tool_context: ToolContext) -> dict:
    """Autoriza a entrada de um visitante em uma data (AAAA-MM-DD).

    Liberar acesso sempre fica pendente até o morador confirmar pelo aplicativo.

    Args:
        nome: nome completo do visitante.
        data: data da visita no formato AAAA-MM-DD.
    """
    try:
        apartamento = _apartamento(tool_context)
        n = normalizar_nome(nome)
        d = normalizar_data(data)
    except EntradaInvalida as e:
        return {"erro": str(e)}
    detalhes = {"nome": n, "data": d}
    confirmado = _confirmado(tool_context)
    if confirmado is None:
        return _pedir_confirmacao(tool_context, "autorizar_visitante", detalhes)
    if not confirmado:
        return {"ok": False, "motivo": "Autorização não confirmada pelo morador.", **detalhes}
    repositorio.autorizar_visitante(apartamento, n, d)
    return {"ok": True, **detalhes}


TOOLS_RESERVAS = [listar_minhas_reservas, verificar_disponibilidade, reservar_area, cancelar_reserva]
TOOLS_VISITANTES = [listar_meus_visitantes, autorizar_visitante]
