"""Configuration for Sentiment Analysis Service."""

import os
from dataclasses import dataclass
from typing import List


@dataclass
class SentimentConfig:
    """Configuration for sentiment analysis."""
    
    # Reddit API Configuration
    reddit_client_id: str = os.getenv("REDDIT_CLIENT_ID", "")
    reddit_client_secret: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    reddit_user_agent: str = os.getenv("REDDIT_USER_AGENT", "Zenith Trading Bot v1.0")
    
    # LLM Configuration
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    
    # Scraping Configuration
    news_poll_interval: int = int(os.getenv("NEWS_POLL_INTERVAL", "900"))  # 15 minutes
    social_poll_interval: int = int(os.getenv("SOCIAL_POLL_INTERVAL", "1800"))  # 30 minutes
    
    # RSS Feed URLs for Crypto News
    news_feeds: List[str] = None
    
    # Reddit Subreddits to Monitor
    reddit_subreddits: List[str] = None
    
    # Twitter RSS Feeds (using Nitter or similar)
    twitter_feeds: List[str] = None
    
    # Sentiment Calculation
    news_weight: float = 0.5
    reddit_weight: float = 0.3
    twitter_weight: float = 0.2
    
    # Time decay (how much to weight recent vs old data)
    time_decay_hours: int = 24  # Data older than this gets less weight
    
    def __post_init__(self):
        """Initialize default lists if not provided."""
        if self.news_feeds is None:
            self.news_feeds = [
                "https://cointelegraph.com/rss",
                "https://www.coindesk.com/arc/outboundfeeds/rss/",
                "https://decrypt.co/feed",
                "https://bitcoinmagazine.com/.rss/full/",
            ]
        
        if self.reddit_subreddits is None:
            self.reddit_subreddits = [
                "cryptocurrency",
                "bitcoin",
                "ethtrader",
                "CryptoMarkets",
            ]
        
        if self.twitter_feeds is None:
            # Using Nitter RSS feeds for popular crypto accounts
            self.twitter_feeds = [
                "https://nitter.net/cointelegraph/rss",
                "https://nitter.net/coindesk/rss",
                "https://nitter.net/documentingbtc/rss",
            ]


def load_sentiment_config() -> SentimentConfig:
    """Load sentiment configuration from environment."""
    return SentimentConfig()
