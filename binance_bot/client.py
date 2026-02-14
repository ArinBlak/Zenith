import hashlib
import hmac
import logging
import time
from typing import Any
from urllib.parse import urlencode

import requests

from .config import BinanceConfig
from .exceptions import BinanceAPIError, NetworkError


class BinanceFuturesClient:
    def __init__(self, config: BinanceConfig, timeout_seconds: int = 15) -> None:
        self._config = config
        self._timeout = timeout_seconds
        self._logger = logging.getLogger(self.__class__.__name__)
        self._session = requests.Session()
        self._session.headers.update({"X-MBX-APIKEY": self._config.api_key})
        self._exchange_info_cache = {}  # Cache for exchange info to avoid repeated API calls

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        stop_price: float | None = None,
        callback_rate: float | None = None,
        reduce_only: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": self._format_number(quantity),
            "timestamp": self._timestamp_ms(),
            "recvWindow": 5000,
            "newOrderRespType": "RESULT",
            "reduceOnly": "true" if reduce_only else "false",
        }

        if order_type in ["LIMIT", "STOP", "TAKE_PROFIT"]:
            params["price"] = self._format_number(price)
            params["timeInForce"] = "GTC"

        if order_type in ["STOP", "TAKE_PROFIT", "STOP_MARKET", "TAKE_PROFIT_MARKET"]:
            if stop_price is None:
                raise ValueError(f"stop_price is required for {order_type}")
            params["stopPrice"] = self._format_number(stop_price)

        if order_type == "TRAILING_STOP_MARKET":
            if callback_rate is None:
                raise ValueError("callback_rate is required for TRAILING_STOP_MARKET")
            params["callbackRate"] = callback_rate

        response = self._send_signed_request("POST", "/fapi/v1/order", params)

        if order_type == "MARKET":
            order_id = response.get("orderId")
            if order_id is not None:
                details = self.get_order(symbol=symbol, order_id=int(order_id))
                response = {**response, **details}

        return response

    def get_order(self, symbol: str, order_id: int) -> dict[str, Any]:
        params = {
            "symbol": symbol,
            "orderId": order_id,
            "timestamp": self._timestamp_ms(),
            "recvWindow": 5000,
        }
        return self._send_signed_request("GET", "/fapi/v1/order", params)

    def get_symbol_price(self, symbol: str) -> float:
        response = self._send_signed_request("GET", "/fapi/v1/ticker/price", {"symbol": symbol})
        return float(response["price"])

    def _send_signed_request(
        self, method: str, path: str, params: dict[str, Any]
    ) -> dict[str, Any] | list[Any]:
        query_string = urlencode(params)
        signature = self._sign(query_string)
        final_query = f"{query_string}&signature={signature}"
        url = f"{self._config.base_url}{path}"

        self._logger.info("API request | method=%s url=%s params=%s", method, url, params)

        try:
            response = self._session.request(
                method=method,
                url=url,
                params=final_query,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            self._logger.exception("Network failure while calling Binance")
            raise NetworkError(f"Network error: {exc}") from exc

        body: dict[str, Any] | str
        try:
            body = response.json()
        except ValueError:
            body = response.text

        self._logger.info(
            "API response | status_code=%s body=%s", response.status_code, body
        )

        if response.status_code >= 400:
            if isinstance(body, dict):
                code = body.get("code", "unknown")
                msg = body.get("msg", "no message")
                raise BinanceAPIError(code=code, message=msg)
            raise BinanceAPIError(f"Binance API HTTP {response.status_code}: {body}")

        if not isinstance(body, (dict, list)):
            raise BinanceAPIError("Unexpected API response format.")

        return body

    def get_account_info(self) -> dict[str, Any]:
        """Get account information including balance and PnL.
        
        Returns:
            Account info with totalWalletBalance, totalUnrealizedProfit, etc.
        """
        params = {
            "timestamp": self._timestamp_ms(),
            "recvWindow": 5000
        }
        return self._send_signed_request("GET", "/fapi/v2/account", params)

    def get_position_info(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Get position information.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of positions with entry price, quantity, leverage, etc.
        """
        params = {
            "timestamp": self._timestamp_ms(),
            "recvWindow": 5000
        }
        if symbol:
            params["symbol"] = symbol
        
        result = self._send_signed_request("GET", "/fapi/v2/positionRisk", params)
        # Ensure we return a list
        if isinstance(result, list):
            return result
        return []


    def get_account_trades(self, symbol: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        """Get account trade history.
        
        Args:
            symbol: Optional symbol filter
            limit: Number of trades to fetch (max 1000)
            
        Returns:
            List of executed trades with realizedPnl, commission, etc.
        """
        params = {
            "timestamp": self._timestamp_ms(),
            "recvWindow": 5000,
            "limit": min(limit, 1000)  # Binance max is 1000
        }
        if symbol:
            params["symbol"] = symbol
        
        result = self._send_signed_request("GET", "/fapi/v1/userTrades", params)
        return result if isinstance(result, list) else []


    def get_exchange_info(self, symbol: str) -> dict[str, Any]:
        """Get exchange info for a symbol including precision and filters.
        
        Caches results to avoid repeated API calls.
        
        Returns:
            Dict with keys: pricePrecision, quantityPrecision, minNotional, minQty, maxQty
        """
        if symbol in self._exchange_info_cache:
            return self._exchange_info_cache[symbol]
        
        # Fetch exchange info from Binance
        url = f"{self._config.base_url}/fapi/v1/exchangeInfo"
        try:
            response = self._session.get(url, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            self._logger.error(f"Failed to fetch exchange info: {e}")
            raise NetworkError(f"Failed to fetch exchange info: {e}")
        
        # Find symbol info
        symbol_info = None
        for s in data.get("symbols", []):
            if s["symbol"] == symbol:
                symbol_info = s
                break
        
        if not symbol_info:
            raise BinanceAPIError(f"Symbol {symbol} not found in exchange info")
        
        # Extract precision and filters
        price_precision = symbol_info.get("pricePrecision", 2)
        quantity_precision = symbol_info.get("quantityPrecision", 3)
        
        # Extract filters
        min_notional = 5.0  # Default minimum
        min_qty = 0.001
        max_qty = 10000000
        tick_size = 0.01  # Default tick size
        
        for filter_item in symbol_info.get("filters", []):
            if filter_item["filterType"] == "MIN_NOTIONAL":
                min_notional = float(filter_item.get("notional", 5.0))
            elif filter_item["filterType"] == "LOT_SIZE":
                min_qty = float(filter_item.get("minQty", 0.001))
                max_qty = float(filter_item.get("maxQty", 10000000))
            elif filter_item["filterType"] == "PRICE_FILTER":
                tick_size = float(filter_item.get("tickSize", 0.01))
        
        result = {
            "pricePrecision": price_precision,
            "quantityPrecision": quantity_precision,
            "minNotional": min_notional,
            "minQty": min_qty,
            "maxQty": max_qty,
            "tickSize": tick_size
        }
        
        # Cache the result
        self._exchange_info_cache[symbol] = result
        self._logger.info(f"Cached exchange info for {symbol}: {result}")
        
        return result

    def format_price(self, symbol: str, price: float) -> float:
        """Format price to correct tick size for the symbol.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            price: Raw price value
            
        Returns:
            Price rounded to exchange-specific tick size
        """
        info = self.get_exchange_info(symbol)
        tick_size = info["tickSize"]
        
        # Round to nearest tick size
        # Formula: round(price / tickSize) * tickSize
        precision = info["pricePrecision"]
        rounded_price = round(round(price / tick_size) * tick_size, precision)
        
        return rounded_price

    def format_quantity(self, symbol: str, quantity: float) -> float:
        """Format quantity to correct decimal places for the symbol.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            quantity: Raw quantity value
            
        Returns:
            Quantity rounded to exchange-specific precision
        """
        info = self.get_exchange_info(symbol)
        precision = info["quantityPrecision"]
        return round(quantity, precision)

    def calculate_min_quantity(self, symbol: str, price: float) -> float:
        """Calculate minimum quantity needed to meet minimum notional value.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            price: Order price
            
        Returns:
            Minimum quantity that satisfies both minQty and minNotional requirements
        """
        info = self.get_exchange_info(symbol)
        min_notional = info["minNotional"]
        min_qty = info["minQty"]
        
        # Calculate quantity needed for minimum notional
        qty_for_notional = min_notional / price
        
        # Take the larger of minQty and qty_for_notional
        min_quantity = max(min_qty, qty_for_notional)
        
        # Round up to next valid precision to ensure we meet minimum
        precision = info["quantityPrecision"]
        multiplier = 10 ** precision
        min_quantity = round(min_quantity * multiplier + 0.5) / multiplier
        
        return min_quantity

    def _timestamp_ms(self) -> int:
        return int(time.time() * 1000)

    def _sign(self, query_string: str) -> str:
        return hmac.new(
            self._config.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def get_account_info(self) -> dict[str, Any]:
        """Fetch account balance, margin, and risk details."""
        params = {"timestamp": self._timestamp_ms(), "recvWindow": 5000}
        return self._send_signed_request("GET", "/fapi/v2/account", params)

    def get_position_risk(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Fetch current open positions."""
        params = {"timestamp": self._timestamp_ms(), "recvWindow": 5000}
        if symbol:
            params["symbol"] = symbol
        return self._send_signed_request("GET", "/fapi/v2/positionRisk", params)
    
    def get_active_symbols(self) -> list[str]:
        """Get list of symbols with active positions.
        
        Returns:
            List of symbols that have non-zero positions
        """
        try:
            positions = self.get_position_risk()
            active = [
                p["symbol"] for p in positions 
                if float(p.get("positionAmt", 0)) != 0
            ]
            return active if active else ["BTCUSDT", "ETHUSDT"]  # Default symbols
        except Exception as e:
            self._logger.warning(f"Error getting active symbols: {e}")
            return ["BTCUSDT", "ETHUSDT"]  # Default fallback

    @staticmethod
    def _format_number(value: float | None) -> str:
        if value is None:
            raise ValueError("Numeric value cannot be None.")
        return f"{value:.8f}".rstrip("0").rstrip(".")

