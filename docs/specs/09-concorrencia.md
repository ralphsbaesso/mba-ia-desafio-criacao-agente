# Spec 09: Concorrência na gravação de reservas

## Objetivo
Duas aprovações simultâneas para a mesma área e data geram exatamente uma reserva, ambas respondendo `200` (Garantia 5).

## Decisões
- A exclusividade é o índice único parcial `reservas(area, data) WHERE status='ativa'` (spec 02). O `INSERT` é a verificação: não há janela entre checar e gravar.
- `criar_reserva` abre conexão própria com `BEGIN IMMEDIATE`, faz o `SELECT` de idempotência e o `INSERT` na mesma transação, e distingue colisão de código de data ocupada como descrito na spec 02 (fonte única dessa regra).
- A tool converte `ocupada` em resposta normal ao modelo, que explica ao morador. Nenhuma exceção sobe até a API.
- As rotas de sessões diferentes rodam em paralelo (lock apenas por `session_id`); o serviço de sessão SQLite do ADK (aiosqlite) tolera escritas concorrentes de sessões distintas.
- `uvicorn` roda com um worker; a garantia não depende disso, pois está no banco.

## Critérios de aceite
- Teste: 10 threads chamando `criar_reserva(apt_i, "salao-de-festas", "2030-05-11")` com apartamentos distintos: exatamente uma `ok=True`, nenhuma exceção.
