# AUDYT KODU - Polymarket-IB Bridge

**Data audytu:** 2025-01-25
**Audytor:** Senior Python Developer / Trading Systems Architect
**Zakres:** Wszystkie pliki w src/ i scripts/
**Metodologia:** Statyczna analiza kodu + weryfikacja importow/metod/pol

---

## PODSUMOWANIE

| Kategoria | Liczba |
|---|---|
| Bledy KRYTYCZNE | 11 |
| Bledy WAZNE | 21 |
| Bledy BEZPIECZENSTWA | 2 |
| Zalozenia nieprawdziwe | 2 |
| Brak implementacji | 5 |
| Bledy lekkie | 8 |
| **RAZEM** | **49** |

**Werdykt:** Projekt NIE JEST uruchomialny. 11 bledow krytycznych (w tym brak __init__.py we wszystkich pakietach, nieistniejace klasy/metody w importach) uniemozliwia uruchomienie. Dodatkowo co najmniej 5 stubow nie ma implementacji.

---

## BLEDY KRYTYCZNE (11)

### 1. Brak __init__.py we wszystkich pakietach
- **PLIK:** Wszystkie pakiety (src/, src/api/, src/correlation/, src/discovery/, src/execution/, src/notifications/, src/risk/)
- **LINIA:** -
- **TYP:** blad_krytyczny
- **OPIS:** Brak plikow __init__.py we wszystkich 8 pakietach. Importy pakietow w Pythonie (np. `from src.discovery.whale_detector import WhaleDetector`) absolutnie nie zadzialaja bez nich. Projekt jest calkowicie nieuruchomialny.
- **PROPOZYCJA:** Utworzyc puste pliki __init__.py w kazdym katalogu pakietu.

### 2. Nieistniejaca klasa LiveTradingEngine w imporcie
- **PLIK:** scripts/live_trader.py
- **LINIA:** 29
- **TYP:** blad_krytyczny
- **OPIS:** Importuje `LiveTradingEngine` z `src.execution.live_trading`, ale w tym module klasa nazywa sie `LiveExecutionEngine`. Dodatkowo importuje `OrderSide` ktory nie istnieje w `live_trading.py` (tam jest `LiveOrderStatus`, nie `OrderSide`). Skrypt sie wysypie na imporcie w trybie live.
- **PROPOZYCJA:** Zmienic na: `from src.execution.live_trading import LiveExecutionEngine`. Usunac `OrderSide` z importu.

### 3. Wywolanie nieistniejacej klasy LiveTradingEngine
- **PLIK:** scripts/live_trader.py
- **LINIA:** 94
- **TYP:** blad_krytyczny
- **OPIS:** `self.execution_engine = LiveTradingEngine()` - klasa nie istnieje. Prawidlowa nazwa to `LiveExecutionEngine`. Kod w trybie live (`--live`) w ogole sie nie uruchomi.
- **PROPOZYCJA:** Zmienic na `self.execution_engine = LiveExecutionEngine()`

### 4. Nieistniejaca klasa MarketCorrelation i metoda correlate_single
- **PLIK:** scripts/paper_trader.py
- **LINIA:** 173-175
- **TYP:** blad_krytyczny
- **OPIS:** Importuje `MarketCorrelation` (nie istnieje - jest `CorrelationResult`) oraz wywoluje `self.correlation_engine.correlate_single()` (nie istnieje - sa `find_correlation` i `batch_correlate`). Skrypt sie wysypie przy pierwszym sygnale.
- **PROPOZYCJA:** Zmienic import na: `from src.correlation.engine import CorrelationResult`. Zmienic wywolanie na: `corr = self.correlation_engine.find_correlation(market, ib_contracts)`

### 5. Nieistniejaca metoda correlate_single w live_trader.py
- **PLIK:** scripts/live_trader.py
- **LINIA:** 212
- **TYP:** blad_krytyczny
- **OPIS:** Wywolanie `self.correlation_engine.correlate_single(market, ib_contracts)` - metoda nie istnieje w `CorrelationEngine`. Jest `find_correlation()` i `batch_correlate()`.
- **PROPOZYCJA:** Zmienic na: `corr = self.correlation_engine.find_correlation(market, ib_contracts)`

### 6. Nieistniejaca metoda can_open_position w RiskManager (paper_trader)
- **PLIK:** scripts/paper_trader.py
- **LINIA:** 198
- **TYP:** blad_krytyczny
- **OPIS:** `self.risk_manager.can_open_position(estimated_ib_price * 100)` - metoda `can_open_position()` nie istnieje w `RiskManager`. `RiskManager` ma tylko `check_all(position_size)`. Skrypt sie wysypie.
- **PROPOZYCJA:** Zmienic na: `risk = self.risk_manager.check_all(estimated_ib_price * 100); if not risk.can_trade: ...`

### 7. Nieistniejaca metoda can_open_position w RiskManager (live_trader)
- **PLIK:** scripts/live_trader.py
- **LINIA:** 258
- **TYP:** blad_krytyczny
- **OPIS:** To samo co wyzej - `self.risk_manager.can_open_position(rec.ib_suggested_price * 100)` - ta sama nieistniejaca metoda.
- **PROPOZYCJA:** Uzyc `self.risk_manager.check_all(position_size)` i sprawdzic `.can_trade`

### 8. Nieistniejace pole filled_quantity w PaperOrder
- **PLIK:** scripts/paper_trader.py
- **LINIA:** 218
- **TYP:** blad_krytyczny
- **OPIS:** `order.filled_quantity` - pole nie istnieje w `PaperOrder` (dataclass). Jest pole `quantity`. Skrypt sie wysypie przy `AttributeError`.
- **PROPOZYCJA:** Zmienic na `order.quantity`

### 9. Nieistniejace pole fee_paid w PaperOrder
- **PLIK:** scripts/paper_trader.py
- **LINIA:** 219
- **TYP:** blad_krytyczny
- **OPIS:** `order.fee_paid` - pole nie istnieje w `PaperOrder`. Nie ma takiego pola w dataclass. Skrypt sie wysypie.
- **PROPOZYCJA:** Dodac pole `fee_paid` do `PaperOrder` lub usunac logowanie oplaty.

### 10. Nieistniejace pole filled_quantity w LiveOrder
- **PLIK:** scripts/live_trader.py
- **LINIA:** 280-282
- **TYP:** blad_krytyczny
- **OPIS:** `order.filled_quantity` - pole nie istnieje w `LiveOrder`. Jest pole `quantity`. Skrypt sie wysypie.
- **PROPOZYCJA:** Zmienic na `order.quantity`

### 11. Nieistniejaca metoda send_message w TelegramNotifier
- **PLIK:** scripts/live_trader.py
- **LINIA:** 285-290
- **TYP:** blad_krytyczny
- **OPIS:** `self.notifier.telegram.send_message(...)` - metoda `send_message()` nie istnieje w `TelegramNotifier`. Sa: `send_recommendation()`, `send_summary()`, `send_error()`. Skrypt sie wysypie przy wywolaniu.
- **PROPOZYCJA:** Uzyc `send_recommendation()` z odpowiednim `TradeRecommendation`, lub dodac metode `send_message()` do `TelegramNotifier`.

---

## BLEDY WAZNE (21)

### 12. Błąd logiczny - volume spike nigdy nie wykryty przy pierwszym checku
- **PLIK:** src/discovery/whale_detector.py
- **LINIA:** 316-325
- **TYP:** blad_wazny
- **OPIS:** W `PublicAPIWhaleMonitor._analyze_market()`: najpierw zapisuje `self.previous_volumes[slug] = current_volume`, a POTEM sprawdza `if slug not in self.previous_volumes`. Ten warunek NIGDY nie przejdzie, bo slug został zapisany 5 linii wyżej. Pierwszy volume spike nigdy nie zostanie wykryty (zawsze delta = 0).
- **PROPOZYCJA:** Przeniesc sprawdzenie `if slug not in self.previous_volumes` PRZED zapisaniem `self.previous_volumes[slug] = current_volume`.

### 13. Nieuzasadnione importy z ib_insync w module Polymarket
- **PLIK:** src/discovery/polymarket_discovery.py
- **LINIA:** 13
- **TYP:** blad_wazny
- **OPIS:** Niepotrzebne importy `IB`, `Contract`, `ContractDetails` z `ib_insync`. Ten plik to klient API Polymarket - nie powinien zależeć od biblioteki IB. Jesli ib_insync nie jest zainstalowany, import sie wysypie mimo ze nie jest uzywany.
- **PROPOZYCJA:** Usunac linie: `from ib_insync import IB, Contract, ContractDetails`

### 14. Nieuzasadniony import numpy
- **PLIK:** src/correlation/engine.py
- **LINIA:** 16
- **TYP:** blad_wazny
- **OPIS:** `import numpy as np` nigdzie nie jest używany w module. Niepotrzebna zależność.
- **PROPOZYCJA:** Usunac import numpy.

### 15. Nieuzasadniony import Decimal
- **PLIK:** src/discovery/whale_tracker.py
- **LINIA:** 14
- **TYP:** blad_wazny
- **OPIS:** `from decimal import Decimal` - importowany ale nigdy nie używany.
- **PROPOZYCJA:** Usunac nieużywany import.

### 16. Niepoprawny type hint callable
- **PLIK:** src/discovery/whale_tracker.py
- **LINIA:** 116
- **TYP:** blad_wazny
- **OPIS:** `self.on_signal: Optional[callable] = None` - `callable` jako typ nie jest poprawny w standardzie type hints (przed Python 3.9 to blad). Powinno być `Optional[Callable[...]]` z `typing`.
- **PROPOZYCJA:** Zmienic na: `from typing import Callable; self.on_signal: Optional[Callable] = None`

### 17. Nieprawidłowy secType dla kontraktów krypto
- **PLIK:** src/discovery/ib_discovery.py
- **LINIA:** 128-133
- **TYP:** blad_wazny
- **OPIS:** Tworzy Contract bazowy z `secType='IND'` dla wszystkich symboli (w tym BTC, ETH). Dla kryptowalut powinno być `CRYPTO` lub `CMDTY`, a nie `IND`. Nieprawidłowy secType spowoduje ze IB nie znajdzie kontraktów krypto.
- **PROPOZYCJA:** Używać różnych secType w zależności od symbolu: `IND` dla ekonomicznych/finansowych, `CRYPTO` dla BTC/ETH.

### 18. Brak obsługi None w commissionReport
- **PLIK:** src/execution/live_trading.py
- **LINIA:** 197
- **TYP:** blad_wazny
- **OPIS:** `fill.commissionReport.commission` - `commissionReport` może być None (IB nie zawsze wysyła commissionReport natychmiast). Odniesienie do `.commission` rzuci `AttributeError` jesli `commissionReport` jest None.
- **PROPOZYCJA:** Zmienic na: `getattr(fill.commissionReport, 'commission', None) if fill and fill.commissionReport else None`

### 19. BRAK graceful reconnect w connect()
- **PLIK:** src/execution/live_trading.py
- **LINIA:** 76-88
- **TYP:** blad_wazny
- **OPIS:** `connect()` - jesli polaczenie sie nie powiedzie, wyjatek jest rzucony ponownie. Brak obslugi ponownego laczenia (retry logic). W systemie 24/7 tymczasowa przerwa w polaczeniu z IB powinna byc obslugiwana automatycznie.
- **PROPOZYCJA:** Dodac retry logic z exponential backoff w connect().

### 20. Niepoprawna obsługa pozycji short i overage w paper trading
- **PLIK:** src/execution/paper_trading.py
- **LINIA:** 262-273
- **TYP:** blad_wazny
- **OPIS:** W `_update_position` dla SELL: `realized_pnl = (order.filled_price - current_avg) * order.quantity` oblicza PnL zawsze dla `order.quantity` kontraktów, ale powinno tylko dla zamykanej czesci (`min(order.quantity, current_qty)`). Gdy `new_qty < 0` (overage, np. mamy 5, sprzedajemy 10), zamykamy calosc z blednym PnL i nie otwieramy short.
- **PROPOZYCJA:** Poprawic logike: obliczac PnL tylko dla zamykanej czesci pozycji. Obsluzyc overage (otworzyc short lub odrzucic).

### 21. Synchroniczne endpointy blokujace event loop FastAPI
- **PLIK:** src/api/server.py
- **LINIA:** 108-137 (i wszystkie endpointy)
- **TYP:** blad_wazny
- **OPIS:** Endpointy HTTP sa synchroniczne i blokują na SQLite. Przy wolniejszym zapytaniu SQL zablokuja event loop FastAPI, opozniajac inne zapytania.
- **PROPOZYCJA:** Uzyc `aiosqlite` lub `asyncpg` dla async DB access. Dodac try/finally aby zamykać polaczenia.

### 22. Hacky import datetime + brak obslugi None
- **PLIK:** src/api/server.py
- **LINIA:** 242
- **TYP:** blad_wazny
- **OPIS:** Uzycie `__import__('datetime').datetime.now()` wewnątrz funkcji - jest to hacky sposob na unikniecie importu na gorze pliku.
- **PROPOZYCJA:** Dodac normalny `import datetime` na gorze pliku.

### 23. ValueError przy pustej zmiennej srodowiskowej SMTP_PORT
- **PLIK:** src/notifications/manager.py
- **LINIA:** 252
- **TYP:** blad_wazny
- **OPIS:** `int(os.getenv('SMTP_PORT', '587'))` - jesli zmienna srodowiskowa `SMTP_PORT` istnieje ale jest pusta (np. `SMTP_PORT=`), `int('')` rzuci `ValueError` przy inicjalizacji.
- **PROPOZYCJA:** Zmienic na: `int(os.getenv('SMTP_PORT') or '587')`

### 24. To samo dla RATE_LIMIT_MSG_PER_SEC
- **PLIK:** src/risk/manager.py
- **LINIA:** 52
- **TYP:** blad_wazny
- **OPIS:** `int(os.getenv('RATE_LIMIT_MSG_PER_SEC', '10'))` - pusta zmienna srodowiskowa spowoduje `ValueError`.
- **PROPOZYCJA:** Zmienic na: `int(os.getenv('RATE_LIMIT_MSG_PER_SEC') or '10')`

### 25. Deprecated datetime.utcnow()
- **PLIK:** src/discovery/whale_detector.py
- **LINIA:** 148
- **TYP:** blad_wazny
- **OPIS:** Uzycie `datetime.utcnow()` - jest deprecated w Python 3.12+ (PEP 2567). Moze przestac dzialac w przyszlych wersjach Pythona.
- **PROPOZYCJA:** Zmienic na: `datetime.now(timezone.utc)` lub `datetime.now(UTC)`

### 26. Absolutny import zamiast wzglednego
- **PLIK:** src/discovery/whale_tracker.py
- **LINIA:** 459
- **TYP:** blad_wazny
- **OPIS:** `from src.notifications.manager import TradeRecommendation` - uzywa absolutnego importu `src.notifications.manager`. Ten import zadziala tylko gdy root projektu jest w PYTHONPATH. Przy uruchomieniu jako modul moze sie wysypac.
- **PROPOZYCJA:** Uzyc wzglednego importu: `from ...notifications.manager import TradeRecommendation`

### 27. Timeout 10s na fill zlecenia - niewystarczajacy
- **PLIK:** src/execution/live_trading.py
- **LINIA:** 97-221
- **TYP:** blad_wazny
- **OPIS:** `place_order` czeka tylko 10 sekund na fill (`asyncio.wait_for(timeout=10.0)`). Dla Event Contracts fill moze zajac duzo dluzej lub nigdy nie nastapic (limit order). Po timeout zlecenie pozostaje otwarte na IB ale funkcja zwraca blad.
- **PROPOZYCJA:** Nie czekac na fill synchronicznie. Uzyc callbackow (`orderStatusEvent`) lub zwracac od razu ze statusem PENDING.

### 28. Nieskonczona petla bez graceful shutdown
- **PLIK:** src/discovery/whale_tracker.py
- **LINIA:** 269-279
- **TYP:** blad_wazny
- **OPIS:** `start_monitoring` - nieskonczona petla `while True` bez mechanizmu graceful shutdown. Przy `KeyboardInterrupt` nie zamknie WebSocket czysto.
- **PROPOZYCJA:** Dodac obsluge `asyncio.Event` do zatrzymywania petli.

### 29. Wyciek sesji aiohttp
- **PLIK:** src/discovery/polymarket_discovery.py
- **LINIA:** 179-196
- **TYP:** blad_wazny
- **OPIS:** `get_market_by_slug` - tworzy nowa sesje aiohttp jesli `self.session` jest None, ale nigdy jej nie zamyka. Przy wielokrotnym wywolaniu tworzy wycieki sesji.
- **PROPOZYCJA:** Nie tworzyc nowej sesji - wymusic uzycie w kontekscie `async with`.

### 30. Kumulowanie callbackow orderStatusEvent
- **PLIK:** src/execution/live_trading.py
- **LINIA:** 84
- **TYP:** blad_wazny
- **OPIS:** Subskrypcja `self.ib.orderStatusEvent += self._on_order_status` - nigdy nie jest odsubskrybowana w `disconnect()`. Przy wielokrotnym connect/disconnect callbacki sie kumuluja, powodujac wielokrotne logowanie tego samego zdarzenia.
- **PROPOZYCJA:** W `disconnect()` dodac: `self.ib.orderStatusEvent -= self._on_order_status`

### 31. Nieaktualizowanie realized_pnl w dziennych statystykach
- **PLIK:** src/execution/paper_trading.py
- **LINIA:** 299-312
- **TYP:** blad_wazny
- **OPIS:** `_update_daily_stats` nie aktualizuje `realized_pnl` przy zamykaniu pozycji. Tylko `volume_traded` i `trades_count` sa inkrementowane. `realized_pnl` pozostaje zawsze 0.
- **PROPOZYCJA:** Przekazywac `realized_pnl` z `_update_position` do `_update_daily_stats` i dodawac do bazy.

### 32. Tworzenie nowej instancji RiskManager w kazdym endpoincie
- **PLIK:** src/api/server.py
- **LINIA:** 264-267
- **TYP:** blad_wazny
- **OPIS:** Tworzenie nowej instancji `RiskManager` w kazdym endpoincie (`/risk/status`, `/risk/kill-switch`). Powoduje utrate stanu in-memory (msg_times, error_count) miedzy wywolaniami.
- **PROPOZYCJA:** Uzyc singletona lub dependency injection w FastAPI (Depends).

---

## BLEDY BEZPIECZENSTWA (2)

### 33. CORS allow_origins=['*'] w produkcji
- **PLIK:** src/api/server.py
- **LINIA:** 89
- **TYP:** blad_bezpieczenstwa
- **OPIS:** `allow_origins=["*"]` pozwala kazdej domenie na dostep do API. W polaczeniu z brakiem autentykacji to otwiera mozliwosc CSRF/Clickjacking atakow.
- **PROPOZYCJA:** Przeniesc do konfiguracji: `allow_origins=os.getenv('ALLOWED_ORIGINS', 'http://localhost').split(',')`

### 34. Brak autentykacji na endpointach kill-switch
- **PLIK:** src/api/server.py
- **LINIA:** 270-287
- **TYP:** blad_bezpieczenstwa
- **OPIS:** Endpointy `/risk/kill-switch` (POST i DELETE) nie wymagaja ZADNEJ autentykacji. Kazdy kto zna URL moze aktywowac/dezaktywowac kill switch, calkowicie zatrzymujac trading.
- **PROPOZYCJA:** Dodac API key auth (np. `X-API-Key` header) lub Bearer token do endpointow kill-switch.

---

## ZALOZENIA NIEPRAWDZIWIE (2)

### 35. Uproszczone wnioskowanie kierunku transakcji
- **PLIK:** src/discovery/whale_detector.py
- **LINIA:** 353
- **TYP:** zalozenie_nieprawdziwe
- **OPIS:** Jesli cena spadnie o >1% zaklada `BUY_NO`. Ale cena moze spasc z innych powodow (np. ktos sprzedaje YES = `SELL_YES`). Zawsze przypisywanie `BUY_YES/BUY_NO` jest uproszczeniem prowadzacym do blednych sygnalow.
- **PROPOZYCJA:** Oznaczyc jako niska pewnosc lub dodac wiecej heurystyk.

### 36. Uproszczony model slippage (0-2%)
- **PLIK:** src/execution/paper_trading.py
- **LINIA:** 180-206
- **TYP:** zalozenie_nieprawdziwe
- **OPIS:** `slippage = random.uniform(0, 0.02)` - zaklada maksymalnie 2% slippage. Dla Event Contracts na FORECASTX rzeczywisty slippage moze byc duzo wiekszy (brak plynnosci, szerokie spready). Symulacja jest zbyt optymistyczna.
- **PROPOZYCJA:** Dodac konfigurowalny max_slippage lub bazowac na historycznym slippage per kontrakt.

---

## BRAK IMPLEMENTACJI (5)

### 37. Stub get_whale_activity
- **PLIK:** src/discovery/polymarket_discovery.py
- **LINIA:** 198-211
- **TYP:** brak_implementacji
- **OPIS:** `get_whale_activity` zwraca pusta liste `[]` z komentarzem "stub". Funkcjonalnosc sledzenia wielorybow przez blockchain nie jest zaimplementowana.
- **PROPOZYCJA:** Zaimplementowac uzywajac CLOB API lub zintegrowac z `WhaleDetector`.

### 38. Stub _process_transaction
- **PLIK:** src/discovery/whale_tracker.py
- **LINIA:** 295-309
- **TYP:** brak_implementacji
- **OPIS:** `_process_transaction` konczy sie na `# TODO: Implementacja dekodowania ERC-1155`. Brak faktycznej implementacji przetwarzania transakcji blockchain.
- **PROPOZYCJA:** Zaimplementowac dekodowanie ERC-1155 lub uzyc web3.py.

### 39. Stub BlockchainWhaleMonitor.get_large_trades
- **PLIK:** src/discovery/whale_detector.py
- **LINIA:** 418-438
- **TYP:** brak_implementacji
- **OPIS:** `BlockchainWhaleMonitor.get_large_trades` zwraca `[]` ze stub comment. Brak integracji z blockchain.
- **PROPOZYCJA:** Zaimplementowac za pomoca web3.py + event logs lub subgraph API.

### 40. Stub EmailNotifier
- **PLIK:** src/notifications/manager.py
- **LINIA:** 261-275
- **TYP:** brak_implementacji
- **OPIS:** `EmailNotifier` - wszystkie metody to tylko `logger.info()` stub. Brak faktycznej implementacji wysylki email przez SMTP.
- **PROPOZYCJA:** Zaimplementowac wysylke przez `aiosmtplib`.

### 41. Brak implementacji embedding similarity
- **PLIK:** src/correlation/engine.py
- **LINIA:** 2-8
- **TYP:** brak_implementacji
- **OPIS:** W komentarzu wspomniane sa 4 strategie (fuzzy, keyword, embedding, manual), ale implementacja `embedding similarity` (sentence-transformers) jest w ogole niezaimplementowana.
- **PROPOZYCJA:** Dodac metode `_embedding_match()` lub usunac z dokumentacji.

---

## BLEDY LEKKIE (8)

### 42. Redundantny warunek w _log_status
- **PLIK:** scripts/live_trader.py
- **LINIA:** 304-317
- **TYP:** blad_lekki
- **OPIS:** `if int(hours) > 0 and int(hours) % 1 == 0` - `int(hours) % 1 == 0` jest zawsze True dla int. Warunek jest redundantny.
- **PROPOZYCJA:** Uproscic lub uzyc flagi co godzine.

### 43. next() bez default wartosci
- **PLIK:** src/correlation/engine.py
- **LINIA:** 264
- **TYP:** blad_lekki
- **OPIS:** `next(c for c, n in ib_names if n == matched_name)` - moze rzucic `StopIteration` jesli nie znajdzie pasujacej nazwy.
- **PROPOZYCJA:** Zmienic na: `next((c for c, n in ib_names if n == matched_name), None)`

### 44. Brak warningu dla nieznanych kombinacji side/outcome
- **PLIK:** src/discovery/whale_detector.py
- **LINIA:** 190
- **TYP:** blad_lekki
- **OPIS:** Ostatni `else` zawsze przypisuje `SELL_NO`. Jesli API zwroci nieznany side/outcome, tez przypisze `SELL_NO` bez ostrzezenia.
- **PROPOZYCJA:** Dodac logowanie `warning` dla nieznanych kombinacji.

### 45. refresh_prices nie obsluguje braku odpowiedzi od IB
- **PLIK:** src/discovery/ib_discovery.py
- **LINIA:** 220
- **TYP:** blad_lekki
- **OPIS:** `refresh_prices` nie sprawdza timeoutu. Jesli IB nie odpowie, `ticker.bid`/`ticker.ask` pozostaną None.
- **PROPOZYCJA:** Sprawdzac czy ticker.bid/ticker.ask sa None i oznaczac jako brak danych.

### 46. Redundantne tworzenie action
- **PLIK:** src/execution/live_trading.py
- **LINIA:** 146
- **TYP:** blad_lekki
- **OPIS:** `action = 'BUY' if side == 'BUY' else 'SELL'` - calkowicie redundantne. `side` juz jest 'BUY' lub 'SELL'.
- **PROPOZYCJA:** Uzyc `action=side` bezposrednio.

### 47. Niestabilne dopasowanie w reset_kill_switch
- **PLIK:** src/risk/manager.py
- **LINIA:** 171-181
- **TYP:** blad_lekki
- **OPIS:** `LIKE '%Kill switch: {reason}%'` - reason zawiera timestamp, wiec dopasowanie moze byc niestabilne.
- **PROPOZYCJA:** Uzyc ID lub dokladniejszego dopasowania.

### 48. Niezgodnosc nazw argumentow
- **PLIK:** scripts/live_trader.py
- **LINIA:** 356
- **TYP:** blad_lekki
- **OPIS:** `min_confidence=args.min_confidence` przekazywany do `min_signal_confidence`. Dziala przez keyword ale jest mylace.
- **PROPOZYCJA:** Uzyc spojnego nazewnictwa.

### 49. Redundantny import datetime
- **PLIK:** src/notifications/manager.py
- **LINIA:** 70
- **TYP:** blad_lekki
- **OPIS:** `from datetime import datetime` wewnątrz metody `_timestamp()` mimo ze `datetime` jest juz zaimportowany na gorze pliku (linia 8).
- **PROPOZYCJA:** Usunac redundantny import.

---

## REKOMENDACJE PRIORYTETOWE

### Do natychmiastowej naprawy (blokujace uruchomienie):
1. Dodac `__init__.py` do wszystkich pakietow
2. Naprawic nazwy klas/metod w importach (LiveTradingEngine->LiveExecutionEngine, MarketCorrelation->CorrelationResult, correlate_single->find_correlation)
3. Zastapic wywolania `can_open_position()` na `check_all()`
4. Usunac odwolania do nieistniejacych pol (`filled_quantity`, `fee_paid`)
5. Dodac metode `send_message()` do TelegramNotifier lub zmienic wywolanie

### Do naprawy w kolejnym sprincie:
6. Poprawic blad logiczny w `_analyze_market` (kolejnosc zapisu/sprawdzenia previous_volumes)
7. Dodac autentykacje do endpointow kill-switch
8. Zmienic CORS z `*` na konkretne domeny
9. Usunac nieuzywane importy (numpy, Decimal, ib_insync z polymarket)
10. Zaimplementowac brakujace stuby (email, blockchain, ERC-1155 decoding)
11. Poprawic obsluge pozycji w paper trading (short, overage, realized_pnl)
12. Dodac graceful shutdown do petli WebSocket

### Do rozwazenia:
13. Przejsc na async SQLite (aiosqlite) w API
14. Dodac retry logic do polaczenia z IB
15. Uzyc singletona dla RiskManager w API
16. Poprawic model slippage (nie tylko random 0-2%)
