"""
Tester for 08_kjor_backtest.py — CLI-inngangspunktet for walk-forward-
backtesten (plan 05-10). Filnavnet starter med et siffer og kan derfor ikke
importeres normalt; modulen lastes via importlib.util.spec_from_file_location
akkurat slik tests/test_bot.py laster 06_bot.py.

Ingen test her kjører en ekte walk-forward-backtest, åpner odds_arkiv.db
eller trener en modell, og ingen rører bankroll.json/bets.json. Hver test
gjør ett av tre: kaller en ren validator direkte på den lastede modulen,
starter scriptet som en subprocess med argumenter som feiler FØR noen data
leses (argparse-stadiet, eller de eksplisitte parser.error-avvisningene
Task 2 legger til), eller — den ene skip-guardede unntagelsen i banner 3
(plan 05-10 Task 3) — kjører et ekte, men billig, to-ukers CLI-drevet løp
når nba_features.csv/odds_arkiv.db/nba_spillerlogg_raw.csv finnes på disk.

Hver subprocess-test peker --katalog på tmp_path, slik at selv en uventet
suksess aldri kan skrive inn i repoets ekte backtests/-katalog.
"""

import argparse
import importlib.util
import inspect
import json
import os
import subprocess
import sys

import pytest

import backtest
import config


def _last_cli():
    spec = importlib.util.spec_from_file_location("kjor_backtest", "08_kjor_backtest.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture
def cli():
    return _last_cli()


def _kjor_cli(argv, ekstra_env=None):
    env = dict(os.environ)
    if ekstra_env:
        env.update(ekstra_env)
    return subprocess.run(
        [sys.executable, "08_kjor_backtest.py"] + argv,
        capture_output=True, text=True, env=env,
    )


# ---------------------------------------------------------------------------
# 1. Validatorer, parser og numeriske vakter (Task 1)
# ---------------------------------------------------------------------------


def test_iso_dato_godtar_gyldig_dato_og_returnerer_streng(cli):
    resultat = cli.iso_dato("2024-10-01")
    assert resultat == "2024-10-01"
    assert isinstance(resultat, str)


def test_iso_dato_avviser_ugyldig_dato(cli):
    for verdi in ["2024-13-45", "01/10/2024", "i går", ""]:
        with pytest.raises(argparse.ArgumentTypeError) as exc_info:
            cli.iso_dato(verdi)
        assert verdi in str(exc_info.value)


def test_iso_dato_avviser_ikke_nullpolstret_dato(cli):
    """
    "2024-1-5" er en gyldig dato for datetime.strptime, men sorterer
    leksikalsk UNDER "2024-10-01" fordi '-' < '0' som byte — brukes den i en
    streng-sammenligning (som hent_unike_kampdatoer og _sikre_ikke_holdout
    begge gjør), havner den stille på feil side av holdout-grensen i stedet
    for å feile. iso_dato må derfor avvise FORMEN, ikke bare gyldigheten.
    """
    with pytest.raises(argparse.ArgumentTypeError):
        cli.iso_dato("2024-1-5")


def test_dag_for_holdout_er_dagen_for_holdoutstart(cli):
    from datetime import date, timedelta

    forventet = (date.fromisoformat(config.HOLDOUT_START_DATO) - timedelta(days=1)).isoformat()
    resultat = cli.dag_for_holdout()
    assert isinstance(resultat, str)
    assert resultat == forventet
    assert resultat < config.HOLDOUT_START_DATO


def test_cli_avviser_ugyldig_fra_dato(tmp_path):
    resultat = _kjor_cli(["--fra", "2024-13-45", "--katalog", str(tmp_path / "ubrukt")])
    assert resultat.returncode == 2
    assert "2024-13-45" in resultat.stderr


def test_cli_avviser_fra_etter_til(tmp_path):
    resultat = _kjor_cli([
        "--fra", "2023-01-02", "--til", "2023-01-01",
        "--katalog", str(tmp_path / "ubrukt"),
    ])
    assert resultat.returncode == 2
    assert not (tmp_path / "ubrukt").exists()


def test_cli_avviser_kellyfraksjon_null(tmp_path):
    for verdi in ["0", "-0.25", "1.5"]:
        resultat = _kjor_cli([
            "--kelly-fraksjon", verdi, "--katalog", str(tmp_path / f"ubrukt-{verdi}"),
        ])
        assert resultat.returncode == 2, (verdi, resultat.stderr)
    resultat_null = _kjor_cli(["--kelly-fraksjon", "0", "--katalog", str(tmp_path / "ubrukt-0-igjen")])
    assert "flat" in resultat_null.stderr.lower()


def test_cli_avviser_min_odds_over_maks_odds(tmp_path):
    resultat = _kjor_cli([
        "--min-odds", "4.5", "--maks-odds", "2.0",
        "--katalog", str(tmp_path / "ubrukt"),
    ])
    assert resultat.returncode == 2


def test_cli_avviser_ikke_positiv_startkapital(tmp_path):
    resultat = _kjor_cli(["--startkapital", "0", "--katalog", str(tmp_path / "ubrukt")])
    assert resultat.returncode == 2


def test_hjelpeteksten_advarer_om_holdout():
    resultat = _kjor_cli(["--help"])
    assert resultat.returncode == 0
    assert "--holdout" in resultat.stdout
    assert "én gang" in resultat.stdout


def test_cli_gjor_ingen_kjoring_ved_lasting(monkeypatch):
    def boom_kjor(*args, **kwargs):
        raise AssertionError("backtest.kjor_og_lagre ble kalt under modul-lasting av CLI-en")

    def boom_last(*args, **kwargs):
        raise AssertionError("backtest.klargjor_backtestdata ble kalt under modul-lasting av CLI-en")

    monkeypatch.setattr(backtest, "kjor_og_lagre", boom_kjor)
    monkeypatch.setattr(backtest, "klargjor_backtestdata", boom_last)

    modul = _last_cli()
    assert modul is not None
    assert hasattr(modul, "bygg_parser")


def test_ingen_bar_except_i_cli():
    """
    Ingen bred unntaksfanger (`except Exception` eller en bar `except:`) skal
    noensinne finnes i denne filen — en slik ville kunnet svelge
    backtest.HoldoutLaastFeil og gjort fasens primære vakt om til en
    printet advarsel. `iso_dato` sin egen, smale `except ValueError:` (Task
    1) er en bevisst konvertering til argparse.ArgumentTypeError, ikke en
    bred fanger, og er derfor ikke rammet av dette forbudet. Task 2 legger
    til den ENESTE andre except-typen filen skal ha: `except FileNotFoundError`.
    """
    kilde = open("08_kjor_backtest.py", encoding="utf-8").read()
    ikke_kommentarlinjer = [l for l in kilde.splitlines() if not l.strip().startswith("#")]
    tekst = "\n".join(ikke_kommentarlinjer)
    assert "except Exception" not in tekst
    assert "except:" not in tekst
    except_linjer = [l for l in ikke_kommentarlinjer if l.strip().startswith("except")]
    for linje in except_linjer:
        assert "FileNotFoundError" in linje or "ValueError" in linje, linje


# ---------------------------------------------------------------------------
# 2. Dispatch, holdout-kombinasjoner og oppsummeringsutskrift (Task 2)
# ---------------------------------------------------------------------------


def _fake_manifest(**overrides):
    manifest = {
        "run_id": "20260101-000000-deadbeef",
        "type": "tuning",
        "periode": {
            "fra_dato": "2022-11-01", "til_dato": "2022-11-30",
            "datoer_totalt": 5, "datoer_behandlet": 5, "kamper_totalt": 12,
        },
        "datakvalitet": {
            "kamper_hoppet_over_manglende_odds": 3,
            "kandidater_flagget": 2,
            "kandidater_blokkert_av_skadefilter": 1,
            "retreninger": 1,
        },
        "metrikker": {
            "antall_bets": 4, "roi": 0.123, "roi_ci_nedre": -0.05,
            "roi_ci_oevre": 0.30, "vinnrate": 0.5,
            "maks_drawdown_andel": 0.1, "maks_drawdown_kroner": 12.0,
            "clv_snitt": 0.01, "antall_uten_clv": 0, "bootstrap_seed": 42,
        },
    }
    manifest.update(overrides)
    return manifest


def _kjor_main(cli, monkeypatch, argv, manifest=None):
    """
    Kjører cli.main() med sys.argv patchet og backtest.klargjor_backtestdata/
    backtest.kjor_og_lagre erstattet med spioner som aldri rører disk eller
    nettverk. Returnerer (last_kall, kjor_kall, avslutningskode) —
    nøkkelordargumentene hvert spionert kall ble mottatt med, pluss
    SystemExit-koden main() endte med.
    """
    last_kall = {}
    kjor_kall = {}

    def fake_last(**kwargs):
        last_kall.update(kwargs)
        return {"features_df": None, "datoer": [], "spillerlogg_df": None, "con": None}

    def fake_kjor(data, **kwargs):
        kjor_kall.update(kwargs)
        return ("backtests/FAKE-KJORING", manifest or _fake_manifest(), [])

    monkeypatch.setattr(backtest, "klargjor_backtestdata", fake_last)
    monkeypatch.setattr(backtest, "kjor_og_lagre", fake_kjor)
    monkeypatch.setattr(sys, "argv", ["08_kjor_backtest.py"] + argv)

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    return last_kall, kjor_kall, exc_info.value.code


def test_standardkjoring_ber_om_tuning(cli, monkeypatch):
    last_kall, kjor_kall, exit_code = _kjor_main(cli, monkeypatch, [])
    assert exit_code == 0
    assert not kjor_kall.get("holdout", False)
    assert kjor_kall.get("kjor_sweep") is False
    assert last_kall["fra"] is None
    assert last_kall["til"] == cli.dag_for_holdout()
    assert last_kall["til"] < config.HOLDOUT_START_DATO


def test_eksplisitt_til_overstyrer_standarden(cli, monkeypatch):
    last_kall, _, exit_code = _kjor_main(
        cli, monkeypatch, ["--fra", "2023-01-02", "--til", "2023-02-01"]
    )
    assert exit_code == 0
    assert last_kall["fra"] == "2023-01-02"
    assert last_kall["til"] == "2023-02-01"

    last_kall2, _, exit_code2 = _kjor_main(cli, monkeypatch, ["--fra", "2023-01-02"])
    assert exit_code2 == 0
    assert last_kall2["fra"] == "2023-01-02"
    assert last_kall2["til"] == cli.dag_for_holdout()


def test_sweep_flagget_slaar_paa_sweep(cli, monkeypatch):
    _, kjor_kall, exit_code = _kjor_main(cli, monkeypatch, ["--sweep"])
    assert exit_code == 0
    assert kjor_kall["kjor_sweep"] is True
    assert not kjor_kall.get("holdout", False)


def test_holdout_krever_bekreftelse(tmp_path):
    katalog = tmp_path / "ubrukt"
    resultat = _kjor_cli(["--holdout", "--katalog", str(katalog)])
    assert resultat.returncode == 2
    assert "bekreft-holdout" in resultat.stderr
    assert "én gang" in resultat.stderr or "ÉN GANG" in resultat.stderr
    assert not katalog.exists()


def test_bekreftelse_uten_holdout_avvises(tmp_path):
    katalog = tmp_path / "ubrukt"
    resultat = _kjor_cli(["--bekreft-holdout", "--katalog", str(katalog)])
    assert resultat.returncode == 2
    assert not katalog.exists()


def test_holdout_og_sweep_avvises(tmp_path):
    katalog = tmp_path / "ubrukt"
    resultat = _kjor_cli([
        "--holdout", "--bekreft-holdout", "--sweep", "--katalog", str(katalog),
    ])
    assert resultat.returncode == 2
    assert not katalog.exists()


def test_holdout_med_datoomrade_avvises(tmp_path):
    for i, flagg in enumerate([["--fra", "2024-11-01"], ["--til", "2024-11-15"]]):
        katalog = tmp_path / f"ubrukt-{i}"
        resultat = _kjor_cli([
            "--holdout", "--bekreft-holdout", *flagg, "--katalog", str(katalog),
        ])
        assert resultat.returncode == 2, flagg
        assert not katalog.exists()


def test_holdout_veien_kaller_motoren_med_holdout(cli, monkeypatch):
    last_kall, kjor_kall, exit_code = _kjor_main(
        cli, monkeypatch, ["--holdout", "--bekreft-holdout"],
        manifest=_fake_manifest(type="holdout"),
    )
    assert exit_code == 0
    assert kjor_kall["holdout"] is True
    assert not kjor_kall.get("kjor_sweep", False)
    assert last_kall["fra"] is None
    assert last_kall["til"] is None


def test_bare_holdout_funksjonen_apner_vinduet(cli):
    kilde = open("08_kjor_backtest.py", encoding="utf-8").read()
    holdout_kilde = inspect.getsource(cli.kjor_holdout)
    rest_linjer = [
        l for l in kilde.replace(holdout_kilde, "").splitlines()
        if not l.strip().startswith("#")
    ]
    rest = "\n".join(rest_linjer)
    assert "holdout=True" not in rest


def test_terskler_naar_motoren(cli, monkeypatch):
    _, kjor_kall, exit_code = _kjor_main(cli, monkeypatch, [
        "--min-value-terskel", "0.10", "--min-odds", "1.20", "--maks-odds", "3.00",
        "--kelly-fraksjon", "0.25", "--startkapital", "500", "--min-treningskamper", "250",
    ])
    assert exit_code == 0
    assert kjor_kall["min_value_terskel"] == 0.10
    assert kjor_kall["min_odds"] == 1.20
    assert kjor_kall["maks_odds"] == 3.00
    assert kjor_kall["kelly_fraksjon"] == 0.25
    assert kjor_kall["startkapital"] == 500.0
    assert kjor_kall["min_treningskamper"] == 250


def test_uten_skadefilter_naar_bade_lasting_og_kjoring(cli, monkeypatch):
    last_kall, kjor_kall, exit_code = _kjor_main(cli, monkeypatch, ["--uten-skadefilter"])
    assert exit_code == 0
    assert last_kall["bruk_skadefilter"] is False
    assert kjor_kall["bruk_skadefilter"] is False


def test_cli_skriver_run_id_og_hoppetellere(cli, monkeypatch, capsys):
    _, _, exit_code = _kjor_main(cli, monkeypatch, [])
    assert exit_code == 0
    ut = capsys.readouterr().out
    assert "20260101-000000-deadbeef" in ut
    assert "backtests/FAKE-KJORING" in ut
    assert "4" in ut          # antall_bets
    assert "12.3%" in ut      # roi .1%
    assert "3" in ut          # kamper_hoppet_over_manglende_odds


def test_cli_rorer_ikke_live_tilstand():
    kilde = open("08_kjor_backtest.py", encoding="utf-8").read()
    assert "bankroll.json" not in kilde
    assert "bets.json" not in kilde
    assert "dashboard" not in kilde
