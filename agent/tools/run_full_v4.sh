#!/bin/bash
# v4 gauntlet gate: v4 (v3 + tracker hooks T1-T5) vs same-batch v3 (T flags off).
# 15 opponents x N x 3 seeds per config, 6 parallel single-seed bakeoff runs.
cd ~/ptcg-work || exit 1
D=~/ptcg-work/v4_full
mkdir -p "$D"
N=${1:-100}
SEEDS="12345 23456 34567"
# v3 shipped config (P-flags default; T-hooks OFF)
V3="PTCG_T1=0 PTCG_T2=0 PTCG_T3=0 PTCG_T4=0 PTCG_T5=0"
# v4 = all defaults (P0-P5+P7 + T1-T5 on) -> no env needed, but set explicitly
V4="PTCG_T1=1 PTCG_T2=1 PTCG_T3=1 PTCG_T4=1 PTCG_T5=1"
for s in $SEEDS; do
  env $V4 PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" bakeoff.py v4 "$N" "$s" > "$D/v4_$s.log" 2>&1 &
  env $V3 PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" bakeoff.py v3 "$N" "$s" > "$D/v3_$s.log" 2>&1 &
done
wait
PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" combine_v3.py "$D"/v4_*.log "$D"/v3_*.log
