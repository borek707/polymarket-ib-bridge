"""
Whale Detector - śledzenie wielorybów na Polymarket.

Architektura:
- Primary: CLOB API (REST, 5-10s delay)
- Fallback: Blockchain direct (1-2s delay, gdy CLOB nie działa)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from enum import Enum

import aiohttp

logger = logging.getLogger(__name__)


class WhaleDirection(Enum):
    BUY_YES = "buy_yes"
    BUY_NO = "buy_no"
    SELL_YES = "sell_yes"
    SELL_NO = "sell_no"


@dataclass
class WhaleSignal:
    """Sygnał wieloryba."""
    market_slug: str
    market_question: str
    direction: WhaleDirection
    volume_usd: float
    price_before: float
    price_after: float
    timestamp: datetime
    wallet_address: Optional[str] = None
    tx_hash: Optional[str] = None
    source: str = "clob"  # "clob" lub "blockchain"
    
    @property
    def price_impact(self) -> float:
        """Procentowy wpływ na cenę."""
        if self.price_before == 0:
            return 0
        return abs(self.price_after - self.price_before) / self.price_before
    
    @property
    def confidence_score(self) -> int:
        """0-10 - jak bardzo wierzymy w ten sygnał."""
        score = 0
        
        # Volume (max 4 pkt)
        if self.volume_usd >= 500000:
            score += 4
        elif self.volume_usd >= 100000:
            score += 3
        elif self.volume_usd >= 50000:
            score += 2
        elif self.volume_usd >= 10000:
            score += 1
            
        # Price impact (max 3 pkt)
        if self.price_impact >= 0.05:  # 5%
            score += 3
        elif self.price_impact >= 0.02:  # 2%
            score += 2
        elif self.price_impact >= 0.01:  # 1%
            score += 1
            
        # Freshness (max 3 pkt)
        minutes_old = (datetime.now() - self.timestamp).total_seconds() / 60
        if minutes_old <= 2:
            score += 3
        elif minutes_old <= 5:
            score += 2
        elif minutes_old <= 10:
            score += 1
            
        return min(10, score)
    
    def is_fresh(self, max_age_minutes: int = 30) -> bool:
        """Czy sygnał jest jeszcze świeży?"""
        age = datetime.now() - self.timestamp
        return age <= timedelta(minutes=max_age_minutes)


class ClobWhaleMonitor:
    """
    Primary source: Polymarket CLOB API.
    
    Docs: https://docs.polymarket.com/
    """
    
    API_URL = "https://clob.polymarket.com"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_check = datetime.min
        self.min_whale_volume = 50000  # $50k
        
    async def __aenter__(self):
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self.session = aiohttp.ClientSession(headers=headers)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def is_healthy(self) -> bool:
        """Sprawdź czy API odpowiada."""
        if not self.session:
            return False
        try:
            async with self.session.get(f"{self.API_URL}/health", timeout=5) as resp:
                return resp.status == 200
        except:
            return False
    
    async def get_large_trades(
        self,
        min_volume: float = 50000,
        lookback_minutes: int = 10
    ) -> List[WhaleSignal]:
        """
        Pobiera duże trady z CLOB API.
        
        Note: CLOB API ma endpoint /trades ale może wymagać API key
        dla historycznych danych. Darmowy tier daje ~5min delay.
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        signals = []
        
        try:
            # Endpoint dla ostatnich trade'ów
            # W realnym API to może być /trades, /activity, lub /orders/filled
            url = f"{self.API_URL}/trades"
            params = {
                "min_size": min_volume,
                "since": (datetime.utcnow() - timedelta(minutes=lookback_minutes)).isoformat()
            }
            
            async with self.session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    logger.warning(f"CLOB API returned {resp.status}")
                    return []
                    
                data = await resp.json()
                
                for trade in data.get("trades", []):
                    signal = self._parse_trade(trade)
                    if signal and signal.volume_usd >= min_volume:
                        signals.append(signal)
                        
            logger.info(f"CLOB: Found {len(signals)} whale signals")
            self.last_check = datetime.now()
            
        except Exception as e:
            logger.error(f"CLOB API error: {e}")
            
        return signals
    
    def _parse_trade(self, data: dict) -> Optional[WhaleSignal]:
        """Parsuje trade z CLOB na WhaleSignal."""
        try:
            # Mapowanie pól zależy od dokładnej struktury CLOB API
            # To jest przykład - trzeba zweryfikować z docs
            size = float(data.get("size", 0))
            price = float(data.get("price", 0))
            
            # CLOB zwraca size w shares, konwertuj na USD
            volume_usd = size * price
            
            side = data.get("side", "").lower()
            outcome = data.get("outcome", "").lower()
            
            if side == "buy" and outcome == "yes":
                direction = WhaleDirection.BUY_YES
            elif side == "buy" and outcome == "no":
                direction = WhaleDirection.BUY_NO
            elif side == "sell" and outcome == "yes":
                direction = WhaleDirection.SELL_YES
            else:
                direction = WhaleDirection.SELL_NO
                
            return WhaleSignal(
                market_slug=data.get("market_slug", ""),
                market_question=data.get("market_question", ""),
                direction=direction,
                volume_usd=volume_usd,
                price_before=price,  # CLOB może nie dawać price_before
                price_after=price,
                timestamp=datetime.fromisoformat(data.get("timestamp", "").replace('Z', '+00:00')),
                wallet_address=data.get("trader_address"),
                source="clob"
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse CLOB trade: {e}")
            return None


class PublicAPIWhaleMonitor:
    """
    Fallback: Public Polymarket Gamma API (no API key needed).
    
    Uses volume spikes and recent trades to infer whale activity.
    Less precise than CLOB but works without authentication.
    """
    
    API_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.previous_volumes: Dict[str, float] = {}  # market_slug -> volume_24h
        self.price_history: Dict[str, List[tuple]] = {}  # market_slug -> [(timestamp, price), ...]
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def is_healthy(self) -> bool:
        """Sprawdź czy API odpowiada."""
        if not self.session:
            return False
        try:
            async with self.session.get(f"{self.API_URL}/markets", params={"limit": 1}, timeout=5) as resp:
                return resp.status == 200
        except:
            return False
    
    async def get_large_trades(
        self,
        min_volume: float = 50000,
        lookback_minutes: int = 10
    ) -> List[WhaleSignal]:
        """
        Pobiera aktywne markety i szuka anomalii (volume spikes, price jumps).
        
        Strategia:
        1. Pobierz wszystkie aktywne markety
        2. Porównaj volume 24h z poprzednim checkiem
        3. Szukaj dużych zmian w krótkim czasie (price impact)
        4. Wygeneruj sygnały dla marketów z anomaliami
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        signals = []
        
        try:
            # Pobierz aktywne markety
            url = f"{self.API_URL}/markets"
            params = {
                "active": "true",
                "closed": "false",
                "archived": "false",
                "limit": 100,
                "sort": "volume",
                "order": "desc"
            }
            
            async with self.session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    logger.warning(f"Public API returned {resp.status}")
                    return []
                    
                data = await resp.json()
                
                for market_data in data:
                    signal = self._analyze_market(market_data, min_volume)
                    if signal:
                        signals.append(signal)
                        
            logger.info(f"Public API: Found {len(signals)} whale signals from volume analysis")
            
        except Exception as e:
            logger.error(f"Public API error: {e}")
            
        return signals
    
    def _analyze_market(self, data: dict, min_volume: float) -> Optional[WhaleSignal]:
        """Analizuje pojedynczy market pod kątem whale activity."""
        try:
            slug = data.get("slug", "")
            question = data.get("question", "")
            current_volume = float(data.get("volume24hr", 0) or 0)
            
            # Sprawdź czy to binary market (YES/NO)
            outcomes = data.get("outcomes", [])
            if len(outcomes) != 2:
                return None
                
            # Pobierz ceny
            yes_price = 0.0
            no_price = 0.0
            for outcome in outcomes:
                name = outcome.get("name", "").lower()
                price = float(outcome.get("price", 0))
                if name == "yes":
                    yes_price = price
                elif name == "no":
                    no_price = price
                    
            # Oblicz volume spike
            previous_volume = self.previous_volumes.get(slug, current_volume)
            volume_delta = current_volume - previous_volume
            
            # Zapisz aktualny volume
            self.previous_volumes[slug] = current_volume
            
            # Jeśli nie mamy historii, nie możemy wykryć spike
            if slug not in self.previous_volumes:
                return None
                
            # Szukaj volume spike > min_volume w krótkim czasie
            if volume_delta < min_volume:
                return None
                
            # Sprawdź price impact (jeśli mamy historię)
            price_before = yes_price
            price_after = yes_price
            
            if slug in self.price_history and len(self.price_history[slug]) > 0:
                price_before = self.price_history[slug][-1][1]
                price_after = yes_price
                
            # Aktualizuj historię cen
            if slug not in self.price_history:
                self.price_history[slug] = []
            self.price_history[slug].append((datetime.now(), yes_price))
            # Keep only last 20 entries
            self.price_history[slug] = self.price_history[slug][-20:]
            
            # Wywnioskuj kierunek na podstawie zmiany ceny
            if price_after > price_before * 1.01:  # Price went up > 1%
                direction = WhaleDirection.BUY_YES
            elif price_after < price_before * 0.99:  # Price went down > 1%
                direction = WhaleDirection.BUY_NO
            else:
                direction = WhaleDirection.BUY_YES  # Default assumption
                
            timestamp_str = data.get("updatedAt") or data.get("createdAt")
            timestamp = datetime.now()
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except:
                    pass
                    
            return WhaleSignal(
                market_slug=slug,
                market_question=question,
                direction=direction,
                volume_usd=volume_delta,  # Tylko delta (nowy volume)
                price_before=price_before,
                price_after=price_after,
                timestamp=timestamp,
                wallet_address=None,  # Public API nie daje tego
                source="public_api"
            )
            
        except Exception as e:
            logger.debug(f"Failed to analyze market: {e}")
            return None


class BlockchainWhaleMonitor:
    """
    Fallback source: Blockchain direct (Polygon).
    
    Używane gdy CLOB API nie działa lub dla dodatkowej walidacji.
    """
    
    def __init__(self, rpc_url: Optional[str] = None):
        self.rpc_url = rpc_url or "https://polygon-rpc.com"
        self.session: Optional[aiohttp.ClientSession] = None
        self.polymarket_contracts = [
            # Główne kontrakty Polymarket na Polygon
            "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",  # Exchange
        ]
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def is_healthy(self) -> bool:
        """Sprawdź czy RPC odpowiada."""
        if not self.session:
            return False
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_blockNumber",
                "params": [],
                "id": 1
            }
            async with self.session.post(self.rpc_url, json=payload, timeout=5) as resp:
                return resp.status == 200
        except:
            return False
    
    async def get_large_trades(
        self,
        min_volume: float = 50000,
        lookback_blocks: int = 100
    ) -> List[WhaleSignal]:
        """
        Pobiera duże trady bezpośrednio z blockchain.
        
        Note: To wymaga indeksowania eventów lub użycia
        subgraph API. Stub implementation.
        """
        logger.info("Blockchain fallback: scanning for whale trades...")
        
        # W pełnej implementacji:
        # 1. Pobierz aktualny block number
        # 2. Iteruj przez ostatnie N bloków
        # 3. Parsuj eventy OrderFilled/Matched z kontraktów Polymarket
        # 4. Filtruj po wartości > min_volume
        
        # Stub - zwróć pustą listę
        return []


class WhaleDetector:
    """
    Główna klasa do wykrywania wielorybów.
    
    Priority:
    1. CLOB API (jeśli masz klucz) - najlepsze dane
    2. Public API (fallback bez klucza) - volume spike detection
    3. Blockchain direct (opcjonalnie) - najszybsze
    """
    
    def __init__(
        self,
        clob_api_key: Optional[str] = None,
        blockchain_rpc: Optional[str] = None,
        min_volume: float = 50000
    ):
        self.clob_api_key = clob_api_key
        self.clob = ClobWhaleMonitor(api_key=clob_api_key)
        self.public_api = PublicAPIWhaleMonitor()
        self.blockchain = BlockchainWhaleMonitor(rpc_url=blockchain_rpc)
        self.min_volume = min_volume
        self.signals_history: List[WhaleSignal] = []
        self._dedup_window = timedelta(minutes=5)
        
    async def __aenter__(self):
        await self.clob.__aenter__()
        await self.public_api.__aenter__()
        await self.blockchain.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.clob.__aexit__(exc_type, exc_val, exc_tb)
        await self.public_api.__aexit__(exc_type, exc_val, exc_tb)
        await self.blockchain.__aexit__(exc_type, exc_val, exc_tb)
    
    async def get_signals(self, lookback_minutes: int = 10) -> List[WhaleSignal]:
        """
        Pobiera sygnały wielorybów.
        
        Priority:
        1. CLOB API (jeśli dostępne i zdrowe)
        2. Public API (fallback)
        3. Blockchain (opcjonalny fallback)
        
        Returns:
            Lista unikalnych sygnałów posortowana po confidence (malejąco)
        """
        signals = []
        source = "none"
        
        # Priority 1: CLOB API (tylko jeśli mamy klucz)
        if self.clob_api_key and await self.clob.is_healthy():
            signals = await self.clob.get_large_trades(
                min_volume=self.min_volume,
                lookback_minutes=lookback_minutes
            )
            source = "clob"
            logger.info(f"Got {len(signals)} signals from CLOB API")
            
        # Priority 2: Public API (fallback bez klucza)
        if not signals and await self.public_api.is_healthy():
            logger.info("CLOB unavailable, using Public API fallback...")
            signals = await self.public_api.get_large_trades(
                min_volume=self.min_volume,
                lookback_minutes=lookback_minutes
            )
            source = "public_api"
            logger.info(f"Got {len(signals)} signals from Public API")
            
        # Priority 3: Blockchain (opcjonalnie)
        if not signals and await self.blockchain.is_healthy():
            logger.info("Trying blockchain fallback...")
            signals = await self.blockchain.get_large_trades(
                min_volume=self.min_volume,
                lookback_blocks=100
            )
            source = "blockchain"
            logger.info(f"Got {len(signals)} signals from blockchain")
            
        if not signals:
            logger.warning("All whale detection sources unavailable")
            
        # Dedup i filtruj
        new_signals = self._deduplicate(signals)
        
        # Dodaj do historii
        self.signals_history.extend(new_signals)
        
        # Sortuj po confidence
        new_signals.sort(key=lambda s: s.confidence_score, reverse=True)
        
        return new_signals
    
    def _deduplicate(self, signals: List[WhaleSignal]) -> List[WhaleSignal]:
        """Usuwa duplikaty (ten sam market + kierunek w krótkim czasie)."""
        unique = []
        
        for signal in signals:
            is_dup = False
            for hist in self.signals_history:
                if (
                    hist.market_slug == signal.market_slug
                    and hist.direction == signal.direction
                    and abs((hist.timestamp - signal.timestamp).total_seconds()) < self._dedup_window.total_seconds()
                ):
                    is_dup = True
                    break
                    
            if not is_dup:
                unique.append(signal)
                
        return unique
    
    def get_high_confidence_signals(self, min_score: int = 7) -> List[WhaleSignal]:
        """Zwraca tylko sygnały z wysokim confidence."""
        fresh = [s for s in self.signals_history if s.is_fresh()]
        return [s for s in fresh if s.confidence_score >= min_score]
    
    async def watch_continuous(
        self,
        callback,
        interval_seconds: int = 30
    ):
        """
        Continuous monitoring - wywołuje callback na każdy nowy sygnał.
        
        Args:
            callback: Funkcja przyjmująca WhaleSignal
            interval_seconds: Jak często sprawdzać API
        """
        logger.info(f"Starting continuous whale watch (interval: {interval_seconds}s)")
        
        while True:
            try:
                signals = await self.get_signals(lookback_minutes=2)
                
                for signal in signals:
                    if signal.confidence_score >= 7:
                        logger.info(
                            f"🐋 HIGH CONFIDENCE SIGNAL: {signal.market_slug} "
                            f"(score: {signal.confidence_score}, vol: ${signal.volume_usd:,.0f})"
                        )
                        await callback(signal)
                    else:
                        logger.debug(
                            f"Low confidence signal ignored: {signal.market_slug} "
                            f"(score: {signal.confidence_score})"
                        )
                        
            except Exception as e:
                logger.error(f"Error in watch loop: {e}")
                
            await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    async def test():
        print("🔍 Testing whale detection (no API key needed)...\n")
        
        # Test bez klucza - użyje Public API
        async with WhaleDetector() as detector:
            print("Sources status:")
            
            # Test CLOB (będzie unhealthy bez klucza)
            clob_ok = await detector.clob.is_healthy()
            print(f"  CLOB API: {'✅ Healthy' if clob_ok else '❌ Unhealthy (no key)'}")
            
            # Test Public API
            public_ok = await detector.public_api.is_healthy()
            print(f"  Public API: {'✅ Healthy' if public_ok else '❌ Unhealthy'}")
            
            # Test blockchain
            chain_ok = await detector.blockchain.is_healthy()
            print(f"  Blockchain: {'✅ Healthy' if chain_ok else '❌ Unhealthy'}")
            
            if not clob_ok and not public_ok and not chain_ok:
                print("\n❌ No data sources available!")
                return
            
            # Get signals
            print("\n📡 Fetching signals (using best available source)...")
            signals = await detector.get_signals(lookback_minutes=30)
            
            print(f"\n🎯 Found {len(signals)} whale signals:\n")
            for s in signals[:5]:
                print(f"  Market: {s.market_question[:50]}...")
                print(f"  Direction: {s.direction.value}")
                print(f"  Volume: ${s.volume_usd:,.0f}")
                print(f"  Impact: {s.price_impact:.1%}")
                print(f"  Confidence: {s.confidence_score}/10")
                print(f"  Source: {s.source}")
                print()
                
    asyncio.run(test())
