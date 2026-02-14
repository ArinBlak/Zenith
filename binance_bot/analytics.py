"""Portfolio analytics calculation service."""
import logging
from typing import Any

logger = logging.getLogger(__name__)


class PortfolioAnalytics:
    """Calculate portfolio performance metrics from trade history."""
    
    def __init__(self, trades: list[dict[str, Any]]):
        """Initialize analytics with trade history.
        
        Args:
            trades: List of trade dictionaries from Binance API
        """
        self.trades = trades
    
    def calculate_win_rate(self) -> float:
        """Calculate win rate percentage.
        
        Win rate = (number of profitable trades / total trades) * 100
        
        Returns:
            Win rate as percentage (0-100)
        """
        if not self.trades:
            return 0.0
        
        profitable = sum(1 for t in self.trades if float(t.get('realizedPnl', 0)) > 0)
        total = len(self.trades)
        
        return (profitable / total * 100) if total > 0 else 0.0
    
    def calculate_profit_factor(self) -> float:
        """Calculate profit factor.
        
        Profit factor = gross profit / gross loss
        Values > 1 indicate profitable trading
        
        Returns:
            Profit factor ratio
        """
        if not self.trades:
            return 0.0
        
        gross_profit = sum(
            float(t.get('realizedPnl', 0)) 
            for t in self.trades 
            if float(t.get('realizedPnl', 0)) > 0
        )
        gross_loss = abs(sum(
            float(t.get('realizedPnl', 0)) 
            for t in self.trades 
            if float(t.get('realizedPnl', 0)) < 0
        ))
        
        return gross_profit / gross_loss if gross_loss > 0 else 0.0
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio.
        
        Sharpe = (average return - risk free rate) / standard deviation
        Higher values indicate better risk-adjusted returns
        
        Args:
            risk_free_rate: Annual risk-free rate (default 0%)
            
        Returns:
            Sharpe ratio
        """
        if len(self.trades) < 2:
            return 0.0
        
        returns = [float(t.get('realizedPnl', 0)) for t in self.trades]
        
        # Calculate average and standard deviation
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5
        
        if std_dev == 0:
            return 0.0
        
        return (avg_return - risk_free_rate) / std_dev
    
    def calculate_sortino_ratio(self, risk_free_rate: float = 0.0) -> float:
        """Calculate Sortino ratio.
        
        Sortino = (average return - risk free rate) / downside deviation
        Similar to Sharpe but only considers downside volatility
        
        Args:
            risk_free_rate: Annual risk-free rate (default 0%)
            
        Returns:
            Sortino ratio
        """
        if len(self.trades) < 2:
            return 0.0
        
        returns = [float(t.get('realizedPnl', 0)) for t in self.trades]
        avg_return = sum(returns) / len(returns)
        
        # Calculate downside deviation (only negative returns)
        downside_returns = [r for r in returns if r < 0]
        
        if not downside_returns:
            return 0.0
        
        downside_variance = sum(r ** 2 for r in downside_returns) / len(downside_returns)
        downside_dev = downside_variance ** 0.5
        
        if downside_dev == 0:
            return 0.0
        
        return (avg_return - risk_free_rate) / downside_dev
    
    def get_pnl_by_symbol(self) -> dict[str, float]:
        """Aggregate realized PnL by trading symbol.
        
        Returns:
            Dictionary mapping symbol to total realized PnL
        """
        pnl_map: dict[str, float] = {}
        
        for trade in self.trades:
            symbol = trade.get('symbol', '')
            pnl = float(trade.get('realizedPnl', 0))
            
            if symbol:
                pnl_map[symbol] = pnl_map.get(symbol, 0.0) + pnl
        
        return pnl_map
    
    def get_total_pnl(self) -> float:
        """Calculate total realized PnL across all trades.
        
        Returns:
            Total realized PnL
        """
        return sum(float(t.get('realizedPnl', 0)) for t in self.trades)
    
    def get_all_metrics(self) -> dict[str, Any]:
        """Get all analytics metrics in one call.
        
        Returns:
            Dictionary with all calculated metrics
        """
        return {
            "winRate": round(self.calculate_win_rate(), 2),
            "profitFactor": round(self.calculate_profit_factor(), 2),
            "sharpeRatio": round(self.calculate_sharpe_ratio(), 2),
            "sortinoRatio": round(self.calculate_sortino_ratio(), 2),
            "pnlBySymbol": self.get_pnl_by_symbol(),
            "totalTrades": len(self.trades),
            "totalPnl": round(self.get_total_pnl(), 2)
        }
