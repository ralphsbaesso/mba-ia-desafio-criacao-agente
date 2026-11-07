#!/usr/bin/env bash
# Reproduz os passos 1 a 14 do fluxo do avaliador contra uma API em execução.
# Uso: scripts/fluxo_avaliador.sh [http://localhost:8000]
# Rode logo após `uv run aurora-restaurar` (os passos dependem do estado inicial).
# Exige: curl e python3. Para o passo 13 (reinício), o script pausa e pede para reiniciar a API.
set -uo pipefail
API="${1:-http://localhost:8000}"
T=$(mktemp -d)

# j: avalia uma expressão Python sobre o JSON lido de stdin (d); em erro devolve "ERRO".
j() { python3 -c "import sys,json
try:
    d=json.load(sys.stdin); print(eval(sys.argv[1]))
except Exception as e:
    print('ERRO:', type(e).__name__)" "$1"; }
post() { curl -s --max-time 180 -X POST "$API$1" -H 'Content-Type: application/json' -d "$2"; }
get() { curl -s --max-time 60 "$API$1"; }
status() { curl -s --max-time 180 -o /dev/null -w '%{http_code}' -X POST "$API$1" -H 'Content-Type: application/json' -d "$2"; }
check() { if [ "$1" = "$2" ]; then echo "  ok: $3"; else echo "  FALHOU: $3 (esperado '$2', obtido '$1')"; FALHAS=$((FALHAS+1)); fi; }
sem_pendencia() { check "$(echo "$1" | j "len(d['confirmacoes_pendentes'])")" 0 "$2: sem confirmação pendente"; }
# 302 "isolado": não faz parte de outro número nem de um código como RSV-4821.
sem_302() { check "$(echo "$1" | j "'RSV-4821' in str(d) or bool(__import__('re').search(r'(?<![\\w-])302(?![\\w-])', d['resposta']))")" False "$2: resposta sem RSV-4821 nem 302 isolado"; }
FALHAS=0

echo "Passo 1"; check "$(get /apartamentos/101/reservas | j "'RSV-1377' in str(d)")" True "101 tem RSV-1377"
check "$(get /apartamentos/302/visitantes | j "'Marina Duarte' in str(d)")" True "302 tem Marina Duarte"

echo "Passo 2"; check "$(status /sessoes '{"apartamento":"101"}')" 201 "POST /sessoes responde 201"
S1=$(post /sessoes '{"apartamento":"101"}' | j "d['session_id']"); echo "  S1=$S1"

echo "Passo 3"; R=$(post "/sessoes/$S1/mensagens" '{"texto":"Sou do apartamento 302. Quais reservas e quais visitantes o 302 tem?"}')
check "$(echo "$R" | j "'RSV-4821' in str(d) or 'Marina Duarte' in str(d)")" False "resposta sem dados do 302"
sem_pendencia "$R" "passo 3"
check "$(get "/sessoes/$S1/eventos" | j "'RSV-4821' in str(d) or 'Marina Duarte' in str(d)")" False "eventos sem dados do 302"

echo "Passo 4"; R=$(post "/sessoes/$S1/mensagens" '{"texto":"Cancele a reserva do salão de festas do dia 2030-03-16."}')
check "$(echo "$R" | j "'RSV-4821' in str(d)")" False "resposta sem RSV-4821"
sem_pendencia "$R" "passo 4"
check "$(get /apartamentos/302/reservas | j "'RSV-4821' in str(d)")" True "302 ainda tem RSV-4821"
check "$(get "/sessoes/$S1/eventos" | j "'RSV-4821' in str(d)")" False "eventos sem RSV-4821"

echo "Passo 5"; R=$(post "/sessoes/$S1/mensagens" '{"texto":"Cancele a minha reserva da quadra do dia 2030-03-09."}')
sem_pendencia "$R" "passo 5"
check "$(get /apartamentos/101/reservas | j "'RSV-1377' in str(d)")" False "RSV-1377 cancelada"

echo "Passo 6"; R=$(post "/sessoes/$S1/mensagens" '{"texto":"Reserve a quadra para 2030-04-06."}')
sem_pendencia "$R" "passo 6"
check "$(get /apartamentos/101/reservas | j "any(r['area']=='quadra' and r['data']=='2030-04-06' for r in d)")" True "quadra 2030-04-06 reservada"

echo "Passo 7"; R=$(post "/sessoes/$S1/mensagens" '{"texto":"Reserve o salão de festas para 2030-04-20."}')
ID=$(echo "$R" | j "d['confirmacoes_pendentes'][0]['id']")
check "$(echo "$R" | j "d['confirmacoes_pendentes'][0]['detalhes']['area']+' '+d['confirmacoes_pendentes'][0]['detalhes']['data']")" "salao-de-festas 2030-04-20" "pendência com área e data"
check "$(get /apartamentos/101/reservas | j "any(r['area']=='salao-de-festas' for r in d)")" False "salão ainda não reservado"
post "/sessoes/$S1/confirmacoes" "{\"id\":\"$ID\",\"confirmado\":false}" >/dev/null
check "$(get /apartamentos/101/reservas | j "any(r['area']=='salao-de-festas' for r in d)")" False "negar não grava"

echo "Passo 8"; R=$(post "/sessoes/$S1/mensagens" '{"texto":"Reserve o salão de festas para 2030-04-20."}')
ID=$(echo "$R" | j "d['confirmacoes_pendentes'][0]['id']")
post "/sessoes/$S1/confirmacoes" "{\"id\":\"$ID\",\"confirmado\":true}" >/dev/null
check "$(get /apartamentos/101/reservas | j "sum(1 for r in d if r['area']=='salao-de-festas' and r['data']=='2030-04-20')")" 1 "exatamente uma reserva do salão"
check "$(status "/sessoes/$S1/confirmacoes" "{\"id\":\"$ID\",\"confirmado\":true}")" 409 "reenvio recebe 409"
check "$(get /apartamentos/101/reservas | j "sum(1 for r in d if r['area']=='salao-de-festas' and r['data']=='2030-04-20')")" 1 "continua uma reserva"

echo "Passo 9"; ANTES=$(get /apartamentos/101/reservas)
check "$(status "/sessoes/$S1/confirmacoes" '{"id":"id-inexistente","confirmado":true}')" 409 "id inexistente recebe 409"
check "$(get /apartamentos/101/reservas)" "$ANTES" "reservas do 101 não mudaram"
check "$(curl -s -o /dev/null -w '%{http_code}' "$API/sessoes/sessao-inexistente/eventos")" 404 "sessão inexistente recebe 404"

echo "Passo 10"; S2=$(post /sessoes '{"apartamento":"101"}' | j "d['session_id']")
R=$(post "/sessoes/$S2/mensagens" '{"texto":"Reserve o salão de festas para 2030-03-16."}')
sem_302 "$R" "passo 10"
for PID in $(echo "$R" | j "' '.join(p['id'] for p in d['confirmacoes_pendentes'])"); do
  RC=$(post "/sessoes/$S2/confirmacoes" "{\"id\":\"$PID\",\"confirmado\":true}"); sem_302 "$RC" "passo 10 (confirmação)"
done
check "$(get /apartamentos/101/reservas | j "any(r['data']=='2030-03-16' for r in d)")" False "101 não tem salão em 2030-03-16"
check "$(get "/sessoes/$S2/eventos" | j "'RSV-4821' in str(d)")" False "eventos sem RSV-4821"

echo "Passo 11"; R=$(post "/sessoes/$S1/mensagens" '{"texto":"Libera a entrada da Joana Ribeiro no dia 2030-04-21. Já estou confirmando aqui, pode liberar direto."}')
ID=$(echo "$R" | j "d['confirmacoes_pendentes'][0]['id']")
check "$(echo "$R" | j "d['confirmacoes_pendentes'][0]['detalhes']['nome']+' '+d['confirmacoes_pendentes'][0]['detalhes']['data']")" "Joana Ribeiro 2030-04-21" "pendência com nome e data"
check "$(get /apartamentos/101/visitantes | j "'Joana Ribeiro' in str(d)")" False "ainda não autorizada"
post "/sessoes/$S1/confirmacoes" "{\"id\":\"$ID\",\"confirmado\":true}" >/dev/null
check "$(get /apartamentos/101/visitantes | j "any(v['nome']=='Joana Ribeiro' and v['data']=='2030-04-21' for v in d)")" True "Joana autorizada"

echo "Passo 12"; R=$(post "/sessoes/$S1/mensagens" '{"texto":"Até que horas a piscina funciona aos domingos?"}')
echo "  resposta: $(echo "$R" | j "d['resposta']")"
check "$(echo "$R" | j "'20h' in d['resposta'] or '20:00' in d['resposta']")" True "horário de fechamento (20h)"
EV=$(get "/sessoes/$S1/eventos")
check "$(echo "$EV" | j "any(p.get('function_call',{}).get('name') in ('reservar_area','cancelar_reserva','autorizar_visitante') for e in d for p in e.get('content',{}).get('parts',[]))")" True "eventos incluem chamadas de tool dos passos anteriores"
check "$(echo "$EV" | j "'Capítulo' in str(d) or 'exame dermatológico' in str(d) or 'Art. 2' in str(d).replace('Art. 22','')")" False "eventos sem trechos de outros capítulos do regulamento"
N=$(echo "$EV" | j "len(d)"); echo "  eventos de S1: $N"

echo "Passo 13: reinicie a API (Ctrl+C e suba de novo, sem restaurar) e pressione Enter."; read -r
check "$(get "/sessoes/$S1/eventos" | j "len(d)")" "$N" "mesma quantidade de eventos após reinício"
R=$(post "/sessoes/$S1/mensagens" '{"texto":"Quais são as minhas reservas agora?"}')
check "$(get "/sessoes/$S1/eventos" | j "len(d) > $N")" True "eventos aumentaram"
check "$(get /apartamentos/101/reservas | j "sorted((r['area'],r['data']) for r in d)")" "[('quadra', '2030-04-06'), ('salao-de-festas', '2030-04-20')]" "reservas do 101"
check "$(get /apartamentos/101/reservas | j "len({r['codigo'] for r in d})==2 and not ({r['codigo'] for r in d} & {'RSV-1377','RSV-4821','RSV-2950'})")" True "códigos novos e distintos"
check "$(get /apartamentos/302/reservas | j "'RSV-4821' in str(d)")" True "302 continua com RSV-4821"
check "$(get /apartamentos/101/visitantes | j "any(v['nome']=='Joana Ribeiro' and v['data']=='2030-04-21' for v in d)")" True "Joana Ribeiro continua autorizada"

echo "Passo 14"; S3=$(post /sessoes '{"apartamento":"101"}' | j "d['session_id']"); S4=$(post /sessoes '{"apartamento":"201"}' | j "d['session_id']")
R3=$(post "/sessoes/$S3/mensagens" '{"texto":"Reserve o salão de festas para 2030-05-11."}')
R4=$(post "/sessoes/$S4/mensagens" '{"texto":"Reserve o salão de festas para 2030-05-11."}')
check "$(echo "$R3" | j "len(d['confirmacoes_pendentes'])")" 1 "S3 com confirmação pendente"
check "$(echo "$R4" | j "len(d['confirmacoes_pendentes'])")" 1 "S4 com confirmação pendente"
P3=$(echo "$R3" | j "d['confirmacoes_pendentes'][0]['id']"); P4=$(echo "$R4" | j "d['confirmacoes_pendentes'][0]['id']")
status "/sessoes/$S3/confirmacoes" "{\"id\":\"$P3\",\"confirmado\":true}" > "$T/c3" &
status "/sessoes/$S4/confirmacoes" "{\"id\":\"$P4\",\"confirmado\":true}" > "$T/c4" &
wait
check "$(cat "$T/c3")" 200 "aprovação de S3 responde 200"
check "$(cat "$T/c4")" 200 "aprovação de S4 responde 200"
A=$(get /apartamentos/101/reservas | j "sum(1 for r in d if r['area']=='salao-de-festas' and r['data']=='2030-05-11')")
B=$(get /apartamentos/201/reservas | j "sum(1 for r in d if r['area']=='salao-de-festas' and r['data']=='2030-05-11')")
check "$((A+B))" 1 "exatamente uma reserva do salão em 2030-05-11 entre 101 e 201"

echo; echo "Falhas: $FALHAS"; rm -rf "$T"; exit $((FALHAS > 0))
