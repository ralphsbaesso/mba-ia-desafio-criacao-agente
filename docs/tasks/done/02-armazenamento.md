# Task 02: Banco SQLite do condomínio
Spec: `docs/specs/02-armazenamento.md`, `docs/specs/09-concorrencia.md`
- [x] `aurora/storage/db.py` (conexão, esquema com CHECK/UNIQUE, índice único parcial, meta.seed)
- [x] `aurora/storage/repositorio.py` com todas as funções da spec (código RSV-6 chars, IntegrityError distinguido, idempotência por apartamento)
- [x] `aurora/storage/dados_iniciais.py` lendo `dados/`
- [x] `restaurar()` limpa tabelas do `sessoes.db` sem apagar o arquivo
- [x] testes: dados iniciais, clone limpo, colisão de código, código nunca repete, seed único, concorrência (10 threads)
