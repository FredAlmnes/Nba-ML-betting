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

# -------------------------------------------------------
# Konfigurasjon
# -------------------------------------------------------
STARTKAPITAL      = 1000.0   # kr
INNSATS_PROSENT   = 0.03     # 3% av bankroll per bet
MAX_INNSATS       = 150.0    # Aldri mer enn 150 kr på ett bet
MIN_INNSATS       = 20.0     # Aldri mindre enn 20 kr
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
    lag_oppslag = {lag["full_name"]: lag["id"] for lag in alle_lag}
    lag_oppslag.update({lag["nickname"]: lag["id"] for lag in alle_lag})

    # Finn hjemmelagets ID
    hjemme_id = None
    for nøkkel, tid in lag_oppslag.items():
        if nøkkel.lower() in hjemme_lag.lower() or hjemme_lag.lower() in nøkkel.lower():
            hjemme_id = tid
            break

    if not hjemme_id:
        return None

    try:
        finder = leaguegamefinder.LeagueGameFinder(
            team_id_nullable=hjemme_id,
            date_from_nullable=kamp_dato,
            date_to_nullable=kamp_dato,
            league_id_nullable="00"
        )
        df = finder.get_data_frames()[0]
        time.sleep(0.6)

        if df.empty:
            return None  # Kampen ikke spilt ennå

        # Finn kamp mot riktig motstander
        for _, rad in df.iterrows():
            if borte_lag.lower().split()[-1] in rad["MATCHUP"].lower():
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

        # Ikke sjekk bets fra i dag (kampen er ikke spilt ennå)
        if bet["dato"] == str(date.today()):
            continue

        print(f"  Sjekker resultat: {bet['kamp']} ({bet['dato']})...")
        deler       = bet["kamp"].split(" vs ")
        hjemme_navn = deler[0].strip()
        borte_navn  = deler[1].strip()

        vinner = hent_kampresultat(hjemme_navn, borte_navn, bet["dato"])

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
# 2. Beregn innsats
# -------------------------------------------------------

def beregn_innsats(saldo):
    innsats = saldo * INNSATS_PROSENT
    innsats = max(MIN_INNSATS, min(MAX_INNSATS, innsats))
    return round(innsats, 2)


# -------------------------------------------------------
# 3. Kjør pipeline og plasser bets
# -------------------------------------------------------

def kjør_pipeline():
    """Kjører 04 og 05 for å få dagens value bets med skadefilter."""
    print("Kjører value detector...")
    result = subprocess.run([sys.executable, "04_value_detector.py"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  Feil i 04_value_detector.py:\n{result.stderr[-500:]}")
        return None

    print("Kjører skadefilter...")
    result = subprocess.run([sys.executable, "05_skadefilter.py"],
                            capture_output=True, text=True)
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
    saldo          = bankroll_data["saldo"]
    nye_bets       = 0
    allerede_i_dag = {b["kamp"] + b["bet"] for b in bets if b["dato"] == str(date.today())}

    for _, rad in value_bets_df.iterrows():
        nøkkel = rad["Kamp"] + rad["Bet"]
        if nøkkel in allerede_i_dag:
            continue  # Ikke bett to ganger på samme kamp

        innsats = beregn_innsats(saldo)

        if saldo - innsats < MIN_INNSATS * 2:
            print(f"  ⚠️  Bankroll for lav til å bette ({saldo:.0f} kr)")
            break

        saldo -= innsats  # Trekk innsatsen med en gang

        nytt_bet = {
            "dato":    str(date.today()),
            "kamp":    rad["Kamp"],
            "bet":     rad["Bet"],
            "odds":    float(rad["Odds"]),
            "innsats": innsats,
            "modell":  rad["Modell %"],
            "value":   rad["Value"],
            "ev":      rad["Forv. EV"],
            "status":  "venter",
            "gevinst": None
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

    pnl_klasse    = "green" if total_pnl >= 0 else "red"
    roi_klasse    = "green" if roi >= 0 else "red"
    saldo_klasse  = "green" if saldo >= startkapital else "red"
    pnl_prefix    = "+" if total_pnl >= 0 else ""
    roi_prefix    = "+" if roi >= 0 else ""

    html = f"""<!DOCTYPE html>
<html lang="no">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NBA Bet Tracker</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg:        #0d0f14;
      --surface:   #13161f;
      --border:    #1e2130;
      --muted:     #3d4460;
      --text:      #c9cfe0;
      --text-dim:  #5a6380;
      --green:     #34d399;
      --green-bg:  rgba(52,211,153,.1);
      --red:       #f87171;
      --red-bg:    rgba(248,113,113,.1);
      --blue:      #60a5fa;
      --blue-bg:   rgba(96,165,250,.08);
      --accent:    #6366f1;
    }}

    body {{
      font-family: 'Inter', -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
    }}

    /* ── NAV ── */
    nav {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 32px;
      height: 56px;
      border-bottom: 1px solid var(--border);
      background: var(--surface);
    }}
    .nav-brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 700;
      font-size: 15px;
      letter-spacing: -.01em;
    }}
    .nav-brand .dot {{
      width: 8px; height: 8px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 8px var(--green);
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; }}
      50%       {{ opacity: .4; }}
    }}
    .nav-date {{
      font-size: 13px;
      color: var(--text-dim);
    }}

    /* ── LAYOUT ── */
    .page {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px; }}

    /* ── CARDS ── */
    .cards {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-bottom: 24px;
    }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 18px 20px;
      position: relative;
      overflow: hidden;
    }}
    .card::before {{
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 2px;
    }}
    .card.green::before {{ background: var(--green); }}
    .card.red::before   {{ background: var(--red); }}
    .card.blue::before  {{ background: var(--blue); }}
    .card.purple::before {{ background: var(--accent); }}
    .card-label {{
      font-size: 11px;
      font-weight: 500;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: .07em;
      margin-bottom: 10px;
    }}
    .card-value {{
      font-size: 26px;
      font-weight: 700;
      letter-spacing: -.02em;
      line-height: 1;
    }}
    .card-value.green  {{ color: var(--green); }}
    .card-value.red    {{ color: var(--red); }}
    .card-value.blue   {{ color: var(--blue); }}
    .card-value.purple {{ color: var(--accent); }}
    .card-sub {{
      font-size: 12px;
      color: var(--text-dim);
      margin-top: 6px;
    }}

    /* ── PANEL ── */
    .panel {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      margin-bottom: 20px;
      overflow: hidden;
    }}
    .panel-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 20px;
      border-bottom: 1px solid var(--border);
    }}
    .panel-title {{
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
      letter-spacing: -.01em;
    }}
    .panel-body {{ padding: 20px; }}

    /* ── CHART ── */
    #chart {{ width: 100%; height: 240px; }}

    /* ── TABLE ── */
    table {{ width: 100%; border-collapse: collapse; }}
    thead th {{
      padding: 10px 16px;
      font-size: 11px;
      font-weight: 500;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: .06em;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    tbody td {{
      padding: 13px 16px;
      font-size: 13px;
      border-bottom: 1px solid var(--border);
      color: var(--text);
      vertical-align: middle;
    }}
    tbody tr:last-child td {{ border-bottom: none; }}
    tbody tr {{ transition: background .15s; }}
    tbody tr:hover td {{ background: rgba(255,255,255,.02); }}
    .td-dim  {{ color: var(--text-dim); font-size: 12px; }}
    .td-mono {{ font-variant-numeric: tabular-nums; }}

    /* ── BADGE ── */
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 3px 9px;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 600;
      white-space: nowrap;
    }}
    .badge-venter {{ background: rgba(255,255,255,.06); color: var(--text-dim); }}
    .badge-vant   {{ background: var(--green-bg);  color: var(--green); }}
    .badge-tapte  {{ background: var(--red-bg);    color: var(--red); }}

    /* ── EMPTY ── */
    .empty {{
      text-align: center;
      padding: 48px 0;
      color: var(--text-dim);
      font-size: 13px;
    }}

    /* ── TOOLTIP ── */
    #tooltip {{
      position: fixed;
      background: #1e2130;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 12px;
      font-size: 12px;
      pointer-events: none;
      opacity: 0;
      transition: opacity .15s;
      z-index: 100;
    }}
    #tooltip .t-date  {{ color: var(--text-dim); margin-bottom: 2px; }}
    #tooltip .t-value {{ font-weight: 600; font-size: 14px; }}

    @media (max-width: 700px) {{
      .cards {{ grid-template-columns: repeat(2, 1fr); }}
      .page  {{ padding: 16px; }}
    }}
  </style>
</head>
<body>

<nav>
  <div class="nav-brand">
    <span>🏀</span>
    <span>NBA Bet Tracker</span>
    <span class="dot"></span>
  </div>
  <span class="nav-date">Oppdatert {date.today().strftime('%-d. %B %Y')}</span>
</nav>

<div class="page">

  <!-- KPI-kort -->
  <div class="cards">
    <div class="card {saldo_klasse}">
      <div class="card-label">Bankroll</div>
      <div class="card-value {saldo_klasse}">{saldo:.0f} kr</div>
      <div class="card-sub">Start: {startkapital:.0f} kr</div>
    </div>
    <div class="card {pnl_klasse}">
      <div class="card-label">Profitt / Tap</div>
      <div class="card-value {pnl_klasse}">{pnl_prefix}{total_pnl:.0f} kr</div>
      <div class="card-sub">{len(avsluttede)} avsluttede bets</div>
    </div>
    <div class="card {roi_klasse}">
      <div class="card-label">ROI</div>
      <div class="card-value {roi_klasse}">{roi_prefix}{roi}%</div>
      <div class="card-sub">Siden oppstart</div>
    </div>
    <div class="card purple">
      <div class="card-label">Win Rate</div>
      <div class="card-value purple">{win_rate}%</div>
      <div class="card-sub">{len(vunnet)} av {len(avsluttede)} vant</div>
    </div>
  </div>

  <!-- Graf -->
  <div class="panel">
    <div class="panel-header">
      <span class="panel-title">Bankroll-utvikling</span>
    </div>
    <div class="panel-body">
      <div id="chart"></div>
    </div>
  </div>

  <!-- Bet-tabell -->
  <div class="panel">
    <div class="panel-header">
      <span class="panel-title">Alle bets</span>
    </div>
    <table>
      <thead>
        <tr>
          <th>Dato</th>
          <th>Kamp</th>
          <th>Bet</th>
          <th>Odds</th>
          <th>Innsats</th>
          <th>Value</th>
          <th>Status</th>
          <th>Resultat</th>
        </tr>
      </thead>
      <tbody id="bet-body"></tbody>
    </table>
  </div>

</div>

<div id="tooltip">
  <div class="t-date" id="t-date"></div>
  <div class="t-value" id="t-value"></div>
</div>

<script>
const historikk = {historikk_json};
const bets = {bets_json};
const START = {startkapital};

// ── TABELL ──
const tbody = document.getElementById('bet-body');
if (bets.length === 0) {{
  tbody.innerHTML = `<tr><td colspan="8"><div class="empty">Ingen bets registrert ennå.</div></td></tr>`;
}} else {{
  [...bets].reverse().forEach(b => {{
    const gevinst = b.gevinst !== null
      ? (b.gevinst >= 0
          ? `<span style="color:var(--green)">+${{b.gevinst.toFixed(0)}} kr</span>`
          : `<span style="color:var(--red)">${{b.gevinst.toFixed(0)}} kr</span>`)
      : '<span style="color:var(--text-dim)">–</span>';
    const badge = b.status === 'vant'  ? 'badge-vant'
                : b.status === 'tapte' ? 'badge-tapte'
                :                        'badge-venter';
    const icon  = b.status === 'vant'  ? '●'
                : b.status === 'tapte' ? '●'
                :                        '○';
    const label = b.status === 'vant'  ? 'Vant'
                : b.status === 'tapte' ? 'Tapte'
                :                        'Venter';
    tbody.innerHTML += `
      <tr>
        <td class="td-dim td-mono">${{b.dato.slice(5)}}</td>
        <td class="td-dim" style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${{b.kamp}}</td>
        <td style="font-size:12px">${{b.bet}}</td>
        <td class="td-mono" style="color:var(--blue)">${{b.odds.toFixed(2)}}</td>
        <td class="td-mono">${{b.innsats.toFixed(0)}} kr</td>
        <td class="td-mono" style="color:var(--green)">${{b.value}}</td>
        <td><span class="badge ${{badge}}">${{icon}} ${{label}}</span></td>
        <td class="td-mono">${{gevinst}}</td>
      </tr>`;
  }});
}}

// ── GRAF ──
const container = document.getElementById('chart');
const tooltip   = document.getElementById('tooltip');
const tDate     = document.getElementById('t-date');
const tValue    = document.getElementById('t-value');

if (historikk.length < 2) {{
  container.innerHTML = '<div class="empty">Kjør boten noen dager for å se utviklingen her.</div>';
}} else {{
  const W = container.offsetWidth || 900;
  const H = 240;
  const p = {{ t: 16, r: 16, b: 36, l: 58 }};
  const iW = W - p.l - p.r;
  const iH = H - p.t - p.b;

  const vals   = historikk.map(h => h.saldo);
  const minV   = Math.min(...vals, START) * 0.97;
  const maxV   = Math.max(...vals, START) * 1.03;
  const n      = historikk.length;

  const xS = i => p.l + (i / (n - 1)) * iW;
  const yS = v => p.t + iH - ((v - minV) / (maxV - minV)) * iH;

  // Smooth bezier path
  function smoothPath(pts) {{
    if (pts.length < 2) return '';
    let d = `M ${{pts[0][0]}} ${{pts[0][1]}}`;
    for (let i = 1; i < pts.length; i++) {{
      const [x0, y0] = pts[i - 1];
      const [x1, y1] = pts[i];
      const cx = (x0 + x1) / 2;
      d += ` C ${{cx}} ${{y0}}, ${{cx}} ${{y1}}, ${{x1}} ${{y1}}`;
    }}
    return d;
  }}

  const pts  = historikk.map((h, i) => [xS(i), yS(h.saldo)]);
  const path = smoothPath(pts);
  const area = path + ` L ${{p.l + iW}} ${{p.t + iH}} L ${{p.l}} ${{p.t + iH}} Z`;

  const startY = yS(START);

  // Y gridlines
  const ticks = 4;
  let gridLines = '', yLabels = '';
  for (let i = 0; i <= ticks; i++) {{
    const v = minV + (i / ticks) * (maxV - minV);
    const y = yS(v);
    gridLines += `<line x1="${{p.l}}" y1="${{y}}" x2="${{p.l + iW}}" y2="${{y}}" stroke="#1e2130" stroke-width="1"/>`;
    yLabels   += `<text x="${{p.l - 8}}" y="${{y + 4}}" text-anchor="end" font-size="11" fill="#3d4460">${{Math.round(v)}}</text>`;
  }}

  // X labels (max 6)
  const step = Math.max(1, Math.ceil(n / 6));
  let xLabels = '';
  for (let i = 0; i < n; i += step) {{
    xLabels += `<text x="${{xS(i)}}" y="${{H - 6}}" text-anchor="middle" font-size="11" fill="#3d4460">${{historikk[i].dato.slice(5)}}</text>`;
  }}
  if ((n - 1) % step !== 0) {{
    xLabels += `<text x="${{xS(n-1)}}" y="${{H - 6}}" text-anchor="middle" font-size="11" fill="#3d4460">${{historikk[n-1].dato.slice(5)}}</text>`;
  }}

  // Hover dots (invisible, large hit area)
  let hoverDots = pts.map(([x, y], i) =>
    `<circle class="hdot" cx="${{x}}" cy="${{y}}" r="14" fill="transparent"
             data-i="${{i}}" data-x="${{x}}" data-y="${{y}}"/>`
  ).join('');

  container.innerHTML = `
    <svg width="100%" viewBox="0 0 ${{W}} ${{H}}" preserveAspectRatio="none" style="overflow:visible">
      <defs>
        <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stop-color="#6366f1" stop-opacity=".18"/>
          <stop offset="100%" stop-color="#6366f1" stop-opacity="0"/>
        </linearGradient>
        <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%"   stop-color="#6366f1"/>
          <stop offset="100%" stop-color="#60a5fa"/>
        </linearGradient>
      </defs>

      ${{gridLines}}${{yLabels}}${{xLabels}}

      <!-- startlinje -->
      <line x1="${{p.l}}" y1="${{startY}}" x2="${{p.l + iW}}" y2="${{startY}}"
            stroke="#3d4460" stroke-width="1" stroke-dasharray="4 3"/>

      <!-- area fill -->
      <path d="${{area}}" fill="url(#areaGrad)"/>

      <!-- linje -->
      <path d="${{path}}" fill="none" stroke="url(#lineGrad)" stroke-width="2.5"
            stroke-linecap="round" stroke-linejoin="round"/>

      <!-- synlige punkter -->
      ${{pts.map(([x, y], i) => `
        <circle cx="${{x}}" cy="${{y}}" r="3.5" fill="#6366f1" stroke="#0d0f14" stroke-width="2"/>
      `).join('')}}

      ${{hoverDots}}
    </svg>`;

  // Tooltip-logikk
  container.querySelectorAll('.hdot').forEach(dot => {{
    dot.addEventListener('mouseenter', e => {{
      const i   = +e.target.dataset.i;
      const h   = historikk[i];
      const pnl = h.saldo - START;
      tDate.textContent  = h.dato;
      tValue.innerHTML   = `<span style="color:${{pnl>=0?'var(--green)':'var(--red)'}}">${{h.saldo.toFixed(0)}} kr</span>
                            <span style="color:var(--text-dim);font-size:11px;margin-left:6px">${{pnl>=0?'+':''}}${{pnl.toFixed(0)}} kr</span>`;
      tooltip.style.opacity = '1';
    }});
    dot.addEventListener('mousemove', e => {{
      tooltip.style.left = (e.clientX + 14) + 'px';
      tooltip.style.top  = (e.clientY - 32) + 'px';
    }});
    dot.addEventListener('mouseleave', () => {{ tooltip.style.opacity = '0'; }});
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
    venter = [b for b in bets if b["status"] == "venter" and b["dato"] != str(date.today())]
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
