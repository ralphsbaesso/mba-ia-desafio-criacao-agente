# Spec 10: Comandos, testes e README

## Comandos (documentados no README)
- `uv sync`
- Subir a API: `uv run aurora-api` (script em `pyproject.toml` → `aurora.cli:api`, que chama `uvicorn.run("aurora.api.app:app", host=config.host(), port=config.porta())`).
- Restaurar dados: `uv run aurora-restaurar` (→ `aurora.cli:restaurar`): recria reservas e visitantes a partir de `dados/` e limpa as sessões. Executar com a API parada.
- Testes: `uv run pytest`.

## README (`README.md`, substitui o enunciado)
Seções, nesta ordem:
1. **Detalhes do projeto**: propósito e stack.
2. **Arquitetura**: cada agente, responsabilidade, como é acionado e por quê (spec 05); diagrama em texto.
3. **Garantias**: para cada uma das cinco, arquivo e função/trecho que a implementa e por que não depende do modelo.
4. **Como rodar**: pré-requisitos, `.env`, subir, restaurar, testar.
5. Nota final: desafio do curso, link para `docs/INDEX.md`.

## Entrega
- Ao final, a branch de trabalho é mesclada em `main` (o enunciado exige tudo na `main`).

## Documentação
- `docs/INDEX.md` lista o enunciado, as specs, as tasks e os arquivos de dúvidas.

## Critérios de aceite
- Todo caminho citado na seção Garantias existe (`tests/test_readme.py`).
