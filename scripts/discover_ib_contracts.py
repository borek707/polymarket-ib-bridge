#!/usr/bin/env python3
"""
Script: discover_ib_contracts.py

Pierwszy krok - odkryj jakie faktycznie kontrakty są dostępne na IB.
Bez hardcoded symboli, wszystko z TWS API.
"""

import asyncio
import json
import sys
from pathlib import Path

# Dodaj src do path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.discovery.ib_discovery import IBContractDiscovery


async def main():
    print("🔍 IB Contract Discovery")
    print("=" * 50)
    
    discovery = IBContractDiscovery(
        host='localhost',  # lub 'ib-gateway' w dockerze
        port=4002
    )
    
    try:
        await discovery.connect()
        print("✅ Connected to IB Gateway\n")
        
        # Discovery
        contracts = await discovery.discover_all_contracts()
        print(f"\n📊 Total discovered: {len(contracts)} contracts\n")
        
        # Grupuj po kategorii
        by_category = {}
        for c in contracts:
            by_category.setdefault(c.category, []).append(c)
        
        # Pobierz ceny dla pierwszych 10
        print("💰 Fetching prices...")
        priced = await discovery.refresh_prices(contracts[:10])
        
        # Output
        output = {
            'discovered_at': str(asyncio.get_event_loop().time()),
            'total': len(contracts),
            'by_category': {
                cat: [
                    {
                        'conid': c.conid,
                        'symbol': c.symbol,
                        'name': c.name,
                        'expiry': c.expiry.isoformat(),
                        'strike': c.strike,
                        'right': c.right,
                        'bid': c.bid,
                        'ask': c.ask,
                        'mid': c.mid_price
                    }
                    for c in cat_contracts[:5]  # Top 5 per category
                ]
                for cat, cat_contracts in by_category.items()
            }
        }
        
        # Zapisz do JSON
        output_path = Path('data/discovered_contracts.json')
        output_path.parent.mkdir(exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n💾 Saved to {output_path}")
        
        # Podsumowanie
        print("\n📋 Summary:")
        for cat, cat_contracts in by_category.items():
            print(f"  {cat}: {len(cat_contracts)} contracts")
        
        # Lista niedostępnych (wybory)
        print("\n🚫 Blocked for PL (elections):")
        print("  - US Presidential Election")
        print("  - Senate/House Control")
        print("  - Any political contracts")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        discovery.disconnect()
    
    return 0


if __name__ == '__main__':
    exit(asyncio.run(main()))
