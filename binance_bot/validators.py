from .exceptions import InputValidationError

VALID_SIDES = {"BUY", "SELL"}
VALID_TYPES = {"MARKET", "LIMIT"}



def normalize_and_validate(symbol: str, side: str, order_type: str, quantity: float, price: float | None) -> dict:
    normalized_symbol = symbol.strip().upper()
    normalized_side = side.strip().upper()
    normalized_type = order_type.strip().upper()

    if not normalized_symbol:
        raise InputValidationError("Symbol cannot be empty.")

    if normalized_side not in VALID_SIDES:
        raise InputValidationError("Side must be BUY or SELL.")

    if normalized_type not in VALID_TYPES:
        raise InputValidationError("Order type must be MARKET or LIMIT.")

    if quantity <= 0:
        raise InputValidationError("Quantity must be greater than 0.")

    if normalized_type == "LIMIT":
        if price is None:
            raise InputValidationError("Price is required for LIMIT orders.")
        if price <= 0:
            raise InputValidationError("Price must be greater than 0 for LIMIT orders.")

    if normalized_type == "MARKET" and price is not None:
        raise InputValidationError("Price must not be provided for MARKET orders.")

    return {
        "symbol": normalized_symbol,
        "side": normalized_side,
        "order_type": normalized_type,
        "quantity": quantity,
        "price": price,
    }
