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

    @staticmethod
    def _format_number(value: float | None) -> str:
        if value is None:
            raise ValueError("Numeric value cannot be None.")
        return f"{value:.8f}".rstrip("0").rstrip(".")
