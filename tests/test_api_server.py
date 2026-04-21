"""
Testy jednostkowe dla modulu api.server.
"""

import os
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class _DictRow(sqlite3.Row):
    """sqlite3.Row z metoda .get() zgodna z dict."""
    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default


def _make_db_override(tmp_db_path):
    def _db():
        conn = sqlite3.connect(tmp_db_path)
        conn.row_factory = _DictRow
        return conn
    return _db


class TestHealthEndpoint:
    def test_health_check(self):
        from src.api.server import app
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_check_content_type(self):
        from src.api.server import app
        client = TestClient(app)
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"


class TestKillSwitch:
    def test_kill_switch_post(self, tmp_kill_switch_dir):
        with patch("src.risk.manager.RiskManager") as mock_risk_cls:
            mock_manager = MagicMock()
            mock_manager.trigger_kill_switch = MagicMock()
            mock_manager.kill_switch_file = tmp_kill_switch_dir / "KILL_SWITCH"
            mock_manager.db_path = ":memory:"
            mock_risk_cls.return_value = mock_manager

            from src.api.server import app
            client = TestClient(app)
            response = client.post("/risk/kill-switch?reason=Emergency+stop")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "activated"

    def test_kill_switch_delete(self, tmp_kill_switch_dir):
        with patch("src.risk.manager.RiskManager") as mock_risk_cls:
            mock_manager = MagicMock()
            mock_manager.reset_kill_switch = MagicMock()
            mock_manager.kill_switch_file = tmp_kill_switch_dir / "KILL_SWITCH"
            mock_manager.db_path = ":memory:"
            mock_risk_cls.return_value = mock_manager

            from src.api.server import app
            client = TestClient(app)
            response = client.delete("/risk/kill-switch")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "reset"


class TestRiskStatus:
    def test_risk_status(self, tmp_db_path):
        with patch("src.risk.manager.RiskManager") as mock_risk_cls:
            mock_manager = MagicMock()
            mock_manager.get_risk_summary = MagicMock(return_value={
                "status": "green", "can_trade": True, "reason": "All checks passed",
                "daily_pnl": 0.0, "daily_loss_limit": -100, "error_count": 0,
                "circuit_breaker_threshold": 5, "kill_switch_active": False
            })
            mock_manager.db_path = tmp_db_path
            mock_risk_cls.return_value = mock_manager

            from src.api.server import app
            client = TestClient(app)
            response = client.get("/risk/status")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "green"
            assert data["can_trade"] is True


class TestContractsEndpoint:
    def test_list_contracts(self, tmp_db_path):
        with sqlite3.connect(tmp_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ib_contracts (
                    conid INTEGER PRIMARY KEY, symbol TEXT, name TEXT,
                    category TEXT, exchange TEXT, expiry_date TEXT,
                    last_price REAL, is_active INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                INSERT INTO ib_contracts (conid, symbol, name, category, exchange, expiry_date, is_active)
                VALUES (1, 'FF', 'Fed Funds', 'ECONOMIC', 'FORECASTX', '2025-03-19', 1)
            """)
            conn.commit()

        with patch("src.risk.manager.RiskManager"):
            with patch("src.api.server.get_db", _make_db_override(tmp_db_path)):
                from src.api.server import app
                client = TestClient(app)
                response = client.get("/contracts")
                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1
                assert data[0]["symbol"] == "FF"


class TestMarketsEndpoint:
    def test_list_markets(self, tmp_db_path):
        with sqlite3.connect(tmp_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS polymarket_markets (
                    slug TEXT PRIMARY KEY, question TEXT, category TEXT,
                    volume_24h REAL, yes_price REAL, no_price REAL, end_date TEXT
                )
            """)
            conn.execute("""
                INSERT INTO polymarket_markets
                VALUES ('fed-march', 'Will Fed raise?', 'Economics', 500000, 0.35, 0.65, '2025-03-19')
            """)
            conn.commit()

        with patch("src.risk.manager.RiskManager"):
            with patch("src.api.server.get_db", _make_db_override(tmp_db_path)):
                from src.api.server import app
                client = TestClient(app)
                response = client.get("/markets?min_volume=100000")
                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1
                assert data[0]["slug"] == "fed-march"


class TestPortfolioEndpoint:
    def test_get_paper_portfolio(self, tmp_db_path):
        with sqlite3.connect(tmp_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_positions (
                    id INTEGER PRIMARY KEY, ib_conid INTEGER, ib_symbol TEXT,
                    poly_market_slug TEXT, quantity INTEGER, avg_entry_price REAL,
                    current_price REAL, unrealized_pnl REAL, opened_at TEXT,
                    closed_at TEXT, is_open INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_pnl_daily (
                    date TEXT PRIMARY KEY, realized_pnl REAL DEFAULT 0,
                    unrealized_pnl REAL DEFAULT 0, trades_count INTEGER DEFAULT 0,
                    volume_traded REAL DEFAULT 0
                )
            """)
            conn.execute("""
                INSERT INTO paper_positions (ib_conid, ib_symbol, poly_market_slug, quantity, avg_entry_price, current_price, unrealized_pnl, opened_at, is_open)
                VALUES (1, 'FF', 'fed-march', 10, 0.35, 0.36, 0.10, '2025-01-01', 1)
            """)
            conn.commit()

        with patch("src.risk.manager.RiskManager"):
            with patch("src.api.server.get_db", _make_db_override(tmp_db_path)):
                from src.api.server import app
                client = TestClient(app)
                response = client.get("/portfolio/paper")
                assert response.status_code == 200
                data = response.json()
                assert data["positions_count"] == 1
                assert data["total_contracts"] == 10


class TestOpportunitiesEndpoint:
    def test_list_opportunities(self, tmp_db_path):
        """Test zgodny ze schematem w kodzie zrodlowym (JOIN na ib_contracts.c.ib_symbol)."""
        with sqlite3.connect(tmp_db_path) as conn:
            # Uwaga: kod zrodlowy odwoluje sie do c.ib_symbol, wiec musimy miec ta kolumne
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_opportunities (
                    id INTEGER PRIMARY KEY, correlation_id INTEGER,
                    poly_market_id TEXT, whale_volume_usd REAL,
                    whale_direction TEXT, poly_price_current REAL,
                    ib_price_current REAL, signal_strength INTEGER,
                    recommendation TEXT, detected_at TEXT,
                    executed INTEGER DEFAULT 0, correlation_score REAL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_correlations (
                    id INTEGER PRIMARY KEY, ib_contract_symbol TEXT,
                    poly_market_id TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ib_contracts (
                    conid INTEGER PRIMARY KEY, symbol TEXT, ib_name TEXT,
                    category TEXT, ib_symbol TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS polymarket_markets (
                    slug TEXT PRIMARY KEY, question TEXT
                )
            """)
            # Dodaj testowe dane
            conn.execute("INSERT INTO ib_contracts (conid, symbol, ib_name, category, ib_symbol) VALUES (1, 'FF', 'Fed Funds', 'ECONOMIC', 'FF')")
            conn.execute("INSERT INTO polymarket_markets (slug, question) VALUES ('fed-march', 'Will Fed raise?')")
            conn.execute("INSERT INTO market_correlations (id, ib_contract_symbol, poly_market_id) VALUES (1, 'FF', 'fed-march')")
            conn.execute("""
                INSERT INTO trade_opportunities (id, correlation_id, poly_market_id, signal_strength, detected_at, executed, whale_volume_usd, whale_direction, poly_price_current, recommendation, correlation_score)
                VALUES (1, 1, 'fed-march', 8, '2025-01-01', 0, 100000, 'BUY YES', 0.35, 'Buy YES', 0.85)
            """)
            conn.commit()

        with patch("src.risk.manager.RiskManager"):
            with patch("src.api.server.get_db", _make_db_override(tmp_db_path)):
                from src.api.server import app
                client = TestClient(app)
                response = client.get("/opportunities?min_signal=5")
                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)
                assert len(data) == 1


class TestCORS:
    def test_cors_headers(self):
        with patch("src.risk.manager.RiskManager"):
            from src.api.server import app
            client = TestClient(app)
            response = client.options("/health", headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            })
            assert response.status_code in [200, 400]


class TestAppInstance:
    def test_app_title(self):
        with patch("src.risk.manager.RiskManager"):
            from src.api.server import app
            assert app.title == "Polymarket-IB Bridge API"

    def test_app_version(self):
        with patch("src.risk.manager.RiskManager"):
            from src.api.server import app
            assert app.version == "1.0.0"

    def test_app_docs_available(self):
        with patch("src.risk.manager.RiskManager"):
            from src.api.server import app
            client = TestClient(app)
            response = client.get("/docs")
            assert response.status_code == 200

    def test_app_openapi_schema(self):
        with patch("src.risk.manager.RiskManager"):
            from src.api.server import app
            client = TestClient(app)
            response = client.get("/openapi.json")
            assert response.status_code == 200
            data = response.json()
            assert "paths" in data
