"""
Grunnleggende oppsett-test: bekrefter at pytest.ini sin pythonpath = .
faktisk lar tester importere moduler fra repo-roten, FØR noen ekte
test avhenger av at dette virker.
"""

import pathlib


def test_repo_rot_er_importerbar():
    import modell_utils

    assert hasattr(modell_utils, "KalibrertModell")


def test_backtest_artefakter_er_gitignorert():
    # backtests/ og nba_spillerlogg_raw.csv må være gitignorert FØR disse
    # artefaktene finnes — Plan 05-05 skriver nba_spillerlogg_raw.csv og
    # Plan 05-08 oppretter den første backtests/<run_id>/-mappen. En committet
    # backtest-ledger eller en 77k-rads spillerlogg er langt vanskeligere å
    # fjerne fra git-historikken enn å forhindre på forhånd.
    gitignore_sti = pathlib.Path(__file__).resolve().parent.parent / ".gitignore"
    linjer = [
        linje.strip()
        for linje in gitignore_sti.read_text(encoding="utf-8").splitlines()
        if linje.strip()
    ]
    assert "backtests/" in linjer
    assert "nba_spillerlogg_raw.csv" in linjer
