"""Condition evaluator for trading strategy execution."""

import logging
from typing import Dict, Any, Optional
from binance_bot.indicators.rsi import RSICalculator

logger = logging.getLogger("nlp.conditions")


class ConditionEvaluator:
    """Evaluate trading conditions like RSI, sentiment, etc."""
    
    def __init__(self, client=None, sentiment_worker=None):
        """Initialize condition evaluator.
        
        Args:
            client: BinanceFuturesClient instance for market data
            sentiment_worker: SentimentWorker instance for sentiment data
        """
        self.client = client
        self.sentiment_worker = sentiment_worker
        self.rsi_calculator = RSICalculator(period=14)
    
    async def evaluate(self, symbol: str, conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate all conditions for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            conditions: Dict of conditions to evaluate
        
        Returns:
            Dict with keys: met (bool), details (dict), errors (list)
        """
        if not conditions:
            return {"met": True, "details": {}, "errors": []}
        
        results = {
            "met": True,
            "details": {},
            "errors": []
        }
        
        # Check RSI conditions
        if "rsi_below" in conditions or "rsi_above" in conditions:
            rsi_result = await self._check_rsi(symbol, conditions)
            results["details"]["rsi"] = rsi_result
            
            if not rsi_result["met"]:
                results["met"] = False
            
            if rsi_result.get("error"):
                results["errors"].append(rsi_result["error"])
        
        # Check sentiment conditions
        if any(k in conditions for k in ["sentiment_above", "sentiment_below", "pause_on_bearish"]):
            sentiment_result = self._check_sentiment(symbol, conditions)
            results["details"]["sentiment"] = sentiment_result
            
            if not sentiment_result["met"]:
                results["met"] = False
            
            if sentiment_result.get("error"):
                results["errors"].append(sentiment_result["error"])
        
        return results
    
    async def _check_rsi(self, symbol: str, conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Check RSI conditions."""
        try:
            if not self.client:
                return {
                    "met": True,
                    "value": None,
                    "error": "No client available for RSI calculation, skipping check"
                }
            
            # Fetch recent prices for RSI calculation
            prices = await RSICalculator.fetch_from_binance(
                self.client,
                symbol,
                interval="1h",
                limit=50
            )
            
            if not prices:
                return {
                    "met": True,
                    "value": None,
                    "error": "Failed to fetch price data for RSI calculation"
                }
            
            # Calculate RSI
            rsi = self.rsi_calculator.calculate(prices)
            
            if rsi is None:
                return {
                    "met": True,
                    "value": None,
                    "error": "Insufficient data for RSI calculation"
                }
            
            # Check conditions
            met = True
            description = f"RSI: {rsi}"
            
            if "rsi_below" in conditions:
                threshold = conditions["rsi_below"]
                if rsi >= threshold:
                    met = False
                    description += f" (should be < {threshold})"
            
            if "rsi_above" in conditions:
                threshold = conditions["rsi_above"]
                if rsi <= threshold:
                    met = False
                    description += f" (should be > {threshold})"
            
            return {
                "met": met,
                "value": rsi,
                "description": description,
                "error": None
            }
        
        except Exception as e:
            logger.error(f"Error checking RSI: {e}")
            return {
                "met": True,  # Don't block on error
                "value": None,
                "error": f"RSI check error: {str(e)}"
            }
    
    def _check_sentiment(self, symbol: str, conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Check sentiment conditions."""
        try:
            if not self.sentiment_worker:
                return {
                    "met": True,
                    "value": None,
                    "error": "No sentiment worker available, skipping check"
                }
            
            # Get current sentiment
            sentiment = self.sentiment_worker.get_sentiment(symbol)
            
            if "error" in sentiment:
                return {
                    "met": True,
                    "value": None,
                    "error": f"Sentiment unavailable: {sentiment['error']}"
                }
            
            score = sentiment.get("score", 50)
            label = sentiment.get("label", "Neutral")
            
            # Check conditions
            met = True
            description = f"{label} ({score})"
            
            if "sentiment_above" in conditions:
                threshold = conditions["sentiment_above"]
                if score <= threshold:
                    met = False
                    description += f" (should be > {threshold})"
            
            if "sentiment_below" in conditions:
                threshold = conditions["sentiment_below"]
                if score >= threshold:
                    met = False
                    description += f" (should be < {threshold})"
            
            if "pause_on_bearish" in conditions and conditions["pause_on_bearish"]:
                if label == "Bearish":
                    met = False
                    description += " (paused on bearish)"
            
            return {
                "met": met,
                "value": score,
                "label": label,
                "description": description,
                "error": None
            }
        
        except Exception as e:
            logger.error(f"Error checking sentiment: {e}")
            return {
                "met": True,  # Don't block on error
                "value": None,
                "error": f"Sentiment check error: {str(e)}"
            }
