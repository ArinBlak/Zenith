import time
import logging
from typing import Optional
from binance_bot.client import BinanceFuturesClient

logger = logging.getLogger("strategy.twap")

class TWAPStrategy:
    def __init__(
        self,
        client: BinanceFuturesClient,
        symbol: str,
        side: str,
        total_quantity: float,
        duration_seconds: int,
        num_orders: int,
        min_sentiment_score: Optional[int] = None,
        pause_on_bearish: bool = False,
        sentiment_worker = None
    ):
        self.client = client
        self.symbol = symbol
        self.side = side
        self.total_quantity = total_quantity
        self.duration_seconds = duration_seconds
        self.num_orders = num_orders
        self.min_sentiment_score = min_sentiment_score
        self.pause_on_bearish = pause_on_bearish
        self.sentiment_worker = sentiment_worker
        
        if num_orders < 1:
            raise ValueError("num_orders must be >= 1")
            
        self.qty_per_order = total_quantity / num_orders
        self.interval = duration_seconds / num_orders

    def _check_sentiment(self) -> bool:
        """Check if sentiment conditions are met for trading.
        
        Returns:
            True if conditions are met, False if should pause
        """
        if not self.sentiment_worker:
            return True  # No sentiment worker, proceed normally
        
        if not self.min_sentiment_score and not self.pause_on_bearish:
            return True  # No sentiment restrictions
        
        try:
            sentiment = self.sentiment_worker.get_sentiment(self.symbol)
            score = sentiment.get("score", 50)
            label = sentiment.get("label", "Neutral")
            
            logger.info(f"Current sentiment for {self.symbol}: {label} ({score})")
            
            # Check minimum score threshold
            if self.min_sentiment_score and score < self.min_sentiment_score:
                logger.warning(
                    f"TWAP paused: Sentiment score ({score}) below minimum ({self.min_sentiment_score})"
                )
                return False
            
            # Check bearish pause
            if self.pause_on_bearish and label == "Bearish":
                logger.warning(f"TWAP paused: Market sentiment is Bearish")
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"Error checking sentiment: {e}. Proceeding with trade.")
            return True  # On error, proceed normally

    def run(self):
        logger.info(
            f"Starting TWAP: {self.total_quantity} {self.symbol} {self.side} "
            f"over {self.duration_seconds}s in {self.num_orders} orders."
        )
        
        if self.min_sentiment_score or self.pause_on_bearish:
            logger.info(
                f"Sentiment guard enabled: min_score={self.min_sentiment_score}, "
                f"pause_on_bearish={self.pause_on_bearish}"
            )
        
        for i in range(self.num_orders):
            # Check sentiment before each order
            if not self._check_sentiment():
                logger.info(f"Skipping TWAP slice {i+1}/{self.num_orders} due to sentiment")
                if i < self.num_orders - 1:
                    time.sleep(self.interval)
                continue
            
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
