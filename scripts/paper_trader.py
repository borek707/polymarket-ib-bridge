#!/usr/bin/env python3
"""
Script: paper_trader.py

Główna pętla paper trading.
Skanuje Polymarket, szuka wielorybów, symuluje zlecenia na IB.
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
from src.correlation.engine import CorrelationEngine
from src.execution.paper_trading import PaperTradingEngine, OrderSide
from src.risk.manager import RiskManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PaperTrader:
    """Główna klasa paper trading."""
    
    def __init__(
        self,
        min_whale_volume: float = 50000,  # $50k
        min_correlation_score: float = 0.7,
        check_interval: int = 30,  # 30 sekund (szybciej dla whale signals)
        max_runtime_hours: int = 24,
        min_signal_confidence: int = 7  # Min 7/10 confidence
    ):
        self.min_whale_volume = min_whale_volume
        self.min_correlation_score = min_correlation_score
        self.check_interval = check_interval
        self.max_runtime = timedelta(hours=max_runtime_hours)
        self.min_signal_confidence = min_signal_confidence
        
        self.poly_discovery = PolymarketDiscovery()
        self.whale_detector = WhaleDetector(min_volume=min_whale_volume)
        self.ib_discovery = IBContractDiscovery()
        self.correlation_engine = CorrelationEngine()
        self.paper_engine = PaperTradingEngine()
        self.risk_manager = RiskManager()
        
        self.start_time = datetime.now()
        self.signals_detected = 0
        self.trades_executed = 0
        self.high_confidence_signals = []
        
    async def run(self):
        """Główna pętla."""
        logger.info("=" * 60)
        logger.info("🚀 PAPER TRADING STARTED (Whale Following Mode)")
        logger.info(f"⏱️  Check interval: {self.check_interval}s")
        logger.info(f"🐋 Min whale volume: ${self.min_whale_volume:,.0f}")
        logger.info(f"🎯 Min correlation: {self.min_correlation_score}")
        logger.info(f"⭐ Min signal confidence: {self.min_signal_confidence}/10")
        logger.info("=" * 60)
        
        # Inicjalizacja IB (sprawdź czy działa)
        try:
            await self.ib_discovery.connect()
            ib_contracts = await self.ib_discovery.discover_all_contracts()
            logger.info(f"✅ IB connected, {len(ib_contracts)} contracts available")
            self.ib_discovery.disconnect()
        except Exception as e:
            logger.error(f"❌ IB connection failed: {e}")
            logger.info("Continuing without IB price checks (will use cached)")
            ib_contracts = []
            
        async with self.poly_discovery, self.whale_detector:
            while True:
                # Sprawdź czy nie przekroczyliśmy czasu
                if datetime.now() - self.start_time > self.max_runtime:
                    logger.info("⏰ Max runtime reached, stopping")
                    break
                    
                # Risk check
                risk = self.risk_manager.check_all()
                if not risk.can_trade:
                    logger.warning(f"🚫 Risk check failed: {risk.reason}")
                    await asyncio.sleep(self.check_interval)
                    continue
                    
                try:
                    await self._scan_for_whales_and_trade(ib_contracts)
                except Exception as e:
                    logger.error(f"❌ Error in scan loop: {e}")
                    self.risk_manager.log_error("SCAN_ERROR", str(e))
                    
                # Pokaż podsumowanie
                summary = self.paper_engine.get_portfolio_summary()
                logger.info(
                    f"📊 Session: {self.trades_executed} trades | "
                    f"PnL: ${summary['daily_realized_pnl']:.2f} | "
                    f"Signals: {self.signals_detected} | "
                    f"Open: {summary['positions_count']} positions"
                )
                
                # Czekaj do następnego skanu
                logger.info(f"💤 Sleeping {self.check_interval}s...")
                await asyncio.sleep(self.check_interval)
                
        logger.info("=" * 60)
        logger.info("🏁 PAPER TRADING FINISHED")
        logger.info(f"🐋 High-confidence signals detected: {self.signals_detected}")
        logger.info(f"📝 Trades executed: {self.trades_executed}")
        
        final_summary = self.paper_engine.get_portfolio_summary()
        logger.info(f"💰 Final PnL: ${final_summary['daily_realized_pnl']:.2f}")
        logger.info("=" * 60)
        
    async def _scan_for_whales_and_trade(self, ib_contracts: list):
        """
        Główna logika: szukaj wielorybów -> mapuj na IB -> wykonaj.
        
        Flow:
        1. Pobierz sygnały wielorybów (CLOB primary, blockchain fallback)
        2. Dla każdego sygnału wysokiego confidence:
           - Znajdź korelację z kontraktem IB
           - Sprawdź czy warto wykonać
           - Wyślij paper order na IB
        """
        logger.info("🔍 Scanning for whale signals...")
        
        # 1. Pobierz sygnały wielorybów
        signals = await self.whale_detector.get_signals(lookback_minutes=2)
        
        # Filtrowanie tylko high confidence
        high_conf_signals = [
            s for s in signals 
            if s.confidence_score >= self.min_signal_confidence
        ]
        
        if not high_conf_signals:
            logger.debug("No high-confidence whale signals found")
            return
            
        logger.info(f"🐋 Found {len(high_conf_signals)} high-confidence signals")
        
        # 2. Dla każdego sygnału
        for signal in high_conf_signals:
            await self._execute_on_signal(signal, ib_contracts)
            
    async def _execute_on_signal(self, signal, ib_contracts: list):
        """Wykonuje trade na podstawie sygnału wieloryba."""
        self.signals_detected += 1
        
        logger.info(f"🎯 Processing signal: {signal.market_question[:50]}...")
        logger.info(f"   Direction: {signal.direction.value}")
        logger.info(f"   Whale volume: ${signal.volume_usd:,.0f}")
        logger.info(f"   Price impact: {signal.price_impact:.1%}")
        logger.info(f"   Confidence: {signal.confidence_score}/10")
        
        # Pobierz market z Polymarket (dla aktualnych cen)
        market = await self.poly_discovery.get_market_by_slug(signal.market_slug)
        if not market:
            logger.warning(f"   ❌ Could not fetch market data for {signal.market_slug}")
            return
            
        # Znajdź korelację z IB
        from src.correlation.engine import MarketCorrelation
        
        corr = self.correlation_engine.correlate_single(market, ib_contracts)
        if not corr or corr.score < self.min_correlation_score:
            logger.info(f"   ⚠️  No high-confidence IB correlation (score: {corr.score if corr else 0:.2f})")
            return
            
        logger.info(f"   ✅ IB correlation found: {corr.ib_symbol} (score: {corr.score:.2f})")
        
        # Określ kierunek na IB
        if signal.direction in [WhaleDirection.BUY_YES, WhaleDirection.SELL_NO]:
            side = OrderSide.BUY
            target_price = market.yes_price
        else:
            side = OrderSide.BUY  # BUY NO (też buy, tylko inny kontrakt)
            target_price = market.no_price
            
        # Sprawdź czy cena na IB jeszcze nie dogoniła
        # W realu: pobierz aktualną cenę z IB
        # Na razie: zakładamy opóźnienie 2-5%
        estimated_ib_price = target_price * 0.97  # 3% discount (opóźnienie)
        
        logger.info(f"   📊 Poly price: ${target_price:.2f}, Est. IB price: ${estimated_ib_price:.2f}")
        
        # Risk check per trade
        if not self.risk_manager.can_open_position(estimated_ib_price * 100):  # 100 contracts
            logger.warning(f"   🚫 Risk limits prevent this trade")
            return
            
        # Wykonaj paper trade
        order = self.paper_engine.place_order(
            poly_market_slug=signal.market_slug,
            poly_question=signal.market_question,
            ib_conid=corr.ib_conid,
            ib_symbol=corr.ib_symbol,
            side=side,
            quantity=100,  # 100 contracts = $100 jeśli price ~$1
            limit_price=estimated_ib_price,
            poly_price=target_price,
            ib_bid=estimated_ib_price - 0.01,
            ib_ask=estimated_ib_price + 0.01
        )
        
        if order.status.value == "FILLED":
            self.trades_executed += 1
            logger.info(f"   ✅ Paper trade EXECUTED: {order.filled_quantity} @ ${order.filled_price:.2f}")
            logger.info(f"      Slippage: {order.slippage:.2f}% | Fee: ${order.fee_paid:.2f}")
        else:
            logger.info(f"   ❌ Paper trade {order.status.value}")
            
    # Legacy method - kept for compatibility but not used
    async def _scan_and_trade(self, ib_contracts: list):
        """Legacy method - now uses _scan_for_whales_and_trade."""
        await self._scan_for_whales_and_trade(ib_contracts)
        
    async def _evaluate_opportunity(self, corr):
        """Legacy method - not used in whale following mode."""
        pass


def main():
    parser = argparse.ArgumentParser(description='Paper Trading Bot - Whale Following Mode')
    parser.add_argument('--duration', type=int, default=24, help='Runtime in hours')
    parser.add_argument('--interval', type=int, default=30, help='Check interval in seconds (default: 30)')
    parser.add_argument('--min-volume', type=float, default=50000, help='Min whale volume')
    parser.add_argument('--min-correlation', type=float, default=0.7, help='Min correlation score')
    parser.add_argument('--min-confidence', type=int, default=7, help='Min signal confidence 1-10 (default: 7)')
    
    args = parser.parse_args()
    
    trader = PaperTrader(
        min_whale_volume=args.min_volume,
        min_correlation_score=args.min_correlation,
        check_interval=args.interval,
        max_runtime_hours=args.duration,
        min_signal_confidence=args.min_confidence
    )
    
    try:
        asyncio.run(trader.run())
    except KeyboardInterrupt:
        logger.info("\n🛑 Interrupted by user")


if __name__ == '__main__':
    main()
