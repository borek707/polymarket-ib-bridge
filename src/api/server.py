"""
API Server - FastAPI dla dashboardu i zewnętrznych integracji.
"""

import os
import sqlite3
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# Pydantic models
class ContractResponse(BaseModel):
    conid: int
    symbol: str
    name: str
    category: str
    exchange: str
    expiry: str
    last_price: Optional[float]
    is_active: bool


class MarketResponse(BaseModel):
    slug: str
    question: str
    category: str
    volume_24h: float
    yes_price: float
    no_price: float
    end_date: str


class OpportunityResponse(BaseModel):
    id: int
    poly_slug: str
    poly_question: str
    ib_symbol: str
    correlation_score: float
    whale_volume: float
    whale_direction: str
    poly_price: float
    ib_price: Optional[float]
    signal_strength: int
    recommendation: str
    detected_at: str


class PortfolioResponse(BaseModel):
    positions_count: int
    total_contracts: int
    total_exposure_usd: float
    daily_realized_pnl: float
    daily_volume: float
    daily_trades: int


# Database helper
def get_db():
    db_path = os.getenv('DATABASE_URL', 'sqlite:///data/bridge.db').replace('sqlite:///', '')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# Lifespan - startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 API Server starting...")
    yield
    # Shutdown
    print("🛑 API Server shutting down...")


app = FastAPI(
    title="Polymarket-IB Bridge API",
    description="API dla arbitrage prediction markets",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # W produkcji: specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "polymarket-ib-bridge"}


@app.get("/contracts", response_model=List[ContractResponse])
def list_contracts(
    category: Optional[str] = None,
    active_only: bool = True
):
    """Lista kontraktów IB."""
    conn = get_db()
    
    query = "SELECT * FROM ib_contracts WHERE 1=1"
    params = []
    
    if active_only:
        query += " AND is_active = 1"
    if category:
        query += " AND category = ?"
        params.append(category)
        
    query += " ORDER BY category, symbol"
    
    cur = conn.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    
    return [
        ContractResponse(
            conid=row['conid'],
            symbol=row['symbol'],
            name=row['name'],
            category=row['category'],
            exchange=row['exchange'],
            expiry=row['expiry_date'],
            last_price=row['last_price'],
            is_active=bool(row['is_active'])
        )
        for row in rows
    ]


@app.get("/markets", response_model=List[MarketResponse])
def list_markets(
    min_volume: float = Query(50000, description="Minimalny volume 24h"),
    category: Optional[str] = None
):
    """Lista marketów Polymarket."""
    conn = get_db()
    
    query = "SELECT * FROM polymarket_markets WHERE volume_24h >= ?"
    params = [min_volume]
    
    if category:
        query += " AND category = ?"
        params.append(category)
        
    query += " ORDER BY volume_24h DESC"
    
    cur = conn.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    
    return [
        MarketResponse(
            slug=row['slug'],
            question=row['question'],
            category=row['category'],
            volume_24h=row['volume_24h'],
            yes_price=row['yes_price'],
            no_price=row['no_price'],
            end_date=row['end_date']
        )
        for row in rows
    ]


@app.get("/opportunities", response_model=List[OpportunityResponse])
def list_opportunities(
    min_signal: int = Query(5, ge=1, le=10),
    category: Optional[str] = None
):
    """Lista okazji handlowych."""
    conn = get_db()
    
    query = """
        SELECT o.*, c.ib_symbol, c.ib_name, p.question as poly_question
        FROM trade_opportunities o
        JOIN market_correlations mc ON o.correlation_id = mc.id
        JOIN ib_contracts c ON mc.ib_contract_symbol = c.symbol
        JOIN polymarket_markets p ON mc.poly_market_id = p.slug
        WHERE o.signal_strength >= ? AND o.executed = FALSE
    """
    params = [min_signal]
    
    if category:
        query += " AND c.category = ?"
        params.append(category)
        
    query += " ORDER BY o.signal_strength DESC, o.detected_at DESC LIMIT 20"
    
    cur = conn.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    
    return [
        OpportunityResponse(
            id=row['id'],
            poly_slug=row['poly_market_id'],
            poly_question=row['poly_question'],
            ib_symbol=row['ib_symbol'],
            correlation_score=row.get('correlation_score', 0),
            whale_volume=row['whale_volume_usd'],
            whale_direction=row['whale_direction'],
            poly_price=row['poly_price_current'],
            ib_price=row['ib_price_current'],
            signal_strength=row['signal_strength'],
            recommendation=row['recommendation'],
            detected_at=row['detected_at']
        )
        for row in rows
    ]


@app.get("/portfolio/paper", response_model=PortfolioResponse)
def get_paper_portfolio():
    """Podsumowanie paper trading portfolio."""
    conn = get_db()
    
    # Otwarte pozycje
    cur = conn.execute("SELECT COUNT(*) as cnt, SUM(quantity) as qty FROM paper_positions WHERE is_open = 1")
    row = cur.fetchone()
    positions_count = row['cnt'] or 0
    total_contracts = row['qty'] or 0
    
    # Ekspozycja
    cur = conn.execute("""
        SELECT SUM(quantity * avg_entry_price) as exposure 
        FROM paper_positions WHERE is_open = 1
    """)
    row = cur.fetchone()
    total_exposure = row['exposure'] or 0
    
    # Dzisiejsze statystyki
    today = __import__('datetime').datetime.now().strftime('%Y-%m-%d')
    cur = conn.execute("""
        SELECT realized_pnl, volume_traded, trades_count 
        FROM paper_pnl_daily WHERE date = ?
    """, (today,))
    row = cur.fetchone()
    
    conn.close()
    
    return PortfolioResponse(
        positions_count=positions_count,
        total_contracts=total_contracts,
        total_exposure_usd=round(total_exposure, 2),
        daily_realized_pnl=round(row['realized_pnl'], 2) if row else 0,
        daily_volume=round(row['volume_traded'], 2) if row else 0,
        daily_trades=row['trades_count'] if row else 0
    )


@app.get("/risk/status")
def get_risk_status():
    """Status risk management."""
    from ..risk.manager import RiskManager
    
    manager = RiskManager()
    return manager.get_risk_summary()


@app.post("/risk/kill-switch")
def trigger_kill_switch(reason: str):
    """Aktywuje kill switch (emergency stop)."""
    from ..risk.manager import RiskManager
    
    manager = RiskManager()
    manager.trigger_kill_switch(reason)
    return {"status": "activated", "reason": reason}


@app.delete("/risk/kill-switch")
def reset_kill_switch():
    """Deaktywuje kill switch."""
    from ..risk.manager import RiskManager
    
    manager = RiskManager()
    manager.reset_kill_switch()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
