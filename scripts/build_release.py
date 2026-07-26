#!/usr/bin/env python3
"""Build the public release export from an explicit allowlist.

Per intel/RELEASE_BLOCKERS_2026-07-15.md: NEVER zip the workspace. This script
copies an allowlist into release_export/, stamps LICENSE + NOTICES + FLAGS at
the root, emits requirements.txt + MANIFEST_SHA256.txt, then runs the automated
reject-list (name globs, path segments, and a private-path content scan); ANY
match fails the build (exit 1) and the export directory is left in place for
inspection but must not be published.

Publishing itself is a human step (explicit release branch / new repo, user in
the loop). This script only stages and verifies.

Usage:
  python scripts/build_release.py [--dest release_export]
  python scripts/build_release.py --list-only     # print selection + verdicts,
                                                  # write nothing
"""

import argparse
import fnmatch
import hashlib
import json
import shutil
import sys
from importlib import metadata as _im
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MARKER_NAME = ".release_export_marker"
MARKER_TEXT = "release export tree staged by scripts/build_release.py\n"

# ---------------------------------------------------------------- allowlist --
# Directories copied recursively (subject to prune + reject afterwards) and
# individual files. Everything not listed stays out — that is the whole point.
# scripts/ is deliberately NOT an allowlisted directory: only the reviewed
# tooling files below ship, so scripts/scheduled/, host automation and logs can
# never ride along.
ALLOW_DIRS = [
    "agent",            # our agent + tools (provenance-swept; see NOTICES)
    "report",           # writeup body, appendices, reproducibility code, figures
]
ALLOW_FILES = [
    # reviewed scripts/ tooling (per-file allowance; see note above)
    "scripts/anchor_settle.py",
    "scripts/build_release.py",
    "scripts/check_numbers.py",
    "scripts/deck_consistency_crustle.py",
    "scripts/endgame_simulator.py",
    # submit/ runbook is internal ops, NOT release material; only code ships.
    "intel/deck_consistency_starmie.md",          # cited by report §5.3 chain
    "intel/deck_consistency_crustle_2026-07-21.md",
]
RELEASE_META = [
    ("release/LICENSE", "LICENSE"),
    ("release/NOTICES.md", "NOTICES.md"),
    ("release/README_RELEASE.md", "README.md"),
    ("release/FLAGS.md", "FLAGS.md"),
]

# The one notebook we ship gets its outputs/execution counts cleared on copy
# (kernel temp paths and machine paths live in outputs; sources are clean).
NOTEBOOK_STRIP = "report/reproducibility.ipynb"

# Paths under the allowlist that must still be pruned (working artifacts that
# are not part of the public artifact).
PRUNE_GLOBS = [
    "report/strategy_report_draft.md",   # internal working draft; body ships via Kaggle
    "scripts/anchor_read_task.*",        # host automation, machine-specific
    "scripts/daily_monitor.sh",          # leaderboard scraping cadence tooling
    "scripts/scheduled/**",              # scheduled ops kit (never release material)
    "agent/**/__pycache__/**",
    "**/*.pyc",
    "**/*.log",
    "**/.ipynb_checkpoints/**",
    # dev harnesses hardcoding machine-private paths (and, for the first two,
    # referencing non-shipped intel); verified unrunnable in the export
    "agent/tools/regress_ep85544056.py",
    "agent/tools/sync_agent.sh",
    "agent/tools/run_ablations_r3.sh",
    "agent/tools/wait_ablations.sh",
]

# ------------------------------------------------------------- reject-list --
# From RELEASE_BLOCKERS §3 — any match anywhere in the export FAILS the build.
REJECT_GLOBS = [
    "*.whl", "*.so", "*.dll", "*.zip", "*.tar.gz", "*.7z",
    "*.exe", "*.pyd", "*.dylib", "*.a", "*.lib", "*.o",
    "*.cmd", "*.log",
    "intel/engine_src/**", "cg/**", "baselines/**",
    "*_main.py", "*_extracted_source.py",
]
# Any relative path containing one of these as a path SEGMENT is rejected
# (segment check, not fnmatch: fnmatch("agent/cg/x.py", "cg/**") is False, so
# glob patterns alone cannot police nested engine/baseline trees).
REJECT_SEGMENTS = {"cg", "engine_src", "baselines"}
# Third-party names whose raw artifacts must never appear as files.
REJECT_NAME_FRAGMENTS = [
    "ichigoe", "kiyotah_mega", "romanrozen", "rl_mcts_extracted",
]
# Private-path / operator-flag content scan over every selected TEXT file
# (utf-8; undecodable files are skipped). Needles are assembled from pieces so
# this file — which itself ships — stays self-scan clean. Both the raw and the
# JSON/string-escaped Windows-path forms are covered.
_BS = chr(92)
FORBIDDEN_CONTENT = [
    ("WINPATH", "C:" + _BS + "Users" + _BS + "AL"),
    ("WINPATH_ESC", "C:" + _BS * 2 + "Users" + _BS * 2 + "AL"),
    ("WSLPATH", "/mnt/c/Users" + "/AL"),
    ("WSLHOME", "/home" + "/al/"),
    ("SKIPPERM", "dangerously-" + "skip-permissions"),
]

REQUIREMENTS_PACKAGES = ["matplotlib", "numpy"]


def matches_any(rel, patterns):
    rp = rel.replace("\\", "/")
    for pat in patterns:
        if fnmatch.fnmatch(rp, pat) or fnmatch.fnmatch(Path(rp).name, pat):
            return True
    return False


def rejected_segment(rel):
    for seg in rel.replace("\\", "/").split("/"):
        if seg in REJECT_SEGMENTS:
            return seg
    return None


def sanitize_notebook_bytes(raw):
    """Clear all cell outputs / execution_count and drop metadata.execution so
    no machine paths or kernel ids ship. Returns utf-8 bytes of the clean nb."""
    nb = json.loads(raw.decode("utf-8"))
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
        if isinstance(cell.get("metadata"), dict):
            cell["metadata"].pop("execution", None)
    return json.dumps(nb, ensure_ascii=False, indent=1).encode("utf-8")


def shipped_bytes(rel, src):
    """The bytes that would actually ship for this selection entry."""
    raw = src.read_bytes()
    if rel.replace("\\", "/") == NOTEBOOK_STRIP:
        return sanitize_notebook_bytes(raw)
    return raw


def content_violations(data):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return []
    return [tag for tag, needle in FORBIDDEN_CONTENT if needle in text]


def reject_verdict(rel, data):
    """List of reject reasons for one would-be export path (empty = OK)."""
    reasons = []
    if matches_any(rel, REJECT_GLOBS):
        reasons.append("glob")
    seg = rejected_segment(rel)
    if seg:
        reasons.append("segment:" + seg)
    low = rel.replace("\\", "/").lower()
    for frag in REJECT_NAME_FRAGMENTS:
        if frag in low:
            reasons.append("name:" + frag)
    if data is not None:
        for tag in content_violations(data):
            reasons.append("content:" + tag)
    return reasons


def build_selection():
    """Return [(rel, src_path)] for everything that would ship, or raise
    SystemExit on a missing allowlist entry. Prune globs apply uniformly."""
    selection = []
    for d in ALLOW_DIRS:
        src = ROOT / d
        if not src.is_dir():
            raise SystemExit("FATAL: allowlisted dir missing: " + d)
        for p in sorted(src.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            if matches_any(rel, PRUNE_GLOBS):
                continue
            selection.append((rel, p))
    for f in ALLOW_FILES:
        src = ROOT / f
        if not src.is_file():
            raise SystemExit("FATAL: allowlisted file missing: " + f)
        if matches_any(f, PRUNE_GLOBS):
            continue
        selection.append((f, src))
    return selection


def check_release_meta():
    for src_rel, _out in RELEASE_META:
        if not (ROOT / src_rel).is_file():
            raise SystemExit("FATAL: release meta file missing: " + src_rel)


def resolve_dest(arg_dest):
    """--dest guard: the destination must be a strict subdirectory of the repo
    root, and must be either release-named, not yet existing, or a directory we
    previously stamped with the export marker. Anything else refuses."""
    dest = (ROOT / arg_dest).resolve()
    if dest == ROOT or ROOT not in dest.parents:
        raise SystemExit(
            "FATAL: --dest must resolve to a subdirectory of the repo root "
            "(got: %s)" % dest)
    if not (dest.name.startswith("release")
            or not dest.exists()
            or (dest / MARKER_NAME).is_file()):
        raise SystemExit(
            "FATAL: --dest exists, is not release-named, and has no %s; "
            "refusing to clear it (got: %s)" % (MARKER_NAME, dest))
    return dest


def write_requirements(dest):
    lines = []
    for pkg in REQUIREMENTS_PACKAGES:
        try:
            ver = _im.version(pkg)
        except _im.PackageNotFoundError:
            raise SystemExit(
                "FATAL: %s not installed in this interpreter; cannot pin "
                "requirements.txt" % pkg)
        lines.append("%s==%s" % (pkg, ver))
    (dest / "requirements.txt").write_text("\n".join(lines) + "\n",
                                           encoding="utf-8")


def write_manifest(dest):
    entries = []
    for p in dest.rglob("*"):
        if not p.is_file() or p.name == "MANIFEST_SHA256.txt":
            continue
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        entries.append((p.relative_to(dest).as_posix(), digest))
    entries.sort()
    out = "".join("%s  %s\n" % (digest, rel) for rel, digest in entries)
    (dest / "MANIFEST_SHA256.txt").write_text(out, encoding="utf-8")
    return len(entries)


def list_only(selection):
    print("would-be selection (%d files) + release meta:" % len(selection))
    any_reject = False
    for rel, src in selection:
        reasons = reject_verdict(rel, shipped_bytes(rel, src))
        if reasons:
            any_reject = True
            print("  REJECT %-60s [%s]" % (rel, ", ".join(reasons)))
        else:
            print("  ok     %s" % rel)
    for src_rel, out_name in RELEASE_META:
        reasons = reject_verdict(out_name, (ROOT / src_rel).read_bytes())
        if reasons:
            any_reject = True
            print("  REJECT %-60s [%s]  (from %s)"
                  % (out_name, ", ".join(reasons), src_rel))
        else:
            print("  ok     %s  (from %s)" % (out_name, src_rel))
    print("plus generated: requirements.txt, MANIFEST_SHA256.txt, %s"
          % MARKER_NAME)
    if any_reject:
        print("reject verdicts present — a real build would FAIL.")
        return 1
    print("reject verdicts: none. A real build would stage cleanly.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="release_export")
    ap.add_argument("--list-only", action="store_true",
                    help="print the would-be selection + reject verdicts; "
                         "write nothing")
    args = ap.parse_args()

    check_release_meta()
    selection = build_selection()

    if args.list_only:
        return list_only(selection)

    dest = resolve_dest(args.dest)

    # Clear CONTENTS rather than rmtree(dest): on Windows a stale cwd handle on
    # the directory root makes os.rmdir fail, but content deletion still works.
    if dest.exists():
        for child in dest.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    dest.mkdir(parents=True, exist_ok=True)
    (dest / MARKER_NAME).write_text(MARKER_TEXT, encoding="utf-8")

    copied = []
    for rel, src in selection:
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if rel == NOTEBOOK_STRIP:
            out.write_bytes(sanitize_notebook_bytes(src.read_bytes()))
        else:
            shutil.copy2(src, out)
        copied.append(rel)
    for src_rel, out_name in RELEASE_META:
        shutil.copy2(ROOT / src_rel, dest / out_name)
        copied.append("%s -> %s" % (src_rel, out_name))

    write_requirements(dest)
    n_manifest = write_manifest(dest)

    # Reject-list scan over the actual export tree (ground truth, not intent):
    # name globs + path segments + private-path content scan on every file.
    violations = []
    for p in dest.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(dest).as_posix()
        reasons = reject_verdict(rel, p.read_bytes())
        if reasons:
            violations.append((rel, reasons))

    print("copied %d files -> %s (manifest: %d entries)"
          % (len(copied), dest, n_manifest))
    if violations:
        print("REJECT-LIST VIOLATIONS (build FAILED, do not publish):")
        for rel, reasons in violations:
            print("  %s [%s]" % (rel, ", ".join(reasons)))
        return 1
    print("reject-list scan: CLEAN. Export staged; publishing remains a human step.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
