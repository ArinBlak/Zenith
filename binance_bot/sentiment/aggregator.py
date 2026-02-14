"""Sentiment aggregator that combines multiple sources."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
import statistics

from .config import SentimentConfig

logger = logging.getLogger("sentiment.aggregator")


class SentimentAggregator:
    """Aggregates sentiment from multiple sources and symbols."""
    
    def __init__(self, config: SentimentConfig):
        self.config = config
        
        # Store sentiment data: {symbol: [{score, timestamp, source, confidence, ...}]}
        self.sentiment_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # Cache for computed aggregates
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = timedelta(seconds=30)  # Cache for 30 seconds
    
    def add_sentiment(
        self,
        symbol: str,
        score: int,
        source: str,
        confidence: float,
        timestamp: Optional[datetime] = None,
        **kwargs
    ):
        """Add a sentiment data point."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        data = {
            "score": score,
            "source": source,
            "confidence": confidence,
            "timestamp": timestamp,
            **kwargs
        }
        
        self.sentiment_history[symbol].append(data)
        
        # Cleanup old data
        self._cleanup_old_data()
        
        # Invalidate cache
        self._cache_timestamp = None
    
    def get_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Get aggregated sentiment for a specific symbol.
        
        Returns:
            Dict with keys: score, label, confidence, breakdown_by_source, last_update
        """
        if symbol not in self.sentiment_history or not self.sentiment_history[symbol]:
            return self._neutral_sentiment()
        
        # Check cache
        cache_key = f"symbol_{symbol}"
        if self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]
        
        data_points = self.sentiment_history[symbol]
        result = self._aggregate_data_points(data_points)
        
        # Cache result
        self._cache[cache_key] = result
        return result
    
    def get_market_sentiment(self) -> Dict[str, Any]:
        """Get overall market sentiment (aggregated across all symbols).
        
        Returns:
            Dict with keys: score, label, confidence, breakdown_by_source, last_update
        """
        # Check cache
        cache_key = "market_wide"
        if self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]
        
        # Collect all data points except symbol-specific ones
        all_data = []
        for symbol, data_points in self.sentiment_history.items():
            # Include MARKET sentiment and all other symbols
            all_data.extend(data_points)
        
        if not all_data:
            return self._neutral_sentiment()
        
        result = self._aggregate_data_points(all_data)
        
        # Cache result
        self._cache[cache_key] = result
        self._cache_timestamp = datetime.now(timezone.utc)
        return result
    
    def get_history(self, symbol: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get historical sentiment data for a symbol.
        
        Returns:
            List of sentiment data points from the last N hours
        """
        if symbol not in self.sentiment_history:
            return []
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        return [
            dp for dp in self.sentiment_history[symbol]
            if dp["timestamp"] > cutoff
        ]
    
    def get_breakdown_by_source(self, symbol: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Get sentiment breakdown by source.
        
        Args:
            symbol: If provided, get breakdown for specific symbol. If None, market-wide.
        
        Returns:
            Dict mapping source name to aggregated sentiment
        """
        # Collect data points
        if symbol:
            data_points = self.sentiment_history.get(symbol, [])
        else:
            data_points = []
            for data_list in self.sentiment_history.values():
                data_points.extend(data_list)
        
        # Group by source
        by_source = defaultdict(list)
        for dp in data_points:
            by_source[dp["source"]].append(dp)
        
        # Aggregate each source
        breakdown = {}
        for source, source_data in by_source.items():
            breakdown[source] = self._aggregate_data_points(source_data)
        
        return breakdown
    
    def _aggregate_data_points(self, data_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate multiple sentiment data points into a single score."""
        if not data_points:
            return self._neutral_sentiment()
        
        # Apply time decay
        now = datetime.now(timezone.utc)
        decay_hours = self.config.time_decay_hours
        
        weighted_scores = []
        total_weight = 0
        
        for dp in data_points:
            # Time weight (more recent = higher weight)
            age_hours = (now - dp["timestamp"]).total_seconds() / 3600
            time_weight = max(0, 1 - (age_hours / decay_hours))
            
            # Source weight
            source_weight = self._get_source_weight(dp["source"])
            
            # Confidence weight
            confidence_weight = dp.get("confidence", 0.5)
            
            # Combined weight
            weight = time_weight * source_weight * confidence_weight
            
            weighted_scores.append(dp["score"] * weight)
            total_weight += weight
        
        # Calculate weighted average
        if total_weight > 0:
            avg_score = sum(weighted_scores) / total_weight
        else:
            avg_score = 50
        
        # Calculate confidence (based on number of data points and their individual confidence)
        confidences = [dp.get("confidence", 0.5) for dp in data_points]
        avg_confidence = statistics.mean(confidences) if confidences else 0.5
        
        # Adjust confidence based on sample size
        sample_size_factor = min(1.0, len(data_points) / 10)  # More data = more confidence
        final_confidence = avg_confidence * sample_size_factor
        
        # Determine label
        label = self._score_to_label(avg_score)
        
        # Get most recent update
        last_update = max(dp["timestamp"] for dp in data_points)
        
        return {
            "score": round(avg_score, 1),
            "label": label,
            "confidence": round(final_confidence, 2),
            "data_points": len(data_points),
            "last_update": last_update.isoformat(),
        }
    
    def _get_source_weight(self, source: str) -> float:
        """Get the weight for a given source."""
        source_lower = source.lower()
        
        if "reddit" in source_lower or "r/" in source_lower:
            return self.config.reddit_weight
        elif "twitter" in source_lower:
            return self.config.twitter_weight
        else:
            # Assume it's news
            return self.config.news_weight
    
    def _score_to_label(self, score: float) -> str:
        """Convert numeric score to label."""
        if score < 30:
            return "Bearish"
        elif score > 70:
            return "Bullish"
        else:
            return "Neutral"
    
    def _neutral_sentiment(self) -> Dict[str, Any]:
        """Return a neutral sentiment (no data)."""
        return {
            "score": 50.0,
            "label": "Neutral",
            "confidence": 0.0,
            "data_points": 0,
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
    
    def _cleanup_old_data(self):
        """Remove data older than the decay period."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.config.time_decay_hours)
        
        for symbol in list(self.sentiment_history.keys()):
            self.sentiment_history[symbol] = [
                dp for dp in self.sentiment_history[symbol]
                if dp["timestamp"] > cutoff
            ]
            
            # Remove symbol if no data left
            if not self.sentiment_history[symbol]:
                del self.sentiment_history[symbol]
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if self._cache_timestamp is None:
            return False
        
        age = datetime.now(timezone.utc) - self._cache_timestamp
        return age < self._cache_ttl
