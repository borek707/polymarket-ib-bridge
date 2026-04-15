"""
Discovery Layer - pobieranie faktycznych kontraktów z IB.

NIE używa hardcoded symboli - wszystko dynamicznie z TWS API.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from ib_insync import IB, Contract, ContractDetails

logger = logging.getLogger(__name__)


@dataclass
class IBContract:
    """Represents an IB Event Contract."""
    conid: int
    symbol: str
    name: str
    exchange: str  # FORECASTX or CME
    category: str  # ECONOMIC, CRYPTO, CLIMATE, etc.
    expiry: datetime
    strike: Optional[float]  # Próg (np. 4.875 dla Fed)
    right: str  # 'C' (YES) lub 'P' (NO)
    bid: Optional[float] = None
    ask: Optional[float] = None
    last_price: Optional[float] = None
    
    @property
    def mid_price(self) -> Optional[float]:
        if self.bid and self.ask:
            return (self.bid + self.ask) / 2
        return self.last_price
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expiry
    
    @property
    def days_to_expiry(self) -> int:
        return (self.expiry - datetime.now()).days


class IBContractDiscovery:
    """
    Discovery dla IB Event Contracts.
    
    IB nie ma endpointu "daj wszystkie kontrakty" - musimy:
    1. Znać podstawowe symbole (FF, USIP, CPI - z Frontendu ForecastTrader)
    2. Dla każdego symbolu pobrać chain opcji (strikes + expiries)
    3. Zapisać wszystkie kombinacje
    """
    
    # Znane podstawowe symbole z ForecastTrader (znalezione ręcznie w UI)
    # Te trzeba raz zdobyć z https://www.interactivebrokers.com/en/index.php?f=22255 
    BASE_SYMBOLS = {
        # Economic
        'FF': {'category': 'ECONOMIC', 'name': 'Fed Funds Target Rate'},
        'USIP': {'category': 'ECONOMIC', 'name': 'US Industrial Production'},
        'CPI': {'category': 'ECONOMIC', 'name': 'US CPI YoY'},
        'NFP': {'category': 'ECONOMIC', 'name': 'Non-Farm Payrolls'},
        'CONF': {'category': 'ECONOMIC', 'name': 'Consumer Confidence'},
        # Financial  
        'SPX': {'category': 'FINANCIAL', 'name': 'S&P 500', 'exchange': 'CME'},
        'BTC': {'category': 'CRYPTO', 'name': 'Bitcoin', 'exchange': 'CME'},
        'ETH': {'category': 'CRYPTO', 'name': 'Ethereum', 'exchange': 'CME'},
    }
    
    def __init__(self, host: str = 'ib-gateway', port: int = 4002):
        self.host = host
        self.port = port
        self.ib = IB()
        
    async def connect(self):
        """Połączenie z IB Gateway."""
        await self.ib.connectAsync(self.host, self.port, clientId=99)
        logger.info(f"Connected to IB Gateway at {self.host}:{self.port}")
        
    def disconnect(self):
        """Rozłączenie."""
        self.ib.disconnect()
        logger.info("Disconnected from IB Gateway")
        
    async def discover_all_contracts(self) -> List[IBContract]:
        """
        Pobiera wszystkie dostępne Event Contracts.
        
        Dla każdego base symbol pobiera chain opcji (różne strike + expiry).
        """
        contracts = []
        
        for symbol, info in self.BASE_SYMBOLS.items():
            try:
                symbol_contracts = await self._discover_symbol_chain(
                    symbol=symbol,
                    category=info['category'],
                    exchange=info.get('exchange', 'FORECASTX')
                )
                contracts.extend(symbol_contracts)
                logger.info(f"Discovered {len(symbol_contracts)} contracts for {symbol}")
                await asyncio.sleep(0.5)  # Rate limiting - nie bombarduj IB
            except Exception as e:
                logger.error(f"Failed to discover {symbol}: {e}")
                continue
                
        return contracts
        
    async def _discover_symbol_chain(
        self, 
        symbol: str, 
        category: str,
        exchange: str
    ) -> List[IBContract]:
        """
        Dla danego symbolu pobiera wszystkie strikes i expiries.
        
        Event Contracts to de facto opcje binarne:
        - secType='OPT'
        - right='C' (YES - powyżej progu) lub 'P' (NO - poniżej progu)
        """
        contracts = []
        
        # 1. Pobierz kontrakt bazowy (podstawa dla opcji)
        underlying = Contract(
            symbol=symbol,
            secType='IND',  # Index dla podstawy
            exchange=exchange,
            currency='USD'
        )
        
        # 2. Pobierz dostępne expiries i strikes
        # reqContractDetails zwraca chain opcji jeśli podamy OPT
        # Ale dla Event Contracts musimy próbować różnych kombinacji
        
        # Podejście: pobierz wszystkie kontrakty OPT dla tego symbolu
        opt_contract = Contract(
            symbol=symbol,
            secType='OPT',
            exchange=exchange,
            currency='USD'
        )
        
        details_list = await self.ib.reqContractDetailsAsync(opt_contract)
        
        for details in details_list:
            c = details.contract
            
            # Sprawdź czy to Event Contract (ma krótki expiry i strike jako próg)
            if not c.lastTradeDateOrContractMonth:
                continue
                
            try:
                expiry = datetime.strptime(
                    c.lastTradeDateOrContractMonth, 
                    '%Y%m%d'
                )
            except ValueError:
                continue
                
            # Pomiń wygasłe
            if expiry < datetime.now():
                continue
                
            # Pomiń zbyt bliskie (brak płynności w ostatnich 48h)
            if expiry < datetime.now() + timedelta(hours=48):
                continue
            
            contracts.append(IBContract(
                conid=c.conId,
                symbol=symbol,
                name=f"{symbol} {c.lastTradeDateOrContractMonth} {c.strike}{c.right}",
                exchange=exchange,
                category=category,
                expiry=expiry,
                strike=c.strike if c.strike else None,
                right=c.right  # 'C' = YES, 'P' = NO
            ))
            
        return contracts
        
    async def refresh_prices(self, contracts: List[IBContract]) -> List[IBContract]:
        """
        Pobiera aktualne ceny (Bid/Ask) dla listy kontraktów.
        
        FORECASTX ma tylko Bid/Ask, nie ma Last Price.
        """
        updated = []
        
        for contract in contracts:
            try:
                # Stwórz obiekt Contract do subskrypcji
                ib_contract = Contract(
                    conId=contract.conid,
                    exchange=contract.exchange
                )
                
                # Pobierz market data (non-streaming, snapshot)
                ticker = self.ib.reqMktData(ib_contract, '', False, False)
                await asyncio.sleep(0.3)  # Daj czas na odpowiedź
                
                contract.bid = ticker.bid
                contract.ask = ticker.ask
                contract.last_price = ticker.last
                
                updated.append(contract)
                
                self.ib.cancelMktData(ib_contract)
                await asyncio.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"Failed to get price for {contract.symbol}: {e}")
                updated.append(contract)  # Dodaj bez ceny
                continue
                
        return updated


# Singleton dla łatwego użycia
discovery = IBContractDiscovery()


if __name__ == '__main__':
    # Test discovery
    logging.basicConfig(level=logging.INFO)
    
    async def test():
        await discovery.connect()
        
        print("🔍 Discovering IB Event Contracts...")
        contracts = await discovery.discover_all_contracts()
        
        print(f"\n📊 Found {len(contracts)} contracts:")
        
        # Grupuj po kategorii
        by_category = {}
        for c in contracts:
            by_category.setdefault(c.category, []).append(c)
            
        for cat, cat_contracts in by_category.items():
            print(f"\n{cat} ({len(cat_contracts)}):")
            for c in cat_contracts[:5]:  # Pokaż pierwsze 5
                print(f"  - {c.name} | Expiry: {c.expiry.strftime('%Y-%m-%d')} | Strike: {c.strike}")
                
        # Pobierz ceny dla pierwszych 3
        if contracts:
            print("\n💰 Refreshing prices for first 3 contracts...")
            priced = await discovery.refresh_prices(contracts[:3])
            for p in priced:
                print(f"  {p.symbol}: Bid={p.bid}, Ask={p.ask}, Mid={p.mid_price}")
        
        discovery.disconnect()
        
    asyncio.run(test())
