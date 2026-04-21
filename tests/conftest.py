"""
Fixtury wspolne dla wszystkich testow Polymarket-IB Bridge.

Uzywaj pytest, pytest-asyncio, unittest.mock.
Mockujemy WSZYSTKIE zewnetrzne wywolania HTTP (aiohttp) i IB (ib_insync).
"""

import asyncio
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock

import aiohttp
import pytest


# ---------------------------------------------------------------------------
# Fixtury pomocnicze
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db_path(tmp_path):
    """Sciezka do tymczasowej bazy SQLite."""
    return str(tmp_path / "test_bridge.db")


@pytest.fixture
def tmp_kill_switch_dir(tmp_path):
    """Tymczasowy katalog dla kill switch file."""
    ks_dir = tmp_path / "data"
    ks_dir.mkdir()
    return ks_dir


# ---------------------------------------------------------------------------
# Sample market data (Polymarket)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_binary_market_json():
    """Poprawny JSON binary marketu z Polymarket API."""
    return {
        "slug": "will-fed-raise-rates-march",
        "question": "Will the Fed raise interest rates in March 2025?",
        "description": "Federal Reserve target rate decision",
        "category": "Economics",
        "volume": 1500000,
        "volume24hr": 500000,
        "liquidity": 250000,
        "endDate": "2025-03-19T00:00:00Z",
        "resolutionDate": "2025-03-19T18:00:00Z",
        "outcomes": [
            {"name": "Yes", "price": 0.35},
            {"name": "No", "price": 0.65}
        ]
    }


@pytest.fixture
def sample_nonbinary_market_json():
    """JSON non-binary marketu (wiele outcomes)."""
    return {
        "slug": "multiple-choice-market",
        "question": "Who will win the election?",
        "description": "Multiple candidates",
        "category": "Politics",
        "volume": 2000000,
        "volume24hr": 800000,
        "liquidity": 500000,
        "endDate": "2025-11-05T00:00:00Z",
        "outcomes": [
            {"name": "Candidate A", "price": 0.4},
            {"name": "Candidate B", "price": 0.3},
            {"name": "Candidate C", "price": 0.2},
            {"name": "Candidate D", "price": 0.1}
        ]
    }


@pytest.fixture
def sample_incomplete_market_json():
    """JSON marketu z brakujacymi polami."""
    return {
        "slug": "broken-market",
        "category": "Unknown"
        # Brak outcomes, question, volume, endDate
    }


@pytest.fixture
def sample_markets_list(sample_binary_market_json):
    """Lista marketow do testow paginacji."""
    market2 = dict(sample_binary_market_json)
    market2["slug"] = "will-fed-raise-rates-april"
    market2["question"] = "Will the Fed raise interest rates in April 2025?"
    market2["volume24hr"] = 200000
    market3 = dict(sample_binary_market_json)
    market3["slug"] = "eth-above-3000"
    market3["question"] = "Will ETH be above $3000?"
    market3["category"] = "Crypto"
    market3["volume24hr"] = 75000  # Ponizej min_volume
    return [sample_binary_market_json, market2, market3]


# ---------------------------------------------------------------------------
# Sample IB contracts
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_ib_contracts():
    """Przykladowe kontrakty IB do testow korelacji."""
    from src.correlation.engine import IBContract as CorrIBContract
    return [
        CorrIBContract(
            conid=1, symbol='FF', name='Fed Funds Mar25 4.875C',
            category='ECONOMIC', expiry='2025-03-19', strike=4.875, right='C'
        ),
        CorrIBContract(
            conid=2, symbol='ETH', name='ETH Mar25 3000C',
            category='CRYPTO', expiry='2025-03-28', strike=3000, right='C'
        ),
        CorrIBContract(
            conid=3, symbol='CPI', name='CPI Mar25 3.0C',
            category='ECONOMIC', expiry='2025-03-15', strike=3.0, right='C'
        ),
    ]


@pytest.fixture
def sample_polymarket_markets():
    """Przykladowe markety Polymarket do testow korelacji."""
    from src.correlation.engine import PolymarketMarket as CorrPolyMarket
    return [
        CorrPolyMarket(
            slug="will-fed-raise-rates-march",
            question="Will the Fed raise interest rates in March 2025?",
            description="Federal Reserve target rate decision",
            category="Economics",
            volume_24h=500000,
            yes_price=0.35,
            no_price=0.65,
            end_date="2025-03-19"
        ),
        CorrPolyMarket(
            slug="trump-win-2024",
            question="Will Trump win the 2024 election?",
            description="US Presidential election",
            category="Politics",
            volume_24h=1000000,
            yes_price=0.52,
            no_price=0.48,
            end_date="2024-11-05"
        ),
        CorrPolyMarket(
            slug="eth-above-3000",
            question="Will ETH be above $3000 on March 31?",
            description="Ethereum price prediction",
            category="Crypto",
            volume_24h=200000,
            yes_price=0.45,
            no_price=0.55,
            end_date="2025-03-31"
        ),
    ]


# ---------------------------------------------------------------------------
# Mock fixtures dla aiohttp
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_aiohttp_session():
    """Mock sesji aiohttp.ClientSession."""
    session = AsyncMock()
    session.get = AsyncMock()
    session.post = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_aiohttp_response():
    """Mock odpowiedzi aiohttp."""
    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock()
    response.text = AsyncMock()
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    return response


# ---------------------------------------------------------------------------
# Mock fixtures dla IB (ib_insync)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ib():
    """Mock obiektu IB z ib_insync."""
    ib = MagicMock()
    ib.connectAsync = AsyncMock()
    ib.disconnect = Mock()
    ib.reqContractDetailsAsync = AsyncMock()
    ib.reqMktData = Mock()
    ib.cancelMktData = Mock()
    ib.placeOrder = Mock()
    ib.trades = Mock(return_value=[])
    ib.cancelOrder = Mock()
    ib.orderStatusEvent = MagicMock()
    return ib


# ---------------------------------------------------------------------------
# Whale fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_whale_signal():
    """Przykladowy sygnal wieloryba."""
    from src.discovery.whale_detector import WhaleSignal, WhaleDirection
    return WhaleSignal(
        market_slug="fed-march-2025",
        market_question="Will Fed raise rates in March?",
        direction=WhaleDirection.BUY_YES,
        volume_usd=200000,
        price_before=0.35,
        price_after=0.38,
        timestamp=datetime.now(),
        wallet_address="0x1234567890abcdef",
        tx_hash="0xabc123",
        source="clob"
    )


@pytest.fixture
def sample_whale_signals_list():
    """Lista sygnalow wielorybow."""
    from src.discovery.whale_detector import WhaleSignal, WhaleDirection
    now = datetime.now()
    return [
        WhaleSignal(
            market_slug="fed-march-2025",
            market_question="Will Fed raise rates?",
            direction=WhaleDirection.BUY_YES,
            volume_usd=500000,
            price_before=0.35,
            price_after=0.40,
            timestamp=now,
            wallet_address="0x1234",
            source="clob"
        ),
        WhaleSignal(
            market_slug="eth-above-3000",
            market_question="Will ETH be above $3000?",
            direction=WhaleDirection.BUY_YES,
            volume_usd=100000,
            price_before=0.45,
            price_after=0.47,
            timestamp=now - timedelta(minutes=3),
            wallet_address="0x5678",
            source="clob"
        ),
        WhaleSignal(
            market_slug="cpi-above-3",
            market_question="Will CPI be above 3%?",
            direction=WhaleDirection.BUY_NO,
            volume_usd=25000,
            price_before=0.60,
            price_after=0.61,
            timestamp=now - timedelta(minutes=10),
            wallet_address="0x9abc",
            source="public_api"
        ),
    ]


# ---------------------------------------------------------------------------
# Wallet / Tracker fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_wallet_score():
    """Przykladowy WalletScore."""
    from src.discovery.whale_tracker import WalletScore
    return WalletScore(
        address="0x1234567890abcdef",
        win_rate_90d=65.0,
        avg_roi=25.0,
        trade_frequency=45,
        total_volume=500000
    )


@pytest.fixture
def sample_whale_position():
    """Przykladowa pozycja wieloryba."""
    from src.discovery.whale_tracker import WhalePosition
    return WhalePosition(
        market_id="market-123",
        market_slug="fed-march-2025",
        market_question="Will Fed raise rates?",
        outcome="YES",
        size_usdc=10000,
        entry_price=0.35,
        entry_time=datetime.now(),
        wallet_address="0x1234567890abcdef",
        wallet_score=85.0
    )


@pytest.fixture
def sample_wallet_positions():
    """Lista pozycji portfela do testow."""
    from src.discovery.whale_tracker import WhalePosition
    return [
        WhalePosition(
            market_id="market-123",
            market_slug="fed-march-2025",
            market_question="Will Fed raise rates?",
            outcome="YES",
            size_usdc=10000,
            entry_price=0.35,
            entry_time=datetime.now(),
            wallet_address="0x1234",
            wallet_score=85.0
        ),
        WhalePosition(
            market_id="market-456",
            market_slug="eth-above-3000",
            market_question="Will ETH be above $3000?",
            outcome="NO",
            size_usdc=5000,
            entry_price=0.55,
            entry_time=datetime.now(),
            wallet_address="0x1234",
            wallet_score=85.0
        ),
    ]


# ---------------------------------------------------------------------------
# Trade / Paper trading fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_trade_recommendation():
    """Przykladowa rekomendacja tradeu."""
    from src.notifications.manager import TradeRecommendation
    return TradeRecommendation(
        market_name="Fed Interest Rate Decision - March 2025",
        poly_slug="fed-march-2025",
        ib_symbol="FF MAR25",
        ib_conid=751047561,
        action="BUY YES",
        confidence=9,
        whale_volume=200000,
        poly_price=0.72,
        ib_suggested_price=0.66,
        expected_profit_pct=9.1,
        reason="Whale bought $200k YES, IB hasn't caught up yet"
    )


# ---------------------------------------------------------------------------
# Async event loop fixtura
# ---------------------------------------------------------------------------

@pytest.fixture
def event_loop():
    """Tworzy nowa petla zdarzen dla kazdego testu."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
