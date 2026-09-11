"""道具の説明の書き方を縛る。

規約は ControlDeck の docs/addon-agent-tool-writing.md にある。ここでは
機械で見られるところだけを検査する。

なぜ要るか: 2026-09-11 に数えたとき、MediaForge と SonicForge の 22 個のうち
11 個は label 一行だけで、用途の説明が無かった。ローカルモデル（Qwen3.8-27B）で
測ると、誤って選ばれた道具は全部その側だった。音声を文字に起こす依頼で、
モデルは SonicForge ではなく MediaForge の inspect を選んだ。sonic.transcribe の
説明は「Transcribe audio」の 36 文字しかなかった。

Haiku では同じ題が通る。書いていないことを名前から補えるかどうかの差で、
補えないモデルのほうが多い。
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]

IMPLEMENTATION_WORDS = ("typed", "durable", "bounded", "owner-scoped", "immutable", "detached")
READ_ONLY_TOOLS = {"sonic.capabilities", "sonic.inspect", "sonic.voice.list"}
LABEL_LIMIT = 80
DESCRIPTION_MINIMUM = 120


def agent_tools():
    manifest = json.loads((ROOT / "addon.json").read_text(encoding="utf-8"))
    return manifest["contributions"]["agent_tools"]


def schema_of(tool):
    return json.loads((ROOT / str(tool["schema_path"]).lstrip("/")).read_text(encoding="utf-8"))


def label_of(tool):
    label = tool["label"]
    if isinstance(label, dict):
        return label.get("en") or label.get("ja") or tool["id"]
    return label


@pytest.mark.parametrize("tool", agent_tools(), ids=lambda t: t["id"])
def test_the_label_says_what_the_tool_does_without_implementation_words(tool):
    label = label_of(tool)
    assert len(label) <= LABEL_LIMIT, f"{tool['id']}: labelが長い（{len(label)}文字）"
    leaked = [word for word in IMPLEMENTATION_WORDS if word in label.lower()]
    assert not leaked, f"{tool['id']}: 呼ぶ側の語ではない: {leaked}"


@pytest.mark.parametrize("tool", agent_tools(), ids=lambda t: t["id"])
def test_every_agent_tool_says_what_it_is_for(tool):
    description = schema_of(tool).get("description")
    assert isinstance(description, str) and description.strip(), (
        f"{tool['id']}: 入力schemaにtop-level descriptionが無い。"
        "一覧に出る説明がlabel一行だけになる"
    )
    assert len(description) >= DESCRIPTION_MINIMUM, (
        f"{tool['id']}: 説明が{len(description)}文字しかない。"
        "何のためか・いつ呼ぶか・何に使わないかを書く"
    )


@pytest.mark.parametrize(
    "tool", [t for t in agent_tools() if t["id"] in READ_ONLY_TOOLS], ids=lambda t: t["id"]
)
def test_a_read_only_tool_says_what_it_is_not_for(tool):
    """読むだけの道具は、行動する道具の代わりに選ばれる。名指しで断る。"""
    description = schema_of(tool)["description"]
    # 説明は英語で書く。日本語より同じ内容で 1〜2 割安く、MediaForge 側と揃う。
    assert any(phrase in description for phrase in
               ("does not", "changes nothing", "makes nothing", "creates nothing", "not this")), (
        f"{tool['id']}: 「何をしない道具か」が書かれていない"
    )
    assert any(other["id"] in description for other in agent_tools()
               if other["id"] != tool["id"]), (
        f"{tool['id']}: 代わりに呼ぶべき道具を名指ししていない"
    )


def test_two_tools_never_share_one_input_schema():
    seen: dict[str, str] = {}
    for tool in agent_tools():
        path = str(tool["schema_path"])
        assert path not in seen, (
            f"{tool['id']} と {seen[path]} が {path} を共有している。分けること"
        )
        seen[path] = tool["id"]
