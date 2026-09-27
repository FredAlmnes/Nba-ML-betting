# NBA Value Betting Bot

Et personlig papir-trading-prosjekt for NBA moneyline-betting. En kalibrert
XGBoost-modell anslår vinnersannsynlighet for hver kamp. Anslaget sammenlignes
med bookmaker-oddsen fra [The Odds API](https://the-odds-api.com), og kamper der
modellen mener bookmakeren tar feil blir flagget som *value bets*. Bets der en
nøkkelspiller trolig er skadet filtreres bort, og innsatsen settes med halvt
Kelly mot en virtuell bankroll.

Ingen ekte penger er involvert. Boten spiller bare på papiret til en ordentlig
backtest viser positiv ROI.

> **Status (v1.0):** Walk-forward-backtesten fungerer. Den låste 2024-25-holdouten
> ga ROI -25,0 % (95 % KI [-64,5 %, +24,6 %]) på bare 19 bets, altså et
> **uavklart** resultat. Strategien er ikke validert.

---

## Hvordan det henger sammen

```
nba_api ──► 01_hent_data ──► 02_feature_engineering ──► 03_tren_modell ──► nba_modell.pkl
                                                                               │
The Odds API ──► odds.py ──► verdi_deteksjon.py ──► skadefilter.py ◄───────────┘
                                         │
                                         ▼
                                    06_bot.py  (daglig, via run_daglig.sh)
                                         │
                   ┌─────────────────────┼────────────────────────┐
                   ▼                     ▼                        ▼
            bankroll.json            bets.json           public/index.html ──► Vercel
```

| Fil | Rolle |
|---|---|
| `01_hent_data.py` | Henter historiske kampdata fra `nba_api` → `nba_kamper_raw.csv` |
| `02_feature_engineering.py` | Rullende 10-kampers snitt med `shift(1)` (lekkasjesikkert) → `nba_features.csv` |
| `03_tren_modell.py` | Trener XGBoost + isotonisk kalibrering på disjunkte tren/kalibrer/test-slicer → `nba_modell.pkl` |
| `06_bot.py` | Daglig bot: gjør opp gårsdagens bets, finner og plasserer nye, skriver dashboardet |
| `07_hent_historisk_odds.py` | Engangs-backfill av historiske odds til `odds_arkiv.db` (SQLite) |
| `08_kjor_backtest.py` | Walk-forward-backtest mot arkiverte odds, med en holdout-sperre som bare kan brukes én gang |
| `config.py` | Strategiparametrene: value-terskel, oddsgrenser, Kelly-fraksjon, innsatsgrenser, startkapital |
| `features.py`, `model.py`, `strategy.py`, `teams.py`, `odds.py`, `verdi_deteksjon.py`, `skadefilter.py`, `spillerlogg.py`, `kalibrering.py` | Delt kjerne som brukes av både live-boten og backtesten |
| `backtest.py`, `metrics.py` | Backtest-motoren og rapporteringen (ROI, win rate, drawdown, CLV, bootstrap/Wilson-KI) |
| `run_daglig.sh` | launchd-wrapper: kjører boten og deployer dashboardet til Vercel |

---

## Oppsett

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env   # legg inn ODDS_API_NOKKEL
```

Bygg data og modell (første gang):

```bash
python 01_hent_data.py
python 02_feature_engineering.py
python 03_tren_modell.py
```

Kjør boten:

```bash
python 06_bot.py
```

Mer om de enkelte stegene, backtesten og holdout-regelen står i
[KOMME_I_GANG.md](KOMME_I_GANG.md).

### Tester

```bash
pytest
```

---

## Dashboard på Vercel

Boten skriver dashboardet til `public/index.html`. Det er én statisk side med
bankroll og bets bakt inn, så Vercel trenger ingen build og ingen server.

Siden inneholder bet-historikken din og repoet er offentlig, så dashboardet
**går aldri via git** (`public/index.html` er git-ignorert). I stedet
deployer `run_daglig.sh` mappen `public/` rett fra maskinen med Vercel CLI
etter hver kjøring.

### Engangsoppsett

```bash
npm install -g vercel
vercel login
```

Koble `public/` til Vercel-prosjektet (lager `public/.vercel/`, som er git-ignorert):

```bash
cd public && vercel link --yes --project nba-ml-betting
```

Prosjektet skal **ikke** være koblet til GitHub-repoet. Da prøver Vercel å
bygge hele repoet som en Python-app, og bygget feiler. Er det koblet, fjern
koblingen med `vercel git disconnect`. Lager `vercel link` en `.env.local` i
`public/`, kan den slettes. Den trengs ikke, og `public/.vercelignore` holder
den uansett utenfor deployen.

Generer dashboardet og gjør første produksjons-deploy:

```bash
python 06_bot.py && (cd public && vercel deploy --prod)
```

Etter dette deployer `run_daglig.sh` automatisk hver dag. Mangler
`vercel`-kommandoen eller `public/.vercel/`, hoppes deployen over, og det
står i `logs/run_daglig.log`. En feilet deploy endrer ikke botens exit-kode.

### Personvern

- `public/vercel.json` setter `X-Robots-Tag: noindex`, så søkemotorer ikke
  indekserer siden.
- Produksjons-URL-en er likevel åpen for alle som har lenken. Vil du ha
  innlogging foran, slå på *Deployment Protection* i Vercel-prosjektet
  (Settings → Deployment Protection). Merk at beskyttelse av
  produksjonsdomenet krever en betalt plan.

---

## Daglig kjøring (launchd)

`run_daglig.sh` startes av en launchd-jobb kl. 14:00. Den finner
prosjektmappen selv, bruker `./venv/bin/python3` og logger til
`logs/run_daglig.log`.

Plist-en ligger i `~/Library/LaunchAgents/com.fredalmnes.nba-betting-bot.plist`.
Stien i `ProgramArguments` må peke på `run_daglig.sh` der repoet faktisk ligger.
Flytter du repoet, oppdater stien og last jobben inn på nytt:

```bash
launchctl unload ~/Library/LaunchAgents/com.fredalmnes.nba-betting-bot.plist
```

```bash
launchctl load ~/Library/LaunchAgents/com.fredalmnes.nba-betting-bot.plist
```

---

## Hva ligger ikke i git

Data, modell og personlig tilstand er git-ignorert og må genereres lokalt:
`nba_kamper_raw.csv`, `nba_features.csv`, `nba_spillerlogg_raw.csv`,
`nba_modell.pkl`, `odds_arkiv.db`, `bankroll.json`, `bets.json`, `backtests/`,
`public/index.html`, `logs/` og `.env`.

---

⚠️ Dette er et læringsprosjekt. Ingen garanti for profitt. Spill ansvarlig.
