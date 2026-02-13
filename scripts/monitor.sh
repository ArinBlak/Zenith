#!/bin/bash

# Script to monitor the bot's log file in real-time
# Usage: ./scripts/monitor.sh

# Get absolute path to log file
BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$BOT_ROOT/binance_bot.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found at $LOG_FILE"
    echo "Creating empty log file..."
    touch "$LOG_FILE"
fi

echo "Monitoring $LOG_FILE..."
echo "Press Ctrl+C to stop."
echo "--------------------------------"

tail -f "$LOG_FILE"
