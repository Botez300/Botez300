# OmniRoute skills

45 skills for [OmniRoute](https://github.com/cheaper-inference/OmniRoute), the free AI gateway that lets Claude Code run through 385 providers with auto-fallback and token compression.

- **Start here:** `/omniroute-claude-code-setup` — install OmniRoute, point Claude Code at it, connect the MCP server.
- `omniroute-*` (23) — the OmniRoute REST API (auth, providers, models, combos/routing, compression, budget, MCP, A2A…). Upstream `omni-*`.
- `omniroute-cli-*` (21) — the `omniroute` CLI commands. Upstream `cli-*`.

Copied from upstream `skills/` at commit `1b2b799c`, renamed with an `omniroute-` prefix to avoid name clashes. Skipped: `config-codex-cli` (Codex only) and `ponytail` (unrelated third-party skill).

The `omniroute` MCP server is declared in `/.mcp.json` (`http://localhost:20128/api/mcp/stream`, Bearer `$OMNIROUTE_API_KEY`). It only connects while OmniRoute is running locally.

To update: clone upstream, then for each `skills/omni-*` / `skills/cli-*` copy `SKILL.md` here under the prefixed folder name and change its `name:` line to match.

MIT licensed — see OMNIROUTE-LICENSE.
