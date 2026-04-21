"""
Paper Trading Engine - symulacja tradingu bez realnych pieniędzy.

Używamy tego do:
1. Testowania strategii bez ryzyka
2. Walidacji mapowania Polymarket -> IB
3. Mierzenia slippage (różnica między ceną na Poly a wykonaną na IB)
4. Budowania confidence przed przejściem na live
"""

import sqlite3
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List
import json

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class PaperOrder:
    """Symulowane zlecenie."""
    id: Optional[int]
    timestamp: datetime
    poly_market_slug: str
    poly_question: str
    ib_conid: int
    ib_symbol: str
    side: OrderSide
    quantity: int  # Liczba kontraktów
    limit_price: float  # Cena limit (0.01 - 0.99)
    
    # Ceny referencyjne (z momentu złożenia zlecenia)
    poly_price_at_order: float
    ib_bid_at_order: Optional[float]
    ib_ask_at_order: Optional[float]
    
    # Wynik symulacji
    status: OrderStatus = OrderStatus.PENDING
    filled_price: Optional[float] = None
    filled_timestamp: Optional[datetime] = None
    slippage: Optional[float] = None  # Różnica między oczekiwaną a wykonaną
    
    # PnL (dla zamkniętych pozycji)
    realized_pnl: Optional[float] = None
    fee_paid: Optional[float] = None


class PaperTradingEngine:
    """
    Silnik paper trading.
    
    Symuluje realizację zleceń na podstawie:
    - Cen z IB (bid/ask)
    - Cen z Polymarket (jako reference)
    - Realistycznego slippage
    """
    
    def __init__(self, db_path: str = 'data/bridge.db', fill_delay_seconds: int = 2):
        self.db_path = db_path
        self.fill_delay_seconds = fill_delay_seconds  # Symulacja opóźnienia
        self._init_db()
        
    def _init_db(self):
        """Inicjalizuje tabele dla paper trading."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS paper_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    poly_market_slug TEXT,
                    poly_question TEXT,
                    ib_conid INTEGER,
                    ib_symbol TEXT,
                    side TEXT,
                    quantity INTEGER,
                    limit_price REAL,
                    poly_price_at_order REAL,
                    ib_bid_at_order REAL,
                    ib_ask_at_order REAL,
                    status TEXT,
                    filled_price REAL,
                    filled_timestamp TEXT,
                    slippage REAL,
                    realized_pnl REAL
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS paper_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ib_conid INTEGER,
                    ib_symbol TEXT,
                    poly_market_slug TEXT,
                    quantity INTEGER,
                    avg_entry_price REAL,
                    current_price REAL,
                    unrealized_pnl REAL,
                    opened_at TEXT,
                    closed_at TEXT,
                    is_open BOOLEAN DEFAULT 1
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS paper_pnl_daily (
                    date TEXT PRIMARY KEY,
                    realized_pnl REAL DEFAULT 0,
                    unrealized_pnl REAL DEFAULT 0,
                    trades_count INTEGER DEFAULT 0,
                    volume_traded REAL DEFAULT 0
                )
            ''')
            
    def place_order(
        self,
        poly_market_slug: str,
        poly_question: str,
        ib_conid: int,
        ib_symbol: str,
        side: OrderSide,
        quantity: int,
        limit_price: float,
        poly_price: float,
        ib_bid: Optional[float],
        ib_ask: Optional[float]
    ) -> PaperOrder:
        """
        Składa symulowane zlecenie.
        
        W paper trading zlecenie jest od razu "filled" z realistycznym slippage.
        """
        order = PaperOrder(
            id=None,
            timestamp=datetime.now(),
            poly_market_slug=poly_market_slug,
            poly_question=poly_question,
            ib_conid=ib_conid,
            ib_symbol=ib_symbol,
            side=side,
            quantity=quantity,
            limit_price=limit_price,
            poly_price_at_order=poly_price,
            ib_bid_at_order=ib_bid,
            ib_ask_at_order=ib_ask,
            status=OrderStatus.PENDING
        )
        
        # Symulacja fill (realistyczny)
        order = self._simulate_fill(order)
        
        # Zapisz do bazy
        order.id = self._save_order(order)
        
        # Zaktualizuj pozycje
        if order.status == OrderStatus.FILLED:
            self._update_position(order)
            self._update_daily_stats(order)
            
        logger.info(f"[PAPER] Order {order.id}: {side.value} {quantity}x {ib_symbol} @ {order.filled_price}")
        
        return order
        
    def _simulate_fill(self, order: PaperOrder) -> PaperOrder:
        """
        Symuluje realizację zlecenia.
        
        Logika:
        - BUY: fill po ask (kupujesz drożej)
        - SELL: fill po bid (sprzedajesz taniej)
        - Dodajemy losowy slippage 0-2%
        """
        import random
        
        # Podstawowa cena
        if order.side == OrderSide.BUY:
            base_price = order.ib_ask_at_order or order.limit_price
            # Dodaj slippage (kupujesz drożej niż ask)
            slippage = random.uniform(0, 0.02)  # 0-2%
            filled_price = min(base_price * (1 + slippage), 0.99)
        else:  # SELL
            base_price = order.ib_bid_at_order or order.limit_price
            # Dodaj slippage (sprzedajesz taniej niż bid)
            slippage = random.uniform(0, 0.02)
            filled_price = max(base_price * (1 - slippage), 0.01)
        
        order.filled_price = round(filled_price, 4)
        order.filled_timestamp = datetime.now() + timedelta(seconds=self.fill_delay_seconds)
        order.slippage = round(slippage * 100, 2)  # w procentach
        order.fee_paid = round(0.01 * order.quantity, 4)
        order.status = OrderStatus.FILLED
        
        return order
        
    def _save_order(self, order: PaperOrder) -> int:
        """Zapisuje zlecenie do bazy."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute('''
                INSERT INTO paper_orders 
                (timestamp, poly_market_slug, poly_question, ib_conid, ib_symbol,
                 side, quantity, limit_price, poly_price_at_order, ib_bid_at_order,
                 ib_ask_at_order, status, filled_price, filled_timestamp, slippage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                order.timestamp.isoformat(),
                order.poly_market_slug,
                order.poly_question,
                order.ib_conid,
                order.ib_symbol,
                order.side.value,
                order.quantity,
                order.limit_price,
                order.poly_price_at_order,
                order.ib_bid_at_order,
                order.ib_ask_at_order,
                order.status.value,
                order.filled_price,
                order.filled_timestamp.isoformat() if order.filled_timestamp else None,
                order.slippage
            ))
            conn.commit()
            return cur.lastrowid
            
    def _update_position(self, order: PaperOrder):
        """Aktualizuje otwarte pozycje."""
        with sqlite3.connect(self.db_path) as conn:
            # Sprawdź czy mamy już pozycję w tym kontrakcie
            cur = conn.execute('''
                SELECT id, quantity, avg_entry_price FROM paper_positions
                WHERE ib_conid = ? AND is_open = 1
            ''', (order.ib_conid,))
            
            existing = cur.fetchone()
            
            if existing:
                position_id, current_qty, current_avg = existing
                
                if order.side == OrderSide.BUY:
                    # Dodaj do pozycji
                    new_qty = current_qty + order.quantity
                    new_avg = ((current_qty * current_avg) + (order.quantity * order.filled_price)) / new_qty
                    
                    conn.execute('''
                        UPDATE paper_positions 
                        SET quantity = ?, avg_entry_price = ?
                        WHERE id = ?
                    ''', (new_qty, round(new_avg, 4), position_id))
                else:
                    # Zmniejsz pozycję (częściowe zamknięcie)
                    closing_qty = min(order.quantity, current_qty)
                    new_qty = current_qty - order.quantity
                    
                    # Oblicz PnL tylko dla zamykanej części
                    realized_pnl = (order.filled_price - current_avg) * closing_qty
                    
                    if new_qty <= 0:
                        # Zamknij całkowicie
                        conn.execute('''
                            UPDATE paper_positions 
                            SET quantity = 0, is_open = 0, closed_at = ?,
                                realized_pnl = ?
                            WHERE id = ?
                        ''', (datetime.now().isoformat(), realized_pnl, position_id))
                    else:
                        # Aktualizuj pozycję i zapisz PnL
                        conn.execute('''
                            UPDATE paper_positions SET quantity = ?, realized_pnl = ? WHERE id = ?
                        ''', (new_qty, realized_pnl, position_id))
            else:
                # Nowa pozycja (tylko dla BUY)
                if order.side == OrderSide.BUY:
                    conn.execute('''
                        INSERT INTO paper_positions
                        (ib_conid, ib_symbol, poly_market_slug, quantity, avg_entry_price,
                         current_price, unrealized_pnl, opened_at, is_open)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    ''', (
                        order.ib_conid,
                        order.ib_symbol,
                        order.poly_market_slug,
                        order.quantity,
                        order.filled_price,
                        order.filled_price,
                        0.0,
                        datetime.now().isoformat()
                    ))
            
            conn.commit()
            
    def _update_daily_stats(self, order: PaperOrder):
        """Aktualizuje dzienne statystyki."""
        today = datetime.now().strftime('%Y-%m-%d')
        volume = order.quantity * order.filled_price
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO paper_pnl_daily (date, volume_traded, trades_count)
                VALUES (?, ?, 1)
                ON CONFLICT(date) DO UPDATE SET
                    volume_traded = volume_traded + excluded.volume_traded,
                    trades_count = trades_count + 1
            ''', (today, volume))
            conn.commit()
            
    def get_positions(self) -> List[dict]:
        """Zwraca otwarte pozycje."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute('''
                SELECT * FROM paper_positions WHERE is_open = 1
            ''')
            return [dict(row) for row in cur.fetchall()]
            
    def get_portfolio_summary(self) -> dict:
        """Podsumowanie portfolio paper trading."""
        positions = self.get_positions()
        
        total_exposure = sum(p['quantity'] * p['avg_entry_price'] for p in positions)
        total_contracts = sum(p['quantity'] for p in positions)
        
        # Dzisiejsze statystyki
        today = datetime.now().strftime('%Y-%m-%d')
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute('''
                SELECT realized_pnl, volume_traded, trades_count
                FROM paper_pnl_daily WHERE date = ?
            ''', (today,))
            row = cur.fetchone()
            
        daily_stats = {
            'realized_pnl': row[0] if row else 0,
            'volume_traded': row[1] if row else 0,
            'trades_count': row[2] if row else 0
        }
        
        return {
            'positions_count': len(positions),
            'total_contracts': total_contracts,
            'total_exposure_usd': round(total_exposure, 2),
            'daily_realized_pnl': round(daily_stats['realized_pnl'], 2),
            'daily_volume': round(daily_stats['volume_traded'], 2),
            'daily_trades': daily_stats['trades_count'],
            'positions': positions
        }
        
    def get_trade_history(self, limit: int = 50) -> List[dict]:
        """Historia zleceń."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute('''
                SELECT * FROM paper_orders
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cur.fetchall()]


if __name__ == '__main__':
    # Test paper trading
    logging.basicConfig(level=logging.INFO)
    
    engine = PaperTradingEngine()
    
    print("📊 Paper Trading Test\n")
    
    # Symuluj zlecenie BUY
    order = engine.place_order(
        poly_market_slug="fed-march-2025",
        poly_question="Will Fed raise rates in March 2025?",
        ib_conid=751047561,
        ib_symbol="FF",
        side=OrderSide.BUY,
        quantity=10,
        limit_price=0.35,
        poly_price=0.32,
        ib_bid=0.34,
        ib_ask=0.36
    )
    
    print(f"✅ Filled: {order.filled_price} (slippage: {order.slippage}%)")
    
    # Sprawdź pozycje
    summary = engine.get_portfolio_summary()
    print(f"\n📈 Portfolio:")
    print(f"   Contracts: {summary['total_contracts']}")
    print(f"   Exposure: ${summary['total_exposure_usd']}")
    
    # Symuluj SELL (zamknięcie)
    order2 = engine.place_order(
        poly_market_slug="fed-march-2025",
        poly_question="Will Fed raise rates in March 2025?",
        ib_conid=751047561,
        ib_symbol="FF",
        side=OrderSide.SELL,
        quantity=10,
        limit_price=0.40,
        poly_price=0.42,
        ib_bid=0.39,
        ib_ask=0.41
    )
    
    print(f"\n✅ Closed: {order2.filled_price}")
    
    summary = engine.get_portfolio_summary()
    print(f"\n📊 Final PnL: ${summary['daily_realized_pnl']}")
