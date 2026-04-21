"""
Testy jednostkowe dla modulu IBContractDiscovery.

Testy:
- IBContract wlasciwosci (mid_price, is_expired, days_to_expiry)
- Mock discover_all_contracts z ib_insync
- Mock _discover_symbol_chain
- refresh_prices
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.discovery.ib_discovery import IBContract, IBContractDiscovery


class TestIBContractProperties:
    def test_mid_price_z_bid_i_ask(self):
        contract = IBContract(
            conid=1, symbol="FF", name="Fed Funds Mar25 4.875C",
            exchange="FORECASTX", category="ECONOMIC",
            expiry=datetime.now() + timedelta(days=30),
            strike=4.875, right="C", bid=0.34, ask=0.36, last_price=None
        )
        assert contract.mid_price == 0.35

    def test_mid_price_bez_bid_ask(self):
        contract = IBContract(
            conid=1, symbol="FF", name="Fed Funds Mar25 4.875C",
            exchange="FORECASTX", category="ECONOMIC",
            expiry=datetime.now() + timedelta(days=30),
            strike=4.875, right="C", bid=None, ask=None, last_price=0.35
        )
        assert contract.mid_price == 0.35

    def test_mid_price_brak_wszystkiego(self):
        contract = IBContract(
            conid=1, symbol="FF", name="Fed Funds Mar25 4.875C",
            exchange="FORECASTX", category="ECONOMIC",
            expiry=datetime.now() + timedelta(days=30),
            strike=4.875, right="C", bid=None, ask=None, last_price=None
        )
        assert contract.mid_price is None

    def test_is_expired_false(self):
        contract = IBContract(
            conid=1, symbol="FF", name="Fed Funds Mar25 4.875C",
            exchange="FORECASTX", category="ECONOMIC",
            expiry=datetime.now() + timedelta(days=30),
            strike=4.875, right="C"
        )
        assert contract.is_expired is False

    def test_is_expired_true(self):
        contract = IBContract(
            conid=1, symbol="FF", name="Fed Funds Mar25 4.875C",
            exchange="FORECASTX", category="ECONOMIC",
            expiry=datetime.now() - timedelta(days=1),
            strike=4.875, right="C"
        )
        assert contract.is_expired is True

    def test_days_to_expiry(self):
        contract = IBContract(
            conid=1, symbol="FF", name="Fed Funds Mar25 4.875C",
            exchange="FORECASTX", category="ECONOMIC",
            expiry=datetime.now() + timedelta(days=15),
            strike=4.875, right="C"
        )
        assert 14 <= contract.days_to_expiry <= 15


class TestIBContractDiscovery:
    def test_init(self):
        with patch("ib_insync.IB"):
            discovery = IBContractDiscovery(host="localhost", port=4002)
            assert discovery.host == "localhost"
            assert discovery.port == 4002

    @pytest.mark.asyncio
    async def test_connect(self, mock_ib):
        with patch("ib_insync.IB"):
            discovery = IBContractDiscovery(host="localhost", port=4002)
            discovery.ib = mock_ib
            await discovery.connect()
            mock_ib.connectAsync.assert_awaited_once_with("localhost", 4002, clientId=99)

    def test_disconnect(self, mock_ib):
        """Test disconnect - kod zrodlowy nie ustawia connected=False (bug w zrodle).
        Testujemy ze disconnect jest wywolane na IB."""
        with patch("ib_insync.IB"):
            discovery = IBContractDiscovery()
            discovery.ib = mock_ib
            discovery.disconnect()
            mock_ib.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_all_contracts(self, mock_ib):
        with patch("ib_insync.IB"):
            discovery = IBContractDiscovery()
            discovery.ib = mock_ib

            mock_details = MagicMock()
            mock_contract = MagicMock()
            mock_contract.conId = 12345
            mock_contract.lastTradeDateOrContractMonth = (datetime.now() + timedelta(days=30)).strftime("%Y%m%d")
            mock_contract.strike = 4.875
            mock_contract.right = "C"
            mock_details.contract = mock_contract

            mock_ib.reqContractDetailsAsync = AsyncMock(return_value=[mock_details])
            contracts = await discovery.discover_all_contracts()
            assert len(contracts) > 0
            assert isinstance(contracts[0], IBContract)

    @pytest.mark.asyncio
    async def test_discover_symbol_chain_pomija_wygasle(self, mock_ib):
        with patch("ib_insync.IB"):
            discovery = IBContractDiscovery()
            discovery.ib = mock_ib

            mock_details = MagicMock()
            mock_contract = MagicMock()
            mock_contract.conId = 99999
            mock_contract.lastTradeDateOrContractMonth = (datetime.now() - timedelta(days=5)).strftime("%Y%m%d")
            mock_contract.strike = 4.875
            mock_contract.right = "C"
            mock_details.contract = mock_contract

            mock_ib.reqContractDetailsAsync = AsyncMock(return_value=[mock_details])
            contracts = await discovery._discover_symbol_chain("FF", "ECONOMIC", "FORECASTX")
            assert len(contracts) == 0

    @pytest.mark.asyncio
    async def test_discover_symbol_chain_pomija_za_bliskie(self, mock_ib):
        with patch("ib_insync.IB"):
            discovery = IBContractDiscovery()
            discovery.ib = mock_ib

            mock_details = MagicMock()
            mock_contract = MagicMock()
            mock_contract.conId = 88888
            mock_contract.lastTradeDateOrContractMonth = (datetime.now() + timedelta(hours=24)).strftime("%Y%m%d")
            mock_contract.strike = 4.875
            mock_contract.right = "C"
            mock_details.contract = mock_contract

            mock_ib.reqContractDetailsAsync = AsyncMock(return_value=[mock_details])
            contracts = await discovery._discover_symbol_chain("FF", "ECONOMIC", "FORECASTX")
            assert len(contracts) == 0

    @pytest.mark.asyncio
    async def test_discover_symbol_chain_niepoprawna_data(self, mock_ib):
        with patch("ib_insync.IB"):
            discovery = IBContractDiscovery()
            discovery.ib = mock_ib

            mock_details = MagicMock()
            mock_contract = MagicMock()
            mock_contract.conId = 77777
            mock_contract.lastTradeDateOrContractMonth = "invalid-date"
            mock_contract.strike = 4.875
            mock_contract.right = "C"
            mock_details.contract = mock_contract

            mock_ib.reqContractDetailsAsync = AsyncMock(return_value=[mock_details])
            contracts = await discovery._discover_symbol_chain("FF", "ECONOMIC", "FORECASTX")
            assert len(contracts) == 0

    @pytest.mark.asyncio
    async def test_refresh_prices(self, mock_ib):
        with patch("ib_insync.IB"):
            discovery = IBContractDiscovery()
            discovery.ib = mock_ib

            mock_ticker = MagicMock()
            mock_ticker.bid = 0.34
            mock_ticker.ask = 0.36
            mock_ticker.last = 0.35
            mock_ib.reqMktData = MagicMock(return_value=mock_ticker)

            contracts = [
                IBContract(
                    conid=12345, symbol="FF", name="Fed Funds Mar25 4.875C",
                    exchange="FORECASTX", category="ECONOMIC",
                    expiry=datetime.now() + timedelta(days=30),
                    strike=4.875, right="C"
                )
            ]
            updated = await discovery.refresh_prices(contracts)
            assert len(updated) == 1
            assert updated[0].bid == 0.34
            assert updated[0].ask == 0.36
            assert updated[0].last_price == 0.35

    @pytest.mark.asyncio
    async def test_refresh_prices_wyjatek(self, mock_ib):
        with patch("ib_insync.IB"):
            discovery = IBContractDiscovery()
            discovery.ib = mock_ib
            mock_ib.reqMktData = MagicMock(side_effect=Exception("No market data"))

            contracts = [
                IBContract(
                    conid=12345, symbol="FF", name="Fed Funds Mar25 4.875C",
                    exchange="FORECASTX", category="ECONOMIC",
                    expiry=datetime.now() + timedelta(days=30),
                    strike=4.875, right="C"
                )
            ]
            updated = await discovery.refresh_prices(contracts)
            assert len(updated) == 1
            assert updated[0].bid is None

    def test_base_symbols_zdefiniowane(self):
        with patch("ib_insync.IB"):
            discovery = IBContractDiscovery()
            assert "FF" in discovery.BASE_SYMBOLS
            assert "CPI" in discovery.BASE_SYMBOLS
            assert "ETH" in discovery.BASE_SYMBOLS
            assert "BTC" in discovery.BASE_SYMBOLS
            assert discovery.BASE_SYMBOLS["FF"]["category"] == "ECONOMIC"
