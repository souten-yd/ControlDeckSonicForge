from __future__ import annotations

import argparse
import json
import sys
import uvicorn

from .config import Settings, ensure_directories, load_settings
from .db import make_session_factory
from . import setup as setup_service


SETUP_PROFILES = tuple(setup_service.PROFILE_COMPONENTS)
SETUP_COMPONENTS = ("speech-essentials", "gpt-sovits", "game-audio", "music")


def _apply_arguments(parser: argparse.ArgumentParser, *, positional: bool) -> None:
    if positional:
        parser.add_argument(
            "profile",
            nargs="?",
            choices=SETUP_PROFILES,
            default="speech-essentials",
        )
    else:
        parser.add_argument(
            "--profile", choices=SETUP_PROFILES, default="speech-essentials"
        )
    parser.add_argument("--component", action="append", choices=SETUP_COMPONENTS)
    parser.add_argument(
        "--accept-term",
        action="append",
        choices=(setup_service.STABILITY_TERMS,),
        default=[],
    )


def _apply_setup(settings: Settings, args: argparse.Namespace) -> dict:
    import asyncio

    factory = make_session_factory(settings)
    with factory() as session:
        return asyncio.run(
            setup_service.apply(
                settings,
                session,
                args.profile,
                args.component,
                accepted_terms=args.accept_term,
            )
        )


def _run_setup_apply(settings: Settings, args: argparse.Namespace) -> int:
    try:
        result = _apply_setup(settings, args)
    except setup_service.SetupError as exc:
        print(
            json.dumps(
                {"ok": False, "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


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
    setup = sub.add_parser("setup")
    setup_sub = setup.add_subparsers(dest="setup_command", required=True)
    setup_plan = setup_sub.add_parser("plan")
    setup_plan.add_argument(
        "profile", nargs="?", choices=SETUP_PROFILES, default="speech-essentials"
    )
    setup_plan.add_argument("--component", action="append", choices=SETUP_COMPONENTS)
    setup_apply = setup_sub.add_parser("apply")
    _apply_arguments(setup_apply, positional=True)
    setup_repair = setup_sub.add_parser("repair")
    setup_repair.add_argument("component", choices=SETUP_COMPONENTS)
    setup_repair.add_argument(
        "--accept-term",
        action="append",
        choices=(setup_service.STABILITY_TERMS,),
        default=[],
    )
    provision = sub.add_parser("provision")
    _apply_arguments(provision, positional=False)
    args = parser.parse_args()
    settings = load_settings()
    ensure_directories(settings)
    if args.command == "doctor":
        return doctor()
    if args.command == "serve":
        uvicorn.run(
            "sonicforge.bootstrap:app",
            host=settings.host,
            port=settings.port,
            log_level="info",
            timeout_graceful_shutdown=15,
        )
        return 0
    if args.command == "setup" and args.setup_command == "plan":
        result = setup_service.plan(settings, args.profile, args.component)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "setup" and args.setup_command == "repair":
        args.profile = "custom"
        args.component = [args.component]
        return _run_setup_apply(settings, args)
    if args.command == "setup" and args.setup_command == "apply":
        return _run_setup_apply(settings, args)
    if args.command == "provision":
        return _run_setup_apply(settings, args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
