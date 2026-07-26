"""Build a FULL-AGENT band-gauntlet opponent row from a frozen submission build.

Why (2026-07-14, v11 pool re-baseline): the generic-pilot crustle_live row reads
96.7% while the live active pair went 4-11 vs tuned crustle mirrors (six
OUR_DECKOUT losses t29-35, twice while ahead on prizes -- intel/
nightly_2026-07-13.md). The list was never the problem; the PILOT was. This tool
turns our own frozen v10 submission build (the strongest tuned crustle pilot we
have) into a gauntlet_band opponent that can pilot ANY deck.csv (the pilot is
deck-generalized via scoring.set_profile_from_deck), giving the instrument
tuned-mirror and tuned-blitz rows: self_mirror, mirror_wall_fdedde79,
mirror_tusk_ee52c8d3, mirror_216305d7, starmie_blitz.

Mechanics (the mirror_ab.py precedent, generalized):
- module stack renamed *_v10b (pilot_v10b.py, scoring_v10b.py, ...) so the
  opponent coexists with the agent under test in ONE gauntlet process;
- the baked `os.environ.setdefault` ledger is converted to an ENV DANCE: save
  the harness arm's PTCG_* env, clear it, HARD-assign the frozen 38-flag v10
  ledger (so scoring_v10b's import-time _flag() reads see ONLY the ledger --
  the opponent must stay CONSTANT across A/B arms and must not inherit arm
  flags via setdefault), then restore the arm env after the import chain;
- a reset stanza (main.py is re-executed fresh every game by gauntlet.py)
  mirrors gauntlet.reset_our(): _last_turn=-1 / _game_elapsed=0 -> pilot's
  _update_clock resets belief + tracker + search breaker on the next decision;
- deck.csv is the row's tuned list; main sets pilot.DECK and re-derives the
  deck profile per exec, so all rows can share the cached *_v10b modules.

Usage (WSL):
  ~/ptcg-venv/bin/python make_fullagent_opp.py <build_dir> <row_dir> <deck_csv>
e.g.
  ~/ptcg-venv/bin/python make_fullagent_opp.py ~/submission_v10_build \
      ~/gauntlet_band/self_mirror /mnt/c/.../agent/deck_crustle.csv
"""
import os
import re
import shutil
import sys

SUFFIX = "_v10b"
MODS = ["pilot", "obs", "scoring", "search", "belief", "opp_tracker"]
IMPORT_REWRITES = [
    ("import obs as O", "import obs%s as O" % SUFFIX),
    ("import scoring as SC", "import scoring%s as SC" % SUFFIX),
    ("import belief as BEL", "import belief%s as BEL" % SUFFIX),
    ("import opp_tracker as OT", "import opp_tracker%s as OT" % SUFFIX),
    ("import search as SE", "import search%s as SE" % SUFFIX),
    ("import pilot as _pilot_mod", "import pilot%s as _pilot_mod" % SUFFIX),
]


def build(build_dir, row_dir, deck_csv):
    build_dir = os.path.expanduser(build_dir)
    row_dir = os.path.expanduser(row_dir)
    os.makedirs(row_dir, exist_ok=True)

    # 1) renamed module stack
    for m in MODS:
        src = open(os.path.join(build_dir, m + ".py"), encoding="utf-8").read()
        for a, b in IMPORT_REWRITES:
            src = src.replace(a, b)
        open(os.path.join(row_dir, m + SUFFIX + ".py"), "w", encoding="utf-8").write(src)

    # 2) main.py: extract the baked setdefault ledger -> env dance + hard assign
    src = open(os.path.join(build_dir, "main.py"), encoding="utf-8").read()
    ledger = re.findall(r'_os\.environ\.setdefault\("(PTCG_[A-Z0-9_]+)", "([^"]*)"\)', src)
    if not ledger:
        sys.exit("no baked setdefault ledger found in %s/main.py" % build_dir)
    src = re.sub(r'_os\.environ\.setdefault\("PTCG_[A-Z0-9_]+", "[^"]*"\)\n', "", src)
    src = src.replace("import os as _os\n", "", 1)
    ledger_lit = ("{" + ", ".join('"%s": "%s"' % kv for kv in ledger) + "}")
    prologue = (
        "import os as _os\n"
        "# FULL-AGENT OPPONENT ENV DANCE (make_fullagent_opp.py): pin the frozen\n"
        "# v10 ledger for the *_%s import chain regardless of the harness arm's\n"
        "# PTCG_* env; the arm env is restored right after the pilot import.\n"
        "_PTCG_SAVED = {k: _os.environ[k] for k in list(_os.environ)"
        " if k.startswith(\"PTCG_\")}\n"
        "for _k in list(_PTCG_SAVED):\n"
        "    del _os.environ[_k]\n"
        "_os.environ.update(%s)\n" % (SUFFIX.strip("_"), ledger_lit)
    )
    marker = "import os\nimport sys\n"
    assert marker in src, "main.py import block not found"
    src = src.replace(marker, marker + prologue, 1)
    for a, b in IMPORT_REWRITES:
        src = src.replace(a, b)
    epilogue = (
        "\n# restore the harness arm's env (opponent ledger already frozen at import)\n"
        "for _k in list(_os.environ):\n"
        "    if _k.startswith(\"PTCG_\"):\n"
        "        del _os.environ[_k]\n"
        "_os.environ.update(_PTCG_SAVED)\n"
        "del _PTCG_SAVED\n"
        "# per-game reset (gauntlet re-executes main.py fresh every game; mirrors\n"
        "# gauntlet.reset_our -> pilot._update_clock resets belief/tracker/breaker)\n"
        "if _PILOT is not None:\n"
        "    _PILOT._last_turn = -1\n"
        "    _PILOT._game_elapsed = 0.0\n"
    )
    anchor = "except Exception:\n    _PILOT = None\n"
    assert anchor in src, "pilot import block not found"
    src = src.replace(anchor, anchor + epilogue, 1)
    open(os.path.join(row_dir, "main.py"), "w", encoding="utf-8").write(src)

    # 3) the tuned deck
    deck = [int(x) for x in open(deck_csv) if x.strip()]
    assert len(deck) == 60, "deck %s has %d cards" % (deck_csv, len(deck))
    open(os.path.join(row_dir, "deck.csv"), "w").write("\n".join(map(str, deck)) + "\n")
    print("built %s (%d-flag ledger, deck %s)" % (row_dir, len(ledger),
                                                  os.path.basename(deck_csv)))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    build(sys.argv[1], sys.argv[2], sys.argv[3])
