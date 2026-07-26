#!/bin/bash
# Wave-3 sentinel screens: P2/P6 isolation inside the no-P8 stack (2 seeds each).
cd ~/ptcg-work || exit 1
D=~/ptcg-work/v3_ab
mkdir -p "$D"
N=${1:-300}
STACK="PTCG_P0=1 PTCG_P1=1 PTCG_P2=1 PTCG_P3=1 PTCG_P4=1 PTCG_P5=1 PTCG_P6=1 PTCG_P6B=0 PTCG_P7=1 PTCG_P8=0"
run() {
  local label=$1 seed=$2
  shift 2
  env $STACK "$@" PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" ab_v3.py "$label" "$N" "$seed" > "$D/$label.log" 2>&1 &
}
run np8_np2 12345 PTCG_P2=0
run np8_np2_s2 23456 PTCG_P2=0
run np8_np6 12345 PTCG_P6=0
run np8_np6_s2 23456 PTCG_P6=0
run np8_np2_np6 12345 PTCG_P2=0 PTCG_P6=0
run np8_np2_np6_s2 23456 PTCG_P2=0 PTCG_P6=0
run np8_s3 34567
run np8_p6b 12345 PTCG_P6B=1
wait
grep -h "^AB\[" "$D"/np8_*.log 2>/dev/null
