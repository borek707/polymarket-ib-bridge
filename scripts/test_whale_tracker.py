#!/usr/bin/env python3
"""
Test whale tracker - sprawdź czy działa.
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.discovery.whale_tracker import WhaleTracker

logging.basicConfig(level=logging.INFO)


async def test_tracker():
    print("=" * 60)
    print("🐋 WHALE TRACKER TEST")
    print("=" * 60)
    
    # Stwórz tracker
    tracker = WhaleTracker(
        min_whale_score=50,  # Niższy próg dla testu
        max_wallets_tracked=20
    )
    
    print("\n1️⃣  Inicjalizacja...")
    print("   Pobieram top wallets z Polymarket...")
    
    try:
        await tracker.initialize()
        
        print(f"\n✅ Znaleziono {len(tracker.tracked_wallets)} wielorybów")
        
        if not tracker.tracked_wallets:
            print("\n⚠️  Brak wielorybów - API może być puste lub problem z połączeniem.")
            return
        
        # Pokaż top 10
        print("\n🏆 Top 10 Whale Wallets:")
        print("-" * 60)
        
        top_wallets = sorted(
            tracker.tracked_wallets.items(),
            key=lambda x: x[1].composite_score,
            reverse=True
        )[:10]
        
        for i, (addr, score) in enumerate(top_wallets, 1):
            print(f"{i:2}. {addr[:16]}...")
            print(f"    Score: {score.composite_score:.1f}/100")
            print(f"    Win Rate (90d): {score.win_rate_90d:.1f}%")
            print(f"    Avg ROI: {score.avg_roi:+.1f}%")
            print(f"    Trades: {score.trade_frequency}")
            print(f"    Volume: ${score.total_volume:,.0f}")
            print()
            
        # Sprawdź pozycje pierwszego wieloryba
        if top_wallets:
            top_addr = top_wallets[0][0]
            print(f"\n2️⃣  Pobieram pozycje dla top wallet...")
            positions = await tracker.get_wallet_positions(top_addr)
            
            if positions:
                print(f"   Znaleziono {len(positions)} pozycji:")
                for pos in positions[:3]:
                    print(f"   • {pos.market_question[:40]}...")
                    print(f"     {pos.outcome}: ${pos.size_usdc:,.0f} @ ${pos.entry_price:.2f}")
            else:
                print("   Brak aktywnych pozycji lub API nie zwróciło danych")
                
        print("\n✅ Test zakończony sukcesem!")
        
    except Exception as e:
        print(f"\n❌ Błąd: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_tracker())
