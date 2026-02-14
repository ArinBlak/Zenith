"""Background worker for sentiment analysis."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional, Callable

from .config import SentimentConfig, load_sentiment_config
from .scrapers import CryptoNewsScraper, RedditScraper, TwitterScraper
from .analyzer import SentimentAnalyzer
from .aggregator import SentimentAggregator

logger = logging.getLogger("sentiment.worker")


class SentimentWorker:
    """Background worker that scrapes and analyzes sentiment continuously."""
    
    def __init__(
        self,
        config: Optional[SentimentConfig] = None,
        on_update: Optional[Callable] = None
    ):
        """Initialize the sentiment worker.
        
        Args:
            config: Sentiment configuration (loads from env if not provided)
            on_update: Optional callback function called when sentiment updates
        """
        self.config = config or load_sentiment_config()
        self.on_update = on_update
        
        # Initialize components
        self.news_scraper = CryptoNewsScraper(self.config)
        self.reddit_scraper = RedditScraper(self.config)
        self.twitter_scraper = TwitterScraper(self.config)
        self.analyzer = SentimentAnalyzer(self.config)
        self.aggregator = SentimentAggregator(self.config)
        
        # Task handles
        self._news_task: Optional[asyncio.Task] = None
        self._social_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("SentimentWorker initialized")
    
    async def start(self, symbols: Optional[List[str]] = None):
        """Start the background worker.
        
        Args:
            symbols: List of trading symbols to monitor. If None, monitors general market.
        """
        if self._running:
            logger.warning("SentimentWorker already running")
            return
        
        self._running = True
        logger.info("Starting SentimentWorker...")
        
        # Start background tasks
        self._news_task = asyncio.create_task(self._news_loop(symbols))
        self._social_task = asyncio.create_task(self._social_loop(symbols))
        
        logger.info("SentimentWorker started successfully")
    
    async def stop(self):
        """Stop the background worker."""
        self._running = False
        
        if self._news_task:
            self._news_task.cancel()
        if self._social_task:
            self._social_task.cancel()
        
        logger.info("SentimentWorker stopped")
    
    def get_sentiment(self, symbol: str):
        """Get current sentiment for a symbol."""
        return self.aggregator.get_sentiment(symbol)
    
    def get_market_sentiment(self):
        """Get current market-wide sentiment."""
        return self.aggregator.get_market_sentiment()
    
    def get_breakdown(self, symbol: Optional[str] = None):
        """Get sentiment breakdown by source."""
        return self.aggregator.get_breakdown_by_source(symbol)
    
    def get_history(self, symbol: str, hours: int = 24):
        """Get sentiment history."""
        return self.aggregator.get_history(symbol, hours)
    
    async def _news_loop(self, symbols: Optional[List[str]]):
        """Background loop for news scraping."""
        while self._running:
            try:
                logger.info("Starting news scraping cycle...")
                
                # Scrape news
                articles = await self.news_scraper.scrape(symbols or [])
                logger.info(f"Scraped {len(articles)} news articles")
                
                # Analyze sentiment for each article
                for article in articles:
                    try:
                        sentiment = await self.analyzer.analyze(
                            text=article["content"],
                            title=article["title"]
                        )
                        
                        # Add to aggregator for each mentioned symbol
                        for symbol in article["symbols"]:
                            self.aggregator.add_sentiment(
                                symbol=symbol,
                                score=sentiment["score"],
                                source=article["source"],
                                confidence=sentiment["confidence"],
                                timestamp=article["timestamp"],
                                title=article["title"],
                                url=article.get("url", ""),
                                reasoning=sentiment.get("reasoning", "")
                            )
                    
                    except Exception as e:
                        logger.error(f"Error analyzing article: {e}")
                
                # Notify update callback
                if self.on_update:
                    try:
                        await self.on_update({
                            "type": "sentiment_update",
                            "source": "news",
                            "market": self.get_market_sentiment()
                        })
                    except Exception as e:
                        logger.error(f"Error in update callback: {e}")
                
                logger.info("News scraping cycle completed")
                
                # Wait for next cycle
                await asyncio.sleep(self.config.news_poll_interval)
            
            except asyncio.CancelledError:
                logger.info("News loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in news loop: {e}")
                await asyncio.sleep(60)  # Wait a bit before retrying
    
    async def _social_loop(self, symbols: Optional[List[str]]):
        """Background loop for social media scraping."""
        # Wait a bit before starting to stagger with news loop
        await asyncio.sleep(10)
        
        while self._running:
            try:
                logger.info("Starting social media scraping cycle...")
                
                # Scrape Reddit
                reddit_posts = await self.reddit_scraper.scrape(symbols or [])
                logger.info(f"Scraped {len(reddit_posts)} Reddit posts")
                
                # Scrape Twitter
                tweets = await self.twitter_scraper.scrape(symbols or [])
                logger.info(f"Scraped {len(tweets)} tweets")
                
                # Combine social media content
                social_content = reddit_posts + tweets
                
                # Analyze sentiment for each item
                for item in social_content:
                    try:
                        sentiment = await self.analyzer.analyze(
                            text=item["content"],
                            title=item["title"]
                        )
                        
                        # Adjust confidence for Reddit based on score
                        confidence = sentiment["confidence"]
                        if "score" in item and item["source"].startswith("r/"):
                            # Higher upvotes = higher confidence
                            reddit_score = item["score"]
                            score_factor = min(1.0, reddit_score / 100)
                            confidence *= (0.5 + 0.5 * score_factor)
                        
                        # Add to aggregator for each mentioned symbol
                        for symbol in item["symbols"]:
                            self.aggregator.add_sentiment(
                                symbol=symbol,
                                score=sentiment["score"],
                                source=item["source"],
                                confidence=confidence,
                                timestamp=item["timestamp"],
                                title=item["title"],
                                url=item.get("url", ""),
                                reasoning=sentiment.get("reasoning", "")
                            )
                    
                    except Exception as e:
                        logger.error(f"Error analyzing social content: {e}")
                
                # Notify update callback
                if self.on_update:
                    try:
                        await self.on_update({
                            "type": "sentiment_update",
                            "source": "social",
                            "market": self.get_market_sentiment()
                        })
                    except Exception as e:
                        logger.error(f"Error in update callback: {e}")
                
                logger.info("Social media scraping cycle completed")
                
                # Wait for next cycle
                await asyncio.sleep(self.config.social_poll_interval)
            
            except asyncio.CancelledError:
                logger.info("Social loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in social loop: {e}")
                await asyncio.sleep(60)  # Wait a bit before retrying
