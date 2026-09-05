from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

UPSTREAM_COMMIT = "48b1a0169a28582a8984402f82cf438d3bfa6aca"
UPSTREAM_SHA256 = "1c967e31777b2b88468af3e7481bcb770ac4d09dd854bdb9ee065d8c8c75fcb6"
MODEL_REVISION = "336b2ec4e8d4ac74740798dd40af44e74659ecaf"
LANG_ID_SHA256 = "7e69ec5451bc261cc7844e49e4792a85d7f09c06789ec800fc4a44aec362764e"
MODEL_FILES = (
    "s1v3.ckpt",
    "v2Pro/s2Gv2ProPlus.pth",
    "sv/pretrained_eres2netv2w24s4ep4.ckpt",
    "chinese-hubert-base/*",
    "chinese-roberta-wwm-ext-large/*",
)


def _download(url: str, destination: Path, digest: str) -> None:
    urllib.request.urlretrieve(url, destination)
    actual = hashlib.sha256(destination.read_bytes()).hexdigest()
    if actual != digest:
        raise RuntimeError(f"download digest mismatch: {actual}")


def _extract(archive: Path, destination: Path) -> Path:
    with tarfile.open(archive, "r:gz") as bundle:
        root = destination.resolve()
        for member in bundle.getmembers():
            resolved = (destination / member.name).resolve()
            if root not in resolved.parents and resolved != root:
                raise RuntimeError("upstream archive attempts path traversal")
            if member.issym() or member.islnk():
                raise RuntimeError("upstream archive contains a link")
        bundle.extractall(destination, filter="data")
    return destination / f"GPT-SoVITS-{UPSTREAM_COMMIT}"


def _replace(path: Path, old: str, new: str, *, count: int | None = None) -> None:
    source = path.read_text(encoding="utf-8")
    found = source.count(old)
    expected = found if count is None else count
    if found != expected or found == 0:
        raise RuntimeError(f"upstream patch context changed: {path.name}: {old!r}")
    path.write_text(source.replace(old, new), encoding="utf-8")


def _patch_bfloat16(source: Path) -> None:
    tts = source / "GPT_SoVITS/TTS_infer_pack/TTS.py"
    _replace(tts, "import numpy as np\n", "import numpy as np\nimport soundfile as sf\n", count=1)
    _replace(tts, "torch.float16 if self.configs.is_half else torch.float32", "torch.bfloat16 if self.configs.is_half else torch.float32", count=1)
    _replace(tts, ".half()", ".to(torch.bfloat16)", count=14)
    _replace(tts, "self.vocoder = self.vocoder.to(torch.bfloat16).to(self.configs.device)", "self.vocoder = self.vocoder.to(device=self.configs.device, dtype=torch.bfloat16)", count=1)
    _replace(
        tts,
        "raw_audio, raw_sr = torchaudio.load(ref_audio_path)",
        "raw_array, raw_sr = sf.read(ref_audio_path, dtype=\"float32\", always_2d=True)\n        raw_audio = torch.from_numpy(raw_array.T)",
        count=1,
    )
    _replace(tts, "dtype=np.float16 if self.configs.is_half else np.float32", "dtype=np.float32", count=1)
    _replace(tts, "audio = audio.cpu().numpy()", "audio = audio.float().cpu().numpy()", count=2)

    sv = source / "GPT_SoVITS/sv.py"
    _replace(sv, "self.embedding_model = self.embedding_model.half().to(device)", "self.embedding_model = self.embedding_model.to(device=device, dtype=torch.bfloat16)", count=1)
    _replace(sv, "wav = wav.half()", "wav = wav.float()", count=1)
    _replace(
        sv,
        "            sv_emb = self.embedding_model.forward3(feat)",
        "            if self.is_half:\n                feat = feat.to(torch.bfloat16)\n            sv_emb = self.embedding_model.forward3(feat)",
        count=1,
    )


def main() -> None:
    from huggingface_hub import snapshot_download

    target = Path(sys.argv[1]).resolve()
    manifest = target / "sonicforge-gpt-sovits.json"
    if manifest.is_file():
        value = json.loads(manifest.read_text(encoding="utf-8"))
        if value.get("upstream_commit") == UPSTREAM_COMMIT and value.get("model_revision") == MODEL_REVISION:
            print(json.dumps([value]))
            return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gpt-sovits-", dir=target.parent) as temporary:
        staging = Path(temporary) / "active"
        staging.mkdir()
        archive = Path(temporary) / "source.tar.gz"
        _download(
            f"https://github.com/RVC-Boss/GPT-SoVITS/archive/{UPSTREAM_COMMIT}.tar.gz",
            archive,
            UPSTREAM_SHA256,
        )
        source = _extract(archive, Path(temporary))
        _patch_bfloat16(source)
        weights = source / "GPT_SoVITS/pretrained_models"
        snapshot_download(
            repo_id="lj1995/GPT-SoVITS",
            revision=MODEL_REVISION,
            allow_patterns=list(MODEL_FILES),
            local_dir=weights,
        )
        lang_id = weights / "fast_langdetect/lid.176.bin"
        lang_id.parent.mkdir(parents=True, exist_ok=True)
        _download(
            "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin",
            lang_id,
            LANG_ID_SHA256,
        )
        # Provision every network-backed Japanese text asset before activation;
        # ordinary generation is deliberately offline.
        previous_cwd = Path.cwd()
        try:
            os.chdir(source)
            sys.path[:0] = [str(source), str(source / "GPT_SoVITS")]
            import pyopenjtalk
            from GPT_SoVITS.text.japanese import g2p

            pyopenjtalk.g2p("音声")
            g2p("音声")
        finally:
            os.chdir(previous_cwd)
        source.rename(staging / "source")
        value = {
            "model": "lj1995/GPT-SoVITS",
            "model_revision": MODEL_REVISION,
            "upstream": "RVC-Boss/GPT-SoVITS",
            "upstream_commit": UPSTREAM_COMMIT,
            "upstream_archive_sha256": UPSTREAM_SHA256,
            "license": "MIT",
            "path": str(target / "source"),
        }
        (staging / manifest.name).write_text(json.dumps(value, indent=2), encoding="utf-8")
        previous = target.with_name(f".{target.name}.previous")
        if previous.exists():
            shutil.rmtree(previous)
        if target.exists():
            target.rename(previous)
        os.replace(staging, target)
    print(json.dumps([value]))


if __name__ == "__main__":
    main()
