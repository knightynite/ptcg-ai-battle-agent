"""Sacred-Ash CRN gate mechanism instrument (intel/sacred_ash_gate_prereg_2026-07-17.md).

Runs one (opponent row, N, seed0) band-gauntlet unit via an UNMODIFIED call to
gauntlet.play() -- reused byte-identical (crash/illegal/timeout/cap/BANDROW accounting
untouched) -- then layers mechanism logging on top by monkeypatching
gauntlet.battle_start/battle_select/battle_finish to snoop the obs stream gauntlet.py
already produces internally. This is the same "wrap, don't reimplement" convention as
discipline_instrument.py (which reads module counters instead); here there are no
existing module counters for Sacred Ash / deck-out state, so we tap the obs logs
directly instead of reimplementing play()'s loop (which mechanism_instrument.py did,
at higher drift risk).

Arm (control vs variant) is toggled OUTSIDE this script by swapping the file sitting at
$PTCG_OUR_DIR/deck.csv before invocation -- same convention run_v11_gate.sh /
manabase mechanism_instrument.py use for deck-only A/Bs.

Per game (using obs["current"]["players"][idx].deckCount/prize -- both public per
intel/engine_log_semantics.md sec.3) classifies the TERMINAL frame exactly like
intel/episodes_raw/sacred_ash_precheck_0717.py's win_condition rule:
  prize_us==0 -> prize_race_us_won ; prize_opp==0 -> prize_race_opp_won ;
  deck_us==0  -> deck_out_us       ; deck_opp==0  -> deck_out_opp ; else other.
For deck_out_us games only, also records "ahead" = (prize_us < prize_opp) at that same
terminal frame (fewer prizes remaining for us = we had banked MORE prizes = we were
AHEAD in the race when we decked out) -- the pre-registered "deck-out-while-AHEAD vs
deck-out-while-BEHIND" split. Games that abort (crash/illegal) or hit the decision cap
unresolved are excluded from classification (result < 0 at battle_finish time) and
counted separately as "unresolved" (should be 0 given the gate's 0-crash/0-illegal/
0-timeout requirement).

Sacred-Ash engagement, from obs["logs"] (LogType map, engine_log_semantics.md sec.2):
  LogType 10 Play, playerIndex==us_seat, cardId==1129           -> fired (ash_fires+=1)
  LogType 6  MoveCard, playerIndex==us_seat, fromArea==3(DISCARD),
             toArea==1(DECK), cardId in POKEMON_IDS, AFTER a fire this game -> target
             returned (ash_targets+=1). Sticky "pending" flag is safe here: verified
             (2026-07-17 setup) no OTHER card in either deck (control or variant list)
             does discard-Pokemon->deck recovery, and Sacred Ash itself resolves to our
             OWN discard (a non-Pokemon card, fromArea=2 not 3) so it cannot re-fire
             itself within a game (single copy in the 60).

  DEDUP (2026-07-17, found via a first live run: ash_fires came back at a razor-clean
  ~2.00x ash_fire_games ratio on every single unit -- ratio 1.94-2.00, far too uniform to
  be a real per-game double-play with only 1 copy of the card in the 60). Root cause:
  "each obs contains exactly the events since THAT PLAYER's previous selection"
  (engine_log_semantics.md sec.1) means log CURSORS are per-recipient, not per-event --
  a public event (Play/MoveCard, openType 0) gets delivered once to OUR cursor and once
  to the OPPONENT's cursor as each independently sweeps past it. This harness processes
  obs["logs"] on every battle_select return regardless of whose decision it was for
  (matching gauntlet.play()'s own loop, which does the same), so it sees each physical
  event via both cursors. Fix: dedup by (LogType, serial) -- `serial` is the per-match-
  unique physical card instance (engine_log_semantics.md sec.2 footnote), present on
  both Play and MoveCard -- within a per-game `seen` set, so a re-delivery of the exact
  same physical event is a no-op. Verified fix below; do not remove the seen-set.

Output (stdout):
  BANDROW,...   -- identical schema to band_gauntlet.py/gauntlet.py (crn_pool.py-ready)
  MECHROW,<row>,<seed0>,<n>,deckout_us=<d>,deckout_ahead=<a>,deckout_behind=<b>,
          ash_fires=<f>,ash_fire_games=<fg>,ash_targets=<t>,unresolved=<u>
  MECHGAME,<row>,<seed0>,<gidx>,<classification>,<ahead 0/1/NA>,<ash_fires_this_game>,
           <ash_targets_this_game>     (one per game, aligned to BANDROW's outcome-string index)

Usage (WSL): PYTHONPATH=$HOME/ptcg-work PTCG_OUR_DIR=$HOME/v11agentB \
  <fixed v11 ledger incl. PTCG_EXACT_DET=0 PTCG_SUPPLY_RULE=0 PTCG_DISCIPLINE_RULE=0> \
  ~/ptcg-venv/bin/python sacred_ash_instrument.py <row> <N> <seed0>
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.environ.get("HOME", os.path.expanduser("~")), "ptcg-work"))
import gauntlet as G  # noqa: E402 -- reuses OUR_DIR load, CRN shim, play()

G.GDIR = os.path.join(os.environ.get("HOME", os.path.expanduser("~")), "gauntlet_band")

from cg.api import all_card_data, CardType  # noqa: E402

POKEMON_IDS = {c.cardId for c in all_card_data() if c.cardType == CardType.POKEMON}
SACRED_ASH_ID = 1129
AREA_DISCARD = 3
AREA_DECK = 1
LOG_PLAY = 10
LOG_MOVECARD = 6

_orig_start = G.battle_start
_orig_select = G.battle_select
_orig_finish = G.battle_finish

_GS = {  # per-current-game scratch state
    "us_seat": None,
    "ash_pending": False,
    "ash_fires_game": 0,
    "ash_targets_game": 0,
    "last_obs": None,
    "gidx": -1,
    "seen_events": None,   # set of (LogType, serial) already counted this game -- dedup
}
AGG = Counter()          # aggregate counters for the MECHROW line
CLASS_COUNTS = Counter()  # win_condition classification counts (diagnostic)
GAMELOG = []             # (gidx, classification, ahead, ash_fires_game, ash_targets_game)


def _process_logs(obs):
    logs = obs.get("logs") or []
    us_seat = _GS["us_seat"]
    seen = _GS["seen_events"]
    for lg in logs:
        if not isinstance(lg, dict):
            continue
        lt = lg.get("type")
        if lt == LOG_PLAY and lg.get("playerIndex") == us_seat and lg.get("cardId") == SACRED_ASH_ID:
            key = (LOG_PLAY, lg.get("serial"))
            if key not in seen:
                seen.add(key)
                _GS["ash_fires_game"] += 1
                _GS["ash_pending"] = True
        elif (lt == LOG_MOVECARD and _GS["ash_pending"]
              and lg.get("playerIndex") == us_seat
              and lg.get("fromArea") == AREA_DISCARD and lg.get("toArea") == AREA_DECK
              and lg.get("cardId") in POKEMON_IDS):
            key = (LOG_MOVECARD, lg.get("serial"))
            if key not in seen:
                seen.add(key)
                _GS["ash_targets_game"] += 1


def _wrapped_start(a, b):
    obs, sd = _orig_start(a, b)
    _GS["us_seat"] = 0 if a is G.our.DECK else 1
    _GS["ash_pending"] = False
    _GS["ash_fires_game"] = 0
    _GS["ash_targets_game"] = 0
    _GS["seen_events"] = set()
    _GS["gidx"] += 1
    _GS["last_obs"] = obs
    _process_logs(obs)
    return obs, sd


def _wrapped_select(sel):
    obs = _orig_select(sel)
    _GS["last_obs"] = obs
    _process_logs(obs)
    return obs


def _wrapped_finish():
    obs = _GS["last_obs"]
    us_seat = _GS["us_seat"]
    cur = (obs.get("current") or {}) if obs else {}
    result = cur.get("result", -1)
    classification = "unresolved"
    ahead = None
    if result is not None and result >= 0 and us_seat is not None:
        players = cur.get("players") or []
        if len(players) >= 2:
            p_us = players[us_seat] or {}
            p_opp = players[1 - us_seat] or {}
            deck_us = p_us.get("deckCount") or 0
            deck_opp = p_opp.get("deckCount") or 0
            prize_us = len(p_us.get("prize") or [])
            prize_opp = len(p_opp.get("prize") or [])
            if prize_us == 0:
                classification = "prize_race_us_won"
            elif prize_opp == 0:
                classification = "prize_race_opp_won"
            elif deck_us == 0:
                classification = "deck_out_us"
                ahead = prize_us < prize_opp
            elif deck_opp == 0:
                classification = "deck_out_opp"
            else:
                classification = "other"
    CLASS_COUNTS[classification] += 1
    if classification == "unresolved":
        AGG["unresolved"] += 1
    if classification == "deck_out_us":
        AGG["deckout_us"] += 1
        AGG["deckout_ahead" if ahead else "deckout_behind"] += 1
    if _GS["ash_fires_game"] > 0:
        AGG["ash_fires"] += _GS["ash_fires_game"]
        AGG["ash_fire_games"] += 1
        AGG["ash_targets"] += _GS["ash_targets_game"]
    GAMELOG.append((_GS["gidx"], classification, ahead,
                     _GS["ash_fires_game"], _GS["ash_targets_game"]))
    return _orig_finish()


G.battle_start = _wrapped_start
G.battle_select = _wrapped_select
G.battle_finish = _wrapped_finish


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    name = sys.argv[1]
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    seed0 = int(sys.argv[3]) if len(sys.argv) > 3 else 12345

    print(G.HEADER)
    r = G.play(name, N, seed0)
    print(G.fmt_row(name, "?", r))
    print("BANDROW,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%s" % (
        name, seed0, r["us"], r["tot"], r["draw"], r["crashes"], r["illegal"],
        r["timeouts"], r["wf"], r["nf"], r["ws"], r["ns"],
        r.get("cap", 0), r.get("capw", 0), r.get("outcomes", "")), flush=True)
    print("MECHROW,%s,%d,%d,deckout_us=%d,deckout_ahead=%d,deckout_behind=%d,"
          "ash_fires=%d,ash_fire_games=%d,ash_targets=%d,unresolved=%d" % (
              name, seed0, r["tot"], AGG["deckout_us"], AGG["deckout_ahead"],
              AGG["deckout_behind"], AGG["ash_fires"], AGG["ash_fire_games"],
              AGG["ash_targets"], AGG["unresolved"]), flush=True)
    print("MECHCLASS,%s,%d,%s" % (
        name, seed0, ";".join("%s=%d" % (k, v) for k, v in CLASS_COUNTS.items())), flush=True)
    for gidx, cls, ahead, af, at in GAMELOG:
        print("MECHGAME,%s,%d,%d,%s,%s,%d,%d" % (
            name, seed0, gidx, cls, ("NA" if ahead is None else ("1" if ahead else "0")),
            af, at))
    if r.get("err"):
        print("ERR: " + str(r["err"]))


if __name__ == "__main__":
    main()
