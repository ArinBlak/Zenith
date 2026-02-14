"""Data scrapers for sentiment analysis."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Dict, Any
import feedparser
import aiohttp
from bs4 import BeautifulSoup
import praw
from dateutil import parser as date_parser

from .config import SentimentConfig

logger = logging.getLogger("sentiment.scrapers")


class ScraperBase(ABC):
    """Base class for all scrapers."""
    
    @abstractmethod
    async def scrape(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Scrape content for given symbols.
        
        Returns:
            List of dicts with keys: title, content, source, timestamp, symbols
        """
        pass


class CryptoNewsScraper(ScraperBase):
    """Scraper for crypto news RSS feeds."""
    
    def __init__(self, config: SentimentConfig):
        self.config = config
        self.feeds = config.news_feeds
    
    async def scrape(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Scrape news feeds for crypto content."""
        articles = []
        
        for feed_url in self.feeds:
            try:
                # feedparser is synchronous, run in executor
                loop = asyncio.get_event_loop()
                feed = await loop.run_in_executor(None, feedparser.parse, feed_url)
                
                for entry in feed.entries[:10]:  # Limit to 10 most recent per feed
                    # Extract content
                    title = entry.get("title", "")
                    content = entry.get("summary", entry.get("description", ""))
                    
                    # Clean HTML from content
                    if content:
                        soup = BeautifulSoup(content, "html.parser")
                        content = soup.get_text()
                    
                    # Parse timestamp
                    timestamp = datetime.now(timezone.utc)
                    if "published" in entry:
                        try:
                            timestamp = date_parser.parse(entry.published)
                            if timestamp.tzinfo is None:
                                timestamp = timestamp.replace(tzinfo=timezone.utc)
                        except Exception:
                            pass
                    
                    # Determine which symbols this article mentions
                    mentioned_symbols = self._extract_symbols(title + " " + content, symbols)
                    
                    articles.append({
                        "title": title,
                        "content": content[:1000],  # Limit content length
                        "source": feed.feed.get("title", feed_url),
                        "timestamp": timestamp,
                        "symbols": mentioned_symbols,
                        "url": entry.get("link", "")
                    })
                
                logger.info(f"Scraped {len(feed.entries[:10])} articles from {feed_url}")
            
            except Exception as e:
                logger.error(f"Error scraping {feed_url}: {e}")
        
        return articles
    
    def _extract_symbols(self, text: str, symbols: List[str]) -> List[str]:
        """Extract which trading symbols are mentioned in the text."""
        mentioned = []
        text_lower = text.lower()
        
        # Create a mapping of common names to symbols
        symbol_map = {
            "bitcoin": "BTCUSDT",
            "btc": "BTCUSDT",
            "ethereum": "ETHUSDT",
            "eth": "ETHUSDT",
            "solana": "SOLUSDT",
            "sol": "SOLUSDT",
            "binance": "BNBUSDT",
            "bnb": "BNBUSDT",
            "cardano": "ADAUSDT",
            "ada": "ADAUSDT",
            "ripple": "XRPUSDT",
            "xrp": "XRPUSDT",
        }
        
        for keyword, symbol in symbol_map.items():
            if keyword in text_lower and (not symbols or symbol in symbols):
                if symbol not in mentioned:
                    mentioned.append(symbol)
        
        # If no specific symbols found, mark as general market sentiment
        if not mentioned:
            mentioned = ["MARKET"]
        
        return mentioned


class RedditScraper(ScraperBase):
    """Scraper for Reddit posts and comments."""
    
    def __init__(self, config: SentimentConfig):
        self.config = config
        self.reddit = None
        
        # Only initialize if credentials are provided
        if config.reddit_client_id and config.reddit_client_secret:
            try:
                self.reddit = praw.Reddit(
                    client_id=config.reddit_client_id,
                    client_secret=config.reddit_client_secret,
                    user_agent=config.reddit_user_agent,
                )
                logger.info("Reddit API client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Reddit API: {e}")
    
    async def scrape(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Scrape Reddit posts from crypto subreddits."""
        if not self.reddit:
            logger.warning("Reddit API not configured, skipping Reddit scraping")
            return []
        
        posts = []
        
        for subreddit_name in self.config.reddit_subreddits:
            try:
                # PRAW is synchronous, run in executor
                loop = asyncio.get_event_loop()
                subreddit = await loop.run_in_executor(
                    None, 
                    self.reddit.subreddit, 
                    subreddit_name
                )
                
                # Get hot posts
                submissions = await loop.run_in_executor(
                    None,
                    lambda: list(subreddit.hot(limit=20))
                )
                
                for submission in submissions:
                    title = submission.title
                    content = submission.selftext[:500] if submission.selftext else ""
                    
                    timestamp = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
                    
                    mentioned_symbols = self._extract_symbols(title + " " + content, symbols)
                    
                    posts.append({
                        "title": title,
                        "content": content,
                        "source": f"r/{subreddit_name}",
                        "timestamp": timestamp,
                        "symbols": mentioned_symbols,
                        "url": f"https://reddit.com{submission.permalink}",
                        "score": submission.score  # Reddit upvotes can indicate importance
                    })
                
                logger.info(f"Scraped {len(submissions)} posts from r/{subreddit_name}")
            
            except Exception as e:
                logger.error(f"Error scraping r/{subreddit_name}: {e}")
        
        return posts
    
    def _extract_symbols(self, text: str, symbols: List[str]) -> List[str]:
        """Extract which trading symbols are mentioned in the text."""
        # Use same logic as news scraper
        scraper = CryptoNewsScraper(self.config)
        return scraper._extract_symbols(text, symbols)


class TwitterScraper(ScraperBase):
    """Scraper for Twitter/X using RSS feeds (Nitter)."""
    
    def __init__(self, config: SentimentConfig):
        self.config = config
        self.feeds = config.twitter_feeds
    
    async def scrape(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Scrape Twitter feeds using Nitter RSS."""
        tweets = []
        
        for feed_url in self.feeds:
            try:
                loop = asyncio.get_event_loop()
                feed = await loop.run_in_executor(None, feedparser.parse, feed_url)
                
                for entry in feed.entries[:15]:  # Limit to 15 most recent per feed
                    title = entry.get("title", "")
                    content = entry.get("summary", entry.get("description", ""))
                    
                    # Clean HTML
                    if content:
                        soup = BeautifulSoup(content, "html.parser")
                        content = soup.get_text()
                    
                    # Parse timestamp
                    timestamp = datetime.now(timezone.utc)
                    if "published" in entry:
                        try:
                            timestamp = date_parser.parse(entry.published)
                            if timestamp.tzinfo is None:
                                timestamp = timestamp.replace(tzinfo=timezone.utc)
                        except Exception:
                            pass
                    
                    mentioned_symbols = self._extract_symbols(title + " " + content, symbols)
                    
                    tweets.append({
                        "title": title[:100],  # Tweets don't have titles, use first part
                        "content": content[:280],  # Twitter character limit
                        "source": "Twitter",
                        "timestamp": timestamp,
                        "symbols": mentioned_symbols,
                        "url": entry.get("link", "")
                    })
                
                logger.info(f"Scraped {len(feed.entries[:15])} tweets from {feed_url}")
            
            except Exception as e:
                logger.error(f"Error scraping Twitter feed {feed_url}: {e}")
        
        return tweets
    
    def _extract_symbols(self, text: str, symbols: List[str]) -> List[str]:
        """Extract which trading symbols are mentioned in the text."""
        scraper = CryptoNewsScraper(self.config)
        return scraper._extract_symbols(text, symbols)
