"""
Notification system - multi-channel alerts (Telegram, Discord, Email, Console).
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class TradeRecommendation:
    """Rekomendacja trade'u do wysłania."""
    market_name: str
    poly_slug: str
    ib_symbol: str
    ib_conid: int
    action: str  # "BUY YES" lub "BUY NO"
    confidence: int  # 1-10
    whale_volume: float
    poly_price: float
    ib_suggested_price: float
    expected_profit_pct: float
    reason: str
    
    def format_message(self) -> str:
        """Formatuje ładną wiadomość do wysłania."""
        emoji = "🟢" if self.confidence >= 8 else "🟡" if self.confidence >= 6 else "🔴"
        
        message = f"""{emoji} <b>WHALE SIGNAL - Confidence {self.confidence}/10</b>

📊 <b>Market:</b> {self.market_name}
🐋 <b>Whale Activity:</b> ${self.whale_volume:,.0f}
🎯 <b>Action:</b> {self.action}

💰 <b>PRICES:</b>
• Polymarket: ${self.poly_price:.2f}
• IB Suggested: ${self.ib_suggested_price:.2f}
• Expected Profit: {self.expected_profit_pct:.1f}%

📝 <b>HOW TO EXECUTE:</b>
1. Open IB TWS / Mobile
2. Search: <code>{self.ib_symbol}</code>
3. Select "{self.action}"
4. Limit Price: <code>${self.ib_suggested_price:.2f}</code>
5. Quantity: 100 contracts ($100)
6. Submit Order

⚠️ <b>Risk:</b> {self._risk_level()}
💡 <b>Reason:</b> {self.reason}

<i>Signal time: {self._timestamp()}</i>
"""
        return message
    
    def _risk_level(self) -> str:
        if self.confidence >= 8:
            return "LOW - High confidence whale signal"
        elif self.confidence >= 6:
            return "MEDIUM - Moderate signal quality"
        else:
            return "HIGH - Low confidence, consider skipping"
    
    def _timestamp(self) -> str:
        return datetime.now().strftime("%H:%M:%S")


class TelegramNotifier:
    """Wysyła powiadomienia na Telegram."""
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            logger.warning("Telegram not configured - notifications disabled")
            logger.info("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
    
    async def send_recommendation(self, rec: TradeRecommendation):
        """Wysyła rekomendację na Telegram."""
        if not self.enabled:
            logger.info(f"[NOTIFICATION] {rec.market_name}: {rec.action}")
            return
            
        try:
            message = rec.format_message()
            await self._send_message(message)
            logger.info(f"✅ Telegram notification sent: {rec.market_name}")
        except Exception as e:
            logger.error(f"Failed to send Telegram: {e}")
    
    async def _send_message(self, text: str):
        """Wysyła wiadomość przez Bot API."""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise Exception(f"Telegram API error: {error}")
    
    async def send_summary(self, signals_count: int, trades_executed: int, pnl: float):
        """Wysyła podsumowanie dnia."""
        if not self.enabled:
            return
            
        emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
        
        message = f"""{emoji} <b>DAILY SUMMARY</b>

📊 Signals Detected: {signals_count}
📝 Trades Executed: {trades_executed}
💰 PnL: ${pnl:+.2f}

<i>Keep watching for whale activity...</i>
"""
        await self._send_message(message)
    
    async def send_error(self, error_message: str):
        """Wysyła alert o błędzie."""
        if not self.enabled:
            logger.error(f"[ERROR] {error_message}")
            return
            
        message = f"""🚨 <b>SYSTEM ERROR</b>

{error_message}

<i>Check logs and restart if needed.</i>
"""
        await self._send_message(message)


class ConsoleNotifier:
    """Notyfikacje w konsoli (gdy Telegram nie skonfigurowany)."""
    
    async def send_recommendation(self, rec: TradeRecommendation):
        """Wyświetla rekomendację w konsoli."""
        print("\n" + "=" * 60)
        print(f"🐋 WHALE SIGNAL - Confidence {rec.confidence}/10")
        print("=" * 60)
        print(f"Market: {rec.market_name}")
        print(f"Action: {rec.action}")
        print(f"IB Symbol: {rec.ib_symbol}")
        print(f"Suggested Price: ${rec.ib_suggested_price:.2f}")
        print(f"Expected Profit: {rec.expected_profit_pct:.1f}%")
        print("\n📋 EXECUTE IN IB:")
        print(f"  1. Search: {rec.ib_symbol}")
        print(f"  2. Select: {rec.action}")
        print(f"  3. Limit: ${rec.ib_suggested_price:.2f}")
        print(f"  4. Qty: 100")
        print(f"  5. Submit")
        print("=" * 60 + "\n")
    
    async def send_summary(self, signals_count: int, trades_executed: int, pnl: float):
        print(f"\n📊 Daily: {signals_count} signals, {trades_executed} trades, PnL: ${pnl:+.2f}\n")
    
    async def send_error(self, error_message: str):
        print(f"\n🚨 ERROR: {error_message}\n")


class DiscordNotifier:
    """Powiadomienia przez Discord webhook."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)
        
        if not self.enabled:
            logger.debug("Discord not configured")
    
    async def send_recommendation(self, rec: TradeRecommendation):
        """Wysyła embed na Discord."""
        if not self.enabled:
            return
            
        try:
            color = 0x00ff00 if rec.confidence >= 8 else 0xffaa00 if rec.confidence >= 6 else 0xff0000
            
            embed = {
                "title": f"🐋 WHALE SIGNAL - Confidence {rec.confidence}/10",
                "color": color,
                "fields": [
                    {"name": "📊 Market", "value": rec.market_name, "inline": False},
                    {"name": "🎯 Action", "value": rec.action, "inline": True},
                    {"name": "🐋 Whale Volume", "value": f"${rec.whale_volume:,.0f}", "inline": True},
                    {"name": "💰 Prices", "value": f"Poly: ${rec.poly_price:.2f}\nIB: ${rec.ib_suggested_price:.2f}", "inline": True},
                    {"name": "📈 Expected Profit", "value": f"{rec.expected_profit_pct:.1f}%", "inline": True},
                    {"name": "📝 How to Execute", "value": f"1. Open IB TWS\n2. Search: `{rec.ib_symbol}`\n3. Select: {rec.action}\n4. Limit: ${rec.ib_suggested_price:.2f}\n5. Qty: 100\n6. Submit", "inline": False},
                    {"name": "💡 Reason", "value": rec.reason, "inline": False}
                ],
                "timestamp": datetime.now().isoformat()
            }
            
            payload = {"embeds": [embed]}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload, timeout=10) as resp:
                    if resp.status not in [200, 204]:
                        logger.warning(f"Discord webhook failed: {resp.status}")
                        
        except Exception as e:
            logger.error(f"Discord error: {e}")
    
    async def send_summary(self, signals: int, trades: int, pnl: float):
        if not self.enabled:
            return
        color = 0x00ff00 if pnl > 0 else 0xff0000 if pnl < 0 else 0x808080
        embed = {
            "title": "📊 Daily Summary",
            "color": color,
            "fields": [
                {"name": "Signals", "value": str(signals), "inline": True},
                {"name": "Trades", "value": str(trades), "inline": True},
                {"name": "PnL", "value": f"${pnl:+.2f}", "inline": True}
            ]
        }
        async with aiohttp.ClientSession() as session:
            await session.post(self.webhook_url, json={"embeds": [embed]}, timeout=10)
    
    async def send_error(self, message: str):
        if not self.enabled:
            return
        embed = {
            "title": "🚨 System Error",
            "color": 0xff0000,
            "description": message
        }
        async with aiohttp.ClientSession() as session:
            await session.post(self.webhook_url, json={"embeds": [embed]}, timeout=10)


class EmailNotifier:
    """Powiadomienia przez email (SMTP)."""
    
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT") or "587")
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")
        self.to_email = os.getenv("ALERT_EMAIL")
        self.enabled = all([self.smtp_host, self.smtp_user, self.smtp_pass, self.to_email])
        
        if not self.enabled:
            logger.debug("Email not configured")
    
    async def send_recommendation(self, rec: TradeRecommendation):
        if not self.enabled:
            return
        # SMTP wymaga sync library - stub na razie
        logger.info(f"[EMAIL] Would send: {rec.market_name} - {rec.action}")
    
    async def send_summary(self, signals: int, trades: int, pnl: float):
        if not self.enabled:
            return
        logger.info(f"[EMAIL] Daily: {signals} signals, PnL: ${pnl:.2f}")
    
    async def send_error(self, message: str):
        if not self.enabled:
            return
        logger.error(f"[EMAIL] Error: {message}")


class NotificationManager:
    """Zarządza wszystkimi kanałami notyfikacji."""
    
    def __init__(self):
        self.console = ConsoleNotifier()
        self.telegram = TelegramNotifier()
        self.discord = DiscordNotifier()
        self.email = EmailNotifier()
        
        # Sprawdź które są aktywne
        active = []
        if self.telegram.enabled:
            active.append("Telegram")
        if self.discord.enabled:
            active.append("Discord")
        if self.email.enabled:
            active.append("Email")
        active.append("Console")
        
        logger.info(f"Notifications: {', '.join(active)}")
        
    async def notify_opportunity(self, rec: TradeRecommendation):
        """Wysyła powiadomienie o okazji wszystkimi kanałami."""
        await self.console.send_recommendation(rec)
        await self.telegram.send_recommendation(rec)
        await self.discord.send_recommendation(rec)
        await self.email.send_recommendation(rec)
        
    async def notify_summary(self, signals: int, trades: int, pnl: float):
        """Wysyła podsumowanie."""
        await self.console.send_summary(signals, trades, pnl)
        await self.telegram.send_summary(signals, trades, pnl)
        await self.discord.send_summary(signals, trades, pnl)
        await self.email.send_summary(signals, trades, pnl)
        
    async def notify_error(self, message: str):
        """Wysyła alert o błędzie."""
        await self.console.send_error(message)
        await self.telegram.send_error(message)
        await self.discord.send_error(message)
        await self.email.send_error(message)


if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    
    async def test():
        # Test notification
        notifier = NotificationManager()
        
        rec = TradeRecommendation(
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
        
        await notifier.notify_opportunity(rec)
    
    asyncio.run(test())
