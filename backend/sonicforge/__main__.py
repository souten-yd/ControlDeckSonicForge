from __future__ import annotations

import argparse
import json
import sys
import uvicorn

from .config import ensure_directories, load_settings
from .db import make_session_factory
from . import setup as setup_service


def doctor() -> int:
    settings = load_settings()
    info = setup_service.plan(settings, "speech-essentials")
    print(json.dumps({"ok": True, "read_only": True, **info}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="sonic-forge")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve")
    sub.add_parser("doctor")
    provision = sub.add_parser("provision")
    provision.add_argument("--profile", default="speech-essentials")
    args = parser.parse_args()
    settings = load_settings()
    ensure_directories(settings)
    if args.command == "doctor":
        return doctor()
    if args.command == "serve":
        uvicorn.run("sonicforge.app:app", host=settings.host, port=settings.port, log_level="info")
        return 0
    if args.command == "provision":
        import asyncio
        factory = make_session_factory(settings)
        with factory() as session:
            result = asyncio.run(setup_service.apply(settings, session, args.profile))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
