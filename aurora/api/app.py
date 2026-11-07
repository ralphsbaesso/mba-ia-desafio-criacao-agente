"""API HTTP do assistente do Residencial Aurora.

Contrato: POST /sessoes, POST /sessoes/{id}/mensagens, POST /sessoes/{id}/confirmacoes,
GET /sessoes/{id}/eventos, GET /apartamentos/{n}/reservas, GET /apartamentos/{n}/visitantes.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException, Request
from google.adk.runners import Runner
from google.adk.sessions.base_session_service import BaseSessionService
from google.adk.sessions.session import Session
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.genai import types

from aurora import config, confirmacoes
from aurora.agents.app import APP_NAME, criar_app
from aurora.api import execucao
from aurora.api.schemas import (
    CriarSessao,
    Mensagem,
    Reserva,
    RespostaConfirmacao,
    RespostaMensagem,
    SessaoCriada,
    Visitante,
)
from aurora.storage import dados_iniciais, db, repositorio

log = logging.getLogger("aurora.api")


@dataclass
class Infra:
    session_service: BaseSessionService
    runner: Runner
    locks: dict[str, tuple[asyncio.Lock, int]] = field(default_factory=dict)


def criar_infra(session_service: BaseSessionService | None = None, runner: Runner | None = None) -> Infra:
    session_service = session_service or SqliteSessionService(str(config.db_sessoes()))
    runner = runner or Runner(app=criar_app(), session_service=session_service)
    return Infra(session_service=session_service, runner=runner)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.garantir_diretorios()
    db.inicializar()
    if not config.api_key_configurada():
        log.warning("GOOGLE_API_KEY não configurada: as chamadas ao modelo vão falhar.")
    if getattr(app.state, "infra", None) is None:
        app.state.infra = criar_infra()
    try:
        yield
    finally:
        await app.state.infra.runner.close()


app = FastAPI(title="Assistente do Residencial Aurora", lifespan=lifespan)


def _infra(request: Request) -> Infra:
    return request.app.state.infra


class _LockDaSessao:
    """Serializa as requisições de uma mesma sessão; sessões diferentes rodam em paralelo."""

    def __init__(self, infra: Infra, session_id: str):
        self.infra, self.session_id = infra, session_id

    def _liberar_referencia(self) -> None:
        lock, n = self.infra.locks[self.session_id]
        if n <= 1:
            del self.infra.locks[self.session_id]
        else:
            self.infra.locks[self.session_id] = (lock, n - 1)

    async def __aenter__(self):
        lock, n = self.infra.locks.get(self.session_id, (asyncio.Lock(), 0))
        self.infra.locks[self.session_id] = (lock, n + 1)
        self.lock = lock
        try:
            await lock.acquire()
        except BaseException:
            self._liberar_referencia()  # cancelado enquanto esperava: não vaza a entrada
            raise

    async def __aexit__(self, *exc):
        self.lock.release()
        self._liberar_referencia()


async def _carregar_sessao(infra: Infra, session_id: str) -> tuple[str, Session]:
    apartamento = await asyncio.to_thread(repositorio.apartamento_da_sessao, session_id)
    sessao = None
    if apartamento:
        sessao = await infra.session_service.get_session(app_name=APP_NAME, user_id=apartamento, session_id=session_id)
    if not apartamento or sessao is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    return apartamento, sessao


async def _executar(infra: Infra, apartamento: str, session_id: str, conteudo: types.Content) -> RespostaMensagem:
    try:
        return await execucao.executar(infra.runner, infra.session_service, apartamento, session_id, conteudo)
    except execucao.FalhaDoModelo:
        raise HTTPException(status_code=502, detail="Falha ao consultar o modelo. Tente novamente em instantes.")


@app.post("/sessoes", status_code=201, response_model=SessaoCriada)
async def criar_sessao(corpo: CriarSessao, request: Request) -> SessaoCriada:
    apartamento = corpo.apartamento.strip()
    if not dados_iniciais.apartamento_existe(apartamento):
        raise HTTPException(status_code=422, detail="Apartamento não cadastrado.")
    infra = _infra(request)
    session_id = str(uuid.uuid4())
    await infra.session_service.create_session(
        app_name=APP_NAME, user_id=apartamento, session_id=session_id, state={"apartamento": apartamento}
    )
    await asyncio.to_thread(repositorio.registrar_sessao, session_id, apartamento)
    return SessaoCriada(session_id=session_id)


@app.post("/sessoes/{session_id}/mensagens", response_model=RespostaMensagem)
async def enviar_mensagem(session_id: str, corpo: Mensagem, request: Request) -> RespostaMensagem:
    infra = _infra(request)
    async with _LockDaSessao(infra, session_id):
        apartamento, _ = await _carregar_sessao(infra, session_id)
        conteudo = types.Content(role="user", parts=[types.Part(text=corpo.texto)])
        return await _executar(infra, apartamento, session_id, conteudo)


@app.post("/sessoes/{session_id}/confirmacoes", response_model=RespostaMensagem)
async def responder_confirmacao(session_id: str, corpo: RespostaConfirmacao, request: Request) -> RespostaMensagem:
    infra = _infra(request)
    async with _LockDaSessao(infra, session_id):
        apartamento, sessao = await _carregar_sessao(infra, session_id)
        if corpo.id not in confirmacoes.ids_pendentes(sessao.events):
            raise HTTPException(status_code=409, detail="Não existe confirmação pendente com esse id nesta sessão.")
        conteudo = confirmacoes.resposta_do_usuario(corpo.id, corpo.confirmado)
        return await _executar(infra, apartamento, session_id, conteudo)


@app.get("/sessoes/{session_id}/eventos")
async def listar_eventos(session_id: str, request: Request) -> list[dict]:
    _, sessao = await _carregar_sessao(_infra(request), session_id)
    return [e.model_dump(mode="json", exclude_none=True) for e in sessao.events]


@app.get("/apartamentos/{apartamento}/reservas", response_model=list[Reserva])
async def reservas_do_apartamento(apartamento: str) -> list[Reserva]:
    return [Reserva(**r) for r in await asyncio.to_thread(repositorio.listar_reservas, apartamento)]


@app.get("/apartamentos/{apartamento}/visitantes", response_model=list[Visitante])
async def visitantes_do_apartamento(apartamento: str) -> list[Visitante]:
    return [Visitante(**v) for v in await asyncio.to_thread(repositorio.listar_visitantes, apartamento)]
