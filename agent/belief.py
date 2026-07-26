"""Opponent archetype belief model (agent R3).

The R3 hypothesis: the measured ladder deficits (the Alakazam non-ex prize race and
the Crustle attrition/snipe race) are hidden-information / multi-turn problems that
R2's junk determinization + one-turn rollout could not see. This module supplies the
missing piece -- a *realistic* opponent -- in two parts:

  1. A Bayesian archetype classifier. Prior = the top-quartile archetype shares
     (Alakazam .55, Crustle .22, ... -- the same weights the gauntlet meta-weights by,
     from intel/meta_current_2026-07-10.csv + replay_mining_2026-07-10.md). Likelihood =
     signature-card evidence: revealed opponent Pokemon lines (active / bench / discard,
     all visible in the observation) each vote for their archetype and against the others.
     Posterior = softmax(log prior + evidence). Updated every decision as cards reveal.

  2. A representative 60-card decklist per archetype (exact card IDs, taken from the
     top-50 leaderboard lists in intel/top50_decklists.csv via the derived decks table).
     search.py uses these to *complete* the opponent's hidden zones (deck / hand / prize)
     for a belief-informed determinization -- minus the cards already revealed -- so the
     opponent-turn rollout draws and plays realistic cards instead of junk energy.

Signature ids are resolved from card NAMES against the engine card DB at import (robust
to alternate printings -- e.g. Alakazam prints 245 & 743 both tag alakazam), with an
embedded id fallback so the module still classifies if the DB name lookup is unavailable.

Everything here is pure data + arithmetic; no engine/Search-API calls, no I/O at runtime.
"""

import math

import obs as O

# --- archetypes we model with a representative decklist -------------------------------
ARCHS = ["alakazam", "crustle", "grimmsnarl", "cynthia", "lucario", "dragapult",
         "archaludon", "kangaskhan", "starmie", "other"]

# Prior = top rating-quartile archetype shares (task/meta weights; see gauntlet ARCH_WEIGHT
# and replay_mining_2026-07-10.md sec.5). 'other' absorbs the long tail. Normalized below.
PRIOR = {
    "alakazam": 0.55, "crustle": 0.22, "grimmsnarl": 0.06, "cynthia": 0.06,
    "lucario": 0.035, "dragapult": 0.03, "archaludon": 0.02, "kangaskhan": 0.005,
    "starmie": 0.005, "other": 0.015,
}
_ps = sum(PRIOR.values())
PRIOR = {a: PRIOR.get(a, 0.0) / _ps for a in ARCHS}
LOG_PRIOR = {a: math.log(max(PRIOR[a], 1e-6)) for a in ARCHS}

# Signature Pokemon lines per archetype (lowercase name substrings). Only strong,
# archetype-DEFINING evolution lines -- generic tech (Poffin/Boss/energy) is uninformative.
SIG_NAMES = {
    "alakazam":   ["abra", "kadabra", "alakazam"],
    "crustle":    ["dwebble", "crustle"],
    "grimmsnarl": ["marnie's impidimp", "marnie's morgrem", "marnie's grimmsnarl"],
    "cynthia":    ["cynthia's gible", "cynthia's gabite", "cynthia's garchomp"],
    "lucario":    ["riolu", "makuhita", "hariyama", "mega lucario"],
    "dragapult":  ["dreepy", "drakloak", "dragapult"],
    "archaludon": ["duraludon", "archaludon"],
    "kangaskhan": ["kangaskhan"],
    "starmie":    ["staryu", "mega starmie"],
    "other":      [],
}

# Embedded id fallback (from intel/card_db_full.csv) if runtime name lookup finds nothing.
_SIG_ID_FALLBACK = {
    "alakazam":   [109, 741, 742, 743, 245],
    "crustle":    [344, 345, 532, 533],
    "grimmsnarl": [646, 647, 648],
    "cynthia":    [379, 380, 381],
    "lucario":    [333, 677, 974, 673, 674, 678],
    "dragapult":  [119, 120, 121],
    "archaludon": [169, 839, 992, 170, 840, 190],
    "kangaskhan": [472, 756, 24],
    "starmie":    [1030, 1031],
}


def _build_sig_ids():
    """id -> archetype, resolved from card names (fallback to embedded ids)."""
    id2arch = {}
    table = getattr(O, "CARD_TABLE", {}) or {}
    for cid, c in table.items():
        nm = (getattr(c, "name", None) or "").lower()
        if not nm:
            continue
        if getattr(c, "cardType", None) is not None and not O.is_pokemon(cid):
            continue
        for arch, subs in SIG_NAMES.items():
            if any(s in nm for s in subs):
                id2arch.setdefault(cid, arch)
                break
    if not id2arch:  # DB name lookup unavailable -> embedded ids
        for arch, ids in _SIG_ID_FALLBACK.items():
            for cid in ids:
                id2arch.setdefault(cid, arch)
    return id2arch


SIG_ID_TO_ARCH = _build_sig_ids()

# Representative 60-card lists (exact ids) from top-50 leaderboard decks (top50_decklists.csv
# deck_keys -> derived decks table). One per archetype we can complete; others fall back to junk.
REP_DECKS = {
    "alakazam": {5: 2, 13: 1, 19: 4, 66: 2, 140: 1, 305: 3, 343: 1, 741: 4, 742: 4,
                 743: 4, 1079: 3, 1081: 3, 1086: 4, 1097: 1, 1129: 1, 1152: 4, 1182: 3,
                 1184: 1, 1197: 3, 1225: 4, 1231: 4, 1266: 3},
    "crustle": {1: 1, 11: 4, 14: 4, 18: 4, 343: 1, 344: 4, 345: 4, 756: 4, 1086: 4,
                1087: 1, 1122: 4, 1123: 4, 1147: 4, 1159: 1, 1182: 2, 1197: 4, 1225: 4,
                1227: 4, 1264: 2},
    "grimmsnarl": {7: 10, 66: 3, 112: 3, 140: 1, 235: 1, 305: 3, 646: 4, 647: 2, 648: 4,
                   689: 1, 1079: 4, 1086: 4, 1137: 1, 1152: 4, 1159: 1, 1182: 2, 1197: 1,
                   1227: 4, 1231: 3, 1259: 3, 1260: 1},
    "cynthia": {6: 5, 20: 4, 341: 4, 342: 3, 379: 4, 380: 4, 381: 3, 387: 2, 1080: 1,
                1086: 4, 1097: 2, 1142: 4, 1152: 4, 1173: 3, 1182: 2, 1197: 1, 1203: 1,
                1225: 3, 1227: 4, 1261: 2},
    "dragapult": {2: 3, 5: 4, 7: 2, 66: 1, 112: 2, 119: 4, 120: 4, 121: 3, 140: 1,
                  235: 1, 305: 2, 306: 1, 1071: 1, 1079: 2, 1080: 1, 1086: 4, 1097: 3,
                  1121: 4, 1152: 4, 1182: 3, 1198: 3, 1227: 4, 1240: 1, 1260: 2},
    "lucario": {6: 11, 20: 4, 675: 2, 676: 3, 677: 4, 678: 4, 1102: 4, 1123: 2, 1141: 4,
                1142: 4, 1152: 4, 1159: 1, 1192: 3, 1197: 2, 1227: 4, 1229: 4},
    "archaludon": {8: 13, 169: 4, 190: 4, 666: 4, 1097: 4, 1121: 4, 1122: 4, 1147: 4,
                   1152: 4, 1159: 1, 1185: 4, 1197: 2, 1227: 4, 1244: 4},
}

# Evidence weights (log space, per distinct revealed signature LINE-card).
HIT_W = 2.5     # a revealed signature votes FOR its archetype
MISS_W = 2.0    # ...and against every other archetype
CONF_THRESHOLD = 0.60   # below this, search.py falls back to junk determinization


class BeliefState:
    """Per-game opponent belief. Recomputed from scratch each update (cheap, idempotent)."""

    def __init__(self):
        self.post = dict(PRIOR)
        self.revealed = set()
        self.hits = {a: 0 for a in ARCHS}

    def reset(self):
        self.__init__()

    def _opponent(self, obs):
        try:
            st = obs.current
            yi = st.yourIndex
            return st.players[1 - yi]
        except Exception:
            return None

    def update(self, obs):
        """Fold the currently-revealed opponent cards into the posterior."""
        op = self._opponent(obs)
        if op is None:
            return
        revealed = set()
        try:
            pk = list(op.active or []) + list(op.bench or [])
            for p in pk:
                if p is None:
                    continue
                revealed.add(p.id)
                for ec in (getattr(p, "energyCards", None) or []):
                    revealed.add(ec.id)
                for t in (getattr(p, "tools", None) or []):
                    revealed.add(t.id)
            for c in (op.discard or []):
                if c is not None:
                    revealed.add(c.id)
        except Exception:
            pass
        self.revealed = revealed

        hits = {a: 0 for a in ARCHS}
        for cid in revealed:
            a = SIG_ID_TO_ARCH.get(cid)
            if a is not None:
                hits[a] += 1
        self.hits = hits
        total_sig = sum(hits.values())

        score = {}
        for a in ARCHS:
            off = total_sig - hits[a]
            score[a] = LOG_PRIOR[a] + HIT_W * hits[a] - MISS_W * off
        m = max(score.values())
        exps = {a: math.exp(score[a] - m) for a in ARCHS}
        z = sum(exps.values()) or 1.0
        self.post = {a: exps[a] / z for a in ARCHS}

    def top_archetype(self):
        a = max(self.post, key=lambda k: self.post[k])
        return a, self.post[a]

    def confidence(self):
        return self.top_archetype()[1]

    def rep_deck(self):
        """Representative id->count list for the current top archetype IF we are confident
        AND have a decklist for it; else None (search.py then uses junk determinization)."""
        a, p = self.top_archetype()
        if p < CONF_THRESHOLD:
            return None
        return REP_DECKS.get(a)
