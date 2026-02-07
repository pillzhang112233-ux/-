"""
交易协调器

职责：
- 协调完整的交易流程
- 调用策略决策器、价格查询器、执行器
- 统一错误处理和日志记录
"""

import logging

logger = logging.getLogger(__name__)


class TradingCoordinator:
    """
    交易协调器
    
    功能：
    - 接收交易信号
    - 协调策略决策 → 价格查询 → 交易执行
    - 统一处理交易流程
    """
    
    def __init__(self, strategy, price_oracle, executor):
        """
        初始化协调器
        
        参数:
            strategy: TradingStrategy - 策略决策器
            price_oracle: PriceOracle - 价格查询器
            executor: VirtualExecutor - 虚拟执行器
        """
        self.strategy = strategy
        self.price_oracle = price_oracle
        self.executor = executor
    
    def process_signal(self, signal):
        """
        处理交易信号（完整流程）
        
        参数:
            signal: TradeSignal - 交易信号
        
        返回:
            ExecutionResult - 执行结果
        
        流程：
        1. 策略决策
        2. 查询价格
        3. 执行交易
        4. 返回结果
        """
        pass
