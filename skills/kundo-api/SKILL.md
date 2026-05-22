---
name: kundo-api
description: "Query the Kundo API for tickets, threads, events, and contacts."
---

# Kundo API (ärende-data)

The full endpoint catalog, every field, every gotcha, error shapes, and the Stillma test fixtures are in [REFERENCE.md](REFERENCE.md). Read it before constructing any non-trivial request — the public schema is leaner than newcomers expect.

Upstream sources of truth:

- **Swagger UI**: https://api.kundo.app/docs
- **OpenAPI spec**: https://api.kundo.app/openapi.json

Base URL: `https://api.kundo.app`. All endpoints GET, JSON responses, list envelope `{count, data: [...]}`, single envelope `{data: {...}}`.

## When NOT to use

- **Help-center articles** → `kundo-helpcenter-api` skill (different auth, cookie-based).
- **Forum / dialog posts** → legacy public API at `kundo.se/api-doc/` (separate `?key=` query auth). The `kundo-api` skill does NOT cover that.
- **Creating or modifying tickets** → this API is read-only. No POST/PUT/DELETE on tickets.

## Auth

- **Header**: `Token: <api-key>`. NOT `Authorization: Bearer …`. Wrong header → 401 `{"detail":"Authentication required"}`.
- **Resolution order** (every script uses this):
  1. `$KUNDO_API_TOKEN` — preferred for shells and Cowork.
  2. `~/.kundo/credentials.json` (file mode 0600) — for multi-org use in Claude Code.
  3. **Onboarding wizard** if neither is set — `python3 scripts/kapi.py onboard --token <pasted-key>` smoke-tests `/v1/me`, discovers the bound org, and persists.

### First-run onboarding (the customer flow)

When a user first asks to query the API and no token is resolvable, say exactly this and stop:

> Get an API key by following these instructions: https://www.kundo.se/hjalp-support?path=%2Fguide%2Fapi-for-arende-data#Hur_kommerjagigng
>
> Then paste the key here and I'll take care of the rest.

When they paste the key:

1. Run `python3 .claude/skills/kundo-api/scripts/kapi.py onboard --token <pasted-key>`. It hits `/v1/me`, discovers the bound `organization_id`, and writes `~/.kundo/credentials.json` (mode 0600).
2. Confirm the org name back to the user using the bound id.

Do NOT ask the user for their `org_id` — the token reveals it. Do NOT walk them through the dashboard UI yourself — the help-center guide does that.

In Claude Cowork (no local file writes), tell the user to set `KUNDO_API_TOKEN=<value>` in their environment instead of running `onboard`.

## Quick recipes

```sh
# Auth check — what org does this token belong to?
curl -s -H "Token: $KUNDO_API_TOKEN" https://api.kundo.app/v1/me
# → {"id":"<token-name>","organization_id":"<org_id_as_string>"}

# 10 most recently created tickets, with title + status
curl -s -H "Token: $KUNDO_API_TOKEN" \
  "https://api.kundo.app/v1/tickets?limit=10&sort=-created_at&fields=id,created_at,title,status,channel"

# Single ticket with assignee + tags
curl -s -H "Token: $KUNDO_API_TOKEN" \
  "https://api.kundo.app/v1/tickets/<uuid>?fields=id,title,status,assignee_id,tags,editors,contacts"

# Email thread for one ticket
curl -s -H "Token: $KUNDO_API_TOKEN" \
  "https://api.kundo.app/v1/tickets/<uuid>/messages/email?fields=id,created_at,editor_id,contact_id,content"

# Who reassigned this ticket?
curl -s -H "Token: $KUNDO_API_TOKEN" \
  "https://api.kundo.app/v1/tickets/<uuid>/events?fields=event_type,event_data,user_id,triggered_by,created_at&event_types=assign"
```

Or via the CLI wrapper (handles auth resolution + pretty-printing):

```sh
python3 .claude/skills/kundo-api/scripts/kapi.py me
python3 .claude/skills/kundo-api/scripts/kapi.py tickets --limit 10 --sort=-created_at
python3 .claude/skills/kundo-api/scripts/kapi.py ticket <uuid>
python3 .claude/skills/kundo-api/scripts/kapi.py messages <uuid>
python3 .claude/skills/kundo-api/scripts/kapi.py events <uuid> --event-types assign
```

Use `--sort=-created_at` (with `=`), not `--sort -created_at` — argparse treats a leading dash as a flag.

## Critical rules

- **Default response is bare**. Without `?fields=`, you get only `id`. Always pass `fields=` listing what you need. Unknown field names are silently ignored — no error, just missing data. Double-check spelling against [REFERENCE.md](REFERENCE.md).
- **No `status` filter on `/v1/tickets`**. Returns 422 `"Parameter 'status' does not exist."`. Filter client-side after fetching `fields=...,status`.
- **`csat` field on single-ticket can return HTTP 500** on some tickets. If you need CSAT, request it in its own call and tolerate the 500 (treat as "no CSAT available").
- **Events strip `event_data` and `user_id` by default**. Without `fields=event_type,event_data,user_id,triggered_by,created_at`, the response is useless.
- **`/v1/tickets/messages/email` caps `limit` at 50** (everything else caps at 500).
- **EmailMessage `id` is usually `null`**. You can't address individual messages by id; identify them by `created_at` + `editor_id`/`contact_id`.
- **PII**: email message `content` is full raw HTML including signatures and quoted threads. Don't echo verbatim into shared transcripts; summarize or redact.

The full list — including error envelope shapes, channel-type vs Django enum mismatches, `num_messages` discrepancies, and the editor/contact symmetry quirk — is in [REFERENCE.md](REFERENCE.md).

## Known orgs

| `org_id` | Name |
|---|---|
| 1 | Kundo |
| 1320 | ExperTent |
| 1888 | Stillma (DEMO — safe to query freely) |

Stillma test fixtures (channel ids, sample ticket UUIDs) live in [REFERENCE.md](REFERENCE.md#reference-data--stillma-test-fixtures).

## Cowork / portability note

This skill works in Claude Cowork (claude.ai) too — every recipe above is plain `curl`. The differences:

- **No `~/.kundo/credentials.json`**. Set `$KUNDO_API_TOKEN` in the session/environment instead.
- **No Playwright onboarding**. Walk the user through the dashboard manually (the 4 steps above) and have them paste the token.
- **`scripts/kapi.py` still works** if Python is available — it just falls back to env-only mode when `~/.kundo/` isn't writable.
