# RAPORT: Polymarket-IB Bridge - Analiza sensu biznesowego i technologicznego

## Ocena koncowa: 2/10 (projekt praktycznie nie ma racji bytu)

---

## 1. IB ForecastTrader / Event Contracts - co faktycznie oferuje IB?

### Kategorie kontraktow na IB ForecastTrader:

Na podstawie oficjalnych zrodel IBKR [^59^][^60^][^37^]:

| Kategoria | Przyklady kontraktow | Dostepnosc EU |
|---|---|---|
| **Economic Indicators** | CPI, Fed Funds Rate, GDP, Consumer Confidence, Retail Sales, Unemployment | TAK |
| **Financial Markets** | S&P 500 futures, Ethereum Price, Solana Price, indeksy | TAK |
| **Environmental/Climate** | Global CO2, Global Temperature, US Electricity Generation | TAK |
| **Government** | House/Senate control, ballot measures | TAK |
| **Elections** | US Presidential, Congressional races | **Tylko US residents** [^30^] |
| **CME Event Contracts** | Equity Index, Energy, Metals, FX futures | TAK |

### Czego IB ForecastTrader NIE oferuje:

- **SPORT** - IB NIE ma kontraktow sportowych [^37^]
- **Crypto CFD** - IB NIE oferuje crypto CFD (to zupelnie inny instrument) [^51^][^53^]
- **Geopolityka** - brak kontraktow na wojny, konflikty, ceasfire
- **Kultura/rozrywka** - brak kontraktow na Oscary, Grammy, Netflix
- **Technology/AI** - brak kontraktow na product launches, AI benchmarks

> "The key event contract categories on ForecastTrader are: financial markets, economic indicators, elections, environment, government actions" [^37^]

> "Forecast contracts on U.S. elections are only available to eligible U.S. residents" [^32^]

### Podsumowanie:
IB ForecastTrader to platforma skoncentrowana na **makroekonomii, klimacie i wyborach USA**. To NIE jest platforma do betowania na sport, kulture czy geopolityke. Wersja dla EU (.ie) jest jeszcze bardziej okrojona - brakuje na niej kategorii "Elections" [^30^].

---

## 2. Polymarket vs IB - jaki jest faktyczny OVERLAP?

### Kategorie Polymarket (10,000+ aktywnych rynkow) [^43^][^48^][^56^]:

| Kategoria | Udzial w wolumenie | Na IB? |
|---|---|---|
| Sports | ~39% | **NIE** |
| Politics | ~34% | **Czesciowo** (tylko US elections, tylko US residents) |
| Crypto | ~18% | **Czesciowo** (tylko ETH/SOL price, nie event contracts) |
| Geopolitics | ~5% | **NIE** |
| Finance/Economy | ~3% | **TAK** (to glowny overlap) |
| Technology/AI | ~1% | **NIE** |
| Culture/Weather | <1% | **NIE** (climate tylko czesciowo) |

### FAKTYCZNY OVERLAP:

**Tylko ~3-5% rynkow Polymarket ma ekwiwalent na IB ForecastTrader.**

Konkretnie:
- **Fed Funds Rate** - TAK na obu
- **CPI/inflacja** - TAK na obu  
- **S&P 500 futures** - TAK na obu
- **ETH/SOL price** - TAK na obu (ale jako rozne instrumenty)

**90-95% rynkow Polymarket NIE ISTNIEJE na IB**, w tym:
- 100% sportu (NBA, NFL, NHL, MLB, FIFA, F1, itd.)
- 100% kultury (Eurovision, Oscary, Netflix)
- 100% geopolityki (Israel/Hezbollah, Iran, ceasefire)
- 100% technologii (ChatGPT, product launches, AI benchmarks)
- 95% polityki (nie-US elections, prywatne polityczne zaklady)

### Wniosek:
Strategia "skopiuj z Polymarket na IB" ma sens tylko dla ~5% rynkow. Dla 95% rynkow Polymarket nie ma gdzie kopiowac.

---

## 3. Whale following jako strategia - czy to sie oplaca?

### Statystyki Polymarket - ogolna skutecznosc:

| Metryka | Wartosc | Zrodlo |
|---|---|---|
| % traderow tracacych pieniadze | **84.1%** | Badanie Andrey Sergeenkov, kwiecien 2026, 2.5M walletow [^17^][^19^] |
| % traderow z zyskiem >$1000 | **2%** | Sergeenkov 2026 [^17^] |
| % traderow z zyskiem >$10,000 | **0.033%** (840 walletow) | Sergeenkov 2026 [^20^] |
| % traderow konsekwentnie zarabiajacych >$1000/msc | **~1%** | [^19^] |
| Wash trading | **25% calego wolumenu** | Badanie Columbia University [^62^][^63^] |

> "A new study says 84.1% of Polymarket traders lose money. That's down from 40% just two years ago" [^17^]

### Analiza top 10 wielorybow Polymarket [^15^][^16^]:

| Wieloryb | Win rate (settled) | PRAWDZIWY win rate (z zombie orders) | Zysk grudzien 2025 |
|---|---|---|---|
| SeriouslySirius | 73.7% | **53.3%** | $3.29M |
| DrPufferfish | 83.5% | **50.9%** | $2.06M |
| gmanas | N/D | **51.8%** | $1.97M |
| simonbanza | N/D | **57.6%** | $1.04M |
| gmpm | N/D | **56.2%** | N/D |
| swisstony | N/D | N/D | $860K (avg $156/trade) |
| 0xafEe | N/D | **69.5%** | $929K |

### Kluczowe wnioski o wielorybach:

1. **"Zombie orders" zawyzaja win rate** - wieloryby nie zamykaja przegranych pozycji, zeby statystyki wygladaly lepiej. Prawdziwy win rate to ~50-57%, czyli lekko powyzej monety [^15^].

2. **Zyski pochodza z position management, nie predykcji** - SeriouslySirius mial profit/loss ratio 2.52, DrPufferfish az 8.62. To zarzadzanie ryzykiem daje zyski, nie trafnosc predykcji [^16^].

3. **Hedging, nie kierunkowe zaklady** - ~40% zlecen top wieloryba to zlecenia hedgingowe. Strategia to NIE "kupuje YES jak wieloryb", tylko skomplikowane sieci zabezpieczen [^15^].

4. **25% wolumenu to wash trading** - Badanie Columbia University wykrylo ze 25% historycznego wolumenu to sztuczne transakcje, w szczegolnosci 45% w sportowych rynkach [^62^][^63^].

5. **Copy trading na Hyperliquid** - badanie akademickie pokazalo, ze kopioanie wielorybow >=$5M daje +11% w 2.5 miesiaca, ale kopioanie wszystkich wielorybow traci pieniadze [^44^]. **To badanie bylo na Hyperliquid (perpetual futures), NIE na Polymarket.**

### Wniosek:
Sledzenie wielorybow na Polymarket NIE daje edge. Prawdziwy win rate to ~50-57%, a zyski pochodza z zarzadzania ryzykiem, nie z kierunkowych predykcji. Nie da sie "skopiowac" strategii hedgingowej automatycznie.

---

## 4. Latency arbitrage - czy 2-5% opoznienia to realna przewaga?

### Jak szybko zamyka sie arbitrage na prediction markets:

| Typ arbitrage | Window czasowy | Zrodlo |
|---|---|---|
| Intra-market (YES+NO<$1) | **Sekundy** w plynnym rynku [^25^] | |
| Cross-signal (Binance BTC -> Polymarket) | **30-90 sekund** [^25^] | |
| Repricing po newsach | **1-3 minuty** [^38^] | |
| Sports live arbitrage | **5-15 sekund** (stream delay) [^24^] | |

### Polymarket infrastruktura:

- Serwery: **AWS eu-west-2 (Londyn)** [^35^]
- Latency z US: ~130ms RTT [^25^]
- Target dla market makerow/arbitrage: **<5ms** [^35^]
- API rate limit: 60 orders/minute [^25^]
- Dynamic taker fees: do **3.15% na kontraktach 50-centowych** [^35^]

### Dlaczego 2-5% opoznienia to PRZEGRANA strategia:

1. **W erze HFT, arbitrage window to milisekundy-sekundy**, nie procenty. Boty arbitrage na Polymarket dzialaja w skali milisekund [^5^].

2. **Intra-market arbitrage (YES+NO<$1) zamyka sie w SEKUNDY** - bot "gabagool" zrealizowal 1,266 YES + 1,294 NO jednoczesnie. Top 3 portfele zarobily $4.2M na tym w 12 miesiecy [^25^].

3. **Dynamic taker fees zjadaja zysk** - Polymarket wprowadzil dynamic taker fees az do 3.15% na kontraktach 50-centowych, celowo aby zwalczac latency arbitrage [^35^].

4. **Cross-platform arbitrage jest utrudniony** - rozne regulacje settlement, rozne oracle, rozne definicje wydarzen. "The hardest part here is the four words 'same event'" [^27^].

### Wniosek:
Opoznienie 2-5% to **szmat czasu** w prediction markets. Realne arbitrage window to milisekundy (intra-market) lub 30-90 sekund (cross-signal). Strategia "poczekaj 2-5% i skopiuj" jest skazana na porazke.

---

## 5. Crypto na IB - co faktycznie oferuje?

### Co IB oferuje w krypto (stan na kwiecien 2026):

| Instrument | Dostepnosc | Uwagi |
|---|---|---|
| **CME Bitcoin Futures** | TAK | Od 2021, wymagany margin ~$50K |
| **CME Ethereum Futures** | TAK | Od 2021 |
| **Crypto SPOT (11 krypto)** | TAK (EEA od marca 2026) [^54^][^55^] | Przez Zero Hash, prowizja 0.12-0.18% |
| **Crypto CFD** | **NIE** | IB NIE oferuje crypto CFD |
| **Crypto ETF/ETN** | TAK | Dla EU dostepne jako CFD [^53^] |

### Co IB ForecastTrader oferuje w krypto:

- **"Ethereum Price"** - forecast contract (event contract, NIE CFD)
- **"Solana Price"** - forecast contract (event contract, NIE CFD)

To sa kontrakty typu "Will ETH be above $X by date Y?" - binary outcome $0/$1. To NIE sa CFD, NIE sa futures, NIE sa spot.

### Wniosek:
Projekt zaklada "symbole BTC/ETH na IB jako CME" - to jest NIEPOPRAWNE. IB ForecastTrader nie oferuje CME futures przez ForecastTrader. ForecastTrader oferuje **forecast contracts** na ceny ETH/SOL (binary $0/$1). CME futures to osobne kontrakty dostepne przez glowna platforme IB, nie przez ForecastTrader.

---

## 6. Maker/taker fees - jak wygladaja w praktyce?

### Polymarket fees (od marca 2026) [^21^][^22^][^49^]:

Wzor: **Fee = 0.05 x C x p x (1-p)**

| Cena kontraktu | Taker fee (na 100 kontraktow) | % od wartosci |
|---|---|---|
| $0.50 (50/50) | $1.25 | **2.5%** |
| $0.10 (longshot) | $0.45 | **0.9%** |
| $0.90 (near-certain) | $0.45 | **0.9%** |
| $0.01 | $0.05 | **1.0%** |

**Kategorie zroznicowane** (od kwietnia 2026):
- Crypto: rate 0.072 (max **1.8%** przy $0.50)
- Sports: rate 0.03 (max **0.75%** przy $0.50)
- Finance/Politics/Tech: rate 0.04 (max **1.0%**)
- Economics/Culture: rate 0.05 (max **1.25%**)
- Geopolitics: **0% fee**

**Maker: 0 fee + rebate 20-25% taker fees** [^18^]

### IB ForecastTrader fees [^32^][^33^]:

| Wersja | Fee |
|---|---|
| US (.com) | **$0 commission** (exchange bierze $0.01 spread YES+NO=$1.01) [^23^] |
| EU (.ie) | **$0.01 per contract** [^33^] |
| CME Event Contracts | **$0.10 per contract** [^42^] |

### Wniosek:
Projekt zaklada "2% fee na wygrane" - to jest NIEPRECYZYJNE. Polymarket ma **zmienne fees w zaleznosci od kategorii i ceny**. Przy 50/50 marketach fee to 1-1.8%, przy ekstremalnych cenach ~0.9%. Maker pay ZERO. IB bierze $0.01/contract (1% przy $1 kontrakcie, ale mniejszy % przy wiekszych).

---

## 7. Regulacje - czy Polacy moga handlowac na IB ForecastTrader?

### Dostepnosc ForecastTrader wg jurysdykcji:

| Entity | Kraje | ForecastTrader? |
|---|---|---|
| IB LLC (US) | USA | TAK (wlacznie elections dla US residents) |
| IB Ireland Limited | EU/EEA | TAK (bez elections) |
| IB Hong Kong | HK | TAK |
| IB Singapore | SG | TAK |
| IB Canada | CA | TAK |

### OGRANICZENIA dla EU retail [^30^]:

> "All Interactive Brokers Ireland Limited clients from **Belgium** are prohibited from trading forecast contracts. In addition, retail clients from **Spain, Liechtenstein and Slovenia** are prohibited from trading forecast contracts."

**POLSKA NIE JEST na liscie zabronionych krajow.**

### Limity dla retail w EU [^30^]:

> "Retail clients in eligible countries may trade up to the **lessor of 1% of their NAV or USD 1.0 million** in forecast contracts."

### Inne wymagania:
- Wiek: **21+ lat** [^32^]
- Odpowiednie trading permissions (wg IBKR)
- Polska jest wymieniona jako niedozwolona dla programu "Refer a Friend" [^57^], ale to NIE oznacza zakazu tradingu

### Wniosek:
**Polacy MOGA handlowac na IB ForecastTrader** poprzez IB Ireland Limited, pod warunkiem:
- Ukonczone 21 lat
- Limit do 1% NAV lub $1M dla retail
- Brak dostepu do kontraktow wyborczych (US only)
- Musza miec konto u IB z odpowiednimi permissions

---

## 8. Alternatywne strategie na prediction markets - co REALNIE dziala?

### Strategie, ktore maja empiryczne potwierdzenie:

#### A. Structural Arbitrage (YES+NO<$1) - ZAMKNIETA DLA RETAIL [^24^][^25^][^27^]

| Fakt | Wartosc |
|---|---|
| Zysk top 3 portfeli | $4.2M w 12 miesiecy [^25^] |
| Window czasowy | Sekundy |
| Wymagana infrastruktura | VPS w Londynie/Dublinie (<5ms) |
| Konkurencja | HFT boty |
| Dla retail? | **NIE** - "extremely competitive, dominated by high-frequency bots" [^24^] |

**WAZNE**: W shared order book Polymarket, YES+NO<$1 sie NIE pojawia, bo system automatycznie matchuje przeciwstawne zlecenia [^27^]. Arbitrage istnieje pomiedzy ROZNYMI rynkami (multi-option), nie na tym samym binarnym rynku.

#### B. Cross-Platform Arbitrage (Polymarket vs Kalshi) [^24^][^27^]

| Fakt | Wartosc |
|---|---|
| Zasada | Buy YES na A + Buy NO na B, jesli razem <$1 |
| Glowne ryzyko | Rozne definicje settlement, rozne oracle |
| Koszt czasowy | Wysoki - kapital zamrozony do settlement |
| Dostepnosc | Kalshi tylko dla US residentow |

#### C. Cross-Signal Arbitrage (Binance -> Polymarket) [^25^]

| Fakt | Wartosc |
|---|---|
| Sygnal | BTC move >0.3% w 60s |
| Window | 30-90 sekund |
| Win rate (dokumentowany) | 69.6% (23 trasy, luty 2025) |
| Profit | $11.51 z malego kapitalu |
| Latency z US | 130ms - wystarczajace |

#### D. Multi-Option Arbitrage [^27^]

- Kup wszystkie YES opcje w rynku multi-outcome jesli suma <$1
- Wymaga 30+ opcji (np. Musk tweet volume)
- "Is there such an opportunity? Yes, there is. However, it's all guarded by a large number of bots" [^27^]

#### E. News-Based Front-Running [^24^][^38^]

- Wykorzystanie streamow 5-10 sekund szybszych niz TV
- Algorytmy analizujace live streams (np. przemowienia Fed) w <10ms
- "Markets lag breaking information. Significant repricing often occurs within minutes of major announcements" [^38^]

#### F. Time Decay / Convergence [^38^]

- Kontrakty 90-95 cent konwerguja do $1 blizej settlement
- "High-probability contracts (90-95 cents) can offer consistent, lower-volatility returns" [^38^]

### Wniosek:
Wszystkie realnie dzialajace strategie arbitrage na prediction markets sa **zdominowane przez boty HFT**. Retail trader nie ma szans konkurowac w intra-market arbitrage. Jedyna realna strategia dla retail to news-based trading lub convergence edge, ale wymaga to wlasnej analizy, nie slepego kopiowania wielorybow.

---

## PODSUMOWANIE I OCENA KONCOWA

### Dlaczego projekt Polymarket-IB Bridge dostaje ocene 2/10:

| # | Problem | Waga |
|---|---|---|
| 1 | **95% rynkow Polymarket nie istnieje na IB** - brak sportu, kultury, geopolityki | Krytyczny |
| 2 | **Whale following nie daje edge** - prawdziwy win rate 50-57%, zyski z risk management | Krytyczny |
| 3 | **Latency 2-5% to smiesznie duzo** - arbitrage zamyka sie w sekundy/milisekundy | Krytyczny |
| 4 | **IB nie ma crypto CFD** - projekt zaklada cos czego nie ma | Wysoki |
| 5 | **IB ForecastTrader != CME futures** - to rozne instrumenty | Wysoki |
| 6 | **Fees Polymarket sa zmienne** - nie "2% na wygrane" | Sredni |
| 7 | **25% wolumenu to wash trading** - sygnal jest zanieczyszczony | Sredni |
| 8 | **Polacy moga handlowac** - to jedyny pozytyw | Pozytywny |
| 9 | **Zombie orders zawyzaja statystyki** - kopiuje sie pozory, nie realna strategie | Wysoki |
| 10 | **Arbitrage boty dominuja** - retail nie ma szans | Krytyczny |

### Jedyny sensowny use case (ocena 2/10, nie 1/10):

Projekt moglby miec **bardzo ograniczone zastosowanie** jako:
- Powiadomienia o ruchach wielorybow na makroekonomicznych rynkach Polymarket (Fed, CPI, S&P 500)
- Reczna egzekucja podobnych tradow na IB ForecastTrader
- ALE: tylko dla ~5% rynkow, bez gwarancji edge, z duzym opoznieniem

### Werdykt:
**Projekt jest oparty na blednych zalozeniach:**
1. Nie rozumie czym jest IB ForecastTrader (nie CFD, nie sport, nie geopolityka)
2. Nie rozumie ze whale following to strategia hedgingowa, nie kierunkowa
3. Nie rozumie ze latency arbitrage w prediction markets to gra HFT botow
4. Nie rozumie struktury fees na Polymarket
5. Nie uwzglednia ze 95% rynkow Polymarket nie ma odpowiednika na IB

---

## ZRODLA

[^15^] The Block Beats - "Dissecting Polymarket's Top 10 Whales' 27000 Transactions" (2026)
[^16^] Odaily - "Behind 27,000 Transactions: The Survival Algorithm of Polymarket Whales" (2026)
[^17^] Casino.org - "84% of Polymarket Traders Aren't Profitable" (kwiecien 2026)
[^18^] MEXC News - "Polymarket Just Changed Its Fees" (kwiecien 2026)
[^19^] Sigma World - "Polymarket data shows majority of traders lose money" (kwiecien 2026)
[^20^] TechFlow - "Polymarket 84% traders losing money" (kwiecien 2026)
[^21^] Polymarket Docs - "Fee Schedule" (oficjalna dokumentacja)
[^22^] Polymarket US DCM - "Trading Fee Schedule" (oficjalna)
[^23^] GoodMoneyGuide - "What's it like trading event contracts on Interactive Brokers?" (luty 2026)
[^24^] RootData - "Hidden Profits: Arbitrage Battle in Prediction Markets" (luty 2026)
[^25^] TradoxVPS - "How to Set Up a Polymarket Bot on a VPS" (kwiecien 2026)
[^27^] KuCoin - "Explaining Polymarket: Why YES + NO Must Equal 1" (2026)
[^30^] IBKR ForecastTrader IE - oficjalna strona (.ie) z disclosures
[^32^] IBKR ForecastTrader US - oficjalna strona (.com) z disclosures
[^33^] IBKR ForecastTrader IE Learn - oficjalna strona z fees
[^35^] NYC Servers - "Polymarket Server Locations & Latency Guide" (kwiecien 2026)
[^37^] BrokerChooser - "ForecastTrader by Interactive Brokers: Step-by-Step Guide" (2025)
[^38^] MEXC Learn - "Prediction Market Trading Strategies" (kwiecien 2026)
[^42^] Finder - "8 Top Prediction Markets to Trade Event Contracts" (luty 2026)
[^43^] Polymarket.com/predictions - oficjalna lista kategorii
[^44^] Medium/Academic - "Combining Simulation and ML Analysis of Whale Trading on Hyperliquid" (2025)
[^48^] Intercom Help - "Polymarket sign up guide 2026" (2026)
[^49^] Medium - "Polymarket Fees Explained" (kwiecien 2026)
[^51^] BrokerChooser - "Interactive Brokers CFD Trading Conditions" (2026)
[^53^] IB UK - "Trade Contract for Difference (CFDs)"
[^54^] FX News Group - "IB launches crypto trading for EEA" (marzec 2026)
[^59^] IBKR Campus - "Prediction Markets at Interactive Brokers" (kwiecien 2026)
[^60^] IBKR Traders' Insight - "Prediction Markets 101" (marzec 2026)
[^62^] Yahoo Finance/Columbia - "25% of Polymarket trades are inflated" (listopad 2025)
[^63^] Fortune - "Polymarket volume inflated by artificial activity" (listopad 2025)
