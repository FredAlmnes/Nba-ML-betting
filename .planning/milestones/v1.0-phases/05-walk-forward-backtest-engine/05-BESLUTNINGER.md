# Phase 5 — Låste beslutninger (Plan 05-01)

Dette dokumentet er den maskin-grep-bare kilden for de fire beslutningene som
Plan 05-01s blokkerende checkpoint krevde før noe Phase 5-kode kunne skrives.
Planene 05-07, 05-08 og 05-09 leser denne tabellen direkte — ikke
05-RESEARCH.md eller 05-CONTEXT.md — som autoritativ kilde for de låste
verdiene.

| ID | Beslutning | Låst verdi | Leses av |
|----|-----------|------------|----------|
| D-05-01 | Eksakt verdi av `HOLDOUT_START_DATO` | `"2024-10-01"` | Plan 05-07 (`_sikre_ikke_holdout`), Plan 05-09 (sweep-guard), Plan 05-10 (`--holdout` CLI-sti), Plan 05-13 (den ene holdout-kjøringen) |
| D-05-02 | Burn-in / tidlige-måneder rapporteringspolicy | Inkluder alle måneder i ledgeren; rapporter hovedtall to ganger — full periode OG ekskludert de første 2-3 månedene | Plan 05-08 (manifest-metrikkfelt), Plan 05-12 (human-verify-vurdering) |
| D-05-03 | Definisjon av "flat" i BT-07 Kelly-sweepen | En `backtest.py`-lokal gren: fast 2% av `config.STARTKAPITAL` (20.0 kr) per bet når sweepens fraksjons-label er "flat"; `strategy.py` er urørt | Plan 05-09 (sweepens fjerde rad) |
| D-05-04 | Disposisjon for scratch-artefakter og arbeidstre | Uendret, kun ignore (matcher Phase 1s D-08) | Plan 05-01 Task 3 (bekreftelse — styrer om `.gitignore`-endringen er den eneste repo-tilstandsendringen denne planen gjør) |

## Begrunnelser

**D-05-01.** `2024-10-01` er valgt fordi det er en ren kalendermånedsgrense
som er identisk i praksis med den faktiske sesongstarten 2024-10-22 — det
finnes null kamper i `nba_features.csv` mellom disse to datoene, så ingen
data forsvinner. En lesbar månedsgrense i koden og i manifestet slår en
"magisk" dato som må utledes på nytt hver gang `nba_features.csv`
regenereres. Fra og med denne datoen kan tallene kun leses gjennom
`kjor_endelig_holdout_backtest()` (BT-03) — én gang, ugjenkallelig for denne
milepælen.

**D-05-02.** Walk-forward-loopens første måneder trener på svært lite data
(1-2 ukers kamper), og Phase 3 viste allerede at et kalibreringssett på bare
172 rader ga dårligere log-loss enn ukalibrert på denne dataen — de tidligste
månedene er med andre ord kjent støyete. Å droppe dem ville skjult nettopp
det spørsmålet Phase 3s funn reiser; å beholde alt og rapportere to
hovedtall (full periode = hovedtall, ekskl. burn-in = sensitivitetssjekk)
koster nesten ingenting siden begge bare er ulike datofiltre over samme
cachede ledger.

**D-05-03.** `strategy.beregn_innsats` har ingen flat-modus i dag —
`kelly_fraksjon=0` returnerer 0.0 for hvert bet, ikke en flat innsats. En
ekte flat-stake-baseline skal isolere edge-skalering fra alt annet, så den
må være uavhengig av edge, odds og løpende saldo. Å legge dette som en gren
lokalt i `backtest.py` holder `strategy.py` — som deles med den live boten —
byte-identisk, og 20.0 kr sammenfaller bevisst med `config.MIN_INNSATS`,
slik at den flate armen er direkte sammenlignbar med Kelly-armenes gulv.

**D-05-04.** `_linux_pkgs/`, `_pip_tmp/`, `_pip_home/`, `_wheels/`,
`_test.bin`, `test_write.tmp` er fortsatt til stede på disk og fortsatt
kun gitignored, per Phase 1s D-08. Sletting er en destruktiv operasjon som
er helt utenfor denne fasens omfang og fortjener sin egen eksplisitte
beslutning — ikke en bieffekt av en backtest-fase. Dette holder Phase 5s
commits avgrenset til Phase 5s egne filer.
