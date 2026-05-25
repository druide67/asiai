"""CLI handlers for ``asiai auth`` subcommands.

The auth surface manages API tokens used by remote orchestrators to call
fleet write commands. Plaintext secrets are shown EXACTLY ONCE at
``init`` / ``create`` / ``rotate`` time and never persisted unhashed.
"""

from __future__ import annotations

import argparse
import json as _json
import sys
import time
from typing import Any

from asiai.auth import config as auth_config
from asiai.display.formatters import bold, dim, green, red, yellow


def _format_ts(unix_ts: int | None) -> str:
    if unix_ts is None:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(unix_ts)))


def _print_secret_once(token_id: str, secret: str, *, action: str) -> None:
    """Print a freshly-minted secret with a clear one-shot warning."""
    print(green(f"✓ {action} token {token_id}"))
    print()
    print(bold("  Secret (shown ONCE — copy it now):"))
    print(f"    {secret}")
    print()
    print(
        dim(
            "  Store it in your orchestrator's fleet.json:\n"
            f"    asiai fleet add <nickname> --url <node-url> --auth-token {secret}\n"
            "  Or save it to a secret manager. asiai will never display it again."
        )
    )


def _cmd_init(args: argparse.Namespace) -> int:
    created, token_id, secret = auth_config.init_auth(force=args.force)
    if not created:
        if args.json:
            print(_json.dumps({"created": False, "reason": "already_initialized"}))
        else:
            print(yellow("auth.json already holds at least one live token; nothing to do."))
            print(dim("  use 'asiai auth create' to add another, or --force to add one anyway."))
        return 1 if not args.force else 0
    if args.json:
        print(_json.dumps({"created": True, "token_id": token_id, "secret": secret}))
    else:
        _print_secret_once(token_id or "?", secret or "?", action="created initial")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    tokens = auth_config.list_tokens()
    if args.json:
        print(_json.dumps({"tokens": tokens}, indent=2))
        return 0
    if not tokens:
        print(dim("no tokens configured (run 'asiai auth init')"))
        return 0
    print(bold(f"{'ID':<18} {'LABEL':<24} {'CREATED':<18} {'LAST USED':<18} STATUS"))
    for t in tokens:
        status = red("revoked") if t.get("revoked_at") else green("active")
        print(
            f"{t.get('id', '?'):<18} "
            f"{(t.get('label') or '—'):<24} "
            f"{_format_ts(t.get('created_at')):<18} "
            f"{_format_ts(t.get('last_used_at')):<18} "
            f"{status}"
        )
    return 0


def _cmd_create(args: argparse.Namespace) -> int:
    try:
        token_id, secret = auth_config.create_token(label=args.label or "")
    except ValueError as e:
        print(red(f"✗ {e}"), file=sys.stderr)
        return 1
    except OSError as e:
        print(red(f"✗ failed to save: {e}"), file=sys.stderr)
        return 1
    if args.json:
        print(_json.dumps({"token_id": token_id, "secret": secret}))
    else:
        _print_secret_once(token_id, secret, action="created")
    return 0


def _cmd_rotate(args: argparse.Namespace) -> int:
    result = auth_config.rotate_token(args.token_id, label=args.label)
    if result is None:
        if args.json:
            print(_json.dumps({"rotated": False, "reason": "not_found_or_revoked"}))
        else:
            print(red(f"✗ token {args.token_id} not found or already revoked"), file=sys.stderr)
        return 1
    new_id, new_secret = result
    if args.json:
        print(
            _json.dumps(
                {
                    "rotated": True,
                    "old_token_id": args.token_id,
                    "new_token_id": new_id,
                    "secret": new_secret,
                }
            )
        )
    else:
        print(dim(f"  revoked {args.token_id}"))
        _print_secret_once(new_id, new_secret, action="rotated to")
    return 0


def _cmd_revoke(args: argparse.Namespace) -> int:
    ok = auth_config.revoke_token(args.token_id)
    if not ok:
        if args.json:
            print(_json.dumps({"revoked": False, "reason": "not_found_or_already_revoked"}))
        else:
            print(red(f"✗ token {args.token_id} not found or already revoked"), file=sys.stderr)
        return 1
    if args.json:
        print(_json.dumps({"revoked": True, "token_id": args.token_id}))
    else:
        print(green(f"✓ revoked token {args.token_id}"))
    return 0


def cmd_auth(args: argparse.Namespace) -> int:
    """Dispatch ``asiai auth <action>`` to the matching handler."""
    action = getattr(args, "action", None)
    handlers: dict[str, Any] = {
        "init": _cmd_init,
        "list": _cmd_list,
        "create": _cmd_create,
        "rotate": _cmd_rotate,
        "revoke": _cmd_revoke,
    }
    handler = handlers.get(action)
    if handler is None:
        print(red("usage: asiai auth {init,list,create,rotate,revoke}"), file=sys.stderr)
        return 2
    return handler(args)


def add_auth_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``auth`` parser and its sub-actions on ``subparsers``."""
    auth_parser = subparsers.add_parser(
        "auth",
        help="Manage API tokens for fleet write commands (Phase 2).",
    )
    auth_sub = auth_parser.add_subparsers(dest="action", metavar="<action>")

    p_init = auth_sub.add_parser(
        "init",
        help="Initialize auth.json and print the first token (run once per node).",
    )
    p_init.add_argument("--force", action="store_true", help="Add a token even if one exists.")
    p_init.add_argument("--json", action="store_true")

    p_list = auth_sub.add_parser("list", help="List configured tokens (no secrets shown).")
    p_list.add_argument("--json", action="store_true")

    p_create = auth_sub.add_parser("create", help="Create a new token.")
    p_create.add_argument(
        "--label", default="", help="Free-text label, e.g. 'orchestrator-laptop'."
    )
    p_create.add_argument("--json", action="store_true")

    p_rotate = auth_sub.add_parser(
        "rotate",
        help="Revoke a token and create a replacement (returns the new secret).",
    )
    p_rotate.add_argument("token_id")
    p_rotate.add_argument("--label", default=None, help="Override label on the replacement.")
    p_rotate.add_argument("--json", action="store_true")

    p_revoke = auth_sub.add_parser("revoke", help="Revoke a token without replacing it.")
    p_revoke.add_argument("token_id")
    p_revoke.add_argument("--json", action="store_true")
