import time
import logging
from binance_bot.client import BinanceFuturesClient

logger = logging.getLogger("strategy.twap")

class TWAPStrategy:
    def __init__(self, client: BinanceFuturesClient, symbol: str, side: str, total_quantity: float, duration_seconds: int, num_orders: int):
        self.client = client
        self.symbol = symbol
        self.side = side
        self.total_quantity = total_quantity
        self.duration_seconds = duration_seconds
        self.num_orders = num_orders
        
        if num_orders < 1:
            raise ValueError("num_orders must be >= 1")
            
        self.qty_per_order = total_quantity / num_orders
        self.interval = duration_seconds / num_orders

    def run(self):
        logger.info(f"Starting TWAP: {self.total_quantity} {self.symbol} {self.side} over {self.duration_seconds}s in {self.num_orders} orders.")
        
        for i in range(self.num_orders):
            logger.info(f"Executing TWAP slice {i+1}/{self.num_orders}...")
            try:
                self.client.place_order(
                    symbol=self.symbol,
                    side=self.side,
                    order_type="MARKET",
                    quantity=self.qty_per_order
                )
            except Exception as e:
                logger.error(f"Failed to place TWAP order {i+1}: {e}")
                
            if i < self.num_orders - 1:
                time.sleep(self.interval)
                
        logger.info("TWAP Strategy completed.")
