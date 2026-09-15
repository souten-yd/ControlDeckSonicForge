"""作った音を、いま見ている端末へ持ち出す。

これまでの持ち出しは「書き出し」だけで、行き先はホストのファイル選択だった。
手元が携帯だと、選ばせる相手が別の機械なので選べない。ここは押した端末へ
そのまま落とす経路を用意する。

押した瞬間に落ち始めるようにしてある。iOS の Safari は、利用者の操作から
離れた場所で始まった遷移をダウンロードとして扱わないことがある。先に
組み立ててから URL を差し替える形にすると、組み立てを待つ間に操作との繋がりが
切れる。だから **GET 一本** で、押した先がそのまま中身である。

zip は要求のたびに作って、返し終えたら消す。素材は増減するので、作り置きを
持つと「古い zip が落ちてくる」ことになる。
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# 1 回に持ち出せる件数。
#
# 押した瞬間に落ち始めるようにするため、選んだ素材の id は URL に載る。上限が
# 無いと URL が伸びて、途中で切れても切れたことが分からない。
MAX_ASSETS = 100

# 1 回に持ち出せる合計。
#
# 相手は携帯であることが多い。入り切らない大きさを黙って送り始めると、詰まった
# ことしか分からない形で失敗する。断って、選び直してもらうほうがよい。
# 音は画や動画より軽いので、件数の上限のほうが先に当たる。
MAX_TOTAL_BYTES = 2 * 1024**3

# zip の中の名前として許す文字。区切り文字を含む名前を書き込むと、展開した先で
# 階層が生える。
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")

# 種類ごとの、名前に出す語。id だけの名前で 20 件落とすと、どれが台詞でどれが
# 効果音か分からない。中身を聴く前に見分けられるようにする。
_KIND_WORD: dict[str, str] = {
    "speech": "speech",
    "sfx": "sfx",
    "ambience": "ambience",
    "music": "music",
    "transcript": "transcript",
}


class DownloadRefused(Exception):
    """持ち出しを断る。code は画面がそのまま文言へ訳せるものにする。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Entry:
    asset_id: str
    path: Path
    name: str
    size_bytes: int


def safe_name(value: str, fallback: str) -> str:
    cleaned = _UNSAFE.sub("-", str(value or "")).strip("-.")
    return cleaned or fallback


def suggested_name(asset) -> str:
    """落ちてきたファイルを見て、何の音か分かる名前にする。

    保存名は uuid である。それをそのまま渡すと、20 件落としたときにどれが
    どれだか分からない。種類と、元の名前の頭を残す。
    """
    stored = Path(str(asset.relative_path or "")).name
    suffix = Path(stored).suffix or ".wav"
    word = _KIND_WORD.get(str(asset.kind or ""), safe_name(str(asset.kind or ""), "audio"))
    short = safe_name(Path(stored).stem, "asset")[:8]
    return safe_name(f"sonic-forge-{word}-{short}{suffix}", "sonic-forge-audio.wav")


def archive_name(now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    return f"sonic-forge-{stamp}.zip"


def plan(resolve, asset_ids: Iterable[str]) -> list[Entry]:
    """何を詰めるかを先に決める。詰めながら気づくのでは遅い。

    `resolve(asset_id)` は (asset, path) を返すか、見つからなければ KeyError を
    投げる。重複した id は 1 件に畳み、名前がぶつかったら連番を付ける——同じ
    名前で 2 つ書き込むと、展開したとき片方が消える。
    """
    ordered: list[str] = []
    seen: set[str] = set()
    for asset_id in asset_ids:
        value = str(asset_id or "")
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    if not ordered:
        raise DownloadRefused("download_empty", "持ち出す音が選ばれていません")
    if len(ordered) > MAX_ASSETS:
        raise DownloadRefused(
            "download_too_many",
            f"一度に持ち出せるのは {MAX_ASSETS} 件までです（{len(ordered)} 件選ばれています）",
        )

    entries: list[Entry] = []
    used: set[str] = set()
    total = 0
    for asset_id in ordered:
        try:
            asset, path = resolve(asset_id)
        except KeyError as exc:
            raise DownloadRefused("asset_not_found", f"{asset_id} が見つかりません") from exc
        if not path.is_file():
            raise DownloadRefused("asset_not_found", f"{asset_id} の中身がありません")
        name = suggested_name(asset)
        stem, dot, suffix = name.rpartition(".")
        if not dot:
            stem, suffix = name, ""
        candidate = name
        bump = 2
        while candidate.lower() in used:
            candidate = f"{stem}-{bump}{'.' + suffix if suffix else ''}"
            bump += 1
        used.add(candidate.lower())
        size = int(asset.size_bytes or 0)
        total += size
        entries.append(Entry(asset_id, path, candidate, size))

    if total > MAX_TOTAL_BYTES:
        raise DownloadRefused(
            "download_too_large",
            f"合計 {total // 1024 // 1024} MB は一度に持ち出せる大きさを超えています",
        )
    return entries


def build(entries: list[Entry], target: Path) -> Path:
    """zip を作る。

    wav は圧縮が効くが、かけない。押した先で待たされる経路なので、待ち時間を
    伸ばすほうが損である。回線より、携帯の前で待つ時間のほうが痛い。
    """
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for entry in entries:
            archive.write(entry.path, arcname=entry.name)
    return target


# 返し終えた zip は消すが、途中で落ちたぶんは残る。残ったまま溜まると、置き場が
# 静かに膨らむ。作る前に古いものを掃く——掃除のためだけに別の仕掛けを増やさない。
STALE_AFTER_SEC = 3600


def sweep(directory: Path, now: float, max_age_sec: int = STALE_AFTER_SEC) -> int:
    """置き場に残った古い zip を消す。消した数を返す。"""
    if not directory.is_dir():
        return 0
    removed = 0
    for path in directory.glob("*.zip"):
        try:
            if now - path.stat().st_mtime < max_age_sec:
                continue
            path.unlink()
        except OSError:
            continue
        removed += 1
    return removed
