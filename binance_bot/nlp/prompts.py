"""LLM prompts and JSON schemas for command parsing."""

PARSE_COMMAND_PROMPT = """You are a cryptocurrency trading strategy parser. Your job is to extract structured parameters from natural language trading commands.

SUPPORTED STRATEGIES:
1. TWAP (Time-Weighted Average Price) - Split large orders over time
2. Grid Trading - Place buy/sell orders at regular intervals
3. Market Order - Execute immediately at market price

PARAMETERS TO EXTRACT:

General:
- strategy: "twap" | "grid" | "market"
- symbol: Trading pair (e.g., "BTCUSDT", "SOLUSDT", "ETHUSDT")
- side: "BUY" | "SELL" (default: "BUY")
- quantity: Amount to trade (e.g., 0.5, 1.0)

TWAP specific:
- duration_seconds: How long to spread the order (convert from minutes/hours)
- num_orders: Number of slices/orders

Grid specific:
- lower_price: Bottom of price range
- upper_price: Top of price range
- grids: Number of grid levels
- quantity_per_grid: Amount per grid level (optional)

Conditions (optional):
- rsi_below: Execute only if RSI is below this value
- rsi_above: Execute only if RSI is above this value
- sentiment_above: Execute only if sentiment score is above this value
- sentiment_below: Execute only if sentiment score is below this value
- pause_on_bearish: Pause if market turns bearish (true/false)

SYMBOL ALIASES:
- BTC, Bitcoin → BTCUSDT
- ETH, Ethereum → ETHUSDT
- SOL, Solana → SOLUSDT
- Convert to trading pair format if needed

TIME CONVERSIONS:
- "30 minutes" → 1800 seconds
- "1 hour" → 3600 seconds
- "2 hours" → 7200 seconds

USER COMMAND:
{command}

RESPOND ONLY WITH VALID JSON (no markdown, no explanations):
{{
  "intent": "twap" | "grid" | "market",
  "parameters": {{
    "symbol": "...",
    "side": "BUY" | "SELL",
    "quantity": number,
    "duration_seconds": number (TWAP only),
    "num_orders": number (TWAP only),
    "lower_price": number (Grid only),
    "upper_price": number (Grid only),
    "grids": number (Grid only),
    "quantity_per_grid": number (Grid only, optional),
    "conditions": {{
      "rsi_below": number (optional),
      "rsi_above": number (optional),
      "sentiment_above": number (optional),
      "sentiment_below": number (optional),
      "pause_on_bearish": boolean (optional)
    }}
  }},
  "confidence": 0.0-1.0,
  "error": null | "error message if command is unclear"
}}

EXAMPLES:

Input: "Set up a grid strategy for SOL between $130 and $150 with 10 grids, but only if RSI is below 40"
Output: {{"intent": "grid", "parameters": {{"symbol": "SOLUSDT", "side": "BUY", "lower_price": 130.0, "upper_price": 150.0, "grids": 10, "conditions": {{"rsi_below": 40}}}}, "confidence": 0.95, "error": null}}

Input: "Buy 0.5 BTC using TWAP over 2 hours with 12 slices, pause if sentiment goes bearish"
Output: {{"intent": "twap", "parameters": {{"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.5, "duration_seconds": 7200, "num_orders": 12, "conditions": {{"pause_on_bearish": true}}}}, "confidence": 0.92, "error": null}}

Now parse the user command above and respond with JSON only.
"""

# Example commands for UI autocomplete
EXAMPLE_COMMANDS = [
    "Buy 0.5 BTC using TWAP over 1 hour with 12 slices",
    "Set up grid for SOL between $130 and $150 with 10 grids",
    "Execute TWAP for 1 ETH over 30 minutes, pause if bearish",
    "Create grid bot for BTC from 60000 to 65000, 20 grids",
    "Buy 0.2 BTC only if RSI is below 30",
    "Sell 1 ETH using TWAP over 2 hours if sentiment above 70",
    "Grid strategy for SOL $120-$160, 15 grids, 0.5 SOL per grid",
]
