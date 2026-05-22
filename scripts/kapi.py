#!/usr/bin/env python3
"""Kundo ärende-data API CLI.

Subcommands:
    me                          show /v1/me (token sanity check)
    tickets                     list tickets (filters: --limit, --sort, --channel-id, --tags, --created-gt/lt, --fields)
    ticket <uuid>               single ticket details
    messages <uuid>             email thread for a ticket
    events <uuid>               audit log for a ticket (filters: --event-types, --limit, --sort)
    channels                    list channels
    users                       list editors (Kundo staff)
    contacts                    list contacts (end-users)
    onboard                     interactive token setup; org is auto-discovered from the token via /v1/me. --token <value> to skip the paste prompt

Auth resolution (every command):
    1. $KUNDO_API_TOKEN
    2. ~/.kundo/credentials.json: {"default_org_id": int, "tokens": {"<org_id>": {"token": "...", ...}}}
       Pass --org <id> to pick a specific org; otherwise default_org_id is used.
    3. Onboarding wizard if neither is set.

Examples:
    kapi.py me
    kapi.py tickets --limit 10 --sort -created_at --fields id,created_at,title,status
    kapi.py ticket 019df21c-1022-758c-bd4e-64c077db35b8
    kapi.py messages 019df21c-1022-758c-bd4e-64c077db35b8
    kapi.py events 019df21c-1022-758c-bd4e-64c077db35b8 --event-types assign,update_status
    kapi.py onboard
"""

import argparse
import json
import os
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.kundo.app"
CREDS_PATH = Path.home() / ".kundo" / "credentials.json"
TOKEN_GUIDE = "https://www.kundo.se/hjalp-support?path=%2Fguide%2Fapi-for-arende-data#Hur_kommerjagigng"

DEFAULT_TICKET_FIELDS = "id,created_at,channel,title,url,status,num_messages,incoming,assignee_id,tags,editors,contacts"
DEFAULT_EVENT_FIELDS = "event_type,event_data,user_id,triggered_by,created_at"
DEFAULT_MESSAGE_FIELDS = "id,created_at,editor_id,contact_id,content"


def _read_creds_file():
    if not CREDS_PATH.exists():
        return None
    try:
        return json.loads(CREDS_PATH.read_text())
    except json.JSONDecodeError:
        return None


def _write_creds_file(data):
    CREDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CREDS_PATH.write_text(json.dumps(data, indent=2))
    CREDS_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)


def resolve_token(prefer_org=None):
    """Return (token, source-description). Raises SystemExit with onboarding hint if missing."""
    env = os.environ.get("KUNDO_API_TOKEN")
    if env:
        return env, "$KUNDO_API_TOKEN"

    creds = _read_creds_file()
    if creds and creds.get("tokens"):
        org = str(prefer_org) if prefer_org else str(creds.get("default_org_id") or "")
        if org and org in creds["tokens"]:
            return creds["tokens"][org]["token"], f"~/.kundo/credentials.json (org {org})"
        if not prefer_org and len(creds["tokens"]) == 1:
            only = next(iter(creds["tokens"].items()))
            return only[1]["token"], f"~/.kundo/credentials.json (org {only[0]})"

    hint = "No Kundo API token found.\n"
    hint += "  - Set $KUNDO_API_TOKEN, or\n"
    hint += f"  - Run: python3 {sys.argv[0]} onboard\n"
    hint += f"  - Get a token by following: {TOKEN_GUIDE}\n"
    print(hint, file=sys.stderr)
    sys.exit(2)


def _request(path, token, params=None):
    url = BASE + path
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)
    req = urllib.request.Request(url, headers={"Token": token, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.getcode(), json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(body)
        except Exception:
            pass
        return e.code, body


def _print(obj):
    json.dump(obj, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _bail(code, body):
    print(f"HTTP {code}", file=sys.stderr)
    if isinstance(body, (dict, list)):
        json.dump(body, sys.stderr, indent=2, ensure_ascii=False)
        sys.stderr.write("\n")
    else:
        sys.stderr.write(str(body) + "\n")
    sys.exit(1)


def cmd_me(args):
    token, source = resolve_token(args.org)
    code, body = _request("/v1/me", token)
    if code != 200:
        _bail(code, body)
    body["_source"] = source
    _print(body)


def cmd_tickets(args):
    token, _ = resolve_token(args.org)
    params = {
        "fields": args.fields,
        "limit": args.limit,
        "offset": args.offset,
        "sort": args.sort,
        "ids": args.ids,
        "channel_ids": args.channel_id,
        "tags": args.tags,
        "created_gt": args.created_gt,
        "created_lt": args.created_lt,
        "created_gte": args.created_gte,
        "created_lte": args.created_lte,
    }
    code, body = _request("/v1/tickets", token, params)
    if code != 200:
        _bail(code, body)
    _print(body)


def cmd_ticket(args):
    token, _ = resolve_token(args.org)
    code, body = _request(f"/v1/tickets/{args.ticket_id}", token, {"fields": args.fields})
    if code != 200:
        _bail(code, body)
    _print(body)


def cmd_messages(args):
    token, _ = resolve_token(args.org)
    code, body = _request(
        f"/v1/tickets/{args.ticket_id}/messages/email",
        token,
        {"fields": args.fields, "limit": args.limit, "offset": args.offset},
    )
    if code != 200:
        _bail(code, body)
    _print(body)


def cmd_events(args):
    token, _ = resolve_token(args.org)
    code, body = _request(
        f"/v1/tickets/{args.ticket_id}/events",
        token,
        {
            "fields": args.fields,
            "limit": args.limit,
            "offset": args.offset,
            "sort": args.sort,
            "event_types": args.event_types,
        },
    )
    if code != 200:
        _bail(code, body)
    _print(body)


def cmd_channels(args):
    token, _ = resolve_token(args.org)
    code, body = _request("/v1/channels", token, {
        "fields": args.fields, "limit": args.limit, "offset": args.offset,
        "sort": args.sort, "ids": args.ids,
    })
    if code != 200:
        _bail(code, body)
    _print(body)


def cmd_users(args):
    token, _ = resolve_token(args.org)
    code, body = _request("/v1/users", token, {
        "fields": args.fields, "limit": args.limit, "offset": args.offset,
        "sort": args.sort, "ids": args.ids, "emails": args.emails,
    })
    if code != 200:
        _bail(code, body)
    _print(body)


def cmd_contacts(args):
    token, _ = resolve_token(args.org)
    code, body = _request("/v1/contacts", token, {
        "fields": args.fields, "limit": args.limit, "offset": args.offset,
        "sort": args.sort, "ids": args.ids, "emails": args.emails,
    })
    if code != 200:
        _bail(code, body)
    _print(body)


def cmd_onboard(args):
    """Persist a token and discover the bound org via /v1/me."""
    print("\nKundo API onboarding")
    print("─" * 60)
    print(f"Need a token? Follow: {TOKEN_GUIDE}\n")

    token = args.token
    if not token:
        try:
            token = input("Paste token here: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.", file=sys.stderr)
            sys.exit(1)
    if not token:
        print("No token entered.", file=sys.stderr)
        sys.exit(1)

    print("\nSmoke-testing /v1/me ...")
    code, body = _request("/v1/me", token)
    if code != 200:
        print(f"  ✗ HTTP {code}: {body}", file=sys.stderr)
        print("  Token rejected. Check the value and try again.", file=sys.stderr)
        sys.exit(1)
    bound_org = body.get("organization_id")
    print(f"  ✓ Token valid. Bound to org {bound_org} (token name: {body.get('id')}).")

    creds = _read_creds_file() or {"tokens": {}}
    creds.setdefault("tokens", {})
    creds["tokens"][str(bound_org)] = {
        "token": token,
        "name": body.get("id"),
        "smoke_test_passed_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }
    creds.setdefault("default_org_id", int(bound_org))
    _write_creds_file(creds)
    print(f"  ✓ Stored in {CREDS_PATH} (mode 0600).")
    print(f"\nDone. Try: python3 {sys.argv[0]} tickets --limit 3")
    print(f"Or:        export KUNDO_API_TOKEN={token}")


def main():
    p = argparse.ArgumentParser(prog="kapi", description="Kundo ärende-data API CLI")
    p.add_argument("--org", type=int, help="Org id for token selection (default: credentials default_org_id)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("me", help="Token sanity check (/v1/me)")
    sp.set_defaults(func=cmd_me)

    sp = sub.add_parser("tickets", help="List tickets")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--offset", type=int)
    sp.add_argument("--sort", choices=["created_at", "-created_at"])
    sp.add_argument("--fields", default=DEFAULT_TICKET_FIELDS)
    sp.add_argument("--ids", help="CSV UUIDs")
    sp.add_argument("--channel-id", dest="channel_id", help="CSV channel UUIDs")
    sp.add_argument("--tags", help="CSV tag slugs")
    sp.add_argument("--created-gt", dest="created_gt")
    sp.add_argument("--created-lt", dest="created_lt")
    sp.add_argument("--created-gte", dest="created_gte")
    sp.add_argument("--created-lte", dest="created_lte")
    sp.set_defaults(func=cmd_tickets)

    sp = sub.add_parser("ticket", help="Single ticket details")
    sp.add_argument("ticket_id")
    sp.add_argument("--fields", default=DEFAULT_TICKET_FIELDS,
                    help="Note: do NOT include 'csat' unless you can tolerate HTTP 500 on some tickets.")
    sp.set_defaults(func=cmd_ticket)

    sp = sub.add_parser("messages", help="Email thread for a ticket")
    sp.add_argument("ticket_id")
    sp.add_argument("--limit", type=int, default=50, help="Max 50 (API hard cap).")
    sp.add_argument("--offset", type=int)
    sp.add_argument("--fields", default=DEFAULT_MESSAGE_FIELDS)
    sp.set_defaults(func=cmd_messages)

    sp = sub.add_parser("events", help="Audit log for a ticket")
    sp.add_argument("ticket_id")
    sp.add_argument("--limit", type=int, default=100)
    sp.add_argument("--offset", type=int)
    sp.add_argument("--sort", choices=["created_at", "-created_at"], default="-created_at")
    sp.add_argument("--event-types", dest="event_types",
                    help="CSV: assign, update_status, modify_tags, set_priority, forward_email, move_to_email_channel")
    sp.add_argument("--fields", default=DEFAULT_EVENT_FIELDS)
    sp.set_defaults(func=cmd_events)

    sp = sub.add_parser("channels", help="List channels")
    sp.add_argument("--limit", type=int, default=50)
    sp.add_argument("--offset", type=int)
    sp.add_argument("--sort", choices=["name", "-name"])
    sp.add_argument("--ids")
    sp.add_argument("--fields", default="id,name,type")
    sp.set_defaults(func=cmd_channels)

    sp = sub.add_parser("users", help="List editors (Kundo staff)")
    sp.add_argument("--limit", type=int, default=50)
    sp.add_argument("--offset", type=int)
    sp.add_argument("--sort", choices=["name"])
    sp.add_argument("--ids")
    sp.add_argument("--emails")
    sp.add_argument("--fields", default="id,name,email")
    sp.set_defaults(func=cmd_users)

    sp = sub.add_parser("contacts", help="List contacts (end-users)")
    sp.add_argument("--limit", type=int, default=50)
    sp.add_argument("--offset", type=int)
    sp.add_argument("--sort", choices=["name"])
    sp.add_argument("--ids")
    sp.add_argument("--emails")
    sp.add_argument("--fields", default="id,name,email")
    sp.set_defaults(func=cmd_contacts)

    sp = sub.add_parser("onboard", help="Persist a token and auto-discover its org via /v1/me")
    sp.add_argument("--token", help="Skip the paste prompt; pass the token inline")
    sp.set_defaults(func=cmd_onboard)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
