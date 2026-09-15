"""作った音を、いま見ている端末へ持ち出す経路。

携帯（iPhone）から使うことを前提にしている。今までの持ち出しは「書き出し」だけで、
行き先はホストのファイル選択だった。手元が携帯だと選ばせる相手が別の機械なので、
そこでは選べない。
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sonicforge import asset_download

from test_core import load_app


def _make_asset(module, tmp_path: Path, *, kind: str, content: bytes) -> str:
    """素材を 1 件、直接置く。生成を待たずに持ち出しだけを試すため。"""
    import uuid

    from sonicforge.db import Asset, Provenance

    asset_id = f"asset:{uuid.uuid4()}"
    provenance_id = f"prov:{uuid.uuid4()}"
    relative = Path("assets") / f"{uuid.uuid4().hex}.wav"
    target = module.settings.data_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    with module.session_factory() as session:
        session.add(Provenance(
            id=provenance_id, operation=f"audio.{kind}.generate",
            engine_id="fake", engine_version="1", model_id="fake", model_license_id="test-only",
        ))
        session.add(Asset(
            id=asset_id, kind=kind, mime_type="audio/wav",
            relative_path=str(relative), size_bytes=len(content),
            sha256="0" * 64, duration_ms=1000, sample_rate=24000, channels=1,
            provenance_id=provenance_id,
        ))
        session.commit()
    return asset_id


def test_one_sound_comes_back_named_for_what_it_is(env):
    """落ちてきたファイルを見て、何の音か分かる。

    保存名は uuid である。そのまま渡すと、20 件落としたときにどれがどれだか
    分からない。種類を名前に出す。
    """
    m = load_app()
    with TestClient(m.app) as c:
        from sonicforge import app as module
        asset_id = _make_asset(module, env, kind="sfx", content=b"RIFF....sfx")
        response = c.get(f"/addon/v1/assets/{asset_id}/download")
        assert response.status_code == 200, response.text
        assert response.content == b"RIFF....sfx"
        disposition = response.headers["content-disposition"]
        assert disposition.startswith("attachment")
        assert "sonic-forge-sfx-" in disposition


def test_several_sounds_come_back_as_one_archive(env):
    """選んだぶんが 1 つの zip で落ちてくる。

    台詞をまとめて作ったあと、1 本ずつ開いて保存するのは携帯で現実的でない。
    """
    m = load_app()
    with TestClient(m.app) as c:
        from sonicforge import app as module
        ids = [
            _make_asset(module, env, kind=kind, content=f"RIFF-{kind}".encode())
            for kind in ("speech", "sfx", "music")
        ]
        query = "&".join(f"asset_id={item}" for item in ids)
        response = c.get(f"/addon/v1/assets-download?{query}")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/zip"
        assert response.headers["content-disposition"].startswith("attachment")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.testzip() is None
            names = archive.namelist()
            assert len(names) == 3
            # 種類が名前に出ているので、開かなくても見分けが付く。
            assert any("speech" in name for name in names)
            assert any("sfx" in name for name in names)
            assert any("music" in name for name in names)
            assert archive.read(next(n for n in names if "music" in n)) == b"RIFF-music"
        # 返し終えた zip を置き場に残さない。作り置きは古い中身を配る。
        assert list((module.settings.data_dir / "downloads").glob("*.zip")) == []


def test_a_missing_sound_is_named_instead_of_silently_skipped(env):
    """欠けた素材を黙って抜かない。

    抜いて成功にすると、落とした側は全部あると思ったまま元を消してしまう。
    """
    m = load_app()
    with TestClient(m.app) as c:
        from sonicforge import app as module
        asset_id = _make_asset(module, env, kind="speech", content=b"RIFF")
        response = c.get(
            f"/addon/v1/assets-download?asset_id={asset_id}&asset_id=asset:missing"
        )
        assert response.status_code == 404, response.text
        assert response.json()["detail"]["code"] == "asset_not_found"


def test_nothing_selected_is_refused(env):
    m = load_app()
    with TestClient(m.app) as c:
        response = c.get("/addon/v1/assets-download")
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == "download_empty"


class _Row:
    def __init__(self, kind: str, relative_path: str, size_bytes: int = 10) -> None:
        self.kind = kind
        self.relative_path = relative_path
        self.size_bytes = size_bytes


def test_too_many_is_refused_before_anything_is_built():
    """入り切らない要求を始めない。

    選んだ id は URL に載るので、件数の上限は URL の長さの上限でもある。
    途中で切れても、切れたことは落ちてきた zip を開くまで分からない。
    """
    with pytest.raises(asset_download.DownloadRefused) as refused:
        asset_download.plan(lambda _: (None, None), [f"asset:{i}" for i in range(200)])
    assert refused.value.code == "download_too_many"


def test_names_that_collide_do_not_overwrite_each_other(tmp_path: Path):
    """同じ名前になる素材が 2 つあっても、両方が zip に残る。

    同じ arcname で 2 回書くと、展開したとき片方が消える。消えたことは展開する
    まで分からない。
    """
    first = tmp_path / "same.wav"
    first.write_bytes(b"first")
    rows = {
        "a": (_Row("speech", "assets/same.wav", 5), first),
        "b": (_Row("speech", "assets/same.wav", 6), first),
        "c": (_Row("speech", "../../escape.wav", 7), first),
    }
    entries = asset_download.plan(lambda key: rows[key], ["a", "b", "c"])
    names = [entry.name for entry in entries]
    assert len(set(names)) == 3, names
    assert all("/" not in name and "\\" not in name and not name.startswith(".") for name in names)
    target = tmp_path / "out.zip"
    asset_download.build(entries, target)
    with zipfile.ZipFile(target) as archive:
        assert sorted(archive.namelist()) == sorted(names)


def test_size_beyond_the_bound_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    source = tmp_path / "big.wav"
    source.write_bytes(b"x")
    monkeypatch.setattr(asset_download, "MAX_TOTAL_BYTES", 0)
    with pytest.raises(asset_download.DownloadRefused) as refused:
        asset_download.plan(lambda _: (_Row("music", "assets/big.wav", 1), source), ["a"])
    assert refused.value.code == "download_too_large"


def test_stale_archives_are_swept(tmp_path: Path):
    """途中で落ちて残ったぶんを掃く。掃除のために別の仕掛けを増やさない。"""
    import os

    downloads = tmp_path / "downloads"
    downloads.mkdir()
    old = downloads / "old.zip"
    old.write_bytes(b"stale")
    fresh = downloads / "fresh.zip"
    fresh.write_bytes(b"new")
    now = old.stat().st_mtime + asset_download.STALE_AFTER_SEC + 1
    os.utime(fresh, (now, now))
    assert asset_download.sweep(downloads, now) == 1
    assert not old.exists() and fresh.exists()
