# NOTICES — provenance and attribution

This release contains only our own original code and documents, licensed under the root
`LICENSE` (MIT). It deliberately EXCLUDES: the competition engine (source, headers,
wheels, or any binary), competition data dumps or episode archives, and all third-party
agent code. Nothing in this repository grants or implies any license to Pokémon
intellectual property; there is no card artwork or card-image asset anywhere in this tree.

## Ideas and public approaches we credit (no third-party code included)

- **Kiyotah** — two credits. (1) The documented determinization recipe over the
  organizer's public `search_begin/step` API; our exact-attack-resolve integration and
  its failure-boundary analysis are our own work. (2) The prize-count semantics in
  `agent/obs.py` (megaEx/ex base prizes; Legacy Energy and Lillie's Pearl adjustments)
  follow Kiyotah's public helper; the implementation is our reimplementation,
  equivalence-tested against the prior port. No Kiyotah source is included.
- **Masamikobayashi** — the publicly described own-prize inference approach (legal
  own-deck search under the masked observation). The integration and validation in
  `agent/` are ours; no Masamikobayashi source is included.
- **PokeForge** — publicly described the idea of native-shuffle interposition for paired
  testing. Our development-only CRN harness (libstdc++ `random_device` interposition,
  audit, and verdict changes) is an independent implementation. It is a LOCAL TESTING
  tool only: it was never part of any submitted agent, changes no game rules, and alters
  no agent-visible information. Submitted agents use only the documented Search APIs.
- **Ichigoe** — the greedy action-sequencing pattern and scoring-band idiom visible in
  public agents informed early versions of our pilot and scorer; both were reimplemented
  and substantially generalized. No Ichigoe source is included.
- **Romanrozen** — the crash-safe loader / fallback-contract pattern in public agents
  informed the structure of our pilot's safety ladder; ours is a structural
  reimplementation. No Romanrozen source is included.
- **WinDecks, Budew** (ladder team names) — subjects of our counterfactual behavior-diff
  analysis, which replayed publicly available ladder episodes. No code of theirs was ever
  available to us; only public game logs were analyzed. Deck lists we piloted (card-ID
  lists) were observed in publicly visible ladder games.

Provenance sweep (2026-07-22, updated 2026-07-25): the codebase was swept for
ported/adapted fragments before release. Two helpers in `agent/obs.py` formerly carried
code ported from Kiyotah's public agent: `get_card()` (verbatim-ported dispatcher,
reimplemented 2026-07-22 in accessor-map form, equivalence-tested 130/130 cases) and
`prize_count()` (disclosed port, reimplemented 2026-07-25 in base-prize-table +
modifier-registry form, equivalence-tested 529/529 cases). No verbatim third-party code
remains; adapted patterns and semantics are credited above. If you believe any
attribution here is incomplete, contact the authors and we will correct it.

## Trademarks

Pokémon and Pokémon TCG are trademarks of their respective owners. This project is an
independent competition entry and is not affiliated with, endorsed by, or sponsored by
The Pokémon Company, Nintendo, Creatures Inc., or GAME FREAK inc.
