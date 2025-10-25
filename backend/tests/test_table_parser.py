"""
Unit tests for TableParser service

Tests table classification and parsing logic for:
- Capital calls
- Distributions
- Adjustments
- Date parsing
- Amount parsing
"""
import pytest
from decimal import Decimal
from datetime import date
from app.services.table_parser import TableParser


class TestTableParser:
    """Test suite for TableParser"""

    @pytest.fixture
    def parser(self):
        """Create TableParser instance"""
        return TableParser()

    # ==================== Table Classification Tests ====================

    def test_classify_capital_call_table(self, parser):
        """Test classification of capital call tables"""
        table = [
            ["Date", "Capital Call", "Amount", "Description"],
            ["2024-01-15", "Investment", "$1,000,000", "Series A"]
        ]

        result = parser._classify_table(table)
        assert result == "capital_call"

    def test_classify_distribution_table(self, parser):
        """Test classification of distribution tables"""
        table = [
            ["Date", "Distribution", "Amount", "Type"],
            ["2024-01-15", "Dividend", "$500,000", "Return of Capital"]
        ]

        result = parser._classify_table(table)
        assert result == "distribution"

    def test_classify_adjustment_table(self, parser):
        """Test classification of adjustment tables"""
        table = [
            ["Date", "Adjustment", "Amount", "Category"],
            ["2024-01-15", "Rebalance", "$100,000", "Clawback"]
        ]

        result = parser._classify_table(table)
        assert result == "adjustment"

    def test_classify_unknown_table(self, parser):
        """Test classification of unknown table types"""
        table = [
            ["Random", "Headers", "Here"],
            ["Some", "Data", "Here"]
        ]

        result = parser._classify_table(table)
        assert result == "unknown"

    def test_classify_empty_table(self, parser):
        """Test classification of empty table"""
        table = []

        result = parser._classify_table(table)
        assert result == "unknown"

    # ==================== Date Parsing Tests ====================

    def test_parse_iso_date(self, parser):
        """Test parsing ISO format date (YYYY-MM-DD)"""
        result = parser._parse_date("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_parse_us_date(self, parser):
        """Test parsing US format date (MM/DD/YYYY)"""
        result = parser._parse_date("01/15/2024")
        assert result == date(2024, 1, 15)

    def test_parse_written_date(self, parser):
        """Test parsing written date format"""
        result = parser._parse_date("January 15, 2024")
        assert result == date(2024, 1, 15)

    def test_parse_invalid_date(self, parser):
        """Test parsing invalid date"""
        result = parser._parse_date("not a date")
        assert result is None

    def test_parse_empty_date(self, parser):
        """Test parsing empty date"""
        result = parser._parse_date("")
        assert result is None

    def test_parse_none_date(self, parser):
        """Test parsing None date"""
        result = parser._parse_date(None)
        assert result is None

    # ==================== Amount Parsing Tests ====================

    def test_parse_simple_amount(self, parser):
        """Test parsing simple amount"""
        result = parser._parse_amount("1000")
        assert result == Decimal("1000")

    def test_parse_amount_with_dollar_sign(self, parser):
        """Test parsing amount with dollar sign"""
        result = parser._parse_amount("$1,000,000.50")
        assert result == Decimal("1000000.50")

    def test_parse_amount_with_commas(self, parser):
        """Test parsing amount with thousands separators"""
        result = parser._parse_amount("1,234,567.89")
        assert result == Decimal("1234567.89")

    def test_parse_negative_amount_parentheses(self, parser):
        """Test parsing negative amount in parentheses (accounting notation)"""
        result = parser._parse_amount("($500,000)")
        assert result == Decimal("-500000")

    def test_parse_negative_amount_minus(self, parser):
        """Test parsing negative amount with minus sign"""
        result = parser._parse_amount("-$500,000")
        assert result == Decimal("-500000")

    def test_parse_invalid_amount(self, parser):
        """Test parsing invalid amount"""
        result = parser._parse_amount("not a number")
        assert result is None

    def test_parse_empty_amount(self, parser):
        """Test parsing empty amount"""
        result = parser._parse_amount("")
        assert result is None

    # ==================== Capital Call Parsing Tests ====================

    def test_parse_capital_calls(self, parser):
        """Test parsing complete capital call table"""
        table = [
            ["Date", "Amount", "Type", "Description"],
            ["2024-01-15", "$1,000,000", "Investment", "Series A Round"],
            ["2024-02-20", "$500,000.50", "Management Fee", "Q1 2024"],
        ]

        result = parser._parse_capital_calls(table, fund_id=1)

        assert len(result) == 2

        # First call
        assert result[0]["fund_id"] == 1
        assert result[0]["call_date"] == date(2024, 1, 15)
        assert result[0]["amount"] == Decimal("1000000")
        assert result[0]["call_type"] == "Investment"
        assert result[0]["description"] == "Series A Round"

        # Second call
        assert result[1]["fund_id"] == 1
        assert result[1]["call_date"] == date(2024, 2, 20)
        assert result[1]["amount"] == Decimal("500000.50")
        assert result[1]["call_type"] == "Management Fee"

    def test_parse_capital_calls_missing_data(self, parser):
        """Test parsing capital calls with missing date or amount"""
        table = [
            ["Date", "Amount", "Type"],
            ["2024-01-15", "$1,000,000", "Investment"],  # Valid
            ["", "$500,000", "Investment"],  # Missing date
            ["2024-02-20", "", "Investment"],  # Missing amount
        ]

        result = parser._parse_capital_calls(table, fund_id=1)

        # Only the valid row should be parsed
        assert len(result) == 1
        assert result[0]["call_date"] == date(2024, 1, 15)

    # ==================== Distribution Parsing Tests ====================

    def test_parse_distributions(self, parser):
        """Test parsing complete distribution table"""
        table = [
            ["Date", "Amount", "Type", "Recallable", "Description"],
            ["2024-03-15", "$750,000", "Dividend", "Yes", "Q1 Distribution"],
            ["2024-04-20", "$250,000.25", "Return of Capital", "No", "Exit proceeds"],
        ]

        result = parser._parse_distributions(table, fund_id=1)

        assert len(result) == 2

        # First distribution
        assert result[0]["fund_id"] == 1
        assert result[0]["distribution_date"] == date(2024, 3, 15)
        assert result[0]["amount"] == Decimal("750000")
        assert result[0]["distribution_type"] == "Dividend"
        assert result[0]["is_recallable"] is True

        # Second distribution
        assert result[1]["fund_id"] == 1
        assert result[1]["distribution_date"] == date(2024, 4, 20)
        assert result[1]["amount"] == Decimal("250000.25")
        assert result[1]["is_recallable"] is False

    def test_parse_distributions_default_type(self, parser):
        """Test distributions get default type if not specified"""
        table = [
            ["Date", "Amount"],
            ["2024-03-15", "$750,000"],
        ]

        result = parser._parse_distributions(table, fund_id=1)

        assert len(result) == 1
        assert result[0]["distribution_type"] == "Return of Capital"

    # ==================== Adjustment Parsing Tests ====================

    def test_parse_adjustments(self, parser):
        """Test parsing complete adjustment table"""
        table = [
            ["Date", "Amount", "Type", "Category", "Description"],
            ["2024-05-15", "$100,000", "Rebalance", "Clawback", "Q1 adjustment"],
            ["2024-06-20", "-$50,000", "Refund", "Capital Call", "Overcall return"],
        ]

        result = parser._parse_adjustments(table, fund_id=1)

        assert len(result) == 2

        # First adjustment
        assert result[0]["fund_id"] == 1
        assert result[0]["adjustment_date"] == date(2024, 5, 15)
        assert result[0]["amount"] == Decimal("100000")
        assert result[0]["adjustment_type"] == "Rebalance"
        assert result[0]["category"] == "Clawback"

        # Second adjustment (with contribution flag)
        assert result[1]["fund_id"] == 1
        assert result[1]["adjustment_date"] == date(2024, 6, 20)
        assert result[1]["amount"] == Decimal("-50000")
        assert result[1]["is_contribution_adjustment"] is True

    def test_parse_adjustments_negative_amounts(self, parser):
        """Test adjustments can have negative amounts"""
        table = [
            ["Date", "Amount", "Type"],
            ["2024-05-15", "($100,000)", "Clawback"],
        ]

        result = parser._parse_adjustments(table, fund_id=1)

        assert len(result) == 1
        assert result[0]["amount"] == Decimal("-100000")

    # ==================== Integration Tests ====================

    def test_parse_table_capital_call(self, parser):
        """Test complete parse_table flow for capital call"""
        table = [
            ["Date", "Capital Call Amount", "Description"],
            ["2024-01-15", "$1,000,000", "Investment"],
        ]

        result = parser.parse_table(table, fund_id=1)

        assert result["type"] == "capital_call"
        assert len(result["data"]) == 1
        assert result["data"][0]["amount"] == Decimal("1000000")

    def test_parse_table_too_small(self, parser):
        """Test parse_table with insufficient rows"""
        table = [
            ["Date", "Amount"]
        ]

        result = parser.parse_table(table, fund_id=1)

        assert result["type"] == "unknown"
        assert "error" in result

    def test_parse_table_empty(self, parser):
        """Test parse_table with empty table"""
        table = []

        result = parser.parse_table(table, fund_id=1)

        assert result["type"] == "unknown"
        assert "error" in result


class TestTableParserEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def parser(self):
        return TableParser()

    def test_parse_table_with_none_cells(self, parser):
        """Test parsing table with None cells"""
        table = [
            ["Date", "Amount", None],
            ["2024-01-15", None, "$1,000,000"],
        ]

        result = parser.parse_table(table, fund_id=1)
        # Should not crash, may or may not find valid data
        assert "type" in result

    def test_parse_date_with_extra_text(self, parser):
        """Test parsing date with extra text (fuzzy parsing)"""
        result = parser._parse_date("As of 2024-01-15 the date")
        assert result == date(2024, 1, 15)

    def test_parse_amount_with_currency_symbols(self, parser):
        """Test parsing amounts with various currency symbols"""
        assert parser._parse_amount("€1,000") == Decimal("1000")
        assert parser._parse_amount("£500.50") == Decimal("500.50")
        assert parser._parse_amount("¥100000") == Decimal("100000")

    def test_parse_capital_calls_various_formats(self, parser):
        """Test capital call parsing with various cell formats"""
        table = [
            ["Call Date", "Contribution Amount", "Type of Call"],
            ["01/15/2024", "$1,000,000.00", "Investment Capital"],
            ["January 20, 2024", "500000", "Mgmt Fee"],
        ]

        result = parser._parse_capital_calls(table, fund_id=1)

        assert len(result) == 2
        assert result[0]["amount"] == Decimal("1000000")
        assert result[1]["amount"] == Decimal("500000")
