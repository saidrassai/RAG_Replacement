class LatticeJitError(Exception):
    """Base application error."""


class NotFoundError(LatticeJitError):
    """Raised when a requested resource cannot be located."""


class ValidationFailure(LatticeJitError):
    """Raised when inputs fail domain validation."""
