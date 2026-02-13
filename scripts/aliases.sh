# Binance Bot Aliases
# Source this file to add shortcuts to your shell:
# source scripts/aliases.sh

# Get absolute path to main.py
# For sourced scripts, BASH_SOURCE[0] is reliable in bash, but zsh uses ${(%):-%x}
if [ -n "$BASH_SOURCE" ]; then
    SCRIPT_PATH="$BASH_SOURCE"
elif [ -n "$ZSH_VERSION" ]; then
    SCRIPT_PATH="${(%):-%x}"
else
    SCRIPT_PATH="$0"
fi

BOT_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"
MAIN_SCRIPT="$BOT_ROOT/main.py"

# Function to run the bot
function binance-bot() {
    python3 "$MAIN_SCRIPT" "$@"
}

# --- Shortcuts ---

# Market Buy
# Usage: btc-buy <quantity> [symbol]
# Example: btc-buy 0.001
alias btc-buy='function _btc_buy(){ symbol=${2:-BTCUSDT}; binance-bot --symbol "$symbol" --side BUY --type MARKET --quantity "$1"; }; _btc_buy'

# Market Sell
# Usage: btc-sell <quantity> [symbol]
# Example: btc-sell 0.001
alias btc-sell='function _btc_sell(){ symbol=${2:-BTCUSDT}; binance-bot --symbol "$symbol" --side SELL --type MARKET --quantity "$1"; }; _btc_sell'

# Limit Buy
# Usage: btc-limit-buy <quantity> <price> [symbol]
alias btc-limit-buy='function _btc_limit_buy(){ symbol=${3:-BTCUSDT}; binance-bot --symbol "$symbol" --side BUY --type LIMIT --quantity "$1" --price "$2"; }; _btc_limit_buy'

# Limit Sell
# Usage: btc-limit-sell <quantity> <price> [symbol]
alias btc-limit-sell='function _btc_limit_sell(){ symbol=${3:-BTCUSDT}; binance-bot --symbol "$symbol" --side SELL --type LIMIT --quantity "$1" --price "$2"; }; _btc_limit_sell'

echo "Binance Bot aliases loaded. Try 'btc-buy 0.001'"
