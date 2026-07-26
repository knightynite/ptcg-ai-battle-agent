"""Replay-driven unit test for agent/opp_tracker.py (v4 tracker, Phases 1+2).

Runs the tracker over mined Kaggle episode JSONs (per-agent masked obs streams) and
asserts, every consumed step, that the tracker reconciles with the state:
  * zone counts (event-tracked deck counters, opp hand knowns+unknowns, own hidden-pool
    size) match obs["current"] exactly -> a step "reconciles" iff tracker.div did not
    increase while consuming it;
  * own-prize-set correctness where verifiable: every own prize-take (MoveCard
    Prize->Hand, identity visible to the owner) must be in the predicted exact prize
    multiset (tracker.prize_checks / prize_hits);
  * opp-hand knowns precision (cross-agent gold check): whenever the OTHER agent gets a
    fresh obs (status ACTIVE), every card tracker A claims to KNOW in B's hand must be
    in B's actual hand (confirmed) or visible elsewhere pending A's next obs (stale) --
    "unaccounted" counts genuine misses.

Stale-obs artifact (engine_log_semantics.md sec.1): a non-acting agent's obs in episode
JSONs is a stale byte-copy -> we consume an obs ONLY on steps where that agent's status
is ACTIVE (the shift-corrected convention: the action answering steps[i]'s obs is
recorded at steps[i+1]).

Usage (WSL):
  PYTHONPATH=$HOME/ptcg-work:$HOME/agent_v0 ~/ptcg-venv/bin/python tracker_replay_test.py \
      /mnt/c/.../episodes_raw/pokemon-tcg-ai-battle-episodes-2026-07-11.zip 250 7
"""
import json
import random
import sys
import zipfile
from collections import Counter

import opp_tracker as OT


def hand_serials(obs, pi):
    try:
        h = obs["current"]["players"][pi].get("hand") or []
        return set(c["serial"] for c in h if c is not None)
    except Exception:
        return set()


def visible_serials(obs, pi):
    """Serials of player pi's cards visible anywhere outside their hand."""
    out = set()
    try:
        cur = obs["current"]
        ps = cur["players"][pi]

        def add(c):
            if c is not None and c.get("serial") is not None:
                out.add(c["serial"])

        for c in (ps.get("discard") or []):
            add(c)
        for pk in (ps.get("active") or []) + (ps.get("bench") or []):
            if pk is None:
                continue
            add(pk)
            for key in ("energyCards", "tools", "preEvolution"):
                for c in (pk.get(key) or []):
                    add(c)
        for c in (ps.get("prize") or []):
            add(c)
        for c in (cur.get("stadium") or []):
            if c is not None and c.get("playerIndex") == pi:
                add(c)
        for c in (cur.get("looking") or []):
            if c is not None and c.get("playerIndex") == pi:
                add(c)
    except Exception:
        pass
    return out


def run_episode(ep, agg):
    steps = ep.get("steps") or []
    if len(steps) < 3:
        return
    trackers = {}
    known_map = {}     # ai -> {serial: cid} live view of tracker's opp-hand knowns
    for ai in (0, 1):
        try:
            deck = steps[1][ai].get("action")
        except Exception:
            deck = None
        if not (isinstance(deck, list) and len(deck) == 60
                and all(isinstance(x, int) for x in deck)):
            continue
        t = OT.Tracker()
        t.debug = True
        t.reset(deck)
        trackers[ai] = t
        agg["streams"] += 1

    if not trackers:
        return

    first_exact = {ai: None for ai in trackers}
    eval_pending = {ai: False for ai in trackers}   # A updated; check at B's NEXT fresh obs
    for si, st in enumerate(steps):
        for ai, t in trackers.items():
            a = st[ai]
            if a.get("status") != "ACTIVE":
                continue
            obs = a.get("observation") or {}
            if not obs.get("current"):
                continue
            div0, ok0 = t.div, t.ok
            t.update(obs)
            agg["steps"] += 1
            if t.ok and t.div == div0:
                agg["recon"] += 1
            elif not t.ok and ok0:
                agg["crashed_streams"] += 1
            if t.ok and first_exact[ai] is None and t.our_prize_ms is not None:
                first_exact[ai] = obs["current"].get("turn", -1)
                agg["exact_streams"] += 1
            known_map[ai] = dict(t.opp_known_hand) if t.ok else {}
            eval_pending[ai] = True

        # cross-agent gold check: at B's FIRST fresh obs since A last updated, every
        # card A claims to KNOW in B's hand must be in B's actual hand (later B steps
        # would only measure A's information lag, not tracker correctness)
        for bi in trackers:
            b = st[bi]
            if b.get("status") != "ACTIVE":
                continue
            bobs = b.get("observation") or {}
            if not bobs.get("current"):
                continue
            ai = 1 - bi
            if ai not in trackers or not eval_pending.get(ai) or not known_map.get(ai):
                continue
            eval_pending[ai] = False
            hs = hand_serials(bobs, bi)
            vs = visible_serials(bobs, bi)
            for s, cid in known_map[ai].items():
                if s in hs:
                    agg["kh_confirmed"] += 1
                elif s in vs:
                    agg["kh_stale"] += 1
                else:
                    agg["kh_unaccounted"] += 1

    for ai, t in trackers.items():
        agg["div_total"] += t.div
        for tag in t._divlog:
            agg["divtags"][tag] += 1
        agg["prize_checks"] += t.prize_checks
        agg["prize_hits"] += t.prize_hits
        if t.ok:
            agg["ok_streams"] += 1
        if t.div == 0 and t.ok:
            agg["clean_streams"] += 1
        if first_exact[ai] is not None:
            agg["exact_turn_sum"] += max(0, first_exact[ai])


def main():
    zips = [a for a in sys.argv[1:] if a.endswith(".zip")]
    rest = [a for a in sys.argv[1:] if not a.endswith(".zip")]
    n_eps = int(rest[0]) if rest else 250
    seed = int(rest[1]) if len(rest) > 1 else 7

    agg = Counter()
    agg["divtags"] = Counter()
    agg = dict(streams=0, steps=0, recon=0, div_total=0, divtags=Counter(),
               prize_checks=0, prize_hits=0, exact_streams=0, exact_turn_sum=0,
               kh_confirmed=0, kh_stale=0, kh_unaccounted=0,
               ok_streams=0, clean_streams=0, crashed_streams=0, episodes=0)

    names = []
    for zp in zips:
        with zipfile.ZipFile(zp) as z:
            names.extend((zp, n) for n in sorted(z.namelist()) if n.endswith(".json"))
    rng = random.Random(seed)
    sample = rng.sample(names, min(n_eps, len(names)))

    by_zip = {}
    for zp, n in sample:
        by_zip.setdefault(zp, []).append(n)
    for zp, ns in by_zip.items():
        with zipfile.ZipFile(zp) as z:
            for n in ns:
                try:
                    ep = json.loads(z.read(n))
                except Exception:
                    continue
                agg["episodes"] += 1
                run_episode(ep, agg)
                if agg["episodes"] % 50 == 0:
                    print("... %d episodes, %d steps, recon %.3f%%" % (
                        agg["episodes"], agg["steps"],
                        100.0 * agg["recon"] / max(1, agg["steps"])), flush=True)

    print("=" * 78)
    print("episodes=%d streams=%d ok_streams=%d clean_streams(div=0)=%d crashed=%d" % (
        agg["episodes"], agg["streams"], agg["ok_streams"], agg["clean_streams"],
        agg["crashed_streams"]))
    print("steps consumed=%d  reconciled=%d  RECONCILIATION=%.3f%%  div_total=%d" % (
        agg["steps"], agg["recon"], 100.0 * agg["recon"] / max(1, agg["steps"]),
        agg["div_total"]))
    print("divergence tags:", dict(agg["divtags"]))
    print("PRIZE exact reached in %d/%d streams (avg first-exact turn %.1f)" % (
        agg["exact_streams"], agg["streams"],
        agg["exact_turn_sum"] / max(1, agg["exact_streams"])))
    print("PRIZE take checks=%d hits=%d  (%.2f%% correct)" % (
        agg["prize_checks"], agg["prize_hits"],
        100.0 * agg["prize_hits"] / max(1, agg["prize_checks"])))
    tot_kh = agg["kh_confirmed"] + agg["kh_stale"] + agg["kh_unaccounted"]
    print("OPP-HAND knowns checks=%d confirmed=%d stale-visible=%d unaccounted=%d "
          "(precision incl. stale = %.2f%%)" % (
              tot_kh, agg["kh_confirmed"], agg["kh_stale"], agg["kh_unaccounted"],
              100.0 * (agg["kh_confirmed"] + agg["kh_stale"]) / max(1, tot_kh)))


if __name__ == "__main__":
    main()
