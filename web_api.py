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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    stream_task = asyncio.create_task(binance_price_streamer())
    yield
    # Shutdown
    stream_task.cancel()

app = FastAPI(title="Binance Bot Dashboard", lifespan=lifespan)
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
