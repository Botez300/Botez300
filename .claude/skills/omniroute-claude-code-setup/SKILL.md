---
name: omniroute-claude-code-setup
description: Install OmniRoute (free AI gateway, 385 providers, auto-fallback, token compression) and point Claude Code at it — via `omniroute launch`, environment variables, or ~/.claude/settings.json — and connect the OmniRoute MCP server. Use when the user wants to run Claude Code through OmniRoute, route Claude to cheaper/free models, or set up the omniroute MCP server.
---

## What OmniRoute does for Claude Code

OmniRoute is a local gateway that speaks the Anthropic Messages API. Claude Code sends its
requests to OmniRoute, which routes them to whichever providers/combos you configured
(Claude, GPT, Gemini, GLM, free tiers…) with fallback and prompt compression.

Default address: `http://localhost:20128` (dashboard at the same URL).

## 1. Install and start

```bash
npm install -g omniroute     # Node 20+
omniroute                    # starts server + dashboard on :20128
# or: docker compose up -d   (from a clone of github.com/cheaper-inference/OmniRoute)
```

Open the dashboard, add at least one provider connection, then create an API key
(Dashboard → API Keys, or `omniroute keys create`).

## 2. Point Claude Code at OmniRoute

Pick one.

**A. Easiest — let OmniRoute launch Claude Code**

```bash
omniroute launch                                  # local server
omniroute launch --remote http://HOST:20128 --api-key oma_live_xxx
omniroute setup-claude && omniroute launch --profile <name>   # per-model profiles
```

**B. Environment variables (current shell)**

```bash
export ANTHROPIC_BASE_URL="http://localhost:20128"   # root URL — NO /v1 suffix
export ANTHROPIC_AUTH_TOKEN="<your OmniRoute API key>"
# optional:
export ANTHROPIC_MODEL="<provider/model or combo name>"
export CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1   # /model lists gateway models
claude
```

**C. Persist in `~/.claude/settings.json`** (user-level, not committed to a repo)

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:20128",
    "ANTHROPIC_AUTH_TOKEN": "<your OmniRoute API key>"
  }
}
```

Env vars are read once at startup — restart Claude Code after changing them.
To go back to normal Anthropic access, remove these variables.

## 3. MCP server (OmniRoute tools inside Claude)

This repo's `.mcp.json` already declares an `omniroute` server at
`http://localhost:20128/api/mcp/stream`, authenticated with `$OMNIROUTE_API_KEY`.
Enable the streamable-HTTP transport once on the OmniRoute side:

```bash
omniroute mcp enable --transport streamable-http   # or toggle it on /dashboard/mcp
export OMNIROUTE_API_KEY="<your OmniRoute API key>"  # needs mcp:connect + read scopes
```

Elsewhere, add it manually:

```bash
claude mcp add --transport http omniroute http://localhost:20128/api/mcp/stream \
  --header "Authorization: Bearer $OMNIROUTE_API_KEY"
```

Stdio alternative: `{"command": "omniroute", "args": ["--mcp"], "env": {"OMNIROUTE_API_KEY": "...", "OMNIROUTE_BASE_URL": "http://localhost:20128"}}`.

Check it works by calling `omniroute_get_health` and `omniroute_list_combos`.

## 4. Verify

```bash
curl -s http://localhost:20128/v1/models -H "Authorization: Bearer $ANTHROPIC_AUTH_TOKEN" | head
omniroute health
```

## Related skills

- `omniroute-auth`, `omniroute-api-keys` — keys and scopes
- `omniroute-providers`, `omniroute-models`, `omniroute-combos-routing` — what Claude gets routed to
- `omniroute-compression` — RTK/Caveman token savings
- `omniroute-mcp`, `omniroute-cli-mcp` — the MCP server
- `omniroute-cli-*` — every `omniroute` CLI command

## Notes

- Never commit API keys; keep them in env vars or user-level settings.
- Provider free tiers are third-party; each provider's limits and terms apply.
