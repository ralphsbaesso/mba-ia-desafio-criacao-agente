"""App do ADK usado pela API e pelos testes de integração."""

from __future__ import annotations

from google.adk.apps import App
from google.adk.models.base_llm import BaseLlm

from aurora.agents.fabrica import criar_agentes

APP_NAME = "aurora"


def criar_app(model: str | BaseLlm | None = None) -> App:
    return App(name=APP_NAME, root_agent=criar_agentes(model))
