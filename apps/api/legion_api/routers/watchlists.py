from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from legion_data import ProviderError, SymbolNotFound

from ..db import get_db
from ..deps import CachedBars, Principal, audit, current_principal, get_market, writer
from ..entitlements import limit
from ..models import Watchlist, WatchlistItem

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


class WatchlistIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class SymbolIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)


def _out(w: Watchlist) -> dict:
    return {"id": w.id, "name": w.name, "created_at": w.created_at.isoformat(),
            "symbols": [i.symbol for i in w.items]}


def owned(db: Session, principal: Principal, watchlist_id: str) -> Watchlist:
    """Load a watchlist only if it belongs to the caller's organization; otherwise 404 (never 403)."""
    w = db.scalar(select(Watchlist).options(selectinload(Watchlist.items))
                  .where(Watchlist.id == watchlist_id, Watchlist.org_id == principal.org_id))
    if w is None:
        raise HTTPException(404, "Watchlist not found")
    return w


@router.get("")
def list_watchlists(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(Watchlist).options(selectinload(Watchlist.items))
                      .where(Watchlist.org_id == principal.org_id).order_by(Watchlist.created_at)).all()
    return {"watchlists": [_out(w) for w in rows]}


@router.post("", status_code=201)
def create_watchlist(body: WatchlistIn, request: Request, principal: Principal = Depends(writer),
                     db: Session = Depends(get_db)) -> dict:
    count = db.scalar(select(func.count()).select_from(Watchlist).where(Watchlist.org_id == principal.org_id)) or 0
    cap = limit(principal.org.plan, "max_watchlists")
    if count >= cap:
        raise HTTPException(403, f"Your plan allows {cap} watchlists")
    w = Watchlist(org_id=principal.org_id, created_by=principal.user.id, name=body.name.strip())
    db.add(w)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A watchlist with this name already exists") from None
    audit(db, "watchlist.create", request=request, principal=principal, target=w.id)
    db.commit()
    return _out(w)


@router.get("/{watchlist_id}")
def get_watchlist(watchlist_id: str, principal: Principal = Depends(current_principal),
                  db: Session = Depends(get_db)) -> dict:
    return _out(owned(db, principal, watchlist_id))


@router.patch("/{watchlist_id}")
def rename_watchlist(watchlist_id: str, body: WatchlistIn, principal: Principal = Depends(writer),
                     db: Session = Depends(get_db)) -> dict:
    w = owned(db, principal, watchlist_id)
    w.name = body.name.strip()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A watchlist with this name already exists") from None
    return _out(w)


@router.delete("/{watchlist_id}", status_code=204)
def delete_watchlist(watchlist_id: str, request: Request, principal: Principal = Depends(writer),
                     db: Session = Depends(get_db)) -> None:
    w = owned(db, principal, watchlist_id)
    db.delete(w)
    audit(db, "watchlist.delete", request=request, principal=principal, target=watchlist_id)
    db.commit()


@router.post("/{watchlist_id}/symbols", status_code=201)
def add_symbol(watchlist_id: str, body: SymbolIn, principal: Principal = Depends(writer),
               db: Session = Depends(get_db), market: CachedBars = Depends(get_market)) -> dict:
    w = owned(db, principal, watchlist_id)
    try:
        symbol = market.provider.get_symbol(body.symbol).symbol
    except SymbolNotFound:
        raise HTTPException(404, f"Unknown symbol '{body.symbol}' for provider '{market.name}'") from None
    except ProviderError as e:
        raise HTTPException(502, f"Market-data provider error: {e}") from None
    if symbol in {i.symbol for i in w.items}:
        return _out(w)
    cap = limit(principal.org.plan, "max_symbols_per_watchlist")
    if len(w.items) >= cap:
        raise HTTPException(403, f"Your plan allows {cap} symbols per watchlist")
    w.items.append(WatchlistItem(symbol=symbol, position=max((i.position for i in w.items), default=-1) + 1))
    db.commit()
    return _out(w)


@router.delete("/{watchlist_id}/symbols/{symbol}")
def remove_symbol(watchlist_id: str, symbol: str, principal: Principal = Depends(writer),
                  db: Session = Depends(get_db)) -> dict:
    w = owned(db, principal, watchlist_id)
    w.items[:] = [i for i in w.items if i.symbol != symbol.strip().upper()]
    db.commit()
    return _out(w)
