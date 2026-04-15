#!/usr/bin/env python3
"""
Script: test_correlation.py

Testuje silnik korelacji - czy potrafi poprawnie mapować Polymarket na IB.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.correlation.engine import CorrelationEngine, PolymarketMarket, IBContract


def main():
    # Przykładowe markety do testu
    test_markets = [
        PolymarketMarket(
            slug="fed-march-2025",
            question="Will the Fed raise rates in March 2025?",
            description="Federal Reserve interest rate decision",
            category="Economics",
            volume_24h=750000,
            yes_price=0.32,
            no_price=0.68,
            end_date="2025-03-19"
        ),
        PolymarketMarket(
            slug="cpi-above-3",
            question="Will CPI YoY be above 3% in January?",
            description="Consumer Price Index year over year",
            category="Economics",
            volume_24h=450000,
            yes_price=0.55,
            no_price=0.45,
            end_date="2025-01-15"
        ),
        PolymarketMarket(
            slug="trump-2024",
            question="Will Trump win the 2024 election?",
            description="US Presidential election",
            category="Politics",
            volume_24h=2000000,
            yes_price=0.51,
            no_price=0.49,
            end_date="2024-11-05"
        ),
        PolymarketMarket(
            slug="eth-3000-march",
            question="Will ETH be above $3000 on March 31?",
            description="Ethereum price prediction",
            category="Crypto",
            volume_24h=300000,
            yes_price=0.48,
            no_price=0.52,
            end_date="2025-03-31"
        ),
    ]
    
    # Symulowane kontrakty IB (w realu z discovery)
    ib_contracts = [
        IBContract(conid=751047561, symbol='FF', name='Fed Funds Mar25 4.875C', 
                  category='ECONOMIC', expiry='2025-03-19', strike=4.875, right='C'),
        IBContract(conid=751047562, symbol='FF', name='Fed Funds Mar25 4.875P',
                  category='ECONOMIC', expiry='2025-03-19', strike=4.875, right='P'),
        IBContract(conid=751048000, symbol='CPI', name='CPI Jan25 3.0C',
                  category='ECONOMIC', expiry='2025-01-15', strike=3.0, right='C'),
        IBContract(conid=751060000, symbol='ETH', name='ETH Mar25 3000C',
                  category='CRYPTO', expiry='2025-03-28', strike=3000, right='C'),
    ]
    
    engine = CorrelationEngine()
    
    print("🧪 Testing Correlation Engine")
    print("=" * 60)
    
    for market in test_markets:
        print(f"\n📊 Polymarket: {market.question[:50]}...")
        print(f"   Volume: ${market.volume_24h:,.0f} | YES: {market.yes_price:.2f}")
        
        result = engine.find_correlation(market, ib_contracts)
        
        if result:
            icon = "✅" if result.is_tradeable else "⚠️"
            print(f"\n   {icon} IB Match: {result.ib_name}")
            print(f"      Method: {result.method} | Score: {result.score:.2f} | {result.confidence}")
            print(f"      Direction: {result.direction}")
            print(f"      {result.rationale}")
        else:
            print(f"\n   ❌ No match (blocked or not found)")
    
    print("\n" + "=" * 60)
    print("Test complete. Check rationale for each match.")


if __name__ == '__main__':
    main()
