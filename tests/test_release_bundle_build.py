import pytest
from scripts import build_release_bundle


def test_release_bundle_rejects_foreign_pyinstaller(monkeypatch, tmp_path):
    monkeypatch.setattr(build_release_bundle.sys, "prefix", str(tmp_path / "active"))

    with pytest.raises(SystemExit, match="active SonicForge environment"):
        build_release_bundle._pyinstaller_argv(tmp_path / "foreign" / "bin" / "pyinstaller")


def test_release_bundle_provisions_default_profile_before_registration():
    feature = build_release_bundle._feature_manifest("0.1.2")

    assert feature["entrypoint"] == "bin/sonicforge-core"
    assert feature["provision_args"] == ["provision"]
    assert feature["smoke_args"] == ["doctor"]
    assert feature["service_args"] == ["serve"]
