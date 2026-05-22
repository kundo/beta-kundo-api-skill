# Kundo API — full reference

Verified against `https://api.kundo.app/openapi.json` and live smoke-tests on org 1888 (Stillma DEMO) on 2026-05-20.

- Base URL: **`https://api.kundo.app`**
- Interactive docs (Swagger UI): https://api.kundo.app/docs
- OpenAPI spec: https://api.kundo.app/openapi.json
- All endpoints are GET unless noted; all return JSON.

## Authentication

| | |
|---|---|
| Header name | **`Token`** |
| Header value | the 32-char hex API key |
| Scheme | apiKey-in-header (NOT Bearer / NOT `Authorization`) |
| Error if missing/invalid | `401 {"detail": "Authentication required"}` |
| Scope | one organization per token (the org the token was issued for) |

```sh
curl -H "Token: a91b2ce5..." https://api.kundo.app/v1/me
```

### Where customers create a token

Customers should follow the help-center guide: https://www.kundo.se/hjalp-support?path=%2Fguide%2Fapi-for-arende-data#Hur_kommerjagigng

Under the hood that walks them to `https://kundo.app/account/<org_id>/integrations/` → **Generera API-nyckel** → name it → **Spara** → the 32-char `token` is shown ONCE in the **Notera! Detta är den enda gången du kommer kunna se denna API-nyckel** dialog. Default expiry: **2 years**. Required permission: organization editor / EDIT_ACCOUNT_SETTINGS.

The token-creation endpoint (BFF) is `POST /bff/integrations/organization/<org_id>/auth-tokens/` with `{"name": "..."}`. The skill doesn't call this directly — the human-in-dashboard step is the supported flow.

### `/v1/me` — auth check

```
GET /v1/me
```

```json
{"id": "claude-cli-test", "organization_id": "1888"}
```

- `id`: the token's display name (NOT a UUID, despite the schema hint).
- `organization_id`: the org id as a **string** (e.g. `"1888"`, not `1888`).
- Use this as a "ping" to verify a token is alive and to discover which org it's bound to.

## Common request conventions

All read endpoints share:

| Param | Type | Default | Notes |
|---|---|---|---|
| `fields` | CSV string | (returns only `id`) | Unknown names silently dropped, no error. |
| `limit` | int | 100 | Max 500 (except `messages/email`, max 50). 0 → 422. |
| `offset` | int | 0 | Plain offset pagination. |
| `sort` | enum | endpoint-specific | See per-endpoint table. |
| `ids` | CSV UUIDs | — | Filter by id list. |

Response envelope:

- List: `{"count": <total-after-filtering>, "data": [...]}`
- Single object: `{"data": {...}}`

## Endpoints

### `GET /v1/tickets` — list tickets

Filters:

| Param | Type | Notes |
|---|---|---|
| `ids` | CSV UUIDs | |
| `channel_ids` | CSV UUIDs | UUIDs from `/v1/channels`. |
| `tags` | CSV strings | Tag slugs. Empty result if none match — no error. |
| `created_gt` / `_lt` / `_gte` / `_lte` | ISO 8601 datetime | Inclusive/exclusive comparisons. |
| `sort` | `created_at` \| `-created_at` | No `updated_at` sort available. |
| `fields`, `limit`, `offset` | — | See common. |

**NOT supported** (returns 422 `Parameter 'X' does not exist.`):
`status`, `updated_*`, `assignee_id`, `assignee_ids`, `editor_*`, `contact_*`. If you need to filter by status, fetch with `fields=...,status` and filter client-side.

Returned `Ticket` fields (all opt-in via `fields=`):

| Field | Type | Notes |
|---|---|---|
| `id` | UUID string | Always present. |
| `created_at` | ISO 8601 (UTC, with `Z`, microsecond precision) | |
| `channel` | `{id: uuid, type: string}` | `type` ∈ `email`, `chat`, `ai_assistant`, `calls`, `knowledgebase`, `forum`, … (lowercase). |
| `title` | string | First line of the conversation; may be empty. |
| `url` | string | `https://kundo.app/dashboard/r/<int>` — opens the ticket in dashboard. |
| `status` | enum string | `OPEN`, `WAITING`, `DONE` (uppercase). |
| `num_messages` | int | **May not match** `messages/email` count; treat as advisory. |
| `incoming` | bool? | `true` = contact-initiated, `false` = staff-initiated, `null` = unknown / non-applicable channel (e.g. ai_assistant). |
| `assignee_id` | UUID? | `null` if unassigned. Look up in `/v1/users`. |
| `tags` | string[] | Tag slugs. |
| `editors` | UUID[] | Editors who participated. Look up in `/v1/users`. |
| `contacts` | UUID[] | Contacts (customers) on the ticket. Look up in `/v1/contacts`. |

Example:

```sh
curl -s -H "Token: $TOK" \
  "https://api.kundo.app/v1/tickets?limit=5&sort=-created_at&channel_ids=01985a37-6776-78c4-9c61-ffab15e1f17c&fields=id,created_at,title,status,assignee_id"
```

### `GET /v1/tickets/{ticket_id}` — single ticket

Path param `ticket_id` is the **UUID** from the list endpoint (the `id`).

Same fields as the list endpoint, plus:

| Field | Type | Notes |
|---|---|---|
| `csat` | `{rating: int?, comment: string?}` | ⚠️ Requesting this can return **HTTP 500** `{"detail":"Error fetching ticket"}` for some tickets. Likely a server-side bug when the ticket has no CSAT row. Request it in its own call so a 500 doesn't poison your main fetch. |

Example:

```sh
curl -s -H "Token: $TOK" \
  "https://api.kundo.app/v1/tickets/019df21c-1022-758c-bd4e-64c077db35b8?fields=id,title,status,assignee_id,tags,editors,contacts"
```

### `GET /v1/tickets/{ticket_id}/messages/email` — email thread

Params: `fields`, `limit` (**max 50**, default 50), `offset`. No sort param — fixed order (oldest first).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID? | Almost always `null` in practice — can't address individual messages. |
| `created_at` | ISO 8601 | Seconds precision (no microseconds here, unlike Ticket). |
| `editor_id` | UUID? | Set iff the message was sent by an editor (staff). Look up in `/v1/users`. |
| `contact_id` | UUID? | Set iff the message was sent by a contact (customer). Look up in `/v1/contacts`. |
| `content` | string? | Raw HTML body. Includes signatures, quoted prior emails, embedded image tags. Don't echo verbatim — summarize / redact PII. |

The first message is the original; subsequent entries are the reply chain in chronological order.

### `GET /v1/tickets/{ticket_id}/events` — audit log

Params:

| Param | Notes |
|---|---|
| `event_types` | CSV. Allowed values below. |
| `sort` | `created_at` (default) or `-created_at`. |
| `limit` | max 500, default 100. |
| `fields` | **Critical**: default response is only `event_type` + `created_at`. Pass `fields=event_type,event_data,user_id,triggered_by,created_at` to get anything useful. |

Common fields on every event:

| Field | Type | Notes |
|---|---|---|
| `event_type` | enum | One of the 6 below. |
| `event_data` | object | Shape depends on `event_type` — see table. |
| `user_id` | UUID? | Editor who triggered. `null` when `triggered_by` ≠ `"user"`. |
| `triggered_by` | enum | `"user"` \| `"automatic_rule"` \| `"system"`. |
| `created_at` | ISO 8601 | |

Event types and `event_data` schemas:

| `event_type` | `event_data` |
|---|---|
| `update_status` | `{status: "OPEN" \| "WAITING" \| "DONE"}` |
| `assign` | `{assignee_id: UUID?, message: string?}` — `assignee_id: null` means **unassigned** |
| `forward_email` | `{email: string}` |
| `modify_tags` | `{tags: string[]}` — full new tag list, not a diff |
| `move_to_email_channel` | `{to_email_channel_id: UUID?, from_email_channel_id: UUID?}` |
| `set_priority` | `{priority: "LOW" \| "MEDIUM" \| "HIGH"}` |

Internal types (`ADD_NOTE`, `UPDATE_NOTE`, `ARCHIVED`, …) are **not exposed**. Pre-2023-03-01 status events may be silently filtered out (legacy storage format).

Example — "who closed this ticket":

```sh
curl -s -H "Token: $TOK" \
  "https://api.kundo.app/v1/tickets/<uuid>/events?fields=event_type,event_data,user_id,created_at&event_types=update_status&sort=-created_at"
```

### `GET /v1/channels` — list channels

| Param | Notes |
|---|---|
| `ids`, `fields`, `limit`, `offset` | Common. |
| `sort` | `name` or `-name`. |

Fields: `id` (UUID), `type` (lowercase string), `name`.

`type` values seen on Stillma: `email`, `chat`, `ai_assistant`, `calls`, `knowledgebase`, `forum`. Use a channel's `id` in `tickets?channel_ids=...`.

### `GET /v1/users` — list editors (Kundo staff)

| Param | Notes |
|---|---|
| `ids`, `emails`, `fields`, `limit`, `offset` | Common. |
| `sort` | `name` only (no `-name`). |

Fields: `id` (UUID), `name` (string?), `email` (string?).

This is the "internal team" — people with dashboard access. Match against `Ticket.assignee_id`, `Ticket.editors[]`, `Event.user_id`.

### `GET /v1/contacts` — list contacts (end-users / customers)

| Param | Notes |
|---|---|
| `ids`, `emails`, `fields`, `limit`, `offset` | Common. |
| `sort` | `name` only. |

Fields: `id` (UUID), `name` (string?), `email` (string?).

End-users who initiated tickets. Match against `Ticket.contacts[]`, `EmailMessage.contact_id`.

### `POST /v1/register-webhook` / `POST /v1/deregister-webhook` — Make.com-style webhooks

Body for register: `{"url": "https://...", "label": "...", "hook_type": "customer_data"}`. Returns `{"id": "<uuid>"}`. The skill does NOT cover this — webhooks are typically set up by Make.com itself when a user creates a scenario; manual registration is rare.

⚠️ **No webhooks for ticket events**. There's no "notify me when a ticket closes" hook in the public API.

## Error response shapes

The gateway is inconsistent about error envelopes. Handle all of these:

| HTTP | Body shape | Meaning |
|---|---|---|
| 401 | `{"detail": "Authentication required"}` | Missing/invalid token. |
| 422 | `{"detail": "Parameter 'X' does not exist."}` | Unknown filter/query param. |
| 422 | `{"detail": [{"type": "...", "loc": [...], "msg": "...", "input": ..., "ctx": {...}}]}` | Pydantic validation (out-of-range, bad type). |
| 500 | `{"detail": "Error fetching ticket"}` | Server-side error — most notably when requesting `fields=csat` on some tickets. |

## Gotchas (every one I tripped over while smoke-testing)

1. **Default response is `{id: …}` only.** Always pass `fields=...`.
2. **Unknown field names → silently dropped.** No 422. Spelling errors look like "field returned null".
3. **Auth header is `Token:`, not `Authorization: Bearer`.** Bearer fails with 401.
4. **No `status` filter on `/v1/tickets`.** Filter client-side.
5. **No `updated_at` exposed.** Tickets only carry `created_at`. To track "recently changed", inspect the events endpoint or `num_messages`.
6. **`status` enum is uppercase in responses** (`OPEN`/`WAITING`/`DONE`) but isn't usable as a filter at all.
7. **`channel.type` is lowercase** (`email`, `ai_assistant`, …) — different from the internal Django enums (`INBOX`, `FORUM`).
8. **`csat` field can 500.** Request it in its own call.
9. **Events default-strip `event_data`.** Without `fields=event_data`, the audit log is useless.
10. **`messages/email` caps `limit` at 50.** Pagination via `offset` if a thread is longer.
11. **EmailMessage `id` is `null` in practice.** No stable identifier per message.
12. **`num_messages` on a Ticket can disagree with the actual count from `messages/email`** (saw `num_messages=2` on a 3-message thread).
13. **Some `editor_id`/`contact_id` pairs aren't symmetric across endpoints** — a UUID that appears as a `contact_id` on a message may actually be a user in `/v1/users` (seen on stillma demo data). Look up both endpoints if you can't find a match.
14. **`organization_id` from `/v1/me` is a string**, not an integer.
15. **PURI format note**: the internal Django code uses `kundo:organization:<id>` puris everywhere, but the public API doesn't expose puris at all — just numeric `organization_id` (as a string) and UUIDs for everything else.

## Reference data — Stillma test fixtures

For reproducing examples on org 1888:

| | Value |
|---|---|
| `email` channel id | `01985a37-6776-78c4-9c61-ffab15e1f17c` (name: `info@stillma.se`) |
| `ai_assistant` channel id | `01985a39-4f42-7d95-b9a5-755d4f54f3e2` (name: `Stillma AI Chat`) |
| Sample 3-msg email ticket | `019df21c-1022-758c-bd4e-64c077db35b8` |
| Sample assigned ticket | `0198837c-7c49-7ba5-93a3-e6ea09a46337` |
| Total tickets (2026-05-20) | 585 |
| Total contacts | 94 |
| Total editors (users) | 20 |
| Total channels | 21 |
