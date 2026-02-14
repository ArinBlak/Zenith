# Text-to-Trade UI Integration Guide

## Quick Setup

The Text-to-Trade feature is fully implemented on the backend with all NLP parsing, RSI calculations, and API endpoints ready. To complete the frontend integration, add the following to your `templates/index.html`:

### 1. Add Search Bar HTML

Insert this **after line 709** (`</div>` closing the ambient-bg div) and **before line 711** (`<div class="container">`):

```html
<h1>⚡ Zenith Trading Bot</h1>

<!-- Text-to-Trade Search Bar -->
<div class="command-search-container">
    <div class="command-search">
        <input type="text" id="trade-command" 
               placeholder="Try: 'Buy 0.5 BTC with TWAP over 1 hour' or 'Set up grid for SOL $130-$150'" 
               autocomplete="off">
        <button onclick="parseCommand()" id="parse-btn">Parse</button>
    </div>
    <div class="suggestions">
        <div class="suggestion-chip" onclick="fillCommand(this.textContent)">Buy 0.5 BTC using TWAP over 1 hour with 12 slices</div>
        <div class="suggestion-chip" onclick="fillCommand(this.textContent)">Set up grid for SOL between $130 and $150 with 10 grids</div>
        <div class="suggestion-chip" onclick="fillCommand(this.textContent)">Execute TWAP for 1 ETH over 30 minutes, pause if bearish</div>
    </div>
    <div id="parsed-preview" style="display:none;">
        <div class="preview-header">
            <div class="preview-title" id="preview-strategy"></div>
            <div class="preview-confidence" id="preview-confidence"></div>
        </div>
        <div class="param-grid" id="preview-params"></div>
        <div id="preview-error" class="error-message" style="display:none;"></div>
        <div class="preview-actions">
            <button class="btn-execute" onclick="executeStrategy()">✓ Execute Strategy</button>
            <button class="btn-cancel" onclick="cancelCommand()">✕ Cancel</button>
        </div>
    </div>
</div>
```

### 2. Add JavaScript File

At the end of `index.html`, just before `</body>`, add:

```html
<script src="/static/text_to_trade.js"></script>
```

## Features

### Natural Language Commands

Try these example commands:
- "Buy 0.5 BTC using TWAP over 1 hour with 12 slices"
- "Set up grid for SOL between $130 and $150 with 10 grids"
- "Execute TWAP for 1 ETH over 30 minutes, pause if bearish"
- "Buy 0.2 BTC only if RSI is below 30"
- "Grid strategy for BTC from 60000 to 65000, 20 grids, only if sentiment above 60"

### Supported Strategies

1. **TWAP (Time-Weighted Average Price)**
   - Parameters: symbol, quantity, duration, number of orders
   - Conditions: RSI, sentiment, pause on bearish

2. **Grid Trading**
   - Parameters: symbol, lower/upper price, number of grids, quantity per grid
   - Conditions: RSI, sentiment thresholds

3. **Market Order**
   - Parameters: symbol, side, quantity
   - Executes immediately at market price

### Condition Support

- **RSI**: "only if RSI is below 40" or "if RSI > 70"
- **Sentiment**: "if sentiment above 60" or "pause if bearish"
- **Combined**: "Set up grid for SOL $130-$150, RSI < 35, sentiment > 55"

## How It Works

1. **User types command** → Click "Parse" or press Enter
2. **LLM analyzes** → llama3.1:8b extracts parameters as JSON
3. **Preview shown** → User reviews parsed strategy and conditions  
4. **Condition check** → RSI/sentiment evaluated in real-time
5. **Execute** → Strategy runs in background, monitored in dashboard

## API Endpoints

- **POST /parse-command**: Parse natural language → structured parameters
- **POST /execute-strategy**: Execute with condition validation

## Files Created

- `binance_bot/nlp/parser.py` - LLM command parser
- `binance_bot/nlp/conditions.py` - Condition evaluator  
- `binance_bot/nlp/prompts.py` - LLM prompts
- `binance_bot/indicators/rsi.py` - RSI calculator
- `static/text_to_trade.js` - Frontend JavaScript
- Updated `web_api.py` with new endpoints

## Testing

Restart your server:
```bash
python web_api.py
```

Then try parsing a command in the search bar. The LLM will analyze it and show you the extracted parameters before execution!
