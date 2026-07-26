/* crn_shim.c -- COMMON RANDOM NUMBERS shim for the PTCG engine (local eval ONLY).
 *
 * Problem (intel/agent_v9_results.md item 6): battle-mode engine RNG is unseeded --
 * ApiBattleStart hardcodes config.deviceRand=true and every shuffle/coin/hidden-order
 * draw constructs a fresh std::random_device temporary (CardMove.h shuffle,
 * SelectProc.h coins, EffectInstant.h ToDeckBottomClose). No exported entry point
 * accepts a seed, so n=300 rows swing +/-5-7pp and single seeds +/-3pp on the 20-row
 * aggregate -- while the effects we chase are ~1-3pp.
 *
 * Fix (the PokeForge "interpose the native shuffle" approach, forum t724187, 4.88x
 * variance reduction for near-clones): libcg.so does NOT define the out-of-line
 * std::random_device members -- it imports them from libstdc++.so.6:
 *     U _ZNSt13random_device7_M_initERKNSt7__cxx1112basic_string...   (ctor)
 *     U _ZNSt13random_device9_M_getvalEv                              (operator())
 *     U _ZNSt13random_device7_M_finiEv                                (dtor)
 * (glibc's libstdc++ would serve these from RDRAND on this CPU, so libc-level
 * getrandom/urandom interposition would NOT work -- interpose the libstdc++ symbols
 * themselves.) Loading this shim with RTLD_GLOBAL *before* libcg.so is dlopened makes
 * the dynamic linker bind those imports here: 100% of battle randomness then flows
 * through one seedable stream. An unversioned definition satisfies the versioned
 * (@GLIBCXX_3.4.18/.21) references -- standard interposition rule.
 *
 * Two streams (splitmix64):
 *   BATTLE stream -- active only while the harness holds PtcgCrnMode(1), i.e. inside
 *     battle_start()/battle_select(). Reseeded per game via PtcgCrnSetSeed(f(seed0,g))
 *     so arm A and arm B of an A/B replay the SAME stochastic worlds (same opening
 *     shuffles, prizes, coins) game-for-game.
 *   FREE stream -- everything else (the one AgentStart() draw that seeds the search
 *     API's internal mt19937, or any other stray consumer). Seeded from getrandom()
 *     unless PTCG_CRN_FREE_SEED is set (set it for full-transcript determinism runs).
 *     Kept separate so per-agent differences in search usage can never shift the
 *     battle stream and break pairing.
 *
 * The search API's own randomness is mt19937 (ApiAgentStart: deviceRand=false), seeded
 * ONCE per process from a single random_device draw -- it does NOT hit this shim per
 * step, so interposition cost during search is zero.
 *
 * Build (WSL):   gcc -shared -fPIC -O2 -o crn_shim.so crn_shim.c
 * Use:           via agent/tools/gauntlet.py --crn (default ON), which dlopens the
 *                compiled .so RTLD_GLOBAL before the engine loads. Never ships in a
 *                submission tarball; the compiled artifact is git-ignored.
 *
 * Single-threaded by design (the harness is a sequential game loop). Not thread-safe.
 */
#include <stdint.h>
#include <stdlib.h>
#include <sys/random.h>

static uint64_t battle_state = 0xDEADBEEFCAFEF00DULL;
static uint64_t free_state;
static int battle_mode = 0;
static uint64_t battle_draws = 0;
static uint64_t free_draws = 0;

static uint64_t splitmix64(uint64_t *s) {
    uint64_t z = (*s += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

__attribute__((constructor))
static void crn_init(void) {
    const char *fs = getenv("PTCG_CRN_FREE_SEED");
    if (fs && *fs) {
        free_state = strtoull(fs, 0, 10) ^ 0xA5A5A5A55A5A5A5AULL;
    } else if (getrandom(&free_state, sizeof free_state, 0) != sizeof free_state) {
        free_state = 0x0123456789ABCDEFULL; /* last resort */
    }
}

/* ---- harness control API (ctypes) -------------------------------------- */
void PtcgCrnSetSeed(unsigned long long seed) {
    battle_state = seed;
    for (int i = 0; i < 4; i++) splitmix64(&battle_state); /* decorrelate small seeds */
}
void PtcgCrnMode(int on) { battle_mode = on; }
unsigned long long PtcgCrnBattleDraws(void) { return battle_draws; }
unsigned long long PtcgCrnFreeDraws(void) { return free_draws; }
int PtcgCrnPresent(void) { return 1; }

/* ---- std::random_device interposition (Itanium ABI mangled names) ------- */
/* std::random_device::_M_init(std::string const&): no-op -- no fd is opened,
 * _M_getval below never reads the object, _M_fini below never closes anything. */
void _ZNSt13random_device7_M_initERKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEE(
        void *self, const void *token) {
    (void)self; (void)token;
}
/* std::random_device::_M_fini(): no-op. */
void _ZNSt13random_device7_M_finiEv(void *self) { (void)self; }
/* std::random_device::_M_getval(): the single funnel for ALL battle randomness. */
unsigned int _ZNSt13random_device9_M_getvalEv(void *self) {
    (void)self;
    if (battle_mode) {
        battle_draws++;
        return (unsigned int)splitmix64(&battle_state);
    }
    free_draws++;
    return (unsigned int)splitmix64(&free_state);
}
