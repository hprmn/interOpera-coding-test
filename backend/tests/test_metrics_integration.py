"""
Integration tests for MetricsCalculator with real database

Tests metrics calculations with actual database data using SQLite fixtures
"""
import pytest
from decimal import Decimal
from datetime import date
from app.services.metrics_calculator import MetricsCalculator


@pytest.mark.integration
class TestMetricsCalculatorIntegration:
    """Integration tests with real database"""

    def test_calculate_pic_with_real_data(self, test_db, complete_fund_data):
        """Test PIC calculation with real database data"""
        calculator = MetricsCalculator(test_db)
        fund = complete_fund_data["fund"]

        pic = calculator.calculate_pic(fund.id)

        # Expected: 1,000,000 + 500,000 + 750,000 = 2,250,000
        # With adjustments: 2,250,000 + 50,000 - 25,000 = 2,275,000
        assert pic == Decimal("2275000")

    def test_calculate_total_distributions_with_real_data(self, test_db, complete_fund_data):
        """Test total distributions with real database data"""
        calculator = MetricsCalculator(test_db)
        fund = complete_fund_data["fund"]

        total_dist = calculator.calculate_total_distributions(fund.id)

        # Expected: 250,000 + 600,000 + 400,000 = 1,250,000
        assert total_dist == Decimal("1250000")

    def test_calculate_dpi_with_real_data(self, test_db, complete_fund_data):
        """Test DPI calculation with real database data"""
        calculator = MetricsCalculator(test_db)
        fund = complete_fund_data["fund"]

        dpi = calculator.calculate_dpi(fund.id)

        # Expected: 1,250,000 / 2,275,000 ≈ 0.549
        assert dpi is not None
        assert dpi == pytest.approx(0.549, abs=0.001)

    def test_calculate_irr_with_real_data(self, test_db, complete_fund_data):
        """Test IRR calculation with real database data"""
        calculator = MetricsCalculator(test_db)
        fund = complete_fund_data["fund"]

        irr = calculator.calculate_irr(fund.id)

        # IRR should be calculated (exact value depends on dates)
        assert irr is not None
        # Should be negative since distributions < capital calls
        assert isinstance(irr, (float, int))

    def test_calculate_all_metrics_with_real_data(self, test_db, complete_fund_data):
        """Test calculating all metrics at once with real data"""
        calculator = MetricsCalculator(test_db)
        fund = complete_fund_data["fund"]

        metrics = calculator.calculate_all_metrics(fund.id)

        # Verify all metrics are present
        assert "pic" in metrics
        assert "dpi" in metrics
        assert "irr" in metrics
        assert "total_distributions" in metrics

        # Verify PIC
        assert metrics["pic"] == 2275000.0

        # Verify total distributions
        assert metrics["total_distributions"] == 1250000.0

        # Verify DPI
        assert metrics["dpi"] == pytest.approx(0.549, abs=0.001)

        # IRR should be calculated or None
        assert metrics["irr"] is None or isinstance(metrics["irr"], (float, int))

    def test_get_calculation_breakdown_dpi_with_real_data(self, test_db, complete_fund_data):
        """Test DPI breakdown with real database data"""
        calculator = MetricsCalculator(test_db)
        fund = complete_fund_data["fund"]

        breakdown = calculator.get_calculation_breakdown(fund.id, "dpi")

        # Verify structure
        assert breakdown["metric"] == "dpi"
        assert "value" in breakdown
        assert "capital_calls" in breakdown
        assert "distributions" in breakdown
        assert "adjustments" in breakdown
        assert "calculation_steps" in breakdown

        # Verify capital calls count
        assert len(breakdown["capital_calls"]) == 3

        # Verify distributions count
        assert len(breakdown["distributions"]) == 3

        # Verify adjustments count
        assert len(breakdown["adjustments"]) == 2

        # Verify calculation steps
        steps = breakdown["calculation_steps"]
        assert "total_capital_calls" in steps
        assert "total_adjustments" in steps
        assert "pic" in steps
        assert "total_distributions" in steps
        assert "dpi" in steps

    def test_get_calculation_breakdown_irr_with_real_data(self, test_db, complete_fund_data):
        """Test IRR breakdown with real database data"""
        calculator = MetricsCalculator(test_db)
        fund = complete_fund_data["fund"]

        breakdown = calculator.get_calculation_breakdown(fund.id, "irr")

        # Verify structure
        assert breakdown["metric"] == "irr"
        assert "value" in breakdown
        assert "cash_flows" in breakdown

        # Verify cash flows
        assert len(breakdown["cash_flows"]) > 0

        # Cash flows should have dates and amounts
        for cf in breakdown["cash_flows"]:
            assert "date" in cf
            assert "amount" in cf
            assert "type" in cf

    def test_calculate_metrics_empty_fund(self, test_db, empty_fund):
        """Test calculations with fund that has no transactions"""
        calculator = MetricsCalculator(test_db)

        # PIC should be 0
        pic = calculator.calculate_pic(empty_fund.id)
        assert pic == Decimal("0")

        # Total distributions should be 0
        total_dist = calculator.calculate_total_distributions(empty_fund.id)
        assert total_dist == Decimal("0")

        # DPI should be 0
        dpi = calculator.calculate_dpi(empty_fund.id)
        assert dpi == 0.0

        # IRR should be None (insufficient data)
        irr = calculator.calculate_irr(empty_fund.id)
        assert irr is None

    def test_calculate_metrics_only_capital_calls(self, test_db, sample_fund, sample_capital_calls):
        """Test calculations with only capital calls (no distributions)"""
        calculator = MetricsCalculator(test_db)

        # PIC should equal sum of capital calls
        pic = calculator.calculate_pic(sample_fund.id)
        assert pic == Decimal("2250000")  # 1M + 500K + 750K

        # Total distributions should be 0
        total_dist = calculator.calculate_total_distributions(sample_fund.id)
        assert total_dist == Decimal("0")

        # DPI should be 0 (no distributions)
        dpi = calculator.calculate_dpi(sample_fund.id)
        assert dpi == 0.0

        # IRR should be None (only negative cash flows)
        irr = calculator.calculate_irr(sample_fund.id)
        assert irr is None

    def test_calculate_metrics_only_distributions(self, test_db, sample_fund, sample_distributions):
        """Test calculations with only distributions (no capital calls)"""
        calculator = MetricsCalculator(test_db)

        # PIC should be 0
        pic = calculator.calculate_pic(sample_fund.id)
        assert pic == Decimal("0")

        # Total distributions
        total_dist = calculator.calculate_total_distributions(sample_fund.id)
        assert total_dist == Decimal("1250000")  # 250K + 600K + 400K

        # DPI should be 0 (can't divide by zero PIC)
        dpi = calculator.calculate_dpi(sample_fund.id)
        assert dpi == 0.0

        # IRR should be None (only positive cash flows)
        irr = calculator.calculate_irr(sample_fund.id)
        assert irr is None


@pytest.mark.integration
class TestMetricsCalculatorScenarios:
    """Test specific fund scenarios"""

    def test_profitable_fund_scenario(self, test_db, sample_fund):
        """Test metrics for a profitable fund (DPI > 1)"""
        from tests.conftest import create_capital_call, create_distribution

        # Create capital calls: $1M total
        create_capital_call(test_db, sample_fund.id, date(2024, 1, 1), Decimal("1000000"))

        # Create distributions: $1.5M total (50% profit)
        create_distribution(test_db, sample_fund.id, date(2024, 6, 1), Decimal("1500000"))

        calculator = MetricsCalculator(test_db)

        # Calculate metrics
        metrics = calculator.calculate_all_metrics(sample_fund.id)

        # PIC = 1M
        assert metrics["pic"] == 1000000.0

        # Distributions = 1.5M
        assert metrics["total_distributions"] == 1500000.0

        # DPI = 1.5 (profitable)
        assert metrics["dpi"] == pytest.approx(1.5, rel=1e-9)

        # IRR should be positive
        if metrics["irr"] is not None:
            assert metrics["irr"] > 0

    def test_underwater_fund_scenario(self, test_db, sample_fund):
        """Test metrics for an underwater fund (DPI < 1)"""
        from tests.conftest import create_capital_call, create_distribution

        # Create capital calls: $1M total
        create_capital_call(test_db, sample_fund.id, date(2024, 1, 1), Decimal("1000000"))

        # Create distributions: $500K total (50% loss)
        create_distribution(test_db, sample_fund.id, date(2024, 12, 31), Decimal("500000"))

        calculator = MetricsCalculator(test_db)

        # Calculate metrics
        metrics = calculator.calculate_all_metrics(sample_fund.id)

        # PIC = 1M
        assert metrics["pic"] == 1000000.0

        # Distributions = 500K
        assert metrics["total_distributions"] == 500000.0

        # DPI = 0.5 (underwater)
        assert metrics["dpi"] == pytest.approx(0.5, rel=1e-9)

        # IRR should be negative
        if metrics["irr"] is not None:
            assert metrics["irr"] < 0

    def test_multiple_calls_and_distributions(self, test_db, sample_fund):
        """Test fund with multiple capital calls and distributions over time"""
        from tests.conftest import create_capital_call, create_distribution

        # Simulate 2-year fund lifecycle
        # Year 1: Multiple capital calls
        create_capital_call(test_db, sample_fund.id, date(2023, 1, 15), Decimal("500000"))
        create_capital_call(test_db, sample_fund.id, date(2023, 6, 15), Decimal("750000"))
        create_capital_call(test_db, sample_fund.id, date(2023, 12, 15), Decimal("1000000"))

        # Year 2: Distributions start coming in
        create_distribution(test_db, sample_fund.id, date(2024, 3, 15), Decimal("300000"))
        create_distribution(test_db, sample_fund.id, date(2024, 6, 15), Decimal("600000"))
        create_distribution(test_db, sample_fund.id, date(2024, 9, 15), Decimal("900000"))
        create_distribution(test_db, sample_fund.id, date(2024, 12, 15), Decimal("500000"))

        calculator = MetricsCalculator(test_db)

        # Calculate metrics
        metrics = calculator.calculate_all_metrics(sample_fund.id)

        # PIC = 500K + 750K + 1M = 2.25M
        assert metrics["pic"] == 2250000.0

        # Total distributions = 300K + 600K + 900K + 500K = 2.3M
        assert metrics["total_distributions"] == 2300000.0

        # DPI = 2.3M / 2.25M ≈ 1.022 (slightly profitable)
        assert metrics["dpi"] == pytest.approx(1.022, abs=0.001)

        # IRR should be positive (though small)
        if metrics["irr"] is not None:
            assert metrics["irr"] >= 0

    def test_fund_with_clawback_adjustments(self, test_db, sample_fund):
        """Test fund with distribution clawbacks"""
        from tests.conftest import create_capital_call, create_distribution, create_adjustment

        # Capital call
        create_capital_call(test_db, sample_fund.id, date(2024, 1, 15), Decimal("1000000"))

        # Distribution (recallable)
        create_distribution(
            test_db, sample_fund.id, date(2024, 6, 15),
            Decimal("800000"), is_recallable=True
        )

        # Clawback adjustment (reduces effective distributions)
        create_adjustment(
            test_db, sample_fund.id, date(2024, 9, 15),
            Decimal("100000"), adjustment_type="Clawback",
            category="Distribution", is_contribution_adjustment=False
        )

        calculator = MetricsCalculator(test_db)

        # Calculate metrics
        pic = calculator.calculate_pic(sample_fund.id)
        total_dist = calculator.calculate_total_distributions(sample_fund.id)

        # PIC = 1M + 100K (clawback increases committed capital)
        # Note: This depends on how clawbacks are accounted
        # If clawback is contribution adjustment: PIC increases
        # If clawback is distribution adjustment: Distributions increase

        # For this test, clawback is NOT contribution adjustment
        assert pic == Decimal("1000000")

        # Distributions = 800K (clawback doesn't reduce this directly)
        assert total_dist == Decimal("800000")

    def test_fund_with_management_fees(self, test_db, sample_fund):
        """Test fund with separate investment and fee capital calls"""
        from tests.conftest import create_capital_call, create_distribution

        # Investment capital
        create_capital_call(
            test_db, sample_fund.id, date(2024, 1, 15),
            Decimal("1000000"), call_type="Investment"
        )

        # Management fee
        create_capital_call(
            test_db, sample_fund.id, date(2024, 1, 15),
            Decimal("100000"), call_type="Management Fee"
        )

        # Distribution
        create_distribution(test_db, sample_fund.id, date(2024, 12, 15), Decimal("1200000"))

        calculator = MetricsCalculator(test_db)

        metrics = calculator.calculate_all_metrics(sample_fund.id)

        # PIC = Investment + Fees = 1M + 100K = 1.1M
        assert metrics["pic"] == 1100000.0

        # DPI = 1.2M / 1.1M ≈ 1.09
        assert metrics["dpi"] == pytest.approx(1.09, abs=0.01)

    def test_fund_complete_lifecycle(self, test_db, sample_fund):
        """Test fund through complete lifecycle: calls, distributions, exit"""
        from tests.conftest import create_capital_call, create_distribution

        # Phase 1: Investment period (Year 1-2)
        create_capital_call(test_db, sample_fund.id, date(2022, 1, 1), Decimal("1000000"))
        create_capital_call(test_db, sample_fund.id, date(2022, 6, 1), Decimal("1000000"))
        create_capital_call(test_db, sample_fund.id, date(2023, 1, 1), Decimal("1000000"))

        # Phase 2: Early distributions (Year 3-4)
        create_distribution(test_db, sample_fund.id, date(2023, 6, 1), Decimal("500000"))
        create_distribution(test_db, sample_fund.id, date(2024, 1, 1), Decimal("750000"))

        # Phase 3: Major exit (Year 5)
        create_distribution(test_db, sample_fund.id, date(2024, 6, 1), Decimal("3000000"))

        calculator = MetricsCalculator(test_db)

        metrics = calculator.calculate_all_metrics(sample_fund.id)

        # PIC = 3M
        assert metrics["pic"] == 3000000.0

        # Total distributions = 4.25M
        assert metrics["total_distributions"] == 4250000.0

        # DPI = 4.25M / 3M ≈ 1.417 (strong performance)
        assert metrics["dpi"] == pytest.approx(1.417, abs=0.001)

        # IRR should be positive and reasonable (not extreme)
        if metrics["irr"] is not None:
            assert metrics["irr"] > 0
            assert metrics["irr"] < 1.0  # Less than 100% (reasonable)


@pytest.mark.integration
@pytest.mark.slow
class TestMetricsCalculatorPerformance:
    """Test calculator performance with large datasets"""

    def test_calculate_with_many_transactions(self, test_db, sample_fund):
        """Test performance with 1000+ transactions"""
        from tests.conftest import create_capital_call, create_distribution
        import time

        # Create 500 capital calls
        for i in range(500):
            create_capital_call(
                test_db, sample_fund.id,
                date(2020 + i // 365, 1 + (i % 12), 1 + (i % 28)),
                Decimal(str(10000 + i * 100))
            )

        # Create 500 distributions
        for i in range(500):
            create_distribution(
                test_db, sample_fund.id,
                date(2021 + i // 365, 1 + (i % 12), 1 + (i % 28)),
                Decimal(str(8000 + i * 80))
            )

        calculator = MetricsCalculator(test_db)

        # Measure calculation time
        start = time.time()
        metrics = calculator.calculate_all_metrics(sample_fund.id)
        elapsed = time.time() - start

        # Should complete in reasonable time (< 1 second)
        assert elapsed < 1.0

        # Should return valid metrics
        assert metrics["pic"] > 0
        assert metrics["total_distributions"] > 0
        assert metrics["dpi"] > 0
