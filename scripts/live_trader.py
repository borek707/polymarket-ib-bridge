#!/usr/bin/env python3
"""
Script: live_trader.py

GŁÓWNA PĘTLA 24/7 - monitoring whale'ów + powiadomienia + live trading.

Flow:
1. Monitoruje Polymarket 24/7 (CLOB API / Public API)
2. Wykrywa wieloryby (volume spikes, large trades)
3. Mapuje na kontrakty IB (correlation engine)
4. Wysyła powiadomienia z dokładną instrukcją
5. (Opcjonalnie) Wykonuje automatycznie na IB
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.discovery.polymarket_discovery import PolymarketDiscovery
from src.discovery.ib_discovery import IBContractDiscovery
from src.discovery.whale_detector import WhaleDetector, WhaleDirection
from src.discovery.whale_tracker import WhaleTracker, WhaleTrackerAdapter, WhaleSignal
from src.correlation.engine import CorrelationEngine
from src.execution.live_trading import LiveTradingEngine, OrderSide
from src.risk.manager import RiskManager
from src.notifications.manager import NotificationManager, TradeRecommendation

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LiveTrader:
    """
    Główna klasa live trading - 24/7 monitoring i egzekucja.
    """
    
    def __init__(
        self,
        min_whale_volume: float = 50000,
        min_correlation_score: float = 0.7,
        min_signal_confidence: int = 7,
        check_interval: int = 30,
        auto_execute: bool = False,
        paper_mode: bool = True,
        use_whale_tracker: bool = True,  # NOWE: tracker portfeli
        min_whale_score: float = 65      # NOWE: min score wieloryba
    ):
        self.min_whale_volume = min_whale_volume
        self.min_correlation_score = min_correlation_score
        self.min_signal_confidence = min_signal_confidence
        self.check_interval = check_interval
        self.auto_execute = auto_execute
        self.paper_mode = paper_mode
        self.use_whale_tracker = use_whale_tracker
        self.min_whale_score = min_whale_score
        
        # Komponenty
        self.poly_discovery = PolymarketDiscovery()
        self.whale_detector = WhaleDetector(min_volume=min_whale_volume)
        self.ib_discovery = IBContractDiscovery()
        self.correlation_engine = CorrelationEngine()
        self.risk_manager = RiskManager()
        self.notifier = NotificationManager()
        
        # NOWE: Whale Tracker (z github.com/punkde99)
        self.whale_tracker = None
        self.whale_tracker_adapter = None
        if use_whale_tracker:
            self.whale_tracker = WhaleTracker(
                min_whale_score=min_whale_score,
                max_wallets_tracked=50
            )
            self.whale_tracker_adapter = WhaleTrackerAdapter(
                self.whale_tracker, 
                self.notifier
            )
            # Podłącz handler sygnałów
            self.whale_tracker.on_signal = self.whale_tracker_adapter.handle_signal
        
        # Execution engine (paper lub live)
        if paper_mode:
            from src.execution.paper_trading import PaperTradingEngine
            self.execution_engine = PaperTradingEngine()
            logger.info("📘 PAPER TRADING MODE (simulation)")
        else:
            self.execution_engine = LiveTradingEngine()
            logger.info("💰 LIVE TRADING MODE (REAL MONEY!)")
        
        # Statystyki
        self.start_time = datetime.now()
        self.signals_detected = 0
        self.trades_executed = 0
        self.total_pnl = 0.0
        
    async def run(self):
        """Główna pętla 24/7."""
        logger.info("=" * 70)
        logger.info("🚀 LIVE TRADER STARTED - 24/7 MONITORING")
        logger.info(f"⏱️  Check interval: {self.check_interval}s")
        logger.info(f"🐋 Min whale volume: ${self.min_whale_volume:,.0f}")
        logger.info(f"⭐ Min confidence: {self.min_signal_confidence}/10")
        logger.info(f"🤖 Auto-execution: {'ON' if self.auto_execute else 'OFF (alerts only)'}")
        logger.info(f"💰 Mode: {'PAPER' if self.paper_mode else 'LIVE'}")
        if self.use_whale_tracker:
            logger.info(f"🐋 Whale Tracker: ENABLED (min score: {self.min_whale_score})")
        logger.info("=" * 70)
        
        # NOWE: Inicjalizacja Whale Tracker
        if self.use_whale_tracker and self.whale_tracker:
            try:
                await self.whale_tracker.initialize()
                # Pokaż top wallets
                top_wallets = sorted(
                    self.whale_tracker.tracked_wallets.items(),
                    key=lambda x: x[1].composite_score,
                    reverse=True
                )[:10]
                logger.info("\n🏆 Top 10 Whale Wallets:")
                for addr, score in top_wallets:
                    logger.info(f"  {addr[:12]}... Score: {score.composite_score:.1f} | Win: {score.win_rate_90d:.1f}%")
            except Exception as e:
                logger.warning(f"Whale tracker init failed: {e}")
                self.use_whale_tracker = False
        
        # Połącz z IB (jeśli live mode)
        if not self.paper_mode:
            try:
                await self.ib_discovery.connect()
                ib_contracts = await self.ib_discovery.discover_all_contracts()
                logger.info(f"✅ IB connected, {len(ib_contracts)} contracts")
            except Exception as e:
                logger.error(f"❌ IB connection failed: {e}")
                logger.info("Falling back to cached contracts")
                ib_contracts = []
        else:
            ib_contracts = []
            
        # Główna pętla
        async with self.poly_discovery, self.whale_detector:
            while True:
                try:
                    # Risk check
                    risk = self.risk_manager.check_all()
                    if not risk.can_trade:
                        logger.warning(f"🚫 Risk halt: {risk.reason}")
                        await self.notifier.notify_error(f"Trading halted: {risk.reason}")
                        await asyncio.sleep(300)  # Wait 5 min
                        continue
                    
                    # Skanuj wieloryby (volume spikes)
                    await self._scan_and_notify(ib_contracts)
                    
                    # NOWE: Odśwież pozycje top wallets (co 5 minut)
                    if self.use_whale_tracker and self.whale_tracker:
                        if int((datetime.now() - self.start_time).total_seconds()) % 300 < self.check_interval:
                            await self.whale_tracker.refresh_positions()
                    
                    # Pokaż status
                    self._log_status()
                    
                    # Czekaj do następnego skanu
                    await asyncio.sleep(self.check_interval)
                    
                except Exception as e:
                    logger.error(f"❌ Error in main loop: {e}")
                    await self.notifier.notify_error(f"System error: {e}")
                    await asyncio.sleep(60)
                    
    async def _scan_and_notify(self, ib_contracts: list):
        """Skanuje wieloryby i wysyła powiadomienia."""
        logger.debug("🔍 Scanning for whale signals...")
        
        # Pobierz sygnały
        signals = await self.whale_detector.get_signals(lookback_minutes=2)
        
        # Filtrowanie
        high_conf_signals = [
            s for s in signals 
            if s.confidence_score >= self.min_signal_confidence
        ]
        
        if not high_conf_signals:
            return
            
        logger.info(f"🐋 Found {len(high_conf_signals)} high-confidence signals")
        
        # Przetwórz każdy sygnał
        for signal in high_conf_signals:
            await self._process_signal(signal, ib_contracts)
            
    async def _process_signal(self, signal, ib_contracts: list):
        """Przetwarza pojedynczy sygnał i wysyła rekomendację."""
        self.signals_detected += 1
        
        logger.info(f"🎯 Processing signal: {signal.market_question[:50]}...")
        
        # Pobierz aktualne dane marketu
        market = await self.poly_discovery.get_market_by_slug(signal.market_slug)
        if not market:
            logger.warning(f"   ❌ Cannot fetch market data")
            return
            
        # Znajdź korelację z IB
        corr = self.correlation_engine.correlate_single(market, ib_contracts)
        if not corr or corr.score < self.min_correlation_score:
            logger.info(f"   ⚠️  No IB correlation (score: {corr.score if corr else 0:.2f})")
            return
            
        logger.info(f"   ✅ IB correlation: {corr.ib_symbol} (score: {corr.score:.2f})")
        
        # Określ akcję
        if signal.direction in [WhaleDirection.BUY_YES, WhaleDirection.SELL_NO]:
            action = "BUY YES"
            target_price = market.yes_price
        else:
            action = "BUY NO"
            target_price = market.no_price
            
        # Estymacja ceny na IB (opóźnienie)
        ib_suggested_price = target_price * 0.97  # 3% discount
        expected_profit = ((target_price - ib_suggested_price) / ib_suggested_price) * 100
        
        # Stwórz rekomendację
        rec = TradeRecommendation(
            market_name=signal.market_question,
            poly_slug=signal.market_slug,
            ib_symbol=corr.ib_symbol,
            ib_conid=corr.ib_conid,
            action=action,
            confidence=signal.confidence_score,
            whale_volume=signal.volume_usd,
            poly_price=target_price,
            ib_suggested_price=ib_suggested_price,
            expected_profit_pct=expected_profit,
            reason=f"Whale {signal.direction.value} ${signal.volume_usd:,.0f}, IB hasn't caught up"
        )
        
        # Wyślij powiadomienie
        await self.notifier.notify_opportunity(rec)
        
        # Wykonaj (jeśli auto-execution ON)
        if self.auto_execute:
            await self._execute_trade(rec, market)
        else:
            logger.info(f"   📧 Alert sent - manual execution required")
            
    async def _execute_trade(self, rec: TradeRecommendation, market):
        """Wykonuje trade na IB."""
        # Risk check per trade
        if not self.risk_manager.can_open_position(rec.ib_suggested_price * 100):
            logger.warning(f"   🚫 Risk limits prevent execution")
            return
            
        # Określ side
        side = OrderSide.BUY if "BUY" in rec.action else OrderSide.SELL
        
        # Wykonaj
        try:
            order = self.execution_engine.place_order(
                poly_market_slug=rec.poly_slug,
                poly_question=rec.market_name,
                ib_conid=rec.ib_conid,
                ib_symbol=rec.ib_symbol,
                side=side,
                quantity=100,  # $100 jeśli price ~$1
                limit_price=rec.ib_suggested_price,
                poly_price=rec.poly_price,
                ib_bid=rec.ib_suggested_price - 0.01,
                ib_ask=rec.ib_suggested_price + 0.01
            )
            
            if order.status.value == "FILLED":
                self.trades_executed += 1
                logger.info(f"   ✅ EXECUTED: {order.filled_quantity} @ ${order.filled_price:.2f}")
                
                # Powiadom o sukcesie
                await self.notifier.telegram.send_message(
                    f"✅ <b>TRADE EXECUTED</b>\n\n"
                    f"{rec.ib_symbol}: {rec.action}\n"
                    f"Price: ${order.filled_price:.2f}\n"
                    f"Qty: {order.filled_quantity}"
                )
            else:
                logger.info(f"   ❌ Order {order.status.value}")
                
        except Exception as e:
            logger.error(f"   ❌ Execution error: {e}")
            await self.notifier.notify_error(f"Trade execution failed: {e}")
            
    def _log_status(self):
        """Loguje status systemu."""
        runtime = datetime.now() - self.start_time
        hours = runtime.total_seconds() / 3600
        
        logger.info(
            f"📊 Status: {self.signals_detected} signals | "
            f"{self.trades_executed} trades | "
            f"Runtime: {hours:.1f}h"
        )
        
        # Co godzinę wyślij podsumowanie
        if int(hours) > 0 and int(hours) % 1 == 0:
            asyncio.create_task(
                self.notifier.notify_summary(
                    self.signals_detected,
                    self.trades_executed,
                    self.total_pnl
                )
            )


def main():
    parser = argparse.ArgumentParser(description='Live Trader - 24/7 Whale Monitoring')
    parser.add_argument('--paper', action='store_true', default=True, 
                        help='Paper trading mode (default)')
    parser.add_argument('--live', action='store_true',
                        help='LIVE TRADING MODE (REAL MONEY!)')
    parser.add_argument('--auto', action='store_true',
                        help='Auto-execution (default: alerts only)')
    parser.add_argument('--interval', type=int, default=30,
                        help='Check interval in seconds (default: 30)')
    parser.add_argument('--min-volume', type=float, default=50000,
                        help='Min whale volume (default: 50000)')
    parser.add_argument('--min-confidence', type=int, default=7,
                        help='Min signal confidence 1-10 (default: 7)')
    parser.add_argument('--no-wallet-tracker', action='store_true',
                        help='Disable wallet-based whale tracker')
    parser.add_argument('--min-whale-score', type=float, default=65,
                        help='Min whale wallet score 0-100 (default: 65)')
    
    args = parser.parse_args()
    
    # Live mode wymaga potwierdzenia
    if args.live:
        print("\n" + "=" * 60)
        print("⚠️  LIVE TRADING MODE - REAL MONEY!")
        print("=" * 60)
        confirm = input("Type 'YES' to confirm: ")
        if confirm != "YES":
            print("Cancelled.")
            return
        paper_mode = False
    else:
        paper_mode = True
    
    trader = LiveTrader(
        min_whale_volume=args.min_volume,
        min_confidence=args.min_confidence,
        check_interval=args.interval,
        auto_execute=args.auto,
        paper_mode=paper_mode,
        use_whale_tracker=not args.no_wallet_tracker,
        min_whale_score=args.min_whale_score
    )
    
    try:
        asyncio.run(trader.run())
    except KeyboardInterrupt:
        logger.info("\n🛑 Stopped by user")
        print(f"\n📊 Session Summary:")
        print(f"   Signals: {trader.signals_detected}")
        print(f"   Trades: {trader.trades_executed}")


if __name__ == '__main__':
    main()
