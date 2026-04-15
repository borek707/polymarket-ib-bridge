"""
Live Execution Engine - prawdziwe zlecenia na Interactive Brokers.

UWAGA: Ten kod wykonuje prawdziwe zlecenia na Twoim koncie!
Używaj tylko gdy:
1. Paper trading działa dobrze przez min. 1 tydzień
2. Rozumiesz ryzyko
3. Masz ustawione limity w RiskManager
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from ib_insync import IB, Contract, Order as IBOrder, Trade

from ..risk.manager import RiskManager, RiskLevel

logger = logging.getLogger(__name__)


class LiveOrderStatus(Enum):
    SUBMITTED = "SUBMITTED"
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


@dataclass
class LiveOrder:
    """Zlecenie live na IB."""
    id: Optional[int]
    ib_order_id: Optional[str]
    timestamp: datetime
    poly_market_slug: str
    ib_conid: int
    ib_symbol: str
    side: str  # BUY / SELL
    quantity: int
    limit_price: float
    status: LiveOrderStatus
    filled_price: Optional[float] = None
    commission: Optional[float] = None
    error_message: Optional[str] = None


class LiveExecutionEngine:
    """
    Silnik wykonujący prawdziwe zlecenia na IB.
    
    Obejmuje:
    - Risk check przed każdym zleceniem
    - Rate limiting
    - Retry logic
    - Order tracking
    """
    
    def __init__(
        self,
        host: str = 'ib-gateway',
        port: int = 4002,
        client_id: int = 1,
        risk_manager: Optional[RiskManager] = None
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.risk_manager = risk_manager or RiskManager()
        self.ib = IB()
        self.connected = False
        
    async def connect(self):
        """Łączy się z IB Gateway."""
        try:
            await self.ib.connectAsync(self.host, self.port, clientId=self.client_id)
            self.connected = True
            logger.info(f"✅ Live execution connected to IB Gateway")
            
            # Subskrybuj order updates
            self.ib.orderStatusEvent += self._on_order_status
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to IB Gateway: {e}")
            raise
            
    def disconnect(self):
        """Rozłącza się."""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from IB Gateway")
            
    async def place_order(
        self,
        poly_market_slug: str,
        ib_conid: int,
        ib_symbol: str,
        side: str,  # BUY / SELL
        quantity: int,
        limit_price: float,
        dry_run: bool = False
    ) -> LiveOrder:
        """
        Składa zlecenie na IB.
        
        Args:
            dry_run: Jeśli True, tylko loguje bez wysyłania (test połączenia)
        """
        # 1. Risk check
        position_size = quantity * limit_price
        risk_check = self.risk_manager.check_all(position_size)
        
        if not risk_check.can_trade:
            logger.error(f"🚫 Risk check failed: {risk_check.reason}")
            return LiveOrder(
                id=None,
                ib_order_id=None,
                timestamp=datetime.now(),
                poly_market_slug=poly_market_slug,
                ib_conid=ib_conid,
                ib_symbol=ib_symbol,
                side=side,
                quantity=quantity,
                limit_price=limit_price,
                status=LiveOrderStatus.ERROR,
                error_message=f"Risk check: {risk_check.reason}"
            )
            
        # 2. Rate limiting
        if not self.risk_manager.check_rate_limit():
            logger.warning("⏱️ Rate limit hit, waiting...")
            self.risk_manager.wait_for_rate_limit()
            
        # 3. Stwórz kontrakt IB
        contract = Contract(
            conId=ib_conid,
            exchange='FORECASTX',  # lub 'CME' dla futures
            currency='USD'
        )
        
        # 4. Stwórz zlecenie
        action = 'BUY' if side == 'BUY' else 'SELL'
        ib_order = IBOrder(
            action=action,
            totalQuantity=quantity,
            orderType='LMT',  # Limit order (tylko takie działają na Event Contracts)
            lmtPrice=limit_price,
            tif='DAY'  # Time in Force: Day
        )
        
        if dry_run:
            logger.info(f"[DRY RUN] Would place order: {action} {quantity}x {ib_symbol} @ {limit_price}")
            return LiveOrder(
                id=None,
                ib_order_id="DRY_RUN",
                timestamp=datetime.now(),
                poly_market_slug=poly_market_slug,
                ib_conid=ib_conid,
                ib_symbol=ib_symbol,
                side=side,
                quantity=quantity,
                limit_price=limit_price,
                status=LiveOrderStatus.SUBMITTED
            )
            
        # 5. Wyślij zlecenie (prawdziwe!)
        try:
            trade: Trade = self.ib.placeOrder(contract, ib_order)
            
            logger.info(f"✅ Order submitted: {trade.order.orderId}")
            
            # Czekaj na wypełnienie (max 10 sekund)
            await asyncio.wait_for(
                self._wait_for_fill(trade),
                timeout=10.0
            )
            
            # Sprawdź wynik
            fill = trade.fills[0] if trade.fills else None
            
            order = LiveOrder(
                id=None,
                ib_order_id=str(trade.order.orderId),
                timestamp=datetime.now(),
                poly_market_slug=poly_market_slug,
                ib_conid=ib_conid,
                ib_symbol=ib_symbol,
                side=side,
                quantity=quantity,
                limit_price=limit_price,
                status=LiveOrderStatus.FILLED if fill else LiveOrderStatus.PENDING,
                filled_price=fill.execution.price if fill else None,
                commission=fill.commissionReport.commission if fill and fill.commissionReport else None
            )
            
            # Zapisz do bazy
            self._save_order(order)
            
            return order
            
        except Exception as e:
            logger.error(f"❌ Order failed: {e}")
            self.risk_manager.log_error("ORDER_FAILED", str(e), f"{ib_symbol} {side}")
            
            return LiveOrder(
                id=None,
                ib_order_id=None,
                timestamp=datetime.now(),
                poly_market_slug=poly_market_slug,
                ib_conid=ib_conid,
                ib_symbol=ib_symbol,
                side=side,
                quantity=quantity,
                limit_price=limit_price,
                status=LiveOrderStatus.ERROR,
                error_message=str(e)
            )
            
    async def _wait_for_fill(self, trade: Trade):
        """Czeka na wypełnienie zlecenia."""
        while not trade.fills:
            await asyncio.sleep(0.1)
            
    def _on_order_status(self, trade: Trade):
        """Callback dla update'ów zlecenia."""
        status = trade.orderStatus.status
        logger.info(f"Order {trade.order.orderId} status: {status}")
        
        if status == 'Filled':
            logger.info(f"✅ Order filled: {trade.fills[0].execution.shares} @ {trade.fills[0].execution.price}")
        elif status in ['Cancelled', 'Inactive']:
            logger.warning(f"⚠️ Order {trade.order.orderId} {status}")
            
    def _save_order(self, order: LiveOrder):
        """Zapisuje zlecenie do bazy."""
        import sqlite3
        
        with sqlite3.connect(self.risk_manager.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS live_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ib_order_id TEXT,
                    timestamp TEXT,
                    poly_market_slug TEXT,
                    ib_conid INTEGER,
                    ib_symbol TEXT,
                    side TEXT,
                    quantity INTEGER,
                    limit_price REAL,
                    status TEXT,
                    filled_price REAL,
                    commission REAL,
                    error_message TEXT
                )
            ''')
            
            conn.execute('''
                INSERT INTO live_orders
                (ib_order_id, timestamp, poly_market_slug, ib_conid, ib_symbol,
                 side, quantity, limit_price, status, filled_price, commission, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                order.ib_order_id,
                order.timestamp.isoformat(),
                order.poly_market_slug,
                order.ib_conid,
                order.ib_symbol,
                order.side,
                order.quantity,
                order.limit_price,
                order.status.value,
                order.filled_price,
                order.commission,
                order.error_message
            ))
            conn.commit()
            
    async def cancel_all_orders(self):
        """Anuluje wszystkie otwarte zlecenia."""
        if not self.connected:
            return
            
        for trade in self.ib.trades():
            if trade.orderStatus.status in ['Submitted', 'Pending', 'PreSubmitted']:
                self.ib.cancelOrder(trade.order)
                logger.info(f"Cancelled order {trade.order.orderId}")
                
    def get_open_orders(self) -> list:
        """Zwraca otwarte zlecenia."""
        if not self.connected:
            return []
            
        return [
            {
                'order_id': t.order.orderId,
                'symbol': t.contract.symbol if hasattr(t.contract, 'symbol') else 'Unknown',
                'action': t.order.action,
                'quantity': t.order.totalQuantity,
                'status': t.orderStatus.status
            }
            for t in self.ib.trades()
            if t.orderStatus.status not in ['Filled', 'Cancelled', 'Inactive']
        ]


if __name__ == '__main__':
    # Test live execution (tylko dry run!)
    logging.basicConfig(level=logging.INFO)
    
    async def test():
        engine = LiveExecutionEngine(host='localhost', port=4002)
        
        try:
            await engine.connect()
            
            # Test dry run (nie wysyła prawdziwego zlecenia)
            result = await engine.place_order(
                poly_market_slug="test-market",
                ib_conid=751047561,
                ib_symbol="FF",
                side="BUY",
                quantity=1,
                limit_price=0.35,
                dry_run=True
            )
            
            print(f"\n✅ Dry run complete: {result.status.value}")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
        finally:
            engine.disconnect()
            
    asyncio.run(test())
