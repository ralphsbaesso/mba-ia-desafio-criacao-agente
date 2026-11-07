# Spec 01: Projeto e stack

## Objetivo
Definir a base do projeto Python gerenciado por `uv`, com a versão exata do Google ADK fixada e as variáveis de ambiente documentadas.

## Decisões
- Python `>=3.12`; `pyproject.toml` com `requires-python = ">=3.12"` e `uv.lock` versionado.
- `[build-system]` com `hatchling` e `[tool.hatch.build.targets.wheel] packages = ["aurora"]`, para que `uv sync` instale o pacote e os scripts de `[project.scripts]` (`aurora-api`, `aurora-restaurar`).
- Dependências: `google-adk==2.14.0` (pin exato, série 2, >= 2.2.0), `fastapi`, `uvicorn`, `python-dotenv`. `aiosqlite` já vem com o ADK; não é dependência direta.
- Dependências de desenvolvimento em `[dependency-groups] dev`: `pytest`, `pytest-asyncio` (`asyncio_mode = "auto"` em `[tool.pytest.ini_options]`), `httpx` (`TestClient`).
- Pacote da aplicação: `aurora/` na raiz do repositório.
- Modelo Gemini configurável por `GEMINI_MODEL` (padrão `gemini-3.5-flash`). O avaliador pode trocar sem mexer no código.

## Configuração (`aurora/config.py`)
- `RAIZ = Path(__file__).resolve().parents[1]`: todos os caminhos (`dados/`, `var/`) são relativos à raiz do repositório, nunca ao diretório atual.
- Primeira linha útil do módulo: `load_dotenv(RAIZ / ".env", override=False)`, antes de qualquer `os.getenv`. Vale para `aurora-api`, `aurora-restaurar` e testes, de qualquer diretório.
- Valor vazio de variável conta como ausente: `os.getenv(nome) or padrao`. Assim `cp .env.example .env` com linhas vazias mantém os padrões.
- `AURORA_DATA_DIR` (padrão `var`; caminho relativo é resolvido contra `RAIZ`) contém `aurora.db` (condomínio) e `sessoes.db` (sessões do ADK). `config.py` expõe **funções** lidas em tempo de chamada, `data_dir()`, `db_condominio()`, `db_sessoes()`, `modelo()`, e `garantir_diretorios()` (`mkdir(parents=True, exist_ok=True)`), chamado por `restaurar()` e pelo `lifespan` da API. Assim os testes redirecionam tudo com `monkeypatch.setenv("AURORA_DATA_DIR", tmp_path)` (fixture `autouse` em `tests/conftest.py`).
- `AURORA_HOST` (padrão `127.0.0.1`) e `AURORA_PORT` (padrão `8000`), expostos como `host()` e `porta()`, para o `aurora-api`.
- `GOOGLE_API_KEY` ausente: a API sobe e registra um aviso; a primeira chamada ao modelo falha com mensagem clara.

## Variáveis de ambiente (`.env.example`)
```
GOOGLE_API_KEY=
GOOGLE_GENAI_USE_VERTEXAI=
GEMINI_MODEL=
AURORA_DATA_DIR=
AURORA_HOST=
AURORA_PORT=
```
- Só nomes, sem valores (exigência do enunciado); vazio conta como ausente e cai no padrão (`FALSE`, `gemini-3.5-flash`, `var`).
- `var/` fica no `.gitignore`.

## Layout
```
aurora/
  __init__.py
  config.py
  confirmacoes.py  # pendências derivadas dos eventos (spec 06)
  storage/         # db.py, repositorio.py, dados_iniciais.py (spec 02)
  agents/          # tools.py, regulamento.py, fabrica.py, app.py (specs 04, 05, 08)
  api/             # app.py, schemas.py, execucao.py (spec 07)
  cli.py           # scripts aurora-api e aurora-restaurar (spec 10)
dados/             # intocado
docs/
tests/
```

## Critérios de aceite
- `uv sync` instala sem erro; `uv run aurora-restaurar` funciona num clone limpo (sem `var/`).
- `uv run python -c "import google.adk; print(google.adk.__version__)"` imprime `2.14.0`.
- `.env` está no `.gitignore`; `.env.example` só com nomes.
- Teste: `GEMINI_MODEL=""` no ambiente resulta no padrão.
- Teste: `.env` temporário na raiz é carregado mesmo com outro diretório atual.
