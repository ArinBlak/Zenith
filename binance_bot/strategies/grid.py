import time
import logging
from binance_bot.client import BinanceFuturesClient

logger = logging.getLogger("strategy.grid")

class GridStrategy:
    def __init__(self, client: BinanceFuturesClient, symbol: str, lower_price: float, upper_price: float, grids: int, quantity_per_grid: float):
        self.client = client
        self.symbol = symbol
        self.lower_price = lower_price
        self.upper_price = upper_price
        self.grids = grids
        self.quantity_per_grid = quantity_per_grid
        
        if grids < 2:
            raise ValueError("grids must be >= 2")

        self.step = (upper_price - lower_price) / (grids - 1)

    def run(self):
        logger.info(f"Starting Grid: {self.grids} grids from {self.lower_price} to {self.upper_price} on {self.symbol}")
        
        current_price = self._get_current_price()
        logger.info(f"Current price: {current_price}")
        
        for i in range(self.grids):
            price = self.lower_price + (i * self.step)
            
            # Simple logic: if price < current_price, place BUY LIMIT. 
            # If price > current_price, place SELL LIMIT.
            # (In a real bot, we'd need more complex state management)
            
            side = "BUY" if price < current_price else "SELL"
            
            # Skip if too close to current price to avoid immediate fill (optional, but good for pure grid)
            if abs(price - current_price) < (current_price * 0.001):
                continue

            try:
                logger.info(f"Placing Grid Order {i+1}: {side} {self.quantity_per_grid} @ {price:.2f}")
                self.client.place_order(
                    symbol=self.symbol,
                    side=side,
                    order_type="LIMIT",
                    quantity=self.quantity_per_grid,
                    price=price
                )
            except Exception as e:
                logger.error(f"Failed to place grid order {i+1}: {e}")
                
        logger.info("Grid Strategy initialization completed.")

    def _get_current_price(self) -> float:
        # We need a way to get current price. 
        # Adding a simple method to get ticker price would be ideal in client, 
        # but for now we can maybe check the mark price endpoint or just trust user knows where price is.
        # Let's add a `get_symbol_price` to client.py quickly or use a dedicated request here.
        
        # Use the public method from client
        return self.client.get_symbol_price(self.symbol)
