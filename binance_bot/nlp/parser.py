"""LLM-based command parser for natural language trading commands."""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
import ollama

from .prompts import PARSE_COMMAND_PROMPT

logger = logging.getLogger("nlp.parser")


class LLMCommandParser:
    """Parse natural language commands into structured trading parameters."""
    
    def __init__(self, model: str = "llama3.1:8b", host: str = "http://localhost:11434"):
        self.model = model
        self.client = ollama.Client(host=host)
        
        # Test connection
        try:
            self.client.list()
            logger.info(f"LLM Command Parser initialized with model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
    
    async def parse(self, command: str) -> Dict[str, Any]:
        """Parse a natural language command into structured parameters.
        
        Args:
            command: Natural language trading command
        
        Returns:
            Dict with keys: intent, parameters, confidence, error
        """
        if not command or not command.strip():
            return {
                "intent": None,
                "parameters": {},
                "confidence": 0.0,
                "error": "Empty command"
            }
        
        prompt = PARSE_COMMAND_PROMPT.format(command=command.strip())
        
        try:
            # Run LLM inference in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.generate(
                    model=self.model,
                    prompt=prompt,
                    options={
                        "temperature": 0.1,  # Low temperature for consistent parsing
                        "num_predict": 500,  # Enough for JSON response
                    }
                )
            )
            
            result = self._parse_response(response['response'])
            logger.info(f"Parsed command: '{command[:50]}...' -> {result['intent']} (confidence: {result['confidence']})")
            
            return result
        
        except Exception as e:
            logger.error(f"Error parsing command: {e}")
            return {
                "intent": None,
                "parameters": {},
                "confidence": 0.0,
                "error": f"Parsing error: {str(e)}"
            }
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM JSON response."""
        try:
            # Clean up response - remove markdown code blocks if present
            response = response.strip()
            if response.startswith("```"):
                # Extract JSON from markdown code block
                lines = response.split("\n")
                json_lines = []
                in_code_block = False
                for line in lines:
                    if line.startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block or not line.startswith("```"):
                        json_lines.append(line)
                response = "\n".join(json_lines)
            
            # Parse JSON
            parsed = json.loads(response)
            
            # Validate required fields
            if "intent" not in parsed:
                return {
                    "intent": None,
                    "parameters": {},
                    "confidence": 0.0,
                    "error": "Missing intent in response"
                }
            
            # Ensure parameters dict exists
            if "parameters" not in parsed:
                parsed["parameters"] = {}
            
            # Ensure confidence is present
            if "confidence" not in parsed:
                parsed["confidence"] = 0.5
            
            # Validate intent
            valid_intents = ["twap", "grid", "market"]
            if parsed["intent"] and parsed["intent"] not in valid_intents:
                return {
                    "intent": None,
                    "parameters": parsed.get("parameters", {}),
                    "confidence": 0.0,
                    "error": f"Unknown intent: {parsed['intent']}"
                }
            
            return parsed
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {response}")
            return {
                "intent": None,
                "parameters": {},
                "confidence": 0.0,
                "error": f"Invalid JSON response: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {e}")
            return {
                "intent": None,
                "parameters": {},
                "confidence": 0.0,
                "error": f"Parsing error: {str(e)}"
            }
    
    def validate_parameters(self, intent: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate extracted parameters for a given intent.
        
        Args:
            intent: Strategy type (twap, grid, market)
            params: Extracted parameters
        
        Returns:
            Dict with keys: valid (bool), errors (list), warnings (list)
        """
        errors = []
        warnings = []
        
        # Check required fields for all strategies
        if "symbol" not in params or not params["symbol"]:
            errors.append("Missing required parameter: symbol")
        
        if intent == "twap":
            # TWAP requirements
            if "quantity" not in params or params["quantity"] <= 0:
                errors.append("TWAP requires quantity > 0")
            if "duration_seconds" not in params or params["duration_seconds"] <= 0:
                errors.append("TWAP requires duration_seconds > 0")
            if "num_orders" not in params or params["num_orders"] < 1:
                errors.append("TWAP requires num_orders >= 1")
        
        elif intent == "grid":
            # Grid requirements
            if "lower_price" not in params or params["lower_price"] <= 0:
                errors.append("Grid requires lower_price > 0")
            if "upper_price" not in params or params["upper_price"] <= 0:
                errors.append("Grid requires upper_price > 0")
            if "grids" not in params or params["grids"] < 2:
                errors.append("Grid requires grids >= 2")
            
            # Validate price range
            if "lower_price" in params and "upper_price" in params:
                if params["lower_price"] >= params["upper_price"]:
                    errors.append("lower_price must be less than upper_price")
        
        elif intent == "market":
            # Market order requirements
            if "quantity" not in params or params["quantity"] <= 0:
                errors.append("Market order requires quantity > 0")
        
        # Validate conditions if present
        if "conditions" in params and params["conditions"]:
            conditions = params["conditions"]
            if "rsi_below" in conditions and "rsi_above" in conditions:
                if conditions["rsi_below"] <= conditions["rsi_above"]:
                    errors.append("rsi_below must be greater than rsi_above")
            
            if "sentiment_below" in conditions and "sentiment_above" in conditions:
                if conditions["sentiment_below"] <= conditions["sentiment_above"]:
                    errors.append("sentiment_below must be greater than sentiment_above")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
