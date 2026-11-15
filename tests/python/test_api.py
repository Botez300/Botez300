from __future__ import annotations

import jwt
import pytest

from conftest import register
from legion_api.config import Settings, get_settings
from legion_api.entitlements import PLANS
from legion_indicators import compute

API = "/api/v1"
RULE = {"left": {"field": "close"}, "op": ">", "right": {"indicator": "sma", "params": {"length": 50}}}
DEFN = {"filter": {"logic": "and", "rules": [RULE]}}

# --------------------------------------------------------------------------- auth


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["database"] == "ok" and r.json()["provider"] == "demo"
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-request-id"]


def test_register_login_me_logout(client):
    r = client.post(f"{API}/auth/register", json={"email": "Ada@Example.com", "password": "correct-horse-battery", "display_name": "Ada"})
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "ada@example.com" and body["role"] == "owner"
    assert body["organization"]["plan"] == "free" and body["organization"]["entitlements"] == PLANS["free"]
    cookie = r.headers["set-cookie"].lower()
    assert "legion_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert "password" not in r.text.replace("password_hash", "") or "correct-horse" not in r.text

    assert client.get(f"{API}/auth/me").json()["user"]["email"] == "ada@example.com"  # cookie session
    assert client.post(f"{API}/auth/logout").status_code == 204
    client.cookies.clear()
    assert client.get(f"{API}/auth/me").status_code == 401

    r = client.post(f"{API}/auth/login", json={"email": "ada@example.com", "password": "correct-horse-battery"})
    assert r.status_code == 200
    client.cookies.clear()
    assert client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).status_code == 200


def test_passwords_are_hashed_with_argon2(client):
    from sqlalchemy import select

    from legion_api.db import get_engine
    from legion_api.models import User

    register(client)
    with get_engine().connect() as conn:
        stored = conn.execute(select(User.password_hash)).scalar_one()
    assert stored.startswith("$argon2id$") and "correct-horse" not in stored


@pytest.mark.parametrize("payload", [
    {"email": "not-an-email", "password": "correct-horse-battery", "display_name": "A"},
    {"email": "a@example.com", "password": "short", "display_name": "A"},
    {"email": "a@example.com", "password": "correct-horse-battery", "display_name": ""},
])
def test_register_validation(client, payload):
    assert client.post(f"{API}/auth/register", json=payload).status_code == 422


def test_duplicate_email_and_bad_credentials(client):
    register(client)
    r = client.post(f"{API}/auth/register", json={"email": "ADA@example.com", "password": "another-long-password", "display_name": "X"})
    assert r.status_code == 409
    wrong = client.post(f"{API}/auth/login", json={"email": "ada@example.com", "password": "wrong-password-here"})
    unknown = client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": "wrong-password-here"})
    assert wrong.status_code == unknown.status_code == 401 and wrong.json() == unknown.json()  # no account enumeration


def test_login_is_rate_limited(client):
    register(client)
    limit = get_settings().login_attempts_per_window
    codes = [client.post(f"{API}/auth/login", json={"email": "ada@example.com", "password": "wrong-password-here"}).status_code
             for _ in range(limit + 2)]
    assert codes[:limit] == [401] * limit and codes[limit:] == [429, 429]
    # The correct password is refused too while the window is closed.
    assert client.post(f"{API}/auth/login", json={"email": "ada@example.com", "password": "correct-horse-battery"}).status_code == 429


@pytest.mark.parametrize("path", ["/auth/me", "/provider", "/symbols/search?q=a", "/bars/ALFA", "/indicators",
                                  "/watchlists", "/scans/presets", "/scans/saved"])
def test_endpoints_require_authentication(client, path):
    assert client.get(f"{API}{path}").status_code == 401


def test_forged_expired_and_orphaned_tokens_are_rejected(client):
    headers = register(client)
    token = headers["Authorization"].split()[1]
    claims = jwt.decode(token, options={"verify_signature": False})
    forged = jwt.encode(claims, "some-other-secret-some-other-secret-00", algorithm="HS256")
    unsigned = jwt.encode(claims, "", algorithm="none")
    expired = jwt.encode({**claims, "exp": 1}, get_settings().jwt_secret, algorithm="HS256")
    other_org = jwt.encode({**claims, "org": "00000000-0000-0000-0000-000000000000"}, get_settings().jwt_secret, algorithm="HS256")
    for bad in (forged, unsigned, expired, other_org, "garbage"):
        assert client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 200


def test_production_settings_refuse_insecure_defaults():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(env="prod", cookie_secure=True, jwt_secret="dev-only-secret-change-me-dev-only-secret")
    with pytest.raises(ValueError, match="COOKIE_SECURE"):
        Settings(env="prod", jwt_secret="x" * 40, cookie_secure=False)
    assert Settings(env="prod", jwt_secret="x" * 40, cookie_secure=True).env == "prod"


# ------------------------------------------------------------------------- market


def test_symbol_search_and_bars_contract(client, demo):
    h = register(client)
    r = client.get(f"{API}/symbols/search", params={"q": "qb"}, headers=h).json()
    assert r["provider"] == "demo" and r["results"][0]["symbol"] == "QBIT" and r["results"][0]["exchange"] == "SIM"
    assert client.get(f"{API}/symbols/AAPL", headers=h).status_code == 404

    body = client.get(f"{API}/bars/alfa", params={"limit": 300}, headers=h).json()
    assert body["symbol"] == "ALFA" and body["provider"] == "demo" and body["timeframe"] == "1D"
    assert body["data_status"] == "SIMULATED" and body["verification"] == "SIMULATED"
    assert body["adjustment"] == "n/a" and body["timezone"] == "America/New_York" and body["last_bar"] == "2025-06-13"
    bars = body["bars"]
    assert len(bars) == 300 and set(bars[0]) == {"t", "o", "h", "l", "c", "v"}
    times = [b["t"] for b in bars]
    assert times == sorted(set(times)) and all(t % 86_400_000 == 0 for t in times)  # ascending, unique, 00:00 UTC
    expected = demo.get_bars("ALFA").frame
    assert bars[-1]["c"] == expected["close"].iloc[-1] and bars[-1]["v"] == expected["volume"].iloc[-1]

    weekly = client.get(f"{API}/bars/ALFA", params={"timeframe": "1W"}, headers=h).json()
    assert weekly["timeframe"] == "1W" and len(weekly["bars"]) < len(expected) / 4
    assert client.get(f"{API}/bars/ALFA", params={"timeframe": "5m"}, headers=h).status_code == 422
    assert client.get(f"{API}/bars/NOPE", headers=h).status_code == 404


def test_indicator_catalog_and_compute_align_with_bars(client, demo):
    h = register(client)
    cat = client.get(f"{API}/indicators", headers=h).json()["indicators"]
    assert len(cat) >= 15 and {"id", "name", "category", "overlay", "params", "outputs", "version", "reference"} <= set(cat[0])

    r = client.post(f"{API}/indicators/compute", headers=h,
                    json={"symbol": "ALFA", "indicator": "bbands", "params": {"length": 20, "mult": 2}, "limit": 250})
    assert r.status_code == 200
    body = r.json()
    bars = client.get(f"{API}/bars/ALFA", params={"limit": 250}, headers=h).json()["bars"]
    assert body["t"] == [b["t"] for b in bars] and set(body["outputs"]) == {"upper", "middle", "lower"}
    ref = compute("bbands", demo.get_bars("ALFA").frame, {"length": 20, "mult": 2})
    assert body["outputs"]["upper"][-1] == pytest.approx(ref["upper"][-1])
    assert body["data_status"] == "SIMULATED"

    warm = client.post(f"{API}/indicators/compute", headers=h,
                       json={"symbol": "ALFA", "timeframe": "1M", "indicator": "sma", "params": {"length": 200}}).json()
    assert all(v is None for v in warm["outputs"]["sma"])  # NaN is serialised as null, never as a number

    for bad in ({"symbol": "ALFA", "indicator": "nope"}, {"symbol": "ALFA", "indicator": "sma", "params": {"length": -1}}):
        assert client.post(f"{API}/indicators/compute", headers=h, json=bad).status_code == 422
    assert client.post(f"{API}/indicators/compute", headers=h, json={"symbol": "NOPE", "indicator": "sma"}).status_code == 404


# --------------------------------------------------------------------- watchlists


def test_watchlist_crud_persists(client):
    h = register(client)
    w = client.post(f"{API}/watchlists", json={"name": "Leaders"}, headers=h)
    assert w.status_code == 201
    wid = w.json()["id"]
    assert client.post(f"{API}/watchlists", json={"name": "Leaders"}, headers=h).status_code == 409
    for s in ("alfa", "QBIT", "ALFA"):  # normalised and de-duplicated
        assert client.post(f"{API}/watchlists/{wid}/symbols", json={"symbol": s}, headers=h).status_code == 201
    assert client.post(f"{API}/watchlists/{wid}/symbols", json={"symbol": "AAPL"}, headers=h).status_code == 404
    assert client.get(f"{API}/watchlists/{wid}", headers=h).json()["symbols"] == ["ALFA", "QBIT"]
    assert client.patch(f"{API}/watchlists/{wid}", json={"name": "Tech"}, headers=h).json()["name"] == "Tech"
    assert client.delete(f"{API}/watchlists/{wid}/symbols/alfa", headers=h).json()["symbols"] == ["QBIT"]
    assert [x["name"] for x in client.get(f"{API}/watchlists", headers=h).json()["watchlists"]] == ["Tech"]
    assert client.delete(f"{API}/watchlists/{wid}", headers=h).status_code == 204
    assert client.get(f"{API}/watchlists/{wid}", headers=h).status_code == 404


def test_plan_limits_come_from_entitlements(client):
    h = register(client)
    cap = PLANS["free"]["max_watchlists"]
    codes = [client.post(f"{API}/watchlists", json={"name": f"W{i}"}, headers=h).status_code for i in range(cap + 1)]
    assert codes == [201] * cap + [403]
    cap = PLANS["free"]["max_saved_scans"]
    codes = [client.post(f"{API}/scans/saved", json={"name": f"S{i}", "definition": DEFN}, headers=h).status_code for i in range(cap + 1)]
    assert codes == [201] * cap + [403]


def test_viewer_role_is_read_only(client):
    from sqlalchemy import update

    from legion_api.db import get_engine
    from legion_api.models import Membership

    h = register(client)
    assert client.post(f"{API}/watchlists", json={"name": "Mine"}, headers=h).status_code == 201
    with get_engine().begin() as conn:
        conn.execute(update(Membership).values(role="viewer"))
    assert client.get(f"{API}/watchlists", headers=h).status_code == 200
    assert client.post(f"{API}/watchlists", json={"name": "Nope"}, headers=h).status_code == 403
    assert client.post(f"{API}/scans/saved", json={"name": "Nope", "definition": DEFN}, headers=h).status_code == 403
    assert client.post(f"{API}/scans/run", json={"definition": DEFN}, headers=h).status_code == 200


# ---------------------------------------------------------------- tenant isolation


def test_tenants_cannot_see_or_touch_each_others_data(client):
    ada = register(client, "ada@example.com", name="Ada")
    bob = register(client, "bob@example.com", name="Bob")
    wid = client.post(f"{API}/watchlists", json={"name": "Ada list"}, headers=ada).json()["id"]
    client.post(f"{API}/watchlists/{wid}/symbols", json={"symbol": "ALFA"}, headers=ada)
    sid = client.post(f"{API}/scans/saved", json={"name": "Ada scan", "definition": DEFN}, headers=ada).json()["id"]

    assert client.get(f"{API}/watchlists", headers=bob).json() == {"watchlists": []}
    assert client.get(f"{API}/scans/saved", headers=bob).json() == {"scans": []}
    attempts = [
        client.get(f"{API}/watchlists/{wid}", headers=bob),
        client.patch(f"{API}/watchlists/{wid}", json={"name": "pwned"}, headers=bob),
        client.delete(f"{API}/watchlists/{wid}", headers=bob),
        client.post(f"{API}/watchlists/{wid}/symbols", json={"symbol": "QBIT"}, headers=bob),
        client.delete(f"{API}/watchlists/{wid}/symbols/ALFA", headers=bob),
        client.delete(f"{API}/scans/saved/{sid}", headers=bob),
        client.post(f"{API}/scans/saved/{sid}/run", headers=bob),
        client.post(f"{API}/scans/run", json={"definition": DEFN, "universe": {"type": "watchlist", "watchlist_id": wid}}, headers=bob),
        client.post(f"{API}/scans/saved", json={"name": "x", "definition": DEFN, "universe": {"type": "watchlist", "watchlist_id": wid}}, headers=bob),
    ]
    assert [r.status_code for r in attempts] == [404] * len(attempts)  # 404, not 403: existence is not disclosed
    assert client.get(f"{API}/watchlists/{wid}", headers=ada).json() == {
        "id": wid, "name": "Ada list", "symbols": ["ALFA"], "created_at": client.get(f"{API}/watchlists/{wid}", headers=ada).json()["created_at"]}
    assert len(client.get(f"{API}/scans/saved", headers=ada).json()["scans"]) == 1
    # The same names are free in another tenant.
    assert client.post(f"{API}/watchlists", json={"name": "Ada list"}, headers=bob).status_code == 201


# -------------------------------------------------------------------------- scans


def test_scan_run_save_and_rerun(client, demo):
    h = register(client)
    presets = client.get(f"{API}/scans/presets", headers=h).json()["presets"]
    trend = next(p for p in presets if p["id"] == "trend-alignment")
    out = client.post(f"{API}/scans/run", json={"definition": trend["definition"]}, headers=h).json()
    assert out["scanned"] == len(demo.universe()) and out["matched"] == len(out["rows"]) > 0
    assert out["data_status"] == "SIMULATED" and out["engine_version"] and len(out["conditions"]) == 3
    for row in out["rows"]:
        v = row["values"]
        assert v["close 1D"] > v["sma(50) 1D"] > v["sma(200) 1D"] and v["rsi(14) 1D"] > 50
        assert row["verification"] == "SIMULATED" and row["bar_date"] == "2025-06-13"
    assert [r["sort_value"] for r in out["rows"]] == sorted((r["sort_value"] for r in out["rows"]), reverse=True)

    stocks = client.post(f"{API}/scans/run", headers=h,
                         json={"definition": DEFN, "universe": {"type": "provider", "asset_types": ["etf"]}}).json()
    assert stocks["scanned"] == 12 and all(r["asset_type"] == "etf" for r in stocks["rows"])

    wid = client.post(f"{API}/watchlists", json={"name": "Two"}, headers=h).json()["id"]
    for s in ("ALFA", "QBIT"):
        client.post(f"{API}/watchlists/{wid}/symbols", json={"symbol": s}, headers=h)
    universe = {"type": "watchlist", "watchlist_id": wid}
    saved = client.post(f"{API}/scans/saved", json={"name": "Above 50d", "definition": DEFN, "universe": universe}, headers=h)
    assert saved.status_code == 201
    rerun = client.post(f"{API}/scans/saved/{saved.json()['id']}/run", headers=h).json()
    direct = client.post(f"{API}/scans/run", json={"definition": DEFN, "universe": universe}, headers=h).json()
    assert rerun["scanned"] == 2 and rerun["rows"] == direct["rows"]

    explicit = client.post(f"{API}/scans/run", headers=h,
                           json={"definition": DEFN, "universe": {"type": "symbols", "symbols": ["alfa", "ALFA", "ZZZZ"]}}).json()
    assert explicit["scanned"] == 2 and [e["symbol"] for e in explicit["errors"]] == ["ZZZZ"]


@pytest.mark.parametrize("payload", [
    {"definition": {"filter": {"rules": []}}},
    {"definition": {"filter": {"rules": [{"left": {"indicator": "nope"}, "op": ">", "right": {"value": 1}}]}}},
    {"definition": DEFN, "universe": {"type": "symbols"}},
    {"definition": DEFN, "universe": {"type": "watchlist"}},
    {"definition": {**DEFN, "limit": 100000}},
])
def test_scan_validation(client, payload):
    h = register(client)
    assert client.post(f"{API}/scans/run", json=payload, headers=h).status_code == 422


def test_audit_log_records_security_events(client):
    from sqlalchemy import select

    from legion_api.db import get_engine
    from legion_api.models import AuditLog

    h = register(client)
    client.post(f"{API}/auth/login", json={"email": "ada@example.com", "password": "wrong-password-here"})
    client.post(f"{API}/watchlists", json={"name": "L"}, headers=h)
    with get_engine().connect() as conn:
        actions = conn.execute(select(AuditLog.action).order_by(AuditLog.at)).scalars().all()
    assert actions == ["auth.register", "auth.login_failed", "watchlist.create"]
