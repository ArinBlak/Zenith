class BinanceBotError(Exception):
    """Base application error."""


class ConfigError(BinanceBotError):
    """Raised when configuration is missing or invalid."""


class InputValidationError(BinanceBotError):
    """Raised when CLI input is invalid."""


class BinanceAPIError(Exception):
    def __init__(self, code=None, message=""):
        self.code = code
        self.message = message
        super().__init__(message)

    """Raised when Binance API returns an error response."""


class NetworkError(BinanceBotError):
    """Raised when network communication fails."""
