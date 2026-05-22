# kundo-api-skill

A [Claude Code](https://docs.claude.com/en/docs/claude-code) plugin that teaches Claude how to query Kundo's public **ärende-data API** (`api.kundo.app`) — tickets, email threads, audit events, channels, editors, contacts.

Works in both terminal Claude Code and the Claude macOS desktop app (they share the same plugin loader).

## Install

In Claude Code, run:

```
/plugin marketplace add kundo/beta-kundo-api-skill
/plugin install kundo-api@kundo
```

After install, just ask Claude things like:

- "List the 10 most recent tickets in Stillma"
- "Who closed ticket `<uuid>` and when?"
- "Show me the email thread for ticket `<uuid>`"

The skill autoloads when the request looks like ärende-data work.

## First-run auth

You need a Kundo API token. The first time Claude queries the API it will tell you:

> Get an API key by following these instructions: <https://www.kundo.se/hjalp-support?path=%2Fguide%2Fapi-for-arende-data>
>
> Then paste the key here and I'll take care of the rest.

Paste the key in the chat — Claude runs the onboarding wizard, verifies it against `/v1/me`, discovers your org id, and saves credentials to `~/.kundo/credentials.json` (mode 0600).

Or set `$KUNDO_API_TOKEN` in your shell if you'd rather skip the wizard (required in Claude Cowork, which has no local filesystem).

## Install (Claude.ai desktop / web — Skills upload)

If you're using the Claude.ai desktop app or web app (not Claude Code), grab the prebuilt skill bundle from the latest [release](https://github.com/kundo/beta-kundo-api-skill/releases) and upload `kundo-api.zip` in **Settings → Capabilities → Skills**.

Or build it yourself from source:

```
./build-claude-skill.sh
# → dist/kundo-api.zip
```

In Claude.ai the skill runs in a sandboxed environment, so the `~/.kundo/credentials.json` persistence trick is **not** available — set `KUNDO_API_TOKEN` via the Skills environment-variable UI instead.

## What's in the plugin

```
.claude-plugin/
  plugin.json            # plugin manifest
  marketplace.json       # marketplace catalog
skills/kundo-api/
  SKILL.md               # the skill (entrypoint Claude reads)
  REFERENCE.md           # full endpoint catalog + Stillma test fixtures
  scripts/kapi.py        # CLI wrapper used for onboarding + scripted queries
```

## Scope

**This plugin covers**: the read-only `api.kundo.app` ärende-data API (tickets, messages, events, channels, editors, contacts).

**This plugin does NOT cover**:

- Help-center articles → separate `kundo-helpcenter-api` skill
- Legacy forum / dialog posts at `kundo.se/api-doc/` (different auth)
- Creating or modifying tickets — the API is read-only

## Updating

When a new version ships:

```
/plugin update kundo-api@kundo
```

## Links

- Kundo API docs (Swagger): <https://api.kundo.app/docs>
- OpenAPI spec: <https://api.kundo.app/openapi.json>
- Kundo help-center guide for the API: <https://www.kundo.se/hjalp-support?path=%2Fguide%2Fapi-for-arende-data>
