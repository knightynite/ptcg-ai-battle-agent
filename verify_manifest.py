"""Verify every file in this release against MANIFEST_SHA256.txt.

Run from the repo root:  python verify_manifest.py
Exits non-zero if any file is missing, altered, or unlisted.
"""
import hashlib
import os
import sys

MANIFEST = "MANIFEST_SHA256.txt"


def main():
    if not os.path.exists(MANIFEST):
        print(f"{MANIFEST} not found - run from the repository root")
        return 2

    listed, ok, bad, missing = {}, 0, [], []
    with open(MANIFEST, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            digest, path = line.split(None, 1)
            listed[path.strip()] = digest

    for path, want in sorted(listed.items()):
        if not os.path.exists(path):
            missing.append(path)
            continue
        with open(path, "rb") as src:
            got = hashlib.sha256(src.read()).hexdigest()
        if got == want:
            ok += 1
        else:
            bad.append(path)

    on_disk = set()
    for base, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            rel = os.path.relpath(os.path.join(base, name), ".").replace(os.sep, "/")
            if rel != MANIFEST:
                on_disk.add(rel)
    unlisted = sorted(on_disk - set(listed))

    for path in bad:
        print(f"ALTERED  {path}")
    for path in missing:
        print(f"MISSING  {path}")
    for path in unlisted:
        print(f"UNLISTED {path}")

    print(f"\n{ok} verified, {len(bad)} altered, {len(missing)} missing, {len(unlisted)} unlisted")
    return 0 if not (bad or missing or unlisted) else 1


if __name__ == "__main__":
    sys.exit(main())
