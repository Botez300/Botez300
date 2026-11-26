"""Robinhood MCP OAuth. Uses the MCP SDK's standard OAuth client (protected-resource discovery, dynamic client
registration, PKCE, automatic refresh). Tokens and client registration are stored ONLY in the operating-system credential
store via `keyring` (Windows Credential Manager / macOS Keychain). There is deliberately NO plaintext-file fallback:
if no secure backend exists, the code refuses to store credentials.

Re-authentication: `python -m legion.rh_auth login` (opens a browser), `... status`, `... logout`."""
import json, sys

SERVICE = "legion-quant-capital/robinhood-mcp"
class InsecureCredentialStore(RuntimeError): pass

def _keyring(backend=None):
    if backend is None:
        import keyring
        backend = keyring.get_keyring()
    kr = backend
    name = type(kr).__module__ + "." + type(kr).__name__
    if "fail" in name.lower() or "null" in name.lower() or "plaintext" in name.lower():
        raise InsecureCredentialStore(f"no secure OS credential store available ({name}); refusing to store Robinhood tokens")
    return kr

class KeyringTokenStorage:
    """mcp.client.auth.TokenStorage implementation backed by the OS credential store."""
    def __init__(self, backend=None, service=SERVICE): self.kr, self.service = _keyring(backend), service
    def _get(self, k):
        v = self.kr.get_password(self.service, k); return json.loads(v) if v else None
    def _set(self, k, v): self.kr.set_password(self.service, k, json.dumps(v))
    async def get_tokens(self):
        from mcp.shared.auth import OAuthToken
        v = self._get("tokens"); return OAuthToken(**v) if v else None
    async def set_tokens(self, tokens): self._set("tokens", tokens.model_dump(mode="json", exclude_none=True))
    async def get_client_info(self):
        from mcp.shared.auth import OAuthClientInformationFull
        v = self._get("client"); return OAuthClientInformationFull(**v) if v else None
    async def set_client_info(self, info): self._set("client", info.model_dump(mode="json", exclude_none=True))
    def clear(self):
        for k in ("tokens", "client"):
            try: self.kr.delete_password(self.service, k)
            except Exception: pass
    def has_tokens(self): return self._get("tokens") is not None

def oauth_provider(server_url, port=8765, storage=None, interactive=False):
    """Build the SDK OAuth provider. Non-interactive (service) mode never opens a browser: if refresh fails the call raises
    and the service fails closed + alerts; the owner then runs `python -m legion.rh_auth login`."""
    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import OAuthClientMetadata
    storage = storage or KeyringTokenStorage()
    redirect = f"http://127.0.0.1:{port}/callback"
    meta = OAuthClientMetadata(client_name="Legion Quant Capital (paper research, read-only)", redirect_uris=[redirect],
                               grant_types=["authorization_code", "refresh_token"], response_types=["code"])
    async def redirect_handler(url):
        if not interactive: raise RuntimeError("Robinhood re-authentication required: run `python -m legion.rh_auth login`")
        import webbrowser; print("Opening browser for Robinhood login:", url); webbrowser.open(url)
    async def callback_handler():
        if not interactive: raise RuntimeError("non-interactive mode")
        return await _wait_for_callback(port)
    return OAuthClientProvider(server_url, meta, storage, redirect_handler, callback_handler)

async def _wait_for_callback(port, timeout=300):
    import asyncio
    from urllib.parse import urlparse, parse_qs
    from mcp.shared.auth import AuthorizationCodeResult
    fut = asyncio.get_running_loop().create_future()
    async def handle(reader, writer):
        line = (await reader.readline()).decode(); q = parse_qs(urlparse(line.split(" ")[1]).query)
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nLegion: Robinhood login complete. You can close this tab.\r\n")
        await writer.drain(); writer.close()
        if not fut.done(): fut.set_result(AuthorizationCodeResult(code=q["code"][0], state=(q.get("state") or [None])[0]))
    srv = await asyncio.start_server(handle, "127.0.0.1", port)
    try: return await asyncio.wait_for(fut, timeout)
    finally: srv.close()

def main(argv=None):                                    # pragma: no cover - interactive, host only
    from .rh import McpHttpTransport, RobinhoodClient, DEFAULT_RH_MCP_URL
    cmd = (argv or sys.argv[1:] or ["status"])[0]; st = KeyringTokenStorage()
    if cmd == "logout": st.clear(); print("tokens removed from OS credential store"); return 0
    if cmd == "status": print("tokens present" if st.has_tokens() else "no tokens: run `python -m legion.rh_auth login`"); return 0
    if cmd == "login":
        c = RobinhoodClient(McpHttpTransport(auth=oauth_provider(DEFAULT_RH_MCP_URL, storage=st, interactive=True)))
        q = c.quote("SPY"); print("authenticated read-only check OK: SPY", q.price, q.ts); return 0
    print("usage: python -m legion.rh_auth [login|status|logout]"); return 2
if __name__ == "__main__": sys.exit(main())
