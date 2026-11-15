from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from legion_data import ProviderError, SymbolInfo
from legion_scanner import PRESETS, ScanDefinition, ScanError, run_scan, validate

from ..db import get_db
from ..deps import CachedBars, Principal, audit, current_principal, get_market, writer
from ..entitlements import limit
from ..models import SavedScan
from .watchlists import owned as owned_watchlist

router = APIRouter(prefix="/scans", tags=["scans"])


class Universe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["provider", "symbols", "watchlist"] = "provider"
    symbols: list[str] = Field(default_factory=list, max_length=10000)
    watchlist_id: str | None = None
    asset_types: list[Literal["stock", "etf", "index"]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self) -> Universe:
        if self.type == "symbols" and not self.symbols:
            raise ValueError("universe.symbols is required when type is 'symbols'")
        if self.type == "watchlist" and not self.watchlist_id:
            raise ValueError("universe.watchlist_id is required when type is 'watchlist'")
        return self


class RunIn(BaseModel):
    definition: ScanDefinition
    universe: Universe = Field(default_factory=Universe)


class SavedScanIn(RunIn):
    name: str = Field(min_length=1, max_length=80)


def _resolve(universe: Universe, principal: Principal, db: Session, market: CachedBars) -> list[SymbolInfo]:
    provider = market.provider
    if universe.type == "provider":
        infos = provider.universe()
        if not infos:
            raise HTTPException(422, f"Provider '{provider.name}' cannot enumerate a universe; scan a watchlist "
                                     "or an explicit symbol list instead")
    else:
        names = universe.symbols if universe.type == "symbols" else \
            [i.symbol for i in owned_watchlist(db, principal, universe.watchlist_id or "").items]
        infos = []
        for name in dict.fromkeys(s.strip().upper() for s in names if s.strip()):
            try:
                infos.append(provider.get_symbol(name))
            except ProviderError:
                infos.append(SymbolInfo(name, name, "", "stock", provider=provider.name))  # reported as an error row
    if universe.asset_types:
        infos = [i for i in infos if i.asset_type in universe.asset_types]
    cap = limit(principal.org.plan, "max_scan_symbols")
    if len(infos) > cap:
        raise HTTPException(403, f"Your plan allows scanning {cap} symbols at a time; this universe has {len(infos)}")
    return infos


def _saved_out(s: SavedScan) -> dict[str, Any]:
    return {"id": s.id, "name": s.name, "definition": s.definition, "universe": s.universe,
            "created_at": s.created_at.isoformat(), "updated_at": s.updated_at.isoformat()}


def _owned(db: Session, principal: Principal, scan_id: str) -> SavedScan:
    s = db.scalar(select(SavedScan).where(SavedScan.id == scan_id, SavedScan.org_id == principal.org_id))
    if s is None:
        raise HTTPException(404, "Saved scan not found")
    return s


def _check(definition: ScanDefinition) -> None:
    try:
        validate(definition)
    except ScanError as e:
        raise HTTPException(422, str(e)) from None


@router.get("/presets")
def presets(_: Principal = Depends(current_principal)) -> dict:
    return {"presets": PRESETS}


@router.post("/run")
def run(body: RunIn, principal: Principal = Depends(current_principal), db: Session = Depends(get_db),
        market: CachedBars = Depends(get_market)) -> dict:
    _check(body.definition)
    symbols = _resolve(body.universe, principal, db, market)
    result = run_scan(market, body.definition, symbols)  # type: ignore[arg-type]
    result["universe"] = body.universe.model_dump(exclude_defaults=True) | {"type": body.universe.type}
    return result


@router.get("/saved")
def list_saved(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(SavedScan).where(SavedScan.org_id == principal.org_id).order_by(SavedScan.name)).all()
    return {"scans": [_saved_out(s) for s in rows]}


@router.post("/saved", status_code=201)
def save(body: SavedScanIn, request: Request, principal: Principal = Depends(writer),
         db: Session = Depends(get_db)) -> dict:
    _check(body.definition)
    if body.universe.type == "watchlist":
        owned_watchlist(db, principal, body.universe.watchlist_id or "")
    count = db.scalar(select(func.count()).select_from(SavedScan).where(SavedScan.org_id == principal.org_id)) or 0
    cap = limit(principal.org.plan, "max_saved_scans")
    if count >= cap:
        raise HTTPException(403, f"Your plan allows {cap} saved scans")
    s = SavedScan(org_id=principal.org_id, created_by=principal.user.id, name=body.name.strip(),
                  definition=body.definition.model_dump(exclude_none=True), universe=body.universe.model_dump())
    db.add(s)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A saved scan with this name already exists") from None
    audit(db, "scan.save", request=request, principal=principal, target=s.id)
    db.commit()
    return _saved_out(s)


@router.delete("/saved/{scan_id}", status_code=204)
def delete_saved(scan_id: str, request: Request, principal: Principal = Depends(writer),
                 db: Session = Depends(get_db)) -> None:
    db.delete(_owned(db, principal, scan_id))
    audit(db, "scan.delete", request=request, principal=principal, target=scan_id)
    db.commit()


@router.post("/saved/{scan_id}/run")
def run_saved(scan_id: str, principal: Principal = Depends(current_principal), db: Session = Depends(get_db),
              market: CachedBars = Depends(get_market)) -> dict:
    s = _owned(db, principal, scan_id)
    return run(RunIn(definition=ScanDefinition.model_validate(s.definition),
                     universe=Universe.model_validate(s.universe)), principal, db, market)
