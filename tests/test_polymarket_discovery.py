"""
Testy jednostkowe dla modulu PolymarketDiscovery.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.discovery.polymarket_discovery import PolymarketDiscovery, PolymarketMarket


class TestParseMarket:
    """Testy dla metody _parse_market."""

    def test_parse_market_poprawny_json(self, sample_binary_market_json):
        discovery = PolymarketDiscovery()
        market = discovery._parse_market(sample_binary_market_json)

        assert market is not None
        assert isinstance(market, PolymarketMarket)
        assert market.slug == "will-fed-raise-rates-march"
        assert market.question == "Will the Fed raise interest rates in March 2025?"
        assert market.category == "Economics"
        assert market.volume_total == 1500000
        assert market.volume_24h == 500000
        assert market.liquidity == 250000
        assert market.yes_price == 0.35
        assert market.no_price == 0.65
        assert isinstance(market.end_date, datetime)
        assert isinstance(market.resolution_date, datetime)

    def test_parse_market_nonbinary_zwraca_none(self, sample_nonbinary_market_json):
        discovery = PolymarketDiscovery()
        market = discovery._parse_market(sample_nonbinary_market_json)
        assert market is None

    def test_parse_market_brakujace_pola(self, sample_incomplete_market_json):
        discovery = PolymarketDiscovery()
        market = discovery._parse_market(sample_incomplete_market_json)
        assert market is None

    def test_parse_market_puste_yes_no_ceny(self):
        discovery = PolymarketDiscovery()
        data = {
            "slug": "test-market", "question": "Test?", "description": "Test",
            "category": "Test", "volume": 1000, "volume24hr": 500,
            "liquidity": 100, "endDate": "2025-03-19T00:00:00Z",
            "outcomes": [{"name": "Yes", "price": 0}, {"name": "No", "price": 0}]
        }
        assert discovery._parse_market(data) is None

    def test_parse_market_outcomes_jako_string(self):
        discovery = PolymarketDiscovery()
        data = {
            "slug": "test-market", "question": "Test?", "description": "Test",
            "category": "Test", "volume": 1000, "volume24hr": 500,
            "endDate": "2025-03-19T00:00:00Z", "outcomes": "invalid"
        }
        assert discovery._parse_market(data) is None

    def test_parse_market_wlasciwosci(self, sample_binary_market_json):
        discovery = PolymarketDiscovery()
        market = discovery._parse_market(sample_binary_market_json)
        assert market.implied_probability == 0.35
        assert market.spread == 1.0


class TestPolymarketMarketProperties:
    def test_implied_probability(self):
        market = PolymarketMarket(
            slug="test", question="Test?", description="Test", category="Test",
            volume_total=1000, volume_24h=500, liquidity=100,
            yes_price=0.72, no_price=0.28, end_date=datetime.now(), resolution_date=None
        )
        assert market.implied_probability == 0.72

    def test_spread(self):
        market = PolymarketMarket(
            slug="test", question="Test?", description="Test", category="Test",
            volume_total=1000, volume_24h=500, liquidity=100,
            yes_price=0.40, no_price=0.60, end_date=datetime.now(), resolution_date=None
        )
        assert market.spread == 1.0


def _make_async_cm(mock_response):
    """Tworzy async context manager dla aiohttp."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _make_mock_session(response_data, status=200):
    """Tworzy mock sesji aiohttp z async CM."""
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.json = AsyncMock(return_value=response_data)
    mock_response.text = AsyncMock(return_value="")

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=_make_async_cm(mock_response))
    mock_session.close = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


class TestGetActiveMarkets:
    @pytest.mark.asyncio
    async def test_get_active_markets_sukces(self, sample_binary_market_json):
        discovery = PolymarketDiscovery()
        discovery.session = _make_mock_session([sample_binary_market_json])

        markets = await discovery.get_active_markets(min_volume=100000)

        assert len(markets) == 1
        assert markets[0].slug == "will-fed-raise-rates-march"

    @pytest.mark.asyncio
    async def test_get_active_markets_pusta_lista(self):
        discovery = PolymarketDiscovery()
        discovery.session = _make_mock_session([])
        markets = await discovery.get_active_markets()
        assert len(markets) == 0

    @pytest.mark.asyncio
    async def test_get_active_markets_blad_http(self):
        discovery = PolymarketDiscovery()
        discovery.session = _make_mock_session([], status=500)
        markets = await discovery.get_active_markets()
        assert len(markets) == 0

    @pytest.mark.asyncio
    async def test_get_active_markets_filtrowanie_kategorii(self, sample_binary_market_json):
        discovery = PolymarketDiscovery()
        market_crypto = dict(sample_binary_market_json)
        market_crypto["slug"] = "eth-market"
        market_crypto["category"] = "Crypto"
        discovery.session = _make_mock_session([sample_binary_market_json, market_crypto])

        markets = await discovery.get_active_markets(min_volume=100000, category="Economics")
        assert len(markets) == 1
        assert markets[0].category == "Economics"

    @pytest.mark.asyncio
    async def test_get_active_markets_filtrowanie_volume(self, sample_markets_list):
        discovery = PolymarketDiscovery()
        discovery.session = _make_mock_session(sample_markets_list)

        markets = await discovery.get_active_markets(min_volume=100000)
        assert len(markets) == 2
        for m in markets:
            assert m.volume_24h >= 100000

    @pytest.mark.asyncio
    async def test_get_active_markets_wyjatek(self):
        discovery = PolymarketDiscovery()
        discovery.session = MagicMock()
        discovery.session.get = MagicMock(side_effect=aiohttp.ClientError("Connection failed"))

        markets = await discovery.get_active_markets()
        assert len(markets) == 0


class TestGetMarketBySlug:
    @pytest.mark.asyncio
    async def test_get_market_by_slug_sukces(self, sample_binary_market_json):
        discovery = PolymarketDiscovery()
        discovery.session = _make_mock_session(sample_binary_market_json)

        market = await discovery.get_market_by_slug("will-fed-raise-rates-march")

        assert market is not None
        assert market.slug == "will-fed-raise-rates-march"

    @pytest.mark.asyncio
    async def test_get_market_by_slug_nie_znaleziono(self):
        discovery = PolymarketDiscovery()
        discovery.session = _make_mock_session({}, status=404)

        market = await discovery.get_market_by_slug("nieistniejacy-market")
        assert market is None


class TestAsyncContextManager:
    @pytest.mark.asyncio
    async def test_aenter_tworzy_session(self):
        discovery = PolymarketDiscovery()
        assert discovery.session is None

        mock_session = _make_mock_session([])
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await discovery.__aenter__()
        assert result is discovery
        assert discovery.session is not None

    @pytest.mark.asyncio
    async def test_aexit_zamyka_session(self):
        discovery = PolymarketDiscovery()
        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        discovery.session = mock_session

        await discovery.__aexit__(None, None, None)
        mock_session.close.assert_awaited_once()


class TestGetWhaleActivity:
    @pytest.mark.asyncio
    async def test_get_whale_activity_stub(self):
        discovery = PolymarketDiscovery()
        result = await discovery.get_whale_activity()
        assert result == []
