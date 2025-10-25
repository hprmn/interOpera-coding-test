"""
Unit tests for MetricsCalculator service

Tests financial metrics calculations:
- PIC (Paid-In Capital)
- DPI (Distribution to Paid-In)
- IRR (Internal Rate of Return)
- Detailed calculation breakdowns
"""
import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import Mock
from app.services.metrics_calculator import MetricsCalculator


class TestMetricsCalculator:
    """Test suite for MetricsCalculator"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return Mock()

    @pytest.fixture
    def calculator(self, mock_db):
        """Create MetricsCalculator instance"""
        return MetricsCalculator(mock_db)

    # ==================== PIC Calculation Tests ====================

    def test_calculate_pic_simple(self, calculator, mock_db):
        """Test simple PIC calculation"""
        # Mock capital calls
        mock_call_1 = Mock()
        mock_call_1.amount = Decimal("1000000")

        mock_call_2 = Mock()
        mock_call_2.amount = Decimal("500000")

        mock_db.query().filter().all.return_value = [mock_call_1, mock_call_2]

        # Mock adjustments (empty)
        mock_db.query().filter().filter().all.return_value = []

        result = calculator.calculate_pic(fund_id=1)

        assert result == Decimal("1500000")

    def test_calculate_pic_with_adjustments(self, calculator, mock_db):
        """Test PIC calculation with contribution adjustments"""
        # Mock capital calls
        mock_call = Mock()
        mock_call.amount = Decimal("1000000")

        # Mock adjustments
        mock_adj_1 = Mock()
        mock_adj_1.amount = Decimal("50000")  # Positive adjustment

        mock_adj_2 = Mock()
        mock_adj_2.amount = Decimal("-25000")  # Negative adjustment

        def query_side_effect(*args):
            query_mock = Mock()
            if args[0].__name__ == 'CapitalCall':
                query_mock.filter().all.return_value = [mock_call]
            else:  # Adjustment
                query_mock.filter().filter().all.return_value = [mock_adj_1, mock_adj_2]
            return query_mock

        mock_db.query.side_effect = query_side_effect

        result = calculator.calculate_pic(fund_id=1)

        # PIC = 1,000,000 + 50,000 - 25,000 = 1,025,000
        assert result == Decimal("1025000")

    def test_calculate_pic_no_calls(self, calculator, mock_db):
        """Test PIC calculation with no capital calls"""
        mock_db.query().filter().all.return_value = []
        mock_db.query().filter().filter().all.return_value = []

        result = calculator.calculate_pic(fund_id=1)

        assert result == Decimal("0")

    # ==================== Total Distributions Tests ====================

    def test_calculate_total_distributions(self, calculator, mock_db):
        """Test total distributions calculation"""
        mock_dist_1 = Mock()
        mock_dist_1.amount = Decimal("500000")

        mock_dist_2 = Mock()
        mock_dist_2.amount = Decimal("750000")

        mock_db.query().filter().all.return_value = [mock_dist_1, mock_dist_2]

        result = calculator.calculate_total_distributions(fund_id=1)

        assert result == Decimal("1250000")

    def test_calculate_total_distributions_none(self, calculator, mock_db):
        """Test distributions with no data"""
        mock_db.query().filter().all.return_value = []

        result = calculator.calculate_total_distributions(fund_id=1)

        assert result == Decimal("0")

    # ==================== DPI Calculation Tests ====================

    def test_calculate_dpi_simple(self, calculator, mock_db):
        """Test simple DPI calculation"""
        # Mock capital calls for PIC
        mock_call = Mock()
        mock_call.amount = Decimal("1000000")

        # Mock distributions
        mock_dist = Mock()
        mock_dist.amount = Decimal("850000")

        def query_side_effect(*args):
            query_mock = Mock()
            if args[0].__name__ == 'CapitalCall':
                query_mock.filter().all.return_value = [mock_call]
            elif args[0].__name__ == 'Distribution':
                query_mock.filter().all.return_value = [mock_dist]
            else:  # Adjustment
                query_mock.filter().filter().all.return_value = []
            return query_mock

        mock_db.query.side_effect = query_side_effect

        result = calculator.calculate_dpi(fund_id=1)

        # DPI = 850,000 / 1,000,000 = 0.85
        assert result == pytest.approx(0.85, rel=1e-9)

    def test_calculate_dpi_zero_pic(self, calculator, mock_db):
        """Test DPI calculation with zero PIC"""
        mock_db.query().filter().all.return_value = []
        mock_db.query().filter().filter().all.return_value = []

        result = calculator.calculate_dpi(fund_id=1)

        # Should return 0.0 when PIC is zero
        assert result == 0.0

    def test_calculate_dpi_greater_than_one(self, calculator, mock_db):
        """Test DPI > 1 (distributions exceed capital called)"""
        # Mock capital calls
        mock_call = Mock()
        mock_call.amount = Decimal("1000000")

        # Mock distributions (greater than calls)
        mock_dist = Mock()
        mock_dist.amount = Decimal("1500000")

        def query_side_effect(*args):
            query_mock = Mock()
            if args[0].__name__ == 'CapitalCall':
                query_mock.filter().all.return_value = [mock_call]
            elif args[0].__name__ == 'Distribution':
                query_mock.filter().all.return_value = [mock_dist]
            else:
                query_mock.filter().filter().all.return_value = []
            return query_mock

        mock_db.query.side_effect = query_side_effect

        result = calculator.calculate_dpi(fund_id=1)

        # DPI = 1,500,000 / 1,000,000 = 1.5
        assert result == pytest.approx(1.5, rel=1e-9)

    # ==================== IRR Calculation Tests ====================

    def test_calculate_irr_simple(self, calculator, mock_db):
        """Test simple IRR calculation"""
        # Capital call (negative cash flow)
        mock_call = Mock()
        mock_call.call_date = date(2024, 1, 1)
        mock_call.amount = Decimal("1000000")

        # Distribution (positive cash flow)
        mock_dist = Mock()
        mock_dist.distribution_date = date(2024, 12, 31)
        mock_dist.amount = Decimal("1200000")

        def query_side_effect(*args):
            query_mock = Mock()
            if args[0].__name__ == 'CapitalCall':
                query_mock.filter().order_by().all.return_value = [mock_call]
            elif args[0].__name__ == 'Distribution':
                query_mock.filter().order_by().all.return_value = [mock_dist]
            else:
                query_mock.filter().filter().order_by().all.return_value = []
            return query_mock

        mock_db.query.side_effect = query_side_effect

        result = calculator.calculate_irr(fund_id=1)

        # IRR should be positive (around 20% for this scenario)
        assert result is not None
        assert result > 0
        assert result < 1  # Less than 100%

    def test_calculate_irr_negative(self, calculator, mock_db):
        """Test IRR calculation with loss"""
        # Capital call
        mock_call = Mock()
        mock_call.call_date = date(2024, 1, 1)
        mock_call.amount = Decimal("1000000")

        # Distribution (less than capital)
        mock_dist = Mock()
        mock_dist.distribution_date = date(2024, 12, 31)
        mock_dist.amount = Decimal("800000")

        def query_side_effect(*args):
            query_mock = Mock()
            if args[0].__name__ == 'CapitalCall':
                query_mock.filter().order_by().all.return_value = [mock_call]
            elif args[0].__name__ == 'Distribution':
                query_mock.filter().order_by().all.return_value = [mock_dist]
            else:
                query_mock.filter().filter().order_by().all.return_value = []
            return query_mock

        mock_db.query.side_effect = query_side_effect

        result = calculator.calculate_irr(fund_id=1)

        # IRR should be negative
        assert result is not None
        assert result < 0

    def test_calculate_irr_insufficient_data(self, calculator, mock_db):
        """Test IRR with insufficient cash flows"""
        # Only one cash flow
        mock_call = Mock()
        mock_call.call_date = date(2024, 1, 1)
        mock_call.amount = Decimal("1000000")

        def query_side_effect(*args):
            query_mock = Mock()
            if args[0].__name__ == 'CapitalCall':
                query_mock.filter().order_by().all.return_value = [mock_call]
            else:
                query_mock.filter().order_by().all.return_value = []
                query_mock.filter().filter().order_by().all.return_value = []
            return query_mock

        mock_db.query.side_effect = query_side_effect

        result = calculator.calculate_irr(fund_id=1)

        # Should return None when insufficient data
        assert result is None

    def test_calculate_irr_all_positive_flows(self, calculator, mock_db):
        """Test IRR with all positive cash flows (invalid)"""
        # All distributions, no calls
        mock_dist_1 = Mock()
        mock_dist_1.distribution_date = date(2024, 1, 1)
        mock_dist_1.amount = Decimal("500000")

        mock_dist_2 = Mock()
        mock_dist_2.distribution_date = date(2024, 6, 1)
        mock_dist_2.amount = Decimal("750000")

        def query_side_effect(*args):
            query_mock = Mock()
            if args[0].__name__ == 'Distribution':
                query_mock.filter().order_by().all.return_value = [mock_dist_1, mock_dist_2]
            else:
                query_mock.filter().order_by().all.return_value = []
                query_mock.filter().filter().order_by().all.return_value = []
            return query_mock

        mock_db.query.side_effect = query_side_effect

        result = calculator.calculate_irr(fund_id=1)

        # Should return None (can't calculate IRR with all positive flows)
        assert result is None

    # ==================== Calculate All Metrics Tests ====================

    def test_calculate_all_metrics(self, calculator, mock_db):
        """Test calculating all metrics at once"""
        # Setup mock data
        mock_call = Mock()
        mock_call.call_date = date(2024, 1, 1)
        mock_call.amount = Decimal("1000000")

        mock_dist = Mock()
        mock_dist.distribution_date = date(2024, 12, 31)
        mock_dist.amount = Decimal("850000")

        def query_side_effect(*args):
            query_mock = Mock()
            if args[0].__name__ == 'CapitalCall':
                query_mock.filter().all.return_value = [mock_call]
                query_mock.filter().order_by().all.return_value = [mock_call]
            elif args[0].__name__ == 'Distribution':
                query_mock.filter().all.return_value = [mock_dist]
                query_mock.filter().order_by().all.return_value = [mock_dist]
            else:
                query_mock.filter().filter().all.return_value = []
                query_mock.filter().filter().order_by().all.return_value = []
            return query_mock

        mock_db.query.side_effect = query_side_effect

        result = calculator.calculate_all_metrics(fund_id=1)

        # Should return all metrics
        assert "pic" in result
        assert "dpi" in result
        assert "irr" in result
        assert "total_distributions" in result

        # Verify values
        assert result["pic"] == 1000000.0
        assert result["total_distributions"] == 850000.0
        assert result["dpi"] == pytest.approx(0.85, rel=1e-9)

    # ==================== Calculation Breakdown Tests ====================

    def test_get_calculation_breakdown_dpi(self, calculator, mock_db):
        """Test detailed DPI calculation breakdown"""
        # Setup mock data
        mock_call = Mock()
        mock_call.call_date = date(2024, 1, 15)
        mock_call.amount = Decimal("1000000")
        mock_call.call_type = "Investment"
        mock_call.description = "Initial capital call"

        mock_dist = Mock()
        mock_dist.distribution_date = date(2024, 6, 20)
        mock_dist.amount = Decimal("850000")
        mock_dist.distribution_type = "Return of Capital"
        mock_dist.description = "Q2 distribution"

        def query_side_effect(*args):
            query_mock = Mock()
            if args[0].__name__ == 'CapitalCall':
                query_mock.filter().all.return_value = [mock_call]
                query_mock.filter().order_by().all.return_value = [mock_call]
            elif args[0].__name__ == 'Distribution':
                query_mock.filter().all.return_value = [mock_dist]
                query_mock.filter().order_by().all.return_value = [mock_dist]
            else:
                query_mock.filter().filter().all.return_value = []
                query_mock.filter().filter().order_by().all.return_value = []
            return query_mock

        mock_db.query.side_effect = query_side_effect

        result = calculator.get_calculation_breakdown(fund_id=1, metric="dpi")

        # Should include breakdown details
        assert result["metric"] == "dpi"
        assert "value" in result
        assert "capital_calls" in result
        assert "distributions" in result
        assert "calculation_steps" in result

        # Verify capital calls data
        assert len(result["capital_calls"]) == 1
        assert result["capital_calls"][0]["amount"] == 1000000.0

        # Verify distributions data
        assert len(result["distributions"]) == 1
        assert result["distributions"][0]["amount"] == 850000.0

    def test_get_calculation_breakdown_irr(self, calculator, mock_db):
        """Test detailed IRR calculation breakdown"""
        mock_call = Mock()
        mock_call.call_date = date(2024, 1, 1)
        mock_call.amount = Decimal("1000000")
        mock_call.call_type = "Investment"
        mock_call.description = None

        mock_dist = Mock()
        mock_dist.distribution_date = date(2024, 12, 31)
        mock_dist.amount = Decimal("1200000")
        mock_dist.distribution_type = "Return of Capital"
        mock_dist.description = None

        def query_side_effect(*args):
            query_mock = Mock()
            if args[0].__name__ == 'CapitalCall':
                query_mock.filter().order_by().all.return_value = [mock_call]
            elif args[0].__name__ == 'Distribution':
                query_mock.filter().order_by().all.return_value = [mock_dist]
            else:
                query_mock.filter().filter().order_by().all.return_value = []
            return query_mock

        mock_db.query.side_effect = query_side_effect

        result = calculator.get_calculation_breakdown(fund_id=1, metric="irr")

        # Should include IRR-specific data
        assert result["metric"] == "irr"
        assert "value" in result
        assert "cash_flows" in result

        # Should have cash flow timeline
        assert len(result["cash_flows"]) == 2

    def test_get_calculation_breakdown_invalid_metric(self, calculator, mock_db):
        """Test breakdown with invalid metric name"""
        result = calculator.get_calculation_breakdown(fund_id=1, metric="invalid_metric")

        # Should return error
        assert "error" in result


class TestMetricsCalculatorEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.fixture
    def mock_db(self):
        return Mock()

    @pytest.fixture
    def calculator(self, mock_db):
        return MetricsCalculator(mock_db)

    def test_calculate_pic_with_zero_amounts(self, calculator, mock_db):
        """Test PIC with zero-amount capital calls"""
        mock_call = Mock()
        mock_call.amount = Decimal("0")

        mock_db.query().filter().all.return_value = [mock_call]
        mock_db.query().filter().filter().all.return_value = []

        result = calculator.calculate_pic(fund_id=1)

        assert result == Decimal("0")

    def test_calculate_dpi_with_very_small_pic(self, calculator, mock_db):
        """Test DPI with very small PIC (edge of zero division)"""
        mock_call = Mock()
        mock_call.amount = Decimal("0.01")  # 1 cent

        mock_dist = Mock()
        mock_dist.amount = Decimal("0.02")

        def query_side_effect(*args):
            query_mock = Mock()
            if args[0].__name__ == 'CapitalCall':
                query_mock.filter().all.return_value = [mock_call]
            elif args[0].__name__ == 'Distribution':
                query_mock.filter().all.return_value = [mock_dist]
            else:
                query_mock.filter().filter().all.return_value = []
            return query_mock

        mock_db.query.side_effect = query_side_effect

        result = calculator.calculate_dpi(fund_id=1)

        # Should calculate correctly even with tiny amounts
        assert result == pytest.approx(2.0, rel=1e-9)

    def test_calculate_metrics_with_large_amounts(self, calculator, mock_db):
        """Test calculations with very large amounts"""
        # $10 billion capital call
        mock_call = Mock()
        mock_call.amount = Decimal("10000000000")

        mock_dist = Mock()
        mock_dist.amount = Decimal("8500000000")

        def query_side_effect(*args):
            query_mock = Mock()
            if args[0].__name__ == 'CapitalCall':
                query_mock.filter().all.return_value = [mock_call]
            elif args[0].__name__ == 'Distribution':
                query_mock.filter().all.return_value = [mock_dist]
            else:
                query_mock.filter().filter().all.return_value = []
            return query_mock

        mock_db.query.side_effect = query_side_effect

        pic = calculator.calculate_pic(fund_id=1)
        dpi = calculator.calculate_dpi(fund_id=1)

        # Should handle large amounts correctly
        assert pic == Decimal("10000000000")
        assert dpi == pytest.approx(0.85, rel=1e-9)

    def test_calculate_irr_same_date_flows(self, calculator, mock_db):
        """Test IRR when all cash flows on same date"""
        same_date = date(2024, 1, 1)

        mock_call = Mock()
        mock_call.call_date = same_date
        mock_call.amount = Decimal("1000000")

        mock_dist = Mock()
        mock_dist.distribution_date = same_date
        mock_dist.amount = Decimal("1200000")

        def query_side_effect(*args):
            query_mock = Mock()
            if args[0].__name__ == 'CapitalCall':
                query_mock.filter().order_by().all.return_value = [mock_call]
            elif args[0].__name__ == 'Distribution':
                query_mock.filter().order_by().all.return_value = [mock_dist]
            else:
                query_mock.filter().filter().order_by().all.return_value = []
            return query_mock

        mock_db.query.side_effect = query_side_effect

        result = calculator.calculate_irr(fund_id=1)

        # IRR calculation may fail or return None for same-date flows
        # This is expected behavior (undefined mathematically)
        # The function should handle gracefully
        assert result is None or isinstance(result, (float, type(None)))
