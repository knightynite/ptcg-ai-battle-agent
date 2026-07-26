#!/bin/bash
# T5 stall-guard 3-arm A/B (task #5): old T5 vs narrowed T5 (T5N) vs T5 off,
# souta_crustle + ryota_alakazam, 6 seeds x 100 = N=600/opponent/arm. R levers OFF.
cd "$HOME/ptcg-work" || exit 1
D="$HOME/ptcg-work/v5_t5"
mkdir -p "$D"
PY="$HOME/ptcg-venv/bin/python"
export PYTHONPATH="$HOME/ptcg-work"
OFF="PTCG_R1=0 PTCG_R2=0 PTCG_R3=0 PTCG_R4=0"

runarm() {  # label env...
  local label=$1; shift
  env "$@" "$PY" - "$label" <<'EOF' > "$D/$label.log" 2>&1
import sys
import gauntlet as G
label = sys.argv[1]
for name in ("souta_crustle", "ryota_alakazam"):
    for s in (12345, 23456, 34567, 45678, 56789, 67890):
        r = G.play(name, 100, s)
        print("T5ROW,%s,%s,%d,%d,%d,%d,%d" % (label, name, s, r["us"], r["tot"],
              r["crashes"], r["illegal"]), flush=True)
EOF
}

runarm t5old $OFF PTCG_T5=1 PTCG_T5N=0 &
runarm t5n   $OFF PTCG_T5=1 PTCG_T5N=1 &
runarm t5off $OFF PTCG_T5=0 PTCG_T5N=0 &
wait
echo "=== T5 3-arm results ==="
grep -h T5ROW "$D"/t5old.log "$D"/t5n.log "$D"/t5off.log | awk -F, '
{k=$2","$3; us[k]+=$5; n[k]+=$6} END {for (k in us) printf "%-24s %4d/%4d  %.1f%%\n", k, us[k], n[k], 100*us[k]/n[k]}' | sort
