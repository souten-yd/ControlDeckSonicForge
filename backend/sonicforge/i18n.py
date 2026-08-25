from __future__ import annotations
MESSAGES={"ja":{"setup_required":"音声基本環境のセットアップが必要です","healthy":"SonicForge は利用可能です","job_queued":"処理を受け付けました"},"en":{"setup_required":"Speech Essentials setup is required","healthy":"SonicForge is available","job_queued":"Job queued"}}
def normalize_locale(value:str|None)->str:
    if value and value.lower().startswith("en"): return "en"
    return "ja"
def tr(key:str,locale:str="ja")->str: return MESSAGES.get(locale,MESSAGES["ja"]).get(key,key)
