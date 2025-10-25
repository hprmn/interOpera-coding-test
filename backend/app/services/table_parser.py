"""
Table parser service for extracting and classifying tables from PDF documents
"""
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import date, datetime
from dateutil import parser as date_parser
import re


class TableParser:
    """Parse tables from PDF documents and classify them"""

    def __init__(self):
        pass

    def parse_table(self, table: List[List[str]], fund_id: int) -> Dict[str, Any]:
        """
        Parse a table and return structured data

        Args:
            table: List of rows, where each row is a list of cells
            fund_id: Fund ID for the transactions

        Returns:
            Dictionary with type and parsed data
        """
        if not table or len(table) < 2:  # Need at least header + 1 row
            return {"type": "unknown", "data": [], "error": "Table too small"}

        table_type = self._classify_table(table)

        if table_type == "capital_call":
            return {"type": "capital_call", "data": self._parse_capital_calls(table, fund_id)}
        elif table_type == "distribution":
            return {"type": "distribution", "data": self._parse_distributions(table, fund_id)}
        elif table_type == "adjustment":
            return {"type": "adjustment", "data": self._parse_adjustments(table, fund_id)}

        return {"type": "unknown", "data": [], "error": "Could not classify table"}

    def _classify_table(self, table: List[List[str]]) -> str:
        """
        Classify table type based on headers and content

        Args:
            table: List of rows

        Returns:
            Table type: 'capital_call', 'distribution', 'adjustment', or 'unknown'
        """
        if not table or not table[0]:
            return "unknown"

        # Join all cells in the first row (header) and convert to lowercase
        header = " ".join([str(cell).lower() if cell else "" for cell in table[0]])

        # Capital call keywords
        if any(keyword in header for keyword in ["capital call", "contribution", "call date", "called", "call number"]):
            return "capital_call"

        # Distribution keywords
        if any(keyword in header for keyword in ["distribution", "distributed", "dividend", "recallable"]):
            return "distribution"

        # Adjustment keywords
        if any(keyword in header for keyword in ["adjustment", "rebalance", "clawback", "refund"]):
            return "adjustment"

        # If header doesn't match, check first few data rows for keywords
        # This helps with generic headers like "Date, Type, Amount, Description"
        if len(table) > 1:
            # Check first 3 data rows (skip header)
            sample_rows = " ".join([
                " ".join([str(cell).lower() if cell else "" for cell in row])
                for row in table[1:min(4, len(table))]
            ])

            # Check for adjustment keywords in data
            if any(keyword in sample_rows for keyword in ["adjustment", "rebalance", "clawback", "refund", "recallable distribution"]):
                return "adjustment"

            # Check for capital call keywords in data
            if any(keyword in sample_rows for keyword in ["call 1", "call 2", "call 3", "call 4", "initial capital", "follow-on"]):
                return "capital_call"

        return "unknown"

    def _parse_capital_calls(self, table: List[List[str]], fund_id: int) -> List[Dict[str, Any]]:
        """Parse capital call table"""
        calls = []

        # Skip header row
        for row in table[1:]:
            if not row or len(row) < 2:
                continue

            try:
                # Try to extract date and amount from the row
                call_date = None
                amount = None
                call_type = None
                description = None

                # Iterate through cells to find date and amount
                for i, cell in enumerate(row):
                    if not cell:
                        continue

                    # Try to parse as date
                    if call_date is None:
                        parsed_date = self._parse_date(str(cell))
                        if parsed_date:
                            call_date = parsed_date
                            continue

                    # Try to parse as amount
                    if amount is None:
                        parsed_amount = self._parse_amount(str(cell))
                        if parsed_amount and parsed_amount > 0:
                            amount = parsed_amount
                            continue

                    # Everything else might be description or type
                    cell_str = str(cell).strip()
                    if cell_str and cell_str.lower() not in ['date', 'amount', 'description']:
                        if call_type is None and len(cell_str) < 50:
                            call_type = cell_str
                        elif description is None:
                            description = cell_str

                # Only add if we have at least date and amount
                if call_date and amount:
                    calls.append({
                        "fund_id": fund_id,
                        "call_date": call_date,
                        "amount": amount,
                        "call_type": call_type or "Investment",
                        "description": description
                    })

            except Exception as e:
                print(f"Error parsing capital call row: {e}")
                continue

        return calls

    def _parse_distributions(self, table: List[List[str]], fund_id: int) -> List[Dict[str, Any]]:
        """Parse distribution table"""
        distributions = []

        # Skip header row
        for row in table[1:]:
            if not row or len(row) < 2:
                continue

            try:
                distribution_date = None
                amount = None
                distribution_type = None
                is_recallable = False
                description = None

                # Iterate through cells
                for i, cell in enumerate(row):
                    if not cell:
                        continue

                    cell_str = str(cell).strip()

                    # Try to parse as date
                    if distribution_date is None:
                        parsed_date = self._parse_date(cell_str)
                        if parsed_date:
                            distribution_date = parsed_date
                            continue

                    # Try to parse as amount
                    if amount is None:
                        parsed_amount = self._parse_amount(cell_str)
                        if parsed_amount and parsed_amount > 0:
                            amount = parsed_amount
                            continue

                    # Check for recallable flag
                    if cell_str.lower() in ['yes', 'true', 'recallable']:
                        is_recallable = True
                        continue

                    # Type or description
                    if cell_str and cell_str.lower() not in ['date', 'amount', 'description', 'no', 'false']:
                        if distribution_type is None and len(cell_str) < 50:
                            distribution_type = cell_str
                        elif description is None:
                            description = cell_str

                # Only add if we have at least date and amount
                if distribution_date and amount:
                    distributions.append({
                        "fund_id": fund_id,
                        "distribution_date": distribution_date,
                        "amount": amount,
                        "distribution_type": distribution_type or "Return of Capital",
                        "is_recallable": is_recallable,
                        "description": description
                    })

            except Exception as e:
                print(f"Error parsing distribution row: {e}")
                continue

        return distributions

    def _parse_adjustments(self, table: List[List[str]], fund_id: int) -> List[Dict[str, Any]]:
        """Parse adjustment table"""
        adjustments = []

        # Skip header row
        for row in table[1:]:
            if not row or len(row) < 2:
                continue

            try:
                adjustment_date = None
                amount = None
                adjustment_type = None
                category = None
                is_contribution_adjustment = False
                description = None

                # Iterate through cells
                for i, cell in enumerate(row):
                    if not cell:
                        continue

                    cell_str = str(cell).strip()

                    # Try to parse as date
                    if adjustment_date is None:
                        parsed_date = self._parse_date(cell_str)
                        if parsed_date:
                            adjustment_date = parsed_date
                            continue

                    # Try to parse as amount (can be negative)
                    if amount is None:
                        parsed_amount = self._parse_amount(cell_str)
                        if parsed_amount != 0:
                            amount = parsed_amount
                            continue

                    # Check for contribution adjustment flag
                    if 'contribution' in cell_str.lower() or 'capital call' in cell_str.lower():
                        is_contribution_adjustment = True

                    # Type, category, or description
                    if cell_str and cell_str.lower() not in ['date', 'amount', 'description', 'type', 'category']:
                        if adjustment_type is None and len(cell_str) < 50:
                            adjustment_type = cell_str
                        elif category is None and len(cell_str) < 50:
                            category = cell_str
                        elif description is None:
                            description = cell_str

                # Only add if we have at least date and amount
                if adjustment_date and amount is not None:
                    adjustments.append({
                        "fund_id": fund_id,
                        "adjustment_date": adjustment_date,
                        "amount": amount,
                        "adjustment_type": adjustment_type or "Rebalance",
                        "category": category,
                        "is_contribution_adjustment": is_contribution_adjustment,
                        "description": description
                    })

            except Exception as e:
                print(f"Error parsing adjustment row: {e}")
                continue

        return adjustments

    def _parse_date(self, date_str: str) -> Optional[date]:
        """
        Parse various date formats

        Args:
            date_str: String containing a date

        Returns:
            date object or None if parsing fails
        """
        if not date_str or not isinstance(date_str, str):
            return None

        try:
            # Remove common extra text
            date_str = date_str.strip()

            # Try dateutil parser (handles many formats)
            parsed = date_parser.parse(date_str, fuzzy=True)
            return parsed.date()
        except:
            return None

    def _parse_amount(self, amount_str: str) -> Optional[Decimal]:
        """
        Parse amount strings like '$1,000,000.00', '(500,000)', etc.

        Args:
            amount_str: String containing an amount

        Returns:
            Decimal amount or None if parsing fails
        """
        if not amount_str or not isinstance(amount_str, str):
            return None

        try:
            # Remove whitespace
            original = amount_str.strip()

            # Reject if it contains letters (e.g., "Call 1", "Call Number")
            # But allow currency symbols ($, €, £, etc.)
            if re.search(r'[a-zA-Z]', original):
                return None

            # Check if it looks like a monetary amount:
            # - Has currency symbol ($, €, £)
            # - Has comma separator (1,000,000)
            # - Has decimal point with 2 digits (.00)
            # - Or is a large number (4+ digits)
            has_currency = bool(re.search(r'[$€£¥]', original))
            has_separator = ',' in original
            has_decimal = bool(re.match(r'.*\.\d{2}$', original))

            cleaned = original

            # Check if amount is negative (parentheses notation)
            is_negative = cleaned.startswith('(') and cleaned.endswith(')')
            if is_negative:
                cleaned = cleaned[1:-1]

            # Check for explicit negative sign
            if cleaned.startswith('-'):
                is_negative = True
                cleaned = cleaned[1:]

            # Remove all non-digit and non-decimal point characters
            cleaned = re.sub(r'[^\d.]', '', cleaned)

            if not cleaned:
                return None

            # Convert to Decimal
            amount = Decimal(cleaned)

            # Reject very small amounts unless they have indicators of being monetary
            # This prevents "Call 1" → 1, "Call 2" → 2, etc.
            if amount < 100 and not (has_currency or has_separator or has_decimal):
                return None

            # Apply negative sign if needed
            if is_negative:
                amount = -amount

            return amount
        except:
            return None
