#!/bin/bash
# Deck re-bakeoff same-batch driver (intel/deck_rebakeoff_2026-07-12.md):
# 4 decks (ctrl=Starmie v5 repo-default / crustle=Budew #2 list / alakazam=Yushin-
# Majkel list / rocket=kashiwashira list) x 3 seeds x (15-opp gauntlet N + starmie-
# mirror row N vs frozen ~/mirror_b). All 24 processes in ONE batch: the engine
# shuffle RNG is unseeded, so only same-batch deltas are the trustworthy read.
#
# Prereqs (WSL): per-deck agent dirs ~/rb_{ctrl,crustle,alakazam,rocket}/ each holding
# the SAME repo-HEAD agent modules + that candidate's deck.csv (60 ids, errorType=0);
# gauntlet.py/mirror_ab.py honor PTCG_OUR_DIR (this round's harness patch).
# Usage: run_rebakeoff.sh [N=100] ["seeds..."]
cd "$HOME/ptcg-work" || exit 1
D="$HOME/ptcg-work/rb_full"
mkdir -p "$D"
N=${1:-100}
SEEDS=${2:-"12345 23456 34567"}
PY="$HOME/ptcg-venv/bin/python"
export PYTHONPATH="$HOME/ptcg-work"

for s in $SEEDS; do
  for deck in ctrl crustle alakazam rocket; do
    PTCG_OUR_DIR="$HOME/rb_$deck" "$PY" bakeoff.py   "$deck" "$N" "$s" > "$D/${deck}_$s.log" 2>&1 &
    PTCG_OUR_DIR="$HOME/rb_$deck" "$PY" mirror_ab.py "$deck" "$N" "$s" > "$D/mir_${deck}_$s.log" 2>&1 &
  done
done
wait
echo "ALL RUNS DONE"
echo "===================== STANDARD META-WEIGHTED READ (frozen top-quartile) ====================="
"$PY" combine_v3.py "$D"/ctrl_*.log "$D"/crustle_*.log "$D"/alakazam_*.log "$D"/rocket_*.log
echo
echo "===================== BAND-WEIGHTED READ (live 700-1000 mix) ====================="
"$PY" band_combine.py "$D"/ctrl_*.log "$D"/crustle_*.log "$D"/alakazam_*.log "$D"/rocket_*.log \
      "$D"/mir_ctrl_*.log "$D"/mir_crustle_*.log "$D"/mir_alakazam_*.log "$D"/mir_rocket_*.log
