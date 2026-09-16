"""外へ出す時刻には必ず時間帯を付ける。

JavaScript はオフセットの無い日時を **その端末の地方時** として読む（ECMAScript の
規定）。UTC の時計の針をそのまま地方時として表示するので、日本だと 9 時間前に
ずれる。実測 2026-09-16: 09:17 JST に作った素材が、ライブラリで 0:17 と出ていた。

ずれても「それらしい日時」が出るので、画面を見ただけでは気づけない。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from sonicforge.db import moment

from test_core import load_app


def test_a_naive_moment_is_read_as_utc():
    """SQLite は時間帯を保たない。読み出した naive を UTC として出す。"""
    naive = datetime(2026, 9, 16, 0, 17, 53)
    assert moment(naive) == "2026-09-16T00:17:53+00:00"
    assert moment(None) is None


def test_an_aware_moment_keeps_its_own_offset():
    """既に時間帯を持っているものを勝手に UTC へ読み替えない。"""
    aware = datetime(2026, 9, 16, 9, 17, 53, tzinfo=timezone(timedelta(hours=9)))
    assert moment(aware) == "2026-09-16T09:17:53+09:00"


def test_the_library_hands_out_timestamps_that_cannot_be_misread(env):
    """一覧に出る時刻は、そのまま `new Date()` に渡して正しく読めること。"""
    m = load_app()
    with TestClient(m.app) as c:
        from sonicforge import app as module
        from test_asset_download import _make_asset

        _make_asset(module, env, kind="speech", content=b"RIFF")
        body = c.get("/addon/v1/assets?limit=1").json()
        created = body["assets"][0]["created_at"]
        # 時間帯が付いていること。付いていないと読む側の地方時と解釈される。
        parsed = datetime.fromisoformat(created)
        assert parsed.tzinfo is not None, created
        # いま作ったものなので、UTC で見て現在に近い。ずれていれば数時間離れる。
        delta = abs((datetime.now(timezone.utc) - parsed).total_seconds())
        assert delta < 300, (created, delta)


def test_jobs_and_voices_carry_a_timezone_too(env):
    """素材だけ直しても、仕事と声の一覧が地方時に化けたままでは直っていない。"""
    m = load_app()
    with TestClient(m.app) as c:
        created = c.post("/addon/v1/agent/voice/create", json={
            "name": "時刻の確認", "method": "preset", "speaker": "Ono_Anna", "languages": ["ja"],
        }).json()
        assert datetime.fromisoformat(created["created_at"]).tzinfo is not None

        response = c.post("/addon/v1/tasks", json={
            "task": "speech.tts.synthesize", "input": {"text": "こんにちは。"},
            "content_language": "ja",
            "output": {"format": "wav", "sample_rate": None, "channels": None},
            "routing": {"engine": "fake", "model": None, "device": "auto"},
            "seed": None, "project_output_grant": None,
        })
        assert response.status_code == 200, response.text
        job = c.get(f"/addon/v1/jobs/{response.json()['job_id']}").json()
        assert datetime.fromisoformat(job["created_at"]).tzinfo is not None
        assert datetime.fromisoformat(job["updated_at"]).tzinfo is not None
