"""
数据模型定义

职责：
- 定义所有模块间传递的数据对象
- 统一数据格式和类型
- 方便类型检查和调试

使用 @dataclass 装饰器：
- 自动生成 __init__、__repr__ 等方法
- 支持类型提示
- 代码简洁清晰
"""

from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


# ==================== 枚举类型 ====================

class TradeAction(Enum):
    """交易动作"""
    BUY = "BUY"
    SELL = "SELL"
    SKIP = "SKIP"


class RiskActionType(Enum):
    """风控动作类型"""
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TIME_STOP = "TIME_STOP"


# ==================== 交易信号相关 ====================

@dataclass
class TradeSignal:
    """
    交易信号（从SignalParser输出）
    
    描述聪明钱的一笔交易行为
    """
    signature: str              # 交易签名
    action: str                 # "BUY" 或 "SELL"
    token_mint: str            # 代币地址
    token_symbol: str          # 代币符号
    amount: float              # 交易数量
    sol_amount: float          # SOL数量
    timestamp: int             # 交易时间戳
    
    # 可选字段
    token_decimals: Optional[int] = None
    is_compressed: Optional[bool] = False


# ==================== 价格信息相关 ====================

@dataclass
class PriceInfo:
    """
    价格信息（从PriceOracle输出）
    
    包含代币的实时价格和市场数据
    """
    mint: str                  # 代币地址
    price_sol: float           # SOL计价
    price_usd: float           # USD计价
    liquidity: float           # 流动性（USD）
    market_cap: float          # 市值（USD）
    timestamp: int             # 查询时间戳
    
    # 可选字段
    volume_24h: Optional[float] = None
    price_change_24h: Optional[float] = None
    source: Optional[str] = None  # 价格来源（Jupiter/Raydium等）


# ==================== 交易决策相关 ====================

@dataclass
class TradingDecision:
    """
    交易决策（从TradingStrategy输出）
    
    决定是否跟单、跟多少
    """
    should_trade: bool         # 是否执行交易
    action: TradeAction        # 交易动作
    token_mint: str            # 代币地址
    token_symbol: str          # 代币符号
    amount: float              # 交易数量（代币数量）
    estimated_cost: float      # 预估成本（USD）
    reason: str                # 决策原因（日志用）
    
    # 决策时的上下文
    current_balance: float     # 当前余额
    position_amount: Optional[float] = None  # 当前持仓数量（卖出时）


# ==================== 交易执行相关 ====================

@dataclass
class ExecutionResult:
    """
    交易执行结果（从VirtualExecutor输出）
    
    记录虚拟交易的执行详情
    """
    success: bool              # 是否成功
    action: TradeAction        # 交易动作
    token_mint: str            # 代币地址
    token_symbol: str          # 代币符号
    
    # 执行详情
    executed_price: float      # 实际执行价格（USD，含滑点）
    executed_amount: float     # 实际执行数量
    cost: float                # 实际花费/收入（USD）
    slippage: float            # 滑点百分比
    
    # 余额变化
    balance_before: float      # 执行前余额
    balance_after: float       # 执行后余额
    
    # 时间戳
    timestamp: int             # 执行时间戳
    
    # 可选字段
    error_message: Optional[str] = None  # 失败原因
    realized_pnl: Optional[float] = None  # 实现盈亏（卖出时）


# ==================== 持仓相关 ====================

@dataclass
class Position:
    """
    持仓信息（从PositionManager管理）
    
    记录单个代币的持仓状态
    """
    mint: str                  # 代币地址
    symbol: str                # 代币符号
    amount: float              # 持有数量
    
    # 成本信息
    cost_basis: float          # 平均成本（USD/token）
    total_cost: float          # 总成本（USD）
    
    # 当前价格
    current_price: float       # 当前价格（USD）
    
    # 盈亏
    unrealized_pnl: float      # 未实现盈亏（USD）
    unrealized_pnl_percent: float  # 未实现盈亏百分比
    
    # 时间
    entry_time: int            # 入场时间戳
    last_update_time: int      # 最后更新时间
    
    # 持仓时长（秒）
    @property
    def holding_duration(self) -> int:
        """持仓时长（秒）"""
        import time
        return int(time.time()) - self.entry_time


# ==================== 风控相关 ====================

@dataclass
class RiskAction:
    """
    风控动作（从RiskController输出）
    
    触发风控时需要执行的动作
    """
    action_type: RiskActionType  # 动作类型
    mint: str                    # 代币地址
    symbol: str                  # 代币符号
    reason: str                  # 触发原因
    
    # 持仓信息
    current_pnl_percent: float   # 当前盈亏百分比
    holding_duration: int        # 持仓时长（秒）
    
    # 建议动作
    suggested_amount: float      # 建议卖出数量


# ==================== 性能报告相关 ====================

@dataclass
class PerformanceReport:
    """
    性能报告（从PerformanceAnalyzer输出）
    
    统计交易表现的各项指标
    """
    # 基础统计
    total_trades: int          # 总交易数
    buy_trades: int            # 买入次数
    sell_trades: int           # 卖出次数
    
    # 胜率统计
    winning_trades: int        # 盈利交易数
    losing_trades: int         # 亏损交易数
    win_rate: float            # 胜率（%）
    
    # 盈亏统计
    total_pnl: float           # 总盈亏（USD）
    realized_pnl: float        # 已实现盈亏
    unrealized_pnl: float      # 未实现盈亏
    
    # 平均值
    avg_profit: float          # 平均盈利（USD）
    avg_loss: float            # 平均亏损（USD）
    avg_profit_percent: float  # 平均盈利百分比
    avg_loss_percent: float    # 平均亏损百分比
    
    # 比率
    profit_factor: float       # 盈亏比（总盈利/总亏损）
    
    # 回撤
    max_drawdown: float        # 最大回撤（USD）
    max_drawdown_percent: float # 最大回撤百分比
    
    # 资产状态
    initial_balance: float     # 初始余额
    current_balance: float     # 当前余额
    position_value: float      # 持仓价值
    total_value: float         # 总资产（余额+持仓）
    
    # 收益率
    total_return: float        # 总收益率（%）
    
    # 时间
    start_time: int            # 开始时间
    end_time: int              # 结束时间
    
    # 持仓统计
    current_positions: int     # 当前持仓数


@dataclass
class DailyStats:
    """
    每日统计（性能报告的子集）
    """
    date: str                  # 日期（YYYY-MM-DD）
    trades: int                # 当日交易数
    pnl: float                 # 当日盈亏
    balance: float             # 日末余额
    total_value: float         # 日末总资产


# ==================== 便捷导出 ====================

__all__ = [
    # 枚举
    'TradeAction',
    'RiskActionType',
    
    # 交易流程
    'TradeSignal',
    'PriceInfo',
    'TradingDecision',
    'ExecutionResult',
    
    # 持仓和风控
    'Position',
    'RiskAction',
    
    # 性能分析
    'PerformanceReport',
    'DailyStats',
]
