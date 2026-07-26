"""agent(obs_dict) entrypoint for the PTCG AI Battle Challenge -- agent v0 (R1).

Crash-safe contract ported from intel/romanrozen_main.py: the double try/except
fallback, dual deck.csv path, and NO reference to __file__ at module load (it is
undefined in the Kaggle loader namespace). Sibling modules (pilot/obs/scoring/
search) are imported flat; we bootstrap sys.path from cwd + the Kaggle agent dir
without __file__ so the loader imports them wherever it drops the bundle.

Deck: Mega Starmie ex (WinDecks top-team list, intel/top50_decklists.csv rank 7).
Differentiator: search.py Search-API exact-resolution lethal/damage oracle.
"""

import os
import sys

# --- flat-import bootstrap (no __file__; covers local cwd and /kaggle_simulations/agent) ---
for _p in (os.getcwd(), "/kaggle_simulations/agent"):
    try:
        if _p and os.path.isdir(_p) and _p not in sys.path:
            sys.path.insert(0, _p)
    except Exception:
        pass


# Fix #5: embedded emergency 60-card deck (validated Mega Starmie ex list). If deck.csv
# is missing / mis-packaged / malformed, the handshake must still return 60 legal ints
# rather than [] (an illegal empty selection that forfeits the game at start).
EMERGENCY_DECK = (
    [3] * 9 + [17] * 4 + [131] * 2 + [132] * 2 + [133] * 2 + [1030] * 4 + [1031] * 3
    + [1086] * 4 + [1121] * 4 + [1122] * 3 + [1152] * 4 + [1167] * 1 + [1192] * 3
    + [1213] * 3 + [1225] * 4 + [1227] * 4 + [1229] * 4
)


def _load_deck():
    """Dual path deck load (cwd, then Kaggle agent dir); parse only the first 60 nonblank
    records and close the file. Falls back to the embedded emergency deck (fix #5)."""
    for p in ("deck.csv", "/kaggle_simulations/agent/deck.csv"):
        try:
            with open(p) as f:
                d = []
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    d.append(int(s))
                    if len(d) == 60:
                        break
            if len(d) == 60:
                return d
        except Exception:
            continue
    return list(EMERGENCY_DECK)


DECK = _load_deck()
if len(DECK) != 60:                 # last-resort guard: never hand back a non-60 deck
    DECK = list(EMERGENCY_DECK)

# Import the pilot lazily-but-at-load; if anything in the "smart" path fails to
# import, _PILOT is None and agent() still plays legally via the fallback.
try:
    import pilot as _pilot_mod
    _pilot_mod.DECK = DECK
    # Generalized deck profile: auto-derive the attacker/feeder/energy role sets from the
    # loaded decklist so the identical pilot plays any deck (pilotability bakeoff). Guarded:
    # on any failure the scoring module keeps its safe Mega Starmie ex defaults.
    try:
        _pilot_mod.SC.set_profile_from_deck(DECK)
    except Exception:
        pass
    _PILOT = _pilot_mod
except Exception:
    _PILOT = None


def _fallback(obs_dict):
    """First-N legal indices honoring minCount/maxCount (romanrozen double fallback).
    Never returns the deck mid-game: if the option list is unreadable/empty the only
    safe answer is an empty selection."""
    try:
        sel = obs_dict.get("select")
        if sel is None:
            return DECK
        opt = sel.get("option") or []
        n = len(opt)
        if n == 0:
            return []
        mn = sel.get("minCount", 1)
        mn = 1 if mn is None else mn
        mx = sel.get("maxCount", 1)
        mx = min(n, max(mn, 1)) if mx is None else mx   # fix #7: not a bare 1
        k = min(max(mn, 0), mx, n)
        if k == 0 and mn == 0:
            return []
        return list(range(max(k, 0)))
    except Exception:
        return []


def _valid_selection(r, sel):
    """Fix #4: final legality gate on the smart result. A valid selection is a list of
    unique in-range ints whose count is within the prompt's [minCount, maxCount]."""
    try:
        if not isinstance(r, list):
            return False
        opt = sel.get("option") or []
        n = len(opt)
        if any((not isinstance(i, int)) or i < 0 or i >= n for i in r):
            return False
        if len(set(r)) != len(r):
            return False
        mn = sel.get("minCount", 1)
        mn = 0 if mn is None else mn
        mx = sel.get("maxCount", 1)
        mx = min(n, max(mn, 1)) if mx is None else mx
        mx = min(mx, n)
        return mn <= len(r) <= mx
    except Exception:
        return False


def agent(obs_dict):
    try:
        sel = obs_dict.get("select")
        if sel is None:   # deck handshake at battle start
            return DECK
        if _PILOT is not None:
            r = _PILOT._pilot(obs_dict)
            if r is not None and _valid_selection(r, sel):
                return r
    except Exception:
        pass
    return _fallback(obs_dict)
