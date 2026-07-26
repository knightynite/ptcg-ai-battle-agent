#!/bin/bash
# v5 sentinel screen: per-lever configs on the 6 sentinel opponents (ab_v5.py).
# All arms pin PTCG_T5N=0 so the R-lever deltas are isolated from the T5 narrowing
# (which has its own 3-arm A/B, t5_ab.sh). Usage: run_ab_v5.sh [N=150] [seed=12345]
cd "$HOME/ptcg-work" || exit 1
D="$HOME/ptcg-work/v5_ab"
mkdir -p "$D"
N=${1:-150}
S=${2:-12345}
PY="$HOME/ptcg-venv/bin/python"
export PYTHONPATH="$HOME/ptcg-work"
export PTCG_T5N=0

OFF="PTCG_R1=0 PTCG_R2=0 PTCG_R3=0 PTCG_R4=0"
env $OFF                                     "$PY" ab_v5.py v4b   "$N" "$S" > "$D/v4b_$S.log"   2>&1 &
env PTCG_R1=1 PTCG_R2=1 PTCG_R3=0 PTCG_R4=0 "$PY" ab_v5.py r12   "$N" "$S" > "$D/r12_$S.log"   2>&1 &
env PTCG_R1=1 PTCG_R2=0 PTCG_R3=1 PTCG_R4=0 "$PY" ab_v5.py r13   "$N" "$S" > "$D/r13_$S.log"   2>&1 &
env PTCG_R1=0 PTCG_R2=0 PTCG_R3=0 PTCG_R4=1 "$PY" ab_v5.py r4    "$N" "$S" > "$D/r4_$S.log"    2>&1 &
env PTCG_R1=1 PTCG_R2=0 PTCG_R3=1 PTCG_R4=1 "$PY" ab_v5.py r134  "$N" "$S" > "$D/r134_$S.log"  2>&1 &
env PTCG_R1=1 PTCG_R2=1 PTCG_R3=1 PTCG_R4=0 "$PY" ab_v5.py r123  "$N" "$S" > "$D/r123_$S.log"  2>&1 &
env PTCG_R1=1 PTCG_R2=1 PTCG_R3=1 PTCG_R4=1 "$PY" ab_v5.py v5all "$N" "$S" > "$D/v5all_$S.log" 2>&1 &
wait
echo "=== sentinel results (seed $S) ==="
grep -h "^AB\[" "$D"/*_"$S".log
