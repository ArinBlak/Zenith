"""RSI (Relative Strength Index) indicator calculation."""

import logging
from typing import List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("indicators.rsi")


class RSICalculator:
    """Calculate RSI indicator from price data."""
    
    def __init__(self, period: int = 14):
        """Initialize RSI calculator.
        
        Args:
            period: RSI period (default: 14)
        """
        self.period = period
    
    def calculate(self, prices: List[float]) -> Optional[float]:
        """Calculate RSI from a list of prices.
        
        Args:
            prices: List of closing prices (most recent last)
        
        Returns:
            RSI value (0-100) or None if insufficient data
        """
        if len(prices) < self.period + 1:
            logger.warning(f"Insufficient data for RSI calculation. Need {self.period + 1}, got {len(prices)}")
            return None
        
        # Calculate price changes
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        # Separate gains and losses
        gains = [max(d, 0) for d in deltas]
        losses = [abs(min(d, 0)) for d in deltas]
        
        # Calculate initial average gain and loss
        avg_gain = sum(gains[:self.period]) / self.period
        avg_loss = sum(losses[:self.period]) / self.period
        
        # Calculate smoothed averages for remaining periods
        for i in range(self.period, len(gains)):
            avg_gain = (avg_gain * (self.period - 1) + gains[i]) / self.period
            avg_loss = (avg_loss * (self.period - 1) + losses[i]) / self.period
        
        # Calculate RSI
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return round(rsi, 2)
    
    @staticmethod
    async def fetch_from_binance(client, symbol: str, interval: str = "1h", limit: int = 100) -> List[float]:
        """Fetch historical candle data from Binance for RSI calculation.
        
        Args:
            client: BinanceFuturesClient instance
            symbol: Trading symbol (e.g., "BTCUSDT")
            interval: Candle interval (default: "1h")
            limit: Number of candles to fetch (default: 100)
        
        Returns:
            List of closing prices
        """
        try:
            # Binance klines endpoint
            from binance_bot.client import BinanceFuturesClient
            
            # Use public endpoint for klines
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            
            klines = client._send_public_request("GET", "/fapi/v1/klines", params)
            
            # Extract closing prices (index 4 in kline data)
            # Kline format: [open_time, open, high, low, close, volume, close_time, ...]
            prices = [float(kline[4]) for kline in klines]
            
            logger.info(f"Fetched {len(prices)} candles for {symbol}")
            return prices
        
        except Exception as e:
            logger.error(f"Error fetching candle data: {e}")
            return []
