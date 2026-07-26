"""Meta-representative gauntlet: our agent v0 vs a roster of frozen public opponents.

Extends smoke_battle.py. For each opponent it runs >=N seat-alternated, paired-seed
games and prints a per-opponent table (WR, Wilson 95% LB, crashes, illegal actions,
our decision p50/p99) plus a META-WEIGHTED aggregate WR -- each opponent weighted by
its archetype's top rating-quartile ladder share (intel/replay_mining_2026-07-10.md:
Alakazam .55, Crustle .22, Grimmsnarl .06, Cynthia .06, others fill the rest .11).
That single number estimates ladder viability against what the top of the ladder
actually looks like (Alakazam + Crustle dominate; Lucario is a rounding error).

Per-game correctness: the opponent module is re-executed fresh every game so no
module-level state leaks across games (policy_base / generic_policy stay cached).
Our pilot state is reset via its known hooks. An abort (crash or an illegal selection
by OUR agent) is scored as OUR loss (conservative).

Run in WSL:
  PYTHONPATH=$HOME/ptcg-work ~/ptcg-venv/bin/python ~/ptcg-work/gauntlet.py <mode>
Modes:
  probe [games]            quick load+play smoke over the whole roster (default 6)
  run   [games] [seed0]    full run + table + meta-weighted WR (default 120 / 12345)
  one   <name> [games] [seed0]
Flags (any mode): --crn / --no-crn  paired engine RNG via crn_shim.so (DEFAULT ON;
  --no-crn or PTCG_CRN=0 reproduces the historical unpaired behavior). With CRN on,
  game index g in arm A and arm B share the same battle world (shuffles/coins), so
  A/B rows are paired: pool with agent/tools/crn_pool.py (per-row McNemar).
  PTCG_CRN_FREE_SEED=<n> pins non-battle entropy (determinism validation);
  PTCG_CRN_HASH=1 prints per-game transcript hashes in `one` mode.

Expects: our agent at ~/agent_v0 (main.py + deck.csv), opponents at ~/gauntlet/<name>/
(main.py + deck.csv, plus policy_base.py/generic_policy.py where imported).
"""
import os, sys, importlib.util, time, traceback, statistics, math, random
import hashlib, json

HOME = os.path.expanduser("~")
# our agent dir; PTCG_OUR_DIR override lets parallel per-deck bakeoff runs coexist
# (deck re-bakeoff 2026-07-12). Default unchanged.
OUR_DIR = os.environ.get("PTCG_OUR_DIR", HOME + "/agent_v0")
GDIR = HOME + "/gauntlet"             # opponent roster root

# ---- CRN: COMMON RANDOM NUMBERS (paired-seed engine RNG) -------------------------------
# 2026-07-13, mandated by agent_v9_results.md item 6: battle-mode engine RNG is unseeded
# (deviceRand=true -> fresh std::random_device per shuffle/coin), which swings n=300 rows
# +/-5-7pp while we chase 1-3pp effects. crn_shim.so (agent/tools/crn_shim.c) interposes
# the libstdc++ std::random_device members that libcg.so imports; per game g we reseed a
# deterministic battle stream with f(seed0, g), so two harness arms (e.g. v8 vs v9) replay
# the SAME stochastic worlds game-for-game and A-B is a paired comparison (McNemar via
# agent/tools/crn_pool.py on the BANDROW outcome strings).
#   Default ON. Disable with --no-crn or PTCG_CRN=0 (exactly reproduces old behavior).
#   PTCG_CRN_SHIM overrides the shim path; PTCG_CRN_FREE_SEED additionally pins the
#   non-battle entropy (the one AgentStart mt19937 seed draw) for full-transcript
#   determinism validation; PTCG_CRN_HASH=1 records per-game transcript hashes.
# The shim MUST be dlopened RTLD_GLOBAL *before* anything loads libcg.so (our agent's
# pilot imports cg.api at load), hence this block sits above the agent load below.
def _crn_flag():
    on = os.environ.get("PTCG_CRN", "1").strip().lower() not in ("0", "off", "no")
    if "--crn" in sys.argv:
        sys.argv.remove("--crn")
        on = True
    if "--no-crn" in sys.argv:
        sys.argv.remove("--no-crn")
        on = False
    return on


CRN = _crn_flag()
CRN_HASH = os.environ.get("PTCG_CRN_HASH", "0") not in ("0", "")
_crn = None
if CRN:
    import ctypes
    _shim_path = os.environ.get("PTCG_CRN_SHIM", HOME + "/ptcg-work/crn_shim.so")
    if not os.path.exists(_shim_path):
        sys.exit("CRN: shim not found at %s\n  build: gcc -shared -fPIC -O2 -o crn_shim.so"
                 " crn_shim.c   (source: agent/tools/crn_shim.c)\n"
                 "  or run with --no-crn / PTCG_CRN=0 for the old unpaired behavior"
                 % _shim_path)
    _crn = ctypes.CDLL(_shim_path, mode=ctypes.RTLD_GLOBAL)
    _crn.PtcgCrnSetSeed.argtypes = [ctypes.c_uint64]
    _crn.PtcgCrnMode.argtypes = [ctypes.c_int]
    _crn.PtcgCrnBattleDraws.restype = ctypes.c_uint64
print("CRN: %s" % ("ON (shim %s)" % _shim_path if _crn else
                   "OFF (unpaired engine RNG -- historical behavior)"), flush=True)


def _crn_game_seed(seed0, g):
    # per-game battle-world seed; any injective-ish mix works (shim splitmixes it again)
    return ((seed0 & 0xFFFFFFFF) * 1000003 + g) & 0xFFFFFFFFFFFFFFFF

# ---- roster: (dir under ~/gauntlet, archetype) ----------------------------------------
ROSTER = [
    ("ryota_alakazam",    "alakazam"),
    ("wmh_alakazam",      "alakazam"),
    ("souta_crustle",     "crustle"),
    ("budew_crustle",     "crustle"),
    ("wmh_grimmsnarl",    "grimmsnarl"),
    ("wmh_garchomp",      "cynthia"),
    ("kiyotah_lucario",   "lucario"),
    ("wmh_dragapult",     "dragapult"),
    ("kiyotah_dragapult", "dragapult"),
    ("masami_archaludon", "archaludon"),
    ("wmh_kangaskhan",    "kangaskhan"),
    ("romanrozen",        "generalist"),
    ("kojimar_baseline",  "generalist"),
    ("wmh_typhlosion",    "other"),
    ("wmh_bellibolt",     "other"),
    # informational row, weight 0 (arch "hops" absent from ARCH_WEIGHT/BAND_WEIGHT):
    # Hop's Snorlax/Cramorant/Trevenant box (SAKU's live list, ep 85544056, engine
    # errorType=0). 2 of 4 v7 live losses on 2026-07-12 with ZERO local coverage
    # (intel/v7_health_check_2026-07-12.md) -- coverage row, not a gate metric.
    ("hops_box",          "hops"),
]
# archetype top-quartile weights (task-specified; the .11 "others" split by ladder presence)
ARCH_WEIGHT = {
    "alakazam": 0.55, "crustle": 0.22, "grimmsnarl": 0.06, "cynthia": 0.06,
    "lucario": 0.035, "dragapult": 0.03, "archaludon": 0.02, "kangaskhan": 0.005,
    "generalist": 0.015, "other": 0.005,
}


def wilson_lb(w, n, z=1.96):
    if n == 0:
        return 0.0
    p = w / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d


def _load(modname, path, wd):
    old = os.getcwd()
    os.chdir(wd)
    if wd not in sys.path:
        sys.path.insert(0, wd)
    try:
        sys.modules.pop(modname, None)
        spec = importlib.util.spec_from_file_location(modname, path)
        m = importlib.util.module_from_spec(spec)
        sys.modules[modname] = m
        spec.loader.exec_module(m)
    finally:
        os.chdir(old)
    return m


# ---- load our agent once --------------------------------------------------------------
our = _load("our_main", OUR_DIR + "/main.py", OUR_DIR)
our.DECK = [int(x) for x in open(OUR_DIR + "/deck.csv") if x.strip()]
import pilot as _pilot          # our agent imported it at load time
_pilot.DECK = our.DECK


def reset_our():
    if hasattr(_pilot, "_last_turn"):
        _pilot._last_turn = -1
    if hasattr(_pilot, "_game_elapsed"):
        _pilot._game_elapsed = 0.0


def opp_deck(name):
    return [int(x) for x in open(GDIR + "/" + name + "/deck.csv") if x.strip()]


def load_opp_fresh(name):
    wd = GDIR + "/" + name
    return _load("opp_" + name, wd + "/main.py", wd)


from cg.game import battle_start, battle_select, battle_finish


def play(name, N, seed0):
    deck_o = opp_deck(name)
    us = lo = draw = 0
    crashes = 0
    illegal = 0
    timeouts = 0
    dtimes = []
    wf = nf = ws = ns = 0          # seat-split: (wins, games) going first / second
    win_steps, loss_steps = [], []  # game length (decision steps) in wins / losses
    # CAP ADJUDICATION (2026-07-13, mandated by the Jul-12 nightly): a game that hits
    # DECISION_CAP unresolved is scored by LOOPER SIDE per the Jun-30 live rule
    # (cabt episodeSteps=10M + "a player entering an infinite loop should eventually
    # lose by timeout"): the side that consumed >90% of the decisions is the looper
    # and LOSES. Neither side >90% (a genuinely long game) stays OUR loss
    # (conservative, matches the old behavior). Previously cap = unconditional OUR
    # loss, which mis-scored the ogerpon_live row (opponent's Solar-Transfer loop =
    # 2,973+/3,000 decisions, we lead the deck race 15/17 -- agent_v8_results.md
    # sec.1: a harness artifact, not a matchup read).
    cap = capw = capl = capu = 0   # capped games: total / adj-win / adj-loss / unresolved
    DECISION_CAP = 3000
    TIMEOUT_S = 520.0
    err = None
    outcomes = []                  # per-game 'W'/'L'/'D' by game index (CRN pairing key)
    ghashes = []                   # per-game transcript hashes (PTCG_CRN_HASH=1)
    for g in range(N):
        random.seed(seed0 + g)
        us_seat = g % 2
        try:
            opp = load_opp_fresh(name)
        except Exception:
            if err is None:
                err = "LOAD: " + traceback.format_exc(limit=4)
            crashes += 1
            lo += 1
            outcomes.append("L")
            ghashes.append("-")
            continue
        reset_our()
        decks = (our.DECK, deck_o) if us_seat == 0 else (deck_o, our.DECK)
        # CRN: reseed the battle-world stream for THIS game index, and confine the
        # deterministic stream to engine battle calls (agents' own search/Python RNG
        # draws stay on the free stream so they can never shift the shared world).
        if _crn:
            _crn.PtcgCrnSetSeed(_crn_game_seed(seed0, g))
            _crn.PtcgCrnMode(1)
        try:
            obs, sd = battle_start(decks[0], decks[1])
        finally:
            if _crn:
                _crn.PtcgCrnMode(0)
        if _crn and _crn.PtcgCrnBattleDraws() == 0:
            sys.exit("CRN: interposition INACTIVE (0 battle draws after battle_start)."
                     " libcg.so bound std::random_device to libstdc++ before the shim"
                     " loaded -- do not trust pairing; fix load order or use --no-crn.")
        if sd.errorPlayer >= 0:
            return {"err": "DECK_ERROR player=%d type=%d" % (sd.errorPlayer, sd.errorType),
                    "tot": 0}
        gh = hashlib.sha1() if CRN_HASH else None
        if gh:
            gh.update(json.dumps(obs["logs"], sort_keys=True, default=str).encode())
        steps = 0
        aborted = None
        our_t = 0.0
        our_dec = opp_dec = 0      # per-side decision counts (cap adjudication)
        while obs["current"]["result"] < 0 and steps < DECISION_CAP:
            yi = obs["current"]["yourIndex"]
            if yi == us_seat:
                our_dec += 1
            else:
                opp_dec += 1
            try:
                if yi == us_seat:
                    t = time.perf_counter()
                    sel = our.agent(obs)
                    dt = time.perf_counter() - t
                    dtimes.append(dt)
                    our_t += dt
                    n = len(obs["select"]["option"])
                    ok = (isinstance(sel, list)
                          and all(isinstance(i, int) and 0 <= i < n for i in sel)
                          and len(set(sel)) == len(sel))
                    if not ok:
                        illegal += 1
                        aborted = "illegal"
                        break
                else:
                    sel = opp.agent(obs)
                if gh:
                    gh.update(repr(sel).encode())
                if _crn:
                    _crn.PtcgCrnMode(1)
                try:
                    obs = battle_select(sel)
                finally:
                    if _crn:
                        _crn.PtcgCrnMode(0)
                if gh:
                    gh.update(json.dumps(obs["logs"], sort_keys=True,
                                         default=str).encode())
            except Exception:
                crashes += 1
                aborted = "crash"
                if err is None:
                    err = "RUN: " + traceback.format_exc(limit=4)
                break
            steps += 1
        if our_t > TIMEOUT_S:
            timeouts += 1
        r = obs["current"]["result"]
        try:
            fp = obs["current"].get("firstPlayer", -1)
        except Exception:
            fp = -1
        battle_finish()
        won = False
        if aborted:
            lo += 1
        elif r < 0:
            # hit DECISION_CAP unresolved -> looper-side adjudication (see above)
            cap += 1
            td = max(1, our_dec + opp_dec)
            if opp_dec > 0.90 * td:
                capw += 1
                us += 1
                won = True             # THEY looped -> live they lose by timeout
            elif our_dec > 0.90 * td:
                capl += 1
                lo += 1                # WE looped -> our loss (correctly)
            else:
                capu += 1
                lo += 1                # genuinely long game: conservative our loss
        elif r == 2:
            draw += 1
        elif r == us_seat:
            us += 1
            won = True
        else:
            lo += 1
        outcomes.append("W" if won else ("D" if (r == 2 and not aborted) else "L"))
        if gh:
            gh.update(("R%d" % r).encode())
            ghashes.append(gh.hexdigest())
        # P0 instrumentation: seat-split WR + win/loss game lengths
        if fp is not None and fp >= 0:
            if fp == us_seat:
                nf += 1
                wf += 1 if won else 0
            else:
                ns += 1
                ws += 1 if won else 0
        if won:
            win_steps.append(steps)
        elif not (r == 2 and not aborted):
            loss_steps.append(steps)
    tot = us + lo + draw
    ds = sorted(dtimes)
    return {"us": us, "lo": lo, "draw": draw, "tot": tot,
            "wr": us / tot if tot else 0.0, "lb": wilson_lb(us, tot),
            "crashes": crashes, "illegal": illegal, "timeouts": timeouts,
            "p50": (statistics.median(ds) * 1000 if ds else 0),
            "p99": (ds[min(len(ds) - 1, int(len(ds) * 0.99))] * 1000 if ds else 0),
            "wf": wf, "nf": nf, "ws": ws, "ns": ns,
            "cap": cap, "capw": capw, "capl": capl, "capu": capu,
            "medw": (statistics.median(win_steps) if win_steps else 0),
            "medl": (statistics.median(loss_steps) if loss_steps else 0),
            "outcomes": "".join(outcomes),      # game-indexed; CRN pairing/McNemar key
            "ghashes": ghashes,                 # per-game transcript sha1 (CRN_HASH)
            "err": err}


HEADER = ("%-20s %-11s %4s  %6s  %8s  %3s  %3s  %3s   %s" %
          ("opponent", "archetype", "n", "ourWR", "WilsonLB", "crs", "ill", "to",
           "p50/p99 ms"))


def fmt_row(name, arch, r):
    if r.get("tot", 0) == 0:
        return "%-20s %-11s  %s" % (name, arch, str(r.get("err", "no games"))[:60])
    seat = ""
    if r.get("nf", 0) or r.get("ns", 0):
        f = 100.0 * r["wf"] / r["nf"] if r["nf"] else 0.0
        s2 = 100.0 * r["ws"] / r["ns"] if r["ns"] else 0.0
        seat = "  1st %4.0f%%(%d) 2nd %4.0f%%(%d) stp %d/%d" % (
            f, r["nf"], s2, r["ns"], r.get("medw", 0), r.get("medl", 0))
    if r.get("cap", 0):
        seat += "  CAP %d(w%d/l%d/u%d)" % (
            r["cap"], r.get("capw", 0), r.get("capl", 0), r.get("capu", 0))
    return ("%-20s %-11s %4d  %5.1f%%  %6.1f%%  %3d  %3d  %3d   %5.2f/%6.2f%s" %
            (name, arch, r["tot"], 100 * r["wr"], 100 * r["lb"], r["crashes"],
             r["illegal"], r["timeouts"], r["p50"], r["p99"], seat))


def run(names, N, seed0):
    print(HEADER)
    print("-" * 96)
    results = {}
    for name, arch in names:
        d = GDIR + "/" + name
        if not os.path.isdir(d) or not os.path.exists(d + "/deck.csv"):
            print("%-20s %-11s  (missing dir/deck -> skipped)" % (name, arch))
            continue
        t0 = time.perf_counter()
        r = play(name, N, seed0)
        r["arch"] = arch
        r["secs"] = time.perf_counter() - t0
        results[name] = r
        print(fmt_row(name, arch, r), " [%.0fs]" % r["secs"])
        if r.get("err") and r.get("tot", 0) == 0:
            print("    -> " + str(r["err"]).replace("\n", "\n       ")[:400])

    by_arch = {}
    for name, arch in names:
        r = results.get(name)
        if not r or r.get("tot", 0) == 0:
            continue
        by_arch.setdefault(arch, []).append(name)
    num = den = 0.0
    print("-" * 96)
    print("meta-weight contributions (weight = archetype top-quartile share / #loaded in archetype):")
    for name, arch in names:
        r = results.get(name)
        if not r or r.get("tot", 0) == 0:
            continue
        w = ARCH_WEIGHT.get(arch, 0.0) / len(by_arch[arch])
        num += w * r["wr"]
        den += w
        print("  %-20s arch=%-11s w=%.4f  wr=%.1f%%" % (name, arch, w, 100 * r["wr"]))
    if den > 0:
        print("-" * 96)
        print("META-WEIGHTED WR (normalized over loaded roster) = %.1f%%" % (100 * num / den))
    wrs = [r["wr"] for r in results.values() if r.get("tot", 0)]
    if wrs:
        print("unweighted mean WR over %d opponents = %.1f%%" %
              (len(wrs), 100 * statistics.mean(wrs)))
    return results


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if mode == "probe":
        g = int(sys.argv[2]) if len(sys.argv) > 2 else 6
        run(ROSTER, g, 12345)
    elif mode == "run":
        g = int(sys.argv[2]) if len(sys.argv) > 2 else 120
        s = int(sys.argv[3]) if len(sys.argv) > 3 else 12345
        run(ROSTER, g, s)
    elif mode == "one":
        name = sys.argv[2]
        g = int(sys.argv[3]) if len(sys.argv) > 3 else 100
        s = int(sys.argv[4]) if len(sys.argv) > 4 else 12345
        arch = dict(ROSTER).get(name, "?")
        print(HEADER)
        r = play(name, g, s)
        print(fmt_row(name, arch, r))
        print("OUTCOMES,%s,%d,%s" % (name, s, r.get("outcomes", "")))
        if CRN_HASH:
            for i, h in enumerate(r.get("ghashes", [])):
                print("GAMEHASH,%s,%d,%d,%s" % (name, s, i, h))
        if r.get("err"):
            print(r["err"])
