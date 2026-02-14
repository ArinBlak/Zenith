import time
import logging
from typing import Optional
from binance_bot.client import BinanceFuturesClient

logger = logging.getLogger("strategy.grid")

class GridStrategy:
    def __init__(
        self,
        client: BinanceFuturesClient,
        symbol: str,
        lower_price: float,
        upper_price: float,
        grids: int,
        quantity_per_grid: float,
        sentiment_threshold: Optional[int] = None,
        sentiment_worker = None
    ):
        self.client = client
        self.symbol = symbol
        self.lower_price = lower_price
        self.upper_price = upper_price
        self.grids = grids
        self.quantity_per_grid = quantity_per_grid
        self.sentiment_threshold = sentiment_threshold
        self.sentiment_worker = sentiment_worker
        
        if grids < 2:
            raise ValueError("grids must be >= 2")

        self.step = (upper_price - lower_price) / (grids - 1)

    def _check_sentiment(self) -> bool:
        """Check if sentiment is above threshold for trading.
        
        Returns:
            True if sentiment is acceptable, False if should pause
        """
        if not self.sentiment_worker or not self.sentiment_threshold:
            return True  # No sentiment restrictions
        
        try:
            sentiment = self.sentiment_worker.get_sentiment(self.symbol)
            score = sentiment.get("score", 50)
            label = sentiment.get("label", "Neutral")
            
            if score < self.sentiment_threshold:
                logger.warning(
                    f"Grid paused: Sentiment score ({score}) below threshold ({self.sentiment_threshold})"
                )
                return False
            
            logger.info(f"Sentiment check passed for {self.symbol}: {label} ({score})")
            return True
        
        except Exception as e:
            logger.error(f"Error checking sentiment: {e}. Proceeding with grid.")
            return True  # On error, proceed normally

    def run(self):
        logger.info(f"Starting Grid: {self.grids} grids from {self.lower_price} to {self.upper_price} on {self.symbol}")
        
        if self.sentiment_threshold:
            logger.info(f"Sentiment guard enabled: threshold={self.sentiment_threshold}")
        
        # Check sentiment before placing any orders
        if not self._check_sentiment():
            logger.warning("Grid initialization paused due to poor sentiment. Waiting...")
            # In a real implementation, this could retry periodically
            return
        
        
        current_price = self._get_current_price()
        logger.info(f"Current price: {current_price}")
        
        # Get exchange info for validation
        exchange_info = self.client.get_exchange_info(self.symbol)
        min_notional = exchange_info['minNotional']
        logger.info(f"Exchange requirements: minNotional=${min_notional}, pricePrecision={exchange_info['pricePrecision']}, qtyPrecision={exchange_info['quantityPrecision']}")
        
        orders_placed = 0
        orders_skipped = 0
        
        for i in range(self.grids):
            price = self.lower_price + (i * self.step)
            
            # Format price to correct precision
            formatted_price = self.client.format_price(self.symbol, price)
            
            # Calculate minimum quantity for this price level
            min_qty = self.client.calculate_min_quantity(self.symbol, formatted_price)
            
            # Use the larger of user-specified quantity or minimum required
            actual_qty = max(self.quantity_per_grid, min_qty)
            formatted_qty = self.client.format_quantity(self.symbol, actual_qty)
            
            # Validate notional value
            notional = formatted_price * formatted_qty
            if notional < min_notional:
                logger.warning(
                    f"Skipping grid {i+1}/{self.grids}: notional ${notional:.2f} < ${min_notional:.2f} "
                    f"(price={formatted_price}, qty={formatted_qty})"
                )
                orders_skipped += 1
                continue
            
            # Simple logic: if price < current_price, place BUY LIMIT. 
            # If price > current_price, place SELL LIMIT.
            side = "BUY" if formatted_price < current_price else "SELL"
            
            # Skip if too close to current price to avoid immediate fill
            if abs(formatted_price - current_price) < (current_price * 0.001):
                logger.info(f"Skipping grid {i+1}/{self.grids}: too close to current price")
                orders_skipped += 1
                continue

            try:
                logger.info(
                    f"Placing Grid Order {i+1}/{self.grids}: {side} {formatted_qty} @ {formatted_price} "
                    f"(notional=${notional:.2f})"
                )
                self.client.place_order(
                    symbol=self.symbol,
                    side=side,
                    order_type="LIMIT",
                    quantity=formatted_qty,
                    price=formatted_price
                )
                orders_placed += 1
            except Exception as e:
                logger.error(f"Failed to place grid order {i+1}: {e}")
                orders_skipped += 1
                
        logger.info(
            f"Grid Strategy completed: {orders_placed} orders placed, {orders_skipped} orders skipped"
        )

    def _get_current_price(self) -> float:
        # We need a way to get current price. 
        # Adding a simple method to get ticker price would be ideal in client, 
        # but for now we can maybe check the mark price endpoint or just trust user knows where price is.
        # Let's add a `get_symbol_price` to client.py quickly or use a dedicated request here.
        
        # Use the public method from client
        return self.client.get_symbol_price(self.symbol)
