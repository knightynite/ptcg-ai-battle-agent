"""Per-context option scoring for agent v0.

Priority-band macro-ordering adapted from intel/kiyotah_mega_lucario_main.py and
intel/ichigoe_mega_lucario_main.py (30000 ability / 20000 play Pokemon / ... bands)
but generalized to card *types* with a small deck-aware override table for the
Starmie list, and with the inherited bugs fixed:
  * we stop taking indices once an option is vetoed (never below minCount) instead
    of always returning maxCount picks (kiyotah/ichigoe bug);
  * Cursed Blast (self-KO ability) is NOT used blanket at 30000 -- only when it
    secures a KO (avoids the ichigoe/kiyotah "ability==30000 always" trap);
  * attack scores come from the Search-API oracle, not a static damage table.
"""

import os
import re
from collections import defaultdict

from cg.api import CardType, OptionType, SelectContext, AreaType
import obs as O


# --- v3 patch flags -------------------------------------------------------------------
# Each WinDecks-playbook patch is independently toggleable for the ablation protocol
# (intel/agent_v3_playbook.md sec.3). Defaults are the shipped v3 config (no env needed
# on Kaggle); the R1 baseline is reproduced exactly with PTCG_P0..P8=0.
def _flag(name, default="1"):
    try:
        return os.environ.get(name, default) == "1"
    except Exception:
        return default == "1"


P0 = _flag("PTCG_P0")          # hygiene: opp-stadium no-op veto + discard inversion
P1 = _flag("PTCG_P1")          # Wally's Compassion un-veto (gated heal)
P2 = _flag("PTCG_P2")          # snipe targeting rewrite + oracle/live target consistency
P3 = _flag("PTCG_P3")          # supporters: Carmine gate / Judge timing / Hilda / Lillie
P4 = _flag("PTCG_P4")          # Ignition/Nebula plan
P5 = _flag("PTCG_P5")          # Duskull->Dusclops->Dusknoir engine, gated
# Measured OFF in the shipped config (intel/agent_v3_results.md): P6's bench cap /
# decline-bench interacted negatively with the P5 engine and the Alakazam pillar
# (v3a/v3b vs v3c/v3d full-gauntlet A/B); P6B never cleared its isolated A/B; P8's
# going-second recipe cost ~15pp vs tuned Crustle inside the stack (blocked engine
# bodies + sacrificial promotes feeding prizes). All remain available for ablation.
P6 = _flag("PTCG_P6", "0")     # tempo: bench cap + decline bench (A/B: negative)
P6B = _flag("PTCG_P6B", "0")   # risky: hold dev items when developed (A/B: no gain)
P7 = _flag("PTCG_P7")          # Duskull pivot retreat
P8 = _flag("PTCG_P8", "0")     # seat-conditional play (A/B: hurt Crustle pillar)

# v4 hidden-state-tracker hooks (agent/opp_tracker.py; intel/engine_log_semantics.md).
# Each is independently toggleable; all off (PTCG_T1..T5=0) reproduces v3 exactly.
T1 = _flag("PTCG_T1", "0")     # Judge timing via judge_ev -- OFF: -9pp ryota in the
                               # v4 ablation (early Judge trades our curated hand too)
T2 = _flag("PTCG_T2")          # Lillie draw-EV from exact remaining-deck composition
T3 = _flag("PTCG_T3")          # KO-over-chip when opp KNOWN to hold switch/heal/scoop
T4 = _flag("PTCG_T4")          # prize-aware energy scarcity (are our W prized?)
T5 = _flag("PTCG_T5")          # stall-guard: no self-KO gifts / big draws on deck clock
                               # (live autopsy 2026-07-11: Crustle library-out loss)
T5N = _flag("PTCG_T5N", "0")   # v5 narrowing of T5 (task #5: T5 re-measured -2.5pp on
                               # souta at N=600, 6/6 seeds): (1) the draw-hold window
                               # tightens deck<=12 -> <=8; (2) during a stall the
                               # self-KO stays ALLOWED for engine/multi-prize KOs --
                               # only the crustle-blanket "any KO is worth it" is
                               # suppressed. OFF: the 3-arm A/B (souta+ryota, N=600
                               # each) measured t5n 62.2% ~ t5old 62.8% pooled -- the
                               # narrowing did NOT recover souta (65.3 vs t5off 70.0),
                               # so v5 keeps v4b's exact T5. NOTE for future work:
                               # t5off beat t5old on BOTH rows in that A/B (+2.4pp
                               # pooled) -- a 15-opponent T5 on/off re-measure is a
                               # candidate next experiment. T5N=0 = v4b's exact T5.

# v5 race-state levers (live autopsy 2026-07-11: the -17.8pp second-seat gap and the
# 700-1000-band bleeders are PRIZE-RACE losses -- "falling behind on the prize race when
# the opponent attacks first" -- not setup failures). Each independently toggleable;
# all off (PTCG_R1..R4=0) reproduces v4b exactly.
R1 = _flag("PTCG_R1")          # race-state evaluator: AHEAD / EVEN / BEHIND(+margin)
R2 = _flag("PTCG_R2", "0")     # behind-race policy (consumes R1; NOT the failed P8
                               # recipe -- no Duskull caps, no sacrificial promotes).
                               # OFF: first cut had 2 measured bugs (see v5 results
                               # sec.3); the fixed cut is only 1-seed-tested and adds
                               # nothing over R1+R3 -- kept toggleable for future work
R3 = _flag("PTCG_R3")          # tank-race math: turns-to-KO tie-break + Nebula plan
                               # (Lucario 340: Jetting 3-shots lose, Nebula 2-shots;
                               # Nebula 210 + Dusknoir blast 130 = exact 340 one-shot)
R4 = _flag("PTCG_R4", "0")     # mirror/attacker-line snipe denial (kill their future
                               # attacker's basic BEFORE it evolves). OFF: solo A/B
                               # bled the ryota pillar ~-6pp over 3 seeds (n=450,
                               # -2.7/-2.7/-14.0) while helping souta/archaludon --
                               # net meta risk at alakazam's .55 weight; toggleable.
                               # r134 (with R3) read benign at 3 seeds -- future gate

# Deck re-bakeoff hooks (2026-07-12): LIGHT per-deck role pins + play-pattern hooks so
# non-Starmie candidate decks get the SPIRIT of the v3-v5 playbook (wall/stall
# discipline, hand-size play, disruption timing) without days of per-deck tuning.
# STRUCTURALLY INERT on the shipped Starmie list: every consumer is additionally gated
# on DECK_KIND != "starmie" (derived from the loaded decklist), so the live Starmie
# path is behavior-identical with DK on or off. PTCG_DK=0 = pure auto-profile
# (hook-fairness ablation). Documented in intel/deck_rebakeoff_2026-07-12.md.
DK = _flag("PTCG_DK")

# v7 Budew lock-and-clock hooks (2026-07-12): the ranked patch list from
# intel/budew_behavior_diff.md -- 59,508 decisions of the #2 player (Budew, LB ~1264)
# on our IDENTICAL Crustle list counterfactually diffed vs the exact shipped v6 config.
# Each patch independently toggleable; all off (PTCG_B1..B6=0) reproduces v6 exactly.
# All consumers are additionally gated on DECK_KIND == "crustle_wall" (or DK card ids
# absent from other decks), so the Starmie/alakazam/rocket paths are untouched.
B1 = _flag("PTCG_B1")   # deck-life economy + stall-lock END band (library = HP;
                        # 5,658 END flips at 99.9% disagreement; 62% of Budew wins
                        # are opponent DECK-OUT; Run-Errand skip median deck 16 vs
                        # our old veto at deck<=6)
B2 = _flag("PTCG_B2")   # gust-lock: Boss's Orders strands a can't-attack body
                        # (Fez ex x87 / Abra x69 flips) + DON'T-BREAK-THE-LOCK
                        # (692 declined attacks, 621 vs an ex hostage; cynthia
                        # 96.5% via 53/55 literal deck-outs)
B3 = _flag("PTCG_B3")   # Kang bench cap / hand economy (1,723 spare-Kang bench
                        # flips: 3-prize Boss bait + bench-out exposure; spares
                        # stay IN HAND)
B4 = _flag("PTCG_B4")   # promote-sac order (Crustle wall > Kang > Shaymin sac >
                        # Dwebble LAST -- feedstock; 403/148/134 promote flips) +
                        # Switch HELD by default (their #1 held card, 2,437 ENDs)
B5 = _flag("PTCG_B5")   # energy role-map (Mist->tank@ACT / Spiky->Kang / Grow
                        # Grass->Crustle / single basic G = emergency Superb fuel;
                        # load the ACTIVE to 3E for Jumbo) + Hero's Cape to the
                        # tank (their 756 vs our 138) + Mist-first fetches
B6 = _flag("PTCG_B6")   # supporter engine: Xerosic priority over early-Hilda
                        # (2,739 vs 1,468 at median opp hand 8), Lillie 6-prize
                        # window widened to hand<=7 (69% usage there), Hilda as
                        # the ~T9 wall/energy refetch, Trimmer at opp hand >=6

# Lever 3 (intel/fable_synthesis_2026-07-16.md sec.2.3, pre-registered in
# intel/supply_rule_2026-07-16.md): prize-multiset resource-supply consumer. Fail-open
# tracker read -> inert (byte-identical to PTCG_SUPPLY_RULE=0) when the tracker is off
# or prize identity hasn't converged. Default ON in the patched build so the CRN A/B is
# flag-vs-flag on one build, not two builds.
SUPPLY_RULE = _flag("PTCG_SUPPLY_RULE")

# Discipline rule (intel/discipline_rule_2026-07-16.md, step 3 of the settlement test in
# intel/codex_top_pilot_reverse_2026-07-15.md): the ONE narrow rule licensed by steps 1-2
# reproducing on a second, independent top-slice pilot (all four over-PLAY/under-ATTACH/
# EVOLVE/END signs held at 20-500x the native-RNG noise floor). Fail-open (tracker/DK/_cw
# gated) -> byte-identical to PTCG_DISCIPLINE_RULE=0 when off, the deck isn't crustle_wall,
# or any state read raises. Default ON in the patched build so the CRN A/B is flag-vs-flag
# on one build, not two builds.
DISCIPLINE_RULE = _flag("PTCG_DISCIPLINE_RULE")
# v8 live-band patches (2026-07-12 evening): the four census patch targets from
# intel/live_band_census_2026-07-12.md sec.6, gated on the live-band gauntlet
# (~/gauntlet_band + agent/tools/band_gauntlet.py). Each independently toggleable;
# all off (PTCG_L1/S1/D1/ST1/O1=0) reproduces the v7(+B2F) behavior exactly. All
# consumers additionally gate on _cw() (crustle profile) -> inert on other decks.
L1 = _flag("PTCG_L1")    # lucario/fighting-threat plan (band .217 @ 32.6% WR):
                         # our FIGHTING-weak 3-prize Mega Kangaskhan is the liability
                         # (Aura Jab 130 -> 260, PPP'd Wild Press 300 exact-KOs it;
                         # diag: every kojimar 6-prize loss = 2 Kang KOs while our
                         # wins are OPP_DECKOUT) -> Kang quarantine + promote-last vs
                         # fighting boards, Boss line-snipe (drag + KO Riolu-class
                         # future attackers / engine bodies), wall {G} payability
                         # (a G source on the active Crustle turns Superb Scissors
                         # on -- the count-only readiness model hid the typed cost)
S1 = _flag("PTCG_S1", "0")  # second-seat wall rush: going 2nd the setup active is
                         # Dwebble (T1 Ascension -> Crustle stands a full turn
                         # earlier); census seat bleed concentrates in the
                         # alakazam-family / bellibolt / grimm rows (-6..-9pp).
                         # OFF: the A/B measured it NEGATIVE on its own target rows
                         # (bellibolt -6.3, grimm -3.0, starmie -3.0, alakazams
                         # flat; n=300/row/arm) -- the Dwebble start costs more
                         # than the T1-Ascension wall gains (the P8 lesson again)
D1 = _flag("PTCG_D1")    # Battle-Cage-aware bench-menace read: Phantom Dive /
                         # Adrena-Brain place damage COUNTERS -- exactly what our
                         # Battle Cage blanks -> with Cage up they do not pierce the
                         # wall; + Cage stadium economy (hold the copy until their
                         # stadium is up (dragapult's Watchtower turns off Run
                         # Errand) or a counter-bench threat shows); + the
                         # bench-menace text read now requires the OPPONENT's bench
                         # (Aura Jab's "your Benched" false-positived the old read)
ST1 = _flag("PTCG_ST1")  # starmie canned-list counter (5fd8867e, 8.9% of band):
                         # Nebula Beam 210 pierces Rock Inn -- the wall is NOT the
                         # win condition; deny the engine instead (Boss line-snipe
                         # covers Staryu/Cinderace via L1 machinery) + keep the
                         # Kang tank Caped and fueled ahead of the wall
O1 = _flag("PTCG_O1", "0")  # stall-tail standoff branch (ogerpon/heal-wall class):
                         # when their board can't touch us (_opp_zero_threat) but
                         # the passive deck race is NOT clearly won, every optional
                         # draw/search ticks the only clock that can still kill us
                         # -> stop Run Errand / Poffin / Pokegear / big draws until
                         # the race flips (attacks stay live: damage is free).
                         # OFF: the A/B measured bellibolt -9.5pp (the stranded-
                         # read standoff froze development in a matchup our racing
                         # draws were winning) and ~0 on ogerpon -- the local
                         # ogerpon row is 85% decided by the OPPONENT's Solar-
                         # Transfer infinite loop hitting the harness 3000-step
                         # cap (scored as our loss; live rule = looper loses by
                         # timeout, cabt episodeSteps=10M + the Jun-30 update)
# v9 patches (2026-07-13): the Jul-12 nightly queue (intel/nightly_2026-07-12.md sec.6).
# Each independently toggleable; both off (PTCG_BF/ED=0) reproduces v8 exactly. All
# consumers _cw()-gated -> inert on other decks.
BF = _flag("PTCG_BF", "0")   # P-BF bench floor: v8's live signature is early
                             # OUR_NOBENCH wipes vs lucario (5/9 losses t2-t11 vs
                             # v7's 1/12) -- the L1a Kang quarantine thins the bench
                             # exactly under Boss/gust aggro. Fix (rev3): quarantine
                             # YIELDS to survival -- when the opponent has shown KO
                             # pressure and our bench is <=1, a held body benches at
                             # the default band; the FIRST Kang joins unless a
                             # weakness-doubled one-shot is payable; a bare bench
                             # (0) releases any Kang; and NOTHING releases in the
                             # SAFE STALL (wall active + _opp_zero_threat), where
                             # the quarantine instead goes ABSOLUTE (the 240 hold
                             # leaks under the B1 lock END band -- 240 > B_END --
                             # which was re-feeding kojimar spare Kangs). rev1
                             # (unconditional release) measured kiyotah +11.0 but
                             # kojimar -6.3; rev3: kiyotah +5.7, kojimar -3.6,
                             # OUR_NOBENCH vs kiyotah 19->11 per 100 (diag seed
                             # 777), kojimar PRIZE_LOSS flat 60->59 (no Kang-feed
                             # regression).
ED = _flag("PTCG_ED", "0")   # P-ED energy-denial resilience: Enhanced Hammer
                             # ("Discard a Special Energy from 1 of your opponent's
                             # Pokemon") / Crushing Hammer (coin: any energy) punish
                             # our 12-special build (Majkel 4xEnh alakazam = 7.1% of
                             # the Jul-12 top dump, 9 teams; 2 v8 live losses to
                             # Comfey/4xCrushing brews). Under an OBSERVED hammer:
                             # (a) the one basic {G} outranks specials onto the
                             # active wall (Enhanced-immune), (b) no sparse special
                             # banking on the bench (hammer food; the attach goes to
                             # the piece being used now), (c) a redundant G source on
                             # the attack-ready active wall is a hammer buffer, not
                             # over-attachment.
                             # OFF (v9 gate): hard-hold cut bled its own target rows
                             # (majkel -4.0 / comfey -5.0, 3/3 seeds); the soft cut
                             # read ~0 on the targets (majkel -1.3, comfey 0.0) but
                             # taxed the OTHER hammer-carrying rows (starmie -4.3,
                             # dragapult -1.3 seed-paired; 7 rows / .43 of band
                             # weight run 3-4 incidental hammers) for a net ~-0.5pp
                             # weighted. Instrument caveat: generic band pilots
                             # don't SEQUENCE hammers like Majkel's 1224-rated bot
                             # -- the local read prices the tempo tax, not the live
                             # resilience. Ships toggleable for a future gate
                             # (S1/O1 precedent).
# v11 patches (2026-07-14): crustle-mirror endgame + starmie blitz, from the Jul-13
# live autopsy (intel/nightly_2026-07-13.md: mirror 4-11 with SIX OUR_DECKOUT losses
# t29-35, twice while AHEAD on prizes; starmie 2-5, killed t4-13). Replay diagnosis
# (the 9 loss + 4 win mirror replays): in every loss we drew 50-73 cards vs the tuned
# bot's 21-44 (Poffin/Pokegear/Hilda/Lillie x12-15 + Run Errand ~1/turn) and decked
# out t28-35; in the one Tusk-mill WIN we drew 36 in 42 turns and won the deck race
# 17-0. The existing B1/B2/O1 economy gates all key on _opp_zero_threat/_lock_clock,
# which are FALSE in real mirrors (their non-ex Crustle always chips our active, and
# the race is not "won"), so NONE of the library discipline ever engages there.
# Both _cw()-gated and default OFF = exact v10 behavior.
MIR = _flag("PTCG_MIR", "0")  # P-MIR mirror deck-life + closure: vs an OBSERVED
                              # crustle-family board (Dwebble/Crustle seen; Great
                              # Tusk 58 = active Land-Collapse MILL of our library),
                              # (a) strict library conservation from early -- Run
                              # Errand off below deck ~30 (Budew skips at med 16;
                              # the tuned mirrors that beat us draw <1.5/turn),
                              # Pokegear/Pad/Ball off late-deck, big-draw supporters
                              # held on a losing clock; (b) prize-race CLOSURE --
                              # when the passive deck race is not clearly won,
                              # attacks get a conversion bonus and Boss's Orders
                              # drags any KILLABLE bench body (Tusk 140 < Kang's
                              # 200 Rapid-Fire) instead of waiting for a hostage
                              # lock that never comes in the mirror.
SBL = _flag("PTCG_SBL", "0")  # P-BLITZ starmie defense: vs an observed Staryu /
                              # Mega Starmie board in the blitz window (their t4-13
                              # kills land before the wall stands: Jetting Blow
                              # 120+50 bench-snipe eats 70-HP Dwebbles, Nebula Beam
                              # 210 pierces Rock Inn), Xerosic's >=6-hand denial
                              # window YIELDS to board development until the wall
                              # line is established -- the t<=9 live losses burned
                              # supporter turns on denial (Xerosic x3 by t9) while
                              # the board died. Tank duty stays with the 300-HP
                              # Caped Kang (ST1 pierce machinery, unchanged).
B2F = _flag("PTCG_B2F")  # v7.1 (2026-07-12, live ep 85544056): B2-class lock-threat
                         # fix. (1) the SELF-KO-RIDER / mutual-KO attack class
                         # ("does N damage to itself", Dynamic Press 140+80self)
                         # disqualifies _opp_zero_threat when near-payable and able
                         # to grind our active down inside the mill horizon -- a
                         # mutual-KO CONVERTS prizes through the stall (T8/T10 END
                         # held a verified 200-vs-150 OHKO; the ensuing trade gave
                         # 3 prizes). (2) an oracle-verified OHKO of their ACTIVE
                         # for a prize is never vetoed on a thin race read. B2F=0
                         # reproduces v7 exactly.

# v12 patches (2026-07-14): Lucario/Mega-Kangaskhan matchup L2 patch spec
# (intel/lucario-root-cause-2026-07-14.md PATCH SPEC #1-#5). Five sub-patches
# under one master switch; PTCG_L2=0 reproduces v11 exactly regardless of the
# subflags -- every consumer is gated `L2 and L2_<NAME> and _cw()`, and further on
# _fighting_threat(tc)/lucario belief where the spec calls for it, so non-Fighting
# matchups and non-crustle decks are byte-identical to v11.
L2 = _flag("PTCG_L2", "0")               # master switch
L2_KANG = _flag("PTCG_L2_KANG", "0")     # #1 hard one-Kang prize-exposure budget
L2_WALL = _flag("PTCG_L2_WALL", "0")     # #2 active-specific wall state + Kang evac
L2_FLOOR = _flag("PTCG_L2_FLOOR", "0")   # #3 predictive non-Kang board floor
L2_BOSS = _flag("PTCG_L2_BOSS", "0")     # #4 Lucario Boss target ordering
L2_CLOCK = _flag("PTCG_L2_CLOCK", "0")   # #5 wall/deck clock replacing zero-threat

# Opponent-archetype belief (BeliefState), injected by pilot.py at import; updated by the
# pilot every decision. Used only for gating (P5 Crustle line, P3 Judge threshold).
BELIEF = None

# Hidden-state tracker (opp_tracker.Tracker), injected + updated by pilot.py every real
# decision. All consumers go through _trk(): tracker off/failed -> exact v3 behavior.
TRACKER = None


def _trk():
    try:
        t = TRACKER
        if t is not None and t.ok:
            return t
    except Exception:
        pass
    return None


def _build_rescue_ids():
    """Trainer cards that can UNDO chip damage next turn: switch the Active out, scoop
    a Pokemon to hand, or heal. Used by T3 (prefer finishing KOs over chip when the
    opponent is KNOWN to hold one). Name-independent: text-pattern scan of the DB."""
    ids = set()
    try:
        pats = (
            re.compile(r"[Ss]witch (your|1 of your).*(Active|Benched)"),
            re.compile(r"[Pp]ut (that|this|1 of your).*Pok.mon.*into (your|its owner..?s) hand"),
            re.compile(r"[Hh]eal (\d+|all) damage"),
        )
        for cid, c in O.CARD_TABLE.items():
            if getattr(c, "cardType", None) not in (
                    CardType.ITEM, CardType.SUPPORTER, CardType.TOOL):
                continue
            for sk in (getattr(c, "skills", None) or []):
                txt = getattr(sk, "text", None) or ""
                if any(p.search(txt) for p in pats):
                    ids.add(cid)
                    break
    except Exception:
        pass
    return ids


RESCUE_IDS = _build_rescue_ids()


def _belief_is(arch, conf=0.60):
    try:
        if BELIEF is None:
            return False
        a, p = BELIEF.top_archetype()
        return a == arch and p >= conf
    except Exception:
        return False

# --- Starmie deck card ids (roles) ---
WATER_ENERGY = 3
IGNITION_ENERGY = 17
STARYU = 1030
MEGA_STARMIE = 1031
DUSKULL, DUSCLOPS, DUSKNOIR = 131, 132, 133
POFFIN, ULTRA_BALL, POKEGEAR, POKE_PAD = 1086, 1121, 1122, 1152
DELUXE_BOMB = 1167
CARMINE, JUDGE, HILDA, LILLIE_DET, WALLY = 1192, 1213, 1225, 1227, 1229

# --- candidate-deck card ids (deck re-bakeoff 2026-07-12; none appear in the Starmie
# list, so every consumer below is a no-op on the shipped deck) ---
XEROSIC, HAND_TRIMMER, JUMBO_ICE, SWITCH_ITEM = 1197, 1087, 1147, 1123
DWEBBLE, CRUSTLE, KANGASKHAN_M = 344, 345, 756          # Budew #2 crustle-wall list
ABRA, ALAKAZAM_ID = 741, 743                            # Yushin/Majkel alakazam list
TAROUNTULA, SPIDOPS, MEWTWO_TR = 400, 401, 431          # kashiwashira rocket list
# v7 crustle-list ids (card texts verified in intel/card_db_full.csv):
#   Mist Energy 11: {C} + "prevent all EFFECTS of attacks" on the holder;
#   Spiky Energy 14: {C} + 2 counters on the attacker while holder is Active;
#   Grow Grass 18: provides {G} (+20 HP to a {G} Pokemon) -- with the SINGLE basic
#   {G} (id 1) these are the only payers of Superb Scissors' {G} cost;
#   Shaymin 343: Flower Curtain bench shield, Budew's designated sacrifice;
#   Hero's Cape 1159 (ACE SPEC): +100 HP tool; Boss's Orders 1182: the gust.
SHAYMIN_CR, HEROS_CAPE, BOSS_ORDERS, BATTLE_CAGE = 343, 1159, 1182, 1264
MIST_ENERGY, SPIKY_ENERGY, GROW_GRASS, BASIC_G = 11, 14, 18, 1

# Abilities that Knock Out their own user (Cursed Blast): counter payload.
SELF_KO_ABILITY_DAMAGE = {DUSCLOPS: 50, DUSKNOIR: 130}

# --- Deck profile (generalized; injected by set_profile_from_deck at load) -------------
# R3 pilotability-bakeoff generalization: the three load-bearing "which cards are my
# attackers / feeders / energy" role sets are AUTO-DERIVED from the decklist by a single
# deck-agnostic algorithm (set_profile_from_deck), so the pilot code is byte-identical
# across every candidate deck. Defaults below are the shipped Mega Starmie ex profile so
# nothing breaks if injection is skipped. The only per-deck knowledge that remains hard-
# coded is Starmie's shipped micro-vetoes (the Duskull/Dusclops/Dusknoir trap line and the
# Wally-bounce heal), which are keyed by card id and are therefore inert no-ops for every
# other deck -- a slight edge retained by the *incumbent*, i.e. conservative for the bakeoff.
MAIN_ATTACKERS = {MEGA_STARMIE}   # Pokemon we build energy onto / want active
FEEDER_BASICS = {STARYU}          # basics that evolve into (or are) an attacker
PRIMARY_ENERGIES = {WATER_ENERGY}  # the deck's Basic energy id(s)
DECK_OWNER_PREFIXES = set()        # owner tags of our Pokemon ("marnie", ...); Starmie: none
DECK_KIND = "starmie"              # starmie | crustle_wall | alakazam | rocket | generic
WALL_IDS = set()                   # our shield-wall Pokemon (crustle_wall: {CRUSTLE})


def set_profile_from_deck(deck):
    """Auto-derive (MAIN_ATTACKERS, FEEDER_BASICS, PRIMARY_ENERGIES) from a 60-card deck.

    Algorithm (identical for every deck): a Pokemon is a candidate attacker if it is
    'top of line' (nothing in the deck evolves from it) and has an attack with base
    damage > 0; the primary is the highest (max_dmg, +mega/ex bonus); MAIN_ATTACKERS =
    every top-of-line attacker within 70% of the primary's damage. FEEDER_BASICS = the
    Basic Pokemon whose evolution line reaches a MAIN_ATTACKER (or basic attackers
    themselves). PRIMARY_ENERGIES = the Basic energy ids in the deck.

    Incumbent override: if the shipped Mega Starmie ex is present, pin the profile to the
    shipped {Mega Starmie}/{Staryu} so the baseline reproduces exactly (the deck's Duskull
    -> Dusknoir line is a deliberately-dormant self-KO engine, not an attacker). Wrapped so
    any failure leaves the safe Starmie defaults in place."""
    global MAIN_ATTACKERS, FEEDER_BASICS, PRIMARY_ENERGIES, DECK_OWNER_PREFIXES
    global DECK_KIND, WALL_IDS
    try:
        ids = set(int(x) for x in deck)

        def cd(cid):
            return O.card_data(cid)

        def max_dmg(cid):
            d = cd(cid)
            best = 0
            for aid in (getattr(d, "attacks", None) or []):
                a = O.attack_data(aid)
                if a is not None:
                    best = max(best, a.damage or 0)
            return best

        pokes = [c for c in ids if O.is_pokemon(c)]
        name = {c: (getattr(cd(c), "name", None) or "") for c in pokes}
        # owner-tagged Pokemon we run ("Marnie's ..."), for the P0 stadium no-op veto
        owners = set()
        for c in pokes:
            m = re.match(r"([A-Za-z]+)['’]s\s", name[c])
            if m:
                owners.add(m.group(1).lower())
        DECK_OWNER_PREFIXES = owners
        evolved_from = set()
        for c in pokes:
            ef = getattr(cd(c), "evolvesFrom", None)
            if ef:
                evolved_from.add(ef)
        top = [c for c in pokes if name[c] not in evolved_from and max_dmg(c) > 0]
        if not top:
            return
        def ascore(c):
            d = cd(c)
            s = max_dmg(c)
            if getattr(d, "megaEx", False):
                s += 40
            elif getattr(d, "ex", False):
                s += 20
            return s
        top.sort(key=ascore, reverse=True)
        pd = max_dmg(top[0])
        attackers = set(c for c in top if max_dmg(c) >= 0.7 * pd)

        def reaches(c0):
            cur = {name[c0]}
            for _ in range(4):
                nxt = set()
                for pc in pokes:
                    if getattr(cd(pc), "evolvesFrom", None) in cur:
                        if pc in attackers:
                            return True
                        nxt.add(name[pc])
                if not nxt:
                    return False
                cur = nxt
            return False

        feeders = set()
        for c in pokes:
            if not O.is_basic_pokemon(c):
                continue
            if c in attackers or reaches(c):
                feeders.add(c)

        energies = set(c for c in ids if O.is_basic_energy(c))

        # incumbent override: reproduce the shipped Mega Starmie ex baseline exactly
        if MEGA_STARMIE in attackers:
            attackers = {MEGA_STARMIE}
            feeders = {STARYU}

        # --- deck re-bakeoff role pins (2026-07-12) -----------------------------------
        # Light per-deck knowledge the deck-agnostic derivation cannot see. Each pin is
        # documented in intel/deck_rebakeoff_2026-07-12.md; PTCG_DK=0 disables them all.
        kind = "starmie" if MEGA_STARMIE in ids else "generic"
        wall = set()
        if kind != "starmie" and DK:
            if CRUSTLE in ids and KANGASKHAN_M in ids:
                # Budew crustle-wall list: Crustle is a WALL (Mysterious Rock Inn blanks
                # ex attack damage), NOT an attacker; Mega Kangaskhan ex is the win
                # condition and Dwebble feeds the wall line.
                kind = "crustle_wall"
                attackers = {KANGASKHAN_M}
                feeders = {KANGASKHAN_M, DWEBBLE}
                wall = {CRUSTLE}
            elif ALAKAZAM_ID in ids:
                # Powerful Hand is dynamic damage (DB damage 0) -> the auto-derivation
                # misses the deck's actual attacker entirely; pin the Abra line.
                kind = "alakazam"
                attackers = {ALAKAZAM_ID}
                feeders = {ABRA}
            elif SPIDOPS in ids:
                # Rocket Rush is dynamic too; Mewtwo ex 160 is the payoff attacker.
                kind = "rocket"
                attackers = {MEWTWO_TR, SPIDOPS}
                feeders = {TAROUNTULA, MEWTWO_TR}
            # Special energies pay attack costs on all these lists (Telepath / Mist /
            # Spiky / Grow Grass / Team Rocket's) -> count them as primary fuel so the
            # discard-protection / Hilda-refuel / race-fuel reads see them.
            energies |= set(c for c in ids
                            if O.is_energy(c) and not O.is_basic_energy(c))
        DECK_KIND = kind
        WALL_IDS = wall

        if attackers:
            MAIN_ATTACKERS = attackers
        if feeders:
            FEEDER_BASICS = feeders
        if energies:
            PRIMARY_ENERGIES = energies
    except Exception:
        pass  # keep safe defaults

# Priority bands (MAIN context)
B_ABILITY = 30000
B_PLAY_POKEMON = 20000
B_PLAY_ITEM = 11000
B_EVOLVE = 9000
B_ATTACH_ENERGY = 8000
B_ATTACH_TOOL = 7000
B_SUPPORTER_EARLY = 12000
B_SUPPORTER_LATE = 2500
B_RETREAT = 2600
B_ATTACK_BASE = 1000
B_END = 0
VETO = -1

# =====================================================================================
# R2 value function (linear, interpretable). Weights tuned briefly on the gauntlet;
# see intel/agent_R2_results.md. Prize differential dominates by design.
# =====================================================================================
W_PRIZE = 1000.0        # per prize of differential (opp_remaining - my_remaining)
W_KO = 250.0            # bonus for taking >=1 prize (KO'd their active) this turn
W_THREAT = 550.0        # penalty if opponent's active can KO our active next turn
W_BOARD = 1.0           # per (hp + energy-unit) of board tempo differential
W_ENERGY_UNIT = 35.0    # value of one energy attached toward an attack (board term)
W_READY = 200.0         # our active is attack-ready next turn (has energy for its attack)
W_BENCH_READY = 8.0     # per energy banked on a benched attacker (small tempo credit)
W_SUCCESSOR = 120.0     # a benched attacker is itself attack-ready (a fuelled successor)...
W_SUCCESSOR_THREAT = 320.0  # ...worth much more when the active is under return-KO threat
W_DECKOUT = 40.0        # per card below the deck-low threshold
W_DECKOUT_HARD = 1500.0 # about to deck out
TERMINAL_WIN = 1.0e6
TERMINAL_LOSS = -1.0e6
TERMINAL_DRAW = -2.0e5   # a draw is bad for us (we need wins) but far better than a loss


def _poke_iter(ps):
    out = []
    if ps is None:
        return out
    if ps.active and ps.active[0] is not None:
        out.append(ps.active[0])
    for p in (ps.bench or []):
        if p is not None:
            out.append(p)
    return out


def _energy_count(pokemon):
    try:
        return len(pokemon.energies)
    except Exception:
        return 0


def _min_attack_cost(cid):
    """Cheapest attack energy requirement (count) for a card id; None if it has no attack."""
    d = O.card_data(cid)
    if d is None or not getattr(d, "attacks", None):
        return None
    best = None
    for aid in d.attacks:
        a = O.attack_data(aid)
        if a is None:
            continue
        need = len(a.energies)
        if best is None or need < best:
            best = need
    return best


def _is_attacker_card(cid):
    return cid in MAIN_ATTACKERS or cid in FEEDER_BASICS


def active_attack_ready(pokemon):
    """True if this Pokemon has enough energy attached to use its cheapest attack."""
    if pokemon is None:
        return False
    need = _min_attack_cost(pokemon.id)
    if need is None:
        return False
    return _energy_count(pokemon) >= need


def opp_best_attack_damage(opp_active, my_active):
    """Max damage the opponent's active could deal to our active with the energy it
    currently has attached (weakness doubles). Static threat estimate (the 'opponent
    attacks for max resolved damage' model from the R2 spec; a full opponent rollout
    is deferred to R3)."""
    if opp_active is None:
        return 0
    d = O.card_data(opp_active.id)
    if d is None or not getattr(d, "attacks", None):
        return 0
    have = _energy_count(opp_active)
    best = 0
    for aid in d.attacks:
        a = O.attack_data(aid)
        if a is None:
            continue
        if len(a.energies) > have:      # can't pay for it right now
            continue
        dmg = a.damage or 0
        best = max(best, dmg)
    if best <= 0:
        return 0
    # weakness: our active takes double if its weakness matches the attacker's type
    try:
        my_data = O.card_data(my_active.id) if my_active is not None else None
        if (my_data is not None and my_data.weakness is not None
                and d.energyType is not None and int(my_data.weakness) == int(d.energyType)):
            best *= 2
    except Exception:
        pass
    return best


def position_value(state, me, prizes_before_me):
    """Linear value of a rolled-out position from OUR (player `me`) perspective.
    `state` is the search observation's `current` State after our turn line resolves.
    `prizes_before_me` is len(our prize) at the search root (to detect KOs we made)."""
    if state is None:
        return 0.0
    result = getattr(state, "result", -1)
    if result is not None and result >= 0:
        if result == me:
            return TERMINAL_WIN
        if result == 2:
            return TERMINAL_DRAW
        return TERMINAL_LOSS

    my = state.players[me]
    op = state.players[1 - me]
    my_rem = len(my.prize)
    opp_rem = len(op.prize)

    v = W_PRIZE * (opp_rem - my_rem)

    prizes_taken = max(0, prizes_before_me - my_rem)
    if prizes_taken > 0:
        v += W_KO

    # board tempo: hp + energy invested, ours minus theirs
    my_board = 0.0
    for p in _poke_iter(my):
        my_board += getattr(p, "hp", 0) + W_ENERGY_UNIT * _energy_count(p)
    op_board = 0.0
    for p in _poke_iter(op):
        op_board += getattr(p, "hp", 0) + W_ENERGY_UNIT * _energy_count(p)
    v += W_BOARD * (my_board - op_board)

    # our active ready to attack next turn
    my_active = my.active[0] if (my.active and my.active[0] is not None) else None
    if active_attack_ready(my_active):
        v += W_READY

    # opponent return-KO threat on our active
    opp_active = op.active[0] if (op.active and op.active[0] is not None) else None
    threatened = (my_active is not None
                  and opp_best_attack_damage(opp_active, my_active) >= getattr(my_active, "hp", 0))
    if threatened:
        v -= W_THREAT

    # second-attacker banking: a small per-energy tempo credit, plus a large bonus when a
    # benched attacker is itself attack-READY -- worth much more when the active is threatened
    # (the "energy-starved fresh attacker" fix: have a fuelled successor before the active dies).
    succ_ready = False
    for p in (my.bench or []):
        if p is not None and _is_attacker_card(p.id):
            v += W_BENCH_READY * _energy_count(p)
            if active_attack_ready(p):
                succ_ready = True
    if succ_ready:
        v += W_SUCCESSOR_THREAT if threatened else W_SUCCESSOR

    # deck-out risk
    dc = my.deckCount
    if dc <= 1:
        v -= W_DECKOUT_HARD
    elif dc <= 5:
        v -= W_DECKOUT * (6 - dc)

    return v


class TurnCtx:
    """Cheap per-decision board summary."""

    def __init__(self, obs):
        st = obs.current
        self.st = st
        self.yi = st.yourIndex
        self.me = st.players[self.yi]
        self.op = st.players[1 - self.yi]
        self.field_counts = defaultdict(int)
        self.hand_counts = defaultdict(int)
        self.discard_counts = defaultdict(int)
        cards = list(self.me.active or []) + list(self.me.bench or [])
        for c in cards:
            if c is not None:
                self.field_counts[c.id] += 1
        for c in (self.me.hand or []):
            self.hand_counts[c.id] += 1
        for c in (self.me.discard or []):
            self.discard_counts[c.id] += 1
        self.active = self.me.active[0] if (self.me.active and self.me.active[0] is not None) else None
        self.developed = any(pid in MAIN_ATTACKERS for pid in self.field_counts)
        self.hand_size = self.me.handCount
        self.deck_low = self.me.deckCount <= 6
        # v3 additions (pure reads; no behavior change while all patch flags are off)
        self.bench_n = sum(1 for p in (self.me.bench or []) if p is not None)
        self.dus_in_play = sum(self.field_counts.get(c, 0)
                               for c in (DUSKULL, DUSCLOPS, DUSKNOIR))
        fp = getattr(st, "firstPlayer", -1)
        fp = -1 if fp is None else fp
        self.going_first = (fp == self.yi)
        self.going_second = (fp >= 0 and fp != self.yi)


def select_by_scores(scores, sel, n):
    """Legal single/multi selection honoring minCount/maxCount; drop vetoed picks
    beyond minCount (fixes the kiyotah/ichigoe always-return-maxCount bug). Shared by
    the pilot's greedy floor and the search rollout so both pick options identically."""
    mn = sel.minCount if sel.minCount is not None else 0
    mx = sel.maxCount if sel.maxCount is not None else 1
    mx = min(mx, n)
    mn = max(0, min(mn, mx))
    order = sorted(range(n), key=lambda i: scores[i], reverse=True)
    take = order[:mx]
    while len(take) > mn and scores[take[-1]] <= VETO:
        take.pop()
    return O.clamp_selection(take, mn, mx, n)


def pokemon_score(pokemon):
    """Value of KO-ing / targeting an opponent Pokemon. Adapted from kiyotah
    pokemon_score() (prizes dominate, then investment, then hp)."""
    data = O.card_data(pokemon.id)
    score = O.prize_count(pokemon) * 1000
    try:
        score += len(pokemon.energies) * 120
        score += len(pokemon.tools) * 80
    except Exception:
        pass
    if data is not None:
        if getattr(data, "stage2", False):
            score += 250
        elif getattr(data, "stage1", False):
            score += 130
    score += getattr(pokemon, "hp", 0)
    return score


def _opponent_can_be_ko_by_ability(tc, dmg):
    """Any opponent Pokemon with <= dmg remaining HP (Cursed Blast KO check)."""
    best = None
    for grp in ((tc.op.active or []), (tc.op.bench or [])):
        for p in grp:
            if p is not None and p.hp <= dmg:
                v = pokemon_score(p)
                if best is None or v > best:
                    best = v
    return best  # None if no KO available


# ================================ v3 patch helpers ====================================

# Names that something in the card DB evolves from -> "evolving" Pokemon detection (P2).
try:
    EVOLVING_NAMES = set(
        getattr(c, "evolvesFrom", None) for c in O.CARD_TABLE.values()
        if getattr(c, "evolvesFrom", None))
except Exception:
    EVOLVING_NAMES = set()


def _engine_target(cid):
    """Non-ex engine/evolving Pokemon (Abra/Kadabra/Dwebble/Shaymin class). The WD
    snipe profile kills these over tanks (windecks_behavior_diff.md sec.4)."""
    d = O.card_data(cid)
    if d is None:
        return False
    if getattr(d, "ex", False) or getattr(d, "megaEx", False):
        return False
    if (getattr(d, "name", None) or "") in EVOLVING_NAMES:
        return True
    if getattr(d, "skills", None):
        return True  # draw/search/support ability carrier (Shaymin/Comfey/Munkidori)
    return False


def _attack_shielded(cid):
    """Card carries a 'prevent all damage ... by attacks' shield ability (Crustle's
    Mysterious Rock Inn, Shaymin's Flower Curtain). Ability damage counters and
    Nebula Beam pierce these; our normal ex attacks do not."""
    d = O.card_data(cid)
    for sk in (getattr(d, "skills", None) or []):
        t = (getattr(sk, "text", None) or "").lower()
        if "prevent all damage" in t and "attack" in t:
            return True
    return False


def _combo_target_ok(card):
    """A chip-into-lethal target must be worth the setup: multi-prize, or the shielded
    wall in a Crustle-classified matchup (where our ex attacks otherwise deal 0)."""
    if O.prize_count(card) >= 2:
        return True
    return _belief_is("crustle") and _attack_shielded(card.id)


def _wall_mode(tc):
    """CR hook (deck re-bakeoff): True when the opponent's board threat is ex/megaEx
    ATTACK damage -- exactly what Crustle's Mysterious Rock Inn blanks -- so our wall
    should hold the Active. Non-ex threats (Alakazam counter placement, crustle
    mirrors, Hariyama-class) leave it False. Cached per decision."""
    if not (DK and WALL_IDS):
        return False
    cached = getattr(tc, "_wallm", None)
    if cached is not None:
        return cached
    out = False
    try:
        for p in _poke_iter(tc.op):
            d = O.card_data(p.id)
            if d is None or not (getattr(d, "ex", False) or getattr(d, "megaEx", False)):
                continue
            for aid in (getattr(d, "attacks", None) or []):
                a = O.attack_data(aid)
                if a is not None and (a.damage or 0) > 0:
                    out = True
                    break
            if out:
                break
    except Exception:
        out = False
    try:
        tc._wallm = out
    except Exception:
        pass
    return out


# ============================ Lever 3: supply-rule instrumentation ====================
# Module-level diag counters (intel/supply_rule_2026-07-16.md pre-registration). Read via
# supply_diag_summary(); a per-game summary line is emitted to stderr when
# PTCG_SUPPLY_DEBUG=1 (called by pilot.py at episode end, best-effort / fail-open).
_SUPPLY_DIAG = {
    "fires": 0,                    # decisions where the supply rule was active (supply
                                    # <=2 AND wall_mode, tracker prize-exact)
    "dwebble_sacs_prevented": 0,   # promote/sac decisions where the old -20 Dwebble
                                    # penalty would have let Dwebble win the promote
                                    # comparison but the new hard demotion doesn't
    "race_checks": 0,              # _lock_clock evaluations under an active supply-<=2
                                    # state that additionally required the wider margin
    "grass_reserved": 0,           # Grow Grass attach decisions where the micro-rule
                                    # vetoed a non-wall (Kangaskhan) target
}
SUPPLY_DEBUG = _flag("PTCG_SUPPLY_DEBUG", "0")


def supply_diag_summary():
    """Returns a copy of the module-level supply-rule diag counters (for per-game/
    per-run stderr logging by pilot.py). Never raises."""
    try:
        return dict(_SUPPLY_DIAG)
    except Exception:
        return {}


def _crustle_accessible_supply(tc):
    """Lever 3 supply counter: 4 - discarded_crustle - prized_crustle. Matches the
    validated pre-check methodology (supply_state_precheck_2026-07-16.md sec.2's
    `stuck = disc_crustle + prize_crustle`), NOT the synthesis prose's
    '- in-play-committed' term -- a Crustle already on the field is still supply in the
    sense this rule cares about (how many more copies remain obtainable), and this keeps
    the live fire-rate measurement comparable to the pre-registered ~30% prediction.
    Fail-open: returns None (rule inert) when the tracker is off or prize identity
    hasn't converged yet."""
    try:
        t = _trk()
        if t is None:
            return None
        prized = t.our_prized(lambda cid: cid == CRUSTLE)
        if prized is None:
            return None
        disc = tc.discard_counts.get(CRUSTLE, 0)
        return 4 - disc - prized
    except Exception:
        return None


def _supply_rule_active(tc):
    """Lever 3 gate: accessible Crustle supply <=2 AND wall mode engaged. Fail-open to
    False (byte-identical old behavior) when SUPPLY_RULE is off, the deck isn't Crustle,
    or the supply counter is unknown. Cached per decision; increments the 'fires' diag
    counter once per decision the first time it's evaluated True."""
    if not (SUPPLY_RULE and DK and WALL_IDS and _cw()):
        return False
    cached = getattr(tc, "_supr", None)
    if cached is not None:
        return cached
    out = False
    try:
        supply = _crustle_accessible_supply(tc)
        out = (supply is not None and supply <= 2 and _wall_mode(tc))
    except Exception:
        out = False
    try:
        tc._supr = out
    except Exception:
        pass
    if out:
        try:
            _SUPPLY_DIAG["fires"] += 1
        except Exception:
            pass
    return out


def _grass_reserved(tc):
    """Lever 3 micro-rule gate: the single basic Grass (id 1) is prized or discarded
    while at least one Grow Grass copy remains accessible -> reserve Grow Grass
    exclusively for the wall (Crustle). Fail-open to False when prize identity unknown."""
    if not (SUPPLY_RULE and DK and WALL_IDS and _cw()):
        return False
    cached = getattr(tc, "_gres", None)
    if cached is not None:
        return cached
    out = False
    try:
        t = _trk()
        if t is not None:
            g_prized = t.our_prized(lambda cid: cid == BASIC_G)
            if g_prized is not None:
                disc_g = tc.discard_counts.get(BASIC_G, 0)
                stuck_g = g_prized + disc_g
                disc_grow = tc.discard_counts.get(GROW_GRASS, 0)
                grow_accessible = 4 - disc_grow  # (Grow Grass is not tracked for
                                                  # prizing here -- id 18 x4 in the
                                                  # decklist; discard is public/exact)
                out = (stuck_g >= 1 and grow_accessible > 0)
    except Exception:
        out = False
    try:
        tc._gres = out
    except Exception:
        pass
    return out


def _opp_wall_active(tc):
    """CR hook: THEIR active blanks our ex main attacker (Crustle-class 'prevent all
    damage ... by attacks from Pokemon ex' shield) -- our own non-ex Crustle (120,
    pierces effects) becomes the win condition (wall-breaker sequencing). Cached."""
    if not (DK and WALL_IDS):
        return False
    cached = getattr(tc, "_owall", None)
    if cached is not None:
        return cached
    out = False
    try:
        opa = tc.op.active[0] if (tc.op.active and tc.op.active[0] is not None) else None
        out = opa is not None and _attack_shielded(opa.id)
    except Exception:
        out = False
    try:
        tc._owall = out
    except Exception:
        pass
    return out


# ============================ Discipline rule instrumentation ====================
# Module-level diag counters (intel/discipline_rule_2026-07-16.md pre-registration). Read
# via discipline_diag_summary(); a per-game summary line is emitted to stderr when
# PTCG_DISCIPLINE_DEBUG=1 (called by pilot.py at episode end, best-effort / fail-open).
_DISCIPLINE_DIAG = {
    "fires": 0,                # decisions where the discipline gate was active: PLAY:
                                # Xerosic's Machinations legal, we are behind on prizes
                                # (len(me.prize) > len(op.prize)), AND an on-curve EVOLVE
                                # (Dwebble->Crustle) or an energy ATTACH toward the active
                                # attacker's cost (Mist/Spiky/Grow Grass -> active Mega
                                # Kangaskhan ex) is also legal this decision
    "evolves_promoted": 0,     # ALWAYS 0 by construction -- this rule demotes the
                                # competing PLAY option, it never boosts EVOLVE's own
                                # score. Kept for pre-registration-template symmetry;
                                # see plays_demoted for the counter that actually moves.
    "attaches_promoted": 0,    # ALWAYS 0 by construction, same reason as evolves_promoted
    "plays_demoted": 0,        # PLAY:Xerosic decisions where the demotion actually fired
                                # (i.e. the branch below returned the demoted score instead
                                # of its old value). Equals 'fires' exactly by construction
                                # here (the demotion is unconditional once the gate is
                                # True) -- tracked separately as a cross-check, same
                                # discipline as the supply-rule instrument.
}
DISCIPLINE_DEBUG = _flag("PTCG_DISCIPLINE_DEBUG", "0")
B_DISCIPLINE_DEMOTE = 700.0    # below every realized B_ATTACH_ENERGY (~7660-8420) and
                                # B_EVOLVE (~8750-9010) floor on this deck; above B_END(0)
                                # and VETO(-1) so Xerosic can still beat a genuinely empty
                                # turn, just never beat on-curve development while behind


def discipline_diag_summary():
    """Returns a copy of the module-level discipline-rule diag counters (for per-game/
    per-run stderr logging by pilot.py). Never raises."""
    try:
        return dict(_DISCIPLINE_DIAG)
    except Exception:
        return {}


def _discipline_behind(tc):
    """Behind on prizes: our own remaining-prize count exceeds the opponent's (we have
    converted fewer knockouts into prizes than they have). Matches the mined state
    condition (intel/discipline_rule_2026-07-16.md sec.3a, tuna_v11_decisions_ours.jsonl):
    the over-PLAY-instead-of-EVOLVE/ATTACH divergence fire-rate rose from 15.9% ahead to
    22.8% even to 26.7% behind, roughly monotonic across the fine prize-margin buckets."""
    try:
        return len(tc.me.prize) > len(tc.op.prize)
    except Exception:
        return False


def _discipline_curve_available(tc):
    """The two 'develop the board' actions the mined divergence pointed at: an on-curve
    EVOLVE (Dwebble already in play -> Crustle in hand, the wall line) or an energy ATTACH
    toward the active attacker's cost (Mist/Spiky/Grow Grass -> Mega Kangaskhan ex while it
    is our active and we have not yet attached energy this turn). This is a state-based
    legality PROXY (reads tc's counts/board directly, matching this file's existing style
    for _wall_mode/_supply_rule_active), not a raw legal-option-list read -- deliberately,
    per the L3 lesson (supply_rule_2026-07-16.md): the proxy's actual fire rate against the
    real option list is verified empirically by the smoke run before the CRN gate, not
    assumed correct from the state read alone."""
    try:
        evolve_ok = (tc.hand_counts.get(CRUSTLE, 0) > 0
                     and any(p is not None and p.id == DWEBBLE
                             for p in (tc.me.bench or [])))
        act = tc.active
        attach_ok = (act is not None and act.id == KANGASKHAN_M
                     and not getattr(tc.st, "energyAttached", False)
                     and any(tc.hand_counts.get(e, 0)
                             for e in (MIST_ENERGY, SPIKY_ENERGY, GROW_GRASS)))
        return bool(evolve_ok or attach_ok)
    except Exception:
        return False


def _discipline_rule_active(tc):
    """Gate: PLAY:Xerosic legal (implied -- only called from that branch) AND behind on
    prizes AND (on-curve EVOLVE or ATTACH-to-active-attacker legal). Fail-open to False
    (byte-identical old behavior) when DISCIPLINE_RULE is off, the deck isn't crustle_wall,
    or either state read raises. Cached per decision; increments 'fires' once per decision
    the first time it evaluates True."""
    if not (DISCIPLINE_RULE and DK and WALL_IDS and _cw()):
        return False
    cached = getattr(tc, "_discr", None)
    if cached is not None:
        return cached
    out = False
    try:
        out = _discipline_behind(tc) and _discipline_curve_available(tc)
    except Exception:
        out = False
    try:
        tc._discr = out
    except Exception:
        pass
    if out:
        try:
            _DISCIPLINE_DIAG["fires"] += 1
        except Exception:
            pass
    return out


def _dyn_dmg_estimate(cid, tc):
    """DK hook: static estimate for OUR pinned attacker's dynamic-damage attack (card-DB
    damage 0, which the static/race models otherwise read as 0). Alakazam Powerful Hand
    = 2 counters x our hand size; Spidops Rocket Rush = 30 x our Team Rocket's Pokemon.
    Used ONLY by the static-damage/race models; real attack selection still resolves
    through the exact oracle. Opponent-side forecasts keep the deliberate 0 bias."""
    try:
        if not DK:
            return 0
        if DECK_KIND == "alakazam" and cid == ALAKAZAM_ID:
            return 20 * max(0, tc.hand_size)
        if DECK_KIND == "rocket" and cid == SPIDOPS:
            n = 0
            for p in _poke_iter(tc.me):
                nm = getattr(O.card_data(p.id), "name", "") or ""
                if nm.startswith("Team Rocket"):
                    n += 1
            return 30 * n
    except Exception:
        pass
    return 0


def _static_best_attack(tc):
    """Max base damage our active could deal this turn (count-based affordability;
    +1 virtual energy while the manual attach is still available and we hold energy).
    Fallback where the exact oracle's resolution is unavailable."""
    a = tc.active
    if a is None:
        return 0
    d = O.card_data(a.id)
    if d is None or not getattr(d, "attacks", None):
        return 0
    have = _energy_count(a)
    try:
        if not getattr(tc.st, "energyAttached", True) and any(
                O.is_energy(c) for c in tc.hand_counts):
            have += 1
    except Exception:
        pass
    best = 0
    for aid in d.attacks:
        at = O.attack_data(aid)
        if at is not None and len(at.energies) <= have:
            best = max(best, (at.damage or 0) or _dyn_dmg_estimate(a.id, tc))
    return best


def _oracle_best_dmg(attack_eval):
    """Best exact-resolved defender damage among this MAIN's attack options."""
    best = 0
    for k, v in (attack_eval or {}).items():
        if isinstance(k, int) and isinstance(v, dict):
            best = max(best, v.get("def_dmg", 0) or 0)
    return best


def _chip_into_lethal(tc, dmg, atk_dmg):
    """Would a `dmg` chip bring a combo-worthy target into this-turn attack lethal?
    Active: chip + main attack. Bench: chip + Jetting Blow's 50 bench snipe."""
    if atk_dmg <= 0:
        return False
    opa = tc.op.active[0] if (tc.op.active and tc.op.active[0] is not None) else None
    if (opa is not None and opa.hp > dmg and (opa.hp - dmg) <= atk_dmg
            and _combo_target_ok(opa)):
        return True
    if atk_dmg >= 120:  # a Jetting-class turn: the 50 bench snipe can finish the chip
        for p in (tc.op.bench or []):
            if (p is not None and p.hp > dmg and (p.hp - dmg) <= 50
                    and _combo_target_ok(p)):
                return True
    return False


def _blast_target_worth(tc, dmg, strict=False):
    """Best-value opponent Pokemon a Cursed Blast KOs that is WORTH our 1-prize
    self-KO: engine targets, multi-prize targets, or anything in a Crustle-classified
    matchup (attrition race where our ex attack damage is shielded). strict (T5N):
    drop the crustle blanket -- only engine / multi-prize KOs count (used during a
    stall profile, where a junk 1-for-1 gift is exactly what loses the library-out)."""
    best = None
    crustle = (not strict) and _belief_is("crustle")
    for grp in ((tc.op.active or []), (tc.op.bench or [])):
        for p in grp:
            if p is None or p.hp > dmg:
                continue
            if _engine_target(p.id) or O.prize_count(p) >= 2 or crustle:
                v = pokemon_score(p)
                if best is None or v > best:
                    best = v
    return best


def damage_target_score(card, amount, combo_ok=False, atk_dmg=0, tc=None):
    """Shared opponent-Pokemon damage-target score (P2). Called by BOTH the live pick
    (_score_card_pick DAMAGE*) and the oracle's forced sub-selections
    (search._greedy_subchoice) so the simulated and executed Jetting Blow /
    Cursed Blast lines aim at the same target (design review sec.2).
    Tiers: exact KO (prize-value tie-break) > chip-into-this-turn-lethal >
    engine/evolving targets > distance-to-kill-penalized rest.
    R4 (v5): while the opponent has NOT yet landed an evolved attacker, add a denial
    bonus to basics whose line reaches their big attacker (mirror Staryu, Riolu, Abra,
    Dreepy, Dwebble) -- kill the attacker line BEFORE it comes online."""
    hp = getattr(card, "hp", 0)
    if hp <= amount:
        return 5000.0 + pokemon_score(card)
    s = 1000.0
    if combo_ok and atk_dmg > 0 and (hp - amount) <= atk_dmg and _combo_target_ok(card):
        s += 3200.0 + 0.5 * pokemon_score(card)
    if _engine_target(card.id):
        s += 800.0
    if (R4 and tc is not None and card.id in BIG_LINE_BASICS
            and not _opp_evolved_attacker(tc)):
        s += 260.0
    if 50 < hp <= 100:
        s += 90.0  # the next 50-chip finishes it
    try:
        s += 30.0 * min(len(card.energies), 4)
    except Exception:
        pass
    return s - 2.0 * max(0, hp - amount)


def _max_mega_damage(tc):
    """Largest damage (maxHp - hp) sitting on one of our Mega Evolution Pokemon."""
    worst = 0
    for p in _poke_iter(tc.me):
        d = O.card_data(p.id)
        if d is not None and getattr(d, "megaEx", False):
            worst = max(worst, getattr(p, "maxHp", p.hp) - p.hp)
    return worst


def _our_turn_no(tc):
    """Our per-player turn number (state.turn: 1 = starting player's first turn)."""
    t = getattr(tc.st, "turn", 0) or 0
    fp = getattr(tc.st, "firstPlayer", -1)
    if fp is None or fp < 0:
        return max(1, (t + 1) // 2)
    return (t + 1) // 2 if fp == tc.yi else t // 2


def _ready_mega_benched(tc):
    """A benched main attacker already has the energy for its cheapest attack."""
    for p in (tc.me.bench or []):
        if p is not None and p.id in MAIN_ATTACKERS and active_attack_ready(p):
            return True
    return False


def _benched_fueled_successor(tc):
    """A benched attacker/feeder carries at least one energy (a developing successor)."""
    for p in (tc.me.bench or []):
        if (p is not None and (p.id in MAIN_ATTACKERS or p.id in FEEDER_BASICS)
                and _energy_count(p) > 0):
            return True
    return False


def _nebula_turn(tc):
    """A Nebula-Beam turn is on: the opponent's active is attack-shielded (Crustle
    class -- Nebula's 'not affected by any effects on your opponent's Active Pokemon'
    pierces it), or sits in the (Jetting 120, Nebula 210] window, or Nebula is our
    only payable line (no W attached or in hand)."""
    opa = tc.op.active[0] if (tc.op.active and tc.op.active[0] is not None) else None
    if opa is None:
        return False
    if _attack_shielded(opa.id):
        return True
    if 120 < opa.hp <= 210:
        return True
    if R3 and _t2k(opa.hp, 210) < _t2k(opa.hp, 120):
        # tank-race window (R3): Nebula wins the KO math outright (Lucario 340 /
        # Archaludon ex 300 / mirror Mega 330: 2-shots vs Jetting's 3-shots)
        return True
    a = tc.active
    if (a is not None and a.id in MAIN_ATTACKERS and _energy_count(a) == 0
            and not any(tc.hand_counts.get(e, 0) for e in PRIMARY_ENERGIES)):
        return True
    return False


def _stall_profile(tc):
    """T5 (live autopsy 2026-07-11): stall/no-pressure read. True when our deck is the
    IMMINENT loss clock while we are strictly behind on prizes (library-out race the
    blast cannot win), or the opponent has applied ~zero pressure deep into the game
    (true wall) -- then a Cursed-Blast self-KO is a pure prize gift and big draws
    tick our own clock. First cut (deck<=8, prizes even) measured -7pp on ryota in
    the v4 ablation (long Alakazam races false-triggered) -> narrowed to this form."""
    try:
        if tc.me.deckCount <= 5 and len(tc.me.prize) > len(tc.op.prize):
            return True
        if _our_turn_no(tc) >= 6 and len(tc.op.prize) == 6:
            our_dmg = sum(getattr(p, "maxHp", p.hp) - p.hp for p in _poke_iter(tc.me))
            if our_dmg <= 20:
                return True
    except Exception:
        pass
    return False


# ================================ v7 Budew lock-and-clock (B1..B6) ====================
# Shared state functions for the deck-life-economy / gust-lock patches
# (intel/budew_behavior_diff.md). Everything here is read-only over the TurnCtx and
# exception-proof; every consumer is flag- and DECK_KIND-gated so B1..B6=0 (or any
# non-crustle deck) reproduces v6 byte-for-byte.


def _cw():
    """The crustle-wall deck profile is live (all B-hook consumers gate on this)."""
    return DK and DECK_KIND == "crustle_wall"


def _their_turn_no(tc):
    """Opponent's per-player turn number (total turns minus ours)."""
    t = getattr(tc.st, "turn", 0) or 0
    return max(0, t - _our_turn_no(tc))


def _deck_race(tc):
    """B1/B2 deck-out race read: (margin, our_ttl, their_ttl) in turns.
    our_ttl = turns until WE fail the mandatory draw if we go fully passive
    (deckCount: we control our optional draws, so the passive floor is 1 card/turn).
    their_ttl = their deckCount over their OBSERVED per-turn depletion rate -- every
    card that left their deck (draws, searches, Poffin, evolution digs) ticks their
    clock; both deck counts are exact (state + the v4 tracker's event-tracked
    state_deck_n cross-check). margin > 0: they deck out first even if we stall."""
    cached = getattr(tc, "_drace", None)
    if cached is not None:
        return cached
    out = (0.0, 99.0, 99.0)
    try:
        my_deck = tc.me.deckCount or 0
        op_deck = tc.op.deckCount or 0
        t = _trk()
        if t is not None:
            try:
                sd = t.state_deck_n
                my_deck, op_deck = sd[tc.yi], sd[1 - tc.yi]
            except Exception:
                pass
        tt = _their_turn_no(tc)
        drawn = max(0, 47 - op_deck)          # 60 - 7 opening hand - 6 prizes
        rate = (drawn / float(tt)) if tt >= 3 else 1.5
        if rate < 1.0:
            rate = 1.0                        # the mandatory draw is the floor
        our_ttl = float(my_deck)
        if MIR and _cw() and _mir_opp(tc)[1]:
            # P-MIR: an observed Great Tusk MILLS our library (Land Collapse: 1
            # top-card/turn, +3 with an Ancient supporter) -- the 1-card/turn
            # passive floor under-counts OUR clock by ~2x. Live: ep-85701444 we
            # read the race as comfortable while 45->0 in 31 turns, 3-0 up.
            our_ttl = my_deck / 2.0
        their_ttl = op_deck / rate
        out = (our_ttl - their_ttl, our_ttl, their_ttl)
    except Exception:
        pass
    try:
        tc._drace = out
    except Exception:
        pass
    return out


def _deck_race_won(tc):
    """We win the library race going passive, with margin. Conservative gates: at
    least 4 opponent turns observed (rate estimate is real), our own deck not yet
    desperate, a >=3-turn cushion, AND an absolute card lead -- the observed-rate
    model alone is a mirage vs decks that burn early then coast (bellibolt diag:
    3 OUR_DECKOUT losses at turn 32-45); if both sides go passive at 1/turn the
    absolute lead is what actually decides the race."""
    try:
        margin, _our_ttl, _their_ttl = _deck_race(tc)
        return (_their_turn_no(tc) >= 4 and (tc.me.deckCount or 0) >= 6
                and margin >= 3.0
                and (tc.op.deckCount or 0) < (tc.me.deckCount or 0))
    except Exception:
        return False


def _menaces_bench(a, tc=None):
    """Attack text reaches our BENCH (Shadow Bullet '30 damage to 1 of your
    opponent's Benched', Phantom Dive '6 damage counters on ... Benched'): these
    convert prizes THROUGH the Rock Inn shield (batch-1/2 diag: the grimm/dragapult
    lock bleeds were exactly this class).

    D1 refinements (census dragapult 44.0%): (1) only the OPPONENT's bench counts
    -- Aura Jab's 'Attach ... to your Benched Pokemon' (their own bench) false-
    positived the substring read; (2) counter-PLACEMENT bench reach (Phantom Dive
    'Put 6 damage counters on your opponent's Benched') is blanked while our
    Battle Cage stadium is up ('Prevent all damage counters from being placed on
    Benched Pokemon ... by effects of attacks and Abilities'); direct bench DAMAGE
    (Shadow Bullet / Jetting Blow 50) is still taken through the Cage."""
    try:
        txt = ((getattr(a, "text", None) or "").lower()).replace("’", "'")
        if not D1:
            return "bench" in txt
        if "opponent's bench" not in txt:
            return False
        if (tc is not None and "damage counter" in txt
                and _our_stadium_id(tc) == BATTLE_CAGE):
            return False                      # Cage blanks counter placement
        return True
    except Exception:
        return True


def _our_stadium_id(tc):
    """Card id of the stadium in play (-1 = none). Shared slot; our only stadium
    is Battle Cage, so a non-Cage id means THEIR stadium is up."""
    try:
        s = getattr(tc.st, "stadium", None)
        if s and s[0] is not None:
            return s[0].id
    except Exception:
        pass
    return -1


def _opp_counter_bench_threat(tc):
    """D1: opponent board holds a unit whose attack or ability PLACES/MOVES damage
    counters onto our side with bench reach (Phantom Dive, Munkidori Adrena-Brain
    class) -- the exact class Battle Cage blanks."""
    try:
        for p in _poke_iter(tc.op):
            d = O.card_data(p.id)
            if d is None:
                continue
            for aid in (getattr(d, "attacks", None) or []):
                a = O.attack_data(aid)
                txt = ((getattr(a, "text", None) or "").lower()).replace("’", "'")
                if "damage counter" in txt and "opponent's bench" in txt:
                    return True
            for sk in (getattr(d, "skills", None) or []):
                txt = ((getattr(sk, "text", None) or "").lower()).replace("’", "'")
                if "damage counter" in txt and ("move" in txt or "bench" in txt):
                    return True
    except Exception:
        pass
    return False


def _fighting_threat(tc):
    """L1: the opponent is a FIGHTING board (any in-play Pokemon of our tank's
    weakness type with a real attack, or a confident lucario belief). In these
    matchups our Mega Kangaskhan takes DOUBLE damage (Aura Jab 130 -> 260 two-shots
    it; a Premium-Power-Pro'd Wild Press 300 exact-KOs it) and every benched Kang
    is a 3-prize Boss / Heave-Ho Catcher target; the wall (which Mega Lucario /
    Garchomp ex cannot damage at all) is the tank of record."""
    cached = getattr(tc, "_fthreat", None)
    if cached is not None:
        return cached
    out = False
    try:
        if _belief_is("lucario"):
            out = True
        else:
            kd = O.card_data(KANGASKHAN_M)
            wk = getattr(kd, "weakness", None)
            if wk is not None:
                for p in _poke_iter(tc.op):
                    d = O.card_data(p.id)
                    if d is None or getattr(d, "energyType", None) is None:
                        continue
                    if int(d.energyType) != int(wk):
                        continue
                    for aid in (getattr(d, "attacks", None) or []):
                        a = O.attack_data(aid)
                        if a is not None and (a.damage or 0) > 0:
                            out = True
                            break
                    if out:
                        break
    except Exception:
        out = False
    try:
        tc._fthreat = out
    except Exception:
        pass
    return out


def _wall_g_count(pokemon):
    """G-providing energies attached (Grow Grass / the basic G): Superb Scissors'
    {G} cost payers. Mist/Spiky provide only {C}."""
    try:
        return sum(1 for e in (pokemon.energies or [])
                   if getattr(e, "id", None) in (GROW_GRASS, BASIC_G))
    except Exception:
        return 0


def _wall_payable_dmg(tc):
    """L1: TYPED payability of our active's attack (the count-only readiness model
    reads a Mist+Mist+Spiky Crustle as 'ready' while the engine never offers
    Superb Scissors -- {G}CC needs a G provider). Crustle: >=3 energies with >=1 G
    -> 120; Kang: >=3 any -> 200; else 0."""
    a = tc.active
    if a is None:
        return 0
    try:
        n = _energy_count(a)
        if a.id in WALL_IDS:
            return 120 if (n >= 3 and _wall_g_count(a) >= 1) else 0
        if a.id == KANGASKHAN_M:
            return 200 if n >= 3 else 0
    except Exception:
        pass
    return 0


def _opp_ko_pressure(tc):
    """BF: the opponent has SHOWN KO pressure this game -- they have taken at least
    one prize (a KO happened), or a gust card (Boss's Orders) sits in their discard
    (they drag-and-KO on sight; kojimar-class pilots)."""
    cached = getattr(tc, "_kopress", None)
    if cached is not None:
        return cached
    out = False
    try:
        if len(tc.op.prize) < 6:
            out = True
        else:
            for c in (tc.op.discard or []):
                if c is not None and getattr(c, "id", None) == BOSS_ORDERS:
                    out = True
                    break
    except Exception:
        out = False
    try:
        tc._kopress = out
    except Exception:
        pass
    return out


def _kang_gust_feed(tc):
    """BF: benching a fresh Mega Kangaskhan feeds an immediate 3-prize gust-KO --
    some opponent in-play Pokemon can pay (with at most one more attach) an attack
    whose weakness-doubled damage one-shots a fresh Kang's printed HP."""
    try:
        kd = O.card_data(KANGASKHAN_M)
        if kd is None:
            return False
        hp = getattr(kd, "hp", 0) or 0
        wk = getattr(kd, "weakness", None)
        if hp <= 0:
            return False
        for p in _poke_iter(tc.op):
            d = O.card_data(p.id)
            if d is None or not getattr(d, "attacks", None):
                continue
            have = _energy_count(p)
            for aid in d.attacks:
                a = O.attack_data(aid)
                if a is None:
                    continue
                if len(a.energies) > have + 1:      # +1: their next-turn attach
                    continue
                dmg = a.damage or 0
                try:
                    if (wk is not None and d.energyType is not None
                            and int(wk) == int(d.energyType)):
                        dmg *= 2
                except Exception:
                    pass
                if dmg >= hp:
                    return True
    except Exception:
        return False
    return False


def _bf_safe_stall(tc):
    """BF rev2: the board is a SAFE STALL -- our wall holds the Active and
    _opp_zero_threat says their board cannot convert at all (the kojimar won-lock).
    There a bare bench is NOT a wipe risk and a benched Kang is pure Boss bait.
    Cached per decision; only evaluated under the BF flag."""
    cached = getattr(tc, "_bfsafe", None)
    if cached is not None:
        return cached
    out = False
    try:
        out = (tc.active is not None and tc.active.id in WALL_IDS
               and _opp_zero_threat(tc))
    except Exception:
        out = False
    try:
        tc._bfsafe = out
    except Exception:
        pass
    return out


def _bench_floor(tc):
    """BF survival floor: bench <=1 while the opponent has shown KO pressure -- one
    gust/KO from a board wipe. Quarantines/holds yield: a body in hand is worth more
    on the bench than the 3-prize exposure it carries (v8 live: 5/9 lucario losses
    were OUR_NOBENCH at t2-t11 with only 1-5 opp prizes taken)."""
    if not (BF and _cw()):
        return False
    cached = getattr(tc, "_bfloor", None)
    if cached is not None:
        return cached
    out = False
    try:
        out = tc.bench_n <= 1 and _opp_ko_pressure(tc)
    except Exception:
        out = False
    try:
        tc._bfloor = out
    except Exception:
        pass
    return out


# ============================ v12 L2 lucario-matchup patches ==========================
# intel/lucario-root-cause-2026-07-14.md PATCH SPEC #1-#5. Every helper here is
# read-only over the TurnCtx and exception-proof (safe direction = assume risk / no
# opinion); every consumer is gated L2-and-subflag-and-_cw(), so PTCG_L2=0 (or all
# subflags 0) reproduces v11 exactly. Placed after the v7 B-hooks so KANGASKHAN_M,
# WALL_IDS, HEROS_CAPE, BOSS_ORDERS, _fighting_threat, _poke_iter, _energy_count,
# _deck_race_won, _wall_payable_dmg etc. are already in scope; forward references to
# _t2k / _deck_race / _opp_zero_threat (defined later in the module) are fine --
# Python resolves names inside a function body at call time, not definition time.

PREMIUM_POWER_PRO = 1141
MAKUHITA, HARIYAMA, LUNATONE, SOLROCK, RIOLU_LINE, MEGA_LUCARIO = 673, 674, 675, 676, 677, 678


def _l2_kang_lethal_risk(tc, kang):
    """#1: projected-lethal exposure for a Kangaskhan -- an actual in-play `kang`
    (its CURRENT hp, which already reflects Hero's Cape, is used) or None (a fresh
    bench add: printed HP, +100 only if Hero's Cape is plausibly available from
    hand). Any opponent attacker -- active OR Switch/Boss/Heave-Ho-reachable bench
    body -- with one more energy attachment, a plausible Premium Power Pro (+30
    before weakness; both strong lists run 4), and Fighting Weakness x2 applied,
    that reaches this HP counts as lethal."""
    try:
        kd = O.card_data(KANGASKHAN_M)
        printed_hp = getattr(kd, "hp", 0) or 0
        wk = getattr(kd, "weakness", None)
        if kang is not None:
            hp = getattr(kang, "hp", None) or printed_hp
        else:
            hp = printed_hp
            if tc.hand_counts.get(HEROS_CAPE, 0) > 0:
                hp += 100          # plausible: we could cape it before it's exposed
        if hp <= 0:
            return True
        for p in _poke_iter(tc.op):          # active + bench: Switch/Boss/Heave-Ho reach
            d = O.card_data(p.id)
            if d is None or not getattr(d, "attacks", None):
                continue
            have = _energy_count(p)
            for aid in d.attacks:
                a = O.attack_data(aid)
                if a is None:
                    continue
                if len(a.energies) > have + 1:      # +1: one more attach
                    continue
                dmg = a.damage or 0
                is_fighting = (wk is not None and getattr(d, "energyType", None) is not None
                               and int(wk) == int(d.energyType))
                if is_fighting and dmg > 0:
                    dmg += 30                        # plausible Premium Power Pro
                if is_fighting:
                    dmg *= 2                          # Fighting weakness x2
                if dmg >= hp:
                    return True
    except Exception:
        return True                                   # unknown -> assume lethal (safe)
    return False


def _l2_kang_emergency(tc):
    """#1: the ONLY exception to the hard veto -- we have no other body in play or
    on the bench (adding this Kang is the sole way to avoid an immediate empty-board
    loss this decision)."""
    try:
        return tc.bench_n == 0 and tc.active is None
    except Exception:
        return False


def _l2_kang_hard_veto(tc):
    """#1: hard one-Kang prize-exposure budget. Vetoes adding ANOTHER Kangaskhan to
    our board (bench or promote) once (a) a Kang is already in play, (b) the
    opponent is at <=3 remaining prizes (their exact winning Boss/Heave-Ho zone), or
    (c) a fresh Kang would already be projected-lethal on arrival. NEVER overridden
    by 'the first Kang is already damaged >=180' -- that permission is retired."""
    if not (L2 and L2_KANG and _cw() and _fighting_threat(tc)):
        return False
    try:
        if tc.field_counts.get(KANGASKHAN_M, 0) >= 1:
            return True
        if len(tc.op.prize) <= 3:
            return True
        if _l2_kang_lethal_risk(tc, None):
            return True
    except Exception:
        return True
    return False


def _l2_kang_veto_score(tc, cid, default):
    """Shared override for every Kang bench/promote scoring site: `default` passes
    through unchanged unless the hard veto applies and this isn't the sole board-out
    emergency, in which case a hard-quarantine score (below the existing L1a/B3
    quarantine bands) is forced."""
    if cid != KANGASKHAN_M:
        return default
    if _l2_kang_hard_veto(tc) and not _l2_kang_emergency(tc):
        return 8.0
    return default


def _l2_wall_active_is_ex(tc):
    """#2 opp_active_is_wallable_ex: TRUE only when the opponent's ACTIVE Pokemon is
    itself an ex/megaEx with a damaging attack -- the wall-promotion trigger should
    track the attacker actually threatening us, not any ex anywhere on their board
    (_wall_mode's board-wide read can promote Crustle into an ACTIVE non-ex
    wall-breaker while a bench Mega Lucario sits idle)."""
    try:
        opa = tc.op.active[0] if (tc.op.active and tc.op.active[0] is not None) else None
        if opa is None:
            return False
        d = O.card_data(opa.id)
        if d is None or not (getattr(d, "ex", False) or getattr(d, "megaEx", False)):
            return False
        for aid in (getattr(d, "attacks", None) or []):
            a = O.attack_data(aid)
            if a is not None and (a.damage or 0) > 0:
                return True
    except Exception:
        return True
    return False


def _l2_ready_nonex_wall_breaker(tc):
    """#2 ready_nonex_wall_breaker: the opponent's ACTIVE is a non-ex Pokemon with a
    real (>=60, or dynamic damage-counter), near-payable (<=1 attachment) attack --
    Hariyama/Solrock class -- that bypasses Crustle's shield on contact."""
    try:
        opa = tc.op.active[0] if (tc.op.active and tc.op.active[0] is not None) else None
        if opa is None:
            return False
        d = O.card_data(opa.id)
        if d is None or getattr(d, "ex", False) or getattr(d, "megaEx", False):
            return False
        have = _energy_count(opa)
        for aid in (getattr(d, "attacks", None) or []):
            a = O.attack_data(aid)
            if a is None or len(a.energies) - have > 1:
                continue
            dmg = a.damage or 0
            if dmg >= 60:
                return True
            if dmg == 0 and "damage counter" in ((getattr(a, "text", None) or "").lower()):
                return True
    except Exception:
        return True
    return False


def _l2_breaker_kills_wall(tc):
    """#2: the ready non-ex breaker on their ACTIVE would KO a fresh wall promoted
    into it (Hariyama's Wild Press 210 does; Solrock's Cosmic Beam 70 doesn't) --
    'prefer a spare one-prize Pokemon over feeding a pristine Crustle unless Crustle
    survives or KOs that attacker'."""
    try:
        opa = tc.op.active[0] if (tc.op.active and tc.op.active[0] is not None) else None
        if opa is None:
            return False
        d = O.card_data(opa.id)
        have = _energy_count(opa)
        wall_hp = 150
        for w in WALL_IDS:
            wd = O.card_data(w)
            if wd is not None:
                wall_hp = max(wall_hp, getattr(wd, "hp", 150) or 150)
        for aid in (getattr(d, "attacks", None) or []):
            a = O.attack_data(aid)
            if a is None or len(a.energies) - have > 1:
                continue
            if (a.damage or 0) >= wall_hp:
                return True
    except Exception:
        return False
    return False


def _l2_kang_evac_lethal(tc):
    """#2 urgent Kang evacuation: Kang is Active, a Benched wall body is available,
    and a current-or-one-Switch Fighting line projects lethal damage on it -- Switch
    outranks every non-winning attack this turn."""
    try:
        if tc.active is None or tc.active.id != KANGASKHAN_M:
            return False
        if not any(p is not None and p.id in WALL_IDS for p in (tc.me.bench or [])):
            return False
        return _l2_kang_lethal_risk(tc, tc.active)
    except Exception:
        return False


def _l2_predicted_pressure(tc):
    """#3: predict Lucario-family pressure from PUBLIC board setup, before any
    prize is lost or Boss is revealed -- Riolu, Makuhita, Hariyama, Lunatone,
    Solrock or Mega Lucario ex anywhere in their play area (an evolve / Lunar-Cycle
    / gust window is always imminent once the line is out)."""
    try:
        watch = (RIOLU_LINE, MAKUHITA, HARIYAMA, LUNATONE, SOLROCK, MEGA_LUCARIO)
        for p in _poke_iter(tc.op):
            if p is not None and p.id in watch:
                return True
    except Exception:
        return True
    return False


def _l2_floor_wanted(tc):
    """#3 predictive non-Kang board floor: only ONE friendly Pokemon is in play
    against Lucario belief/predicted pressure -- a non-Kang Basic (or Poffin to find
    one) should outrank optional Supporters, hand disruption, tools, and draw. If
    the only Basic available is Kang it is allowed once as emergency board-out
    prevention (the #1 hard-veto's own emergency exception already covers that
    case); otherwise Kang stays quarantined."""
    if not (L2 and L2_FLOOR and _cw()):
        return False
    try:
        board = (1 if tc.active is not None else 0) + tc.bench_n
        if board != 1:
            return False
        return _fighting_threat(tc) or _l2_predicted_pressure(tc)
    except Exception:
        return False


def _l2_only_ready(tc, cid):
    """#4: at most one copy of `cid` is anywhere on the opponent's board (removing
    it denies the ONLY Makuhita/Hariyama, not a redundant copy)."""
    try:
        n = sum(1 for p in _poke_iter(tc.op) if p is not None and p.id == cid)
        return n <= 1
    except Exception:
        return False


def _l2_boss_target_score(tc, card, atk):
    """#4 Lucario-specific Boss/target-KO ordering, evaluated only once Superb
    Scissors is payable (atk = its typed damage; callers gate atk>0 -- an
    unpayable/Ascension turn never reaches here). Order: wounded Hariyama<=120 >
    Makuhita > Riolu > Lunatone/Solrock, with a large bonus for removing the ONLY
    Makuhita (denies Heave-Ho Catcher's evolve trigger) or the only ready Hariyama.
    Returns None when this card isn't an exact-KO target under `atk` at all."""
    try:
        cid = card.id
        hp = getattr(card, "hp", 999) or 999
        if hp > atk:
            return None
        if cid == HARIYAMA and hp <= 120:
            bonus = 900.0
            if _l2_only_ready(tc, HARIYAMA):
                bonus += 400.0
            return bonus
        if cid == MAKUHITA:
            bonus = 700.0
            if _l2_only_ready(tc, MAKUHITA):
                bonus += 400.0            # deny the evolve into Heave-Ho Catcher
            return bonus
        if cid == RIOLU_LINE:
            return 500.0
        if cid in (LUNATONE, SOLROCK):
            # suppress the generic bonus when leaving it alive is the better
            # deckout clock (Lunar Cycle burns THEIR hand/deck, not just ours)
            return 150.0 if _deck_race_won(tc) else 350.0
    except Exception:
        return None
    return None


def _l2_wall_deck_clock(tc):
    """#5: replace the binary zero-threat read with an explicit clock comparison.
    Returns (wall_turns, prize_turns, their_deck_turns): wall_turns is turns for
    their live NON-EX board to break Crustle's shield (99 = the shield holds, no
    non-ex near-payable -- effectively infinite); prize_turns is a conservative
    estimate of how long they need at that rate to close the remaining prize gap
    (999 while the shield holds); their_deck_turns is _deck_race's their_ttl."""
    try:
        act = tc.active
        wall_up = act is not None and act.id in WALL_IDS
        if not wall_up:
            # BUG FIX (v12 CRN gate: base-vs-clock read -11.3pp kiyotah / -17.7pp
            # kojimar, p<0.001 both -- root cause): wall_turns defaulted to 99
            # ("shield holds") even when we AREN'T walling, so the clock veto fired
            # as if we were safely locked the entire game and froze our own draw/
            # attack development while actually undefended. prize_turns=0 here
            # forces _l2_clock_veto False whenever the wall isn't actually up.
            return (0, 0, _deck_race(tc)[2])
        wall_turns = 99
        if wall_up:
            best_dmg = 0
            for p in _poke_iter(tc.op):
                d = O.card_data(p.id)
                if d is None or getattr(d, "ex", False) or getattr(d, "megaEx", False):
                    continue                  # the shield blanks ex attacks entirely
                have = _energy_count(p)
                for aid in (getattr(d, "attacks", None) or []):
                    a = O.attack_data(aid)
                    if a is None or len(a.energies) - have > 2:
                        continue
                    dmg = a.damage or 0
                    if dmg > best_dmg:
                        best_dmg = dmg
            if best_dmg > 0:
                wall_hp = getattr(act, "hp", 150) or 150
                wall_turns = _t2k(wall_hp, best_dmg)
        p_op = len(tc.op.prize) if tc.op is not None else 0
        prize_turns = wall_turns * max(1, p_op) if wall_turns < 99 else 999
        _margin, _our_ttl, their_ttl = _deck_race(tc)
        return (wall_turns, prize_turns, their_ttl)
    except Exception:
        return (99, 999, 99.0)


def _l2_clock_veto(tc):
    """#5: TRUE when the opponent cannot finish the prize race before decking out,
    even counting their fastest live non-ex wall-breaker -- optional draw/search
    should be vetoed (it only speeds OUR clock, which isn't the bottleneck) and
    non-essential attacks held for the pass."""
    if not (L2 and L2_CLOCK and _cw()):
        return False
    try:
        _wall_turns, prize_turns, their_deck_turns = _l2_wall_deck_clock(tc)
        return their_deck_turns < prize_turns and their_deck_turns < 90.0
    except Exception:
        return False


ENHANCED_HAMMER, CRUSHING_HAMMER = 1081, 1120


def _denial_belief(tc):
    """ED: the opponent has SHOWN energy denial -- an Enhanced/Crushing Hammer in
    their discard (played) or anywhere in the tracker's seen pool (hand reveals).
    Deliberately NOT triggered by Xerosic's Machinations: its text is hand shred
    ("opponent discards ... until 3 in hand"), not energy removal, and half the band
    runs it (incl. lucario lists) -- triggering there would reshape rows P-ED never
    measured."""
    cached = getattr(tc, "_denial", None)
    if cached is not None:
        return cached
    out = False
    try:
        for c in (tc.op.discard or []):
            if (c is not None and getattr(c, "id", None)
                    in (ENHANCED_HAMMER, CRUSHING_HAMMER)):
                out = True
                break
        if not out:
            t = _trk()
            if t is not None:
                ms = t.opp_seen_ms()
                out = bool(ms.get(ENHANCED_HAMMER, 0) or ms.get(CRUSHING_HAMMER, 0))
    except Exception:
        out = False
    try:
        tc._denial = out
    except Exception:
        pass
    return out


def _standoff(tc):
    """O1 stall-tail read: their board cannot convert against us as things stand
    (zero-threat) BUT the passive deck race is not clearly won -- the only clock
    that can still kill us is our own library. Every optional draw/search ticks
    it. Distinct from _lock_clock (race WON -> B1 END band): this is the
    heal-wall / walrein / beartic standoff where v7 kept drawing into its own
    deck-out (census: grass heal-wall class, 8% WR, median loss at the local
    step cap)."""
    if not (O1 and _cw()):
        return False
    cached = getattr(tc, "_stoff", None)
    if cached is not None:
        return cached
    out = False
    try:
        out = ((not _lock_clock(tc)) and _opp_zero_threat(tc)
               and (tc.me.deckCount or 0) <= (tc.op.deckCount or 0) + 3)
    except Exception:
        out = False
    try:
        tc._stoff = out
    except Exception:
        pass
    return out


def _pierce_threat(tc):
    """ST1: opponent board holds a >=150-damage attack that 'isn't affected by any
    effects' on the defender (Nebula Beam 210) -- it kills the 150-HP Crustle
    THROUGH Mysterious Rock Inn, so the wall is a 1-prize gift, not a tank
    (starmie canned list; the crustle mirror's own 120 Superb Scissors stays under
    the threshold and keeps the normal wall plan)."""
    cached = getattr(tc, "_pierce", None)
    if cached is not None:
        return cached
    out = False
    try:
        for p in _poke_iter(tc.op):
            d = O.card_data(p.id)
            if d is None:
                continue
            for aid in (getattr(d, "attacks", None) or []):
                a = O.attack_data(aid)
                if a is None or (a.damage or 0) < 150:
                    continue
                txt = ((getattr(a, "text", None) or "").lower()).replace("’", "'")
                if "isn't affected by any effects" in txt:
                    out = True
                    break
            if out:
                break
    except Exception:
        out = False
    try:
        tc._pierce = out
    except Exception:
        pass
    return out


_SELF_DMG_RE = re.compile(r"does (\d+) damage to itself")


def _self_rider(a):
    """Self-damage rider printed on an attack ("This Pokemon (also) does N damage to
    itself" class, incl. the optional "You may ..." form -- the opponent picks it
    when the trade pays, safe direction). 0 = no rider. Dynamic riders ("for each
    damage counter") read their base N (under-read, still nonzero)."""
    try:
        m = _SELF_DMG_RE.search(getattr(a, "text", None) or "")
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


def _mutual_ko_threat(tc, opa, atks, have):
    """B2F guard 1 (live ep 85544056 T8/T10): the STRANDED read treats an
    energy-short opponent active as a blocked board, but a MUTUAL-KO attacker
    converts prizes THROUGH the lock: Hop's Snorlax at 1-2 energy short of Dynamic
    Press (140 + 80 self) passed the strand test, then pressed our Caped Kang twice
    into the Spiky counter -- 3 prizes to them for 1 to us, in a game whose mill
    race we had won. The self-KO rider means our counter damage never deters them.
    THREAT iff their active has a near-payable attack (<= 2 attachments away, the
    bench-pierce window) whose rider can consume its own attacker (<= 2 presses:
    2*rider >= its remaining hp) and whose damage can KO our active within the
    mill horizon (successive Hop's-box bodies keep pressing while we sit passive)."""
    act = tc.active
    if act is None:
        return False
    try:
        hp_me = getattr(act, "hp", 0) or 0
        if hp_me <= 0:
            return False
        hp_op = getattr(opa, "hp", 999) or 999
        _margin, _our_ttl, their_ttl = _deck_race(tc)
        horizon = max(2.0, min(their_ttl, 12.0))
        for a in atks:
            if len(a.energies) - have > 2:
                continue                      # not near-payable
            dmg = a.damage or 0
            rider = _self_rider(a)
            if (rider > 0 and 2 * rider >= hp_op and dmg > 0
                    and dmg * horizon >= hp_me):
                return True                   # they can and will trade: prizes flow
        return False
    except Exception:
        return True                           # unknown -> assume threat (safe)


def _live_nonex_board_attacker(tc):
    """A non-ex Pokemon anywhere on their board with a real attack (>=60, or a
    dynamic damage-counter attack) within 2 attachments of payable: it pierces the
    wall the moment it is promoted, so a shielded-active lock is leaky
    (lucario/Hariyama 210, grimm/Munkidori+Yveltal, souta/Great Tusk)."""
    try:
        for p in _poke_iter(tc.op):
            d = O.card_data(p.id)
            if d is None or getattr(d, "ex", False) or getattr(d, "megaEx", False):
                continue
            have = _energy_count(p)
            for aid in (getattr(d, "attacks", None) or []):
                a = O.attack_data(aid)
                if a is None or len(a.energies) - have > 2:
                    continue
                dmg = a.damage or 0
                if dmg >= 60:
                    return True
                if dmg == 0 and "damage counter" in (
                        (getattr(a, "text", None) or "").lower()):
                    return True               # Powerful-Hand-class dynamic counters
        return False
    except Exception:
        return True                           # unknown board -> assume threat


def _opp_zero_threat(tc):
    """Their board cannot convert against us as things stand. Two cases:
    STRANDED -- their active has no payable attack at all: the hostage blocks the
    whole board (the Budew gust-lock, ep 85224267). SHIELDED -- our Crustle wall
    blanks their ex active (Mysterious Rock Inn), AND its attacks don't reach our
    bench (Shadow Bullet / Phantom Dive pierce the shield that way), AND -- unless
    the active is also stranded -- their board holds no live non-ex attacker that
    would pierce the wall on promote. Dynamic damage-0 attacks that are payable
    count as threats (safe direction)."""
    opa = tc.op.active[0] if (tc.op.active and tc.op.active[0] is not None) else None
    act = tc.active
    if opa is None or act is None:
        return False
    if _l2_clock_veto(tc):
        # #5: the explicit wall/deck-clock read supersedes the binary STRANDED/
        # SHIELDED test -- if they cannot finish the prize race before decking out
        # even counting their fastest live non-ex wall-breaker, treat the board as
        # zero-threat regardless of which binary case applies.
        return True
    try:
        d = O.card_data(opa.id)
        if d is None:
            return False
        have = _energy_count(opa)
        atks = [O.attack_data(aid) for aid in (getattr(d, "attacks", None) or [])]
        atks = [a for a in atks if a is not None]
        stranded = all(len(a.energies) > have for a in atks) if atks else True
        shielded = (act.id in WALL_IDS
                    and (getattr(d, "ex", False) or getattr(d, "megaEx", False)))
        if not (shielded or stranded):
            return False
        if shielded:
            for a in atks:
                if len(a.energies) <= have + 2 and _menaces_bench(a, tc):
                    return False              # bench reach pierces the shield
            if not stranded and _live_nonex_board_attacker(tc):
                return False                  # a wall-piercer waits on their bench
        elif B2F and _mutual_ko_threat(tc, opa, atks, have):
            # B2F guard 1: pass came via STRANDED alone (no wall blanking this
            # attacker) and their active is a near-payable mutual-KO trader --
            # the lock is only safe if they truly cannot convert; a mutual KO
            # converts (ep 85544056). Shielded exes stay handled above: the wall
            # blanks their damage, rider or not.
            return False
        return True
    except Exception:
        return False


def _lock_clock(tc):
    """The Budew stall win-state shared by B1/B2: the opponent's active can't touch
    ours AND the passive mill race is won. While true, the plan is Budew's: END
    holding everything, never free the hostage (62% of their wins are deck-outs,
    median 20 turns with only 3 prizes taken). Cached per decision; no B-flag check
    here -- each consumer applies its own patch flag."""
    if not _cw():
        return False
    cached = getattr(tc, "_lockc", None)
    if cached is not None:
        return cached
    out = False
    try:
        # Prize-bleed guard (grimmsnarl diag, batch 1): the zero-threat read only
        # covers their ACTIVE vs our ACTIVE -- a gust+chip deck (Boss on our bench,
        # Munkidori counters) can keep converting prizes THROUGH the stall. If the
        # opponent is ahead on prizes and inside conversion range, the stall is
        # losing: drop it and fight (v6 behavior).
        bleeding = (len(tc.op.prize) <= 4 and len(tc.op.prize) < len(tc.me.prize))
        out = ((not bleeding) and _opp_zero_threat(tc) and _deck_race_won(tc))
        if out and MIR and _mir_opp(tc)[1]:
            # P-MIR: never call the passive race "won" vs an observed Great Tusk
            # miller -- Land Collapse breaks the 1-card/turn passive-floor
            # assumption the whole lock rests on (both while-AHEAD live deckouts
            # are this class).
            out = False
        if out and _supply_rule_active(tc):
            # Lever 3(c): supply-adjusted race check before committing to the
            # END-lock. Thin accessible Crustle supply means a lock that later
            # collapses (Dwebble/Crustle feedstock exhausted) can't be re-established
            # -- require a wider margin than the plain _deck_race_won gate (>=3.0)
            # before treating the passive race as won.
            try:
                _SUPPLY_DIAG["race_checks"] += 1
            except Exception:
                pass
            margin, _our_ttl, _their_ttl = _deck_race(tc)
            if margin < 6.0:
                out = False
    except Exception:
        out = False
    try:
        tc._lockc = out
    except Exception:
        pass
    return out


# ============================ v11 P-MIR / P-BLITZ helpers ============================
GREAT_TUSK = 58


def _mir_opp(tc):
    """P-MIR: (mirror, mill) -- the opponent has SHOWN the crustle family (Dwebble/
    Crustle on their board incl. preEvolutions, or in their public discard); mill =
    a Great Tusk seen the same way (Land Collapse discards OUR library 1-4/turn --
    the ee52c8d3 class behind both while-AHEAD-on-prizes live deckouts). Observation
    -only: no deck-list oracle, so it can't false-positive outside the family.
    Cached per decision."""
    cached = getattr(tc, "_mirop", None)
    if cached is not None:
        return cached
    mirror = mill = False
    try:
        seen = set()
        for p in _poke_iter(tc.op):
            seen.add(p.id)
            for pe in (getattr(p, "preEvolution", None) or []):
                pid = getattr(pe, "id", None)
                if pid is not None:
                    seen.add(pid)
        for c in (tc.op.discard or []):
            cid = getattr(c, "id", None)
            if cid is not None:
                seen.add(cid)
        mirror = (DWEBBLE in seen) or (CRUSTLE in seen)
        mill = GREAT_TUSK in seen
    except Exception:
        mirror = mill = False
    out = (mirror, mill)
    try:
        tc._mirop = out
    except Exception:
        pass
    return out


def _mir_closing(tc):
    """P-MIR(b) closure state: mirror/mill observed AND the passive deck race is
    NOT clearly won (margin < 6 turns; any observed miller = always closing) --
    prizes are the only clock we can still win, so convert them before the
    library runs out (live: 3-0 and 1-0 up, decked out t29-31)."""
    if not (MIR and _cw()):
        return False
    mirror, mill = _mir_opp(tc)
    if not (mirror or mill):
        return False
    if mill:
        return True
    try:
        # margin < 3: genuinely losing/knife-edge only -- the first cut (< 6)
        # kept closure on nearly always in the symmetric true mirror and traded
        # the stall equity away (self_mirror probe b=8/c=1)
        return _deck_race(tc)[0] < 3.0
    except Exception:
        return False


def _blitz_opp(tc):
    """P-BLITZ: the opponent has shown the Staryu/Mega Starmie line (board incl.
    preEvolutions or public discard), or the archetype belief says starmie."""
    cached = getattr(tc, "_blzop", None)
    if cached is not None:
        return cached
    out = False
    try:
        seen = set()
        for p in _poke_iter(tc.op):
            seen.add(p.id)
            for pe in (getattr(p, "preEvolution", None) or []):
                pid = getattr(pe, "id", None)
                if pid is not None:
                    seen.add(pid)
        for c in (tc.op.discard or []):
            cid = getattr(c, "id", None)
            if cid is not None:
                seen.add(cid)
        out = (STARYU in seen) or (MEGA_STARMIE in seen) or _belief_is("starmie", 0.5)
    except Exception:
        out = False
    try:
        tc._blzop = out
    except Exception:
        pass
    return out


def _run_errand_score(tc):
    """B1a: library = HP. Budew uses Run Errand at median own-deck 33 and SKIPS it
    1,466x at median deck 16 (1,067 skips at deck > 10); our old hook vetoed only at
    deck <= 6 -- wrong by ~10 cards (we counterfactually drew 5,605x where they
    decline). Clock-aware replacement: draw while the library is deep or the hand is
    actually thin; never once the passive mill race is won."""
    deck = tc.me.deckCount or 0
    if deck <= 6:
        return VETO                           # v6 hard floor retained
    if MIR and _cw():
        mirror, mill = _mir_opp(tc)
        if mirror or mill:
            # P-MIR(a): in the mirror/mill the library is the loss clock from
            # turn 1 -- the six live OUR_DECKOUT losses drew 50-73 cards vs the
            # tuned bots' 21-44 (Run Errand ~1/turn was the biggest burner); the
            # one Tusk-mill WIN drew 36 in 42 turns. Draw only while genuinely
            # deep (Budew's own median use is at deck 33) or on a dead hand.
            if mill and tc.hand_size >= 2:
                return VETO
            if deck <= 20 and tc.hand_size >= 3:
                return VETO
            if deck <= 12 and tc.hand_size >= 2:
                return VETO
            # (first cut used deck<=30/hand>=3: the blanket hold starved the
            # true mirror's fuel digging and lost the prize race -- self_mirror
            # paired probe b=8/c=1. The 20/12 gates keep the Budew-median-16
            # skip window without freezing development at full deck.)
    if _lock_clock(tc) and tc.hand_size >= 2:
        return VETO                           # race won going passive: stop drawing
    if L2 and L2_CLOCK and _cw() and _l2_clock_veto(tc) and tc.hand_size >= 2:
        return VETO                           # #5: their deck clock already loses --
                                              # every optional draw only speeds ours
    if _standoff(tc) and tc.hand_size >= 2:
        return VETO                           # O1: standoff, race NOT won -- the
                                              # library is the only live loss clock
    if deck <= 18 and tc.hand_size >= 4 and _opp_zero_threat(tc):
        # mid-clock, safely behind the wall (their active can't touch ours): the
        # game is long, the library is HP -- only dig on a thin hand. In racing
        # states (their active hits us) drawing is development, not waste: keep v6
        # behavior (bellibolt diag: the unconditional deck<=18 throttle starved
        # racing matchups, prize losses with lockN=0).
        return VETO
    return B_ABILITY


def _gust_deficit(card):
    """Energy this opponent Pokemon still needs for its CHEAPEST attack (99 = it has
    no attacks at all). Deficit >= 2 = a stranded body: the gust-lock hostage class."""
    try:
        d = O.card_data(card.id)
        if d is None or not getattr(d, "attacks", None):
            return 99
        have = _energy_count(card)
        best = 99
        for aid in d.attacks:
            a = O.attack_data(aid)
            if a is not None:
                best = min(best, max(0, len(a.energies) - have))
        return best
    except Exception:
        return 0


def _gust_stall_wanted(tc):
    """B2 lock-creation window: our wall is standing, the mill clock actually favors
    us, and we are not bleeding prizes. First cut (any op_deck < my_deck+4) fired in
    racing matchups where the lock can't finish (bellibolt diag: hostage-gusts with
    lockN=0 while they converted 6 prizes) -- vs a racing board the Boss stays on
    threat-drag duty (v6 behavior)."""
    try:
        wall_up = any(tc.field_counts.get(w, 0) for w in WALL_IDS)
        if not wall_up:
            return False
        if (len(tc.op.prize) <= 4 and len(tc.op.prize) < len(tc.me.prize)):
            return False                      # they are converting: fight, don't stall
        margin, _our_ttl, _their_ttl = _deck_race(tc)
        return _their_turn_no(tc) >= 3 and margin >= 1.0
    except Exception:
        return False


def _gust_pick_score(tc, card):
    """B2 Boss's Orders target: argmin(attack capability), not argmax(threat).
    Budew's gusts: Fezandipiti ex x87 (energyless 2-prize support = the perfect
    hostage), Abra x69 / Kadabra x38 (engine bodies), opp Dwebble x26 -- while our
    v6 dragged the biggest threat (Kadabra->Alakazam x19+13). Engine basics score
    via the exact-KO branch only when our current attack kills them next turn."""
    try:
        deficit = _gust_deficit(card)
        d = O.card_data(card.id)
        if deficit >= 2:
            s = 3000.0 + 250.0 * min(deficit, 4)
            if d is not None and (getattr(d, "ex", False)
                                  or getattr(d, "megaEx", False)):
                s += 700.0                    # stranded ex support: Fez-class hostage
            s += 60.0 * (getattr(d, "retreatCost", 0) or 0)
            s -= 120.0 * _energy_count(card)
            return s
        atk = _static_best_attack(tc)
        if (getattr(card, "hp", 999) <= atk and _engine_target(card.id)):
            return 2200.0 + pokemon_score(card)   # exact-KO the engine basic
        return 0.5 * pokemon_score(card)      # capable attacker: dragging it feeds it
    except Exception:
        return pokemon_score(card)


def _hostage_candidate(tc):
    """Best gust-lock hostage on their bench (>=2 energy away from any attack), or
    None. Used to decide whether playing Boss's Orders creates a lock at all."""
    try:
        best = None
        for p in (tc.op.bench or []):
            if p is None or _gust_deficit(p) < 2:
                continue
            s = _gust_pick_score(tc, p)
            if best is None or s > best[0]:
                best = (s, p)
        return best
    except Exception:
        return None


def _cw_play_pokemon_hold(tc, cid):
    """B3: spare Mega Kangaskhans stay IN HAND -- fewer 3-prize Boss/bench-out
    targets, mill-safe (the single biggest PLAY flip: we bench a 2nd/3rd Kang
    1,723x at their ENDs). A 2nd Kang benches only as the replacement tank once the
    first is >=180 damaged; never a 3rd. Shaymin benches only onto a bare board
    (it is the planned sacrifice, not development). None = default scoring."""
    if cid == KANGASKHAN_M:
        if L2 and L2_KANG:
            v = _l2_kang_veto_score(tc, cid, None)
            if v is not None:
                return v
        n = tc.field_counts.get(KANGASKHAN_M, 0)
        if n >= 2:
            return 260.0
        if n == 1:
            for p in _poke_iter(tc.me):
                if (p is not None and p.id == KANGASKHAN_M
                        and (getattr(p, "maxHp", p.hp) - p.hp) >= 180):
                    return B_PLAY_POKEMON - 60.0   # replacement for a dying tank
            return 420.0
        return None
    if cid == SHAYMIN_CR:
        if ((1 if tc.active is not None else 0) + tc.bench_n) >= 2:
            return 380.0
        return None
    return None


def _cw_attach_energy_score(tc, cid, tid, target, o):
    """B5 energy role-map (Budew's attach tables: Mist->tank@ACT 1,658 / Spiky->Kang
    920 ACT + 447 BEN / Grow Grass->Crustle 627 -- the only G that pays Superb
    Scissors, +20 HP; Grow->Kang 667 as filler {C}). Load the ACTIVE to 3 energy
    FIRST (Jumbo Ice Cream eligibility + attack readiness) -- our v6 banked onto
    benched Dwebble/successors and starved the correctly-shaped Jumbo gate (their
    1,337 uses vs our 548). The single basic {G} never banks on a bench body."""
    s = B_ATTACH_ENERGY
    is_active = (o.inPlayArea == AreaType.ACTIVE)
    e_have = _energy_count(target) if target is not None else 0
    tank = (tid == KANGASKHAN_M) or (tid in WALL_IDS)
    denial = ED and _denial_belief(tc)
    if is_active and tank and e_have < 3:
        s += 420                              # active tank to 3E first
    elif is_active:
        s += 60
    if e_have >= 3:
        if (denial and is_active and tid in WALL_IDS
                and cid in (GROW_GRASS, BASIC_G)
                and target is not None and _wall_g_count(target) == 1):
            # ED(c): under an observed hammer a SECOND G source on the attack-ready
            # active wall is a buffer, not over-attachment -- one Enhanced Hammer
            # stripping the lone Grow Grass turns Superb Scissors off ({G}CC).
            # Attached the turn it's in use (the wall attacks at 3E+), so it never
            # sits idle for the hammer to flip tempo.
            s -= 40
        elif denial and is_active and tid == KANGASKHAN_M and e_have == 3:
            # ED(b): one buffer energy on the active tank -- a Crushing heads at
            # exactly 3E flips Kang below Jumbo/attack readiness; the 4th is
            # attached the turn it's in use. (A 5th+ is still over-attachment.)
            s -= 40
        else:
            s -= 250                          # 3E is the plan; 4th+ = Hammer exposure
    if denial:
        if cid == BASIC_G and is_active and tid in WALL_IDS:
            s += 260                          # ED(a): the basic {G} is Enhanced-
                                              # immune -- it outranks Grow/Mist here
        if (not is_active) and cid in (MIST_ENERGY, SPIKY_ENERGY, GROW_GRASS):
            # ED(b): specials go where they are used -- a benched bank is hammer
            # food (Enhanced: "Discard a Special Energy from 1 of your opponent's
            # Pokemon" -- any of ours). Strong nudge toward the active, NOT a hard
            # hold: the first cut (s = B_END - 5, never bank under denial) bled
            # its own target rows (majkel 94.3->90.3, comfey 83.3->78.3, 3/3
            # seeds) -- freezing the successor's fuel cost more tempo than the
            # hammers it dodged. Same lesson as O1/S1: hard freezes lose to the
            # tuned default.
            s -= 280
    if (L1 and tid in WALL_IDS and is_active
            and cid in (GROW_GRASS, BASIC_G)
            and target is not None and _wall_g_count(target) == 0):
        # L1c wall payability first: without a G provider the engine never offers
        # Superb Scissors -- a Mist+Mist+Spiky Crustle sat 'ready' for whole games
        # (kiyotah trace: active Crustle e3-e5, zero attacks all game). The first
        # G on the active wall outranks the Mist shield.
        s += 420
    if cid == MIST_ENERGY:
        s += 180 if is_active else -40        # effect shield on the unit being HIT
    elif cid == SPIKY_ENERGY:
        if tid == KANGASKHAN_M:
            s += 120 if is_active else 40     # 2-counter punishment on the tank
    elif cid == GROW_GRASS:
        if tid in WALL_IDS:
            s += 160                          # reserved: Crustle's {G} cost + 20 HP
        elif tid == KANGASKHAN_M:
            if _grass_reserved(tc):
                # Lever 3 micro-rule: the single basic G is prized/discarded --
                # reserve Grow Grass exclusively for Crustle's Superb Scissors cost,
                # never bank it as filler {C} on the Kang tank.
                try:
                    _SUPPLY_DIAG["grass_reserved"] += 1
                except Exception:
                    pass
                return VETO
            s += 20                           # filler {C} on the tank (their 667)
    elif cid == BASIC_G:
        if tid in WALL_IDS:
            s += 140                          # emergency Superb Scissors fuel
        elif not is_active:
            return VETO                       # the one basic G never banks on bench
        else:
            s -= 300
    if (not is_active) and tid == DWEBBLE:
        s -= 80                               # Dwebble is feedstock, not a bank
    return s


def _cw_switch_score(tc):
    """B4: Switch is HELD by default (Budew's #1 END-held card, 2,437x; our v6
    played it proactively, 618 flips). Spend it only when the swap changes
    this-turn damage: wall-in under a LIVE ex attack threat, breaker-in when their
    shield blanks our ex Kangaskhan, or ready-Kang-in when the wall is pointless.
    ST1: vs an effects-piercing 150+ attacker (Nebula Beam 210 kills the wall
    through Rock Inn) the wall-in swap is a free Crustle gift -- skip it, and the
    Caped Kang tank comes back in."""
    a = tc.active
    if a is None:
        return 150.0
    if L2 and L2_WALL and _l2_kang_evac_lethal(tc):
        return 9000.0   # #2 urgent Kang evacuation: outranks every non-winning attack
    wall_benched = any(p is not None and p.id in WALL_IDS
                       for p in (tc.me.bench or []))
    opa = tc.op.active[0] if (tc.op.active and tc.op.active[0] is not None) else None
    pierce = ST1 and _pierce_threat(tc)
    l2w = L2 and L2_WALL
    wall_trigger = _l2_wall_active_is_ex(tc) if l2w else _wall_mode(tc)
    if a.id not in WALL_IDS and wall_benched and not pierce:
        if _opp_wall_active(tc):
            return B_PLAY_ITEM + 250.0        # breaker-in: our non-ex Crustle swings
        if (wall_trigger and opa is not None
                and opp_best_attack_damage(opa, a) > 0
                and not (l2w and _l2_ready_nonex_wall_breaker(tc)
                         and not _l2_breaker_kills_wall(tc))):
            # #2: don't feed a pristine wall into an ACTIVE non-ex breaker unless it
            # would KO that attacker or (checked here) at least survive contact
            return B_PLAY_ITEM + 250.0        # wall-in: live ex damage on our active
    if (a.id in WALL_IDS and _ready_mega_benched(tc)
            and (pierce or not (wall_trigger or _opp_wall_active(tc)))):
        return B_PLAY_ITEM + 200.0            # wall pointless/pierced: tank back in
    return 150.0


# ================================ v5 race-state evaluator (R1) =======================
# The core per-decision computation of the effective prize race: prizes-to-win each side
# divided by realistic KOs-per-turn each side. OUR damage rate comes from the exact
# oracle when available (score_main passes it), else the static affordability model;
# the OPPONENT's from their active's energy + known attacks (card DB, weakness applied).
# Deliberate safe bias: dynamic-damage attacks (DB damage=0, e.g. Alakazam's Powerful
# Hand) count as 0 -> vs Alakazam the race reads AHEAD/EVEN and behavior stays v3/v4b
# (the 70.8%-live pillar is untouched); the levers activate on the measured bleeders
# (Lucario / Archaludon / mirror) where the threat is plain attack damage.

RACE_AHEAD, RACE_EVEN, RACE_BEHIND = 1, 0, -1


def _t2k(hp, dmg):
    """Turns to KO hp at dmg per turn (ceil); 99 = never."""
    if dmg is None or dmg <= 0 or hp is None:
        return 99
    return max(1, int(-(-hp // dmg)))


def _cheapest_attack_dmg(cid):
    """Damage of the cheapest attack of card cid (the sustainable per-turn swing)."""
    d = O.card_data(cid)
    if d is None or not getattr(d, "attacks", None):
        return 0
    best_need, best_dmg = None, 0
    for aid in d.attacks:
        a = O.attack_data(aid)
        if a is None:
            continue
        need = len(a.energies)
        if best_need is None or need < best_need or (need == best_need
                                                     and (a.damage or 0) > best_dmg):
            best_need, best_dmg = need, (a.damage or 0)
    return best_dmg


def _opp_threat_forecast(tc):
    """(damage, lag): the opponent's realistic per-turn damage vs our active from their
    ACTIVE's known attacks, assuming they attach ~1 energy/turn. lag = extra turns until
    the chosen attack is payable. Weakness applied vs our active. Static, DB-only."""
    opa = tc.op.active[0] if (tc.op.active and tc.op.active[0] is not None) else None
    if opa is None:
        return 0, 0
    d = O.card_data(opa.id)
    if d is None or not getattr(d, "attacks", None):
        return 0, 0
    have = _energy_count(opa)
    my_data = O.card_data(tc.active.id) if tc.active is not None else None
    best = None                       # (lag, -dmg): soonest first, then biggest
    for aid in d.attacks:
        a = O.attack_data(aid)
        if a is None:
            continue
        dmg = a.damage or 0
        if dmg <= 0:
            continue                  # dynamic/status attacks: deliberate 0 (see above)
        lag = max(0, len(a.energies) - have - 1)
        if lag > 2:
            continue
        try:
            if (my_data is not None and my_data.weakness is not None
                    and d.energyType is not None
                    and int(my_data.weakness) == int(d.energyType)):
                dmg *= 2
        except Exception:
            pass
        cand = (lag, -dmg)
        if best is None or cand < best:
            best = cand
    if best is None:
        return 0, 0
    return -best[1], best[0]


def _our_dpt_prospect(tc):
    """(damage, lag) when we cannot attack right now: the main attacker's sustainable
    swing and a coarse count of turns until it lands (fuel / evolve / find lag)."""
    base = 0
    for a in MAIN_ATTACKERS:
        base = max(base, _cheapest_attack_dmg(a))
    if base <= 0:
        for a in MAIN_ATTACKERS:
            base = max(base, _dyn_dmg_estimate(a, tc))  # DK: dynamic-damage attacker
    if base <= 0:
        return 0, 0
    in_play = [p for p in _poke_iter(tc.me) if p is not None]
    mega_in_play = any(p.id in MAIN_ATTACKERS for p in in_play)
    have_e = (any(tc.hand_counts.get(e, 0) for e in PRIMARY_ENERGIES)
              or tc.hand_counts.get(IGNITION_ENERGY, 0) > 0)
    if mega_in_play:
        fueled = any(p.id in MAIN_ATTACKERS and _energy_count(p) > 0 for p in in_play)
        return base, (1 if (fueled or have_e) else 2)
    feeder_in_play = any(p.id in FEEDER_BASICS for p in in_play)
    mega_in_hand = any(tc.hand_counts.get(a, 0) for a in MAIN_ATTACKERS)
    if feeder_in_play and mega_in_hand:
        return base, 2
    if feeder_in_play:
        return base, 3
    return base, 4


def _race_compute(tc, our_dpt):
    p_us, p_op = len(tc.me.prize), len(tc.op.prize)
    if p_us <= 0 or p_op <= 0:
        return (RACE_EVEN, 0.0)
    opa = tc.op.active[0] if (tc.op.active and tc.op.active[0] is not None) else None

    # --- our clock: lag + turns for the first KO + full-HP cycles for the rest
    dpt = our_dpt if (our_dpt is not None and our_dpt > 0) else _static_best_attack(tc)
    lag_us = 0
    if dpt <= 0:
        dpt, lag_us = _our_dpt_prospect(tc)
    if opa is None or dpt <= 0:
        return (RACE_EVEN, 0.0)      # no read -> no policy change
    pv_o = max(1, O.prize_count(opa))
    hp_o = getattr(opa, "hp", 0) or 0
    mhp_o = getattr(opa, "maxHp", hp_o) or hp_o
    kos_us = -(-p_us // pv_o)
    turns_us = lag_us + _t2k(hp_o, dpt) + (kos_us - 1) * _t2k(mhp_o, dpt)

    # --- their clock (symmetric, static forecast)
    odmg, olag = _opp_threat_forecast(tc)
    if odmg <= 0:
        return (RACE_AHEAD, 3.0)     # no visible threat rate -> keep current behavior
    act = tc.active
    if act is not None:
        hp_m = getattr(act, "hp", 0) or 0
        pv_m = max(1, O.prize_count(act))
    else:
        hp_m, pv_m = 60, 1           # promotion due: assume a cheap body goes up first
    cyc_hp, cyc_pv = (hp_m or 70), pv_m
    for p in _poke_iter(tc.me):
        if p is not None and p.id in MAIN_ATTACKERS:
            cyc_hp = getattr(p, "maxHp", p.hp) or p.hp
            cyc_pv = max(1, O.prize_count(p))
            break
    rem = p_op - pv_m
    n_cyc = 0 if rem <= 0 else -(-rem // cyc_pv)
    turns_op = olag + _t2k(hp_m, odmg) + n_cyc * _t2k(cyc_hp, odmg)

    margin = float(turns_op - turns_us)   # positive: we finish first (we move first)
    if margin >= 1.0:
        return (RACE_AHEAD, margin)
    if margin <= -1.0:
        return (RACE_BEHIND, margin)
    return (RACE_EVEN, margin)


def race_state(tc, our_dpt=None):
    """R1: (label, margin) of the effective prize race, cached per decision.
    label RACE_AHEAD/EVEN/BEHIND; margin = their turns-to-win minus ours."""
    cached = getattr(tc, "_race", None)
    if cached is not None:
        return cached
    if not R1:
        out = (RACE_EVEN, 0.0)
    else:
        try:
            out = _race_compute(tc, our_dpt)
        except Exception:
            out = (RACE_EVEN, 0.0)
    try:
        tc._race = out
    except Exception:
        pass
    return out


def _race_lbl(tc):
    return race_state(tc)[0]


def _behind(tc):
    return R1 and R2 and _race_lbl(tc) == RACE_BEHIND


def _tank_race_on(tc):
    """R3: the opponent's active is a tank whose KO math favors Nebula Beam over
    Jetting Blow (fewer turns-to-KO at 210 than at 120)."""
    opa = tc.op.active[0] if (tc.op.active and tc.op.active[0] is not None) else None
    if opa is None:
        return False
    hp = getattr(opa, "hp", 0) or 0
    return _t2k(hp, 210) < _t2k(hp, 120)


def _opp_evolved_attacker(tc):
    """Opponent already has an evolved / rule-box attacker in play (denial window over)."""
    for p in _poke_iter(tc.op):
        d = O.card_data(p.id)
        if d is None:
            continue
        if getattr(d, "megaEx", False) or getattr(d, "ex", False):
            return True
        if not getattr(d, "basic", False):
            for aid in (getattr(d, "attacks", None) or []):
                a = O.attack_data(aid)
                if a is not None and (a.damage or 0) >= 100:
                    return True
    return False


def _build_big_line_basics():
    """Basic Pokemon whose evolution line reaches a big attacker (ex/Mega or a >=100
    damage attack): the snipe-denial targets (R4) -- their FUTURE main attacker.
    Generic evolvesFrom-graph walk over the card DB (mirror: Staryu; lucario: Riolu;
    alakazam: Abra; dragapult: Dreepy; crustle: Dwebble)."""
    out = set()
    try:
        by_from = {}
        for cid, c in O.CARD_TABLE.items():
            ef = getattr(c, "evolvesFrom", None)
            if ef:
                by_from.setdefault(ef, []).append(cid)

        def big(cid):
            d = O.card_data(cid)
            if d is None:
                return False
            if getattr(d, "megaEx", False) or getattr(d, "ex", False):
                return True
            for aid in (getattr(d, "attacks", None) or []):
                a = O.attack_data(aid)
                if a is not None and (a.damage or 0) >= 100:
                    return True
            return False

        for cid, c in O.CARD_TABLE.items():
            if not getattr(c, "basic", False):
                continue
            frontier = {getattr(c, "name", "") or ""}
            reach = False
            for _ in range(3):
                nxt = set()
                for nm in frontier:
                    for e in by_from.get(nm, []):
                        if big(e):
                            reach = True
                        nm2 = getattr(O.card_data(e), "name", "") or ""
                        if nm2:
                            nxt.add(nm2)
                if reach or not nxt:
                    break
                frontier = nxt
            if reach:
                out.add(cid)
    except Exception:
        pass
    return out


BIG_LINE_BASICS = _build_big_line_basics()


def _pivot_retreat_ok(tc):
    """P7: active is a cheap (<=1 retreat) non-attacker and a ready Mega waits on the
    bench -- 54/56 of WinDecks' retreats are exactly this pivot."""
    a = tc.active
    if a is None or a.id in MAIN_ATTACKERS:
        return False
    d = O.card_data(a.id)
    if d is None or (getattr(d, "retreatCost", 0) or 0) > 1:
        return False
    return _ready_mega_benched(tc)


def _useless_opp_stadium_ability(o, cid):
    """P0: a stadium ability that can only fetch owner-tagged Pokemon we do not run
    (Spikemuth Gym searches Marnie's Pokemon; for us a pure no-op action)."""
    try:
        if int(o.area) != int(AreaType.STADIUM):
            return False
    except Exception:
        return False
    d = O.card_data(cid)
    if d is None:
        return False
    for sk in (getattr(d, "skills", None) or []):
        txt = getattr(sk, "text", None) or ""
        for owner in re.findall(r"([A-Za-z]+)['’]s Pok", txt):
            if owner.lower() not in DECK_OWNER_PREFIXES:
                return True
    return False


def _dus_evolve_score(tc, attack_eval, poke, evo_id):
    """P5: allow the Duskull-line evolve only when the Cursed Blast payoff is live
    (Crustle-classified matchup / worth-it KO on board / combo chip / selling a
    damaged body). Never when the opponent is on their last prize -- the eventual
    self-KO would hand over the game."""
    if len(tc.op.prize) <= 1:
        return VETO
    dmg = SELF_KO_ABILITY_DAMAGE.get(evo_id, 50)
    if T5 and _stall_profile(tc):
        # stall/deck-clock: the eventual self-KO is a pure prize gift -- unless (T5N)
        # a strict-worth (engine / multi-prize) blast target is on the board now
        if not (T5N and len(tc.op.prize) > 2
                and _blast_target_worth(tc, dmg, strict=True) is not None):
            return VETO
    if _belief_is("crustle"):
        return B_EVOLVE - 200
    if _blast_target_worth(tc, dmg) is not None:
        return B_EVOLVE - 100
    atk = _oracle_best_dmg(attack_eval) or _static_best_attack(tc)
    if _chip_into_lethal(tc, dmg, atk):
        return B_EVOLVE - 150
    try:
        if poke is not None and getattr(poke, "maxHp", poke.hp) > poke.hp:
            return B_EVOLVE - 250  # sell the damaged body before it dies for free
    except Exception:
        pass
    return VETO


def _ignition_attach_score(tc, target, tid, o):
    """P4: Ignition Energy is CCC-on-an-Evolution and is discarded at end of turn --
    it is Nebula Beam fuel, never Jetting fuel (cannot pay {W}) and never a bank (it
    evaporates). Attach to the active Mega on a Nebula turn; to a stuck 1-retreat
    pivot as free retreat fare (P7); otherwise hold it in hand."""
    d = O.card_data(tid)
    is_active = (o.inPlayArea == AreaType.ACTIVE)
    if d is not None and getattr(d, "basic", False):
        if (P7 and is_active and tid not in MAIN_ATTACKERS
                and _ready_mega_benched(tc) and _energy_count(target) == 0):
            return B_ATTACH_ENERGY + 380  # retreat fare on the pivot (discards EOT anyway)
        return VETO  # provides one {C} to a Basic and vanishes: pure card burn
    if is_active and tid in MAIN_ATTACKERS and _nebula_turn(tc):
        return B_ATTACH_ENERGY + 600  # same-turn Nebula Beam (210, pierces shields)
    return 200.0  # hold for a Nebula turn; never attach for a Jetting-only turn


# ---------------------------------------------------------------- MAIN context
def score_main(obs, tc, attack_eval, policy=None):
    """attack_eval: dict option_index -> resolved dict from search.resolve_attack
    (plus key 'lethal' handled by caller). Returns list of scores.

    `policy` (R2): when the search rolls out a candidate turn plan it passes a dict of
    mode flags that re-shape the greedy priorities so the same scorer executes that plan:
        no_attack        -> veto ATTACK options (energy-banking / pass line)
        energy_to_bench  -> attach energy to a benched attacker instead of the active
        force_attack_id  -> make the option with this attackId the top priority
        allow_selfko     -> un-veto Cursed Blast when it secures a KO
        force_retreat    -> retreat the active first (once)
    policy=None reproduces the R1 greedy pilot exactly (the guaranteed floor)."""
    P = policy or {}
    opts = obs.select.option
    if R1:
        # v5: pin this decision's race read using the EXACT oracle damage when we have
        # it (attack_eval), so every consumer below sees the same AHEAD/EVEN/BEHIND.
        try:
            race_state(tc, _oracle_best_dmg(attack_eval) or _static_best_attack(tc))
        except Exception:
            pass
    scores = []
    for i, o in enumerate(opts):
        t = O.opt_type(o)
        s = B_END

        if t == OptionType.ABILITY:
            card = O.get_card(obs, o.area, o.index, tc.yi)
            cid = card.id if card is not None else -1
            if cid in SELF_KO_ABILITY_DAMAGE:
                # Cursed Blast KOs its own user (leaks a prize). R1 floor: never.
                # Under search control (allow_selfko) use it only when it secures a KO.
                # P5 greedy path: fire only on a worth-it KO or a combo chip (never
                # blanket B_ABILITY -- the kiyotah 30000-always trap), and never when
                # the self-KO prize could hand the opponent the game.
                dmg = SELF_KO_ABILITY_DAMAGE[cid]
                if P.get("allow_selfko") and _opponent_can_be_ko_by_ability(
                        tc, dmg) is not None:
                    s = B_ABILITY + 500
                elif T5 and P5 and _stall_profile(tc):
                    # stall-guard: never gift the self-KO prize (T5). T5N narrowing:
                    # an engine / multi-prize KO is still worth it (Dwebble-class
                    # denial beats the wall); only junk crustle-blanket gifts stay
                    # vetoed (souta re-measure: blanket veto cost -2.5pp at N=600).
                    if (T5N and len(tc.op.prize) > 2
                            and _blast_target_worth(tc, dmg, strict=True) is not None):
                        s = B_ABILITY + 450
                    else:
                        s = VETO
                elif P5 and len(tc.op.prize) > 1:
                    if _blast_target_worth(tc, dmg) is not None:
                        s = B_ABILITY + 500
                    elif _chip_into_lethal(
                            tc, dmg,
                            _oracle_best_dmg(attack_eval) or _static_best_attack(tc)):
                        s = B_ABILITY + 400
                    else:
                        s = VETO
                else:
                    s = VETO
            elif P0 and _useless_opp_stadium_ability(o, cid):
                s = VETO  # Spikemuth-class no-op (searches owner Pokemon we don't run)
            elif DK and DECK_KIND != "starmie" and cid == KANGASKHAN_M:
                # CR stall discipline (we ARE the stall deck): Run Errand's draw 2
                # ticks our own library-out clock. B1 replaces the old deck<=6 veto
                # (wrong by ~10 cards vs Budew's skip histogram) with the clock-aware
                # rule; B1 off = exact v6 behavior.
                if B1 and DECK_KIND == "crustle_wall":
                    s = _run_errand_score(tc)
                else:
                    s = VETO if tc.me.deckCount <= 6 else B_ABILITY
            else:
                s = B_ABILITY

        elif t == OptionType.PLAY:
            card = O.get_card(obs, AreaType.HAND, o.index, tc.yi)
            cid = card.id if card is not None else -1
            d = O.card_data(cid)
            ctype = d.cardType if d is not None else -1
            if ctype == CardType.POKEMON:
                s = B_PLAY_POKEMON
                # BF: survival floor -- with bench <=1 under shown KO pressure a held
                # body benches at the default band. A quarantined Kang joins UNLESS
                # (i) benching it feeds an immediate one-shot 3-prize gust-KO while
                # we still have one benched body, or (ii) the board is a SAFE STALL
                # (our wall active + _opp_zero_threat: they cannot convert at all,
                # the kojimar won-lock) -- there a bare bench is not a wipe risk and
                # the benched Kang is pure Boss bait (rev2: the rev1 bench-0
                # unconditional release re-fed kojimar exactly the prizes L1a
                # denies, -6.3pp 3/3 seeds).
                # rev3: at bench 1 only the FIRST Kang releases (kang_n == 0) --
                # spares stay quarantined (kojimar's 6-prize losses need TWO Kang
                # KOs; rev1/rev2 released spares at bench 1 and re-fed them,
                # kojimar -6.3/-4.3pp). Bench 0 releases any Kang (the nobench
                # loss is certain otherwise) unless the stall is safe.
                bf_body = (_bench_floor(tc)
                           and (cid != KANGASKHAN_M
                                or (not _bf_safe_stall(tc)
                                    and (tc.bench_n == 0
                                         or (tc.field_counts.get(
                                                 KANGASKHAN_M, 0) == 0
                                             and not _kang_gust_feed(tc))))))
                hold = (_cw_play_pokemon_hold(tc, cid)
                        if (B3 and _cw()) else None)
                if hold is not None and not bf_body:
                    s = hold
                if (L1 and _cw() and cid == KANGASKHAN_M
                        and _fighting_threat(tc) and not bf_body):
                    # L1a Kang quarantine: vs a FIGHTING board every benched Kang
                    # is a 3-prize Boss/Heave-Ho target that their weakness-doubled
                    # attacks 1-2 shot (kojimar diag: both 6-prize losses = exactly
                    # 2 Kang KOs; our wins are OPP_DECKOUT). Spares stay in hand;
                    # the FIRST Kang still benches while the board is thin (bench-
                    # out insurance + the Run Errand engine).
                    board = (1 if tc.active is not None else 0) + tc.bench_n
                    if tc.field_counts.get(KANGASKHAN_M, 0) >= 1 or board >= 2:
                        s = 240.0
                        if BF and _bf_safe_stall(tc):
                            # BF rev2 (the other polarity): during the SAFE STALL
                            # the 240 hold LEAKS -- under the B1 lock every other
                            # play is vetoed, so 240 > B_END and the spare Kang
                            # benches into kojimar's Boss anyway (the "Kang-fed
                            # prize losses persist" live signature). Survival is
                            # guaranteed here; the quarantine goes absolute.
                            s = B_END - 2.0
                elif P6 and tc.bench_n >= 3 and cid not in MAIN_ATTACKERS:
                    # bench discipline: fewer snipe/spread/counter-move targets
                    # (WD mean bench 1.6-1.8; SETUP/TO_BENCH capped in _score_card_pick)
                    s = 500
                elif cid in FEEDER_BASICS:
                    s += 50  # a feeder basic leads to the attacker
                elif cid == DUSKULL:
                    if P5:
                        # engine body: bench 1 (max 2 with room); never a 3rd
                        if tc.dus_in_play == 0 and tc.bench_n < 3:
                            s += 20  # just under the feeder basics
                        elif (tc.dus_in_play == 1 and tc.bench_n < 2
                              and not (P8 and tc.going_second)):
                            s -= 800
                        else:
                            s = 300
                    else:
                        # R1: Duskull can't attack (Cursed Blast vetoed) -> pure
                        # 1-prize liability. Only bench it to avoid a bare board.
                        n_poke = len(tc.field_counts)
                        if n_poke >= 3:
                            s = 300
                        elif tc.field_counts.get(cid, 0) >= 1:
                            s = 600
                if L2 and L2_KANG:
                    # #1 hard one-Kang exposure budget: overrides every branch above
                    # (B3 hold, L1a/BF quarantine, bench discipline) with a final,
                    # non-negotiable quarantine once the veto applies.
                    s = _l2_kang_veto_score(tc, cid, s)
                if (L2 and L2_FLOOR and cid != KANGASKHAN_M
                        and _l2_floor_wanted(tc)):
                    # #3 predictive non-Kang board floor: a non-Kang body outranks
                    # optional supporters/items/draw whenever only one friendly
                    # Pokemon is in play against Lucario belief/predicted pressure.
                    # No-op when the play is already unsuppressed (s stays at its
                    # normal ~B_PLAY_POKEMON value, which already dominates).
                    s = max(s, 13500.0)
            elif ctype == CardType.SUPPORTER:
                s = _supporter_score(tc, cid)
            elif ctype == CardType.ITEM:
                s = _item_score(tc, cid)
            else:
                s = B_PLAY_ITEM
                if D1 and _cw() and cid == BATTLE_CAGE:
                    # D1b Cage economy (2 copies, stadium wars): dragapult's
                    # Watchtower ({C} Pokemon lose Abilities = our Run Errand OFF)
                    # runs x2 -- leading with an unprovoked Cage loses the war 2-2.
                    # Play it to REPLACE their stadium or against a live counter-
                    # bench threat (Phantom Dive / Munkidori: Cage blanks them);
                    # hold it otherwise, and never burn the spare over our own.
                    cur = _our_stadium_id(tc)
                    if cur == BATTLE_CAGE:
                        s = 150.0             # ours already up: keep the spare
                    elif cur >= 0 or _opp_counter_bench_threat(tc):
                        s = B_PLAY_ITEM + 420
                    # (an unprovoked first Cage keeps the v7 default band: the
                    # measured hold-until-provoked variant scored 400 -- below
                    # the attack band, so the Cage never hit the table and the
                    # dragapult row bled 5.7pp)
            if (B1 and s > B_END and _lock_clock(tc)
                    and not (ctype == CardType.ITEM and cid == JUMBO_ICE
                             and s > B_PLAY_ITEM)
                    and not (ctype == CardType.POKEMON
                             and ((1 if tc.active is not None else 0)
                                  + tc.bench_n) <= 2)
                    and ctype != CardType.STADIUM):
                # B1c stall-lock END band: the clock is won and the hostage can't
                # touch us -- hold EVERY playable (Budew ENDs holding Switch 2,437 /
                # Kang 1,908 / Poffin 1,430 / Pokegear 1,098 / Hilda 703 / Boss 679).
                # Kept playable: a gated Jumbo heal (mill-free value), a bench body
                # while our board is <=2 (bench-out insurance -- grimm diag showed
                # 2/30 bench-outs under the unguarded stall), and our Battle Cage
                # stadium (mill-free; blanks Munkidori-class bench counters that
                # convert prizes through the lock). A this-turn WIN still fires via
                # the pilot's lethal shortcut.
                s = VETO

        elif t == OptionType.EVOLVE:
            poke = O.get_card(obs, o.inPlayArea, o.inPlayIndex, tc.yi)
            evo = O.get_card(obs, o.area, o.index, tc.yi)
            evo_id = evo.id if evo is not None else -1
            if evo_id in (DUSCLOPS, DUSKNOIR):
                # R1 vetoed the line outright; P5 un-vetoes it behind the blast gates.
                s = _dus_evolve_score(tc, attack_eval, poke, evo_id) if P5 else VETO
            else:
                s = B_EVOLVE + (len(poke.energies) if poke is not None else 0)
                if evo_id in MAIN_ATTACKERS:
                    s += 400  # evolving into the attacker is top priority among evolves
                if B1 and _lock_clock(tc):
                    s = VETO  # stall END band: hold the evolve (Budew holds a legal
                              # Crustle EVOLVE at 1,130 of its chosen ENDs)

        elif t == OptionType.ATTACH:
            card = O.get_card(obs, o.area, o.index, tc.yi)
            target = O.get_card(obs, o.inPlayArea, o.inPlayIndex, tc.yi)
            cid = card.id if card is not None else -1
            d = O.card_data(cid)
            ctype = d.cardType if d is not None else -1
            if ctype in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY):
                s = B_ATTACH_ENERGY
                tid = target.id if target is not None else -1
                to_bench = (o.inPlayArea == AreaType.BENCH)
                if P4 and cid == IGNITION_ENERGY:
                    # Ignition is Nebula fuel only (CCC on an Evolution, dies EOT)
                    s = _ignition_attach_score(tc, target, tid, o)
                elif B5 and _cw():
                    # B5 energy role-map replaces the generic target bonuses
                    s = _cw_attach_energy_score(tc, cid, tid, target, o)
                else:
                    # Banking: pour the turn's energy onto the benched successor, but
                    # ONLY when the active is already fuelled to attack (so we never
                    # skip an attack for banking). Otherwise fuel the active.
                    bank_ok = (P.get("energy_to_bench") and to_bench
                               and tid in (MAIN_ATTACKERS | FEEDER_BASICS)
                               and active_attack_ready(tc.active))
                    # P8: going second, bank Basic energy on the successor earlier
                    # (avoid the energy-empty promotion after our active is KO'd)
                    p8_bank = (P8 and tc.going_second and to_bench
                               and cid in PRIMARY_ENERGIES
                               and tid in (MAIN_ATTACKERS | FEEDER_BASICS)
                               and active_attack_ready(tc.active))
                    if bank_ok or p8_bank:
                        s += 400
                    else:
                        if o.inPlayArea == AreaType.ACTIVE:
                            s += 50
                        if tid in MAIN_ATTACKERS:
                            s += 300
                        elif tid in FEEDER_BASICS:
                            s += 120  # will evolve into the attacker
                        if (DK and tid in WALL_IDS
                                and (_wall_mode(tc) or _opp_wall_active(tc))
                                and o.inPlayArea == AreaType.ACTIVE
                                and _energy_count(target) < 3):
                            # CR wall fuel: 3 energy on the active wall = Superb
                            # Scissors 120 (pierces effects) + Jumbo Ice Cream heals.
                            # Also the wall-BREAKER line: vs a shielded opp active our
                            # ex Kangaskhan deals 0 -- the non-ex Crustle is the swing.
                            s += 340
                        if (R2 and _behind(tc) and tid in MAIN_ATTACKERS
                                and o.inPlayArea == AreaType.ACTIVE):
                            # BEHIND: nudge the turn's attach toward the active
                            # attacker. Deliberately a NUDGE (+80), not a band jump:
                            # the first cut (max(s, B_PLAY_ITEM+600)) outranked the
                            # Ignition-Nebula attach (8600) and Wally (8650) and
                            # measurably KILLED the tank-race plan vs lucario
                            # (Nebula 42->24, Wally 17->7 in the 60-game diag)
                            s += 80
                if B1 and _lock_clock(tc):
                    # stall END band: the only attach still worth making is loading
                    # the ACTIVE tank to 3E (Jumbo eligibility / Superb readiness);
                    # everything else is held (Budew ENDs holding an ATTACH 741x)
                    tid2 = target.id if target is not None else -1
                    if not (o.inPlayArea == AreaType.ACTIVE
                            and _energy_count(target) < 3
                            and (tid2 == KANGASKHAN_M or tid2 in WALL_IDS)):
                        s = VETO
            elif ctype == CardType.TOOL:
                s = B_ATTACH_TOOL
                if B5 and _cw() and cid == HEROS_CAPE:
                    # B5: Hero's Cape (+100 HP, the one ACE SPEC) belongs on the
                    # tank -- Budew: Kang ACT 376 / Crustle ACT 139 (756 uses vs our
                    # 138, and ours went to Shaymin 8x)
                    tid = target.id if target is not None else -1
                    if tid == KANGASKHAN_M or tid in WALL_IDS:
                        s += 320
                    elif tid == SHAYMIN_CR:
                        s = VETO              # never Cape the designated sacrifice
                    else:
                        s = B_ATTACH_TOOL - 600.0   # Dwebble-class: last resort
                if o.inPlayArea == AreaType.ACTIVE and s > VETO:
                    s += 30
                if B1 and _lock_clock(tc):
                    s = VETO
            else:
                s = B_ATTACH_TOOL

        elif t == OptionType.RETREAT:
            # R1 floor: never retreat (it wrecks tempo for an evolve-in-place deck).
            # Under search control (force_retreat) reposition once, before attacking.
            # P7: allow the WD pivot -- cheap non-attacker out, ready Mega in.
            if P.get("force_retreat") and not getattr(tc.st, "retreated", False):
                s = 40000
            elif P7 and _pivot_retreat_ok(tc):
                s = B_RETREAT
            else:
                s = VETO

        elif t == OptionType.ATTACK:
            if P.get("no_attack"):
                s = VETO
            elif P.get("force_attack_id") is not None and o.attackId == P.get("force_attack_id"):
                s = 60000
            elif attack_eval:
                s = _attack_score(attack_eval.get(i), tc)
            else:
                # rollout (no oracle): pick the max-static-damage attack consistently across
                # plans, so plan comparison isolates the structural difference, not attack choice.
                a = O.attack_data(o.attackId)
                s = B_ATTACK_BASE + (a.damage if a else 0)

        elif t == OptionType.END:
            s = B_END

        elif t == OptionType.DISCARD:
            s = 100  # discarding in-play cards rarely wanted at MAIN
        else:
            s = 5

        scores.append(s)
    return scores


def _attack_score(ev, tc=None):
    if ev is not None and ev.get("wins"):
        return 50000
    if B2 and tc is not None and _lock_clock(tc):
        # B2 DON'T-BREAK-THE-LOCK: 621 of Budew's END-with-attack-available states
        # are vs a stranded ex hostage -- KOing it frees their board and feeds the
        # re-arm (ep 85224267: Crustle vs Garchomp ex e1 held T19->T41+, opp deck
        # 23->0; our v6 picks Superb Scissors at 85 of these). A this-turn WIN never
        # reaches here (handled above / by the pilot's lethal shortcut).
        # B2F guard 2 (ep 85544056): an oracle-VERIFIED OHKO of their ACTIVE for a
        # prize is never held when the race read is thin -- thin = mill-win margin
        # < 8 (turns ~ cards at the passive 1/turn floor) or their prize path is
        # within ~2 KOs of closing (<= 3 cards left, one mega trade ends it). A
        # free verified KO that doesn't break a WON lock (hostage stranded + big
        # margin, opp not converting) is still held -- that's v7's win condition.
        if B2F and ev is not None and ev.get("ko_active") and ev.get("prizes_taken", 0) >= 1:
            try:
                thin = (_deck_race(tc)[0] < 8.0) or (len(tc.op.prize) <= 3)
            except Exception:
                thin = False
            if thin:
                pass                          # fall through: value the KO normally
            else:
                return VETO
        else:
            return VETO
    elif (L2 and L2_CLOCK and tc is not None and _l2_clock_veto(tc)
          and ev is not None and not ev.get("ko_active")
          and not ev.get("prizes_taken", 0)):
        # #5: the deck clock already wins -- hold non-essential attacks (no KO, no
        # prize) rather than spend the turn; a real KO/prize still falls through.
        return VETO
    if ev is None:
        return B_ATTACK_BASE  # search failed -> still allow attacking as fallback
    mirc = (tc is not None and _mir_closing(tc))
    if P2:
        # prize-aware: a bench-snipe KO is a prize even when the defender survives
        # (pairs with the search.resolve_attack KO-attribution fix)
        chip = min(300, ev.get("def_dmg", 0))
        if T3 and chip > 0 and not ev.get("ko_active"):
            # T3: chip damage is discounted when the opponent is KNOWN to hold a
            # switch/heal/scoop card (the chip can be undone) -> prefer KO lines
            t = _trk()
            try:
                if t is not None and t.opp_holds(RESCUE_IDS):
                    chip *= 0.6
            except Exception:
                pass
        s = (B_ATTACK_BASE + chip
             + 400 * ev.get("prizes_taken", 0)
             + (150 if ev.get("ko_active") else 0))
        if R3 and tc is not None:
            # v5 tank-race tie-break: value each line by prizes-per-turn against the
            # ACTIVE (exact-oracle damage): pace = pv/turns-to-KO. Nebula 210 beats
            # Jetting 120 into a 340 Lucario (3 prizes/2 turns vs /3 turns); no-ops
            # when both lines KO at the same speed (t2k equal -> equal bonus).
            try:
                opa = (tc.op.active[0]
                       if (tc.op.active and tc.op.active[0] is not None) else None)
                if opa is not None:
                    if ev.get("ko_active"):
                        tko = 1
                    else:
                        dd = ev.get("def_dmg", 0) or 0
                        tko = _t2k(getattr(opa, "hp", 0), dd) if dd > 0 else 0
                    if 0 < tko < 99:
                        s += 400.0 * max(1, O.prize_count(opa)) / tko
                        if _behind(tc):
                            # BEHIND: prizes N turns out don't beat their shorter
                            # clock -- take the fastest lethal path on the active
                            s -= 250.0 * (tko - 1)
            except Exception:
                pass
        if R2 and tc is not None and _behind(tc) and ev.get("ko_active"):
            # BEHIND: an active KO (deny their attacker) over chip-and-develop.
            # (The first cut also added +160/prize -- that double-counted the bench
            # snipe and out-bid the faster tank line; dropped after the lucario diag.)
            s += 320.0
        if mirc:
            # P-MIR(b) closure: on a losing/contested mirror clock every prize
            # converted is the win condition -- force the attack race (live: we
            # attacked 0-6x in the losses vs the tuned bots' 8-14 Crustle attacks)
            s += 300.0 + 350.0 * ev.get("prizes_taken", 0) \
                + (150.0 if ev.get("ko_active") else 0.0)
        return s
    s = B_ATTACK_BASE
    if ev.get("ko_active"):
        s = 1700 + 30 * ev.get("prizes_taken", 0)
    else:
        s = 1000 + min(300, ev.get("def_dmg", 0)) * 1.0
    if mirc:
        s += 300.0
    return s


def _supporter_score(tc, cid):
    # Draw / search supporters: dig early (small hand / undeveloped board), refuel late.
    if tc.deck_low and cid in (JUDGE, LILLIE_DET, CARMINE):
        # avoid decking out on big draws when the deck is nearly empty
        if tc.me.deckCount <= 2:
            return VETO
    if (T5 and cid in (JUDGE, LILLIE_DET, CARMINE) and tc.hand_size >= 3
            and tc.me.deckCount <= (8 if T5N else 12) and _stall_profile(tc)):
        # stall-guard: on the deck-out clock every big draw ticks OUR loss timer --
        # hold them unless the hand is actually dead (live autopsy library-out loss).
        # T5N: window tightened to deck<=8 -- at 9-12 vs a wall the hold denied the
        # digging that finds Nebula pieces (souta -2.5pp re-measure); the Alakazam
        # deck-race save (arm a, deck<=5) is unaffected.
        return 2000.0
    if (O1 and _standoff(tc) and tc.hand_size >= 2
            and cid in (CARMINE, JUDGE, LILLIE_DET, HILDA)):
        # O1: draws/searches tick our own clock while theirs runs for free
        return 1900.0
    early = (not tc.developed) or tc.hand_size <= 3
    base = B_SUPPORTER_EARLY if early else B_SUPPORTER_LATE

    if MIR and _cw() and cid in (LILLIE_DET, CARMINE, JUDGE):
        mirror, mill = _mir_opp(tc)
        if ((mirror or mill) and tc.hand_size >= 3
                and (tc.me.deckCount or 0) <= (30 if mill else 20)
                and (mill or not _deck_race_won(tc))):
            # P-MIR(a): on a losing/contested mirror clock the big draws are
            # library damage (Lillie x3-4 in every live deckout loss); hold them
            # while the hand still has plays. Hilda is EXEMPT: the wall/energy
            # refetch is Crustle supply, and holding it lost the true-mirror
            # prize race in the first-cut probe (self_mirror b=8/c=1).
            return 2000.0

    if MIR and _cw() and cid == BOSS_ORDERS and _mir_closing(tc):
        # P-MIR(b) closure: drag any KILLABLE bench body (Great Tusk 140 / a bare
        # Dwebble / Terrakion) in front of our payable attack and convert -- in
        # the mirror the hostage-lock Boss never fires (_gust_stall_wanted needs
        # a won clock) and the default drag-a-threat wastes the gust. Prizes are
        # the only clock we can still win.
        try:
            atk = _wall_payable_dmg(tc)
            if atk > 0:
                for p in (tc.op.bench or []):
                    if p is not None and getattr(p, "hp", 999) <= atk:
                        return B_SUPPORTER_EARLY + 630.0
        except Exception:
            pass

    if DK and DECK_KIND != "starmie" and cid == XEROSIC:
        try:
            if _discipline_rule_active(tc):
                # Pre-registered discipline rule (intel/discipline_rule_2026-07-16.md):
                # demote PLAY:Xerosic's Machinations below the on-curve EVOLVE/ATTACH
                # alternative when we are behind on prizes. Xerosic was v11's single
                # largest PLAY-instead-of-develop divergence target on the mined panel
                # (320/1,542 = 20.8% of rows where the human pilot EVOLVEd/ATTACHed and
                # v11 chose PLAY instead, tuna_v11_decisions_ours.jsonl). Takes priority
                # over the P-BLITZ/hand-size branches below -- being behind on prizes
                # with a real development play on the table outranks the disruption
                # timing this branch otherwise optimizes for.
                _DISCIPLINE_DIAG["plays_demoted"] += 1
                return B_DISCIPLINE_DEMOTE
        except Exception:
            pass
        if (SBL and _cw() and _blitz_opp(tc)
                and not any(tc.field_counts.get(w, 0) for w in WALL_IDS)):
            # P-BLITZ: vs the Staryu/Mega Starmie blitz the denial turn is a dead
            # turn until the wall line stands -- their t4-13 kills don't care
            # about hand size, and our t<=9 live losses burned Xerosic x3 while
            # the board died. Board first; denial windows resume once Crustle is up.
            return base
        # DK disruption timing (the Judge-timing spirit): Xerosic strips their hand
        # to 3 -- fire into a big hand, earlier vs Alakazam (Powerful Hand pays
        # 20/card); hold a dead Xerosic while their hand is already small.
        if tc.op.handCount >= 6:
            return B_SUPPORTER_EARLY + 600.0
        if tc.op.handCount >= 5 and _belief_is("alakazam"):
            return B_SUPPORTER_EARLY + 500.0
        if tc.op.handCount <= 4 and tc.hand_size >= 4:
            return 2000.0
        return base

    if B2 and _cw() and cid == BOSS_ORDERS:
        # B2 gust-lock: Boss's Orders CREATES the lock (drag a can't-attack body in
        # front of the wall) and is then HELD -- re-gusting would free the hostage.
        if _lock_clock(tc):
            return 130.0
        if _gust_stall_wanted(tc) and _hostage_candidate(tc) is not None:
            return B_SUPPORTER_EARLY + 550.0  # below the Xerosic >=6-hand window
        # else: fall through to the default drag-a-threat priority

    if L1 and _cw() and cid == BOSS_ORDERS and not _lock_clock(tc):
        # L1b: a payable drag-and-KO of their line basic / engine body outranks
        # the draw engine this turn (a prize + one fewer future Mega Lucario /
        # Mega Starmie / Alakazam; the TO_ACTIVE pick routes to the same target)
        try:
            atk = _wall_payable_dmg(tc)
            if atk > 0:
                if L2 and L2_BOSS and _fighting_threat(tc):
                    # #4: Lucario-specific KO-target ordering (wounded Hariyama<=120
                    # > Makuhita > Riolu > Lunatone/Solrock), not just the generic
                    # BIG_LINE_BASICS/_engine_target class.
                    best = None
                    for p in (tc.op.bench or []):
                        if p is None:
                            continue
                        sc = _l2_boss_target_score(tc, p, atk)
                        if sc is not None and (best is None or sc > best):
                            best = sc
                    if best is not None:
                        return B_SUPPORTER_EARLY + 620.0 + best
                for p in (tc.op.bench or []):
                    if (p is not None and getattr(p, "hp", 999) <= atk
                            and (p.id in BIG_LINE_BASICS
                                 or _engine_target(p.id))):
                        return B_SUPPORTER_EARLY + 620.0
        except Exception:
            pass

    if cid == WALLY:
        # Wally's Compassion: heal ALL damage from one Mega ex, energy back to hand.
        # R1 vetoed it. P1: with a re-fuel in hand the real cost is ~zero (Jetting
        # costs one W; Ignition alone pays Nebula) -- WD's 341-use sustain engine.
        if not P1:
            return VETO
        dmg = _max_mega_damage(tc)
        refuel = (any(tc.hand_counts.get(e, 0) for e in PRIMARY_ENERGIES)
                  or tc.hand_counts.get(IGNITION_ENERGY, 0) > 0)
        if dmg >= 120 and refuel and not getattr(tc.st, "energyAttached", False):
            return 8650.0  # above ATTACH: Wally -> re-attach -> still attack this turn
        if dmg >= 180 and refuel:
            return 6000.0  # WD's median heal; worth the lost attack
        return VETO

    if P3:
        if cid == CARMINE:
            # "Discard your hand and draw 5": never burn live cards; cheap refresh
            # at hand<=3 (+Carmine) or the card's explicit T1-going-first exception.
            holds_keeps = (any(tc.hand_counts.get(a, 0) for a in MAIN_ATTACKERS)
                           or any(tc.hand_counts.get(e, 0) for e in PRIMARY_ENERGIES)
                           or tc.hand_counts.get(IGNITION_ENERGY, 0) > 0)
            if holds_keeps:
                return VETO
            if tc.hand_size <= 4:
                return base
            if getattr(tc.st, "turn", 0) == 1 and tc.going_first:
                return base
            return 2000.0  # big hand: let any other supporter win
        if cid == JUDGE:
            # opponent-hand denial (Alakazam Powerful Hand = 20 dmg per card)
            thr = 6 if _belief_is("alakazam") else 7
            if tc.op.handCount >= thr:
                return B_SUPPORTER_EARLY + 600.0
            if T1:
                # T1: fire earlier when the tracker KNOWS their hand is curated --
                # judge_ev = 0.5*(hand-4) + value of known searched/kept cards
                t = _trk()
                try:
                    if (t is not None and tc.op.handCount >= thr - 2
                            and t.judge_ev() >= 2.5):
                        return B_SUPPORTER_EARLY + 500.0
                except Exception:
                    pass
        if cid == HILDA:
            if B6 and _cw():
                # B6: Budew's Hilda is the ~T9 wall/energy REFETCH (median turn 9,
                # p25 5), not an opener -- our early +700 fired 2,067x vs their
                # 1,493 total and won the priority fight Xerosic should win.
                need_wall = (sum(tc.field_counts.get(w, 0) for w in WALL_IDS)
                             + sum(tc.hand_counts.get(w, 0) for w in WALL_IDS)) == 0
                need_fuel = not any(tc.hand_counts.get(e, 0)
                                    for e in PRIMARY_ENERGIES)
                if _supply_rule_active(tc):
                    # Lever 3(b): thin accessible Crustle supply -- the refetch is
                    # worth pre-empting other supporter plays, not just tying them
                    # (outranks the plain need_wall/need_fuel +250 band above).
                    return B_SUPPORTER_EARLY + 800.0
                if need_wall or need_fuel:
                    return B_SUPPORTER_EARLY + 250.0
                return min(base, 2400.0)     # nothing to refetch: hold it
            # Evolution Pokemon + Energy to hand: WD's setup engine for the T4 Mega
            if (not tc.developed) or _our_turn_no(tc) < 4:
                return B_SUPPORTER_EARLY + 700.0
            if R2 and _behind(tc) and not any(
                    tc.hand_counts.get(e, 0) for e in PRIMARY_ENERGIES) and not \
                    tc.hand_counts.get(IGNITION_ENERGY, 0):
                # BEHIND with no attack fuel in hand: the guaranteed energy(+evolution)
                # fetch IS the tempo play -- outranks generic draw supporters
                return B_SUPPORTER_EARLY + 650.0
        if cid == LILLIE_DET:
            # the exactly-6-prizes 8-draw window (54% of WD's Lillie plays).
            # B6 (crustle): widen the hand gate to <=7 -- Budew casts Lillie at
            # median hand 6 / p75 7, 69% inside this window; our hand<=5 gate
            # blocked most of it (314 + 331 flips). Mill-neutral (shuffles back).
            lillie = base
            hand_lim = 7 if (B6 and _cw()) else 5
            if len(tc.me.prize) == 6 and tc.hand_size <= hand_lim:
                lillie = max(base, B_SUPPORTER_EARLY + 300.0)
            if T2:
                # T2: Lillie shuffles our hand away -- price the swap with the EXACT
                # remaining-deck composition (draw-pool density of keeper cards vs
                # the keepers currently in hand that get shuffled back)
                t = _trk()
                try:
                    if t is not None:
                        n_draw = 8 if len(tc.me.prize) == 6 else 6
                        density = t.our_good_density(
                            lambda c: _to_hand_value(tc, c), 120.0)
                        keeps = sum(k for c, k in tc.hand_counts.items()
                                    if _to_hand_value(tc, c) >= 120.0)
                        ev = n_draw * density - keeps
                        if ev >= 3.0 and tc.hand_size <= 4:
                            lillie = max(lillie, B_SUPPORTER_EARLY + 350.0)
                        elif ev <= 0.5 and keeps >= 2:
                            # rich hand, thin deck: do not shuffle the keepers away
                            lillie = min(lillie, 2400.0)
                except Exception:
                    pass
            return lillie
    return base


def _item_score(tc, cid):
    if (L2 and L2_FLOOR and cid == POFFIN and _cw() and _l2_floor_wanted(tc)):
        # #3: raise the floor before optional Supporters/disruption/tools/draw --
        # outranks every Supporter-band hold below (checked first, deliberately).
        return 13000.0
    # P6B (risky; isolated A/B): hold development items once developed with a fuelled
    # successor and a modest hand -- WD ENDs holding playables 707x (99.3% disagr.).
    # Scored below the attack band = effectively held (the turn still attacks).
    if (P6B and cid in (POFFIN, ULTRA_BALL, POKEGEAR, POKE_PAD)
            and tc.developed and tc.hand_size <= 6
            and active_attack_ready(tc.active) and _benched_fueled_successor(tc)):
        return 150
    if DK and DECK_KIND != "starmie":
        # --- deck re-bakeoff item hooks (inert on Starmie: ids not in the list) ---
        if (L2 and L2_CLOCK and cid in (POFFIN, POKEGEAR, ULTRA_BALL, POKE_PAD)
                and _l2_clock_veto(tc)):
            return 150.0                      # #5: their deck clock already loses
        if (O1 and cid in (POFFIN, POKEGEAR, ULTRA_BALL, POKE_PAD)
                and _standoff(tc)):
            return 150.0                      # O1: every search costs a library card
        if MIR and _cw() and cid in (POFFIN, POKEGEAR, ULTRA_BALL, POKE_PAD):
            mirror, mill = _mir_opp(tc)
            if ((mirror or mill) and tc.hand_size >= 3
                    and (tc.me.deckCount or 0) <= (24 if mill else 16)):
                # P-MIR(a): late-deck in the mirror every search ticks the only
                # clock that kills us (vs a Tusk miller the effective deck is
                # ~half the count) -- hold unless the hand is actually thin
                return 150.0
        if cid == JUMBO_ICE:
            # CR sustain: heal 80 only when it heals real damage on a >=3-energy active
            a = tc.active
            try:
                if (a is not None and _energy_count(a) >= 3
                        and (getattr(a, "maxHp", a.hp) - a.hp) >= 60):
                    return B_PLAY_ITEM + 350
            except Exception:
                pass
            return 150.0
        if cid == HAND_TRIMMER:
            # both players discard to 5, opponent first -- only into a big opp hand.
            # B6 relaxes the gates (Budew fires it at opp hand >=6 even at own 7).
            if B6 and DECK_KIND == "crustle_wall":
                return (B_PLAY_ITEM + 100.0) if (tc.op.handCount >= 6
                                                 and tc.hand_size <= 7) else 150.0
            return (B_PLAY_ITEM + 100.0) if (tc.op.handCount >= 7
                                             and tc.hand_size <= 6) else 150.0
        if cid == SWITCH_ITEM and DECK_KIND == "crustle_wall":
            if B4:
                return _cw_switch_score(tc)  # B4: HELD unless the swap changes damage
            # CR wall maintenance: Switch serves the wall swap, not random tempo
            a = tc.active
            wall_benched = any(p is not None and p.id in WALL_IDS
                               for p in (tc.me.bench or []))
            if ((_wall_mode(tc) or _opp_wall_active(tc)) and a is not None
                    and a.id not in WALL_IDS and wall_benched):
                return B_PLAY_ITEM + 250.0   # wall in front (their ex attacks, or
                                             # their wall blanks our ex Kangaskhan)
            if ((not (_wall_mode(tc) or _opp_wall_active(tc))) and a is not None
                    and a.id in WALL_IDS and _ready_mega_benched(tc)):
                return B_PLAY_ITEM + 200.0   # wall pointless vs non-ex: promote Kang
            return 150.0
        if B1 and DECK_KIND == "crustle_wall" and cid == POFFIN:
            # B1b: items cost library (Poffin = -2 future draws). Only while the
            # wall supply is unestablished; dead once developed (their 2,144 uses
            # vs our counterfactual 3,069, END-holding Poffin 1,430).
            supply = (tc.field_counts.get(DWEBBLE, 0) + tc.hand_counts.get(DWEBBLE, 0)
                      + sum(tc.field_counts.get(w, 0) + tc.hand_counts.get(w, 0)
                            for w in WALL_IDS))
            if supply >= 2:
                return 150.0
            return B_PLAY_ITEM + 300
        if B1 and DECK_KIND == "crustle_wall" and cid == POKEGEAR:
            # B1b: Pokegear costs 1 library card -- only dig when the hand actually
            # lacks a supporter (they hold it 1,098x at END)
            if any(O.is_supporter(c) for c, n in tc.hand_counts.items() if n > 0):
                return 150.0
            return B_PLAY_ITEM - 500
        if (DECK_KIND == "alakazam" and cid == POFFIN and tc.developed
                and tc.active is not None and tc.active.id == ALAKAZAM_ID
                and active_attack_ready(tc.active)):
            # AZ hand-size play: with Alakazam attacking, every spent hand card is
            # -20 Powerful Hand damage -- hold late development items
            return 150.0
    if cid == POFFIN:
        return B_PLAY_ITEM + 300  # cheap 2-basic search, great early
    if cid == ULTRA_BALL:
        # costs 2 cards; fine unless hand is tiny
        return B_PLAY_ITEM if tc.hand_size >= 3 else 1500
    if cid in (POKEGEAR, POKE_PAD):
        return B_PLAY_ITEM - 500
    return B_PLAY_ITEM


# ---------------------------------------------------- non-MAIN (CARD/etc.) contexts
def score_generic(obs, tc, context):
    opts = obs.select.option
    scores = []
    for o in opts:
        scores.append(_score_generic_option(obs, tc, context, o))
    return scores


def _score_generic_option(obs, tc, context, o):
    t = O.opt_type(o)

    if t == OptionType.NUMBER:
        return float(o.number if o.number is not None else 0)  # draw/place as many
    if t == OptionType.YES:
        return _yesno_pref(context, True)
    if t == OptionType.NO:
        return _yesno_pref(context, False)
    if t == OptionType.SKILL:
        return 1.0
    if t == OptionType.SPECIAL_CONDITION:
        return 1.0
    if t == OptionType.ATTACK:
        return 1.0  # standalone attack-pick context: any legal (oracle handled at MAIN)

    if t in (OptionType.CARD, OptionType.TOOL_CARD, OptionType.ENERGY_CARD, OptionType.ENERGY):
        card = O.get_card(obs, o.area, o.index, o.playerIndex)
        if card is None:
            return 0.0
        return _score_card_pick(tc, context, o, card)

    return 0.0


def _yesno_pref(context, is_yes):
    # Contexts where YES is the good answer.
    yes_good = {
        SelectContext.IS_FIRST,        # go first (extra setup turn)
        SelectContext.MULLIGAN,        # redraw a no-Basic hand
        SelectContext.ACTIVATE,        # activate a (beneficial) effect
        SelectContext.FIRST_EFFECT,
        SelectContext.COIN_HEAD,       # call heads
    }
    prefer_yes = context in yes_good
    if is_yes:
        return 1.0 if prefer_yes else 0.0
    return 0.0 if prefer_yes else 1.0


def _score_card_pick(tc, context, o, card):
    cid = card.id
    mine = (o.playerIndex == tc.yi)
    is_poke = O.is_pokemon(cid)

    # --- opponent-target damage placement (Jetting Blow snipe, Cursed Blast) ---
    if context in (SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER,
                   SelectContext.DAMAGE_COUNTER_ANY):
        if not mine and is_poke:
            if P2:
                # shared targeting (same function the oracle's sub-choices use):
                # exact-KO first, then engine Pokemon over tanks, hp>>amount penalized
                if context == SelectContext.DAMAGE:
                    return damage_target_score(card, 50, tc=tc)
                # counter placement = Cursed Blast: 130 if a Dusknoir is blasting
                amount = 130 if (tc.field_counts.get(DUSKNOIR, 0)
                                 or (tc.discard_counts.get(DUSKNOIR, 0)
                                     and not tc.field_counts.get(DUSCLOPS, 0))) else 50
                return damage_target_score(card, amount, combo_ok=True,
                                           atk_dmg=_static_best_attack(tc), tc=tc)
            # R1: prefer a guaranteed KO (snipe is ~50) for a free prize, else soften
            # the biggest threat (highest value).
            base = pokemon_score(card)
            if card.hp <= 50:
                base += 2000
            elif card.hp <= 90:
                base += 300
            return base
        # placing on our own Pokemon is bad
        return -pokemon_score(card) if is_poke else 0.0

    # --- choosing a Pokemon to send to Active ---
    if context in (SelectContext.SWITCH, SelectContext.TO_ACTIVE, SelectContext.SETUP_ACTIVE_POKEMON):
        if mine:
            s = (len(card.energies) * 3) if hasattr(card, "energies") else 0
            if cid in MAIN_ATTACKERS:
                s += 60
                if active_attack_ready(card) and (
                        P8 or (R2 and R1 and _race_lbl(tc) != RACE_AHEAD)):
                    s += 140  # after a KO, promote the READY Mega first
            elif cid in FEEDER_BASICS:
                s += 25
            elif cid in (DUSKNOIR, DUSCLOPS):
                s += 10
                if (R2 and _behind(tc)
                        and context != SelectContext.SETUP_ACTIVE_POKEMON
                        and len(tc.op.prize) >= 3
                        and not _ready_mega_benched(tc)
                        and _benched_fueled_successor(tc)):
                    # BEHIND pacing body (v5): with NO ready Mega to promote, feeding
                    # an unready 3-prize Mega into a lost exchange loses the race
                    # outright (autopsy: Archaludon 3-vs-2 deficit). Give them the
                    # 1-prize Dus* body instead while the benched successor fuels up
                    # (it still threatens Cursed Blast on its way out). Narrow gates:
                    # never near their last prizes, never at setup, never a Duskull
                    # (the failed P8 recipe), only while a successor is developing.
                    s += 75
            else:
                s += 5
            if P8 and cid == DUSKULL:
                if (context == SelectContext.SETUP_ACTIVE_POKEMON and tc.going_second
                        and sum(tc.hand_counts.get(f, 0) for f in FEEDER_BASICS) <= 1):
                    s += 30  # second-seat lead: shield the lone Staryu behind Duskull
                elif (context != SelectContext.SETUP_ACTIVE_POKEMON and tc.going_second
                        and len(tc.op.prize) > 1 and _benched_fueled_successor(tc)):
                    s += 35  # sacrificial promote protecting a developing attacker
            _l2w_promote = L2 and L2_WALL and _cw()
            _wtrig = _l2_wall_active_is_ex(tc) if _l2w_promote else _wall_mode(tc)
            if DK and cid in WALL_IDS and (_wtrig or _opp_wall_active(tc)):
                # CR wall maintenance: vs ex attack damage the wall takes 0 -- it
                # holds the Active over any attacker/energy tie-break. Same promote
                # when THEIR active is the shielded wall (our Crustle is the breaker).
                # #2: _wtrig is active-specific under L2_WALL (opp_active_is_wallable_ex)
                # instead of board-wide _wall_mode.
                if not (ST1 and _pierce_threat(tc)):
                    s += 260                  # ST1: Nebula kills the wall through
                                              # Rock Inn -- no wall preference
            if _l2w_promote and cid in WALL_IDS and _l2_kang_evac_lethal(tc):
                s += 500.0   # #2: Crustle must win the promote race during an evac
            if (B4 and _cw()
                    and context != SelectContext.SETUP_ACTIVE_POKEMON):
                # B4 promote/sac order (Budew's forced-promote flips: Crustle where
                # we send Dwebble x403 / Kang x148; Shaymin where we send Dwebble
                # x134). Wall first when it blanks them, else the Kang tank;
                # Shaymin is the sacrifice; Dwebble is Crustle feedstock -- LAST
                # (4 Crustle in 60: the wall supply IS the game).
                if cid in WALL_IDS:
                    s += 180 if ((_wtrig or _opp_wall_active(tc))
                                 and not (ST1 and _pierce_threat(tc))) else 60
                elif cid == KANGASKHAN_M:
                    s += 90
                    if L2 and L2_KANG and _l2_kang_hard_veto(tc):
                        s -= 200   # #1: budget veto beats L1a's plain -140
                    elif L1 and _fighting_threat(tc):
                        # L1a: promoting the FIGHTING-weak 3-prize tank into an
                        # Aura Jab / Draconic Buster board is the prize gift the
                        # census lucario losses are made of -- it goes up LAST
                        # (below Shaymin's 40) unless it is the only body left.
                        s -= 140
                    elif ST1 and _pierce_threat(tc) and active_attack_ready(card):
                        s += 140              # the Caped Kang IS the tank vs Nebula
                elif cid == SHAYMIN_CR:
                    s += 40
                elif cid == DWEBBLE:
                    if _supply_rule_active(tc):
                        # Lever 3(a): never sacrifice Dwebble under thin accessible
                        # Crustle supply -- hard demotion well below Shaymin's +40 so
                        # Dwebble is promoted dead last while any other body exists.
                        # Diag counter is a proxy (fires of the harsher penalty on a
                        # Dwebble candidate), not a strict old-vs-new counterfactual.
                        s -= 400
                        try:
                            _SUPPLY_DIAG["dwebble_sacs_prevented"] += 1
                        except Exception:
                            pass
                    else:
                        s -= 20
            if (S1 and _cw() and context == SelectContext.SETUP_ACTIVE_POKEMON
                    and tc.going_second and cid == DWEBBLE):
                # S1 second-seat wall rush: going 2nd we may ATTACK on turn 1 --
                # Dwebble's Ascension (a single {C}) evolves into Crustle from the
                # deck, standing the wall a full turn earlier than the evolve line
                # (census: the 2nd-seat bleed rows are the setup-race classes).
                s += 110
            return float(s)
        else:
            # opponent side (Boss's Orders): drag up the best KO target / threat --
            # unless B2's gust-lock window is open: then strand the weakest body
            if B2 and _cw() and _gust_stall_wanted(tc):
                return _gust_pick_score(tc, card)
            if L1 and _cw():
                # L1b Boss line-snipe: drag-and-KO their FUTURE attacker's basic /
                # engine body when our active's attack actually kills it this turn
                # (typed payability -- no dragging what we cannot kill). Riolu 70
                # under Superb Scissors 120 = a prize AND one fewer Mega Lucario;
                # same machinery covers Abra / Staryu / Cinderace / Dreepy. The
                # old default dragged argmax(pokemon_score) = their unkillable
                # 340-HP Mega Lucario (kiyotah diag: 0 prizes taken all game).
                atk = _wall_payable_dmg(tc)
                if L2 and L2_BOSS and _fighting_threat(tc) and atk > 0:
                    sc = _l2_boss_target_score(tc, card, atk)
                    if sc is not None:
                        return 4200.0 + sc + pokemon_score(card)
                if (atk > 0 and getattr(card, "hp", 999) <= atk
                        and (card.id in BIG_LINE_BASICS
                             or _engine_target(card.id))):
                    return 4200.0 + pokemon_score(card)
            return pokemon_score(card)

    if context in (SelectContext.SETUP_BENCH_POKEMON, SelectContext.TO_BENCH, SelectContext.TO_FIELD):
        if (L2 and L2_KANG and cid == KANGASKHAN_M and _l2_kang_hard_veto(tc)
                and not _l2_kang_emergency(tc)):
            return 8.0  # #1: hard veto mirrors the PLAY-band rule for effect picks
        if (P6 and context != SelectContext.SETUP_BENCH_POKEMON and tc.bench_n >= 3):
            return VETO  # decline the optional bench fill (fewer snipe/spread targets)
        if L1 and _cw() and cid == KANGASKHAN_M and _fighting_threat(tc):
            # L1a quarantine mirrors the PLAY-band rule for effect-driven picks
            board = (1 if tc.active is not None else 0) + tc.bench_n
            if tc.field_counts.get(KANGASKHAN_M, 0) >= 1 or board >= 2:
                return 12.0
        if B3 and _cw():
            # B3 bench discipline mirrors the PLAY-band rule for effect-driven picks
            if cid == KANGASKHAN_M and tc.field_counts.get(KANGASKHAN_M, 0) >= 1:
                return 12.0   # a spare 3-prize Kang stays in hand
            if (cid == SHAYMIN_CR
                    and context != SelectContext.SETUP_BENCH_POKEMON
                    and ((1 if tc.active is not None else 0) + tc.bench_n) >= 2):
                return 10.0   # Shaymin benches as a planned sac, not development
        if cid in FEEDER_BASICS:
            if P6:
                line = (sum(tc.field_counts.get(f, 0) for f in FEEDER_BASICS)
                        + sum(tc.field_counts.get(a, 0) for a in MAIN_ATTACKERS))
                return 40.0 if line < 2 else 22.0
            return 40.0
        if cid == DUSKULL:
            if P5:
                if context == SelectContext.SETUP_BENCH_POKEMON:
                    return 30.0  # setup: Staryu lines first; engine via Poffin later
                cap = 1 if (P8 and tc.going_second) else 2
                if tc.dus_in_play >= cap:
                    return 8.0
                line = (sum(tc.field_counts.get(f, 0) for f in FEEDER_BASICS)
                        + sum(tc.field_counts.get(a, 0) for a in MAIN_ATTACKERS))
                # Poffin plan: Staryu+Duskull (not Staryu+Staryu) once a line is down
                return 45.0 if (tc.dus_in_play == 0 and line >= 1) else 38.0
            return 30.0 - tc.field_counts.get(cid, 0) * 10
        return 20.0 if O.is_basic_pokemon(cid) else 5.0

    # --- taking a card to hand (Ultra Ball / Poffin / Hilda / Pokegear search) ---
    if context == SelectContext.TO_HAND:
        return _to_hand_value(tc, cid)

    # --- discarding from hand (Ultra Ball cost, etc.): higher = more willing ---
    if context in (SelectContext.DISCARD, SelectContext.TO_DECK, SelectContext.TO_DECK_BOTTOM,
                   SelectContext.DISCARD_CARD_OR_ATTACHED_CARD, SelectContext.DISCARD_ENERGY,
                   SelectContext.DISCARD_ENERGY_CARD, SelectContext.DISCARD_TOOL_CARD):
        return _discard_willingness(tc, cid)

    # --- healing / removing damage: prefer our valuable damaged Pokemon ---
    if context in (SelectContext.HEAL, SelectContext.REMOVE_DAMAGE_COUNTER):
        if mine and is_poke:
            dmg = getattr(card, "maxHp", card.hp) - card.hp
            return dmg + (pokemon_score(card) if cid in MAIN_ATTACKERS else 0)
        return 0.0

    # --- attaching (effect asks which Pokemon / which card) ---
    if context in (SelectContext.ATTACH_FROM, SelectContext.EFFECT_TARGET, SelectContext.EVOLVES_TO):
        if mine and is_poke:
            s = 10.0
            if cid in MAIN_ATTACKERS:
                s += 100
            elif cid == STARYU:
                s += 40
            return s + (len(card.energies) if hasattr(card, "energies") else 0)
        return 1.0

    if context == SelectContext.TO_PRIZE:
        # put least-useful cards to prize
        return -_to_hand_value(tc, cid)

    # default: keep/pick Pokemon and energy over filler
    if is_poke:
        return 30.0
    if O.is_energy(cid):
        return 20.0
    return 10.0


def _to_hand_value(tc, cid):
    """How much we want this card in hand (search/draw targets)."""
    if cid in MAIN_ATTACKERS:
        return 300.0 if tc.field_counts.get(cid, 0) == 0 else 120.0
    if DK and cid in WALL_IDS:
        # CR: Hilda/search should assemble the wall line before generic Pokemon
        return 260.0 if tc.field_counts.get(cid, 0) == 0 else 80.0
    if cid in FEEDER_BASICS:
        in_play = (sum(tc.field_counts.get(f, 0) for f in FEEDER_BASICS)
                   + sum(tc.field_counts.get(a, 0) for a in MAIN_ATTACKERS))
        return 200.0 if in_play < 2 else 60.0
    if P5 and cid in (DUSCLOPS, DUSKNOIR):
        # live engine piece once a Dus* body is in play (WD fetches ~600 of these)
        return 160.0 if tc.dus_in_play > 0 else 85.0
    if P4 and cid == IGNITION_ENERGY:
        # Nebula fuel: outranks W while a Mega is in play; low value before that
        mega = any(tc.field_counts.get(a, 0) for a in MAIN_ATTACKERS)
        if R3 and mega and _tank_race_on(tc):
            return 175.0  # tank race: every turn is a Nebula turn -- Ignition is fuel #1
        return 150.0 if mega else 80.0
    if B5 and _cw() and O.is_energy(cid):
        # B5 fetch order: Mist >= Spiky/Grow >= basic G (636 one-way TO_HAND flips;
        # Mist is the scarce protective resource, the single basic G stays in the
        # deck as emergency Superb Scissors fuel)
        if cid == MIST_ENERGY:
            return 168.0
        if cid == SPIKY_ENERGY:
            return 142.0
        if cid == GROW_GRASS:
            return 138.0
        if cid == BASIC_G:
            return 108.0
    if B6 and _cw() and cid in (XEROSIC, LILLIE_DET, HILDA, BOSS_ORDERS):
        # B6 Pokegear/search pick order (Budew's Pokegear picks: Xerosic 724 >
        # Lillie 667 > Hilda 417 > Boss 204; ours took Hilda over Xerosic x261)
        if cid == XEROSIC:
            return 158.0 if tc.op.handCount >= 6 else 126.0
        if cid == LILLIE_DET:
            return 118.0
        if cid == HILDA:
            # Lever 3(b): thin accessible Crustle supply raises the refetch pick
            # priority above Xerosic (158.0) -- reassembling the wall line outranks
            # generic hand disruption when supply is scarce.
            return 175.0 if _supply_rule_active(tc) else 112.0
        return 106.0
    if O.is_basic_pokemon(cid):
        return 150.0
    if cid in PRIMARY_ENERGIES:
        if T4:
            # T4: exact scarcity -- when (nearly) all remaining copies could be the
            # last unprized ones, fetching energy outranks everything but attackers
            t = _trk()
            try:
                if t is not None and t.our_remaining(cid) <= 2:
                    return 170.0
            except Exception:
                pass
        return 140.0
    if cid in (CARMINE, JUDGE, LILLIE_DET, HILDA):
        return 110.0
    if O.is_energy(cid):
        return 100.0
    if O.is_pokemon(cid):
        return 90.0
    return 70.0 - tc.hand_counts.get(cid, 0) * 20.0


def _discard_willingness(tc, cid):
    """Higher = more willing to discard. Protect the attacker line, pitch excess.
    P0/P4 invert the WD-observed order: pitch redundant trainers first, keep
    W + Ignition (they pitch Ultra Ball/Wally dupes, we used to pitch energy)."""
    if B5 and _cw():
        # B5 hand economy (their DISCARD profile, 94% disagreement: pitch spare
        # energy / dupe Pokemon, PROTECT Jumbo/Switch/Boss/Cape)
        if cid in (JUMBO_ICE, SWITCH_ITEM, BOSS_ORDERS, HEROS_CAPE):
            return -80.0
        if (cid == KANGASKHAN_M and tc.hand_counts.get(KANGASKHAN_M, 0) >= 2
                and tc.field_counts.get(KANGASKHAN_M, 0) >= 1):
            return 35.0   # a 3rd+ Kang copy is a mill-safe pitch
        if cid in (SPIKY_ENERGY, GROW_GRASS) and tc.hand_counts.get(cid, 0) >= 3:
            return 55.0   # spare special-energy dupes go first (Mist never listed)
    if cid in MAIN_ATTACKERS or cid in FEEDER_BASICS:
        return -200.0
    if DK and cid in WALL_IDS:
        return -150.0  # CR: never pitch the wall line
    if P5 and cid in (DUSCLOPS, DUSKNOIR) and tc.dus_in_play > 0:
        return -60.0  # live engine piece
    if cid in PRIMARY_ENERGIES:
        # keep at least a couple for attacks
        extra = tc.hand_counts.get(cid, 0) - 1
        if T4:
            t = _trk()
            try:
                if t is not None:
                    rem = t.our_remaining(cid)   # deck (exact) / deck+prizes (bound)
                    if rem + extra <= 1:
                        return -120.0            # the last usable copies: never pitch
                    if (extra > 0 and rem >= 6
                            and t.our_prize_known() is not None):
                        return 60.0              # provably plentiful: pitch dups first
            except Exception:
                pass
        return 40.0 if extra > 0 else -30.0
    if cid == IGNITION_ENERGY:
        if P4:
            mega_live = (any(tc.field_counts.get(a, 0) for a in MAIN_ATTACKERS)
                         or any(tc.hand_counts.get(a, 0) for a in MAIN_ATTACKERS))
            return -40.0 if mega_live else 100.0  # Nebula fuel vs cheapest pitch
        return 60.0
    if O.is_basic_energy(cid):
        return 50.0
    dup = tc.hand_counts.get(cid, 0)
    if dup >= 2:
        return 90.0 if P0 else 80.0
    if O.is_pokemon(cid):
        return -20.0
    if P0 and O.is_item(cid):
        return 55.0  # single redundant trainer before any energy
    return 30.0
