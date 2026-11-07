# Task 01: Estrutura do projeto e stack
Spec: `docs/specs/01-projeto-e-stack.md`
- [x] `pyproject.toml` com build-system hatchling, `google-adk==2.14.0`, fastapi, uvicorn, python-dotenv; dev: pytest, pytest-asyncio, httpx; scripts `aurora-api` e `aurora-restaurar`
- [x] `uv sync` gera `uv.lock`
- [x] `.env.example` só com nomes, valores vazios, `.gitignore` com `var/`
- [x] `aurora/config.py` com load_dotenv, RAIZ, funções de caminho, `or padrao`, `garantir_diretorios()`; `tests/conftest.py` com AURORA_DATA_DIR em tmp_path
- [x] teste de config com valor vazio
