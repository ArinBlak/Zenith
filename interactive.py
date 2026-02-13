import sys
import argparse
import rich
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import questionary
from binance_bot.client import BinanceFuturesClient
from binance_bot.config import load_config
from binance_bot.exceptions import BinanceAPIError

console = Console()

def get_client():
    try:
        config = load_config()
        return BinanceFuturesClient(config)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        sys.exit(1)

def print_header():
    console.print(Panel.fit("[bold cyan]Binance Futures Bot[/bold cyan]"))

def place_order_wizard(client: BinanceFuturesClient):
    console.print("[yellow]--- New Order Wizard ---[/yellow]")
    
    symbol = questionary.text("Symbol (e.g. BTCUSDT):", default="BTCUSDT").ask()
    side = questionary.select("Side:", choices=["BUY", "SELL"]).ask()
    order_type = questionary.select(
        "Order Type:", 
        choices=["MARKET", "LIMIT", "STOP", "TAKE_PROFIT", "TRAILING_STOP_MARKET"]
    ).ask()
    
    quantity = float(questionary.text("Quantity:", validate=lambda text: text.replace('.', '', 1).isdigit()).ask())
    
    price = None
    stop_price = None
    callback_rate = None
    
    if order_type in ["LIMIT", "STOP", "TAKE_PROFIT"]:
        price = float(questionary.text("Price:", validate=lambda text: text.replace('.', '', 1).isdigit()).ask())
        
    if order_type in ["STOP", "TAKE_PROFIT", "STOP_MARKET", "TAKE_PROFIT_MARKET"]:
        stop_price = float(questionary.text("Stop Price:", validate=lambda text: text.replace('.', '', 1).isdigit()).ask())

    if order_type == "TRAILING_STOP_MARKET":
        callback_rate = float(questionary.text("Callback Rate (0.1-5.0):", validate=lambda text: text.replace('.', '', 1).isdigit()).ask())

    confirm = questionary.confirm(f"Place {side} {order_type} for {quantity} {symbol}?").ask()
    
    if confirm:
        with console.status("[bold green]Placing order..."):
            try:
                response = client.place_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    price=price,
                    stop_price=stop_price,
                    callback_rate=callback_rate
                )
                console.print(Panel(str(response), title="Order Response", style="green"))
            except BinanceAPIError as e:
                error_map = {
                    -2019: "Insufficient margin to place this order.",
                    -4164: "Order size is below minimum notional requirement.",
                    -4024: "Limit price is outside allowed range."
                }

                clean_message = error_map.get(e.code, "Order failed. Please check parameters.")

                logger.error(f"Binance error {e.code}: {e.message}")

                console.print(clean_message)
                console.print("[red]Error: {e}[/red]")

            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

def view_account_info(client: BinanceFuturesClient):
    # This would require adding an endpoint for account info to client.py
    # For now, we can just stub it or add the method
    console.print("[dim]Account info not implemented yet in client.[/dim]")

def main():
    print_header()
    client = get_client()

    while True:
        choice = questionary.select(
            "Main Menu:",
            choices=[
                "Place Order",
                "Start TWAP Strategy",
                "Start Grid Strategy",
                "Exit"
            ]
        ).ask()

        if choice == "Place Order":
            place_order_wizard(client)
        elif choice == "Exit":
            console.print("[cyan]Goodbye![/cyan]")
            break
        elif choice == "Start TWAP Strategy":
            symbol = questionary.text("Symbol:", default="BTCUSDT").ask()
            side = questionary.select("Side:", choices=["BUY", "SELL"]).ask()
            total_qty = float(questionary.text("Total Quantity:", validate=lambda text: text.replace('.', '', 1).isdigit()).ask())
            duration = int(questionary.text("Duration (seconds):", validate=lambda text: text.isdigit()).ask())
            num_orders = int(questionary.text("Number of Orders:", validate=lambda text: text.isdigit()).ask())
            
            from binance_bot.strategies.twap import TWAPStrategy
            strategy = TWAPStrategy(client, symbol, side, total_qty, duration, num_orders)
            console.print("[green]Starting TWAP... (Ctrl+C to interrupt)[/green]")
            try:
                strategy.run()
            except KeyboardInterrupt:
                console.print("[yellow]Strategy interrupted.[/yellow]")
            except Exception as e:
                console.print(f"[red]Strategy Error: {e}[/red]")

        elif choice == "Start Grid Strategy":
            symbol = questionary.text("Symbol:", default="BTCUSDT").ask()
            lower = float(questionary.text("Lower Price:", validate=lambda text: text.replace('.', '', 1).isdigit()).ask())
            upper = float(questionary.text("Upper Price:", validate=lambda text: text.replace('.', '', 1).isdigit()).ask())
            grids = int(questionary.text("Number of Grids:", validate=lambda text: text.isdigit()).ask())
            qty_per_grid = float(questionary.text("Qty per Grid:", validate=lambda text: text.replace('.', '', 1).isdigit()).ask())
            
            from binance_bot.strategies.grid import GridStrategy
            strategy = GridStrategy(client, symbol, lower, upper, grids, qty_per_grid)
            console.print("[green]Starting Grid... (Ctrl+C to interrupt)[/green]")
            try:
                strategy.run()
            except KeyboardInterrupt:
                console.print("[yellow]Strategy interrupted.[/yellow]")
            except Exception as e:
                console.print(f"[red]Strategy Error: {e}[/red]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[red]Exiting...[/red]")
        sys.exit(0)
