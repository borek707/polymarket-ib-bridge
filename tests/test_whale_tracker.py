"""
Testy jednostkowe dla modulu WhaleTracker.

Testy:
- WalletScore.calculate() - sprawdza czy score jest w zakresie 0-100
- WhalePosition.is_significant()
- get_whale_consensus - rozne scenariusze (all YES, all NO, mixed)
- Mock get_wallet_positions
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.discovery.whale_tracker import (
    WalletScore,
    WhalePosition,
    WhaleSignal,
    WhaleTracker,
    WhaleTrackerAdapter,
)


class TestWalletScoreCalculate:
    """Testy dla WalletScore.calculate()."""

    def test_calculate_zakres_0_100(self, sample_wallet_score):
        """Test czy score jest w zakresie 0-100."""
        score = sample_wallet_score.calculate()
        assert 0 <= score <= 100

    def test_calculate_dobre_portfel(self):
        """Test dla dobrego portfela - wysoki score."""
        wallet = WalletScore(
            address="0x1234",
            win_rate_90d=80.0,
            avg_roi=50.0,
            trade_frequency=100,
            total_volume=1000000
        )
        score = wallet.calculate()
        assert score > 70

    def test_calculate_slaby_portfel(self):
        """Test dla slabego portfela - niski score."""
        wallet = WalletScore(
            address="0x5678",
            win_rate_90d=20.0,
            avg_roi=-30.0,
            trade_frequency=5,
            total_volume=1000
        )
        score = wallet.calculate()
        assert score < 30

    def test_calculate_roi_capped(self):
        """Test ze ROI jest capped na -50 i 100."""
        wallet = WalletScore(
            address="0x1234",
            win_rate_90d=50.0,
            avg_roi=-100.0,
            trade_frequency=50,
            total_volume=50000
        )
        score = wallet.calculate()
        assert 0 <= score <= 100

    def test_calculate_max_score(self):
        """Test maksymalnego score."""
        wallet = WalletScore(
            address="0x1234",
            win_rate_90d=100.0,
            avg_roi=100.0,
            trade_frequency=200,
            total_volume=10000000
        )
        score = wallet.calculate()
        assert score == 100

    def test_calculate_min_score(self):
        """Test minimalnego score."""
        wallet = WalletScore(
            address="0x1234",
            win_rate_90d=0.0,
            avg_roi=-200.0,
            trade_frequency=0,
            total_volume=0
        )
        score = wallet.calculate()
        assert score == 0

    def test_calculate_frequency_normalizacja(self):
        """Test normalizacji frequency (max 100 tradow = 100%)."""
        wallet_low_freq = WalletScore(
            address="0x1234",
            win_rate_90d=50.0,
            avg_roi=20.0,
            trade_frequency=10,
            total_volume=50000
        )
        wallet_high_freq = WalletScore(
            address="0x5678",
            win_rate_90d=50.0,
            avg_roi=20.0,
            trade_frequency=200,
            total_volume=50000
        )
        score_low = wallet_low_freq.calculate()
        score_high = wallet_high_freq.calculate()

        assert score_high > score_low


class TestWhalePositionIsSignificant:
    """Testy dla WhalePosition.is_significant()."""

    def test_is_significant_true(self, sample_whale_position):
        """Test pozycja >= min_size."""
        assert sample_whale_position.is_significant(min_size=500) is True
        assert sample_whale_position.is_significant(min_size=10000) is True

    def test_is_significant_false(self, sample_whale_position):
        """Test pozycja < min_size."""
        assert sample_whale_position.is_significant(min_size=50000) is False

    def test_is_significant_default(self):
        """Test domyslnego min_size=500."""
        pos = WhalePosition(
            market_id="m1",
            market_slug="test",
            market_question="Test?",
            outcome="YES",
            size_usdc=499,
            entry_price=0.50,
            entry_time=datetime.now(),
            wallet_address="0x1234",
            wallet_score=80.0
        )
        assert pos.is_significant() is False

        pos2 = WhalePosition(
            market_id="m2",
            market_slug="test",
            market_question="Test?",
            outcome="YES",
            size_usdc=501,
            entry_price=0.50,
            entry_time=datetime.now(),
            wallet_address="0x1234",
            wallet_score=80.0
        )
        assert pos2.is_significant() is True


class TestWhaleConsensus:
    """Testy dla get_whale_consensus."""

    def test_consensus_all_yes(self):
        """Test konsensus gdy wszystkie pozycje to YES."""
        tracker = WhaleTracker()

        wallet1 = WalletScore("0x1", 70, 30, 50, 500000)
        wallet1.composite_score = 80.0
        wallet2 = WalletScore("0x2", 65, 25, 40, 300000)
        wallet2.composite_score = 70.0

        tracker.tracked_wallets = {"0x1": wallet1, "0x2": wallet2}
        tracker.positions = {
            "0x1": {
                "market-123": WhalePosition(
                    market_id="market-123",
                    market_slug="test",
                    market_question="Test?",
                    outcome="YES",
                    size_usdc=10000,
                    entry_price=0.35,
                    entry_time=datetime.now(),
                    wallet_address="0x1",
                    wallet_score=80.0
                )
            },
            "0x2": {
                "market-123": WhalePosition(
                    market_id="market-123",
                    market_slug="test",
                    market_question="Test?",
                    outcome="YES",
                    size_usdc=5000,
                    entry_price=0.36,
                    entry_time=datetime.now(),
                    wallet_address="0x2",
                    wallet_score=70.0
                )
            }
        }

        result = tracker.get_whale_consensus("market-123")

        assert result["consensus"] == "YES"
        assert result["yes_count"] == 2
        assert result["no_count"] == 0
        assert result["yes_volume"] == 15000
        assert result["no_volume"] == 0
        assert result["confidence"] > 0.5

    def test_consensus_all_no(self):
        """Test konsensus gdy wszystkie pozycje to NO."""
        tracker = WhaleTracker()

        wallet1 = WalletScore("0x1", 70, 30, 50, 500000)
        wallet1.composite_score = 80.0

        tracker.tracked_wallets = {"0x1": wallet1}
        tracker.positions = {
            "0x1": {
                "market-456": WhalePosition(
                    market_id="market-456",
                    market_slug="test",
                    market_question="Test?",
                    outcome="NO",
                    size_usdc=20000,
                    entry_price=0.60,
                    entry_time=datetime.now(),
                    wallet_address="0x1",
                    wallet_score=80.0
                )
            }
        }

        result = tracker.get_whale_consensus("market-456")

        assert result["consensus"] == "NO"
        assert result["yes_count"] == 0
        assert result["no_count"] == 1
        assert result["yes_volume"] == 0
        assert result["no_volume"] == 20000

    def test_consensus_mixed(self):
        """Test konsensus gdy sa pozycje YES i NO."""
        tracker = WhaleTracker()

        wallet1 = WalletScore("0x1", 70, 30, 50, 500000)
        wallet1.composite_score = 80.0
        wallet2 = WalletScore("0x2", 65, 25, 40, 300000)
        wallet2.composite_score = 70.0

        tracker.tracked_wallets = {"0x1": wallet1, "0x2": wallet2}
        tracker.positions = {
            "0x1": {
                "market-789": WhalePosition(
                    market_id="market-789",
                    market_slug="test",
                    market_question="Test?",
                    outcome="YES",
                    size_usdc=10000,
                    entry_price=0.35,
                    entry_time=datetime.now(),
                    wallet_address="0x1",
                    wallet_score=80.0
                )
            },
            "0x2": {
                "market-789": WhalePosition(
                    market_id="market-789",
                    market_slug="test",
                    market_question="Test?",
                    outcome="NO",
                    size_usdc=8000,
                    entry_price=0.65,
                    entry_time=datetime.now(),
                    wallet_address="0x2",
                    wallet_score=70.0
                )
            }
        }

        result = tracker.get_whale_consensus("market-789")

        assert result["consensus"] == "MIXED"
        assert result["yes_count"] == 1
        assert result["no_count"] == 1

    def test_consensus_brak_pozycji(self):
        """Test konsensus gdy brak pozycji."""
        tracker = WhaleTracker()
        tracker.tracked_wallets = {}
        tracker.positions = {}

        result = tracker.get_whale_consensus("market-000")

        assert result["consensus"] == "NONE"
        assert result["confidence"] == 0


class TestGetWalletPositions:
    """Testy dla get_wallet_positions."""

    @pytest.mark.asyncio
    async def test_get_wallet_positions_sukces(self):
        """Mock test get_wallet_positions - sukces."""
        tracker = WhaleTracker(min_position_usdc=1000)

        positions_data = {
            "positions": [
                {
                    "marketId": "m1",
                    "marketSlug": "fed-march",
                    "question": "Will Fed raise?",
                    "outcome": "YES",
                    "size": 5000,
                    "avgPrice": 0.35,
                    "createdAt": datetime.now().isoformat()
                },
                {
                    "marketId": "m2",
                    "marketSlug": "eth-above",
                    "question": "Will ETH be above?",
                    "outcome": "NO",
                    "size": 500,
                    "avgPrice": 0.55,
                    "createdAt": datetime.now().isoformat()
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=positions_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_sess = MagicMock()
        mock_get_cm = MagicMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_cm.__aexit__ = AsyncMock(return_value=None)
        mock_sess.get = MagicMock(return_value=mock_get_cm)
        mock_sess.close = AsyncMock()

        tracker.tracked_wallets = {
            "0x1234": WalletScore("0x1234", 70, 30, 50, 500000)
        }

        with patch("aiohttp.ClientSession") as mock_sess_cls:
            mock_sess_instance = MagicMock()
            mock_get_cm2 = MagicMock()
            mock_get_cm2.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get_cm2.__aexit__ = AsyncMock(return_value=None)
            mock_sess_instance.get = MagicMock(return_value=mock_get_cm2)
            mock_sess_instance.close = AsyncMock()
            mock_sess_instance.__aenter__ = AsyncMock(return_value=mock_sess_instance)
            mock_sess_instance.__aexit__ = AsyncMock(return_value=None)
            mock_sess_cls.return_value = mock_sess_instance

            positions = await tracker.get_wallet_positions("0x1234")

        assert len(positions) == 1
        assert positions[0].size_usdc == 5000

    @pytest.mark.asyncio
    async def test_get_wallet_positions_blad(self):
        """Test get_wallet_positions gdy API zwraca blad."""
        tracker = WhaleTracker()

        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_sess_cls:
            mock_sess_instance = MagicMock()
            mock_get_cm = MagicMock()
            mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get_cm.__aexit__ = AsyncMock(return_value=None)
            mock_sess_instance.get = MagicMock(return_value=mock_get_cm)
            mock_sess_instance.close = AsyncMock()
            mock_sess_instance.__aenter__ = AsyncMock(return_value=mock_sess_instance)
            mock_sess_instance.__aexit__ = AsyncMock(return_value=None)
            mock_sess_cls.return_value = mock_sess_instance

            positions = await tracker.get_wallet_positions("0x1234")

        assert positions == []


class TestWhaleSignalDescription:
    """Testy dla WhaleSignal.description()."""

    def test_description_entry(self):
        """Test formatowania sygnalu ENTRY."""
        wallet = WalletScore("0x1234567890abcdef", 70, 30, 50, 500000)
        pos = WhalePosition(
            market_id="m1",
            market_slug="test",
            market_question="Test?",
            outcome="YES",
            size_usdc=10000,
            entry_price=0.35,
            entry_time=datetime.now(),
            wallet_address="0x1234567890abcdef",
            wallet_score=85.0
        )
        signal = WhaleSignal("ENTRY", wallet, pos)
        desc = signal.description()

        assert "ENTRY" in desc or "NEW" in desc
        assert "0x123456" in desc

    def test_description_exit(self):
        """Test formatowania sygnalu EXIT."""
        wallet = WalletScore("0xabcdef", 70, 30, 50, 500000)
        pos = WhalePosition(
            market_id="m1",
            market_slug="test",
            market_question="Test?",
            outcome="NO",
            size_usdc=5000,
            entry_price=0.60,
            entry_time=datetime.now(),
            wallet_address="0xabcdef",
            wallet_score=70.0
        )
        signal = WhaleSignal("EXIT", wallet, pos)
        desc = signal.description()

        assert "EXIT" in desc or "EXITED" in desc


class TestWhaleTrackerInit:
    """Testy inicjalizacji WhaleTracker."""

    def test_init_default(self):
        """Test domyslnej inicjalizacji."""
        tracker = WhaleTracker()
        assert tracker.min_whale_score == 65
        assert tracker.max_wallets_tracked == 50
        assert tracker.min_position_usdc == 500
        assert tracker.lookback_days == 90

    def test_init_custom(self):
        """Test inicjalizacji z custom parametrami."""
        tracker = WhaleTracker(
            min_whale_score=80,
            max_wallets_tracked=20,
            min_position_usdc=1000,
            lookback_days=30
        )
        assert tracker.min_whale_score == 80
        assert tracker.max_wallets_tracked == 20
        assert tracker.min_position_usdc == 1000
        assert tracker.lookback_days == 30
