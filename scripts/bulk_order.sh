#!/bin/bash

# Example script to execute a sequence of orders
# Usage: ./scripts/bulk_order.sh

# Get absolute path to main.py
BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN_SCRIPT="$BOT_ROOT/main.py"

SYMBOL="BTCUSDT"
QUANTITY="0.002"

echo "Running Bulk Order Strategy..."
echo "1. Buying $QUANTITY $SYMBOL (Market)..."

python3 "$MAIN_SCRIPT" \
  --symbol "$SYMBOL" \
  --side BUY \
  --type MARKET \
  --quantity "$QUANTITY"

if [ $? -eq 0 ]; then
  echo "Buy successful. Waiting 2 seconds..."
  sleep 2

  echo "2. Setting Limit Sell for profit..."
  # Example: Place a sell order at a higher price (adjust price as needed for logic)
  # For this demo, we'll just place a limit sell at 100,000
  python3 "$MAIN_SCRIPT" \
    --symbol "$SYMBOL" \
    --side SELL \
    --type LIMIT \
    --quantity "$QUANTITY" \
    --price 100000

  if [ $? -eq 0 ]; then
    echo "Limit Sell placed successfully."
  else
    echo "Failed to place Limit Sell."
  fi
else
  echo "Buy failed. Aborting strategy."
fi
