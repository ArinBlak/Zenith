"""LLM-based sentiment analyzer using Ollama."""

import asyncio
import logging
from typing import Dict, Any, List
import ollama

from .config import SentimentConfig

logger = logging.getLogger("sentiment.analyzer")


class SentimentAnalyzer:
    """Analyzes text sentiment using local LLM via Ollama."""
    
    def __init__(self, config: SentimentConfig):
        self.config = config
        self.model = config.ollama_model
        self.client = ollama.Client(host=config.ollama_host)
        
        # Test connection
        try:
            self.client.list()
            logger.info(f"Ollama client initialized with model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
    
    async def analyze(self, text: str, title: str = "") -> Dict[str, Any]:
        """Analyze sentiment of a single piece of text (async).
        
        Args:
            text: The main content to analyze
            title: Optional title/headline
        
        Returns:
            Dict with keys: score (0-100), label, confidence, reasoning
        """
        prompt = self._build_prompt(title, text)
        
        try:
            # Run synchronous Ollama call in executor to prevent blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.generate(
                    model=self.model,
                    prompt=prompt,
                    options={
                        "temperature": 0.3,
                        "num_predict": 200,
                    }
                )
            )
            
            result = self._parse_response(response['response'])
            logger.debug(f"Analyzed: '{title[:50]}...' -> {result['label']} ({result['score']})")
            return result
        
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            # Return neutral on error
            return {
                "score": 50,
                "label": "Neutral",
                "confidence": 0.0,
                "reasoning": f"Error: {str(e)}"
            }
    
    async def analyze_batch(self, items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Analyze sentiment for multiple items.
        
        Args:
            items: List of dicts with 'title' and 'content' keys
        
        Returns:
            List of sentiment results
        """
        results = []
        for item in items:
            result = self.analyze(
                text=item.get("content", ""),
                title=item.get("title", "")
            )
            results.append(result)
        
        return results
    
    def _build_prompt(self, title: str, text: str) -> str:
        """Build the prompt for the LLM."""
        full_text = f"{title}\n\n{text}" if title else text
        
        prompt = f"""You are a cryptocurrency market sentiment analyzer. Analyze the following text and determine if it's Bullish, Bearish, or Neutral for cryptocurrency markets.

Text to analyze:
{full_text[:1500]}

Provide your analysis in this exact format:
SENTIMENT: [Bullish/Bearish/Neutral]
SCORE: [0-100, where 0=very bearish, 50=neutral, 100=very bullish]
CONFIDENCE: [0.0-1.0]
REASONING: [Brief 1-sentence explanation]

Analysis:"""
        
        return prompt
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM response into structured sentiment data."""
        lines = response.strip().split('\n')
        
        sentiment_label = "Neutral"
        score = 50
        confidence = 0.5
        reasoning = ""
        
        for line in lines:
            line = line.strip()
            if line.startswith("SENTIMENT:"):
                sentiment_label = line.split(":", 1)[1].strip()
            elif line.startswith("SCORE:"):
                try:
                    score_str = line.split(":", 1)[1].strip()
                    # Extract just the number
                    score = int(''.join(filter(str.isdigit, score_str)))
                    score = max(0, min(100, score))  # Clamp to 0-100
                except ValueError:
                    score = 50
            elif line.startswith("CONFIDENCE:"):
                try:
                    conf_str = line.split(":", 1)[1].strip()
                    confidence = float(conf_str)
                    confidence = max(0.0, min(1.0, confidence))  # Clamp to 0-1
                except ValueError:
                    confidence = 0.5
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()
        
        # Normalize label
        sentiment_label = sentiment_label.capitalize()
        if "bull" in sentiment_label.lower():
            sentiment_label = "Bullish"
        elif "bear" in sentiment_label.lower():
            sentiment_label = "Bearish"
        else:
            sentiment_label = "Neutral"
        
        return {
            "score": score,
            "label": sentiment_label,
            "confidence": confidence,
            "reasoning": reasoning
        }
