"""Modelos do contrato da API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CriarSessao(BaseModel):
    apartamento: str = Field(min_length=1, max_length=20)


class SessaoCriada(BaseModel):
    session_id: str


class Mensagem(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)


class RespostaConfirmacao(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    confirmado: bool


class Pendencia(BaseModel):
    id: str
    acao: str
    detalhes: dict[str, Any]


class RespostaMensagem(BaseModel):
    resposta: str
    confirmacoes_pendentes: list[Pendencia]


class Reserva(BaseModel):
    codigo: str
    area: str
    data: str


class Visitante(BaseModel):
    nome: str
    data: str
