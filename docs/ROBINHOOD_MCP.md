# Robinhood MCP: transport and authentication

- **Integration:** the official Robinhood MCP server is the only brokerage and market-data integration. Its endpoint, as published in
  third-party guides, is `https://agent.robinhood.com/mcp/trading`. Authentication uses OAuth through Robinhood's own login flow
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
