"""Observation parsing helpers for agent v0.

Provenance:
  * get_card zone lookup      -> own reimplementation (2026-07-22, accessor-map
    form; behavior equivalence-tested against the prior port; the port's form
    followed Kiyotah's public agent — see NOTICES)
  * prize_count               -> own reimplementation (2026-07-25, base-prize
    table + modifier-registry form; behavior equivalence-tested against the
    prior port; the port's form followed Kiyotah's public agent — see NOTICES).
    The prize SEMANTICS (megaEx/ex base prizes; Legacy Energy and Lillie's
    Pearl adjustments) follow Kiyotah's public helper — credit stays. Ids are
    re-derived by NAME from the card DB per agent_design_v0.md, not hard-coded
    ints.
The AreaType->object map and the observation key layout follow
intel/engine_bringup_2026-07-11.md and the engine's public cg/api.py surface.
"""

from cg.api import (  # noqa: F401  (re-exported for other modules)
    AreaType, CardType, EnergyType, OptionType, SelectContext, SelectType,
    Card, Pokemon, all_card_data, all_attack, to_observation_class,
)

# --- Card metadata table (ported from kiyotah: card_table = {c.cardId:c for c in all_card_data()}) ---
try:
    CARD_TABLE = {c.cardId: c for c in all_card_data()}
except Exception:
    CARD_TABLE = {}

# --- Attack metadata table (R2: used by the value function's opponent-threat term
# and by rollout attack selection; damage/cost read straight from the engine DB). ---
try:
    ATTACK_TABLE = {a.attackId: a for a in all_attack()}
except Exception:
    ATTACK_TABLE = {}


def attack_data(aid):
    return ATTACK_TABLE.get(aid)


def _find_card_id(name_substr):
    """Re-derive a card id from its name (spec: don't hard-code the blacklist ints)."""
    for cid, c in CARD_TABLE.items():
        nm = getattr(c, "name", None) or ""
        if name_substr.lower() in nm.lower():
            return cid
    return None


LEGACY_ENERGY_ID = _find_card_id("Legacy Energy")   # spec note: id 12
LILLIE_PEARL_ID = _find_card_id("Lillie's Pearl")   # spec note: id 1172


def card_data(cid):
    return CARD_TABLE.get(cid)


# Accessor map: AreaType -> the observation field holding that area's cards.
# IntEnum==int (and hash equality) holds even though to_dataclass leaves enum
# fields as raw ints (bring-up pitfall #2), so raw-int keys resolve here too.
_AREA_SOURCES = {
    AreaType.DECK:    lambda obs, ps: obs.select.deck,
    AreaType.HAND:    lambda obs, ps: ps.hand,
    AreaType.DISCARD: lambda obs, ps: ps.discard,
    AreaType.ACTIVE:  lambda obs, ps: ps.active,
    AreaType.BENCH:   lambda obs, ps: ps.bench,
    AreaType.PRIZE:   lambda obs, ps: ps.prize,
    AreaType.STADIUM: lambda obs, ps: obs.current.stadium,
    AreaType.LOOKING: lambda obs, ps: obs.current.looking,
}


def get_card(obs, area, index, player_index):
    """AreaType -> Card/Pokemon lookup via `_AREA_SOURCES`. Any invalid area,
    index, or player resolves to None (never raises). Own reimplementation of
    the public area-dispatch API semantics (2026-07-22 rewrite; the original
    if-chain form followed Kiyotah's public agent)."""
    source = _AREA_SOURCES.get(area)
    if source is None:
        return None
    try:
        return source(obs, obs.current.players[player_index])[index]
    except Exception:
        return None


# --- prize table + modifier registry (data for prize_count) ------------------
# Base prizes by card class: the FIRST predicate matching the KO'd Pokemon's
# card data wins (megaEx outranks ex; anything else yields one prize).
_BASE_PRIZES = (
    (lambda data: data.megaEx, 3),
    (lambda data: data.ex, 2),
    (lambda data: True, 1),
)

# Per-attached-card prize modifiers, iterated over the Pokemon's attached-card
# collections. Each entry: (collection accessor, applicability test over the
# (attached card, KO'd Pokemon's card data) pair, prize delta per matching
# copy). All collections share one fail-open guard, so a missing/broken
# collection keeps whatever adjustments were already applied (matching the
# prior port's partial-apply semantics). Named-ID constants (re-derived by
# name above) keep hard-coded card ints out of the source.
_PRIZE_MODIFIERS = (
    # Legacy Energy: each attached copy reduces the prizes given up by one.
    (lambda pk: pk.energyCards,
     lambda card, data: (LEGACY_ENERGY_ID is not None
                         and card.id == LEGACY_ENERGY_ID),
     -1),
    # Lillie's Pearl: reduces prizes only when the KO'd Pokemon is itself a
    # "Lillie" Pokemon (the tool is inert on anything else).
    (lambda pk: pk.tools,
     lambda card, data: (LILLIE_PEARL_ID is not None
                         and card.id == LILLIE_PEARL_ID
                         and "Lillie" in (data.name or "")),
     -1),
)


def prize_count(pokemon):
    """Prizes the opponent takes when this Pokemon is KO'd.

    Base prizes come from the `_BASE_PRIZES` class table (megaEx=3 / ex=2 /
    else 1); `_PRIZE_MODIFIERS` then adjusts per attached card (Legacy Energy;
    Lillie's Pearl on a Lillie Pokemon), clamped at zero. Unknown card data
    defaults to 1. Own reimplementation (2026-07-25 rewrite, behavior
    equivalence-tested against the prior port; the prize semantics follow
    Kiyotah's public helper — see NOTICES). Ids resolved by name."""
    data = CARD_TABLE.get(pokemon.id)
    if data is None:
        return 1
    count = next(prizes for pred, prizes in _BASE_PRIZES if pred(data))
    try:
        for cards_of, applies, delta in _PRIZE_MODIFIERS:
            for card in cards_of(pokemon):
                if applies(card, data):
                    count += delta
    except Exception:
        pass
    return max(0, count)


def is_basic_energy(cid):
    d = CARD_TABLE.get(cid)
    return d is not None and d.cardType == CardType.BASIC_ENERGY


def is_energy(cid):
    d = CARD_TABLE.get(cid)
    return d is not None and d.cardType in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY)


def is_pokemon(cid):
    d = CARD_TABLE.get(cid)
    return d is not None and d.cardType == CardType.POKEMON


def is_supporter(cid):
    d = CARD_TABLE.get(cid)
    return d is not None and d.cardType == CardType.SUPPORTER


def is_item(cid):
    d = CARD_TABLE.get(cid)
    return d is not None and d.cardType == CardType.ITEM


def is_tool(cid):
    d = CARD_TABLE.get(cid)
    return d is not None and d.cardType == CardType.TOOL


def is_basic_pokemon(cid):
    d = CARD_TABLE.get(cid)
    return d is not None and getattr(d, "basic", False)


def opt_type(o):
    """OptionType of an option as a plain int (robust to raw-int enums)."""
    return int(o.type) if o.type is not None else -1


def clamp_selection(indices, min_count, max_count, n_options):
    """Return a legal selection list: unique, in-range, length in [minCount,maxCount].

    Codex fix #7 (count normalization): a missing/None maxCount must default to
    min(n_options, max(minCount, 1)) -- NOT a bare 1 -- so a minCount>1 prompt is
    not silently under-returned (which would be illegal)."""
    min_count = 0 if min_count is None else int(min_count)
    if max_count is None:
        max_count = min(n_options, max(min_count, 1))
    else:
        max_count = int(max_count)
    max_count = min(max_count, n_options)
    min_count = max(0, min(min_count, max_count))
    out = []
    seen = set()
    for i in indices:
        if 0 <= i < n_options and i not in seen:
            out.append(i)
            seen.add(i)
        if len(out) >= max_count:
            break
    # pad to min_count with first legal unused indices
    if len(out) < min_count:
        for i in range(n_options):
            if i not in seen:
                out.append(i)
                seen.add(i)
                if len(out) >= min_count:
                    break
    return out
