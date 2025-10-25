"""
Pytest configuration and fixtures

Provides common test fixtures for database sessions, mock data, and test utilities
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.models.fund import Fund
from app.models.transaction import CapitalCall, Distribution, Adjustment
from app.models.document import Document
from datetime import date
from decimal import Decimal


@pytest.fixture(scope="function")
def test_db():
    """
    Create an in-memory SQLite database for testing

    Uses StaticPool to ensure the same database is used across threads
    Automatically creates all tables and tears down after each test
    """
    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def sample_fund(test_db):
    """Create a sample fund for testing"""
    fund = Fund(
        name="Test Venture Fund I",
        gp_name="Test Capital Partners",
        vintage_year=2024,
        fund_size=Decimal("100000000"),  # $100M fund
        commitment_amount=Decimal("5000000")  # $5M commitment
    )
    test_db.add(fund)
    test_db.commit()
    test_db.refresh(fund)
    return fund


@pytest.fixture(scope="function")
def sample_capital_calls(test_db, sample_fund):
    """Create sample capital calls for testing"""
    calls = [
        CapitalCall(
            fund_id=sample_fund.id,
            call_date=date(2024, 1, 15),
            amount=Decimal("1000000"),
            call_type="Investment",
            description="Initial capital call for Series A investments"
        ),
        CapitalCall(
            fund_id=sample_fund.id,
            call_date=date(2024, 3, 20),
            amount=Decimal("500000"),
            call_type="Management Fee",
            description="Q1 2024 management fee"
        ),
        CapitalCall(
            fund_id=sample_fund.id,
            call_date=date(2024, 6, 15),
            amount=Decimal("750000"),
            call_type="Investment",
            description="Follow-on investments in portfolio companies"
        ),
    ]

    for call in calls:
        test_db.add(call)

    test_db.commit()

    for call in calls:
        test_db.refresh(call)

    return calls


@pytest.fixture(scope="function")
def sample_distributions(test_db, sample_fund):
    """Create sample distributions for testing"""
    distributions = [
        Distribution(
            fund_id=sample_fund.id,
            distribution_date=date(2024, 4, 10),
            amount=Decimal("250000"),
            distribution_type="Dividend",
            is_recallable=False,
            description="Dividend from portfolio company A"
        ),
        Distribution(
            fund_id=sample_fund.id,
            distribution_date=date(2024, 7, 25),
            amount=Decimal("600000"),
            distribution_type="Return of Capital",
            is_recallable=False,
            description="Exit proceeds from company B"
        ),
        Distribution(
            fund_id=sample_fund.id,
            distribution_date=date(2024, 9, 30),
            amount=Decimal("400000"),
            distribution_type="Realized Gain",
            is_recallable=True,
            description="Q3 distributions - subject to recall"
        ),
    ]

    for dist in distributions:
        test_db.add(dist)

    test_db.commit()

    for dist in distributions:
        test_db.refresh(dist)

    return distributions


@pytest.fixture(scope="function")
def sample_adjustments(test_db, sample_fund):
    """Create sample adjustments for testing"""
    adjustments = [
        Adjustment(
            fund_id=sample_fund.id,
            adjustment_date=date(2024, 5, 15),
            amount=Decimal("50000"),
            adjustment_type="Rebalance",
            category="Distribution Clawback",
            is_contribution_adjustment=False,
            description="Clawback of recallable distribution"
        ),
        Adjustment(
            fund_id=sample_fund.id,
            adjustment_date=date(2024, 8, 10),
            amount=Decimal("-25000"),
            adjustment_type="Refund",
            category="Capital Call Adjustment",
            is_contribution_adjustment=True,
            description="Refund of overcalled capital"
        ),
    ]

    for adj in adjustments:
        test_db.add(adj)

    test_db.commit()

    for adj in adjustments:
        test_db.refresh(adj)

    return adjustments


@pytest.fixture(scope="function")
def sample_document(test_db, sample_fund):
    """Create a sample document for testing"""
    document = Document(
        fund_id=sample_fund.id,
        file_name="Q1_2024_Report.pdf",
        file_path="/uploads/20240115_Q1_2024_Report.pdf",
        parsing_status="completed",
        error_message=None
    )

    test_db.add(document)
    test_db.commit()
    test_db.refresh(document)

    return document


@pytest.fixture(scope="function")
def complete_fund_data(test_db, sample_fund, sample_capital_calls,
                        sample_distributions, sample_adjustments):
    """
    Create a complete fund with all transaction types

    Returns a dict with:
    - fund: Fund object
    - capital_calls: List of CapitalCall objects
    - distributions: List of Distribution objects
    - adjustments: List of Adjustment objects
    """
    return {
        "fund": sample_fund,
        "capital_calls": sample_capital_calls,
        "distributions": sample_distributions,
        "adjustments": sample_adjustments
    }


@pytest.fixture(scope="function")
def empty_fund(test_db):
    """Create a fund with no transactions"""
    fund = Fund(
        name="Empty Fund",
        gp_name="Test GP",
        vintage_year=2024,
        fund_size=Decimal("50000000"),
        commitment_amount=Decimal("2500000")
    )
    test_db.add(fund)
    test_db.commit()
    test_db.refresh(fund)
    return fund


# Helper functions for testing

def create_capital_call(db, fund_id, call_date, amount, call_type="Investment", description=None):
    """Helper to create a capital call"""
    call = CapitalCall(
        fund_id=fund_id,
        call_date=call_date,
        amount=amount,
        call_type=call_type,
        description=description
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


def create_distribution(db, fund_id, distribution_date, amount,
                        distribution_type="Return of Capital",
                        is_recallable=False, description=None):
    """Helper to create a distribution"""
    dist = Distribution(
        fund_id=fund_id,
        distribution_date=distribution_date,
        amount=amount,
        distribution_type=distribution_type,
        is_recallable=is_recallable,
        description=description
    )
    db.add(dist)
    db.commit()
    db.refresh(dist)
    return dist


def create_adjustment(db, fund_id, adjustment_date, amount,
                      adjustment_type="Rebalance", category=None,
                      is_contribution_adjustment=False, description=None):
    """Helper to create an adjustment"""
    adj = Adjustment(
        fund_id=fund_id,
        adjustment_date=adjustment_date,
        amount=amount,
        adjustment_type=adjustment_type,
        category=category,
        is_contribution_adjustment=is_contribution_adjustment,
        description=description
    )
    db.add(adj)
    db.commit()
    db.refresh(adj)
    return adj


# Pytest configuration

def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


# Async test support

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
