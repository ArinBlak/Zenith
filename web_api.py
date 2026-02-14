from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import logging
import json
import asyncio
import websockets
from typing import Annotated, List
from contextlib import asynccontextmanager

from binance_bot.client import BinanceFuturesClient
from binance_bot.config import load_config
from binance_bot.sentiment import SentimentWorker
from binance_bot.nlp import LLMCommandParser, ConditionEvaluator
from binance_bot.strategies.twap import TWAPStrategy
from binance_bot.strategies.grid import GridStrategy

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web_ui")

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

# Background Price Streamer
async def binance_price_streamer():
    """Background task to stream price updates from Binance to all connected clients."""
    binance_ws_url = "wss://fstream.binancefuture.com/ws/!markPrice@arr"
    while True:
        try:
            async with websockets.connect(binance_ws_url) as ws:
                logger.info("Connected to Binance WebSocket")
                while True:
                    data = await ws.recv()
                    prices = json.loads(data)
                    # We only care about major pairs for the UI logs
                    updates = []
                    for p in prices:
                        symbol = p['s']
                        if symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]:
                            updates.append({
                                "symbol": symbol,
                                "price": f"{float(p['p']):.2f}",
                                "time": time.strftime("%H:%M:%S")
                            })
                    
                    if updates:
                        await manager.broadcast(json.dumps({"type": "price_update", "data": updates}))
        except Exception as e:
            logger.error(f"WebSocket error: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)

# Global sentiment worker instance
sentiment_worker: SentimentWorker = None
command_parser = None

async def sentiment_update_callback(update: dict):
    """Callback for sentiment updates to broadcast via WebSocket."""
    try:
        await manager.broadcast(json.dumps({
            "type": "sentiment_update",
            "data": update.get("market", {})
        }))
    except Exception as e:
        logger.error(f"Error broadcasting sentiment update: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global sentiment_worker, command_parser
    
    # Startup
    stream_task = asyncio.create_task(binance_price_streamer())
    
    # Initialize command parser
    try:
        logger.info("Initializing command parser...")
        command_parser = LLMCommandParser()
        logger.info("Command parser initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize command parser: {e}")
    
    # Initialize and start sentiment worker
    try:
        logger.info("Starting sentiment worker...")
        sentiment_worker = SentimentWorker(on_update=sentiment_update_callback)
        
        # Get active symbols from client
        symbols = None
        if client:
            symbols = client.get_active_symbols()
            logger.info(f"Monitoring sentiment for symbols: {symbols}")
        
        await sentiment_worker.start(symbols)
        logger.info("Sentiment worker started successfully")
    except Exception as e:
        logger.error(f"Failed to start sentiment worker: {e}")
    
    yield
    
    # Shutdown
    stream_task.cancel()
    if sentiment_worker:
        await sentiment_worker.stop()

app = FastAPI(title="Binance Bot Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
import time

# Initialize Client
try:
    config = load_config()
    client = BinanceFuturesClient(config)
except Exception as e:
    logger.error(f"Failed to initialize client: {e}")
    client = None

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "message": None})

@app.post("/order", response_class=HTMLResponse)
async def place_order(
    request: Request,
    symbol: Annotated[str, Form()],
    side: Annotated[str, Form()],
    order_type: Annotated[str, Form()],
    quantity: Annotated[float, Form()],
    price: Annotated[float, Form()] = None,
    stop_price: Annotated[float, Form()] = None,
    reduce_only: Annotated[bool, Form()] = False
):
    if not client:
        return templates.TemplateResponse("index.html", {"request": request, "message": "Error: Client not initialized (check .env)"})
    
    try:
        response = client.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            reduce_only=reduce_only
        )
        msg = f"Order Success: {response.get('orderId', 'Unknown ID')} ({response.get('status')})"
        return templates.TemplateResponse("index.html", {"request": request, "message": msg, "msg_type": "success"})
    except Exception as e:
        return templates.TemplateResponse("index.html", {"request": request, "message": f"Order Failed: {e}", "msg_type": "error"})

@app.get("/account")
async def get_account_info():
    if not client:
        return {"error": "Client not initialized"}
    try:
        info = client.get_account_info()
        positions = client.get_position_risk()
        return {"info": info, "positions": positions}
    except Exception as e:
        return {"error": str(e)}

from fastapi import BackgroundTasks
from binance_bot.strategies.twap import TWAPStrategy
from binance_bot.strategies.grid import GridStrategy

@app.post("/active-twap")
async def start_twap(
    request: Request,
    background_tasks: BackgroundTasks,
    symbol: Annotated[str, Form()],
    side: Annotated[str, Form()],
    total_qty: Annotated[float, Form()],
    duration: Annotated[int, Form()],
    num_orders: Annotated[int, Form()]
):
    if not client:
        return templates.TemplateResponse("index.html", {"request": request, "message": "Client not initialized", "msg_type": "error"})

    try:
        strategy = TWAPStrategy(client, symbol, side, total_qty, duration, num_orders)
        background_tasks.add_task(strategy.run)
        msg = f"Started TWAP: {side} {total_qty} {symbol} over {duration}s"
        return templates.TemplateResponse("index.html", {"request": request, "message": msg, "msg_type": "success"})
    except Exception as e:
        return templates.TemplateResponse("index.html", {"request": request, "message": f"Strategy Error: {e}", "msg_type": "error"})

@app.post("/active-grid")
async def start_grid(
    request: Request,
    background_tasks: BackgroundTasks,
    symbol: Annotated[str, Form()],
    lower_price: Annotated[float, Form()],
    upper_price: Annotated[float, Form()],
    grids: Annotated[int, Form()],
    qty_per_grid: Annotated[float, Form()]
):
    if not client:
        return templates.TemplateResponse("index.html", {"request": request, "message": "Client not initialized", "msg_type": "error"})

    try:
        strategy = GridStrategy(client, symbol, lower_price, upper_price, grids, qty_per_grid)
        background_tasks.add_task(strategy.run)
        msg = f"Started Grid: {grids} grids on {symbol}"
        return templates.TemplateResponse("index.html", {"request": request, "message": msg, "msg_type": "success"})
    except Exception as e:
        return templates.TemplateResponse("index.html", {"request": request, "message": f"Strategy Error: {e}", "msg_type": "error"})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/sentiment/market")
async def get_market_sentiment():
    """Get overall market sentiment."""
    if not sentiment_worker:
        return {"error": "Sentiment service not available"}
    try:
        sentiment = sentiment_worker.get_market_sentiment()
        return sentiment
    except Exception as e:
        logger.error(f"Error getting market sentiment: {e}")
        return {"error": str(e)}

@app.get("/api/account")
async def get_account():
    """Get account balance and PnL data."""
    if not client:
        return {"error": "Client not initialized"}
    
    try:
        account_info = client.get_account_info()
        
        # Extract key metrics
        total_balance = float(account_info.get("totalWalletBalance", 0))
        unrealized_pnl = float(account_info.get("totalUnrealizedProfit", 0))
        available_balance = float(account_info.get("availableBalance", 0))
        total_margin = float(account_info.get("totalMarginBalance", 0))
        
        # Calculate margin ratio
        margin_ratio = 0.0
        if total_margin > 0:
            used_margin = total_margin - available_balance
            margin_ratio = (used_margin / total_margin) * 100
        
        return {
            "walletBalance": total_balance,
            "unrealizedPnL": unrealized_pnl,
            "availableBalance": available_balance,
            "marginRatio": round(margin_ratio, 2)
        }
    except Exception as e:
        logger.error(f"Error fetching account info: {e}")
        return {"error": str(e)}

@app.get("/api/positions")
async def get_positions():
    """Get open positions."""
    if not client:
        return {"error": "Client not initialized"}
    
    try:
        positions = client.get_position_info()
        
        # Filter out positions with zero quantity
        active_positions = [
            {
                "symbol": pos["symbol"],
                "size": float(pos["positionAmt"]),
                "entryPrice": float(pos["entryPrice"]),
                "unrealizedProfit": float(pos["unRealizedProfit"]),
                "leverage": int(pos["leverage"]),
                "liquidationPrice": float(pos["liquidationPrice"])
            }
            for pos in positions
            if float(pos.get("positionAmt", 0)) != 0
        ]
        
        return {"positions": active_positions}
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return {"error": str(e)}

@app.get("/api/analytics")
async def get_analytics(days: int = 30):
    """Get portfolio analytics for recent period."""
    if not client:
        return {"error": "Client not initialized"}
    
    try:
        import time
        from binance_bot.analytics import PortfolioAnalytics
        
        # Fetch all recent trades (limit 1000)
        trades = client.get_account_trades(limit=1000)
        
        if not trades:
            return {
                "winRate": 0.0,
                "profitFactor": 0.0,
                "sharpeRatio": 0.0,
                "sortinoRatio": 0.0,
                "pnlBySymbol": {},
                "totalTrades": 0,
                "totalPnl": 0.0
            }
        
        # Filter by time period (days parameter)
        cutoff_time = int((time.time() - (days * 86400)) * 1000)
        recent_trades = [t for t in trades if int(t.get('time', 0)) >= cutoff_time]
        
        if not recent_trades:
            return {
                "winRate": 0.0,
                "profitFactor": 0.0,
                "sharpeRatio": 0.0,
                "sortinoRatio": 0.0,
                "pnlBySymbol": {},
                "totalTrades": 0,
                "totalPnl": 0.0
            }
        
        # Calculate analytics
        analytics = PortfolioAnalytics(recent_trades)
        return analytics.get_all_metrics()
        
    except Exception as e:
        logger.error(f"Error calculating analytics: {e}")
        return {"error": str(e)}

@app.get("/sentiment/{symbol}")
async def get_symbol_sentiment(symbol: str):
    """Get sentiment for a specific symbol."""
    if not sentiment_worker:
        return {"error": "Sentiment service not available"}
    try:
        sentiment = sentiment_worker.get_sentiment(symbol.upper())
        return sentiment
    except Exception as e:
        logger.error(f"Error getting sentiment for {symbol}: {e}")
        return {"error": str(e)}

@app.get("/sentiment/breakdown/{symbol}")
async def get_sentiment_breakdown(symbol: str = None):
    """Get sentiment breakdown by source."""
    if not sentiment_worker:
        return {"error": "Sentiment service not available"}
    try:
        breakdown = sentiment_worker.get_breakdown(symbol.upper() if symbol else None)
        return breakdown
    except Exception as e:
        logger.error(f"Error getting sentiment breakdown: {e}")
        return {"error": str(e)}

@app.get("/sentiment/history/{symbol}")
async def get_sentiment_history(symbol: str, hours: int = 24):
    """Get sentiment history for a symbol."""
    if not sentiment_worker:
        return {"error": "Sentiment service not available"}
    try:
        history = sentiment_worker.get_history(symbol.upper(), hours)
        return {"history": history}
    except Exception as e:
        logger.error(f"Error getting sentiment history: {e}")
        return {"error": str(e)}

# Text-to-Trade NLP Parser
# Initialized in lifespan function above

@app.post("/parse-command")
async def parse_command(request: Request):
    """Parse a natural language trading command.
    
    Example: "Buy 0.5 BTC using TWAP over 1 hour with 12 slices"
    """
    try:
        data = await request.json()
        command = data.get("command", "")
        
        if not command:
            return {"error": "No command provided"}
        
        if not command_parser:
            return {"error": "Parser not initialized"}
        
        # Parse the command using LLM
        result = await command_parser.parse(command)
        
        # Validate parameters if parsing succeeded
        if result["intent"] and not result.get("error"):
            validation = command_parser.validate_parameters(
                result["intent"],
                result["parameters"]
            )
            result["validation"] = validation
        
        logger.info(f"Parsed command: {command[:50]}... -> {result['intent']}")
        return result
    
    except Exception as e:
        logger.error(f"Error parsing command: {e}")
        return {"error": str(e)}

@app.post("/execute-strategy")
async def execute_strategy(request: Request, background_tasks: BackgroundTasks):
    """Execute a trading strategy from parsed parameters.
    
    This endpoint checks conditions (RSI, sentiment) before execution.
    """
    try:
        data = await request.json()
        intent = data.get("intent")
        params = data.get("parameters", {})
        
        if not intent:
            return {"error": "No strategy intent provided"}
        
        # Check conditions if present
        conditions = params.get("conditions", {})
        if conditions:
            evaluator = ConditionEvaluator(
                client=client,
                sentiment_worker=sentiment_worker
            )
            
            symbol = params.get("symbol", "BTCUSDT")
            cond_result = await evaluator.evaluate(symbol, conditions)
            
            if not cond_result["met"]:
                return {
                    "status": "conditions_not_met",
                    "message": "Trading conditions not satisfied",
                    "details": cond_result["details"],
                    "errors": cond_result["errors"]
                }
        
        # Execute strategy based on intent
        if intent == "twap":
            # Create TWAP strategy
            strategy = TWAPStrategy(
                client=client,
                symbol=params.get("symbol", "BTCUSDT"),
                side=params.get("side", "BUY"),
                total_quantity=params.get("quantity", 0),
                duration_seconds=params.get("duration_seconds", 3600),
                num_orders=params.get("num_orders", 10),
                min_sentiment_score=conditions.get("sentiment_above") if conditions else None,
                pause_on_bearish=conditions.get("pause_on_bearish", False) if conditions else False,
                sentiment_worker=sentiment_worker
            )
            
            # Run in background
            background_tasks.add_task(strategy.run)
            
            return {
                "status": "executing",
                "strategy": "twap",
                "message": f"TWAP strategy started for {params.get('symbol')}"
            }
        
        elif intent == "grid":
            # Create Grid strategy
            strategy = GridStrategy(
                client=client,
                symbol=params.get("symbol", "BTCUSDT"),
                lower_price=params.get("lower_price", 0),
                upper_price=params.get("upper_price", 0),
                grids=params.get("grids", 10),
                quantity_per_grid=params.get("quantity_per_grid", 0.01),
                sentiment_threshold=conditions.get("sentiment_above") if conditions else None,
                sentiment_worker=sentiment_worker
            )
            
            # Run in background
            background_tasks.add_task(strategy.run)
            
            return {
                "status": "executing",
                "strategy": "grid",
                "message": f"Grid strategy started for {params.get('symbol')}"
            }
        
        elif intent == "market":
            # Execute market order immediately
            order = client.place_order(
                symbol=params.get("symbol", "BTCUSDT"),
                side=params.get("side", "BUY"),
                order_type="MARKET",
                quantity=params.get("quantity", 0)
            )
            
            return {
                "status": "executed",
                "strategy": "market",
                "order": order
            }
        
        else:
            return {"error": f"Unknown strategy intent: {intent}"}
    
    except Exception as e:
        logger.error(f"Error executing strategy: {e}")
        return {"error": str(e)}

@app.get("/logs")
async def get_logs():
    try:
        with open("binance_bot.log", "r") as f:
            lines = f.readlines()
            return {"logs": lines[-50:]} # Return last 50 lines
    except FileNotFoundError:
        return {"logs": ["Log file not found."]}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
