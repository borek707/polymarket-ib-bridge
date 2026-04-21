"""
Risk Management Layer - circuit breakers, rate limiting, kill switches.

Chroni przed:
- Zbyt agresywnym tradingiem (rate limits)
- Kaskadowymi błędami (circuit breaker)
- Utracą więcej niż X% kapitału (daily stop loss)
- Błędnymi decyzjami (cooldown po stratach)
"""

import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional


class RiskLevel(Enum):
    GREEN = "green"      # Wszystko OK
    YELLOW = "yellow"    # Ostrzeżenie (np. zbliżamy się do limitu)
    RED = "red"          # STOP - nie wykonuj nowych zleceń


@dataclass
class RiskCheck:
    """Wynik sprawdzenia ryzyka."""
    level: RiskLevel
    reason: str
    can_trade: bool


class RiskManager:
    """
    Zarządzanie ryzykiem dla trading bot.
    
    Konfiguracja via env vars:
    - MAX_DAILY_LOSS_USD: Max strata dziennia (default: 100)
    - MAX_POSITION_SIZE_USD: Max wielkość pozycji (default: 50)
    - CIRCUIT_BREAKER_ERRORS: Ile błędów przed stop (default: 5)
    - RATE_LIMIT_MSG_PER_SEC: Max wiadomości do IB (default: 10)
    """
    
    def __init__(self, db_path: str = 'data/bridge.db'):
        self.db_path = db_path
        
        # Konfiguracja z env lub default
        self.max_daily_loss = float(os.getenv('MAX_DAILY_LOSS_USD', 100))
        self.max_position_size = float(os.getenv('MAX_POSITION_SIZE_USD', 50))
        self.circuit_breaker_threshold = int(os.getenv('CIRCUIT_BREAKER_ERRORS', 5))
        self.rate_limit = int(os.getenv('RATE_LIMIT_MSG_PER_SEC') or '10')
        
        # Kill switch file
        self.kill_switch_file = Path('data/KILL_SWITCH')
        
        # Rate limiting state
        self.msg_times = []  # Timestampy ostatnich wiadomości
        
        # Error tracking
        self.error_count = 0
        self.last_error_time = None
        
        self._init_db()
        
    def _init_db(self):
        """Inicjalizuje tabele dla risk management."""
        with sqlite3.connect(self.db_path) as conn:
            # PnL tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS daily_pnl (
                    date TEXT PRIMARY KEY,
                    realized_pnl REAL DEFAULT 0,
                    unrealized_pnl REAL DEFAULT 0,
                    trades_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Error log
            conn.execute('''
                CREATE TABLE IF NOT EXISTS error_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_type TEXT,
                    error_message TEXT,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Circuit breaker log
            conn.execute('''
                CREATE TABLE IF NOT EXISTS circuit_breaker_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reason TEXT,
                    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reset_at TIMESTAMP
                )
            ''')
            
    def check_all(self, position_size: float = 0) -> RiskCheck:
        """
        Kompleksowe sprawdzenie ryzyka przed zleceniem.
        
        Zwraca RiskCheck z decyzją czy można handlować.
        """
        # 1. Kill switch (najwyższy priorytet)
        if self.kill_switch_file.exists():
            return RiskCheck(
                level=RiskLevel.RED,
                reason=f"Kill switch active: {self.kill_switch_file.read_text()}",
                can_trade=False
            )
        
        # 2. Daily loss limit
        daily_pnl = self.get_daily_pnl()
        if daily_pnl <= -self.max_daily_loss:
            return RiskCheck(
                level=RiskLevel.RED,
                reason=f"Daily loss limit hit: ${daily_pnl:.2f} (limit: -${self.max_daily_loss})",
                can_trade=False
            )
        
        # 3. Circuit breaker (kaskadowe błędy)
        if self.error_count >= self.circuit_breaker_threshold:
            return RiskCheck(
                level=RiskLevel.RED,
                reason=f"Circuit breaker active: {self.error_count} errors",
                can_trade=False
            )
        
        # 4. Position size
        if position_size > self.max_position_size:
            return RiskCheck(
                level=RiskLevel.RED,
                reason=f"Position size {position_size} > max {self.max_position_size}",
                can_trade=False
            )
        
        # 5. Yellow warning (zbliżamy się do limitu)
        if daily_pnl <= -self.max_daily_loss * 0.7:
            return RiskCheck(
                level=RiskLevel.YELLOW,
                reason=f"Approaching daily loss limit: ${daily_pnl:.2f}",
                can_trade=True  # Jeszcze można, ale ostrożnie
            )
        
        return RiskCheck(
            level=RiskLevel.GREEN,
            reason="All risk checks passed",
            can_trade=True
        )
    
    def trigger_kill_switch(self, reason: str):
        """Aktywuje kill switch - natychmiastowy stop wszystkiego."""
        self.kill_switch_file.parent.mkdir(parents=True, exist_ok=True)
        self.kill_switch_file.write_text(f"{datetime.now()}: {reason}")
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO circuit_breaker_events (reason)
                VALUES (?)
            ''', (f"Kill switch: {reason}",))
            conn.commit()
            
        print(f"🚨 KILL SWITCH ACTIVATED: {reason}")
        
    def reset_kill_switch(self):
        """Deaktywuje kill switch."""
        if self.kill_switch_file.exists():
            reason = self.kill_switch_file.read_text()
            self.kill_switch_file.unlink()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    UPDATE circuit_breaker_events 
                    SET reset_at = CURRENT_TIMESTAMP
                    WHERE reason LIKE ? AND reset_at IS NULL
                ''', (f"%Kill switch: {reason}%",))
                conn.commit()
                
            print(f"✅ Kill switch reset")
            
    def check_rate_limit(self) -> bool:
        """
        Sprawdza czy nie przekraczamy rate limitu do IB.
        
        Zwraca True jeśli można wysłać wiadomość.
        """
        now = time.time()
        
        # Usuń stare timestampy (poza oknem 1 sekundy)
        cutoff = now - 1.0
        self.msg_times = [t for t in self.msg_times if t > cutoff]
        
        # Sprawdź limit
        if len(self.msg_times) >= self.rate_limit:
            return False
            
        # Dodaj nowy timestamp
        self.msg_times.append(now)
        return True
        
    def wait_for_rate_limit(self):
        """Czeka aż będzie miejsce w rate limit."""
        while not self.check_rate_limit():
            time.sleep(0.1)
            
    def log_error(self, error_type: str, message: str, context: str = ""):
        """Loguje błąd i sprawdza circuit breaker."""
        now = datetime.now()
        
        # Resetuj counter jeśli ostatni błąd był > 5 min temu
        if self.last_error_time and (now - self.last_error_time) > timedelta(minutes=5):
            self.error_count = 0
            
        self.error_count += 1
        self.last_error_time = now
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO error_log (error_type, error_message, context)
                VALUES (?, ?, ?)
            ''', (error_type, message, context))
            conn.commit()
            
        print(f"⚠️ Error logged ({self.error_count}/{self.circuit_breaker_threshold}): {message}")
        
        # Sprawdź czy circuit breaker powinien się aktywować
        if self.error_count >= self.circuit_breaker_threshold:
            self.trigger_kill_switch(f"Circuit breaker: {self.error_count} errors in 5min")
            
    def record_trade_pnl(self, realized_pnl: float = 0, unrealized_pnl: float = 0):
        """Rejestruje PnL z trade'u."""
        today = datetime.now().strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO daily_pnl (date, realized_pnl, unrealized_pnl, trades_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(date) DO UPDATE SET
                    realized_pnl = realized_pnl + excluded.realized_pnl,
                    unrealized_pnl = excluded.unrealized_pnl,
                    trades_count = trades_count + 1,
                    updated_at = CURRENT_TIMESTAMP
            ''', (today, realized_pnl, unrealized_pnl))
            conn.commit()
            
    def get_daily_pnl(self) -> float:
        """Zwraca dzisiejszy PnL."""
        today = datetime.now().strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute('''
                SELECT realized_pnl + unrealized_pnl as total_pnl
                FROM daily_pnl
                WHERE date = ?
            ''', (today,))
            row = cur.fetchone()
            return row[0] if row else 0.0
            
    def get_risk_summary(self) -> dict:
        """Podsumowanie ryzyka do wyświetlenia."""
        check = self.check_all()
        daily_pnl = self.get_daily_pnl()
        
        return {
            'status': check.level.value,
            'can_trade': check.can_trade,
            'reason': check.reason,
            'daily_pnl': daily_pnl,
            'daily_loss_limit': -self.max_daily_loss,
            'error_count': self.error_count,
            'circuit_breaker_threshold': self.circuit_breaker_threshold,
            'kill_switch_active': self.kill_switch_file.exists()
        }


if __name__ == '__main__':
    # Test risk manager
    manager = RiskManager()
    
    print("🛡️ Risk Manager Test\n")
    
    # Test 1: Default state
    check = manager.check_all(position_size=30)
    print(f"1. Default check: {check.level.value} - {check.reason}")
    print(f"   Can trade: {check.can_trade}\n")
    
    # Test 2: Position too large
    check = manager.check_all(position_size=100)
    print(f"2. Large position: {check.level.value} - {check.reason}")
    print(f"   Can trade: {check.can_trade}\n")
    
    # Test 3: Rate limiting
    print("3. Rate limiting test:")
    for i in range(12):
        can_send = manager.check_rate_limit()
        status = "✅" if can_send else "❌ BLOCKED"
        print(f"   Message {i+1}: {status}")
    
    # Test 4: Kill switch
    print("\n4. Kill switch test:")
    manager.trigger_kill_switch("Manual test")
    check = manager.check_all()
    print(f"   After trigger: {check.level.value} - {check.reason}")
    
    manager.reset_kill_switch()
    check = manager.check_all()
    print(f"   After reset: {check.level.value} - {check.reason}\n")
    
    # Test 5: Error circuit breaker
    print("5. Circuit breaker test:")
    for i in range(6):
        manager.log_error("TEST", f"Test error {i+1}")
    check = manager.check_all()
    print(f"   After 6 errors: {check.level.value}")
    
    # Reset for other tests
    manager.reset_kill_switch()
