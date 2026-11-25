"""Custom exceptions. The API maps these to clear HTTP responses (SPEC section 16).

InvalidAssumptionError -> HTTP 422 (the user's inputs cannot produce a valid valuation)
DataUnavailableError   -> HTTP 503 (required data could not be loaded)
"""


class DcfError(Exception):
    """Base class for all engine errors."""


class InvalidAssumptionError(DcfError):
    """An assumption is out of bounds or inconsistent (e.g. terminal growth >= WACC)."""


class DataUnavailableError(DcfError):
    """Required financial data is missing, empty or failed quality checks."""
