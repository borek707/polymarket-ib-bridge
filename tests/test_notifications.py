"""
Testy jednostkowe dla modulu notifications.manager.

Mockujemy aiohttp:
- Wszystkie metody: async with aiohttp.ClientSession() as session:
- Telegram _send_message: async with session.post(...) as resp:
- Discord send_recommendation: async with session.post(...) as resp:
- Discord send_summary/send_error: await session.post(...)

Potrzebujemy hybrydowego mocka: post zwraca async CM (dla async with)
ALE tez moze byc awaitowany (dla await session.post()).
"""

from datetime import datetime
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch, Mock

import pytest

from src.notifications.manager import (
    TradeRecommendation,
    TelegramNotifier,
    DiscordNotifier,
    ConsoleNotifier,
    EmailNotifier,
    NotificationManager,
)


def _make_aiohttp_cm(mock_response):
    """Tworzy async context manager dla aiohttp odpowiedzi."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _make_mock_session(status=200):
    """Tworzy mock sesji aiohttp.
    
    Potrzebujemy:
    - session.post ktory dziala jako async CM (dla async with session.post())
    - session.post ktory tez dziala jako awaitable (dla await session.post())
    
    Rozwiazanie: AwaitableCM - obiekt ktory jest jednoczesnie:
    - awaitable (zwraca odpowiedz)
    - async CM (zwraca odpowiedz)
    """
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.text = AsyncMock(return_value="OK")
    mock_response.json = AsyncMock(return_value={"ok": True})

    class AwaitableCM:
        """Obiekt ktory mozna awaitowac i uzyc jako async CM."""
        def __init__(self, response):
            self._response = response
        async def __aenter__(self):
            return self._response
        async def __aexit__(self, *args):
            return None
        def __await__(self):
            async def _coro():
                return self._response
            return _coro().__await__()

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=AwaitableCM(mock_response))
    mock_session.close = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


class TestTradeRecommendationFormatMessage:
    def test_format_message_zawiera_market_name(self, sample_trade_recommendation):
        msg = sample_trade_recommendation.format_message()
        assert "Fed Interest Rate Decision" in msg

    def test_format_message_zawiera_action(self, sample_trade_recommendation):
        msg = sample_trade_recommendation.format_message()
        assert "BUY YES" in msg

    def test_format_message_zawiera_ceny(self, sample_trade_recommendation):
        msg = sample_trade_recommendation.format_message()
        assert "0.72" in msg
        assert "0.66" in msg

    def test_format_message_zawiera_confidence(self, sample_trade_recommendation):
        msg = sample_trade_recommendation.format_message()
        assert "9" in msg

    def test_format_message_zawiera_expected_profit(self, sample_trade_recommendation):
        msg = sample_trade_recommendation.format_message()
        assert "9.1" in msg

    def test_format_message_zawiera_reason(self, sample_trade_recommendation):
        msg = sample_trade_recommendation.format_message()
        assert "Whale bought" in msg

    def test_format_message_high_confidence_emoji(self):
        rec = TradeRecommendation(
            market_name="Test", poly_slug="test", ib_symbol="TEST", ib_conid=1,
            action="BUY YES", confidence=9, whale_volume=100000,
            poly_price=0.50, ib_suggested_price=0.45,
            expected_profit_pct=5.0, reason="Test"
        )
        assert "🟢" in rec.format_message()

    def test_format_message_medium_confidence_emoji(self):
        rec = TradeRecommendation(
            market_name="Test", poly_slug="test", ib_symbol="TEST", ib_conid=1,
            action="BUY YES", confidence=7, whale_volume=100000,
            poly_price=0.50, ib_suggested_price=0.45,
            expected_profit_pct=5.0, reason="Test"
        )
        assert "🟡" in rec.format_message()

    def test_format_message_low_confidence_emoji(self):
        rec = TradeRecommendation(
            market_name="Test", poly_slug="test", ib_symbol="TEST", ib_conid=1,
            action="BUY YES", confidence=4, whale_volume=100000,
            poly_price=0.50, ib_suggested_price=0.45,
            expected_profit_pct=5.0, reason="Test"
        )
        assert "🔴" in rec.format_message()


class TestTradeRecommendationRiskLevel:
    def test_risk_level_low(self, sample_trade_recommendation):
        assert "LOW" in sample_trade_recommendation._risk_level()

    def test_risk_level_medium(self):
        rec = TradeRecommendation(
            market_name="Test", poly_slug="test", ib_symbol="TEST", ib_conid=1,
            action="BUY YES", confidence=6, whale_volume=100000,
            poly_price=0.50, ib_suggested_price=0.45,
            expected_profit_pct=5.0, reason="Test"
        )
        assert "MEDIUM" in rec._risk_level()

    def test_risk_level_high(self):
        rec = TradeRecommendation(
            market_name="Test", poly_slug="test", ib_symbol="TEST", ib_conid=1,
            action="BUY YES", confidence=3, whale_volume=100000,
            poly_price=0.50, ib_suggested_price=0.45,
            expected_profit_pct=5.0, reason="Test"
        )
        assert "HIGH" in rec._risk_level()


class TestTradeRecommendationTimestamp:
    def test_timestamp_format(self):
        rec = TradeRecommendation(
            market_name="Test", poly_slug="test", ib_symbol="TEST", ib_conid=1,
            action="BUY YES", confidence=9, whale_volume=100000,
            poly_price=0.50, ib_suggested_price=0.45,
            expected_profit_pct=5.0, reason="Test"
        )
        assert ":" in rec._timestamp()


class TestTelegramNotifier:
    def test_init_z_parametrow(self):
        notifier = TelegramNotifier(bot_token="test_token", chat_id="12345")
        assert notifier.enabled is True
        assert notifier.bot_token == "test_token"
        assert notifier.chat_id == "12345"

    def test_init_bez_parametrow(self):
        with patch.dict("os.environ", {}, clear=True):
            notifier = TelegramNotifier()
            assert notifier.enabled is False

    @pytest.mark.asyncio
    async def test_send_recommendation_disabled(self, sample_trade_recommendation, caplog):
        import logging
        notifier = TelegramNotifier(bot_token=None, chat_id=None)
        with caplog.at_level(logging.INFO):
            await notifier.send_recommendation(sample_trade_recommendation)

    @pytest.mark.asyncio
    async def test_send_message_mock(self):
        notifier = TelegramNotifier(bot_token="test_token", chat_id="12345")
        mock_session = _make_mock_session(200)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            await notifier._send_message("Test message")
            mock_session.post.assert_called_once()
            _, kwargs = mock_session.post.call_args
            assert kwargs["json"]["chat_id"] == "12345"
            assert kwargs["json"]["text"] == "Test message"

    @pytest.mark.asyncio
    async def test_send_message_blad_api(self):
        notifier = TelegramNotifier(bot_token="test_token", chat_id="12345")
        mock_session = _make_mock_session(400)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(Exception):
                await notifier._send_message("Test")

    @pytest.mark.asyncio
    async def test_send_summary(self):
        notifier = TelegramNotifier(bot_token="test_token", chat_id="12345")
        mock_session = _make_mock_session(200)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            await notifier.send_summary(signals_count=5, trades_executed=3, pnl=25.50)
            mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_error(self):
        notifier = TelegramNotifier(bot_token="test_token", chat_id="12345")
        mock_session = _make_mock_session(200)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            await notifier.send_error("System failure detected")
            mock_session.post.assert_called_once()


class TestDiscordNotifier:
    def test_init_z_webhook(self):
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
        assert notifier.enabled is True

    def test_init_bez_webhook(self):
        with patch.dict("os.environ", {}, clear=True):
            notifier = DiscordNotifier()
            assert notifier.enabled is False

    @pytest.mark.asyncio
    async def test_send_recommendation_mock(self, sample_trade_recommendation):
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
        mock_session = _make_mock_session(204)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            await notifier.send_recommendation(sample_trade_recommendation)
            mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_recommendation_disabled(self, sample_trade_recommendation):
        notifier = DiscordNotifier(webhook_url=None)
        await notifier.send_recommendation(sample_trade_recommendation)

    @pytest.mark.asyncio
    async def test_send_summary(self):
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
        mock_session = _make_mock_session(204)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            await notifier.send_summary(signals=5, trades=3, pnl=25.50)
            mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_error(self):
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
        mock_session = _make_mock_session(204)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            await notifier.send_error("Connection lost")
            mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_recommendation_blad_webhook(self, sample_trade_recommendation, caplog):
        import logging
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
        mock_session = _make_mock_session(404)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            with caplog.at_level(logging.WARNING):
                await notifier.send_recommendation(sample_trade_recommendation)


class TestConsoleNotifier:
    @pytest.mark.asyncio
    async def test_send_recommendation_stdout(self, sample_trade_recommendation, capsys):
        notifier = ConsoleNotifier()
        await notifier.send_recommendation(sample_trade_recommendation)
        captured = capsys.readouterr()
        assert "WHALE SIGNAL" in captured.out
        assert "Fed Interest Rate Decision" in captured.out
        assert "BUY YES" in captured.out

    @pytest.mark.asyncio
    async def test_send_summary_stdout(self, capsys):
        notifier = ConsoleNotifier()
        await notifier.send_summary(signals_count=5, trades_executed=3, pnl=25.50)
        captured = capsys.readouterr()
        assert "5" in captured.out

    @pytest.mark.asyncio
    async def test_send_error_stdout(self, capsys):
        notifier = ConsoleNotifier()
        await notifier.send_error("Critical system error")
        captured = capsys.readouterr()
        assert "ERROR" in captured.out or "error" in captured.out.lower()


class TestEmailNotifier:
    def test_init_bez_konfiguracji(self):
        with patch.dict("os.environ", {}, clear=True):
            notifier = EmailNotifier()
            assert notifier.enabled is False

    @pytest.mark.asyncio
    async def test_send_recommendation_disabled(self, sample_trade_recommendation, caplog):
        import logging
        notifier = EmailNotifier()
        with caplog.at_level(logging.INFO):
            await notifier.send_recommendation(sample_trade_recommendation)


class TestNotificationManager:
    def test_init(self):
        manager = NotificationManager()
        assert manager.console is not None
        assert manager.telegram is not None
        assert manager.discord is not None
        assert manager.email is not None

    @pytest.mark.asyncio
    async def test_notify_opportunity(self, sample_trade_recommendation):
        manager = NotificationManager()
        manager.console.send_recommendation = AsyncMock()
        manager.telegram.send_recommendation = AsyncMock()
        manager.discord.send_recommendation = AsyncMock()
        manager.email.send_recommendation = AsyncMock()
        await manager.notify_opportunity(sample_trade_recommendation)
        manager.console.send_recommendation.assert_awaited_once()
        manager.telegram.send_recommendation.assert_awaited_once()
        manager.discord.send_recommendation.assert_awaited_once()
        manager.email.send_recommendation.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_notify_summary(self):
        manager = NotificationManager()
        manager.console.send_summary = AsyncMock()
        manager.telegram.send_summary = AsyncMock()
        manager.discord.send_summary = AsyncMock()
        manager.email.send_summary = AsyncMock()
        await manager.notify_summary(signals=5, trades=3, pnl=25.50)
        manager.console.send_summary.assert_awaited_once()
        manager.telegram.send_summary.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_notify_error(self):
        manager = NotificationManager()
        manager.console.send_error = AsyncMock()
        manager.telegram.send_error = AsyncMock()
        manager.discord.send_error = AsyncMock()
        manager.email.send_error = AsyncMock()
        await manager.notify_error("System error")
        manager.console.send_error.assert_awaited_once()
        manager.telegram.send_error.assert_awaited_once()
