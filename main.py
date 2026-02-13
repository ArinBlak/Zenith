import argparse
import logging
import sys

from binance_bot.exceptions import BinanceAPIError, BinanceBotError, NetworkError
from binance_bot.logging_config import configure_logging
from binance_bot.validators import normalize_and_validate


logger = logging.getLogger("cli")



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Place MARKET or LIMIT orders on Binance Futures Testnet (USDT-M)."
    )
    parser.add_argument("--symbol", required=True, help="Trading symbol, e.g. BTCUSDT")
    parser.add_argument("--side", required=True, help="BUY or SELL")
    parser.add_argument("--type", required=True, dest="order_type", help="MARKET or LIMIT")
    parser.add_argument("--quantity", required=True, type=float, help="Order quantity")
    parser.add_argument(
        "--price",
        type=float,
        default=None,
        help="Limit price (required for LIMIT, omitted for MARKET)",
    )
    parser.add_argument(
        "--stop-price",
        type=float,
        default=None,
        help="Trigger price for STOP/TAKE_PROFIT orders",
    )
    parser.add_argument(
        "--callback-rate",
        type=float,
        default=None,
        help="Callback rate for TRAILING_STOP_MARKET (0.1 to 5.0)",
    )
    return parser.parse_args()



def print_summary(payload: dict) -> None:
    print("Order request summary")
    print(f"  symbol: {payload['symbol']}")
    print(f"  side: {payload['side']}")
    print(f"  type: {payload['order_type']}")
    print(f"  quantity: {payload['quantity']}")
    print(f"  price: {payload['price'] if payload['price'] is not None else 'N/A'}")



def print_response(resp: dict) -> None:
    avg_price = resp.get("avgPrice")
    if avg_price in (None, "", "0.00000", "0"):
        avg_price = "N/A"

    print("Order response details")
    print(f"  orderId: {resp.get('orderId', 'N/A')}")
    print(f"  status: {resp.get('status', 'N/A')}")
    print(f"  executedQty: {resp.get('executedQty', 'N/A')}")
    print(f"  avgPrice: {avg_price}")



def run() -> int:
    args = parse_args()
    configure_logging()

    try:
        payload = normalize_and_validate(
            symbol=args.symbol,
            side=args.side,
            order_type=args.order_type,
            quantity=args.quantity,
            price=args.price,
        )
        if args.order_type in ["STOP", "TAKE_PROFIT"] and args.stop_price is None:
             raise ValueError(f"--stop-price is required for {args.order_type}")

        from binance_bot.client import BinanceFuturesClient
        from binance_bot.config import load_config

        config = load_config()
        client = BinanceFuturesClient(config)

        print_summary(payload)
        response = client.place_order(
            symbol=payload["symbol"],
            side=payload["side"],
            order_type=payload["order_type"],
            quantity=payload["quantity"],
            price=payload["price"],
            stop_price=args.stop_price,
            callback_rate=args.callback_rate,
        )

        print_response(response)
        print("SUCCESS: order placed on Binance Futures Testnet.")
        return 0

    except (BinanceBotError, BinanceAPIError, NetworkError) as exc:
        logger.exception("Order placement failed")
        print(f"FAILURE: {exc}")
        return 1
    except Exception as exc:  # defensive catch-all
        logger.exception("Unexpected error")
        print(f"FAILURE: unexpected error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(run())
