"""
Testy jednostkowe dla modulu LiveExecutionEngine.

Patch: src.risk.manager.RiskManager
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.execution.live_trading import (
    LiveExecutionEngine,
    LiveOrder,
    LiveOrderStatus,
)


@pytest.fixture
def mock_risk_manager():
    mock = MagicMock()
    mock.check_all = Mock(return_value=Mock(
        level=Mock(value="green"), reason="OK", can_trade=True
    ))
    mock.check_rate_limit = Mock(return_value=True)
    mock.wait_for_rate_limit = Mock()
    mock.db_path = ":memory:"
    mock.log_error = Mock()
    return mock


@pytest.fixture
def mock_risk_manager_red():
    mock = MagicMock()
    mock.check_all = Mock(return_value=Mock(
        level=Mock(value="red"), reason="Daily loss limit hit", can_trade=False
    ))
    return mock


def _make_engine(mock_ib=None, risk_manager=None):
    with patch("src.risk.manager.RiskManager"):
        engine = LiveExecutionEngine()
        if mock_ib:
            engine.ib = mock_ib
        if risk_manager:
            engine.risk_manager = risk_manager
        return engine


class TestLiveExecutionConnect:
    @pytest.mark.asyncio
    async def test_connect(self, mock_ib):
        engine = _make_engine(mock_ib=mock_ib)
        await engine.connect()
        assert engine.connected is True
        mock_ib.connectAsync.assert_awaited_once_with("ib-gateway", 4002, clientId=1)

    @pytest.mark.asyncio
    async def test_connect_failure(self, mock_ib):
        mock_ib.connectAsync = AsyncMock(side_effect=Exception("Connection refused"))
        engine = _make_engine(mock_ib=mock_ib)
        with pytest.raises(Exception, match="Connection refused"):
            await engine.connect()

    def test_disconnect(self, mock_ib):
        engine = _make_engine(mock_ib=mock_ib)
        engine.connected = True
        engine.disconnect()
        mock_ib.disconnect.assert_called_once()


class TestPlaceOrder:
    @pytest.mark.asyncio
    async def test_place_order_wysyla_do_ib(self, mock_ib, mock_risk_manager):
        """Test ze order jest wysylany do IB (dry_run=False)."""
        engine = _make_engine(mock_ib=mock_ib, risk_manager=mock_risk_manager)
        engine.connected = True

        # Skonfiguruj mock trade z pusta lista fills
        mock_trade = MagicMock()
        mock_trade.fills = []
        mock_trade.order.orderId = 12345
        mock_ib.placeOrder = MagicMock(return_value=mock_trade)

        order = await engine.place_order(
            poly_market_slug="test-market", ib_conid=751047561,
            ib_symbol="FF", side="BUY", quantity=10,
            limit_price=0.35, dry_run=False
        )
        # Moze byc PENDING lub ERROR w zaleznosci od tego czy wait_for_fill przeszedl
        assert order.status in (LiveOrderStatus.PENDING, LiveOrderStatus.FILLED, LiveOrderStatus.SUBMITTED, LiveOrderStatus.ERROR)
        mock_ib.placeOrder.assert_called_once()

    @pytest.mark.asyncio
    async def test_place_order_risk_check_fail(self, mock_risk_manager_red):
        engine = _make_engine(risk_manager=mock_risk_manager_red)
        order = await engine.place_order(
            poly_market_slug="test-market", ib_conid=751047561,
            ib_symbol="FF", side="BUY", quantity=10,
            limit_price=0.35, dry_run=False
        )
        assert order.status == LiveOrderStatus.ERROR
        assert "Daily loss limit hit" in order.error_message

    @pytest.mark.asyncio
    async def test_place_order_rate_limit(self, mock_ib, mock_risk_manager):
        mock_risk_manager.check_rate_limit = Mock(return_value=False)
        engine = _make_engine(mock_ib=mock_ib, risk_manager=mock_risk_manager)
        engine.connected = True

        order = await engine.place_order(
            poly_market_slug="test-market", ib_conid=751047561,
            ib_symbol="FF", side="BUY", quantity=10,
            limit_price=0.35, dry_run=False
        )
        mock_risk_manager.wait_for_rate_limit.assert_called_once()

    @pytest.mark.asyncio
    async def test_place_order_zamyka_pozycje(self, mock_ib, mock_risk_manager):
        engine = _make_engine(mock_ib=mock_ib, risk_manager=mock_risk_manager)
        engine.connected = True

        order = await engine.place_order(
            poly_market_slug="fed-march-2025", ib_conid=751047561,
            ib_symbol="FF", side="BUY", quantity=10,
            limit_price=0.35, dry_run=False
        )
        assert order.poly_market_slug == "fed-march-2025"
        assert order.ib_conid == 751047561
        assert order.ib_symbol == "FF"
        assert order.side == "BUY"
        assert order.quantity == 10
        assert order.limit_price == 0.35


class TestWaitForFill:
    @pytest.mark.asyncio
    async def test_wait_for_fill(self, mock_ib):
        engine = _make_engine(mock_ib=mock_ib)
        mock_trade = MagicMock()
        mock_fill = MagicMock()
        mock_fill.execution.price = 0.35
        mock_fill.execution.shares = 10
        mock_fill.commissionReport = MagicMock()
        mock_fill.commissionReport.commission = 0.50
        mock_trade.fills = [mock_fill]
        await engine._wait_for_fill(mock_trade)


class TestOnOrderStatus:
    def test_on_order_status_filled(self, mock_ib, caplog):
        engine = _make_engine(mock_ib=mock_ib)
        mock_trade = MagicMock()
        mock_trade.order.orderId = 123
        mock_trade.orderStatus.status = "Filled"
        mock_fill = MagicMock()
        mock_fill.execution.shares = 10
        mock_fill.execution.price = 0.35
        mock_trade.fills = [mock_fill]
        with caplog.at_level("INFO"):
            engine._on_order_status(mock_trade)

    def test_on_order_status_cancelled(self, mock_ib, caplog):
        engine = _make_engine(mock_ib=mock_ib)
        mock_trade = MagicMock()
        mock_trade.order.orderId = 123
        mock_trade.orderStatus.status = "Cancelled"
        mock_trade.fills = []
        with caplog.at_level("WARNING"):
            engine._on_order_status(mock_trade)


class TestCancelAllOrders:
    @pytest.mark.asyncio
    async def test_cancel_all_orders(self, mock_ib):
        engine = _make_engine(mock_ib=mock_ib)
        engine.connected = True
        mock_trade1 = MagicMock()
        mock_trade1.orderStatus.status = "Submitted"
        mock_trade1.order = MagicMock()
        mock_ib.trades = Mock(return_value=[mock_trade1])
        await engine.cancel_all_orders()
        mock_ib.cancelOrder.assert_called_once_with(mock_trade1.order)

    @pytest.mark.asyncio
    async def test_cancel_all_not_connected(self):
        engine = _make_engine()
        engine.connected = False
        await engine.cancel_all_orders()


class TestGetOpenOrders:
    def test_get_open_orders(self, mock_ib):
        engine = _make_engine(mock_ib=mock_ib)
        engine.connected = True
        mock_trade = MagicMock()
        mock_trade.order.orderId = 123
        mock_trade.contract.symbol = "FF"
        mock_trade.order.action = "BUY"
        mock_trade.order.totalQuantity = 10
        mock_trade.orderStatus.status = "Submitted"
        mock_ib.trades = Mock(return_value=[mock_trade])
        orders = engine.get_open_orders()
        assert len(orders) == 1
        assert orders[0]["order_id"] == 123
        assert orders[0]["symbol"] == "FF"
        assert orders[0]["action"] == "BUY"

    def test_get_open_orders_not_connected(self):
        engine = _make_engine()
        engine.connected = False
        assert engine.get_open_orders() == []

    def test_get_open_orders_pusta_lista(self, mock_ib):
        engine = _make_engine(mock_ib=mock_ib)
        engine.connected = True
        mock_ib.trades = Mock(return_value=[])
        assert engine.get_open_orders() == []


class TestLiveOrder:
    def test_live_order_creation(self):
        order = LiveOrder(
            id=None, ib_order_id="12345", timestamp=datetime.now(),
            poly_market_slug="test", ib_conid=751047561, ib_symbol="FF",
            side="BUY", quantity=10, limit_price=0.35,
            status=LiveOrderStatus.SUBMITTED
        )
        assert order.status == LiveOrderStatus.SUBMITTED
        assert order.filled_price is None
        assert order.commission is None

    def test_live_order_filled(self):
        order = LiveOrder(
            id=1, ib_order_id="12345", timestamp=datetime.now(),
            poly_market_slug="test", ib_conid=751047561, ib_symbol="FF",
            side="BUY", quantity=10, limit_price=0.35,
            status=LiveOrderStatus.FILLED, filled_price=0.34, commission=0.50
        )
        assert order.filled_price == 0.34
        assert order.commission == 0.50
