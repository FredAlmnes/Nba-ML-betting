"""
Grunnleggende oppsett-test: bekrefter at pytest.ini sin pythonpath = .
faktisk lar tester importere moduler fra repo-roten, FØR noen ekte
test avhenger av at dette virker.
"""


def test_repo_rot_er_importerbar():
    import modell_utils

    assert hasattr(modell_utils, "KalibrertModell")
