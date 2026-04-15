"""
Correlation Engine - mapuje Polymarket na IB.

Używa wielu strategii:
1. Fuzzy string matching (rapidfuzz)
2. Keyword mapping (cache w DB)
3. Embedding similarity (sentence-transformers)
4. Manual overrides (DB-based)
"""

import re
import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from rapidfuzz import fuzz, process


@dataclass
class PolymarketMarket:
    """Market z Polymarket."""
    slug: str
    question: str
    description: str
    category: str
    volume_24h: float
    yes_price: float
    no_price: float
    end_date: str
    
    @property
    def implied_probability(self) -> float:
        """Ryzyko-neutralne prawdopodobieństwo (cena YES)."""
        return self.yes_price


@dataclass 
class IBContract:
    """Kontrakt z IB (uproszczony dla engine)."""
    conid: int
    symbol: str
    name: str
    category: str
    expiry: str
    strike: Optional[float]
    right: str  # 'C' (YES) or 'P' (NO)


@dataclass
class CorrelationResult:
    """Wynik mapowania."""
    poly_slug: str
    poly_question: str
    ib_conid: int
    ib_symbol: str
    ib_name: str
    score: float  # 0-1
    method: str  # 'fuzzy', 'keyword', 'embedding', 'manual'
    direction: str  # 'SAME' (YES=C) lub 'INVERSE' (YES=P)
    confidence: str  # 'HIGH' (>=0.8), 'MEDIUM' (>=0.6), 'LOW'
    rationale: str
    
    @property
    def is_tradeable(self) -> bool:
        return self.score >= 0.6 and self.confidence in ('HIGH', 'MEDIUM')


class CorrelationEngine:
    """
    Silnik mapujący markety Polymarket na kontrakty IB.
    """
    
    # Keywords dla szybkiego matchingu
    KEYWORD_MAP = {
        # Polymarket keyword -> IB symbol
        'fed funds': ('FF', 'SAME', 0.95),
        'federal reserve': ('FF', 'SAME', 0.90),
        'fomc': ('FF', 'SAME', 0.95),
        'interest rate': ('FF', 'SAME', 0.80),
        
        'industrial production': ('USIP', 'SAME', 0.90),
        
        'cpi': ('CPI', 'SAME', 0.95),
        'consumer price index': ('CPI', 'SAME', 0.95),
        'inflation': ('CPI', 'SAME', 0.75),  # Słabsza korelacja
        
        'non-farm payrolls': ('NFP', 'SAME', 0.95),
        'nonfarm': ('NFP', 'SAME', 0.95),
        'unemployment rate': ('NFP', 'SAME', 0.70),
        
        'consumer confidence': ('CONF', 'SAME', 0.90),
        
        's&p 500': ('SPX', 'SAME', 0.90),
        'sp500': ('SPX', 'SAME', 0.90),
        'spx': ('SPX', 'SAME', 0.95),
        
        'bitcoin': ('BTC', 'SAME', 0.95),
        'btc': ('BTC', 'SAME', 0.95),
        
        'ethereum': ('ETH', 'SAME', 0.95),
        'eth': ('ETH', 'SAME', 0.95),
        
        # Wybory - zablokowane
        'trump': None,
        'biden': None,
        'election': None,
        'president': None,
    }
    
    def __init__(self, db_path: str = 'data/bridge.db'):
        self.db_path = db_path
        self._init_db()
        
        # Cache manual overrides
        self.manual_overrides = self._load_manual_overrides()
        
    def _init_db(self):
        """Tworzy tabele dla korelacji."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS correlations (
                    poly_slug TEXT PRIMARY KEY,
                    ib_conid INTEGER,
                    score REAL,
                    method TEXT,
                    direction TEXT,
                    confidence TEXT,
                    rationale TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS manual_overrides (
                    poly_slug TEXT PRIMARY KEY,
                    ib_conid INTEGER,
                    rationale TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
    def _load_manual_overrides(self) -> dict:
        """Wczytuje ręczne mapowania z DB."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute('SELECT poly_slug, ib_conid, rationale FROM manual_overrides')
            return {
                row[0]: {'conid': row[1], 'rationale': row[2]}
                for row in cur.fetchall()
            }
    
    def add_manual_override(self, poly_slug: str, ib_conid: int, rationale: str):
        """Dodaje ręczne mapowanie (np. po review)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO manual_overrides (poly_slug, ib_conid, rationale)
                VALUES (?, ?, ?)
            ''', (poly_slug, ib_conid, rationale))
            conn.commit()
        self.manual_overrides[poly_slug] = {'conid': ib_conid, 'rationale': rationale}
        
    def find_correlation(
        self, 
        market: PolymarketMarket, 
        ib_contracts: List[IBContract]
    ) -> Optional[CorrelationResult]:
        """
        Znajduje najlepszy kontrakt IB dla danego marketu Polymarket.
        
        Metody w kolejności priorytetu:
        1. Manual override (najwyższy priorytet)
        2. Keyword matching (szybki)
        3. Fuzzy string matching (dokładny)
        """
        question_lower = market.question.lower()
        desc_lower = market.description.lower() if market.description else ''
        
        # 1. Sprawdź manual override
        if market.slug in self.manual_overrides:
            override = self.manual_overrides[market.slug]
            ib_contract = self._find_contract_by_conid(ib_contracts, override['conid'])
            if ib_contract:
                return CorrelationResult(
                    poly_slug=market.slug,
                    poly_question=market.question,
                    ib_conid=ib_contract.conid,
                    ib_symbol=ib_contract.symbol,
                    ib_name=ib_contract.name,
                    score=1.0,
                    method='manual',
                    direction='SAME',  # Manual overrides zakładają właściwy kierunek
                    confidence='HIGH',
                    rationale=f"Manual override: {override['rationale']}"
                )
        
        # 2. Keyword matching
        keyword_result = self._keyword_match(market, ib_contracts)
        if keyword_result and keyword_result.score >= 0.8:
            return keyword_result
            
        # 3. Fuzzy matching
        fuzzy_result = self._fuzzy_match(market, ib_contracts)
        
        # Zwróć lepszy wynik
        if keyword_result and fuzzy_result:
            return keyword_result if keyword_result.score >= fuzzy_result.score else fuzzy_result
        return keyword_result or fuzzy_result
        
    def _keyword_match(
        self, 
        market: PolymarketMarket, 
        ib_contracts: List[IBContract]
    ) -> Optional[CorrelationResult]:
        """Szybki matching po keywords."""
        question_lower = market.question.lower()
        
        for keyword, mapping in self.KEYWORD_MAP.items():
            if keyword in question_lower:
                if mapping is None:
                    # Wyraźne wykluczenie (np. wybory)
                    return None
                    
                symbol, direction, confidence = mapping
                ib_contract = self._find_contract_by_symbol(ib_contracts, symbol)
                
                if ib_contract:
                    return CorrelationResult(
                        poly_slug=market.slug,
                        poly_question=market.question,
                        ib_conid=ib_contract.conid,
                        ib_symbol=ib_contract.symbol,
                        ib_name=ib_contract.name,
                        score=confidence,
                        method='keyword',
                        direction=direction,
                        confidence='HIGH' if confidence >= 0.8 else 'MEDIUM',
                        rationale=f"Keyword match: '{keyword}' -> {symbol}"
                    )
        return None
        
    def _fuzzy_match(
        self, 
        market: PolymarketMarket, 
        ib_contracts: List[IBContract]
    ) -> Optional[CorrelationResult]:
        """Fuzzy matching nazw."""
        # Przygotuj listę nazw IB
        ib_names = [(c, c.name) for c in ib_contracts]
        
        # Dopasuj pytanie Polymarket do nazw IB
        # Użyj weighted ratio (uwzględnia długość stringów)
        best_match = process.extractOne(
            market.question,
            [n[1] for n in ib_names],
            scorer=fuzz.WRatio
        )
        
        if best_match and best_match[1] >= 60:  # Min 60% similarity
            matched_name = best_match[0]
            score = best_match[1] / 100.0
            
            # Znajdź kontrakt
            ib_contract = next(c for c, n in ib_names if n == matched_name)
            
            return CorrelationResult(
                poly_slug=market.slug,
                poly_question=market.question,
                ib_conid=ib_contract.conid,
                ib_symbol=ib_contract.symbol,
                ib_name=ib_contract.name,
                score=score,
                method='fuzzy',
                direction='SAME',  # Fuzzy nie wie o kierunku - zakładamy same
                confidence='HIGH' if score >= 0.8 else ('MEDIUM' if score >= 0.6 else 'LOW'),
                rationale=f"Fuzzy match: '{market.question[:50]}...' ~ '{matched_name[:50]}...' ({best_match[1]}%)"
            )
        return None
        
    def _find_contract_by_symbol(
        self, 
        contracts: List[IBContract], 
        symbol: str
    ) -> Optional[IBContract]:
        """Znajduje pierwszy aktywny kontrakt dla symbolu."""
        for c in contracts:
            if c.symbol == symbol:
                return c
        return None
        
    def _find_contract_by_conid(
        self, 
        contracts: List[IBContract], 
        conid: int
    ) -> Optional[IBContract]:
        """Znajduje kontrakt po conid."""
        for c in contracts:
            if c.conid == conid:
                return c
        return None
        
    def batch_correlate(
        self,
        poly_markets: List[PolymarketMarket],
        ib_contracts: List[IBContract],
        min_score: float = 0.6
    ) -> List[CorrelationResult]:
        """Mapuje wiele marketów naraz."""
        results = []
        
        for market in poly_markets:
            result = self.find_correlation(market, ib_contracts)
            if result and result.score >= min_score:
                results.append(result)
                self._save_correlation(result)
                
        return results
        
    def _save_correlation(self, result: CorrelationResult):
        """Zapisuje korelację do bazy."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO correlations
                (poly_slug, ib_conid, score, method, direction, confidence, rationale, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                result.poly_slug,
                result.ib_conid,
                result.score,
                result.method,
                result.direction,
                result.confidence,
                result.rationale
            ))
            conn.commit()


if __name__ == '__main__':
    # Test engine
    engine = CorrelationEngine()
    
    # Przykładowe markety
    test_markets = [
        PolymarketMarket(
            slug="will-fed-raise-rates-march",
            question="Will the Fed raise interest rates in March 2025?",
            description="Federal Reserve target rate decision",
            category="Economics",
            volume_24h=500000,
            yes_price=0.35,
            no_price=0.65,
            end_date="2025-03-19"
        ),
        PolymarketMarket(
            slug="trump-win-2024",
            question="Will Trump win the 2024 election?",
            description="US Presidential election",
            category="Politics",
            volume_24h=1000000,
            yes_price=0.52,
            no_price=0.48,
            end_date="2024-11-05"
        ),
        PolymarketMarket(
            slug="eth-above-3000",
            question="Will ETH be above $3000 on March 31?",
            description="Ethereum price prediction",
            category="Crypto",
            volume_24h=200000,
            yes_price=0.45,
            no_price=0.55,
            end_date="2025-03-31"
        )
    ]
    
    # Przykładowe kontrakty IB
    test_contracts = [
        IBContract(conid=1, symbol='FF', name='Fed Funds Mar25 4.875C', category='ECONOMIC', expiry='2025-03-19', strike=4.875, right='C'),
        IBContract(conid=2, symbol='ETH', name='ETH Mar25 3000C', category='CRYPTO', expiry='2025-03-28', strike=3000, right='C'),
    ]
    
    print("🧪 Testing Correlation Engine\n")
    
    for market in test_markets:
        result = engine.find_correlation(market, test_contracts)
        
        if result:
            status = "✅" if result.is_tradeable else "⚠️"
            print(f"{status} {market.question[:50]}...")
            print(f"   Method: {result.method} | Score: {result.score:.2f} | Confidence: {result.confidence}")
            print(f"   IB: {result.ib_name} | Direction: {result.direction}")
            print(f"   Rationale: {result.rationale}")
        else:
            print(f"❌ {market.question[:50]}...")
            print("   No correlation found (probably blocked or no match)")
        print()
