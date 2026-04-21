"""
Testy jednostkowe dla modulu WhaleDetector.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.discovery.whale_detector import (
    WhaleSignal, WhaleDirection,
    ClobWhaleMonitor, PublicAPIWhaleMonitor,
    BlockchainWhaleMonitor, WhaleDetector,
)


def _make_async_cm(mock_response):
    """Tworzy async context manager dla aiohttp."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _make_mock_session(http_method="get", response_data=None, status=200):
    """Tworzy mock sesji aiohttp."""
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.json = AsyncMock(return_value=response_data if response_data is not None else {})
    mock_response.text = AsyncMock(return_value="")

    mock_session = MagicMock()
    setattr(mock_session, http_method, MagicMock(return_value=_make_async_cm(mock_response)))
    mock_session.close = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


class TestWhaleSignalConfidenceScore:
    def test_confidence_max_volume_max_impact(self):
        signal = WhaleSignal(
            market_slug="test", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=500000,
            price_before=0.35, price_after=0.40,
            timestamp=datetime.now(), source="clob"
        )
        assert signal.confidence_score == 10

    def test_confidence_duzy_volume_sredni_impact(self):
        signal = WhaleSignal(
            market_slug="test", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=100000,
            price_before=0.50, price_after=0.51,
            timestamp=datetime.now() - timedelta(minutes=3), source="clob"
        )
        assert 5 <= signal.confidence_score <= 8

    def test_confidence_sredni_volume_maly_impact(self):
        signal = WhaleSignal(
            market_slug="test", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=50000,
            price_before=0.50, price_after=0.505,
            timestamp=datetime.now() - timedelta(minutes=6), source="clob"
        )
        assert 3 <= signal.confidence_score <= 6

    def test_confidence_maly_volume(self):
        signal = WhaleSignal(
            market_slug="test", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=10000,
            price_before=0.50, price_after=0.501,
            timestamp=datetime.now() - timedelta(minutes=11), source="clob"
        )
        assert 0 <= signal.confidence_score <= 3

    def test_confidence_nie_swiezy(self):
        signal = WhaleSignal(
            market_slug="test", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=500000,
            price_before=0.30, price_after=0.40,
            timestamp=datetime.now() - timedelta(minutes=30), source="clob"
        )
        assert signal.confidence_score == 7

    def test_confidence_zero_price_before(self):
        signal = WhaleSignal(
            market_slug="test", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=500000,
            price_before=0, price_after=0.40,
            timestamp=datetime.now(), source="clob"
        )
        assert signal.price_impact == 0

    def test_price_impact_calculation(self):
        signal = WhaleSignal(
            market_slug="test", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=100000,
            price_before=0.50, price_after=0.55,
            timestamp=datetime.now(), source="clob"
        )
        assert signal.price_impact == pytest.approx(0.10, abs=1e-9)


class TestWhaleSignalIsFresh:
    def test_is_fresh_true(self):
        signal = WhaleSignal(
            market_slug="test", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=100000,
            price_before=0.50, price_after=0.55,
            timestamp=datetime.now() - timedelta(minutes=10), source="clob"
        )
        assert signal.is_fresh() is True

    def test_is_fresh_false(self):
        signal = WhaleSignal(
            market_slug="test", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=100000,
            price_before=0.50, price_after=0.55,
            timestamp=datetime.now() - timedelta(minutes=45), source="clob"
        )
        assert signal.is_fresh() is False

    def test_is_fresh_custom_max_age(self):
        signal = WhaleSignal(
            market_slug="test", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=100000,
            price_before=0.50, price_after=0.55,
            timestamp=datetime.now() - timedelta(minutes=5), source="clob"
        )
        assert signal.is_fresh(max_age_minutes=3) is False
        assert signal.is_fresh(max_age_minutes=10) is True


class TestClobWhaleMonitor:
    @pytest.mark.asyncio
    async def test_is_healthy_true(self):
        monitor = ClobWhaleMonitor(api_key="test-key")
        monitor.session = _make_mock_session("get", {}, 200)
        result = await monitor.is_healthy()
        assert result is True

    @pytest.mark.asyncio
    async def test_is_healthy_false(self):
        monitor = ClobWhaleMonitor()
        monitor.session = None
        result = await monitor.is_healthy()
        assert result is False

    @pytest.mark.asyncio
    async def test_get_large_trades_sukces(self):
        monitor = ClobWhaleMonitor(api_key="test-key")
        trade_data = {"trades": [{"size": 100000, "price": 0.50, "side": "buy",
            "outcome": "yes", "market_slug": "fed-march-2025",
            "market_question": "Will Fed raise?",
            "timestamp": datetime.now().isoformat(), "trader_address": "0x1234"}]}
        monitor.session = _make_mock_session("get", trade_data, 200)

        signals = await monitor.get_large_trades(min_volume=50000)

        assert len(signals) == 1
        assert signals[0].market_slug == "fed-march-2025"
        assert signals[0].volume_usd == 50000
        assert signals[0].direction == WhaleDirection.BUY_YES

    @pytest.mark.asyncio
    async def test_get_large_trades_blad_api(self):
        monitor = ClobWhaleMonitor()
        monitor.session = _make_mock_session("get", {}, 500)
        signals = await monitor.get_large_trades()
        assert len(signals) == 0

    @pytest.mark.asyncio
    async def test_get_large_trades_wyjatek(self):
        monitor = ClobWhaleMonitor()
        monitor.session = MagicMock()
        monitor.session.get = MagicMock(side_effect=Exception("Connection error"))
        signals = await monitor.get_large_trades()
        assert len(signals) == 0

    def test_parse_trade_buy_no(self):
        monitor = ClobWhaleMonitor()
        trade = {"size": 50000, "price": 0.60, "side": "buy", "outcome": "no",
            "market_slug": "test-market", "market_question": "Test?",
            "timestamp": datetime.now().isoformat()}
        signal = monitor._parse_trade(trade)
        assert signal is not None
        assert signal.direction == WhaleDirection.BUY_NO

    def test_parse_trade_sell_yes(self):
        monitor = ClobWhaleMonitor()
        trade = {"size": 30000, "price": 0.40, "side": "sell", "outcome": "yes",
            "market_slug": "test-market", "market_question": "Test?",
            "timestamp": datetime.now().isoformat()}
        signal = monitor._parse_trade(trade)
        assert signal is not None
        assert signal.direction == WhaleDirection.SELL_YES

    def test_parse_trade_sell_no(self):
        monitor = ClobWhaleMonitor()
        trade = {"size": 30000, "price": 0.40, "side": "sell", "outcome": "no",
            "market_slug": "test-market", "market_question": "Test?",
            "timestamp": datetime.now().isoformat()}
        signal = monitor._parse_trade(trade)
        assert signal is not None
        assert signal.direction == WhaleDirection.SELL_NO


class TestPublicAPIWhaleMonitor:
    @pytest.mark.asyncio
    async def test_is_healthy_true(self):
        monitor = PublicAPIWhaleMonitor()
        monitor.session = _make_mock_session("get", {}, 200)
        result = await monitor.is_healthy()
        assert result is True

    @pytest.mark.asyncio
    async def test_get_large_trades_volume_spike(self):
        monitor = PublicAPIWhaleMonitor()
        monitor.previous_volumes = {}
        market_data = {"slug": "fed-march-2025", "question": "Will Fed raise?",
            "volume24hr": 1000000, "updatedAt": datetime.now().isoformat(),
            "outcomes": [{"name": "Yes", "price": 0.35}, {"name": "No", "price": 0.65}]}
        monitor.previous_volumes["fed-march-2025"] = 400000
        monitor.session = _make_mock_session("get", [market_data], 200)

        signals = await monitor.get_large_trades(min_volume=500000)

    def test_analyze_market_binary(self):
        monitor = PublicAPIWhaleMonitor()
        monitor.previous_volumes = {}
        data = {"slug": "test-market", "question": "Test?", "volume24hr": 1000000,
            "outcomes": [{"name": "Yes", "price": 0.40}, {"name": "No", "price": 0.60}],
            "updatedAt": datetime.now().isoformat()}
        monitor.previous_volumes["test-market"] = 1000000
        signal = monitor._analyze_market(data, min_volume=50000)
        assert signal is None

    def test_analyze_market_nonbinary(self):
        monitor = PublicAPIWhaleMonitor()
        data = {"slug": "multi-market", "question": "Test?", "volume24hr": 1000000,
            "outcomes": [{"name": "A", "price": 0.3}, {"name": "B", "price": 0.3}, {"name": "C", "price": 0.4}]}
        signal = monitor._analyze_market(data, min_volume=50000)
        assert signal is None

    def test_analyze_market_volume_spike(self):
        monitor = PublicAPIWhaleMonitor()
        monitor.previous_volumes = {}
        monitor.price_history = {}
        data = {"slug": "spike-market", "question": "Test?", "volume24hr": 1000000,
            "outcomes": [{"name": "Yes", "price": 0.42}, {"name": "No", "price": 0.58}],
            "updatedAt": datetime.now().isoformat()}
        monitor.previous_volumes["spike-market"] = 300000
        monitor.price_history["spike-market"] = [(datetime.now(), 0.40)]

        signal = monitor._analyze_market(data, min_volume=500000)

        assert signal is not None
        assert signal.volume_usd == 700000
        assert signal.direction == WhaleDirection.BUY_YES

    def test_analyze_market_volume_za_maly(self):
        monitor = PublicAPIWhaleMonitor()
        monitor.previous_volumes = {}
        data = {"slug": "small-spike", "question": "Test?", "volume24hr": 1000000,
            "outcomes": [{"name": "Yes", "price": 0.40}, {"name": "No", "price": 0.60}]}
        monitor.previous_volumes["small-spike"] = 950000
        signal = monitor._analyze_market(data, min_volume=100000)
        assert signal is None


class TestWhaleDetectorDedup:
    def test_deduplicate_usuwa_duplikaty(self):
        detector = WhaleDetector(min_volume=50000)
        now = datetime.now()
        hist_signal = WhaleSignal(
            market_slug="fed-march-2025", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=100000,
            price_before=0.35, price_after=0.38, timestamp=now, source="clob"
        )
        detector.signals_history = [hist_signal]

        new_signal = WhaleSignal(
            market_slug="fed-march-2025", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=150000,
            price_before=0.35, price_after=0.39, timestamp=now, source="clob"
        )
        unique = detector._deduplicate([new_signal])
        assert len(unique) == 0

    def test_deduplicate_zostawia_rozne(self):
        detector = WhaleDetector(min_volume=50000)
        detector.signals_history = []
        new_signal = WhaleSignal(
            market_slug="eth-market", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=100000,
            price_before=0.45, price_after=0.48, timestamp=datetime.now(), source="clob"
        )
        unique = detector._deduplicate([new_signal])
        assert len(unique) == 1
        assert unique[0].market_slug == "eth-market"

    def test_deduplicate_rozny_kierunek(self):
        detector = WhaleDetector(min_volume=50000)
        now = datetime.now()
        hist_signal = WhaleSignal(
            market_slug="fed-march-2025", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=100000,
            price_before=0.35, price_after=0.38, timestamp=now, source="clob"
        )
        detector.signals_history = [hist_signal]

        new_signal = WhaleSignal(
            market_slug="fed-march-2025", market_question="Test?",
            direction=WhaleDirection.BUY_NO, volume_usd=100000,
            price_before=0.65, price_after=0.62, timestamp=now, source="clob"
        )
        unique = detector._deduplicate([new_signal])
        assert len(unique) == 1
        assert unique[0].direction == WhaleDirection.BUY_NO


class TestWhaleDetectorGetSignals:
    @pytest.mark.asyncio
    async def test_get_signals_clob_priorytet(self, sample_whale_signals_list):
        detector = WhaleDetector(clob_api_key="test-key")
        detector.clob.is_healthy = AsyncMock(return_value=True)
        detector.clob.get_large_trades = AsyncMock(return_value=sample_whale_signals_list)
        detector.public_api.is_healthy = AsyncMock(return_value=True)
        detector.public_api.get_large_trades = AsyncMock(return_value=[])
        detector.blockchain.is_healthy = AsyncMock(return_value=False)

        signals = await detector.get_signals()

        assert len(signals) == 3
        detector.clob.get_large_trades.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_signals_fallback_public(self):
        detector = WhaleDetector()
        detector.clob.is_healthy = AsyncMock(return_value=False)
        detector.public_api.is_healthy = AsyncMock(return_value=True)
        detector.public_api.get_large_trades = AsyncMock(return_value=[])
        detector.blockchain.is_healthy = AsyncMock(return_value=False)
        signals = await detector.get_signals()
        assert len(signals) == 0

    @pytest.mark.asyncio
    async def test_get_signals_brak_zrodel(self):
        detector = WhaleDetector()
        detector.clob.is_healthy = AsyncMock(return_value=False)
        detector.public_api.is_healthy = AsyncMock(return_value=False)
        detector.blockchain.is_healthy = AsyncMock(return_value=False)
        signals = await detector.get_signals()
        assert len(signals) == 0


class TestWhaleDetectorHighConfidence:
    def test_get_high_confidence(self):
        detector = WhaleDetector()
        now = datetime.now()
        high_signal = WhaleSignal(
            market_slug="high", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=500000,
            price_before=0.30, price_after=0.40, timestamp=now, source="clob"
        )
        detector.signals_history = [high_signal]
        high_conf = detector.get_high_confidence_signals(min_score=7)
        for s in high_conf:
            assert s.confidence_score >= 7
            assert s.is_fresh()

    def test_get_high_confidence_nie_swiezy(self):
        detector = WhaleDetector()
        old_signal = WhaleSignal(
            market_slug="old", market_question="Test?",
            direction=WhaleDirection.BUY_YES, volume_usd=500000,
            price_before=0.30, price_after=0.40,
            timestamp=datetime.now() - timedelta(hours=2), source="clob"
        )
        detector.signals_history = [old_signal]
        high_conf = detector.get_high_confidence_signals(min_score=7)
        assert len(high_conf) == 0


class TestBlockchainWhaleMonitor:
    @pytest.mark.asyncio
    async def test_is_healthy_true(self):
        monitor = BlockchainWhaleMonitor(rpc_url="https://polygon-rpc.com")
        monitor.session = _make_mock_session("post", {"result": "0x1"}, 200)
        result = await monitor.is_healthy()
        assert result is True

    @pytest.mark.asyncio
    async def test_get_large_trades_stub(self):
        monitor = BlockchainWhaleMonitor()
        result = await monitor.get_large_trades()
        assert result == []


class TestWhaleDetectorAsyncContextManager:
    @pytest.mark.asyncio
    async def test_aenter(self):
        detector = WhaleDetector()
        with patch.object(detector.clob, "__aenter__", AsyncMock()) as mock_clob, \
             patch.object(detector.public_api, "__aenter__", AsyncMock()) as mock_public, \
             patch.object(detector.blockchain, "__aenter__", AsyncMock()) as mock_chain:
            result = await detector.__aenter__()
            assert result is detector
            mock_clob.assert_awaited_once()
            mock_public.assert_awaited_once()
            mock_chain.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_aexit(self):
        detector = WhaleDetector()
        with patch.object(detector.clob, "__aexit__", AsyncMock()) as mock_clob, \
             patch.object(detector.public_api, "__aexit__", AsyncMock()) as mock_public, \
             patch.object(detector.blockchain, "__aexit__", AsyncMock()) as mock_chain:
            await detector.__aexit__(None, None, None)
            mock_clob.assert_awaited_once()
            mock_public.assert_awaited_once()
            mock_chain.assert_awaited_once()
