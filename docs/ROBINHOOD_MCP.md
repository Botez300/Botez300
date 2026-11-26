# Robinhood MCP: transport and authentication

- **Integration:** the official Robinhood MCP server is the only brokerage and market-data integration. Its endpoint, confirmed on Robinhood's own support article
  "Onboarding an external agent" (`claude mcp add robinhood-trading --transport http https://agent.robinhood.com/mcp/trading`, then authenticate), is `https://agent.robinhood.com/mcp/trading`. Authentication uses OAuth through Robinhood's own login flow
  (`robinhood.com/oauth`). Confirm the endpoint against Robinhood's official documentation before relying on it.
- **Transport:** `legion.rh.McpHttpTransport` is a streamable-HTTP MCP client (`pip install mcp`). It reads the OAuth access token from
  `LEGION_RH_MCP_TOKEN`, or from a token file outside the repository (`LEGION_RH_MCP_TOKEN_FILE`), and the URL from `LEGION_RH_MCP_URL`.
- **Allowlist enforced locally:** the transport refuses any tool not in `READ_ONLY_TOOLS`. All `place_*`, `cancel_*`, `exercise_*`,
  watchlist, alert and saved-scan writes raise `ToolBlocked` before any network call.
- **Status: NOT verified end-to-end.**
  - The build sandbox's proxy refused `agent.robinhood.com` (HTTP 403 from the agent proxy).
  - No OAuth token exists in the sandbox.
  - The interactive OAuth login (browser plus redirect) must be done on your host.
  - Every Robinhood response used in tests was recorded through the Claude connector session, not through this transport.
- **To make it work on the host:**
  1. Complete Robinhood's OAuth for an MCP client.
  2. Store the access token outside the repo.
  3. Run `python -c "from legion.rh import *; print(RobinhoodClient(McpHttpTransport()).quote('SPY'))"`.
  4. Token refresh and dynamic client registration are not implemented. If the token expires, every call fails closed (`ConnectionFailure`).

## Phase 4 changes
- **Fixed a real defect:** the Phase 2/3 transport called `streamablehttp_client(url, headers=...)`, which does not exist in the installed MCP SDK 2.3.0.
  It now uses `streamable_http_client(url, http_client=create_mcp_http_client(auth=...))`.
- **Auth:** `legion/rh_auth.py` wraps the SDK `OAuthClientProvider` (discovery, dynamic client registration, PKCE, refresh). Its token storage is
  OS-keyring-only (`KeyringTokenStorage`) and refuses fail/plaintext backends.
  - Interactive login: `python -m legion.rh_auth login`.
  - The service runs non-interactively: it never opens a browser and fails closed if refresh fails.
- **Retries:** `ResilientTransport` retries transient failures with backoff, never retries blocked tools, and raises `ConnectionFailure` when it gives up.
- **Not verified:** whether Robinhood's OAuth server accepts dynamic client registration from a non-Claude client. Robinhood documents only adding the
  server to an AI platform. If registration is refused, the fallback is a documented manual-reauthentication procedure, and you would need to ask Robinhood
  for a supported standalone-client path.

## Phase 5 review
- **Official instructions:** Robinhood's own support article documents `claude mcp add robinhood-trading --transport http https://agent.robinhood.com/mcp/trading`, then authentication inside the AI platform.
  That is the officially supported path. Whether the app's standalone OAuth client (`legion/rh_auth.py`, MCP SDK dynamic registration + PKCE) is accepted is **UNVERIFIED**.
- **Tool schemas discovered this session** (read-only, via the Claude connector):
  - get_equity_quotes, get_equity_historicals (day/week/month, split-adjusted by default), get_equity_fundamentals, get_equity_technical_indicators;
  - get_option_chains, get_option_instruments, get_option_quotes (Greeks + IV);
  - get_earnings_calendar/results, get_indexes, get_index_historicals, preview_scan, get_sec_filing_index/facts.
  - **There is no market-session tool.** Session state comes from the deterministic NYSE calendar plus quote timestamps.
- **Rate limits:** not documented by the tools. `ResilientTransport` retries with exponential backoff, and errors fail closed.
- **If standalone OAuth is refused, in order:**
  1. Ask Robinhood for a supported standalone-client path.
  2. Run read-only data pulls inside an authenticated Claude Code session on the host, writing timestamped snapshots that the deterministic service ingests as RECORDED data (LLM-mediated transport: lower assurance, labeled as such).
  3. Stay blocked.

  Never bypass authentication.
- **Authenticated tests executed by the app itself:** NONE (sandbox proxy blocks agent.robinhood.com).
