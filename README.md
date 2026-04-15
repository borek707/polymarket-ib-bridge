# Polymarket-IB Bridge 🐋

**Arbitrage prediction markets**: Śledź wieloryby na Polymarket, wykonuj na Interactive Brokers ForecastTrader.

---

## 📖 Spis treści

1. [Jak to działa](#jak-to-działa)
2. [Wymagania](#wymagania)
3. [Instalacja krok po kroku](#instalacja-krok-po-kroku)
4. [Konfiguracja](#konfiguracja)
5. [Użycie](#użycie)
6. [Troubleshooting](#troubleshooting)
7. [Architektura](#architektura)

---

## 🎯 Jak to działa

```
Polymarket = Radar/Sygnał (obserwacja wielorybów)
IB = Egzekucja (tylko tu handlujesz)

Flow:
1. System 24/7 monitoruje Polymarket (2 metody):
   a) Volume spikes (Public API) - duże trady $50k+
   b) Top wallet tracking - śledzi top 20 portfeli z największym volume
2. Wykrywa aktywność wielorybów
3. Mapuje na kontrakty IB (correlation engine)
4. Wysyła powiadomienie (Telegram/Discord/Console)
5. Ty wykonujesz w IB (lub bot auto-egzekucja w trybie LIVE)
```

### Dwie metody detekcji:

| Metoda | Co śledzi | Źródło | Min Volume |
|--------|-----------|--------|------------|
| **Volume Spikes** | Duże trady | data-api.polymarket.com | $50,000 |
| **Wallet Tracker** | Top 20 portfeli | Analiza 1000 ostatnich tradów | Top N |

### Przykład sygnału (Telegram/Console):

```
🟢 WHALE SIGNAL - Confidence 9/10

📊 Market: Fed Interest Rate Decision - March 2025
🐋 Whale Activity: $200,000
🎯 Action: BUY YES

💰 PRICES:
• Polymarket: $0.72
• IB Suggested: $0.66
• Expected Profit: 9.1%

📝 HOW TO EXECUTE:
1. Open IB TWS / Mobile
2. Search: FF MAR25
3. Select "BUY YES"
4. Limit Price: $0.66
5. Quantity: 100 contracts ($100)
6. Submit Order

⚠️ Risk: LOW - High confidence whale signal
💡 Reason: Whale bought $200k YES, IB hasn't caught up yet
```

---

## ✅ Wymagania

### Konto Interactive Brokers
- [ ] Konto IB z włączonymi **Event Contracts** (ForecastX)
- [ ] Min. $500 na paper trading, $2000+ na live
- [ ] Dostęp do TWS lub IB Gateway

### System
- [ ] Python 3.10+
- [ ] Docker (opcjonalnie, dla IB Gateway)
- [ ] 2GB RAM wystarczy (bez lokalnego węzła blockchain!)

### VPN (opcjonalnie)
- Dla Polymarket API nie jest wymagany (publiczne endpointy)
- Dla scrapingu strony może być potrzebny US IP

---

## 🚀 Instalacja krok po kroku

### Krok 1: Klonowanie repo

```bash
git clone https://github.com/twoj-user/polymarket-ib-bridge.git
cd polymarket-ib-bridge
```

### Krok 2: Instalacja zależności

```bash
# Virtual env (zalecane)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# lub: venv\Scripts\activate  # Windows

# Zależności
pip install -r requirements.txt
```

### Krok 3: Konfiguracja środowiska

```bash
cp .env.example .env
# Edytuj .env w swoim edytorze
```

**Minimalna konfiguracja w `.env`:**

```env
# Interactive Brokers
IB_USER=twój_login_ib
IB_PASS=twoje_hasło_ib
IB_ACCOUNT_ID=DU1234567  # lub U1234567 dla live
IB_TRADING_MODE=paper     # paper lub live
VNC_PASSWORD=changeme

# API IB
IB_GATEWAY_HOST=localhost  # lub ib-gateway jeśli Docker
IB_GATEWAY_PORT=4002

# Powiadomienia - wybierz jeden
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=123456789

# Albo Discord:
# DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Risk Management (opcjonalnie)
MAX_DAILY_LOSS_USD=100
MAX_POSITION_SIZE_USD=50
PAPER_TRADING=true
AUTO_EXECUTION=false
```

### Krok 4: Uruchomienie IB Gateway

**Opcja A: Docker (zalecane)**

```bash
docker-compose -f docker/ib-gateway.yml up -d
```

**Opcja B: TWS lokalnie**
- Otwórz TWS → Edit → Global Configuration → API → Enable "Create API message"
- Port: 4002 (lub 7496 dla TWS)

Sprawdź czy działa:
```bash
python scripts/discover_ib_contracts.py
```

---

## ⚙️ Konfiguracja

### Telegram Bot (zalecane)

1. Napisz do [@BotFather](https://t.me/botfather) na Telegramie
2. Utwórz nowego bota: `/newbot`
3. Skopiuj token (np. `123456:ABC...`)
4. Dodaj bota do swojej grupy lub napisz do niego
5. Pobierz chat ID:
   ```bash
   curl https://api.telegram.org/bot<TWÓJ_TOKEN>/getUpdates
   ```
6. Wypełnij `TELEGRAM_BOT_TOKEN` i `TELEGRAM_CHAT_ID` w `.env`

### Discord Webhook

1. W Discordzie: Ustawienia kanału → Integracje → Webhooks
2. Utwórz webhook i skopiuj URL
3. Wypełnij `DISCORD_WEBHOOK_URL` w `.env`

### Risk Management

Zmienne w `.env`:

| Zmienna | Domyślnie | Opis |
|---------|-----------|------|
| `MAX_DAILY_LOSS_USD` | 100 | Max strata dziennia - potem STOP |
| `MAX_POSITION_SIZE_USD` | 50 | Max wartość jednej pozycji |
| `CIRCUIT_BREAKER_ERRORS` | 5 | Ile błędów przed emergency stop |
| `PAPER_TRADING` | true | true = symulacja, false = prawdziwe zlecenia |
| `AUTO_EXECUTION` | false | true = bot sam wykonuje, false = tylko alerty |

---

## 🎮 Użycie

### Testowanie tracker'a wielorybów

```bash
python scripts/test_whale_tracker.py
```

Oczekiwany output:
```
============================================================
🐋 WHALE TRACKER TEST
============================================================

1️⃣  Inicjalizacja...
   Pobieram top wallets z Polymarket...

✅ Znaleziono 20 wielorybów

🏆 Top 10 Whale Wallets:
------------------------------------------------------------
 1. 0x68c24bf4a8ad4d...
    Score: 26.4/100
    Win Rate (90d): 50.3%
    Avg ROI: +3.0%
    Volume: $15,000
...
```

### Testowanie korelacji (mapowania marketów)

```bash
python scripts/test_correlation.py
```

### Uruchomienie paper trading (symulacja)

```bash
# Tryb paper - tylko obserwacja i powiadomienia
python scripts/live_trader.py --paper

# Z włączonym trackerem portfeli (zalecane)
python scripts/live_trader.py --paper --wallet-tracker

# Wyższy próg dla wielorybów
python scripts/live_trader.py --paper --min-whale-score 80
```

### Uruchomienie live trading (OSTROŻNIE!)

```bash
# WYMAGANE: Ustaw w .env: PAPER_TRADING=false, AUTO_EXECUTION=true
# Bot będzie wykonywał prawdziwe zlecenia!
python scripts/live_trader.py --live
```

**Zalecana ścieżka:**
1. Tydzień w `--paper` bez `--auto-execution` → obserwuj sygnały
2. Tydzień w `--paper` z `--auto-execution` → testuj logikę
3. Dopiero potem `--live` z małymi kwotami

### Parametry linii komend

```bash
python scripts/live_trader.py --help
```

| Parametr | Opis |
|----------|------|
| `--paper` | Tryb symulacji (domyślnie) |
| `--live` | Prawdziwe zlecenia |
| `--wallet-tracker` | Włącz śledzenie top portfeli |
| `--no-wallet-tracker` | Wyłącz tracker (tylko volume spikes) |
| `--min-whale-score N` | Min score wieloryba (domyślnie 65) |
| `--check-interval N` | Co ile sekund sprawdzać (domyślnie 30) |
| `--min-volume USD` | Min wielkość tradu (domyślnie 50000) |
| `--auto-execute` | Automatyczne wykonywanie zleceń |

---

## 🔧 Troubleshooting

### "Module not found"

```bash
# Upewnij się że jesteś w virtual env
source venv/bin/activate
pip install -r requirements.txt
```

### "Cannot connect to IB Gateway"

```bash
# Sprawdź czy IB Gateway działa
curl http://localhost:4002/v1/health

# Jeśli nie działa, sprawdź:
# 1. Czy IB Gateway/TWS jest włączony
# 2. Czy port 4002 jest otwarty
# 3. Czy w TWS jest włączony API (Edit → Global Config → API)
```

### "No whale signals detected"

To normalne! Wieloryby pojawiają się falami. Sprawdź czy tracker działa:
```bash
python scripts/test_whale_tracker.py
```

Jeśli pokazuje portfele, system działa — czekaj na sygnały.

### "Telegram not sending messages"

```bash
# Testuj bota:
curl -X POST https://api.telegram.org/bot<TWÓJ_TOKEN>/sendMessage \
  -d chat_id=<TWÓJ_CHAT_ID> \
  -d text="Test message"
```

### "Data API returns 404"

Był to problem z endpointem `/leaderboard` — naprawiliśmy to analizując `/trades` zamiast leaderboardu. Jeśli widzisz ten błąd, zaktualizuj repo:
```bash
git pull origin main
```

---

## 🏗️ Architektura

```
┌─────────────────────────────────────────────────────────────┐
│                      POLYMARKET                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Gamma API   │  │  Data API    │  │   CLOB API   │      │
│  │  (markets)   │  │  (trades)    │  │ (orderbook)  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼────────────────┼────────────────┼──────────────┘
          │                │                │
          └────────────────┴────────────────┘
                           │
          ┌────────────────┴────────────────┐
          │                                 │
┌─────────▼──────────┐          ┌───────────▼──────────┐
│  Volume Spikes     │          │   Wallet Tracker     │
│  (whale_detector)  │          │  (whale_tracker)     │
│  - Duże trady $50k+│          │  - Top 20 portfeli   │
└─────────┬──────────┘          └───────────┬──────────┘
          │                               │
          └──────────────┬────────────────┘
                         │
          ┌──────────────▼────────────────┐
          │      Correlation Engine       │
          │   (mapowanie na IB)           │
          └──────────────┬────────────────┘
                         │
          ┌──────────────▼────────────────┐
          │      Risk Manager             │
          │   - Circuit breakers          │
          │   - Daily limits              │
          └──────────────┬────────────────┘
                         │
          ┌──────────────▼────────────────┐
          │   Notification Manager        │
          │   (Telegram/Discord/Console)  │
          └──────────────┬────────────────┘
                         │
          ┌──────────────▼────────────────┐
          │      Live Execution           │
          │   (Interactive Brokers)       │
          └───────────────────────────────┘
```

### Struktura katalogów:

```
polymarket-ib-bridge/
├── README.md                 # Ten plik
├── requirements.txt          # Zależności
├── .env.example             # Przykładowa konfiguracja
├── .gitignore               # Ignorowane pliki
├── docker/
│   ├── ib-gateway.yml       # Docker Compose dla IB
│   └── polymarket-vpn.yml   # Opcjonalny VPN
├── scripts/
│   ├── live_trader.py       # GŁÓWNY SKRYPT
│   ├── paper_trader.py      # Tylko symulacja
│   ├── test_whale_tracker.py # Test tracker'a
│   ├── test_correlation.py  # Test korelacji
│   ├── discover_ib_contracts.py  # Discovery IB
│   └── setup_telegram.py    # Setup bota Telegram
└── src/
    ├── api/server.py        # REST API (opcjonalne)
    ├── correlation/engine.py # Silnik korelacji
    ├── discovery/
    │   ├── polymarket_discovery.py  # API Polymarket
    │   ├── ib_discovery.py          # API IB
    │   ├── whale_detector.py        # Volume spikes
    │   └── whale_tracker.py         # Wallet tracker
    ├── execution/
    │   ├── live_trading.py  # Prawdziwe zlecenia
│   │   └── paper_trading.py # Symulacja
    ├── notifications/manager.py # Powiadomienia
    └── risk/manager.py      # Zarządzanie ryzykiem
```

---

## ⚠️ Ważne uwagi

1. **Zacznij od paper trading** — nigdy nie uruchamiaj `--live` od razu
2. **Nie wymagamy lokalnego węzła Polygon** — oszczędzasz 500 GB
3. **Risk management jest wymuszony** — system ma wbudowane limity
4. **API Polymarket jest publiczne** — nie wymaga VPN

---

## 📄 Licencja

MIT License — używaj na własne ryzyko. Pamiętaj że trading wiąże się z ryzykiem straty kapitału.

---

## 🆘 Wsparcie

Problemy? Otwórz issue na GitHubie lub sprawdź:
1. `python scripts/test_whale_tracker.py` — czy tracker działa?
2. `python scripts/test_correlation.py` — czy korelacja działa?
3. `curl http://localhost:4002/v1/health` — czy IB Gateway działa?

---

**Niech wieloryby będą z Tobą! 🐋🔥**
