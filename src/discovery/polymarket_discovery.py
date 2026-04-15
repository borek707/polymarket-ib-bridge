"""
Polymarket Discovery - pobieranie danych z Polymarket API.

Nie wymaga VPN (API jest publiczne), ale z VPN mamy lepszy dostęp.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class PolymarketMarket:
    """Market z Polymarket."""
    slug: str
    question: str
    description: str
    category: str
    volume_total: float
    volume_24h: float
    liquidity: float
    yes_price: float
    no_price: float
    end_date: datetime
    resolution_date: Optional[datetime]
    
    @property
    def implied_probability(self) -> float:
        return self.yes_price
    
    @property
    def spread(self) -> float:
        """Spread między YES a NO (powinien być ~1.0)."""
        return self.yes_price + self.no_price


class PolymarketDiscovery:
    """
    Pobiera dane o marketach z Polymarket.
    
    API Endpoint: https://gamma-api.polymarket.com
    """
    
    API_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def get_active_markets(
        self,
        min_volume: float = 50000,  # Min $50k volume
        category: Optional[str] = None
    ) -> List[PolymarketMarket]:
        """
        Pobiera aktywne markety z Polymarket.
        
        Args:
            min_volume: Minimalny volume 24h (USD)
            category: Filtrowanie po kategorii (opcjonalnie)
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        markets = []
        offset = 0
        limit = 100
        
        while True:
            try:
                # Endpoint dla marketów
                url = f"{self.API_URL}/markets"
                params = {
                    'active': 'true',
                    'closed': 'false',
                    'archived': 'false',
                    'limit': limit,
                    'offset': offset,
                    'sort': 'volume',  # Sortuj po volume (największe pierwsze)
                    'order': 'desc'
                }
                
                async with self.session.get(url, params=params, timeout=10) as resp:
                    if resp.status != 200:
                        logger.warning(f"API returned {resp.status}")
                        break
                        
                    data = await resp.json()
                    
                    if not data or len(data) == 0:
                        break
                        
                    for item in data:
                        market = self._parse_market(item)
                        
                        if market and market.volume_24h >= min_volume:
                            # Filtrowanie po kategorii
                            if category and market.category.lower() != category.lower():
                                continue
                            markets.append(market)
                            
                    logger.info(f"Fetched {len(data)} markets (offset: {offset})")
                    
                    if len(data) < limit:
                        break
                        
                    offset += limit
                    await asyncio.sleep(0.5)  # Rate limiting
                    
            except Exception as e:
                logger.error(f"Error fetching markets: {e}")
                break
                
        logger.info(f"Total active markets: {len(markets)}")
        return markets
        
    def _parse_market(self, data: dict) -> Optional[PolymarketMarket]:
        """Parsuje JSON z API na obiekt PolymarketMarket."""
        try:
            # Sprawdź czy to binary market (YES/NO)
            outcomes = data.get('outcomes', [])
            if len(outcomes) != 2:
                return None  # Skip non-binary markets
                
            # Znajdź ceny YES i NO
            yes_price = 0.0
            no_price = 0.0
            
            for outcome in outcomes:
                name = outcome.get('name', '').lower()
                price = outcome.get('price', 0)
                if name == 'yes':
                    yes_price = float(price)
                elif name == 'no':
                    no_price = float(price)
                    
            if yes_price == 0 and no_price == 0:
                return None
                
            # Parsuj daty
            end_date_str = data.get('endDate') or data.get('resolutionDate')
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00')) if end_date_str else datetime.now()
            
            resolution_date = None
            if data.get('resolutionDate'):
                resolution_date = datetime.fromisoformat(data['resolutionDate'].replace('Z', '+00:00'))
                
            return PolymarketMarket(
                slug=data.get('slug', ''),
                question=data.get('question', ''),
                description=data.get('description', ''),
                category=data.get('category', 'Unknown'),
                volume_total=float(data.get('volume', 0) or 0),
                volume_24h=float(data.get('volume24hr', 0) or 0),
                liquidity=float(data.get('liquidity', 0) or 0),
                yes_price=yes_price,
                no_price=no_price,
                end_date=end_date,
                resolution_date=resolution_date
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse market: {e}")
            return None
            
    async def get_market_by_slug(self, slug: str) -> Optional[PolymarketMarket]:
        """Pobiera konkretny market po slug."""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        try:
            url = f"{self.API_URL}/markets/{slug}"
            async with self.session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return self._parse_market(data)
                else:
                    logger.warning(f"Market {slug} not found: {resp.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching market {slug}: {e}")
            return None
            
    async def get_whale_activity(
        self,
        min_trade_size: float = 10000,  # Min $10k
        hours_back: int = 1
    ) -> List[dict]:
        """
        Pobiera aktywność wielorybów (duże trady).
        
        Note: To wymaga dostępu do blockchain (Polygon) lub paid API.
        Tutaj stub - w realu trzeba by użyć CLOB API lub indexer.
        """
        # Stub - w realu to parsowałoby blockchain events
        logger.info("Whale activity tracking requires blockchain access or paid API")
        return []


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    async def test():
        async with PolymarketDiscovery() as discovery:
            print("🔍 Fetching active markets from Polymarket...\n")
            
            markets = await discovery.get_active_markets(min_volume=100000)
            
            print(f"\n📊 Found {len(markets)} markets with volume >$100k:\n")
            
            # Grupuj po kategorii
            by_category = {}
            for m in markets:
                by_category.setdefault(m.category, []).append(m)
                
            for cat, cat_markets in sorted(by_category.items(), key=lambda x: -len(x[1])):
                print(f"\n{cat} ({len(cat_markets)} markets):")
                for m in cat_markets[:3]:  # Top 3 per category
                    print(f"  - {m.question[:60]}...")
                    print(f"    Volume 24h: ${m.volume_24h:,.0f} | YES: ${m.yes_price:.2f} | NO: ${m.no_price:.2f}")
                    
            # Test pojedynczego marketu
            if markets:
                test_slug = markets[0].slug
                print(f"\n📋 Fetching single market: {test_slug}")
                single = await discovery.get_market_by_slug(test_slug)
                if single:
                    print(f"   Question: {single.question}")
                    print(f"   End date: {single.end_date}")
                    
    asyncio.run(test())
