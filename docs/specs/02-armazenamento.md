# Spec 02: Armazenamento dos dados do condomínio

## Objetivo
Guardar reservas e visitantes fora de `dados/` (que é imutável), com persistência entre reinícios e exclusividade de reserva garantida no instante da gravação (detalhes de concorrência na spec 09).

## Decisões
- Um banco SQLite em `config.db_condominio()`, acessado pelo módulo `aurora/storage/db.py` com `sqlite3` da biblioteca padrão. Conexão por operação, `timeout=10`, `isolation_level=None` (transações explícitas), `PRAGMA journal_mode=WAL`.
- Apartamentos, áreas e regulamento são lidos direto de `dados/` (somente leitura), nunca copiados para o banco.
- `db.inicializar()`: cria o diretório, as tabelas e os índices com `IF NOT EXISTS`, e, se a tabela `meta` não tiver a chave `seed`, carrega os dados iniciais e grava `seed=1`. Nunca decide por contagem de linhas.

## Esquema
```sql
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS reservas (
  codigo TEXT PRIMARY KEY,
  apartamento TEXT NOT NULL,
  area TEXT NOT NULL,
  data TEXT NOT NULL CHECK (data GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  status TEXT NOT NULL DEFAULT 'ativa' CHECK (status IN ('ativa', 'cancelada'))
);
CREATE UNIQUE INDEX IF NOT EXISTS reservas_area_data_ativa
  ON reservas(area, data) WHERE status = 'ativa';

CREATE TABLE IF NOT EXISTS visitantes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  apartamento TEXT NOT NULL,
  nome TEXT NOT NULL COLLATE NOCASE,
  data TEXT NOT NULL CHECK (data GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  UNIQUE (apartamento, nome, data)
);

CREATE TABLE IF NOT EXISTS sessoes (
  session_id TEXT PRIMARY KEY,
  apartamento TEXT NOT NULL,
  criada_em TEXT NOT NULL
);
```
- Reserva cancelada **não é apagada**: muda para `status='cancelada'`. O código continua ocupado e nunca se repete (regra de negócio 5).
- O índice único parcial é a Garantia 5: dois `INSERT` simultâneos para a mesma área e data só podem gravar um.
- `visitantes` com `UNIQUE` e `INSERT OR IGNORE`: aprovar duas vezes a mesma autorização não duplica.

## Código da reserva
- Formato `RSV-` + 6 caracteres de `[A-Z0-9]` sorteados com `secrets` (2 bilhões de combinações). A `PRIMARY KEY` é a verificação de colisão.
- `criar_reserva` distingue o `IntegrityError` pela mensagem: se contém `reservas.codigo`, sorteia outro código e repete o `INSERT` (até 5 vezes); se contém `reservas.area`, é data ocupada. Qualquer outra mensagem sobe como exceção.

## API do módulo (`aurora/storage/repositorio.py`)
Toda função recebe `apartamento` explicitamente; quem chama (tools) o obtém da sessão (spec 04). Datas sempre no formato canônico `AAAA-MM-DD` (as tools normalizam antes).
- `listar_reservas(apartamento) -> list[dict(codigo, area, data)]` (só ativas, ordenadas por data).
- `data_disponivel(area, data) -> bool`.
- `situacao_data(apartamento, area, data) -> "livre" | "propria" | "outra"` (se `propria`, inclui o `codigo`). Nunca expõe o apartamento dono.
- `criar_reserva(apartamento, area, data) -> Resultado(ok, codigo, motivo)`. Dentro de `BEGIN IMMEDIATE`: se já existe reserva ativa dessa área e data **do mesmo apartamento**, devolve `ok=True` com o código existente (idempotente); senão tenta o `INSERT` e trata `IntegrityError` como acima. `motivo="ocupada"` quando a reserva ativa é de outro apartamento.
- `cancelar_reserva(apartamento, codigo=None, area=None, data=None) -> dict | None`: exige `codigo` **ou** (`area` **e** `data`); caso contrário `ValueError`. `UPDATE ... WHERE apartamento=? AND status='ativa' AND codigo=?` (ou `AND area=? AND data=?`). Só uma reserva por chamada: se `rowcount != 1`, devolve `None`. Devolve a reserva cancelada.
- `listar_visitantes(apartamento) -> list[dict(nome, data)]`.
- `autorizar_visitante(apartamento, nome, data) -> None` (`INSERT OR IGNORE`). `nome` já normalizado pela tool (NFC, `strip`, espaços internos colapsados); a coluna usa `COLLATE NOCASE` na `UNIQUE`.
- `registrar_sessao(session_id, apartamento)`, `apartamento_da_sessao(session_id) -> str | None`.
- `restaurar()`: `garantir_diretorios()`, `inicializar()`, depois numa transação apaga `reservas`, `visitantes`, `sessoes` e `meta`, recarrega `dados/reservas.json` e `dados/visitantes.json` e grava `seed=1`.

## Restauração das sessões do ADK
- `restaurar()` **não apaga o arquivo** `sessoes.db` (o `SqliteSessionService` em execução ficaria sem tabelas). Se o arquivo existir, abre com `sqlite3`, lista as tabelas em `sqlite_master` e executa `DELETE FROM <tabela>` em cada uma, filhos antes de `sessions` (ignorando tabelas inexistentes, pois o ADK cria o esquema de forma preguiçosa). Ordem: primeiro sessões do ADK, depois o banco do condomínio.
- README documenta: rodar a restauração com a API parada.

## Critérios de aceite
- Após `restaurar()`, `listar_reservas("101")` devolve `RSV-1377` e `listar_visitantes("302")` devolve Marina Duarte.
- Teste: `restaurar()` em diretório temporário sem `var/` funciona.
- Teste: colisão forçada de código (monkeypatch do gerador) não vira "ocupada".
- Teste: código de reserva cancelada nunca é reutilizado.
- Teste: `inicializar()` chamado duas vezes não recarrega o seed.
- Teste: `restaurar()` com `sessoes.db` vazio (sem tabelas) não falha.
- Teste: `cancelar_reserva` sem chave completa não cancela nada.
- Teste: segunda reserva do mesmo apartamento na mesma área e data devolve o código existente.
