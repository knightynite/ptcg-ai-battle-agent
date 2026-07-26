"""Hidden-state tracker (agent v4) -- Phases 1+2 of intel/engine_log_semantics.md sec.5.

Consumes each REAL battle observation (raw dict, incl. obs["logs"]) once per decision
and maintains exact/probabilistic knowledge of the hidden zones:

  PHASE 1 (own side, exact):
    * our_hidden: multiset of our 60 minus everything visible in state (= deck + facedown
      prizes). Recomputed from state every update -- self-healing, no event drift.
    * our_prize_ms: the EXACT facedown-prize multiset, computed the first time an effect
      shows us `select.deck` (our full deck): prizes = hidden - deck snapshot (the
      "prize card tracking" trick, engine_log_semantics.md class (g)). Maintained on
      prize takes/reveals; any inconsistency drops exactness (never guesses).
    * our_deck_ms: exact remaining-deck composition (hidden - prizes) once prizes known.
    * our_p_draw(pred, k): exact/hypergeometric draw odds. Without prize knowledge the
      deck sample is a uniform k-subset of the hidden pool (deck and prizes are
      exchangeable), so P(match) = m/N over the hidden pool -- still exact math.

  PHASE 2 (opponent, knowns + counted unknowns):
    * opp_known_hand: serial->cardId of cards we KNOW are in their hand (public
      searches/returns per the openType masking table; LogType 6 with toArea=Hand).
    * opp_unknown_n: counted unknown hand slots (DrawReverse / hidden moves), rebased
      against state handCount every update (state wins; divergences counted).
    * opp_known_deck: serial->cardId known shuffled/returned into their deck
      (mulligan full-hand reveals, public ToDeck returns) and not seen since.
    * opp_seen: serial->cardId of every opponent identity ever observed (logs + state)
      -> remaining-unknown pool = archetype prior minus opp_seen (by distinct serial).
    * p_opp_in_hand(pred): knowns -> 1.0, else hypergeometric over their unknown hand
      slots vs the hidden pool (deck + unknown hand + facedown prizes).
    * judge_ev(): opponent-side disruption value of a Judge (hand size delta + value of
      known-kept/searched cards destroyed).

Crash-safety contract: update() and every accessor are exception-proof. Any internal
error disables the tracker for the rest of the game (self.ok=False) and every accessor
then returns its safe default -- consumers degrade to exact v3 behavior. No I/O, no
engine/Search-API calls, no logging. Reset per game by pilot._update_clock (same
turn-counter-reset hook as the clock/belief). MUST only be fed real battle obs --
never search_step() observations.
"""

from collections import Counter

try:  # card metadata (judge_ev value weights); tracker works without it
    import obs as O
except Exception:  # pragma: no cover
    O = None

# LogType ints (cg.api.LogType / ApiType.h)
L_SHUFFLE, L_HASBASIC, L_TURNSTART, L_TURNEND = 0, 1, 2, 3
L_DRAW, L_DRAWREV, L_MOVE, L_MOVEREV = 4, 5, 6, 7
L_SWITCH, L_CHANGE, L_PLAY, L_ATTACH, L_EVOLVE, L_DEVOLVE = 8, 9, 10, 11, 12, 13
L_MOVEATT, L_ATTACK, L_HPCHANGE = 14, 15, 16
L_COIN, L_RESULT = 22, 23

# AreaType ints (cg.api.AreaType; 13/14 exist engine-side only: Playing / DeckBottom)
A_DECK, A_HAND, A_TRASH, A_ACTIVE, A_BENCH, A_PRIZE = 1, 2, 3, 4, 5, 6
A_STADIUM, A_ENERGY, A_TOOL, A_PREEVO, A_PLAYER, A_LOOKING = 7, 8, 9, 10, 11, 12
A_PLAYING, A_DECKBOTTOM = 13, 14

_DECK_AREAS = (A_DECK, A_DECKBOTTOM)


def _matches(pred, cid):
    """pred is a card id, a set/frozenset of ids, or a callable(cid)->bool."""
    if callable(pred):
        return bool(pred(cid))
    if isinstance(pred, (set, frozenset)):
        return cid in pred
    return cid == pred


def _p_at_least_one(n_pool, m_match, k_draw):
    """P(>=1 of m marked cards among a uniform k-subset of an n pool)."""
    if m_match <= 0 or k_draw <= 0 or n_pool <= 0:
        return 0.0
    if m_match >= n_pool or k_draw >= n_pool:
        return 1.0
    p_none = 1.0
    for i in range(k_draw):
        p_none *= (n_pool - m_match - i) / float(n_pool - i)
        if p_none <= 0.0:
            return 1.0
    return 1.0 - p_none


class Tracker:
    """Per-game incremental hidden-state tracker. See module docstring."""

    def __init__(self):
        self.reset(None)

    # ------------------------------------------------------------------ lifecycle
    def reset(self, deck60):
        try:
            self.our60 = Counter(int(x) for x in deck60) if deck60 else None
            self.ok = bool(self.our60) and sum(self.our60.values()) == 60
        except Exception:
            self.our60 = None
            self.ok = False
        self.my = None                 # our playerIndex (from state.yourIndex)
        self.div = 0                   # divergence rebase counter (diagnostics)
        self.frozen = False            # Result log seen
        # own side (Phase 1)
        self.our_hidden = Counter()    # our60 - visible - limbo (= deck + fd prizes)
        self.our_prize_ms = None       # Counter | None (exact facedown-prize multiset)
        self.our_deck_order = None     # [ids], last = top; from select.deck; None on shuffle
        self.own_played = {}           # serial -> cid (own played cards; limbo while unseen)
        self.deck_n = [60, 60]         # event-tracked deck counts (cross-check vs state)
        self.state_deck_n = [60, 60]   # last state deckCounts
        self.fd_prizes = [0, 0]        # facedown prize counts from state
        # opponent side (Phase 2)
        self.opp_known_hand = {}       # serial -> cid
        self.opp_known_deck = {}       # serial -> cid
        self.opp_seen = {}             # serial -> cid (every opp identity ever)
        self.opp_unknown_n = 0         # counted unknown opp hand slots
        self.opp_hand_n = 0            # last state handCount
        self.coin_history = []         # [(playerIndex, head)] capped
        self._batch_moved = set()      # serials moved via MoveCard in current log batch
        self._batch_hand = set()       # serials that ENTERED our hand in current batch
        self._amb = [0, 0]             # per-player ambiguous unlogged-source events
        self._h2d_hidden = 0           # opp hidden Hand->Deck moves in current batch
        self._my_hand_serials = set()  # own hand serials at last scrub
        self._my_discard_serials = set()
        self._opp_visible_serials = set()
        # diagnostics (used by the replay/live test harnesses; zero runtime cost)
        self.debug = getattr(self, "debug", False)
        self._divlog = []
        self.prize_checks = 0          # own prize-take identity checks attempted
        self.prize_hits = 0            # ...that matched the predicted prize multiset

    def _div(self, tag):
        """Count a state/event divergence (rebased, never fatal)."""
        self.div += 1
        if self.debug:
            self._divlog.append(tag)

    # ------------------------------------------------------------------ update
    def update(self, obs):
        """Consume one real observation dict. Never raises."""
        if not self.ok:
            return
        try:
            self._update(obs)
        except Exception:
            self.ok = False            # degrade to v3 for the rest of the game

    def _update(self, obs):
        cur = obs.get("current") or {}
        players = cur.get("players") or None
        if players is None or len(players) != 2:
            return
        yi = cur.get("yourIndex")
        if self.my is None:
            if yi not in (0, 1):
                return
            self.my = yi
        elif yi != self.my:
            return   # not our perspective (defensive: mirror-harness/self-play only;
                     # at runtime every obs handed to the agent is our own)
        my, op = self.my, 1 - self.my

        # ---- 1) event pass over the fresh log slice --------------------------------
        self._batch_moved = set()
        self._batch_hand = set()
        self._amb = [0, 0]
        self._h2d_hidden = 0
        for lg in (obs.get("logs") or []):
            self._apply_log(lg, my, op)

        # ---- 2) state scrub + reconciliation (state wins) --------------------------
        mep, opp = players[my], players[op]
        self.state_deck_n = [players[0].get("deckCount", 0) or 0,
                             players[1].get("deckCount", 0) or 0]
        # Attach/ability events carry no source zone (deck-acceleration vs hand); the
        # unresolved ones grant reconciliation slack instead of flagging divergence.
        amb_budget = [self._amb[0], self._amb[1]]
        for pi in (0, 1):
            pz = players[pi].get("prize") or []
            self.fd_prizes[pi] = sum(1 for c in pz if c is None)
            diff = self.deck_n[pi] - self.state_deck_n[pi]
            if diff != 0:
                if 0 < diff <= amb_budget[pi]:
                    amb_budget[pi] -= diff      # unlogged deck departures (accel)
                else:
                    self._div("deckcnt")
                self.deck_n[pi] = self.state_deck_n[pi]

        visible_ids, visible_serials = self._visible_own(cur, mep, my)

        # opp identities visible in state -> opp_seen, and heal stale hand knowns
        self._scrub_opp_state(cur, opp, op)

        # serial sets used to disambiguate next batch's source-less Attach events
        self._my_hand_serials = set(
            c.get("serial") for c in (mep.get("hand") or []) if c is not None)
        self._my_discard_serials = set(
            c.get("serial") for c in (mep.get("discard") or []) if c is not None)

        # own limbo: played cards not yet visible anywhere (mid-resolution)
        for s in [s for s in self.own_played if s in visible_serials]:
            del self.own_played[s]
        limbo = Counter(self.own_played.values())

        hidden = Counter(self.our60)
        hidden.subtract(visible_ids)
        hidden.subtract(limbo)
        neg = [c for c, n in hidden.items() if n < 0]
        if neg:
            self._div("negresid")
            for c in neg:
                del hidden[c]
        self.our_hidden = +hidden

        # own facedown board slots (setup) count toward the expected hidden size
        n_fd_board = sum(1 for c in (mep.get("active") or []) if c is None)
        n_fd_board += sum(1 for c in (mep.get("bench") or []) if c is None)
        n_null_look = sum(1 for c in (cur.get("looking") or []) if c is None)
        expect = self.state_deck_n[my] + self.fd_prizes[my] + n_fd_board
        htot = sum(self.our_hidden.values())
        if htot != expect and htot != expect + n_null_look:
            self._div("hidsize")       # unmodeled edge; sizes rebased implicitly

        # own prize multiset consistency: prizes must be a sub-multiset of hidden
        if self.our_prize_ms is not None:
            if (sum(self.our_prize_ms.values()) != self.fd_prizes[my]
                    or any(self.our_hidden.get(c, 0) < n
                           for c, n in self.our_prize_ms.items())):
                self.our_prize_ms = None       # stale -> drop exactness, never guess
                self._div("prizesub")

        # opp hand reconciliation: knowns + unknowns == handCount (state wins)
        self.opp_hand_n = opp.get("handCount", 0) or 0
        diff_h = len(self.opp_known_hand) + self.opp_unknown_n - self.opp_hand_n
        if diff_h != 0:
            if not (0 < diff_h <= amb_budget[op]):
                self._div("handrec")
            while len(self.opp_known_hand) > self.opp_hand_n:
                self.opp_known_hand.popitem()
            self.opp_unknown_n = max(0, self.opp_hand_n - len(self.opp_known_hand))

        # ---- 3) snapshot hooks ------------------------------------------------------
        sel = obs.get("select") or None
        if sel:
            self._deck_snapshot(sel, my)

    # ------------------------------------------------------------------ log events
    def _apply_log(self, lg, my, op):
        t = lg.get("type")
        p = lg.get("playerIndex")
        if t == L_DRAW:
            self.deck_n[p] -= 1
            if p == my:
                s = lg.get("serial")
                if s is not None:
                    self._batch_hand.add(s)
                if self.our_deck_order:
                    if self.our_deck_order[-1] == lg.get("cardId"):
                        self.our_deck_order.pop()
                    else:
                        self.our_deck_order = None
            if p == op:               # engine never sends these masked-side, but be safe
                s = lg.get("serial")
                if s is not None:
                    self.opp_known_hand[s] = lg.get("cardId")
                    self.opp_seen[s] = lg.get("cardId")
        elif t == L_DRAWREV:
            self.deck_n[p] -= 1
            if p == op:
                self.opp_unknown_n += 1
        elif t == L_MOVE:
            self._apply_move(lg, my, op)
        elif t == L_MOVEREV:
            fa, ta = lg.get("fromArea"), lg.get("toArea")
            if fa == A_DECK:
                self.deck_n[p] -= 1
            if ta in _DECK_AREAS:
                self.deck_n[p] += 1
            if p == op:
                if ta == A_HAND:
                    self.opp_unknown_n += 1
                if fa == A_HAND:
                    if ta in _DECK_AREAS:
                        self._h2d_hidden += 1
                    if self.opp_unknown_n > 0:
                        self.opp_unknown_n -= 1
                    elif self.opp_known_hand:
                        # a known card moved hidden; if it went to deck we still know
                        # it is in the deck (Judge-style full-hand shuffle)
                        s, cid = self.opp_known_hand.popitem()
                        if ta in _DECK_AREAS:
                            self.opp_known_deck[s] = cid
        elif t == L_SHUFFLE:
            if p == my:
                self.our_deck_order = None
            elif p == op and self._h2d_hidden > 0:
                # hidden hand->deck returns followed by their shuffle = Judge/Lillie-
                # class hand reset: every card we knew in that hand is now in the deck.
                # (Conservative for partial returns: loses knowledge, never wrong.)
                for s, cid in self.opp_known_hand.items():
                    self.opp_known_deck[s] = cid
                self.opp_known_hand.clear()
                self._h2d_hidden = 0
        elif t == L_PLAY:
            s, cid = lg.get("serial"), lg.get("cardId")
            if p == my:
                if s is not None:
                    self.own_played[s] = cid
            else:
                self._opp_left_hand(s, cid)
        elif t == L_ATTACH:
            # Attach carries NO source zone: manual attach comes from hand, ability
            # acceleration from deck/discard with no MoveCard companion (replay-
            # verified). Disambiguate by serial knowledge; unresolved -> slack.
            s, cid = lg.get("serial"), lg.get("cardId")
            if s is not None and s in self._batch_moved:
                if p == op:                             # attached -> not in hand
                    self.opp_seen[s] = cid
                    self.opp_known_hand.pop(s, None)
            elif p == my:
                if s is None or s in self._my_hand_serials or s in self._batch_hand:
                    pass                                # hand source (residual covers)
                elif s in self._my_discard_serials:
                    pass                                # discard source (visible zones)
                else:
                    self.deck_n[my] -= 1                # deck acceleration
            elif p == op:
                if s is not None:
                    self.opp_seen[s] = cid
                if s is not None and s in self.opp_known_hand:
                    del self.opp_known_hand[s]          # known hand card attached
                elif s is not None and s in self.opp_known_deck:
                    # was in their deck, but may have been drawn since -> ambiguous
                    del self.opp_known_deck[s]
                    self._amb[op] += 1
                elif s is not None and s in self._opp_visible_serials:
                    pass                                # board/discard source
                else:
                    self._amb[op] += 1                  # unknown hand vs deck source
        elif t == L_EVOLVE:
            # Evolve also carries NO source zone: usually from hand, but deck-evolve
            # abilities exist (replay-verified: Evolve with no companion MoveCard while
            # deckCount drops). Known-hand serials resolve exactly; the rest get slack.
            s, cid = lg.get("serial"), lg.get("cardId")
            if p == my:
                if s is not None and (s in self._my_hand_serials
                                      or s in self._batch_hand):
                    pass                                # hand source (residual covers)
                else:
                    self._amb[my] += 1                  # possible deck-evolve
            elif p == op:
                if s is not None:
                    self.opp_seen[s] = cid
                was_known = self.opp_known_hand.pop(s, None) is not None
                if not was_known:
                    self._amb[op] += 1                  # hand vs deck source unknown
        elif t in (L_SWITCH, L_CHANGE, L_DEVOLVE, L_MOVEATT):
            if p == op:
                for k_id, k_ser in (("cardIdActive", "serialActive"),
                                    ("cardIdBench", "serialBench"),
                                    ("cardIdBefore", "serialBefore"),
                                    ("cardIdAfter", "serialAfter"),
                                    ("cardId", "serial")):
                    s = lg.get(k_ser)
                    if s is not None:
                        self.opp_seen[s] = lg.get(k_id)
        elif t == L_COIN:
            if len(self.coin_history) < 256:
                self.coin_history.append((p, bool(lg.get("head"))))
        elif t == L_RESULT:
            self.frozen = True

    def _apply_move(self, lg, my, op):
        """LogType 6: identity zone move (visible to us per the openType table)."""
        p = lg.get("playerIndex")
        s, cid = lg.get("serial"), lg.get("cardId")
        fa, ta = lg.get("fromArea"), lg.get("toArea")
        if s is not None:
            self._batch_moved.add(s)
        if fa == A_DECK:
            self.deck_n[p] -= 1
        if ta in _DECK_AREAS:
            self.deck_n[p] += 1
        if p == my and ta == A_HAND and s is not None:
            self._batch_hand.add(s)
        if p == op:
            if s is not None:
                self.opp_seen[s] = cid
                if ta == A_HAND:
                    self.opp_known_hand[s] = cid
                    self.opp_known_deck.pop(s, None)
                else:
                    # moved to a non-hand zone -> provably NOT in hand anymore
                    was_known = self.opp_known_hand.pop(s, None) is not None
                    if fa == A_HAND and not was_known and self.opp_unknown_n > 0:
                        self.opp_unknown_n -= 1
                    if ta in _DECK_AREAS:
                        self.opp_known_deck[s] = cid
                    elif fa in _DECK_AREAS or fa == A_LOOKING:
                        self.opp_known_deck.pop(s, None)
        else:
            # our own identity moves
            if fa == A_PRIZE and ta == A_HAND:
                # own prize take (openType 1: we see the identity)
                if self.our_prize_ms is not None:
                    self.prize_checks += 1
                    if self.our_prize_ms.get(cid, 0) > 0:
                        self.prize_hits += 1
                        self.our_prize_ms[cid] -= 1
                        if self.our_prize_ms[cid] == 0:
                            del self.our_prize_ms[cid]
                    # if it was a face-up (already revealed) prize it left the ms at
                    # reveal time; nothing to do -- reconciliation re-checks sizes
            elif ta == A_PRIZE and self.our_prize_ms is not None:
                self.our_prize_ms[cid] += 1
            if s is not None and ta in _DECK_AREAS + (A_PRIZE,):
                self.own_played.pop(s, None)
            if ta in _DECK_AREAS and self.our_deck_order is not None:
                if ta == A_DECK:
                    self.our_deck_order = None    # position unknown (usually + shuffle)
                else:
                    self.our_deck_order.insert(0, cid)   # DeckBottom: index 0 = bottom

    def _opp_left_hand(self, s, cid):
        if s is not None:
            self.opp_seen[s] = cid
        if s is not None and s in self.opp_known_hand:
            del self.opp_known_hand[s]
        elif self.opp_unknown_n > 0:
            self.opp_unknown_n -= 1

    # ------------------------------------------------------------------ state scrub
    def _visible_own(self, cur, mep, my):
        """Multiset of OUR card ids visible in state + the set of visible serials."""
        ids = Counter()
        serials = set()

        def add_card(c):
            if c is None:
                return
            cid = c.get("id")
            if cid is not None:
                ids[cid] += 1
            s = c.get("serial")
            if s is not None:
                serials.add(s)

        def add_pokemon(pk):
            if pk is None:
                return
            add_card(pk)
            for key in ("energyCards", "tools", "preEvolution"):
                for c in (pk.get(key) or []):
                    add_card(c)

        for c in (mep.get("hand") or []):
            add_card(c)
        for c in (mep.get("discard") or []):
            add_card(c)
        for pk in (mep.get("active") or []):
            add_pokemon(pk)
        for pk in (mep.get("bench") or []):
            add_pokemon(pk)
        for c in (mep.get("prize") or []):
            add_card(c)                      # face-up (revealed) prizes only
        for c in (cur.get("stadium") or []):
            if c is not None and c.get("playerIndex") == my:
                add_card(c)
        for c in (cur.get("looking") or []):
            if c is not None and c.get("playerIndex") == my:
                add_card(c)
        return ids, serials

    def _scrub_opp_state(self, cur, opp, op):
        vis = set()

        def see_card(c):
            if c is None:
                return
            s = c.get("serial")
            if s is not None:
                vis.add(s)
                self.opp_seen[s] = c.get("id")
                if s in self.opp_known_hand:      # surfaced elsewhere -> not in hand
                    del self.opp_known_hand[s]
                self.opp_known_deck.pop(s, None)  # surfaced -> not in deck

        def see_pokemon(pk):
            if pk is None:
                return
            see_card(pk)
            for key in ("energyCards", "tools", "preEvolution"):
                for c in (pk.get(key) or []):
                    see_card(c)

        for c in (opp.get("discard") or []):
            see_card(c)
        for pk in (opp.get("active") or []):
            see_pokemon(pk)
        for pk in (opp.get("bench") or []):
            see_pokemon(pk)
        for c in (opp.get("prize") or []):
            see_card(c)                          # face-up opp prizes
        for c in (cur.get("stadium") or []):
            if c is not None and c.get("playerIndex") == op:
                see_card(c)
        for c in (cur.get("looking") or []):
            if c is not None and c.get("playerIndex") == op:
                see_card(c)
        self._opp_visible_serials = vis

    # ------------------------------------------------------------------ snapshots
    def _deck_snapshot(self, sel, my):
        """select.deck = our full remaining deck (ordered, last = top). First clean
        snapshot pins the exact prize multiset: prizes = hidden - deck (class g)."""
        deck = sel.get("deck") or None
        if not deck:
            return
        ids = []
        for c in deck:
            if c is None or c.get("playerIndex") != my:
                return                   # not our deck -> no snapshot
            ids.append(c.get("id"))
        self.our_deck_order = list(ids)

        cand = Counter(self.our_hidden)
        cand.subtract(Counter(ids))
        if any(n < 0 for n in cand.values()):
            self._div("snapneg")
            return
        cand = +cand
        n_cand, n_fd = sum(cand.values()), self.fd_prizes[self.my]
        if n_cand == n_fd:
            pass                          # clean: hidden - deck == the facedown prizes
        elif n_cand == n_fd + 1 and self._effect_id(sel) is not None:
            # the resolving effect card sits in the Playing area (off-state limbo):
            # subtract it if present in the candidate pool
            eid = self._effect_id(sel)
            if cand.get(eid, 0) > 0:
                cand[eid] -= 1
                if cand[eid] == 0:
                    del cand[eid]
            else:
                return
        else:
            return                        # sizes don't reconcile -> don't guess
        if self.our_prize_ms is not None and self.our_prize_ms != cand:
            self._div("snapconflict")
        self.our_prize_ms = cand

    @staticmethod
    def _effect_id(sel):
        for key in ("effect", "contextCard"):
            c = sel.get(key) or None
            if c is not None:
                cid = c.get("id")
                if cid is not None:
                    return cid
        return None

    # ====================================================================== API
    # Every accessor is exception-proof and returns a safe default when not ok.

    # ---- own side (Phase 1)
    def our_prize_known(self):
        """Exact facedown-prize multiset (Counter) or None."""
        try:
            if not self.ok or self.our_prize_ms is None:
                return None
            return Counter(self.our_prize_ms)
        except Exception:
            return None

    def our_deck_ms(self):
        """Exact remaining-deck multiset (Counter) or None (needs prize knowledge)."""
        try:
            if not self.ok or self.my is None or self.our_prize_ms is None:
                return None
            d = Counter(self.our_hidden)
            d.subtract(self.our_prize_ms)
            if any(n < 0 for n in d.values()):
                return None
            d = +d
            if sum(d.values()) != self.state_deck_n[self.my]:
                return None
            return d
        except Exception:
            return None

    def our_pool(self):
        """(pool Counter, pool size, is_exact_deck): the population our next draws are
        a uniform subset of. Exact deck when prizes are known, else deck+prizes."""
        d = self.our_deck_ms()
        if d is not None:
            return d, sum(d.values()), True
        try:
            if not self.ok:
                return None, 0, False
            h = Counter(self.our_hidden)
            return h, sum(h.values()), False
        except Exception:
            return None, 0, False

    def our_remaining(self, pred):
        """Copies matching pred still in our deck (exact) / deck+prize pool (upper bd)."""
        try:
            pool, n, _ = self.our_pool()
            if not pool:
                return 0
            return sum(c for cid, c in pool.items() if _matches(pred, cid))
        except Exception:
            return 0

    def our_prized(self, pred):
        """Copies matching pred KNOWN to be in our prizes; None if prizes unknown."""
        try:
            if not self.ok or self.our_prize_ms is None:
                return None
            return sum(c for cid, c in self.our_prize_ms.items() if _matches(pred, cid))
        except Exception:
            return None

    def our_p_draw(self, pred, k=1):
        """P(>=1 card matching pred among our next k draws). Exact hypergeometric
        (deck and facedown prizes are exchangeable when prizes are unknown)."""
        try:
            pool, n, exact = self.our_pool()
            if not pool or n <= 0:
                return 0.0
            m = sum(c for cid, c in pool.items() if _matches(pred, cid))
            kk = min(k, self.state_deck_n[self.my] if self.my is not None else k, n)
            return _p_at_least_one(n, m, kk)
        except Exception:
            return 0.0

    def our_good_density(self, value_fn, threshold):
        """Fraction of our draw pool with value_fn(cid) >= threshold."""
        try:
            pool, n, _ = self.our_pool()
            if not pool or n <= 0:
                return 0.0
            good = sum(c for cid, c in pool.items() if value_fn(cid) >= threshold)
            return good / float(n)
        except Exception:
            return 0.0

    # ---- opponent side (Phase 2)
    def opp_hand_known(self):
        """Counter(cardId) of cards we KNOW are in the opponent's hand."""
        try:
            if not self.ok:
                return Counter()
            return Counter(self.opp_known_hand.values())
        except Exception:
            return Counter()

    def opp_hand_unknown_n(self):
        try:
            return max(0, self.opp_hand_n - len(self.opp_known_hand)) if self.ok else 0
        except Exception:
            return 0

    def opp_holds(self, pred):
        """True if a KNOWN opponent hand card matches pred."""
        try:
            if not self.ok:
                return False
            return any(_matches(pred, cid) for cid in self.opp_known_hand.values())
        except Exception:
            return False

    def opp_seen_ms(self):
        """Counter(cardId) of every distinct opponent card instance ever observed."""
        try:
            if not self.ok:
                return Counter()
            return Counter(self.opp_seen.values())
        except Exception:
            return Counter()

    def opp_remaining_pool(self, prior_counts):
        """prior 60-list (id->count) minus everything observed, clipped >= 0."""
        try:
            pool = Counter(prior_counts or {})
            pool.subtract(self.opp_seen_ms())
            return +pool
        except Exception:
            return Counter()

    def p_opp_in_hand(self, pred, prior_counts=None):
        """P(opponent holds >=1 card matching pred). Knowns are certain; unknown hand
        slots are a uniform subset of their hidden pool (deck + unknown hand + facedown
        prizes) containing the known-in-deck cards plus the prior residual."""
        try:
            if not self.ok or self.my is None:
                return 0.0
            if self.opp_holds(pred):
                return 1.0
            m = sum(1 for cid in self.opp_known_deck.values() if _matches(pred, cid))
            if prior_counts:
                res = self.opp_remaining_pool(prior_counts)
                # residual copies not otherwise placed (known_deck ids are in opp_seen,
                # so they are already excluded from the residual -- no double count)
                m += sum(c for cid, c in res.items() if _matches(pred, cid))
            hu = self.opp_hand_unknown_n()
            n = (self.state_deck_n[1 - self.my] + hu + self.fd_prizes[1 - self.my])
            return _p_at_least_one(n, m, hu)
        except Exception:
            return 0.0

    def opp_remaining_count(self, pred, prior_counts=None):
        """Estimated copies matching pred the opponent still has in hidden zones + hand."""
        try:
            if not self.ok:
                return 0
            m = sum(1 for cid in self.opp_known_hand.values() if _matches(pred, cid))
            m += sum(1 for cid in self.opp_known_deck.values() if _matches(pred, cid))
            if prior_counts:
                res = self.opp_remaining_pool(prior_counts)
                m += sum(c for cid, c in res.items() if _matches(pred, cid))
            return m
        except Exception:
            return 0

    def judge_known_value(self):
        """Sum of class-values of cards KNOWN in the opponent's hand (what a Judge
        destroys for certain). Supporters/items they searched or kept are worth more
        than energy; capped so a single huge hand can't dominate."""
        try:
            if not self.ok or not self.opp_known_hand:
                return 0.0
            v = 0.0
            for cid in self.opp_known_hand.values():
                v += self._card_value(cid)
            return min(v, 3.0)
        except Exception:
            return 0.0

    def judge_ev(self):
        """Opponent-side disruption EV of a Judge: hand-size delta down to 4 plus the
        value of known-good cards shuffled away. >0 means Judge hurts them."""
        try:
            if not self.ok:
                return 0.0
            return max(0.0, float(self.opp_hand_n - 4)) * 0.5 + self.judge_known_value()
        except Exception:
            return 0.0

    @staticmethod
    def _card_value(cid):
        try:
            if O is None:
                return 0.6
            if O.is_supporter(cid) or O.is_item(cid):
                return 1.0
            if O.is_pokemon(cid):
                return 0.7
            if O.is_energy(cid):
                return 0.5
            return 0.6
        except Exception:
            return 0.6
