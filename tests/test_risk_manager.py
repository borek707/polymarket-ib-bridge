"""
Testy jednostkowe dla modulu RiskManager.

Testy:
- check_all w stanie GREEN
- check_all z przekroczonym daily loss
- check_all z za duza pozycja
- check_rate_limit - przekroczenie limitu
- trigger_kill_switch i reset_kill_switch
- log_error - circuit breaker
- record_trade_pnl i get_daily_pnl
"""

import os
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.risk.manager import RiskManager, RiskCheck, RiskLevel


class TestCheckAllGreen:
    """Testy check_all w stanie GREEN."""

    def test_check_all_green(self, tmp_db_path):
        """Test check_all w stanie GREEN - wszystko OK."""
        manager = RiskManager(db_path=tmp_db_path)

        result = manager.check_all(position_size=30)

        assert result.level == RiskLevel.GREEN
        assert result.can_trade is True
        assert "passed" in result.reason.lower() or "All" in result.reason

    def test_check_all_green_pusta_pozycja(self, tmp_db_path):
        """Test check_all z pozycja 0."""
        manager = RiskManager(db_path=tmp_db_path)

        result = manager.check_all(position_size=0)

        assert result.level == RiskLevel.GREEN
        assert result.can_trade is True


class TestCheckAllDailyLoss:
    """Testy check_all z przekroczonym daily loss."""

    def test_check_all_daily_loss_przekroczony(self, tmp_db_path):
        """Test check_all gdy daily loss przekroczony."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.max_daily_loss = 100

        # Ustaw ujemny PnL
        manager.record_trade_pnl(realized_pnl=-150)

        result = manager.check_all(position_size=10)

        assert result.level == RiskLevel.RED
        assert result.can_trade is False
        assert "loss" in result.reason.lower() or "Daily" in result.reason

    def test_check_all_daily_loss_na_granicy(self, tmp_db_path):
        """Test check_all gdy daily loss dokladnie na limicie."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.max_daily_loss = 100

        # Ustaw PnL rowny limitowi
        manager.record_trade_pnl(realized_pnl=-100)

        result = manager.check_all(position_size=10)

        # Na granicy - powinien zablokowac (<= -max_daily_loss)
        assert result.level == RiskLevel.RED
        assert result.can_trade is False

    def test_check_all_yellow_blisko_limitu(self, tmp_db_path):
        """Test check_all gdy blisko limitu (YELLOW)."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.max_daily_loss = 100

        # Ustaw PnL na 75% limitu (czyli -70)
        manager.record_trade_pnl(realized_pnl=-75)

        result = manager.check_all(position_size=10)

        assert result.level == RiskLevel.YELLOW
        assert result.can_trade is True  # Jeszcze moze handlowac


class TestCheckAllPositionSize:
    """Testy check_all z za duza pozycja."""

    def test_check_all_za_duza_pozycja(self, tmp_db_path):
        """Test check_all gdy pozycja za duza."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.max_position_size = 50

        result = manager.check_all(position_size=100)

        assert result.level == RiskLevel.RED
        assert result.can_trade is False
        assert "size" in result.reason.lower() or "Position" in result.reason

    def test_check_all_pozycja_na_granicy(self, tmp_db_path):
        """Test check_all gdy pozycja dokladnie na limicie."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.max_position_size = 50

        result = manager.check_all(position_size=50)

        # Dokladnie na limicie - powinno przechodzic (> a nie >=)
        assert result.level == RiskLevel.GREEN


class TestCheckAllKillSwitch:
    """Testy check_all z kill switch."""

    def test_check_all_kill_switch_active(self, tmp_db_path, tmp_kill_switch_dir):
        """Test check_all gdy kill switch aktywny."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.kill_switch_file = tmp_kill_switch_dir / "KILL_SWITCH"
        manager.trigger_kill_switch("Test emergency")

        result = manager.check_all(position_size=10)

        assert result.level == RiskLevel.RED
        assert result.can_trade is False
        assert "Kill switch" in result.reason or "kill" in result.reason.lower()

    def test_check_all_kill_switch_nieaktywny(self, tmp_db_path, tmp_kill_switch_dir):
        """Test check_all gdy kill switch nieaktywny."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.kill_switch_file = tmp_kill_switch_dir / "KILL_SWITCH"

        result = manager.check_all(position_size=10)

        assert result.level == RiskLevel.GREEN
        assert result.can_trade is True


class TestCheckAllCircuitBreaker:
    """Testy check_all z circuit breaker."""

    def test_check_all_circuit_breaker(self, tmp_db_path):
        """Test check_all gdy circuit breaker aktywny."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.circuit_breaker_threshold = 5
        manager.error_count = 5

        result = manager.check_all(position_size=10)

        assert result.level == RiskLevel.RED
        assert result.can_trade is False
        assert "circuit" in result.reason.lower() or "error" in result.reason.lower()


class TestKillSwitch:
    """Testy trigger_kill_switch i reset_kill_switch."""

    def test_trigger_kill_switch(self, tmp_db_path, tmp_kill_switch_dir):
        """Test trigger_kill_switch."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.kill_switch_file = tmp_kill_switch_dir / "KILL_SWITCH"

        manager.trigger_kill_switch("Test reason")

        assert manager.kill_switch_file.exists()
        content = manager.kill_switch_file.read_text()
        assert "Test reason" in content

    def test_reset_kill_switch(self, tmp_db_path, tmp_kill_switch_dir):
        """Test reset_kill_switch."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.kill_switch_file = tmp_kill_switch_dir / "KILL_SWITCH"
        manager.trigger_kill_switch("Test")

        assert manager.kill_switch_file.exists()

        manager.reset_kill_switch()

        assert not manager.kill_switch_file.exists()

    def test_trigger_i_reset(self, tmp_db_path, tmp_kill_switch_dir):
        """Test cykl trigger + reset."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.kill_switch_file = tmp_kill_switch_dir / "KILL_SWITCH"

        # Trigger
        manager.trigger_kill_switch("Emergency stop")
        check1 = manager.check_all()
        assert check1.can_trade is False

        # Reset
        manager.reset_kill_switch()
        check2 = manager.check_all()
        assert check2.can_trade is True


class TestRateLimit:
    """Testy check_rate_limit."""

    def test_check_rate_limit_ok(self, tmp_db_path):
        """Test check_rate_limit - pierwsze wywolania przechodza."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.rate_limit = 10

        # Pierwsze 10 wywolan powinno przechodzic
        for i in range(10):
            assert manager.check_rate_limit() is True

    def test_check_rate_limit_przekroczenie(self, tmp_db_path):
        """Test check_rate_limit - przekroczenie limitu."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.rate_limit = 5

        # Pierwsze 5 wywolan przechodzi
        for i in range(5):
            assert manager.check_rate_limit() is True

        # 6-te wywolanie powinno zwrocic False
        assert manager.check_rate_limit() is False

    def test_check_rate_limit_po_czasie(self, tmp_db_path):
        """Test ze stare timestampy sa usuwane."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.rate_limit = 2

        # 2 wywolania - OK
        assert manager.check_rate_limit() is True
        assert manager.check_rate_limit() is True
        # 3 - przekroczenie
        assert manager.check_rate_limit() is False

        # Symuluj ze minela 1.1 sekundy
        import time
        cutoff = time.time() + 2.0
        with patch("time.time", return_value=cutoff):
            # Po czasie powinno byc znowu OK
            assert manager.check_rate_limit() is True


class TestLogError:
    """Testy log_error."""

    def test_log_error_zwieksza_counter(self, tmp_db_path):
        """Test ze log_error zwieksza error_count."""
        manager = RiskManager(db_path=tmp_db_path)
        assert manager.error_count == 0

        manager.log_error("TEST_ERROR", "Something went wrong")

        assert manager.error_count == 1

    def test_log_error_circuit_breaker(self, tmp_db_path, tmp_kill_switch_dir):
        """Test ze log_error aktywuje circuit breaker."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.kill_switch_file = tmp_kill_switch_dir / "KILL_SWITCH"
        manager.circuit_breaker_threshold = 3

        manager.log_error("ERR", "Error 1")
        manager.log_error("ERR", "Error 2")
        assert manager.error_count == 2

        # 3 blad - powinien aktywowac circuit breaker
        manager.log_error("ERR", "Error 3")
        assert manager.error_count >= 3

    def test_log_error_reset_po_czasie(self, tmp_db_path):
        """Test ze error_count resetuje sie po 5 minutach."""
        manager = RiskManager(db_path=tmp_db_path)
        manager.error_count = 3
        manager.last_error_time = datetime.now() - timedelta(minutes=10)

        manager.log_error("ERR", "New error after 10 min")

        # Counter powinien zostac zresetowany i zwiekszony o 1
        assert manager.error_count == 1

    def test_log_error_zapis_do_bazy(self, tmp_db_path):
        """Test ze blad jest zapisywany do bazy."""
        manager = RiskManager(db_path=tmp_db_path)

        manager.log_error("API_ERROR", "Connection timeout", "test_context")

        with sqlite3.connect(tmp_db_path) as conn:
            cur = conn.execute(
                "SELECT error_type, error_message, context FROM error_log WHERE error_type = ?",
                ("API_ERROR",)
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "API_ERROR"
            assert row[1] == "Connection timeout"
            assert row[2] == "test_context"


class TestRecordTradePnl:
    """Testy record_trade_pnl i get_daily_pnl."""

    def test_record_trade_pnl(self, tmp_db_path):
        """Test record_trade_pnl."""
        manager = RiskManager(db_path=tmp_db_path)

        manager.record_trade_pnl(realized_pnl=50.0, unrealized_pnl=10.0)

        pnl = manager.get_daily_pnl()
        assert pnl == 60.0

    def test_record_trade_pnl_negatywny(self, tmp_db_path):
        """Test record_trade_pnl z ujemnym PnL."""
        manager = RiskManager(db_path=tmp_db_path)

        manager.record_trade_pnl(realized_pnl=-30.0)

        pnl = manager.get_daily_pnl()
        assert pnl == -30.0

    def test_record_trade_pnl_agregacja(self, tmp_db_path):
        """Test ze wiel tradow jest agregowanych."""
        manager = RiskManager(db_path=tmp_db_path)

        manager.record_trade_pnl(realized_pnl=50.0)
        manager.record_trade_pnl(realized_pnl=30.0)
        manager.record_trade_pnl(realized_pnl=-20.0)

        pnl = manager.get_daily_pnl()
        assert pnl == 60.0  # 50 + 30 - 20

    def test_get_daily_pnl_brak_danych(self, tmp_db_path):
        """Test get_daily_pnl gdy brak danych."""
        manager = RiskManager(db_path=tmp_db_path)

        pnl = manager.get_daily_pnl()
        assert pnl == 0.0


class TestRiskSummary:
    """Testy get_risk_summary."""

    def test_get_risk_summary(self, tmp_db_path):
        """Test get_risk_summary."""
        manager = RiskManager(db_path=tmp_db_path)

        summary = manager.get_risk_summary()

        assert "status" in summary
        assert "can_trade" in summary
        assert "reason" in summary
        assert "daily_pnl" in summary
        assert "daily_loss_limit" in summary
        assert "error_count" in summary
        assert "circuit_breaker_threshold" in summary
        assert "kill_switch_active" in summary

        assert summary["status"] == "green"
        assert summary["can_trade"] is True
        assert summary["kill_switch_active"] is False


class TestDbInit:
    """Testy inicjalizacji bazy danych."""

    def test_db_creates_tables(self, tmp_db_path):
        """Test ze _init_db tworzy wszystkie tabele."""
        manager = RiskManager(db_path=tmp_db_path)

        with sqlite3.connect(tmp_db_path) as conn:
            cur = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table'
                AND name IN ('daily_pnl', 'error_log', 'circuit_breaker_events')
            """)
            tables = [row[0] for row in cur.fetchall()]
            assert "daily_pnl" in tables
            assert "error_log" in tables
            assert "circuit_breaker_events" in tables


class TestRiskManagerFromEnv:
    """Testy konfiguracji z env vars."""

    def test_init_z_env(self, tmp_db_path):
        """Test inicjalizacji z env vars."""
        with patch.dict(os.environ, {
            "MAX_DAILY_LOSS_USD": "200",
            "MAX_POSITION_SIZE_USD": "100",
            "CIRCUIT_BREAKER_ERRORS": "10",
            "RATE_LIMIT_MSG_PER_SEC": "20"
        }):
            manager = RiskManager(db_path=tmp_db_path)
            assert manager.max_daily_loss == 200
            assert manager.max_position_size == 100
            assert manager.circuit_breaker_threshold == 10
            assert manager.rate_limit == 20

    def test_init_default_values(self, tmp_db_path):
        """Test domyslnych wartosci."""
        with patch.dict(os.environ, {}, clear=True):
            manager = RiskManager(db_path=tmp_db_path)
            assert manager.max_daily_loss == 100
            assert manager.max_position_size == 50
            assert manager.circuit_breaker_threshold == 5
            assert manager.rate_limit == 10
