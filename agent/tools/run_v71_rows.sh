#!/bin/bash
# v7.1 gate, row-sharded + resumable (WSL service crash resilience): one rowjob.py
# process per (arm, seed, opponent), skipped when its log already holds a CSVROW.
# Arms: v7 = ship flags + PTCG_B2F=0 (live sub 54600640 config), v71 = + PTCG_B2F=1.
# Seeded from the partial whole-batch logs in ~/ptcg-work/v71_gate (5 rows x 6 done
# there; mirrors completed there too). Writes $D/DONE when all 96 row logs are in.
cd "$HOME/ptcg-work" || exit 1
D=$HOME/ptcg-work/v71_rows
mkdir -p "$D"
PY=$HOME/ptcg-venv/bin/python
export PYTHONPATH=$HOME/ptcg-work
export PTCG_OUR_DIR=$HOME/v7agent
export PTCG_B1=1 PTCG_B2=1 PTCG_B3=0 PTCG_B4=1 PTCG_B5=1 PTCG_B6=1

ROWS="ryota_alakazam wmh_alakazam souta_crustle budew_crustle wmh_grimmsnarl \
wmh_garchomp kiyotah_lucario wmh_dragapult kiyotah_dragapult masami_archaludon \
wmh_kangaskhan romanrozen kojimar_baseline wmh_typhlosion wmh_bellibolt hops_box"
SEEDS="12345 23456 34567"
N=200
MAX=12

# seed row logs from the partial whole-batch run (same-batch pairing preserved:
# both arms completed the identical 5-row prefix there)
for arm in v7 v71; do
  for seed in $SEEDS; do
    src=$HOME/ptcg-work/v71_gate/${arm}_${seed}.log
    [ -f "$src" ] || continue
    for name in $ROWS; do
      log=$D/row_${arm}_${seed}_${name}.log
      if ! grep -q "^CSVROW," "$log" 2>/dev/null; then
        line=$(grep "^CSVROW,${arm},${name},${seed}," "$src" 2>/dev/null | head -1)
        [ -n "$line" ] && echo "$line" > "$log"
      fi
    done
  done
done

running=0
for round in 1 2 3 4 5 6; do
  launched=0
  for seed in $SEEDS; do
    for arm in v7 v71; do
      b2f=0; [ "$arm" = v71 ] && b2f=1
      for name in $ROWS; do
        log=$D/row_${arm}_${seed}_${name}.log
        grep -q "^CSVROW," "$log" 2>/dev/null && continue
        PTCG_B2F=$b2f "$PY" rowjob.py "$arm" "$name" "$N" "$seed" > "$log" 2>&1 &
        launched=$((launched+1)); running=$((running+1))
        if [ "$running" -ge "$MAX" ]; then wait -n; running=$((running-1)); fi
      done
    done
  done
  wait; running=0
  [ "$launched" -eq 0 ] && break
done

ok=1
for seed in $SEEDS; do
  for arm in v7 v71; do
    for name in $ROWS; do
      grep -q "^CSVROW," "$D/row_${arm}_${seed}_${name}.log" 2>/dev/null || ok=0
    done
  done
done
if [ "$ok" = 1 ]; then
  echo "V71 ROWS DONE" | tee "$D/DONE"
else
  echo "V71 ROWS INCOMPLETE"
fi
