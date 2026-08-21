"""
STEG 6: Betting Bot
====================
Hoved-boten som kjører hele pipelinen daglig:

  1. Sjekker resultater av gårsdagens bets
  2. Oppdaterer bankroll
  3. Finner nye value bets for i dag
  4. Plasserer virtuelle bets (3% av bankroll, maks 150 kr)
  5. Genererer oppdatert dashboard.html

Kjør daglig:
  python 06_bot.py

Bankroll og historikk lagres i:
  - bankroll.json   (nåværende saldo + historikk)
  - bets.json       (alle plasserte bets)
"""

import json
import os
import subprocess
import sys
from datetime import datetime, date, timedelta
import pandas as pd
import time
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.static import teams
from config import KELLY_FRAKSJON, MAX_INNSATS, MIN_INNSATS, STARTKAPITAL

# -------------------------------------------------------
# Konfigurasjon
# -------------------------------------------------------
BANKROLL_FIL      = "bankroll.json"
BETS_FIL          = "bets.json"
DASHBOARD_FIL     = "dashboard.html"

# -------------------------------------------------------
# Hjelpefunksjoner for datalagring
# -------------------------------------------------------

def les_bankroll():
    if not os.path.exists(BANKROLL_FIL):
        data = {
            "saldo": STARTKAPITAL,
            "historikk": [{"dato": str(date.today()), "saldo": STARTKAPITAL}]
        }
        lagre_json(BANKROLL_FIL, data)
    return les_json(BANKROLL_FIL)

def les_bets():
    if not os.path.exists(BETS_FIL):
        lagre_json(BETS_FIL, [])
    return les_json(BETS_FIL)

def les_json(fil):
    with open(fil, "r", encoding="utf-8") as f:
        return json.load(f)

def lagre_json(fil, data):
    with open(fil, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# -------------------------------------------------------
# 1. Sjekk resultater av uavgjorte bets
# -------------------------------------------------------

def hent_kampresultat(hjemme_lag, borte_lag, kamp_dato):
    """
    Henter faktisk kampresultat fra NBA API.
    Returnerer 'hjemme', 'borte', eller None (ikke spilt ennå).
    """
    alle_lag = teams.get_teams()

    # Bygg oppslag: navn/kallenavn -> full lag-info (vi trenger både ID og forkortelse)
    lag_oppslag = {}
    for lag in alle_lag:
        lag_oppslag[lag["full_name"].lower()]   = lag
        lag_oppslag[lag["nickname"].lower()]     = lag
        lag_oppslag[lag["abbreviation"].lower()] = lag

    def finn_lag(navn):
        navn = navn.lower()
        if navn in lag_oppslag:
            return lag_oppslag[navn]
        for nøkkel, info in lag_oppslag.items():
            if nøkkel in navn or navn in nøkkel:
                return info
        return None

    hjemme_info = finn_lag(hjemme_lag)
    borte_info  = finn_lag(borte_lag)

    if not hjemme_info or not borte_info:
        return None

    # MATCHUP i NBA API er på formen "MIN vs. DET" eller "MIN @ DET"
    # Vi matcher på bortelagets FORKORTELSE, ikke fullt navn
    borte_abbr = borte_info["abbreviation"].lower()

    try:
        kamp_dt = datetime.strptime(kamp_dato, "%Y-%m-%d")
        # Søk ±3 dager – kamper registreres ikke alltid på nøyaktig bet-dato
        fra_dato_fmt = (kamp_dt - timedelta(days=1)).strftime("%m/%d/%Y")
        til_dato_fmt = (kamp_dt + timedelta(days=3)).strftime("%m/%d/%Y")

        finder = leaguegamefinder.LeagueGameFinder(
            team_id_nullable=hjemme_info["id"],
            date_from_nullable=fra_dato_fmt,
            date_to_nullable=til_dato_fmt,
            league_id_nullable="00"
        )
        df = finder.get_data_frames()[0]
        time.sleep(0.6)

        if df.empty:
            return None

        # Filtrer til kamper mot riktig motstander
        df = df[df["MATCHUP"].str.lower().str.contains(borte_abbr)]
        if df.empty:
            return None

        # Foretrekk hjemmekamp (vs.) siden betten er lagret som "Hjemme vs Borte"
        hjemme_kamper = df[df["MATCHUP"].str.contains(r"vs\.", case=False)]
        rad = hjemme_kamper.iloc[0] if not hjemme_kamper.empty else df.iloc[0]

        # "vs." → hjemmelaget sin WL-kolonne = hjemmekampens resultat
        er_hjemmekamp = bool(hjemme_kamper.empty is False and rad.equals(hjemme_kamper.iloc[0]))
        return "hjemme" if rad["WL"] == "W" else "borte"

    except Exception:
        return None

    return None


def sjekk_resultater(bets, bankroll_data):
    """Oppdaterer uavgjorte bets med faktiske resultater."""
    endringer = False
    ny_saldo  = bankroll_data["saldo"]

    for bet in bets:
        if bet["status"] != "venter":
            continue

        # Ikke sjekk bets der kampen er i dag eller fremover (ikke spilt ennå)
        sjekk_dato = bet.get("kamp_dato") or bet["dato"]
        if sjekk_dato >= str(date.today()):
            continue

        # Bruk faktisk kampdato om tilgjengelig, ellers bet-dato
        oppslag_dato = bet.get("kamp_dato") or bet["dato"]
        print(f"  Sjekker resultat: {bet['kamp']} (kampdato: {oppslag_dato})...")
        deler       = bet["kamp"].split(" vs ")
        hjemme_navn = deler[0].strip()
        borte_navn  = deler[1].strip()

        vinner = hent_kampresultat(hjemme_navn, borte_navn, oppslag_dato)

        if vinner is None:
            print(f"    Ingen resultat funnet ennå")
            continue

        # Bestem om vi vant
        bet_side = "hjemme" if "Hjemme" in bet["bet"] else "borte"
        vant     = (bet_side == vinner)

        if vant:
            gevinst         = round(bet["innsats"] * bet["odds"] - bet["innsats"], 2)
            bet["status"]   = "vant"
            bet["gevinst"]  = gevinst
            ny_saldo       += gevinst
            print(f"    ✅ VANT! +{gevinst:.0f} kr")
        else:
            bet["status"]   = "tapte"
            bet["gevinst"]  = -bet["innsats"]
            ny_saldo       -= 0  # Innsatsen er allerede trukket ved plassering
            print(f"    ❌ Tapte. -{bet['innsats']:.0f} kr")

        endringer = True

    if endringer:
        bankroll_data["saldo"] = round(ny_saldo, 2)
        # Legg til historikkpunkt for i dag
        if not any(h["dato"] == str(date.today()) for h in bankroll_data["historikk"]):
            bankroll_data["historikk"].append({
                "dato": str(date.today()),
                "saldo": round(ny_saldo, 2)
            })

    return bets, bankroll_data


# -------------------------------------------------------
# 2. Beregn innsats med halvt Kelly-kriteriet
# -------------------------------------------------------

def beregn_innsats(saldo, modell_prob, odds):
    """
    Halvt Kelly-kriteriet:
      f* = (b*p - q) / b   der b = odds-1, p = modellsannsynlighet, q = 1-p
      innsats = saldo * f* * KELLY_FRAKSJON

    Halvt Kelly gir lavere varians enn fullt Kelly, på bekostning av
    litt lavere forventet vekst. Anbefaltes bredt i sportsbetting.
    """
    b = odds - 1.0          # netto gevinst per krone satset
    p = modell_prob
    q = 1.0 - p

    kelly = (b * p - q) / b

    if kelly <= 0:
        return 0.0          # Negativt Kelly = ingen edge, ikke bett

    innsats = saldo * kelly * KELLY_FRAKSJON
    innsats = max(MIN_INNSATS, min(MAX_INNSATS, innsats))
    return round(innsats, 2)


# -------------------------------------------------------
# 3. Kjør pipeline og plasser bets
# -------------------------------------------------------

def kjør_pipeline():
    """Kjører 04 og 05 for å få dagens value bets med skadefilter."""
    print("Kjører value detector...")
    env = os.environ.copy()
    venv_site = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "lib", "python3.10", "site-packages")
    env["PYTHONPATH"] = venv_site + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run([sys.executable, "04_value_detector.py"],
                            capture_output=True, text=True, env=env)
    if result.returncode != 0:
        print(f"  Feil i 04_value_detector.py:\n{result.stderr[-500:]}")
        return None

    print("Kjører skadefilter...")
    result = subprocess.run([sys.executable, "05_skadefilter.py"],
                            capture_output=True, text=True, env=env)
    if result.returncode != 0:
        print(f"  Feil i 05_skadefilter.py:\n{result.stderr[-500:]}")
        return None

    if not os.path.exists("value_bets_med_skadefilter.csv"):
        return None

    df = pd.read_csv("value_bets_med_skadefilter.csv")
    ok = df[df["Skadestatus"].str.contains("OK")]
    return ok if not ok.empty else None


def plasser_bets(value_bets_df, bets, bankroll_data):
    """Plasserer virtuelle bets for dagens kamper."""
    saldo    = bankroll_data["saldo"]
    nye_bets = 0
    # Dedup mot HELE bet-historikken (ikke bare dagens dato) – nøkkelen inkluderer
    # kamp_dato slik at vi aldri bet på samme fysiske kamp to ganger, uansett når
    # boten kjørte. Dette er sikkerhetsnettet mot at en gammel/stale rad fra
    # pipelinen (bug fikset 2026-08-19) blir bettet på nytt.
    allerede_bettet = {
        (b["kamp"], b["bet"], b.get("kamp_dato") or b["dato"]) for b in bets
    }

    for _, rad in value_bets_df.iterrows():
        kamp_dato_rad = rad["KampDato"] if "KampDato" in rad and pd.notna(rad["KampDato"]) else str(date.today())
        nøkkel = (rad["Kamp"], rad["Bet"], kamp_dato_rad)

        if nøkkel in allerede_bettet:
            print(f"  ⏭️  Allerede bettet tidligere – hopper over: {rad['Bet']} ({kamp_dato_rad})")
            continue  # Ikke bett to ganger på samme kamp, uansett dato

        if kamp_dato_rad < str(date.today()):
            print(f"  ⏭️  Kampen er allerede spilt ({kamp_dato_rad}) – trolig stale data, hopper over: {rad['Bet']}")
            continue  # Ikke bett på en kamp som allerede er avviklet

        modell_prob = float(rad["Modell_prob"]) if "Modell_prob" in rad and pd.notna(rad["Modell_prob"]) else 0.55
        innsats = beregn_innsats(saldo, modell_prob, float(rad["Odds"]))

        if innsats == 0.0:
            print(f"  ⏭️  Ingen edge (Kelly=0) – hopper over: {rad['Bet']}")
            continue

        if saldo - innsats < MIN_INNSATS * 2:
            print(f"  ⚠️  Bankroll for lav til å bette ({saldo:.0f} kr)")
            break

        saldo -= innsats  # Trekk innsatsen med en gang

        # Bruk faktisk kampdato fra Odds API om tilgjengelig, ellers dagens dato
        kamp_dato = rad["KampDato"] if "KampDato" in rad and pd.notna(rad["KampDato"]) else str(date.today())

        nytt_bet = {
            "dato":        str(date.today()),   # datoen boten kjørte
            "kamp_dato":   kamp_dato,           # faktisk spilledato fra Odds API
            "kamp":        rad["Kamp"],
            "bet":         rad["Bet"],
            "odds":        float(rad["Odds"]),
            "innsats":     innsats,
            "modell":      rad["Modell %"],
            "modell_prob": modell_prob,         # rå sannsynlighet brukt i Kelly
            "value":       rad["Value"],
            "ev":          rad["Forv. EV"],
            "status":      "venter",
            "gevinst":     None
        }
        bets.append(nytt_bet)
        nye_bets += 1

        print(f"  🎯 Bet plassert: {rad['Bet']} @ {rad['Odds']} – {innsats:.0f} kr")

    bankroll_data["saldo"] = round(saldo, 2)
    return bets, bankroll_data, nye_bets


# -------------------------------------------------------
# 4. Generer HTML-dashboard
# -------------------------------------------------------

def generer_dashboard(bets, bankroll_data):
    """Genererer en selvforsynt HTML-fil med alt av data innbakt."""

    historikk_json = json.dumps(bankroll_data["historikk"])
    bets_json      = json.dumps(bets)
    saldo          = bankroll_data["saldo"]
    startkapital   = STARTKAPITAL
    total_pnl      = round(saldo - startkapital, 2)
    roi            = round((saldo / startkapital - 1) * 100, 1)

    avsluttede = [b for b in bets if b["status"] in ("vant", "tapte")]
    vunnet     = [b for b in avsluttede if b["status"] == "vant"]
    win_rate   = round(len(vunnet) / len(avsluttede) * 100, 1) if avsluttede else 0

    roi_farge   = "#00d97e" if roi >= 0 else "#ff4d4d"
    pnl_prefix  = "+" if total_pnl >= 0 else ""
    roi_prefix  = "+" if roi >= 0 else ""
    win_pct     = win_rate / 100
    total_bets  = len(bets)
    venter_bets = len([b for b in bets if b["status"] == "venter"])

    html = f"""<!DOCTYPE html>
<html lang="no">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bankroll Tracker</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg:     #07080c;
      --s1:     #0d0f18;
      --s2:     #131620;
      --border: rgba(255,255,255,.06);
      --text:   #e2e5f0;
      --dim:    #4a5070;
      --green:  #00d97e;
      --red:    #ff4d4d;
      --orange: #ff6a1f;
      --blue:   #4b9eff;
    }}

    html {{ scroll-behavior: smooth; }}
    body {{
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      -webkit-font-smoothing: antialiased;
      overflow-x: hidden;
    }}

    /* ── HERO ── */
    #hero {{
      position: relative;
      height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      background: #07080c;
    }}
    #three-canvas {{
      position: absolute;
      inset: 0;
      width: 100% !important;
      height: 100% !important;
    }}
    #hero-content {{
      position: relative;
      z-index: 2;
      text-align: center;
      pointer-events: none;
      user-select: none;
    }}
    .hero-eyebrow {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .18em;
      text-transform: uppercase;
      color: var(--orange);
      margin-bottom: 22px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      opacity: 0;
      animation: fadeUp .8s .2s forwards;
    }}
    .hero-eyebrow::before, .hero-eyebrow::after {{
      content: '';
      width: 28px; height: 1px;
      background: var(--orange);
      opacity: .5;
    }}
    .hero-title {{
      font-size: clamp(52px, 9vw, 108px);
      font-weight: 900;
      letter-spacing: -.05em;
      line-height: .9;
      color: #fff;
      margin-bottom: 28px;
      opacity: 0;
      animation: fadeUp .8s .35s forwards;
    }}
    .hero-bankroll {{
      font-size: clamp(18px, 2.5vw, 28px);
      font-weight: 300;
      letter-spacing: -.01em;
      color: rgba(255,255,255,.45);
      margin-bottom: 6px;
      opacity: 0;
      animation: fadeUp .8s .5s forwards;
    }}
    .hero-change {{
      font-size: 15px;
      font-weight: 600;
      margin-bottom: 64px;
      opacity: 0;
      animation: fadeUp .8s .6s forwards;
    }}
    .hero-change.up   {{ color: var(--green); }}
    .hero-change.down {{ color: var(--red); }}
    .scroll-cue {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 10px;
      opacity: 0;
      animation: fadeUp .8s .8s forwards;
    }}
    .scroll-cue span {{
      font-size: 10px;
      letter-spacing: .14em;
      text-transform: uppercase;
      color: var(--dim);
    }}
    .scroll-chevron {{
      width: 20px; height: 20px;
      border-right: 2px solid var(--dim);
      border-bottom: 2px solid var(--dim);
      transform: rotate(45deg);
      animation: bounce 1.8s ease-in-out infinite;
    }}
    @keyframes bounce {{
      0%, 100% {{ transform: rotate(45deg) translate(0,0); opacity: 1; }}
      50%       {{ transform: rotate(45deg) translate(4px,4px); opacity: .4; }}
    }}
    @keyframes fadeUp {{
      from {{ opacity: 0; transform: translateY(20px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}

    /* ── DASHBOARD ── */
    #dash {{
      position: relative;
      z-index: 1;
      background: var(--bg);
    }}
    .dash-header {{
      position: relative;
      overflow: hidden;
      padding: 48px 40px 40px;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(150deg, #120a1e 0%, #0d0f18 55%);
    }}
    .dash-header::after {{
      content: '';
      position: absolute;
      top: -120px; right: -120px;
      width: 500px; height: 500px;
      background: radial-gradient(circle, rgba(255,106,31,.1) 0%, transparent 65%);
      pointer-events: none;
    }}
    .header-inner {{
      max-width: 1080px;
      margin: 0 auto;
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 24px;
    }}
    .logo {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .1em;
      text-transform: uppercase;
      color: var(--dim);
      margin-bottom: 20px;
    }}
    .logo-dot {{
      width: 6px; height: 6px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 8px var(--green);
      animation: pulse 2.5s ease-in-out infinite;
    }}
    @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.2}} }}
    .bankroll-lbl {{
      font-size: 11px;
      font-weight: 600;
      color: var(--dim);
      text-transform: uppercase;
      letter-spacing: .09em;
      margin-bottom: 8px;
    }}
    .bankroll-num {{
      font-size: 52px;
      font-weight: 800;
      letter-spacing: -.04em;
      line-height: 1;
    }}
    .bankroll-pill {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      margin-top: 12px;
      padding: 5px 14px;
      border-radius: 99px;
      font-size: 13px;
      font-weight: 600;
    }}
    .pill-up   {{ background: rgba(0,217,126,.1);  color: var(--green); }}
    .pill-down {{ background: rgba(255,77,77,.1);   color: var(--red);   }}
    .hstats {{ display: flex; gap: 36px; padding-bottom: 6px; }}
    .hstat-v {{ font-size: 24px; font-weight: 700; letter-spacing: -.02em; margin-top: 4px; }}
    .hstat-l {{ font-size: 11px; color: var(--dim); text-transform: uppercase; letter-spacing: .07em; }}
    .dash-main {{ max-width: 1080px; margin: 0 auto; padding: 28px 40px; }}
    .wr {{
      display: flex;
      align-items: center;
      gap: 20px;
      background: var(--s1);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px 22px;
      margin-bottom: 18px;
    }}
    .wr-lbl   {{ font-size: 12px; color: var(--dim); white-space: nowrap; }}
    .wr-track {{ flex: 1; height: 5px; background: var(--s2); border-radius: 99px; overflow: hidden; }}
    .wr-fill  {{ height: 100%; border-radius: 99px; background: linear-gradient(90deg, var(--orange), var(--green)); transition: width 1s cubic-bezier(.4,0,.2,1); }}
    .wr-n     {{ font-size: 13px; font-weight: 600; white-space: nowrap; }}
    .wr-p     {{ font-size: 22px; font-weight: 800; margin-left: 8px; }}
    .panel {{
      background: var(--s1);
      border: 1px solid var(--border);
      border-radius: 12px;
      margin-bottom: 18px;
      overflow: hidden;
    }}
    .panel-hd {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 15px 22px;
      border-bottom: 1px solid var(--border);
    }}
    .panel-ttl {{ font-size: 13px; font-weight: 600; }}
    .panel-sub {{ font-size: 12px; color: var(--dim); }}
    #chart-wrap {{ padding: 20px 22px 10px; }}
    #chart      {{ width: 100%; height: 200px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    thead th {{
      padding: 10px 20px;
      font-size: 11px;
      font-weight: 500;
      color: var(--dim);
      text-transform: uppercase;
      letter-spacing: .07em;
      text-align: left;
    }}
    tbody td {{
      padding: 14px 20px;
      font-size: 13px;
      border-top: 1px solid var(--border);
      vertical-align: middle;
    }}
    tbody tr:hover td {{ background: rgba(255,255,255,.015); }}
    .match-main {{ font-weight: 500; font-size: 13px; }}
    .match-sub  {{ font-size: 11px; color: var(--dim); margin-top: 2px; }}
    .odds-tag {{
      display: inline-block;
      background: rgba(75,158,255,.1);
      color: var(--blue);
      font-size: 12px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 5px;
    }}
    .val-tag {{ font-size: 12px; font-weight: 600; color: var(--green); }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 3px 9px;
      border-radius: 99px;
      font-size: 11px;
      font-weight: 600;
    }}
    .bv {{ background: rgba(255,255,255,.06); color: var(--dim);   }}
    .bw {{ background: rgba(0,217,126,.1);    color: var(--green); }}
    .bl {{ background: rgba(255,77,77,.1);    color: var(--red);   }}
    .bdot {{ width: 4px; height: 4px; border-radius: 50%; background: currentColor; }}
    .r-pos {{ color: var(--green); font-weight: 600; }}
    .r-neg {{ color: var(--red);   font-weight: 600; }}
    .r-nil {{ color: var(--dim); }}
    #tip {{
      position: fixed;
      background: #1a1d2e;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 9px 14px;
      font-size: 12px;
      pointer-events: none;
      opacity: 0;
      transition: opacity .12s;
      z-index: 999;
      white-space: nowrap;
    }}
    @media (max-width: 640px) {{
      .dash-header, .dash-main {{ padding-left: 20px; padding-right: 20px; }}
      .bankroll-num {{ font-size: 38px; }}
      .hstats {{ gap: 20px; }}
    }}
  </style>
</head>
<body>

<!-- ══ HERO ══ -->
<div id="hero">
  <canvas id="three-canvas"></canvas>
  <div id="hero-content">
    <div class="hero-eyebrow">NBA Betting Bot</div>
    <h1 class="hero-title">Bankroll<br>Tracker</h1>
    <div class="hero-bankroll">{saldo:,.0f} kr nåværende saldo</div>
    <div class="hero-change {'up' if total_pnl >= 0 else 'down'}">{'↑' if total_pnl >= 0 else '↓'} {pnl_prefix}{total_pnl:.0f} kr siden oppstart</div>
    <div class="scroll-cue">
      <span>Scroll</span>
      <div class="scroll-chevron"></div>
    </div>
  </div>
</div>

<!-- ══ DASHBOARD ══ -->
<div id="dash">
  <div class="dash-header">
    <div class="header-inner">
      <div>
        <div class="logo">
          <span>🏀</span><span>Bankroll Tracker</span>
          <span class="logo-dot"></span>
        </div>
        <div class="bankroll-lbl">Nåværende bankroll</div>
        <div class="bankroll-num">{saldo:,.0f} kr</div>
        <span class="bankroll-pill {'pill-up' if total_pnl >= 0 else 'pill-down'}">{'↑' if total_pnl >= 0 else '↓'} {pnl_prefix}{total_pnl:.0f} kr</span>
      </div>
      <div class="hstats">
        <div>
          <div class="hstat-l">ROI</div>
          <div class="hstat-v" style="color:{roi_farge}">{roi_prefix}{roi}%</div>
        </div>
        <div>
          <div class="hstat-l">Bets</div>
          <div class="hstat-v">{total_bets}</div>
        </div>
        <div>
          <div class="hstat-l">Venter</div>
          <div class="hstat-v" style="color:var(--dim)">{venter_bets}</div>
        </div>
      </div>
    </div>
  </div>

  <div class="dash-main">
    <div class="wr">
      <span class="wr-lbl">Win rate</span>
      <div class="wr-track"><div class="wr-fill" id="wr-fill" style="width:0"></div></div>
      <span class="wr-n">{len(vunnet)}/{len(avsluttede)}</span>
      <span class="wr-p" style="color:{'var(--green)' if win_rate >= 50 else 'var(--red)'}">{win_rate}%</span>
    </div>

    <div class="panel">
      <div class="panel-hd">
        <span class="panel-ttl">Bankroll-utvikling</span>
        <span class="panel-sub">Start: {startkapital:,.0f} kr</span>
      </div>
      <div id="chart-wrap"><div id="chart"></div></div>
    </div>

    <div class="panel">
      <div class="panel-hd">
        <span class="panel-ttl">Bets</span>
        <span class="panel-sub">{total_bets} totalt · {venter_bets} venter</span>
      </div>
      <table>
        <thead><tr>
          <th>Dato</th><th>Kamp</th><th>Odds</th>
          <th>Innsats</th><th>Value</th><th>Status</th><th>Resultat</th>
        </tr></thead>
        <tbody id="bet-body"></tbody>
      </table>
    </div>
  </div>
</div>

<div id="tip"></div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const historikk = {historikk_json};
const bets      = {bets_json};
const START     = {startkapital};

/* ══ WIN RATE BAR ══ */
setTimeout(() => {{
  document.getElementById('wr-fill').style.width = '{win_pct*100:.1f}%';
}}, 150);

/* ══ THREE.JS BASKETBALL ══ */
(function() {{
  const canvas   = document.getElementById('three-canvas');
  const renderer = new THREE.WebGLRenderer({{ canvas, antialias: true, alpha: true }});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);
  renderer.setSize(window.innerWidth, window.innerHeight);

  const scene  = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, window.innerWidth / window.innerHeight, 0.1, 100);
  camera.position.z = 5;

  scene.add(new THREE.AmbientLight(0xffffff, 0.3));
  const key = new THREE.DirectionalLight(0xff9955, 1.4);
  key.position.set(4, 5, 4);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0x3366ff, 0.25);
  fill.position.set(-4, -3, 2);
  scene.add(fill);
  const rim = new THREE.DirectionalLight(0xffffff, 0.2);
  rim.position.set(0, -4, -4);
  scene.add(rim);

  const tc = document.createElement('canvas');
  tc.width = 1024; tc.height = 512;
  const tx = tc.getContext('2d');

  const baseGrad = tx.createRadialGradient(350, 180, 20, 512, 256, 580);
  baseGrad.addColorStop(0,   '#f07020');
  baseGrad.addColorStop(0.4, '#d05010');
  baseGrad.addColorStop(1,   '#8a2800');
  tx.fillStyle = baseGrad;
  tx.fillRect(0, 0, 1024, 512);

  for (let i = 0; i < 6000; i++) {{
    const px = Math.random() * 1024;
    const py = Math.random() * 512;
    tx.fillStyle = `rgba(0,0,0,${{(Math.random() * 0.06).toFixed(3)}})`;
    tx.beginPath();
    tx.arc(px, py, Math.random() * 2.5, 0, Math.PI * 2);
    tx.fill();
  }}

  tx.strokeStyle = '#180600';
  tx.lineWidth   = 13;
  tx.lineCap     = 'round';

  tx.beginPath();
  for (let x = 0; x <= 1024; x++) {{
    const y = 256 + Math.sin(x / 1024 * Math.PI * 2) * 115;
    x === 0 ? tx.moveTo(x, y) : tx.lineTo(x, y);
  }}
  tx.stroke();

  tx.beginPath();
  for (let x = 0; x <= 1024; x++) {{
    const y = 256 - Math.sin(x / 1024 * Math.PI * 2) * 115;
    x === 0 ? tx.moveTo(x, y) : tx.lineTo(x, y);
  }}
  tx.stroke();

  [0, 512, 1024].forEach(xi => {{
    tx.beginPath();
    tx.moveTo(xi, 0);
    tx.lineTo(xi, 512);
    tx.stroke();
  }});

  const texture = new THREE.CanvasTexture(tc);
  const geo = new THREE.SphereGeometry(1.35, 64, 64);
  const mat = new THREE.MeshPhongMaterial({{
    map:       texture,
    shininess: 55,
    specular:  new THREE.Color(0x441100),
  }});
  const ball = new THREE.Mesh(geo, mat);
  scene.add(ball);

  window.addEventListener('resize', () => {{
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
  }});

  let scrollY = 0;
  window.addEventListener('scroll', () => {{ scrollY = window.scrollY; }});

  let t = 0;
  (function tick() {{
    requestAnimationFrame(tick);
    t += 0.006;
    ball.rotation.y = t;
    ball.rotation.x = Math.sin(t * 0.25) * 0.15;

    const heroH = window.innerHeight;
    const prog  = Math.min(scrollY / heroH, 1);
    const ease  = prog * prog * (3 - 2 * prog);

    ball.position.x =  ease * 2.8;
    ball.position.y = -ease * 2.2;
    const sc = 1 - ease * 0.45;
    ball.scale.set(sc, sc, sc);

    renderer.render(scene, camera);
  }})();
}})();

/* ══ TABELL ══ */
const tbody = document.getElementById('bet-body');
if (!bets.length) {{
  tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:48px;color:var(--dim);font-size:13px">Ingen bets ennå.</td></tr>`;
}} else {{
  [...bets].reverse().forEach(b => {{
    const [hjemme, borte] = b.kamp.split(' vs ');
    const erH  = b.bet.includes('Hjemme');
    const lag  = erH ? hjemme.trim() : borte.trim();
    const mot  = erH ? borte.trim()  : hjemme.trim();
    const resH = b.gevinst === null ? `<span class="r-nil">–</span>`
               : b.gevinst  >= 0    ? `<span class="r-pos">+${{b.gevinst.toFixed(0)}} kr</span>`
               :                      `<span class="r-neg">${{b.gevinst.toFixed(0)}} kr</span>`;
    const bc = b.status==='vant' ? 'bw' : b.status==='tapte' ? 'bl' : 'bv';
    const bl = b.status==='vant' ? 'Vant' : b.status==='tapte' ? 'Tapte' : 'Venter';
    tbody.innerHTML += `<tr>
      <td style="color:var(--dim);font-size:12px">${{b.dato.slice(5)}}</td>
      <td><div class="match-main">${{lag}}</div><div class="match-sub">vs ${{mot}}</div></td>
      <td><span class="odds-tag">${{b.odds.toFixed(2)}}</span></td>
      <td style="font-size:13px">${{b.innsats.toFixed(0)}} kr</td>
      <td><span class="val-tag">${{b.value}}</span></td>
      <td><span class="badge ${{bc}}"><span class="bdot"></span>${{bl}}</span></td>
      <td>${{resH}}</td>
    </tr>`;
  }});
}}

/* ══ GRAF ══ */
const chartEl = document.getElementById('chart');
const tip     = document.getElementById('tip');

if (historikk.length < 2) {{
  chartEl.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:200px;color:var(--dim);font-size:13px">Kjør boten noen dager for å se kurven.</div>`;
}} else {{
  const W  = chartEl.offsetWidth || 960;
  const H  = 200;
  const p  = {{t:10, r:6, b:28, l:48}};
  const iW = W-p.l-p.r, iH = H-p.t-p.b;
  const n  = historikk.length;
  const vs = historikk.map(h => h.saldo);
  const lo = Math.min(...vs, START) * 0.96;
  const hi = Math.max(...vs, START) * 1.04;
  const xS = i => p.l + i/(n-1)*iW;
  const yS = v => p.t + iH - (v-lo)/(hi-lo)*iH;

  const pts = historikk.map((h,i) => [xS(i), yS(h.saldo)]);
  let d = `M${{pts[0][0]}},${{pts[0][1]}}`;
  for (let i=1; i<pts.length; i++) {{
    const [x0,y0]=pts[i-1], [x1,y1]=pts[i], cx=(x0+x1)/2;
    d += ` C${{cx}},${{y0}} ${{cx}},${{y1}} ${{x1}},${{y1}}`;
  }}
  const area = d + ` L${{p.l+iW}},${{p.t+iH}} L${{p.l}},${{p.t+iH}}Z`;
  const isUp = historikk[n-1].saldo >= START;
  const clr  = isUp ? '#00d97e' : '#ff4d4d';
  const sy   = yS(START);

  let grid='', ylbl='', xlbl='';
  [0,.25,.5,.75,1].forEach(tt => {{
    const v=lo+tt*(hi-lo), y=yS(v);
    grid += `<line x1="${{p.l}}" y1="${{y}}" x2="${{p.l+iW}}" y2="${{y}}" stroke="rgba(255,255,255,.04)"/>`;
    ylbl += `<text x="${{p.l-5}}" y="${{y+4}}" text-anchor="end" font-size="10" fill="#4a5070">${{Math.round(v)}}</text>`;
  }});
  const stp = Math.max(1, Math.ceil(n/5));
  for (let i=0; i<n; i+=stp)
    xlbl += `<text x="${{xS(i)}}" y="${{H-3}}" text-anchor="middle" font-size="10" fill="#4a5070">${{historikk[i].dato.slice(5)}}</text>`;

  chartEl.innerHTML = `
    <svg width="100%" viewBox="0 0 ${{W}} ${{H}}" style="overflow:visible">
      <defs>
        <linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stop-color="${{clr}}" stop-opacity=".2"/>
          <stop offset="100%" stop-color="${{clr}}" stop-opacity="0"/>
        </linearGradient>
      </defs>
      ${{grid}}${{ylbl}}${{xlbl}}
      <line x1="${{p.l}}" y1="${{sy}}" x2="${{p.l+iW}}" y2="${{sy}}"
            stroke="rgba(255,255,255,.1)" stroke-dasharray="4 3" stroke-width="1"/>
      <path d="${{area}}" fill="url(#ag)"/>
      <path d="${{d}}" fill="none" stroke="${{clr}}" stroke-width="2.5" stroke-linecap="round"/>
      ${{pts.map(([x,y],i) => `
        <circle class="pt" cx="${{x}}" cy="${{y}}" r="12" fill="transparent" data-i="${{i}}"/>
        <circle cx="${{x}}" cy="${{y}}" r="3.5" fill="${{clr}}" stroke="var(--s1)" stroke-width="2"/>
      `).join('')}}
    </svg>`;

  chartEl.querySelectorAll('.pt').forEach(pt => {{
    pt.addEventListener('mouseenter', e => {{
      const h=historikk[+e.target.dataset.i], pnl=h.saldo-START;
      tip.innerHTML=`<div style="color:var(--dim);margin-bottom:4px">${{h.dato}}</div>
        <div style="font-weight:700;font-size:15px">${{h.saldo.toFixed(0)}} kr
        <span style="color:${{pnl>=0?'var(--green)':'var(--red)'}};font-size:12px;margin-left:8px">${{pnl>=0?'+':''}}${{pnl.toFixed(0)}} kr</span></div>`;
      tip.style.opacity='1';
    }});
    pt.addEventListener('mousemove', e => {{
      tip.style.left=(e.clientX+14)+'px';
      tip.style.top=(e.clientY-48)+'px';
    }});
    pt.addEventListener('mouseleave', () => tip.style.opacity='0');
  }});
}}
</script>
</body>
</html>"""

    with open(DASHBOARD_FIL, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  Dashboard generert: {DASHBOARD_FIL}")


# -------------------------------------------------------
# HOVED-PROGRAM
# -------------------------------------------------------

def main():
    print("=" * 60)
    print(f"NBA BETTING BOT – {date.today()}")
    print("=" * 60)

    # Last inn tilstand
    bankroll_data = les_bankroll()
    bets          = les_bets()

    print(f"\nNåværende bankroll: {bankroll_data['saldo']:.0f} kr")
    print(f"Totalt plasserte bets: {len(bets)}")

    # 1. Sjekk resultater av tidligere bets
    # Bruk kamp_dato (faktisk spilledato) om tilgjengelig, ellers dato (dag boten kjørte).
    # Sjekk bare bets der kampen allerede er spilt (dvs. dato < i dag).
    venter = [b for b in bets if b["status"] == "venter"
              and (b.get("kamp_dato") or b["dato"]) < str(date.today())]
    if venter:
        print(f"\n--- Sjekker {len(venter)} uavgjorte bets ---")
        bets, bankroll_data = sjekk_resultater(bets, bankroll_data)
    else:
        print("\nIngen uavgjorte bets å sjekke.")

    # 2. Kjør pipeline
    print("\n--- Kjører value-pipeline ---")
    value_bets = kjør_pipeline()

    # 3. Plasser bets
    if value_bets is not None and not value_bets.empty:
        print(f"\n--- Plasserer bets (bankroll: {bankroll_data['saldo']:.0f} kr) ---")
        bets, bankroll_data, nye = plasser_bets(value_bets, bets, bankroll_data)
        print(f"  {nye} nye bet(s) plassert")
    else:
        print("\nIngen godkjente value bets i dag.")

    # 4. Legg til bankroll-historikk for i dag
    if not any(h["dato"] == str(date.today()) for h in bankroll_data["historikk"]):
        bankroll_data["historikk"].append({
            "dato": str(date.today()),
            "saldo": bankroll_data["saldo"]
        })

    # 5. Lagre og generer dashboard
    lagre_json(BANKROLL_FIL, bankroll_data)
    lagre_json(BETS_FIL, bets)

    print("\n--- Genererer dashboard ---")
    generer_dashboard(bets, bankroll_data)

    # Oppsummering
    avsluttede = [b for b in bets if b["status"] in ("vant", "tapte")]
    vunnet     = [b for b in avsluttede if b["status"] == "vant"]
    pnl        = round(bankroll_data["saldo"] - STARTKAPITAL, 2)
    roi        = round((bankroll_data["saldo"] / STARTKAPITAL - 1) * 100, 1)

    print(f"""
{'='*60}
OPPSUMMERING
{'='*60}
Bankroll:    {bankroll_data['saldo']:.0f} kr  (start: {STARTKAPITAL:.0f} kr)
P&L:         {'+' if pnl >= 0 else ''}{pnl:.0f} kr
ROI:         {'+' if roi >= 0 else ''}{roi}%
Win rate:    {len(vunnet)}/{len(avsluttede)} bets
{'='*60}
Åpne dashboard.html i nettleseren for full oversikt!
""")


if __name__ == "__main__":
    main()
