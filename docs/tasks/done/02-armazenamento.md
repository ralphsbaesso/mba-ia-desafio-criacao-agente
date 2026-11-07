# Task 02: Banco SQLite do condomínio
Spec: `docs/specs/02-armazenamento.md`, `docs/specs/09-concorrencia.md`
- [ ] `aurora/storage/db.py` (conexão, esquema com CHECK/UNIQUE, índice único parcial, meta.seed)
- [ ] `aurora/storage/repositorio.py` com todas as funções da spec (código RSV-6 chars, IntegrityError distinguido, idempotência por apartamento)
- [ ] `aurora/storage/dados_iniciais.py` lendo `dados/`
- [ ] `restaurar()` limpa tabelas do `sessoes.db` sem apagar o arquivo
- [ ] testes: dados iniciais, clone limpo, colisão de código, código nunca repete, seed único, concorrência (10 threads)
