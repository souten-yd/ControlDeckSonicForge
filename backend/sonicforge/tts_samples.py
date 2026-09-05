from __future__ import annotations

import hashlib
import io
import shutil
import urllib.parse
import urllib.request
import uuid

from sqlalchemy.orm import Session

from . import uploads
from .config import Settings
from .db import Voice

ZUNDAMON_REVISION = "cf5104f20781e3e81be499cd0c872b9801be1c51"
ZUNDAMON_URL = (
    "https://raw.githubusercontent.com/zunzun999/zundamon-speech-webui/"
    f"{ZUNDAMON_REVISION}/reference/reference.wav"
)
ZUNDAMON_SHA256 = "b41e3f0d539c2c294fdbf03349b8b07127bad9576e52936d45c190c7eec07b02"
ZUNDAMON_SOURCE_BYTES = 1_999_242
ZUNDAMON_TERMS = "https://zunko.jp/con_ongen_kiyaku.html"
AMITARO_SOURCE = "https://amitaro.net/voice/corpus-list/ita/"
AMITARO_TERMS = "https://amitaro.net/voice/voice_rule/"
MAX_CATALOG_DOWNLOAD = 4 * 1024 * 1024


class SampleCatalogError(ValueError):
    pass


class _BytesUpload:
    def __init__(self, value: bytes):
        self._stream = io.BytesIO(value)

    async def read(self, size: int) -> bytes:
        return self._stream.read(size)


def catalog(session: Session) -> dict:
    installed = {
        (row.recipe or {}).get("catalog_id"): row.id
        for row in session.query(Voice).filter(Voice.engine_id == "tts.gpt-sovits")
        if (row.recipe or {}).get("catalog_id")
    }
    return {
        "samples": [
            {
                "id": "amitaro-ita-yofukashi",
                "name": "あみたろ（ITA・よふかし）",
                "language": "ja",
                "source_url": AMITARO_SOURCE,
                "terms_url": AMITARO_TERMS,
                "credit": "あみたろの声素材工房（https://amitaro.net/）",
                "reference_text": "イタリア旅行で彼は、いくつか景勝の地として有名な都市、例えば、ナポリやフィレンツェを訪れた。",
                "install_mode": "local_file",
                "installed_voice_id": installed.get("amitaro-ita-yofukashi"),
            },
            {
                "id": "zundamon-reference",
                "name": "ずんだもん（GPT-SoVITS 配布参照音声）",
                "language": "ja",
                "source_url": "https://github.com/zunzun999/zundamon-speech-webui/tree/main/reference",
                "terms_url": ZUNDAMON_TERMS,
                "credit": "ずんだもん（東北ずん子・ずんだもんプロジェクト）",
                "reference_text": "流し切りが完全に入ればデバフの効果が付与される",
                "install_mode": "managed_download",
                "installed_voice_id": installed.get("zundamon-reference"),
            },
        ]
    }


def _download_zundamon() -> bytes:
    request = urllib.request.Request(ZUNDAMON_URL, headers={"User-Agent": "SonicForge/0.6"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            final = urllib.parse.urlsplit(response.geturl())
            allowed = final.hostname == "raw.githubusercontent.com"
            if final.scheme != "https" or not allowed:
                raise SampleCatalogError("sample download redirected outside trusted hosts")
            value = response.read(MAX_CATALOG_DOWNLOAD + 1)
    except OSError as exc:
        raise SampleCatalogError("sample download failed; try again later") from exc
    if len(value) > MAX_CATALOG_DOWNLOAD:
        raise SampleCatalogError("sample download is too large")
    if len(value) != ZUNDAMON_SOURCE_BYTES or hashlib.sha256(value).hexdigest() != ZUNDAMON_SHA256:
        raise SampleCatalogError("sample download did not match its pinned digest")
    return value


async def install(settings: Settings, session: Session, sample_id: str, *, accepted_terms: bool) -> Voice:
    if sample_id != "zundamon-reference":
        raise SampleCatalogError("this sample must be imported from a local file")
    if not accepted_terms:
        raise SampleCatalogError("sample terms must be accepted before installation")
    existing = session.query(Voice).filter(Voice.engine_id == "tts.gpt-sovits").all()
    for row in existing:
        if (row.recipe or {}).get("catalog_id") == sample_id:
            return row

    audio = _download_zundamon()
    uploaded = await uploads.store(settings, _BytesUpload(audio), filename="zundamon-reference.wav")
    source = uploads.resolve(settings, uploaded["upload_id"])
    voices_dir = settings.data_dir / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)
    target = voices_dir / f"{uuid.uuid4().hex}.wav"
    try:
        shutil.copyfile(source, target)
    finally:
        uploads.discard(settings, uploaded["upload_id"])
    row = Voice(
        id=f"voice:{uuid.uuid4()}",
        name="ずんだもん",
        source_type="clone",
        languages=["ja"],
        engine_id="tts.gpt-sovits",
        recipe={
            "reference_audio": str(target.relative_to(settings.data_dir)),
            "reference_text": "流し切りが完全に入ればデバフの効果が付与される",
            "catalog_id": sample_id,
            "source_url": "https://github.com/zunzun999/zundamon-speech-webui/tree/main/reference",
            "source_revision": ZUNDAMON_REVISION,
            "source_sha256": ZUNDAMON_SHA256,
            "terms_url": ZUNDAMON_TERMS,
            "credit": "ずんだもん（東北ずん子・ずんだもんプロジェクト）",
        },
        rights_confirmed=True,
    )
    try:
        session.add(row)
        session.commit()
        session.refresh(row)
    except BaseException:
        session.rollback()
        target.unlink(missing_ok=True)
        raise
    return row
