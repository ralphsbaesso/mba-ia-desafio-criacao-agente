"""Scripts de linha de comando: aurora-api e aurora-restaurar."""

from __future__ import annotations


def api() -> None:
    import uvicorn

    from aurora import config

    uvicorn.run("aurora.api.app:app", host=config.host(), port=config.porta())


def restaurar() -> None:
    from aurora.storage import repositorio

    repositorio.restaurar()
    print("Dados iniciais restaurados e sessões limpas.")
