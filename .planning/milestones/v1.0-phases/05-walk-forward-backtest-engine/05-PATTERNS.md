# Phase 5: Walk-Forward Backtest Engine - Pattern Map

**Mapped:** 2026-08-24
**Files analyzed:** 12 (7 new, 5 modified)
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|---------------|
| `model.py` (new) | service/model | batch (train/calibrate) | `03_tren_modell.py` (script logic) + `kalibrering.py` (split helper) + `modell_utils.py` (wrapper) | role-match (script logic must be extracted into module form) |
| `metrics.py` (new) | utility | transform/batch | `strategy.py` | exact (pure, zero-I/O, parameter-driven module) |
| `backtest.py` (new) | service/orchestrator | event-driven (date-walk loop) | `odds.py` (`kjor_backfill` loop) | role-match (closest existing "iterate dates, call sub-functions, accumulate counters, print summary" loop) |
| `08_kjor_backtest.py` (new) | route/CLI entry | request-response (CLI) | `07_hent_historisk_odds.py` | exact (newest numbered script, same `argparse` + thin-wrapper-calling-a-module convention) |
| `nba_spillerlogg_raw.csv` acquisition (new, likely a `spillerlogg.py` module + call site) | service (data ingestion) | batch/file-I/O | `01_hent_data.py` | role-match (same `nba_api` season-loop-to-CSV shape, player-level instead of team-level) |
| `skadefilter.py` (modified — add as-of function) | service | request-response (lookup) | `skadefilter.py` itself (`sjekk_lag_helse`/`hent_toppspillere_for_lag`) | exact (in-file sibling function, same module) |
| `config.py` (modified — add `HOLDOUT_START_DATO`) | config | — | `config.py` itself | exact (in-file addition) |
| `odds.py` (modified — add best-price-per-outcome helper) | service | CRUD (SQL query) | `odds.py` itself (`hent_unike_kampdatoer`, `er_allerede_arkivert`) | exact (in-file addition, same connection/parameterized-query style) |
| `tests/test_backtest.py` (new) | test | — | `tests/test_parity.py` + `tests/conftest.py` | role-match (new test file, but must reuse existing fixtures) |
| `tests/test_metrics.py` (new) | test | — | `tests/test_strategy.py` | exact (pure-function unit tests, no fixtures/mocks needed) |
| `tests/test_model.py` (new) | test | — | `tests/test_calibrering_split.py` | exact (chronological-split / training-window test shape) |
| `tests/test_skadefilter.py` (modified, NOT new — file already exists) | test | — | `tests/test_skadefilter.py` itself | exact (extend existing file, same injected-DataFrame no-network style) |
| `tests/test_parity.py` (modified — extend per its own docstring instruction) | test | — | `tests/test_parity.py` itself | exact (extend existing file) |

**Correction to task framing:** The orchestrator's file list says "new test files ... `tests/test_skadefilter.py`" — this file **already exists** (7,039 bytes, last modified 2026-08-23, read in full above). Phase 5 must **extend** it with as-of-aware test cases, not create it. Treat it as a modified file, analog = itself.

## Pattern Assignments

### `model.py` (new) — service/model, batch

**Analogs:** `03_tren_modell.py` (lines 1-233, the one-shot train/calibrate logic to extract), `kalibrering.py` (lines 15-45, the chronological-split helper), `modell_utils.py` (lines 1-22, the wrapper class to reuse unmodified).

**Module docstring / ownership pattern** (`kalibrering.py:1-10`):
```python
"""
Delt modul for kronologiske tren/kalibrer/test-grenser.

Denne modulen eier de kronologiske grensene som 03_tren_modell.py bruker
for å dele opp kampdataene i tre ikke-overlappende tidsvinduer...
Modulen holdes ren (ingen I/O, ingen prints) så den kan enhetstestes uten
å kjøre hele treningsskriptet.
"""
```
`model.py` should carry the same "I own X, importers are Y and Z, holds no I/O where possible" framing (RESEARCH.md's own Pattern 3 example at RESEARCH.md:216-240 already drafts this docstring style — reuse it directly).

**Core training pattern to extract** (`03_tren_modell.py:97-122`, XGBoost fit):
```python
modell = xgb.XGBClassifier(
    n_estimators=300, max_depth=4, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8,
    use_label_encoder=False, eval_metric="logloss",
    random_state=42, early_stopping_rounds=20
)
modell.fit(
    X_tren, y_tren,
    eval_set=[(X_kalibrer, y_kalibrer)],
    verbose=50
)
```
and calibration (`03_tren_modell.py:171-177`):
```python
y_rå_kalibrer = modell.predict_proba(X_kalibrer)[:, 1]
kalibrerer    = IsotonicRegression(out_of_bounds="clip")
kalibrerer.fit(y_rå_kalibrer, y_kalibrer)
```
then wrap via `modell_utils.KalibrertModell(modell, kalibrerer)` (`modell_utils.py:14-22`) — do not reimplement the wrapper, import it.

**Split-helper pattern to generalize** (`kalibrering.py:15-45`) — `del_kronologisk_3veis` already returns boolean masks from a date column with configurable month-offsets; `model.py`'s `as_of`-aware walk-forward path needs an analogous but *fraction-based* 2-way split (train/calibrate only, no held-out test — per RESEARCH.md Pattern 3). Reuse the boolean-mask-over-a-date-column idiom, not the month-offset math itself.

**Persistence pattern** (`03_tren_modell.py:225-229`):
```python
with open("nba_modell.pkl", "wb") as f:
    pickle.dump({
        "modell":           kalibrert_modell,
        "feature_kolonner": feature_kolonner
    }, f)
```
Dict-with-named-keys, never a bare model object — `model.py`'s save/load functions (if it persists intermediate walk-forward models at all) must follow this exact shape for consistency with `verdi_deteksjon.py::last_modell` (`verdi_deteksjon.py:77-81`), which already expects `data["modell"]`/`data["feature_kolonner"]`.

**No type hints, Norwegian names throughout** — `tren_mask`, `kalibrer_mask`, `X_tren`, `y_kalibrer` etc. `model.py`'s equivalents should be `tren()`/`kalibrer_andel`/`vindu` per RESEARCH.md's own drafted signature (RESEARCH.md:216-240), not renamed to English.

---

### `metrics.py` (new) — utility, transform/batch

**Analog:** `strategy.py` (full file, 100 lines) — the closest existing "pure functions, zero I/O, zero project imports, parameter-driven" module.

**Module docstring pattern** (`strategy.py:1-13`):
```python
"""
Delt strategi-kjerne for NBA betting-pipeline.

Rene funksjoner for vig-fjerning, value/EV-beregning, halvt Kelly-kriteriet
og bet-dedup-nøkler — ingen I/O, ingen global tilstand. ...

Modulen importerer bevisst INGENTING fra prosjektet (verken config.py eller
pandas) — konfigurasjonsverdier kommer inn som parametre til funksjonene.
Dette holder modulen fritt testbar med kant-verdier og import-syklus-fri.
"""
```
`metrics.py` should adopt the identical "commits to nothing project-specific" framing — bootstrap/Wilson/ROI/drawdown functions take arrays/parameters, never read `config.py` or touch disk. RESEARCH.md's Pattern 5 (RESEARCH.md:341-381) already provides ready-to-copy `bootstrap_roi_ci`/`wilson_ci` implementations that follow this exact docstring/no-import style — copy them near-verbatim.

**Docstring "why, not what" convention** (`strategy.py:48-59`, `beregn_innsats`):
```python
def beregn_innsats(saldo, modell_prob, odds, kelly_fraksjon, min_innsats, max_innsats):
    """
    Halvt Kelly-kriteriet:
      f* = (b*p - q) / b   der b = odds-1, p = modellsannsynlighet, q = 1-p
      innsats = saldo * f* * kelly_fraksjon

    Halvt Kelly gir lavere varians enn fullt Kelly, på bekostning av
    litt lavere forventet vekst. Anbefaltes bredt i sportsbetting.

    NB: min-klemmingen løfter selv en liten positiv edge OPP til
    min_innsats — overraskende, men bevisst og bevart fra originalen.
    """
```
`metrics.py`'s functions (`bootstrap_roi_ci`, `wilson_ci`, drawdown, CLV) should each carry a formula-plus-rationale docstring in this style, not a bare one-liner.

---

### `backtest.py` (new) — service/orchestrator, event-driven date-walk loop

**Analog:** `odds.py::kjor_backfill` (`odds.py:580-743`) — closest existing "iterate a date list, call sub-functions per date, accumulate a result-counter dict, print a summary block, tolerate per-item failure without aborting the whole run" pattern in the codebase.

**Result-dict-with-named-counters pattern** (`odds.py:631-639`):
```python
resultat = {
    "datoer_totalt": len(datoer),
    "hoppet_over": 0,
    "ville_hentet": 0,
    "kall": 0,
    "kreditt_brukt": 0,
    "nye_rader": 0,
    "avbrutt_grunn": None,
}
```
`backtest.py`'s `kjor_backtest()` should return an analogous dict (e.g. `datoer_totalt`, `kamper_hoppet_over_manglende_odds`, `bets_plassert`, `retreninger`) rather than only the ledger — mirrors Pitfall 2's explicit requirement to report a skip-count alongside the bet count.

**Per-item try/except that never aborts the whole run, but lets fatal errors propagate** (`odds.py:725-727`):
```python
except Exception as e:
    print(f"  FEIL for {dato}: {e} - fortsetter til neste dato")
    continue
```
Paired with the explicit comment (`odds.py:624-629`) that `SystemExit` is deliberately NOT caught here — same discipline `backtest.py` needs for the holdout guard's `HoldoutLaastFeil`, which must propagate, never be silently swallowed by a loop-level `except Exception`.

**Summary-block print pattern** (`odds.py:729-741`):
```python
print("=" * 60)
print("BACKFILL-OPPSUMMERING")
print("=" * 60)
print(f"Datoer totalt:  {resultat['datoer_totalt']}")
...
print("=" * 60)
```
`backtest.py`/`08_kjor_backtest.py` should print an equivalent `"=" * 60` banner summary after a run (matches CLAUDE.md's documented `"=" * 60` / `"─" * 50` section-header convention).

**Holdout-guard structural pattern** — no direct existing analog (this is genuinely new control-flow), but RESEARCH.md Pattern 4 (RESEARCH.md:294-332) already provides the exact code to copy:
```python
class HoldoutLaastFeil(Exception):
    """Reist når tuning-/sweep-kode prøver å evaluere en dato i det låste
    holdout-vinduet (BT-03). Dette er IKKE en advarsel — koden skal stoppe."""

def _sikre_ikke_holdout(dato, tillat_holdout=False):
    if not tillat_holdout and dato >= config.HOLDOUT_START_DATO:
        raise HoldoutLaastFeil(...)
```
This mirrors the codebase's only existing custom-exception-adjacent convention (there are none today — CLAUDE.md notes "No custom exception classes exist anywhere in the codebase" — so this is the first, and should stay minimal/single-purpose, not a broad exception hierarchy).

**Date-list source to reuse unmodified:** `odds.py::hent_unike_kampdatoer(features_fil, fra, til)` (`odds.py:543-577`) — already returns sorted, string-inclusive-range-filtered unique dates from `nba_features.csv`. `backtest.py` should call this directly for its walk-forward date iteration, not reimplement date extraction.

---

### `08_kjor_backtest.py` (new) — route/CLI entry point

**Analog:** `07_hent_historisk_odds.py` (full file, 154 lines) — the newest numbered script, and the one CONTEXT.md explicitly says to mirror ("matches Phase 4's D-05" importable-function-plus-`if __name__` pattern).

**Docstring banner pattern** (`07_hent_historisk_odds.py:1-26`):
```python
"""
STEG 7: Historisk odds-backfill (tørrkjøring som standard)
=============================================================
En engangs-/periodisk jobb som fyller det permanente SQLite-arkivet
(`odds_arkiv.db`) med historiske NBA-odds for hver unike kampdato i
`nba_features.csv` – grunnlaget Fase 5-backtesten skal stå på (ODDS-01).
...
"""
```
`08_kjor_backtest.py` should open with `"""\nSTEG 8: ...\n===...\n"""` — same numbered-step banner + `=` underline convention every script (01-07) uses.

**`argparse` + thin-wrapper-calling-a-module pattern** (`07_hent_historisk_odds.py:28-90, 93-153`):
```python
def bygg_parser():
    parser = argparse.ArgumentParser(description=(...))
    parser.add_argument("--snapshot-type", required=True, choices=[...], help="...")
    parser.add_argument("--maks-kreditt", required=True, type=int, help="...")
    parser.add_argument("--utfor", action="store_true", help="...")
    ...
    return parser

def main():
    args = bygg_parser().parse_args()
    print("=" * 60)
    ...
    resultat = odds.kjor_backfill(con, api_nokkel, datoer, args.snapshot_type, args.maks_kreditt, utfor=args.utfor)
    ...
    if resultat["avbrutt_grunn"]:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
```
`08_kjor_backtest.py` should follow this exact shape: a `bygg_parser()` function (if CLI flags are used — CONTEXT.md leaves this as Claude's Discretion, but if flags are added, this is the template), a `main()` that parses args, prints a banner, calls into `backtest.py`'s functions, and an `if __name__ == "__main__":` guard. Per Pattern 4's own guidance, `kjor_endelig_holdout_backtest()` must be invoked from a clearly separate, explicitly-named code path (e.g. a `--holdout` flag mirroring `--utfor`'s "opt-in, off by default" convention), never as the default action.

**Explicit-exit-code discipline** (`07_hent_historisk_odds.py:145-149`):
```python
if resultat["avbrutt_grunn"]:
    print(f"\nLøpet stoppet før alle datoer var behandlet: {resultat['avbrutt_grunn']}")
    sys.exit(1)
sys.exit(0)
```
`08_kjor_backtest.py` should exit non-zero on a failed/aborted run for the same reason CLAUDE.md documents everywhere else in this codebase: bare `exit()` returns exit code 0 and hides failure.

---

### `nba_spillerlogg_raw.csv` acquisition (new — recommend a small `spillerlogg.py` module, or a function inside `01_hent_data.py`)

**Analog:** `01_hent_data.py` (full file, 104 lines) — the existing `nba_api` season-loop-to-CSV script; RESEARCH.md's Pitfall 1 explicitly confirms the same call shape works with `player_or_team_abbreviation='P'`.

**Season-loop pattern to mirror** (`01_hent_data.py:29-51`):
```python
sesonger = ["2022-23", "2023-24", "2024-25"]
alle_kamper = []

for sesong in sesonger:
    print(f"\nHenter kamper for sesong {sesong}...")
    gamefinder = leaguegamefinder.LeagueGameFinder(
        season_nullable=sesong,
        league_id_nullable="00",
        season_type_nullable="Regular Season"
    )
    kamper_df = gamefinder.get_data_frames()[0]
    alle_kamper.append(kamper_df)
    print(f"  Fant {len(kamper_df)} rader (en rad per lag per kamp)")
    time.sleep(1)

df = pd.concat(alle_kamper, ignore_index=True)
```
The player-log fetch should follow the identical shape: loop over the same three seasons, call `leaguegamelog.LeagueGameLog(player_or_team_abbreviation='P', season=sesong, season_type_all_star="Regular Season")`, `time.sleep()` between calls (rate-limit courtesy, matches `01_hent_data.py:48`'s existing comment `"nba_api har rate limiting, så vi venter litt mellom kall"`), concat, write to `nba_spillerlogg_raw.csv` via `to_csv(filnavn, index=False)` (`01_hent_data.py:100-103`).

**Existing player-level API call precedent for signature/columns** — `skadefilter.py::hent_spillerdata` (`skadefilter.py:54-66`) already wraps a sibling player-stats endpoint (`leaguedashplayerstats`) with the identical try/except-returns-empty-DataFrame pattern:
```python
def hent_spillerdata(season_type, sesong, last_n=0):
    """Henter spillerdata for gitt season_type/sesong. Returnerer tom DataFrame ved feil."""
    try:
        df = leaguedashplayerstats.LeagueDashPlayerStats(
            season=sesong, season_type_all_star=season_type, last_n_games=last_n
        ).get_data_frames()[0]
        time.sleep(1.0)
        return df
    except Exception as e:
        print(f"  (Kunne ikke hente {season_type} data: {e})")
        return pd.DataFrame()
```
Reuse this "wrap the nba_api call in try/except, return empty DataFrame + printed error, never raise" convention for the new `leaguegamelog`-based fetch — consistent with the project's existing "skip-and-log" convention (CLAUDE.md, Error Handling section).

---

### `skadefilter.py` (modified — add `sjekk_lag_helse_som_of` / as-of variant)

**Analog:** the file's own existing `sjekk_lag_helse` (`skadefilter.py:151-173`) and `hent_toppspillere_for_lag` (`skadefilter.py:123-129`) — the new as-of function is a sibling in the same module, not a new file.

**Existing function to mirror closely** (`skadefilter.py:151-173`):
```python
def sjekk_lag_helse(siste3, sesong_snitt, team_id, lagnavn):
    """Sjekker et lags topp-N-spillere mot siste3-datasettet og returnerer en helsestatus-dict."""
    toppspillere = hent_toppspillere_for_lag(sesong_snitt, team_id, ANTALL_TOPPSPILLERE)
    resultat = {"lagnavn": lagnavn, "tilgjengelig": True, "advarsler": []}
    print(f"  {lagnavn}:")
    for sp in toppspillere:
        ok, melding = sjekk_spiller(siste3, sp["PLAYER_ID"], sp["PLAYER_NAME"], sp["MIN"])
        ikon = "✅" if ok else "⚠️ "
        print(f"    {ikon} {melding}")
        if not ok:
            resultat["tilgjengelig"] = False
            resultat["advarsler"].append(melding)
    ...
    return resultat
```
`sjekk_spiller` (`skadefilter.py:132-148`) is already pure/injectable and should be reused **unmodified** by the new as-of function — only the *data source* (live `siste3`/`sesong_snitt` DataFrames vs. a filtered historical player-log slice) changes, not the pass/fail rule itself. RESEARCH.md's Pattern 7 (RESEARCH.md:400-431) already drafts the concrete `sjekk_lag_helse_som_of` implementation — copy it, keeping the same return-dict shape (`lagnavn`/`tilgjengelig`/`advarsler`) so `backtest.py`'s ledger code can treat live and as-of results identically.

**Existing duplicated `gjeldende_sesong()` this phase should NOT touch, but must add a parallel date-driven version for** (`skadefilter.py:34-51`):
```python
def gjeldende_sesong():
    """... NB: denne funksjonen og gjeldende_sesong() i verdi_deteksjon.py ... er
    samme NBA-sesong-utledning, duplisert i to filer. ... Flagget som et
    konsolideringspunkt for Phase 5 ..."""
    år = _dt.now().year
    måned = _dt.now().month
    if måned >= 10:
        return f"{år}-{str(år + 1)[-2:]}"
    else:
        return f"{år - 1}-{str(år)[-2:]}"
```
The module's own docstring flags this as a Phase-5 concern. RESEARCH.md's `sesong_grenser_for_dato(dato)` (RESEARCH.md:508-523) is the as-of-safe replacement — a **new, additional** function (parameterized by `dato`, never `datetime.now()`), not a rewrite of `gjeldende_sesong()` itself (which the live path still needs unchanged).

---

### `config.py` (modified — add `HOLDOUT_START_DATO`)

**Analog:** `config.py` itself (`config.py:13-20`).

**Existing constant style to match exactly:**
```python
MIN_VALUE_TERSKEL = 0.05            # Flagg bets der vi er 5%+ over bookmaker
MIN_ODDS = 1.50                     # Ikke bett på favoritter med veldig lave odds
MAX_ODDS = 4.00                     # Ikke bett på store outsidere (over 4x = for usikkert)
```
Add `HOLDOUT_START_DATO = "2024-10-01"   # ...` with an inline trailing comment explaining the practical meaning (per CLAUDE.md's documented "Inline trailing comments annotate config constants with their practical meaning" convention) — string literal (no type hints, matches every other value in the file being a bare literal), placed near the other threshold constants, not in a separate section.

---

### `odds.py` (modified — add best-price-per-outcome helper, e.g. `hent_bet_time_pris`)

**Analog:** `odds.py` itself — `hent_unike_kampdatoer` (`odds.py:543-577`) and `er_allerede_arkivert` (`odds.py:119-130`) for the parameterized-SQL-query style.

**Parameterized query pattern to copy exactly** (`odds.py:126-130`):
```python
rad = con.execute(
    "SELECT 1 FROM odds_arkiv WHERE kamp_dato = ? AND snapshot_type = ? LIMIT 1",
    (kamp_dato, snapshot_type),
).fetchone()
return rad is not None
```
Always `?` placeholders, never string-formatted SQL (already flagged in RESEARCH.md's Security Domain as the mitigation already in place). RESEARCH.md's Pattern 2 (RESEARCH.md:249-278) provides the exact `hent_bet_time_pris()` implementation using `SELECT ... MAX(odds) ... GROUP BY utfall_navn` — copy it, since it already matches this file's existing docstring conventions (multi-paragraph rationale, explicit note on what the caller MUST do with a `(None, None)` return).

**Docstring-explains-the-caller-contract convention** (`odds.py:119-125`, `er_allerede_arkivert`):
```python
def er_allerede_arkivert(con, kamp_dato, snapshot_type):
    """
    True hvis arkivet allerede har minst én rad for (kamp_dato, snapshot_type).

    Dette kalles FØR nettverkskallet gjøres — det er selve kredittsparings-
    mekanismen (D-04), ikke "INSERT OR IGNORE" i arkiver_odds_rader().
    """
```
The new odds helper's docstring should explain not just what it returns but what the *caller* is obligated to do with a miss (skip, don't error) — matches this file's house style of documenting caller contracts inline, not just behavior.

---

### `tests/test_backtest.py` (new)

**Analogs:** `tests/test_parity.py` (fixture usage, determinism-testing style) + `tests/conftest.py` (shared synthetic-data fixtures to reuse, not duplicate).

**Fixture reuse, not reinvention** (`tests/conftest.py:64-91`): `kamper_df`, `fremtidige_kamper_df`, `as_of_dato` are already shared pytest fixtures with deterministic synthetic data (no `random`, no `datetime.now()`). `test_backtest.py` should import/reuse these via `conftest.py`'s auto-discovery rather than building a second synthetic-data generator — same principle `test_parity.py`'s own docstring states explicitly (`tests/test_parity.py:25-28`: *"Alt i denne filen er deterministisk... as_of-verdien kommer utelukkende fra as_of_dato-fixturen i tests/conftest.py, aldri fra klokken"*).

**No-network-call assertion pattern** (`tests/test_skadefilter.py:30-46`, reusable template for any new function that might accidentally hit `nba_api`):
```python
def test_import_skadefilter_gjor_ingen_nettverkskall(monkeypatch):
    from nba_api.stats.endpoints import leaguedashplayerstats
    def _sprengt(*args, **kwargs):
        raise AssertionError("... skal IKKE kalles ved import")
    monkeypatch.setattr(leaguedashplayerstats, "LeagueDashPlayerStats", _sprengt)
    modul = importlib.reload(skadefilter)
    assert modul is not None
```
`test_backtest.py` should apply the same pattern to prove `backtest.py`'s walk-forward loop never calls `odds.hent_live_odds`/`nba_api` mid-run (it should only read `odds_arkiv.db` and the precomputed features table) — monkeypatch the live-fetch entry points to raise, confirm the backtest run still completes.

**In-memory SQLite fixture pattern** (`tests/test_odds.py:47-49`):
```python
@pytest.fixture
def con():
    return odds.apne_arkiv(":memory:")
```
`test_backtest.py`'s tests that exercise the odds join should reuse this exact `:memory:`-SQLite-fixture idiom (via `odds.apne_arkiv(":memory:")` + `odds.arkiver_odds_rader(con, [...])` to seed rows) rather than depending on the real, 67MB `odds_arkiv.db`.

**Holdout-guard test target** (BT-03, per RESEARCH.md's Phase Requirements → Test Map, RESEARCH.md:616): assert `HoldoutLaastFeil` is raised for `kjor_backtest(..., tillat_holdout=False)` on any date `>= config.HOLDOUT_START_DATO`, and NOT raised when called via `kjor_endelig_holdout_backtest()`.

---

### `tests/test_metrics.py` (new)

**Analog:** `tests/test_strategy.py` (pure-function unit-test shape, e.g. `test_fjern_vigorish_summerer_til_en`, lines 60+) — no fixtures, no mocks, direct-call-and-assert against known values.

**Pattern to copy:**
```python
def test_fjern_vigorish_summerer_til_en():
    impl_hjemme, impl_borte = fjern_vigorish(1.90, 1.90)
    assert impl_hjemme == pytest.approx(0.5)
```
`test_metrics.py`'s `bootstrap_roi_ci`/`wilson_ci`/CLV/drawdown tests should follow this exact shape: call with hand-calculable synthetic values, assert with `pytest.approx`. `config_values`-style "snubletråd" (tripwire) tests (`tests/test_strategy.py`'s sibling `test_config.py`-style test in the same file, lines ~30-40) are a good precedent if `metrics.py` ends up with any tunable constant (e.g. default `n_resamples=1000`, `seed=42`) worth locking with an explicit test.

---

### `tests/test_model.py` (new)

**Analog:** `tests/test_calibrering_split.py` — chronological-split-boundary test shape (masks, date cutoffs, non-overlap assertions). Read via Grep-confirmed file presence; same directory, same naming convention (`test_<module>.py` mirrors `kalibrering.py`).

**Expected pattern (inferred from `kalibrering.py`'s own tested contract):** assert the three/two-way split masks (a) never overlap, (b) together cover all rows, (c) respect the `as_of` cutoff strictly (`<`, never `<=` — same leakage-safety discipline `test_parity.py::test_grenserad_paa_as_of_er_ekskludert` already enforces for `features.py`). `test_model.py` should add an equivalent boundary test for `model.py::tren(..., as_of=...)`.

---

### `tests/test_skadefilter.py` (existing file — extend, do not recreate)

**Analog:** itself. Existing injected-DataFrame-no-network pattern (`tests/test_skadefilter.py:119-145`):
```python
def test_filtrer_bets_for_skader_ingen_nettverkskall_og_bevarer_radantall(monkeypatch):
    """Med siste3/sesong_snitt injisert skal ingen nba_api-kall skje, og radantallet bevares."""
    from nba_api.stats.endpoints import leaguedashplayerstats
    def _sprengt(*args, **kwargs):
        raise AssertionError("Skal ikke kalle nba_api når siste3/sesong_snitt er injisert")
    monkeypatch.setattr(leaguedashplayerstats, "LeagueDashPlayerStats", _sprengt)
    ...
    resultat = filtrer_bets_for_skader(value_df, siste3=siste3, sesong_snitt=sesong_snitt)
    assert len(resultat) == len(value_df)
```
New as-of test cases (for `sjekk_lag_helse_som_of`) should follow this exact "inject a synthetic player-log DataFrame, assert no network call, assert the resulting availability dict" shape — matches RESEARCH.md's Wave 0 Gaps note (RESEARCH.md:632) verbatim: *"mirroring the existing siste3/sesong_snitt injection pattern already used for the live path."*

---

### `tests/test_parity.py` (existing file — extend per its own docstring instruction)

**Analog:** itself (`tests/test_parity.py:18-23`), which already contains an explicit forward-pointing instruction:
```python
NÅR BACKTEST-MOTOREN BYGGES I FASE 5, MÅ FØLGENDE LEGGES TIL: en test som
kjører backtest-repriseringen og live-veien side om side for én fast
historisk dato og kamp, og asserter at de to veiene produserer nøyaktig
samme bet-beslutning (samme flagg, samme value, samme EV, samme
innsats). Denne testfilen dekker kun halvparten av CORE-04s bokstavelige
krav — den andre halvparten er instruksjonen i dette avsnittet.
```
Copy `simuler_bet_beslutning` (`tests/test_parity.py:119-144`) as the "live-side" half of the new parity test, and drive the "backtest-side" half through `backtest.py`'s actual per-game decision function for the same fixed historical date/game — assert identical `(bet_flagget, value, ev, innsats)` tuples, same style as `test_identisk_bet_beslutning_fra_to_kallsteder` (`tests/test_parity.py:147-187`).

---

## Shared Patterns

### No type hints, Norwegian snake_case naming
**Source:** every existing module (`features.py`, `strategy.py`, `odds.py`, `skadefilter.py`, `03_tren_modell.py`)
**Apply to:** all 7 new files. No `def tren(features_df: pd.DataFrame, as_of: str | None = None):` — plain `def tren(features_df, as_of=None):`. Function/variable names in Norwegian (`tren`, `kjor_backtest`, `hent_bet_time_pris`, `sesong_grenser_for_dato`), English only for third-party library/API field names (`GAME_DATE_HJEMME`, `PLAYER_ID`, `MIN` stay as the API returns them).

### Docstring style: "why, not what" + explicit caller contracts
**Source:** `strategy.py`, `odds.py`, `features.py` module/function docstrings throughout
**Apply to:** every new function in `backtest.py`, `metrics.py`, `model.py`, `skadefilter.py`'s new function, `odds.py`'s new function. Docstrings explain the formula/rationale and, where relevant, what a `None`/empty return means for the caller (e.g. "skip the game, don't error" for a missing odds snapshot) — not merely restate the signature.

### Numbered section-comment banners + `"=" * 60` print banners
**Source:** every numbered script (`01_hent_data.py`, `02_feature_engineering.py`, `07_hent_historisk_odds.py`), CLAUDE.md's documented Comments/Logging conventions
**Apply to:** `08_kjor_backtest.py` (script-level `# --- N. ... ---` banners) and any CLI summary output in `backtest.py`/`08_kjor_backtest.py` (`"=" * 60` before/after major output blocks).

### `if __name__ == "__main__":` guard + importable functions, no top-level side-effecting code
**Source:** `07_hent_historisk_odds.py:152-153` (`if __name__ == "__main__": main()`), and the Phase-4-established convention that replaced the old top-level-code anti-pattern (CLAUDE.md's own documented Anti-Pattern: "Top-level module code instead of functions/`main()`")
**Apply to:** `08_kjor_backtest.py` (mandatory), and `model.py`/`backtest.py`/`metrics.py`/`skadefilter.py`'s new additions (no module-level I/O or network calls on import — matches `skadefilter.py`'s own explicit design note at lines 10-14 about why the old `05_skadefilter.py` had to be refactored away from this exact anti-pattern).

### `as_of` strict-`<` filtering convention (leakage safety)
**Source:** `features.py::beregn_lag_form` (`features.py:51-52`, `df_raw = df_raw[df_raw["GAME_DATE_HJEMME"] < as_of]`)
**Apply to:** `model.py::tren(..., as_of=...)`, `skadefilter.py`'s new as-of function, and any date-boundary filtering inside `backtest.py`. Always strict `<`, never `<=` — the codebase already has one regression test (`tests/test_parity.py::test_grenserad_paa_as_of_er_ekskludert`) guarding exactly this off-by-one risk in `features.py`; new as-of code should be held to the same standard and get its own equivalent boundary test.

### Skip-and-log for missing/unresolvable data, never silently substitute
**Source:** `04_value_detector.py`/`verdi_deteksjon.py`'s `if not hjemme_id or not borte_id: continue` (`verdi_deteksjon.py:120-122`), `skadefilter.py`'s `if not team_id: continue` (`skadefilter.py:216-218`)
**Apply to:** `backtest.py`'s odds-join miss handling (Pitfall 2 — skip the game, count it, never treat a missing `bet_time` snapshot as "no value") and any unresolvable team-name/player lookup inside the new injury-filter or player-log code.

### Parameterized SQL, never string-formatted
**Source:** `odds.py` throughout (`er_allerede_arkivert`, `arkiver_odds_rader`, `hent_unike_kampdatoer`)
**Apply to:** the new `odds.py::hent_bet_time_pris` helper — always `?` placeholders with a tuple of bound values, per the Security Domain note in RESEARCH.md (already the established, unbroken convention in this file).

## No Analog Found

None. Every file in this phase's scope has at least a role-match or exact analog somewhere in the existing codebase (RESEARCH.md itself already did most of this mapping work at the architecture level — this document translates that into concrete file-by-file code excerpts).

## Metadata

**Analog search scope:** repo root (`*.py`), `tests/` — all 24 top-level Python files and 11 existing test files read or grepped directly; no `Glob`/`Grep` search returned files outside this set relevant to the new modules (flat repo structure, no `src/`/`controllers/`/`services/` subdirectories exist — confirmed via `ls -la` at repo root).
**Files scanned:** `features.py`, `strategy.py`, `odds.py`, `config.py`, `teams.py`, `modell_utils.py`, `kalibrering.py`, `03_tren_modell.py`, `02_feature_engineering.py`, `01_hent_data.py`, `07_hent_historisk_odds.py`, `verdi_deteksjon.py`, `skadefilter.py`, `05_skadefilter.py`, `06_bot.py` (function index only), `tests/conftest.py`, `tests/test_parity.py`, `tests/test_skadefilter.py`, `tests/test_strategy.py`, `tests/test_odds.py` (header), `.gitignore`.
**Pattern extraction date:** 2026-08-24

---
*Phase: 5-Walk-Forward Backtest Engine*
*Patterns mapped: 2026-08-24*
