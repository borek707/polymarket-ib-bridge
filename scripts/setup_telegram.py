#!/usr/bin/env python3
"""
Setup Telegram notifications.

Krok po kroku jak skonfigurować bota i dostać chat ID.
"""

import asyncio
import os

import aiohttp


async def setup_telegram():
    print("=" * 60)
    print("📱 TELEGRAM SETUP")
    print("=" * 60)
    
    print("\n1. Stwórz bota:")
    print("   a) Otwórz Telegram i znajdź @BotFather")
    print("   b) Wyślij: /newbot")
    print("   c) Nadaj nazwę (np. 'My Whale Bot')")
    print("   d) Nadaj username (np. 'my_whale_bot') - musi kończyć się na 'bot'")
    print("   e) Skopiuj token (wygląda tak: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)")
    
    token = input("\n   Wklej token: ").strip()
    
    print("\n2. Znajdź swój chat ID:")
    print("   a) Otwórz: https://t.me/userinfobot")
    print("   b) Kliknij START")
    print("   c) Skopiuj 'Id:' (wygląda tak: 123456789)")
    
    chat_id = input("\n   Wklej chat ID: ").strip()
    
    # Test połączenia
    print("\n3. Testuję połączenie...")
    
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": "🐋 Whale Bot is connected!\n\nYou will receive alerts here.",
            "parse_mode": "HTML"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    print("✅ SUCCESS! Wiadomość testowa wysłana!")
                    print("\n4. Zapisz do .env:")
                    print(f"   TELEGRAM_BOT_TOKEN={token}")
                    print(f"   TELEGRAM_CHAT_ID={chat_id}")
                    
                    # Zapisz do pliku
                    save = input("\nZapisać do .env? (tak/nie): ").strip().lower()
                    if save in ['tak', 't', 'yes', 'y']:
                        with open('.env', 'a') as f:
                            f.write(f"\n# Telegram\n")
                            f.write(f"TELEGRAM_BOT_TOKEN={token}\n")
                            f.write(f"TELEGRAM_CHAT_ID={chat_id}\n")
                        print("✅ Zapisano do .env")
                else:
                    error = await resp.text()
                    print(f"❌ Błąd: {error}")
                    
    except Exception as e:
        print(f"❌ Błąd połączenia: {e}")


if __name__ == '__main__':
    asyncio.run(setup_telegram())
