# Measure the Right Unit — release artifact

Companion code release for our Kaggle **Pokémon TCG AI Battle Challenge** Strategy-track
writeup ("Measure the Right Unit: Decision Diffs, Paired Worlds, and Pilot×Deck Audits").

## What this is

- `agent/` — the agent codebase. The submitted v12 configuration = `deck_crustle.csv`
  installed as `deck.csv` + the flag ledger in `FLAGS.md` (defaults in this tree are the
  v11-era code defaults; see `FLAGS.md` for the exact shipped set). Also includes
  `agent/tools/` measurement harnesses (gauntlet, CRN shim source [development-only],
  band tooling).
- `report/` — the writeup body, appendices (negatives ledger, generation ledger, external
  corroboration), `reproducibility.py` (regenerates every figure; light+dark variants in
  `report/figures/`), and the figure gallery README.
- `scripts/` — release build + number-consistency checks + deck-consistency analysis.
- Root `LICENSE` (MIT) and `NOTICES.md` (attributions and exclusions).

## What this is NOT

No competition engine (source or binaries), no competition data dumps, no third-party
agent code, no card artwork. See `NOTICES.md`. The CRN harness is a development-only
testing tool and was never part of any submission.

## Reproduce the figures

```
python report/reproducibility.py
```

Every figure regenerates from committed data blocks inside the script (external CSV reads
have inline fallbacks, so the script is self-contained).
