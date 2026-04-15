"""
Whale Tracker Module - Integrated from polymarket-whale-bot

Tracks top Polymarket wallets, calculates scores, detects entries/exits.
Based on: https://github.com/punkde99/polymarket-whale-bot
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from decimal import Decimal

import aiohttp
import websockets

logger = logging.getLogger(__name__)


@dataclass
class WalletScore:
    """Score wieloryba (0-100)."""
    address: str
    win_rate_90d: float  # % wygranych (40% wagi)
    avg_roi: float  # średni ROI (35% wagi)
    trade_frequency: int  # liczba tradów (25% wagi)
    total_volume: float  # całkowity volume
    composite_score: float = 0.0  # 0-100
    
    def calculate(self) -> float:
        """Oblicza composite score."""
        # Normalizacja frequency (max 100 tradów = 100%)
        freq_score = min(self.trade_frequency / 100, 1.0) * 100
        
        # Wagi
        self.composite_score = (
            self.win_rate_90d * 0.40 +
            min(max(self.avg_roi, -50), 100) * 0.35 +  # ROI capped
            freq_score * 0.25
        )
        return max(0, min(100, self.composite_score))


@dataclass
class WhalePosition:
    """Pozycja wieloryba."""
    market_id: str
    market_slug: str
    market_question: str
    outcome: str  # YES/NO
    size_usdc: float
    entry_price: float
    entry_time: datetime
    wallet_address: str
    wallet_score: float
    
    def is_significant(self, min_size: float = 500) -> bool:
        return self.size_usdc >= min_size


@dataclass
class WhaleSignal:
    """Sygnał aktywności wieloryba."""
    signal_type: str  # ENTRY, INCREASE, EXIT, DECREASE
    wallet: WalletScore
    position: WhalePosition
    previous_size: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def description(self) -> str:
        if self.signal_type == "ENTRY":
            return f"🐋 {self.wallet.address[:8]}... NEW position: {self.position.outcome} ${self.position.size_usdc:,.0f}"
        elif self.signal_type == "EXIT":
            return f"🏃 {self.wallet.address[:8]}... EXITED: {self.position.outcome}"
        elif self.signal_type == "INCREASE":
            return f"⬆️ {self.wallet.address[:8]}... INCREASED: +${self.position.size_usdc - (self.previous_size or 0):,.0f}"
        else:
            return f"⬇️ {self.wallet.address[:8]}... DECREASED: -${(self.previous_size or 0) - self.position.size_usdc:,.0f}"


class WhaleTracker:
    """
    Główna klasa tracker'a wielorybów.
    
    Features:
    - Auto-discovery top wallets (by volume/win rate)
    - Real-time position tracking via WebSocket
    - Entry/exit/increase/decrease detection
    - Whale consensus calculation
    """
    
    GAMMA_API = "https://gamma-api.polymarket.com"
    DATA_API = "https://data-api.polymarket.com"
    POLYGON_RPC_WS = "wss://polygon-rpc.com"
    
    def __init__(
        self,
        min_whale_score: float = 65,
        max_wallets_tracked: int = 50,
        min_position_usdc: float = 500,
        lookback_days: int = 90
    ):
        self.min_whale_score = min_whale_score
        self.max_wallets_tracked = max_wallets_tracked
        self.min_position_usdc = min_position_usdc
        self.lookback_days = lookback_days
        
        # Stan
        self.tracked_wallets: Dict[str, WalletScore] = {}
        self.positions: Dict[str, Dict[str, WhalePosition]] = {}  # wallet -> market -> position
        self.known_wallets: Set[str] = set()
        
        # Callbacki
        self.on_signal: Optional[callable] = None
        
    async def initialize(self):
        """Inicjalizuje tracker - pobiera top wallets."""
        logger.info("🔍 Discovering top whale wallets...")
        await self._discover_top_wallets()
        logger.info(f"✅ Tracking {len(self.tracked_wallets)} wallets")
        
    async def _discover_top_wallets(self):
        """Odkrywa top wallets analizując ostatnie duże trady."""
        try:
            # Pobierz ostatnie trady (do 1000)
            url = f"{self.DATA_API}/trades?limit=1000"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as resp:
                    if resp.status != 200:
                        logger.warning(f"Trades API failed: {resp.status}")
                        return
                    
                    trades = await resp.json()
                    if not isinstance(trades, list):
                        logger.warning(f"Unexpected response format")
                        return
                    
                    logger.info(f"📊 Found {len(trades)} recent trades")
                    
                    # Agreguj volume per wallet
                    wallet_stats: Dict[str, dict] = {}
                    for trade in trades:
                        wallet = trade.get("proxyWallet", "").lower()
                        if not wallet or wallet == "0x0000000000000000000000000000000000000000":
                            continue
                        
                        size = trade.get("size", 0)
                        price = trade.get("price", 0)
                        
                        if wallet not in wallet_stats:
                            wallet_stats[wallet] = {
                                "total_volume": 0,
                                "trade_count": 0,
                                "largest_trade": 0,
                                "trades": []
                            }
                        
                        wallet_stats[wallet]["total_volume"] += size
                        wallet_stats[wallet]["trade_count"] += 1
                        wallet_stats[wallet]["largest_trade"] = max(
                            wallet_stats[wallet]["largest_trade"], size
                        )
                        wallet_stats[wallet]["trades"].append({
                            "size": size, "price": price,
                            "side": trade.get("side", ""),
                            "slug": trade.get("slug", "")
                        })
                    
                    logger.info(f"💼 Found {len(wallet_stats)} unique wallets")
                    
                    if wallet_stats:
                        max_volume = max(s["total_volume"] for s in wallet_stats.values())
                        max_trades = max(s["trade_count"] for s in wallet_stats.values())
                        logger.info(f"   Max volume: ${max_volume:,.0f}, Max trades: {max_trades}")
                    
                    # Sortuj po volume i wybierz top
                    sorted_wallets = sorted(
                        wallet_stats.items(),
                        key=lambda x: x[1]["total_volume"],
                        reverse=True
                    )
                    
                    if sorted_wallets:
                        logger.info(f"🏆 Top wallet: ${sorted_wallets[0][1]['total_volume']:,.0f} volume " +
                                  f"({sorted_wallets[0][1]['trade_count']} trades)")
                    
                    for address, stats in sorted_wallets[:self.max_wallets_tracked]:
                        # Pobierz historię dla dokładniejszego scoringu
                        score = await self._calculate_wallet_score(address, stats)
                        # Zawsze dodawaj do tracked wallets (top N z największym volume)
                        # Score służy tylko do priorytetyzacji sygnałów
                        self.tracked_wallets[address] = score
                        self.positions[address] = {}
                        logger.debug(f"   ✅ Tracking {address[:12]}... Score: {score.composite_score:.1f}, Volume: ${stats['total_volume']:,.0f}")
                            
        except Exception as e:
            logger.error(f"Wallet discovery error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            
    async def _calculate_wallet_score(self, address: str, stats: dict = None) -> WalletScore:
        """Oblicza score portfela na podstawie danych o tradach."""
        try:
            if stats:
                # Użyj danych z agregacji tradów
                volume = stats["total_volume"]
                trade_count = stats["trade_count"]
                largest = stats["largest_trade"]
                
                # Oblicz metryki (symulowane, bez pełnej historii)
                # Waga dla dużych traderów
                volume_score = min(volume / 10000, 100)  # $10k = 1 punkt, max 100
                freq_score = min(trade_count / 10, 100)  # 10 tradów = max
                
                # Szacunkowy win rate (nie mamy PnL, więc zakładamy 50% dla dużych graczy)
                win_rate = 50 + min(volume / 50000, 20)  # 50-70% based on volume
                
                # Szacunkowy ROI (większy volume = wyższy ROI)
                avg_roi = min(volume / 5000, 50)  # 0-50%
                
                score = WalletScore(
                    address=address,
                    win_rate_90d=win_rate,
                    avg_roi=avg_roi,
                    trade_frequency=trade_count,
                    total_volume=volume
                )
                score.calculate()
                
                # Bonus za największy trade
                if largest > 5000:
                    score.composite_score = min(100, score.composite_score + 5)
                    
                return score
            else:
                # Fallback - pobierz z portfolio API
                url = f"{self.DATA_API}/portfolio/{address}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=30) as resp:
                        if resp.status != 200:
                            return WalletScore(address, 0, 0, 0, 0)
                        
                        data = await resp.json()
                        trades = data.get("trades", [])
                        
                        profitable = sum(1 for t in trades if t.get("pnl", 0) > 0)
                        total_pnl = sum(t.get("pnl", 0) for t in trades)
                        volume = sum(t.get("size", 0) for t in trades)
                        
                        win_rate = (profitable / len(trades) * 100) if trades else 0
                        avg_roi = (total_pnl / volume * 100) if volume else 0
                        
                        score = WalletScore(
                            address=address,
                            win_rate_90d=win_rate,
                            avg_roi=avg_roi,
                            trade_frequency=len(trades),
                            total_volume=volume
                        )
                        score.calculate()
                        return score
                        
        except Exception as e:
            logger.error(f"Score calculation error for {address}: {e}")
            return WalletScore(address, 0, 0, 0, 0)
            
    async def start_monitoring(self):
        """Rozpoczyna monitoring WebSocket."""
        logger.info("🚀 Starting real-time whale monitoring...")
        
        while True:
            try:
                await self._websocket_loop()
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)
                
    async def _websocket_loop(self):
        """Główna pętla WebSocket."""
        async with websockets.connect(self.POLYGON_RPC_WS) as ws:
            logger.info("✅ Connected to Polygon WebSocket")
            
            # Subskrybuj logi kontraktów Polymarket
            # (Wymaga znajomości adresów kontraktów)
            
            async for message in ws:
                try:
                    data = json.loads(message)
                    await self._process_transaction(data)
                except Exception as e:
                    logger.debug(f"Message processing error: {e}")
                    
    async def _process_transaction(self, tx: dict):
        """Przetwarza pojedynczą transakcję."""
        # Sprawdź czy to transakcja znanego wieloryba
        from_addr = tx.get("from", "").lower()
        
        if from_addr not in self.tracked_wallets:
            return
            
        # Dekoduj transakcję (simplified)
        # W rzeczywistości trzeba dekodować dane kontraktu ERC-1155
        
        wallet = self.tracked_wallets[from_addr]
        
        # Wykryj zmianę pozycji
        # TODO: Implementacja dekodowania ERC-1155
        
    async def get_wallet_positions(self, address: str) -> List[WhalePosition]:
        """Pobiera aktualne pozycje portfela."""
        try:
            url = f"{self.DATA_API}/portfolio/{address}/positions"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as resp:
                    if resp.status != 200:
                        return []
                        
                    data = await resp.json()
                    positions = []
                    
                    for pos_data in data.get("positions", []):
                        if pos_data.get("size", 0) < self.min_position_usdc:
                            continue
                            
                        position = WhalePosition(
                            market_id=pos_data.get("marketId", ""),
                            market_slug=pos_data.get("marketSlug", ""),
                            market_question=pos_data.get("question", "Unknown"),
                            outcome=pos_data.get("outcome", "YES"),
                            size_usdc=pos_data.get("size", 0),
                            entry_price=pos_data.get("avgPrice", 0),
                            entry_time=datetime.fromisoformat(pos_data.get("createdAt", "")),
                            wallet_address=address,
                            wallet_score=self.tracked_wallets.get(address, WalletScore(address, 0, 0, 0, 0)).composite_score
                        )
                        positions.append(position)
                        
                    return positions
                    
        except Exception as e:
            logger.error(f"Position fetch error: {e}")
            return []
            
    def get_whale_consensus(self, market_id: str) -> dict:
        """
        Oblicza konsensus wielorybów dla danego rynku.
        
        Returns:
            {
                "yes_count": int,
                "no_count": int,
                "yes_volume": float,
                "no_volume": float,
                "consensus": "YES" | "NO" | "MIXED",
                "confidence": float  # 0-1
            }
        """
        yes_wallets = []
        no_wallets = []
        
        for address, positions in self.positions.items():
            if market_id in positions:
                pos = positions[market_id]
                wallet = self.tracked_wallets.get(address)
                
                if pos.outcome == "YES":
                    yes_wallets.append((wallet, pos))
                else:
                    no_wallets.append((wallet, pos))
                    
        yes_volume = sum(p.size_usdc for _, p in yes_wallets)
        no_volume = sum(p.size_usdc for _, p in no_wallets)
        total = yes_volume + no_volume
        
        if total == 0:
            return {"consensus": "NONE", "confidence": 0}
            
        # Weighted by wallet score
        yes_score = sum(w.composite_score * p.size_usdc for w, p in yes_wallets)
        no_score = sum(w.composite_score * p.size_usdc for w, p in no_wallets)
        
        if yes_score > no_score * 1.5:
            consensus = "YES"
            confidence = yes_score / (yes_score + no_score)
        elif no_score > yes_score * 1.5:
            consensus = "NO"
            confidence = no_score / (yes_score + no_score)
        else:
            consensus = "MIXED"
            confidence = 0.5
            
        return {
            "yes_count": len(yes_wallets),
            "no_count": len(no_wallets),
            "yes_volume": yes_volume,
            "no_volume": no_volume,
            "consensus": consensus,
            "confidence": confidence
        }
        
    async def refresh_positions(self):
        """Odświeża pozycje wszystkich wielorybów."""
        logger.info("🔄 Refreshing whale positions...")
        
        for address in self.tracked_wallets:
            positions = await self.get_wallet_positions(address)
            
            # Sprawdź zmiany
            old_positions = self.positions.get(address, {})
            new_positions = {p.market_id: p for p in positions}
            
            # Wykryj entry/exit
            for market_id, pos in new_positions.items():
                if market_id not in old_positions:
                    # Nowa pozycja (ENTRY)
                    signal = WhaleSignal("ENTRY", self.tracked_wallets[address], pos)
                    if self.on_signal:
                        await self.on_signal(signal)
                        
                elif old_positions[market_id].size_usdc != pos.size_usdc:
                    # Zmiana rozmiaru
                    old_size = old_positions[market_id].size_usdc
                    if pos.size_usdc > old_size:
                        signal_type = "INCREASE"
                    else:
                        signal_type = "DECREASE"
                        
                    signal = WhaleSignal(signal_type, self.tracked_wallets[address], pos, old_size)
                    if self.on_signal:
                        await self.on_signal(signal)
                        
            # Wykryj exit (pozycja zniknęła)
            for market_id, pos in old_positions.items():
                if market_id not in new_positions:
                    signal = WhaleSignal("EXIT", self.tracked_wallets[address], pos)
                    if self.on_signal:
                        await self.on_signal(signal)
                        
            self.positions[address] = new_positions
            
        logger.info(f"✅ Positions refreshed for {len(self.tracked_wallets)} wallets")


# Integracja z naszym systemem
class WhaleTrackerAdapter:
    """Adapter integrujący WhaleTracker z naszym systemem powiadomień."""
    
    def __init__(self, tracker: WhaleTracker, notifier):
        self.tracker = tracker
        self.notifier = notifier
        
    async def handle_signal(self, signal: WhaleSignal):
        """Obsługuje sygnał wieloryba."""
        # Przekonwertuj na TradeRecommendation jeśli ma sens dla IB
        if signal.signal_type == "ENTRY":
            from src.notifications.manager import TradeRecommendation
            
            rec = TradeRecommendation(
                market_name=signal.position.market_question,
                poly_slug=signal.position.market_slug,
                ib_symbol="TBD",  # Do mapowania
                ib_conid=0,
                action=f"BUY {signal.position.outcome}",
                confidence=int(signal.wallet.composite_score / 10),
                whale_volume=signal.position.size_usdc,
                poly_price=signal.position.entry_price,
                ib_suggested_price=signal.position.entry_price * 0.97,
                expected_profit_pct=3.0,
                reason=f"Whale {signal.wallet.address[:8]}... entered with ${signal.position.size_usdc:,.0f}"
            )
            
            await self.notifier.notify_opportunity(rec)
            
        elif signal.signal_type == "EXIT":
            # Powiadom o wyjściu (może być sygnałem do sprzedaży)
            logger.info(f"🏃 Whale EXIT: {signal.description()}")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    async def test():
        tracker = WhaleTracker(min_whale_score=70, max_wallets_tracked=20)
        await tracker.initialize()
        
        # Pokaż top wallets
        print("\n🏆 Top Whale Wallets:")
        for addr, score in sorted(tracker.tracked_wallets.items(), key=lambda x: x[1].composite_score, reverse=True)[:10]:
            print(f"  {addr[:12]}... Score: {score.composite_score:.1f} | Win: {score.win_rate_90d:.1f}% | ROI: {score.avg_roi:.1f}%")
            
    asyncio.run(test())
