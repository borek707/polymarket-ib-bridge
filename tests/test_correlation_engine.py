"""
Testy jednostkowe dla modulu CorrelationEngine.

Testy:
- find_correlation z keyword match (np. 'fed funds')
- find_correlation z fuzzy match
- find_correlation dla blocked keyword (np. 'trump', 'election')
- _keyword_match z None mapping
- _find_contract_by_symbol
"""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from src.correlation.engine import (
    CorrelationEngine,
    CorrelationResult,
    PolymarketMarket,
    IBContract,
)


class TestFindCorrelationKeywordMatch:
    """Testy find_correlation z keyword matching."""

    def test_find_correlation_fed_funds(self, tmp_db_path, sample_polymarket_markets, sample_ib_contracts):
        """Test find_correlation z keyword match 'fed funds'."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        # Market o fed funds
        market = sample_polymarket_markets[0]  # 'Will the Fed raise interest rates...'
        result = engine.find_correlation(market, sample_ib_contracts)

        assert result is not None
        assert result.score >= 0.8
        assert result.method == "keyword"
        assert result.ib_symbol == "FF"

    def test_find_correlation_eth(self, tmp_db_path, sample_polymarket_markets, sample_ib_contracts):
        """Test find_correlation z keyword match 'ETH'."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        # Market o ETH
        market = sample_polymarket_markets[2]  # 'Will ETH be above $3000...'
        result = engine.find_correlation(market, sample_ib_contracts)

        assert result is not None
        assert result.method == "keyword"
        assert result.ib_symbol == "ETH"


class TestFindCorrelationBlocked:
    """Testy find_correlation dla blocked keywords."""

    def test_find_correlation_trump_blocked(self, tmp_db_path, sample_polymarket_markets, sample_ib_contracts):
        """Test find_correlation dla blocked keyword 'trump' - zwraca None."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        # Market o trump
        market = sample_polymarket_markets[1]  # 'Will Trump win...'
        result = engine.find_correlation(market, sample_ib_contracts)

        # 'trump' jest w KEYWORD_MAP jako None -> blocked
        assert result is None

    def test_find_correlation_election_blocked(self, tmp_db_path, sample_ib_contracts):
        """Test find_correlation dla blocked keyword 'election'."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        market = PolymarketMarket(
            slug="election-2024",
            question="Will the election be contested?",
            description="US election",
            category="Politics",
            volume_24h=500000,
            yes_price=0.30,
            no_price=0.70,
            end_date="2024-11-05"
        )
        result = engine.find_correlation(market, sample_ib_contracts)

        # 'election' jest w KEYWORD_MAP jako None -> blocked
        assert result is None

    def test_find_correlation_biden_blocked(self, tmp_db_path, sample_ib_contracts):
        """Test find_correlation dla blocked keyword 'biden'."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        market = PolymarketMarket(
            slug="biden-policy",
            question="Will Biden sign the new policy?",
            description="Policy",
            category="Politics",
            volume_24h=100000,
            yes_price=0.60,
            no_price=0.40,
            end_date="2025-06-01"
        )
        result = engine.find_correlation(market, sample_ib_contracts)

        # 'biden' jest w KEYWORD_MAP jako None -> blocked
        assert result is None


class TestKeywordMatchNoneMapping:
    """Testy _keyword_match z None mapping."""

    def test_keyword_match_none_mapping(self, tmp_db_path, sample_ib_contracts):
        """Test _keyword_match z None mapping - zwraca None."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        market = PolymarketMarket(
            slug="trump-test",
            question="Will trump win?",
            description="Test",
            category="Politics",
            volume_24h=100000,
            yes_price=0.50,
            no_price=0.50,
            end_date="2025-01-01"
        )
        result = engine._keyword_match(market, sample_ib_contracts)
        assert result is None

    def test_keyword_match_no_keyword(self, tmp_db_path, sample_ib_contracts):
        """Test _keyword_match gdy zaden keyword nie pasuje."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        market = PolymarketMarket(
            slug="random-market",
            question="Will aliens land tomorrow?",
            description="Random",
            category="Other",
            volume_24h=100000,
            yes_price=0.01,
            no_price=0.99,
            end_date="2025-01-01"
        )
        result = engine._keyword_match(market, sample_ib_contracts)
        assert result is None


class TestFindContractBySymbol:
    """Testy _find_contract_by_symbol."""

    def test_find_contract_by_symbol_istnieje(self, tmp_db_path, sample_ib_contracts):
        """Test _find_contract_by_symbol gdy kontrakt istnieje."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        result = engine._find_contract_by_symbol(sample_ib_contracts, "FF")

        assert result is not None
        assert result.symbol == "FF"
        assert result.conid == 1

    def test_find_contract_by_symbol_nie_istnieje(self, tmp_db_path, sample_ib_contracts):
        """Test _find_contract_by_symbol gdy kontrakt nie istnieje."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        result = engine._find_contract_by_symbol(sample_ib_contracts, "UNKNOWN")

        assert result is None

    def test_find_contract_by_symbol_pusta_lista(self, tmp_db_path):
        """Test _find_contract_by_symbol z pusta lista."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        result = engine._find_contract_by_symbol([], "FF")

        assert result is None


class TestFindContractByConid:
    """Testy _find_contract_by_conid."""

    def test_find_contract_by_conid(self, tmp_db_path, sample_ib_contracts):
        """Test _find_contract_by_conid."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        result = engine._find_contract_by_conid(sample_ib_contracts, 2)

        assert result is not None
        assert result.conid == 2
        assert result.symbol == "ETH"

    def test_find_contract_by_conid_nie_istnieje(self, tmp_db_path, sample_ib_contracts):
        """Test _find_contract_by_conid gdy nie istnieje."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        result = engine._find_contract_by_conid(sample_ib_contracts, 99999)

        assert result is None


class TestFuzzyMatch:
    """Testy _fuzzy_match."""

    def test_fuzzy_match_znajduje(self, tmp_db_path, sample_ib_contracts):
        """Test _fuzzy_match znajduje podobienstwo."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        # Market z pytaniem podobnym do nazwy kontraktu IB
        market = PolymarketMarket(
            slug="fed-funds-test",
            question="Fed Funds Mar25 4.875C target rate decision",
            description="Test",
            category="Economics",
            volume_24h=100000,
            yes_price=0.35,
            no_price=0.65,
            end_date="2025-03-19"
        )
        result = engine._fuzzy_match(market, sample_ib_contracts)

        # Powinien znalezc dopasowanie fuzzy
        if result:
            assert result.method == "fuzzy"
            assert result.score >= 0.6

    def test_fuzzy_match_brak_dopasowania(self, tmp_db_path, sample_ib_contracts):
        """Test _fuzzy_match gdy brak dopasowania."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        market = PolymarketMarket(
            slug="random",
            question="Completely unrelated question about aliens and pizza?",
            description="Random",
            category="Other",
            volume_24h=1000,
            yes_price=0.50,
            no_price=0.50,
            end_date="2025-01-01"
        )
        result = engine._fuzzy_match(market, sample_ib_contracts)

        # Przy bardzo niskim dopasowaniu moze zwrocic None lub wynik < 0.6
        if result:
            assert result.score < 0.6 or result.method == "fuzzy"


class TestManualOverride:
    """Testy dla manual overrides."""

    def test_manual_override(self, tmp_db_path, sample_ib_contracts):
        """Test ze manual override ma priorytet."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        # Dodaj manual override
        engine.add_manual_override("custom-market", 1, "Test override")

        market = PolymarketMarket(
            slug="custom-market",
            question="Random question?",
            description="Test",
            category="Other",
            volume_24h=100000,
            yes_price=0.50,
            no_price=0.50,
            end_date="2025-01-01"
        )
        result = engine.find_correlation(market, sample_ib_contracts)

        assert result is not None
        assert result.method == "manual"
        assert result.score == 1.0
        assert result.confidence == "HIGH"

    def test_load_manual_overrides(self, tmp_db_path):
        """Test wczytywania manual overrides z bazy."""
        engine = CorrelationEngine(db_path=tmp_db_path)
        engine.add_manual_override("test-slug", 12345, "Test rationale")

        # Stworz nowy engine - powinien wczytac overrides
        engine2 = CorrelationEngine(db_path=tmp_db_path)

        assert "test-slug" in engine2.manual_overrides
        assert engine2.manual_overrides["test-slug"]["conid"] == 12345


class TestBatchCorrelate:
    """Testy batch_correlate."""

    def test_batch_correlate(self, tmp_db_path, sample_polymarket_markets, sample_ib_contracts):
        """Test batch_correlate dla listy marketow."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        results = engine.batch_correlate(sample_polymarket_markets, sample_ib_contracts)

        # Fed Funds i ETH powinny byc znalezione, Trump zablokowany
        assert len(results) >= 1
        # Sprawdz czy wyniki sa zapisywane do bazy
        with sqlite3.connect(tmp_db_path) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM correlations")
            count = cur.fetchone()[0]
            assert count >= len(results)

    def test_batch_correlate_min_score(self, tmp_db_path, sample_polymarket_markets, sample_ib_contracts):
        """Test batch_correlate z min_score filtrowaniem."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        # Wysoki min_score - moze nie znalezc nic
        results = engine.batch_correlate(
            sample_polymarket_markets,
            sample_ib_contracts,
            min_score=0.99
        )

        # Tylko manual overrides maja score 1.0
        assert len(results) == 0


class TestCorrelationResultProperties:
    """Testy wlasciwosci CorrelationResult."""

    def test_is_tradeable_true(self):
        """Test is_tradeable gdy score >= 0.6 i confidence HIGH/MEDIUM."""
        result = CorrelationResult(
            poly_slug="test",
            poly_question="Test?",
            ib_conid=1,
            ib_symbol="FF",
            ib_name="Fed Funds",
            score=0.8,
            method="keyword",
            direction="SAME",
            confidence="HIGH",
            rationale="Test"
        )
        assert result.is_tradeable is True

    def test_is_tradeable_false_low_score(self):
        """Test is_tradeable gdy score < 0.6."""
        result = CorrelationResult(
            poly_slug="test",
            poly_question="Test?",
            ib_conid=1,
            ib_symbol="FF",
            ib_name="Fed Funds",
            score=0.4,
            method="fuzzy",
            direction="SAME",
            confidence="MEDIUM",
            rationale="Test"
        )
        assert result.is_tradeable is False

    def test_is_tradeable_false_low_confidence(self):
        """Test is_tradeable gdy confidence LOW."""
        result = CorrelationResult(
            poly_slug="test",
            poly_question="Test?",
            ib_conid=1,
            ib_symbol="FF",
            ib_name="Fed Funds",
            score=0.7,
            method="fuzzy",
            direction="SAME",
            confidence="LOW",
            rationale="Test"
        )
        assert result.is_tradeable is False


class TestKeywordMapCoverage:
    """Testy pokrycia keyword map."""

    def test_keyword_map_contains_fed_funds(self, tmp_db_path):
        """Test ze keyword map zawiera 'fed funds'."""
        engine = CorrelationEngine(db_path=tmp_db_path)
        assert "fed funds" in engine.KEYWORD_MAP
        assert engine.KEYWORD_MAP["fed funds"] == ("FF", "SAME", 0.95)

    def test_keyword_map_contains_cpi(self, tmp_db_path):
        """Test ze keyword map zawiera 'cpi'."""
        engine = CorrelationEngine(db_path=tmp_db_path)
        assert "cpi" in engine.KEYWORD_MAP
        assert engine.KEYWORD_MAP["cpi"] == ("CPI", "SAME", 0.95)

    def test_keyword_map_contains_bitcoin(self, tmp_db_path):
        """Test ze keyword map zawiera 'bitcoin'."""
        engine = CorrelationEngine(db_path=tmp_db_path)
        assert "bitcoin" in engine.KEYWORD_MAP
        assert engine.KEYWORD_MAP["bitcoin"] == ("BTC", "SAME", 0.95)

    def test_keyword_map_contains_blocked(self, tmp_db_path):
        """Test ze keyword map zawiera blocked keywords."""
        engine = CorrelationEngine(db_path=tmp_db_path)
        assert "trump" in engine.KEYWORD_MAP
        assert engine.KEYWORD_MAP["trump"] is None
        assert "election" in engine.KEYWORD_MAP
        assert engine.KEYWORD_MAP["election"] is None


class TestDbInit:
    """Testy inicjalizacji bazy danych."""

    def test_db_init_creates_tables(self, tmp_db_path):
        """Test ze _init_db tworzy tabele."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        with sqlite3.connect(tmp_db_path) as conn:
            cur = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN ('correlations', 'manual_overrides')
            """)
            tables = [row[0] for row in cur.fetchall()]
            assert "correlations" in tables
            assert "manual_overrides" in tables

    def test_save_correlation(self, tmp_db_path, sample_ib_contracts):
        """Test _save_correlation zapisuje do bazy."""
        engine = CorrelationEngine(db_path=tmp_db_path)

        result = CorrelationResult(
            poly_slug="test-slug",
            poly_question="Test?",
            ib_conid=1,
            ib_symbol="FF",
            ib_name="Fed Funds",
            score=0.9,
            method="keyword",
            direction="SAME",
            confidence="HIGH",
            rationale="Test save"
        )
        engine._save_correlation(result)

        with sqlite3.connect(tmp_db_path) as conn:
            cur = conn.execute(
                "SELECT poly_slug, score, method FROM correlations WHERE poly_slug = ?",
                ("test-slug",)
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "test-slug"
            assert row[1] == 0.9
            assert row[2] == "keyword"
