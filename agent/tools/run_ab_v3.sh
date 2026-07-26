#!/bin/bash
# Per-patch sentinel A/B screens (v3 protocol). One process per config; the agent
# reads PTCG_P0..P8 from env at import. Usage: run_ab_v3.sh [N=300] [seed=12345]
cd ~/ptcg-work || exit 1
D=~/ptcg-work/v3_ab
mkdir -p "$D"
N=${1:-300}
S=${2:-12345}
ZERO="PTCG_P0=0 PTCG_P1=0 PTCG_P2=0 PTCG_P3=0 PTCG_P4=0 PTCG_P5=0 PTCG_P6=0 PTCG_P6B=0 PTCG_P7=0 PTCG_P8=0"
run() {
  local label=$1
  shift
  env $ZERO "$@" PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" ab_v3.py "$label" "$N" "$S" > "$D/$label.log" 2>&1 &
}
run base
run p0 PTCG_P0=1
run p1 PTCG_P1=1
run p2 PTCG_P2=1
run p3 PTCG_P3=1
run p4 PTCG_P4=1
run p5 PTCG_P5=1 PTCG_P7=1
run p6 PTCG_P6=1
run p8 PTCG_P8=1
run all PTCG_P0=1 PTCG_P1=1 PTCG_P2=1 PTCG_P3=1 PTCG_P4=1 PTCG_P5=1 PTCG_P6=1 PTCG_P7=1 PTCG_P8=1
wait
grep -h "^AB\[" "$D"/*.log
