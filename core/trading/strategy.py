"""
交易策略决策器

职责：
- 分析交易信号
- 执行筛选规则
- 计算交易数量
- 生成交易决策
"""

import logging
from typing import Optional
from core.data_models import TradeSignal, TradingDecision, PriceInfo, TradeAction
from core.market.price_oracle import PriceOracle
from core.portfolio.position_manager import PositionManager
from config import TradingConfig

logger = logging.getLogger(__name__)


class TradingStrategy:
    """
    交易策略决策器
    
    功能：
    - 分析信号是否值得跟单
    - 执行筛选规则
    - 计算仓位大小
    - 生成详细的交易决策
    """
    
    def __init__(self, price_oracle: PriceOracle, position_manager: PositionManager):
        """
        初始化策略决策器
        
        参数:
            price_oracle: PriceOracle - 价格查询器
            position_manager: PositionManager - 持仓管理器
        """
        self.price_oracle = price_oracle
        self.position_manager = position_manager
        
        # 加载配置
        self.enable_filtering = TradingConfig.ENABLE_FILTERING
        self.min_liquidity = TradingConfig.MIN_LIQUIDITY
        self.min_market_cap = TradingConfig.MIN_MARKET_CAP
        self.max_market_cap = TradingConfig.MAX_MARKET_CAP
        self.blacklist_tokens = TradingConfig.BLACKLIST_TOKENS
        self.trade_ratio = TradingConfig.TRADE_RATIO
        self.min_trade_amount = TradingConfig.MIN_TRADE_AMOUNT
        
        logger.info(f"✅ 策略决策器初始化完成 (筛选: {'开启' if self.enable_filtering else '关闭'})")
    
    def decide(self, signal: TradeSignal, current_balance: float) -> TradingDecision:
        """
        做出交易决策
        
        参数:
            signal: TradeSignal - 交易信号
            current_balance: float - 当前余额
        
        返回:
            TradingDecision - 交易决策
        """
        # 1. 查询价格和市场数据
        price_info = self.price_oracle.get_price(signal.token_mint)
        
        if not price_info:
            return self._create_skip_decision(
                signal=signal,
                current_balance=current_balance,
                reason="无法获取价格信息"
            )
        
        # 2. 根据信号类型决定动作
        if signal.action == "BUY":
            return self._decide_buy(signal, price_info, current_balance)
        elif signal.action == "SELL":
            return self._decide_sell(signal, price_info, current_balance)
        else:
            return self._create_skip_decision(
                signal=signal,
                current_balance=current_balance,
                reason=f"未知的信号类型: {signal.action}"
            )
    
    def _decide_buy(self, signal: TradeSignal, price_info: PriceInfo, 
                    current_balance: float) -> TradingDecision:
        """
        买入决策
        
        参数:
            signal: TradeSignal - 交易信号
            price_info: PriceInfo - 价格信息
            current_balance: float - 当前余额
        
        返回:
            TradingDecision - 交易决策
        """
        # 检查是否启用筛选
        if self.enable_filtering:
            # 执行筛选
            passed, reason = self._check_filters(signal, price_info)
            
            if not passed:
                return self._create_skip_decision(
                    signal=signal,
                    current_balance=current_balance,
                    reason=reason
                )
        
        # 计算交易数量
        amount, estimated_cost = self._calculate_buy_amount(
            price_info=price_info,
            current_balance=current_balance
        )
        
        if amount <= 0:
            return self._create_skip_decision(
                signal=signal,
                current_balance=current_balance,
                reason="交易金额不足"
            )
        
        # 生成买入决策
        reason = self._generate_buy_reason(signal, price_info)
        
        return TradingDecision(
            should_trade=True,
            action=TradeAction.BUY,
            token_mint=signal.token_mint,
            token_symbol=signal.token_symbol,
            amount=amount,
            estimated_cost=estimated_cost,
            reason=reason,
            current_balance=current_balance
        )
    
    def _decide_sell(self, signal: TradeSignal, price_info: PriceInfo, 
                     current_balance: float) -> TradingDecision:
        """
        卖出决策
        
        参数:
            signal: TradeSignal - 交易信号
            price_info: PriceInfo - 价格信息
            current_balance: float - 当前余额
        
        返回:
            TradingDecision - 交易决策
        """
        # 检查是否有持仓
        position = self.position_manager.get_position(signal.token_mint)
        
        if not position:
            return self._create_skip_decision(
                signal=signal,
                current_balance=current_balance,
                reason="没有持仓，无法卖出"
            )
        
        # 决定卖出数量（全部卖出）
        amount = position.amount
        estimated_income = amount * price_info.price_usd
        
        # 生成卖出决策
        reason = self._generate_sell_reason(signal, price_info, position)
        
        return TradingDecision(
            should_trade=True,
            action=TradeAction.SELL,
            token_mint=signal.token_mint,
            token_symbol=signal.token_symbol,
            amount=amount,
            estimated_cost=estimated_income,  # 卖出时是收入
            reason=reason,
            current_balance=current_balance,
            position_amount=position.amount
        )
    
    def _check_filters(self, signal: TradeSignal, price_info: PriceInfo) -> tuple:
        """
        执行筛选检查
        
        参数:
            signal: TradeSignal - 交易信号
            price_info: PriceInfo - 价格信息
        
        返回:
            tuple - (是否通过, 原因)
        """
        # 1. 黑名单检查
        if signal.token_mint in self.blacklist_tokens:
            return False, f"代币在黑名单中: {signal.token_symbol}"
        
        # 2. 流动性检查
        if self.min_liquidity > 0:
            if price_info.liquidity < self.min_liquidity:
                return False, f"流动性不足: ${price_info.liquidity:,.0f} < ${self.min_liquidity:,.0f}"
        
        # 3. 市值检查（最小值）
        if self.min_market_cap > 0:
            if price_info.market_cap < self.min_market_cap:
                return False, f"市值过低: ${price_info.market_cap:,.0f} < ${self.min_market_cap:,.0f}"
        
        # 4. 市值检查（最大值）
        if self.max_market_cap < float('inf'):
            if price_info.market_cap > self.max_market_cap:
                return False, f"市值过高: ${price_info.market_cap:,.0f} > ${self.max_market_cap:,.0f}"
        
        # 全部通过
        return True, "通过所有筛选"
    
    def _calculate_buy_amount(self, price_info: PriceInfo, 
                             current_balance: float) -> tuple:
        """
        计算买入数量
        
        参数:
            price_info: PriceInfo - 价格信息
            current_balance: float - 当前余额
        
        返回:
            tuple - (数量, 预估成本)
        """
        # 计算可用资金（按比例）
        available_funds = current_balance * self.trade_ratio
        
        # 检查最小交易金额
        if available_funds < self.min_trade_amount:
            logger.warning(
                f"⚠️ 可用资金 ${available_funds:.2f} "
                f"< 最小交易金额 ${self.min_trade_amount:.2f}"
            )
            return 0.0, 0.0
        
        # 计算数量
        amount = available_funds / price_info.price_usd
        
        return amount, available_funds
    
    def _generate_buy_reason(self, signal: TradeSignal, price_info: PriceInfo) -> str:
        """
        生成买入决策理由
        
        参数:
            signal: TradeSignal - 交易信号
            price_info: PriceInfo - 价格信息
        
        返回:
            str - 决策理由
        """
        reasons = []
        
        # 基础信息
        reasons.append(f"跟随聪明钱买入 {signal.token_symbol}")
        
        # 筛选状态
        if self.enable_filtering:
            reasons.append("通过所有筛选")
            
            # 流动性信息
            if price_info.liquidity > 0:
                reasons.append(f"流动性: ${price_info.liquidity:,.0f}")
            
            # 市值信息
            if price_info.market_cap > 0:
                reasons.append(f"市值: ${price_info.market_cap:,.0f}")
        else:
            reasons.append("完全跟单模式（未筛选）")
        
        # 价格信息
        reasons.append(f"价格: ${price_info.price_usd:.6f}")
        
        return ", ".join(reasons)
    
    def _generate_sell_reason(self, signal: TradeSignal, price_info: PriceInfo, 
                             position) -> str:
        """
        生成卖出决策理由
        
        参数:
            signal: TradeSignal - 交易信号
            price_info: PriceInfo - 价格信息
            position: Position - 持仓信息
        
        返回:
            str - 决策理由
        """
        reasons = []
        
        # 基础信息
        reasons.append(f"跟随聪明钱卖出 {signal.token_symbol}")
        
        # 持仓信息
        reasons.append(f"持仓: {position.amount:.4f}")
        
        # 盈亏信息
        if position.unrealized_pnl_percent != 0:
            reasons.append(f"浮动盈亏: {position.unrealized_pnl_percent:+.2f}%")
        
        # 价格变化
        if position.cost_basis > 0:
            price_change = ((price_info.price_usd - position.cost_basis) / position.cost_basis) * 100
            reasons.append(f"价格变化: {price_change:+.2f}%")
        
        return ", ".join(reasons)
    
    def _create_skip_decision(self, signal: TradeSignal, current_balance: float, 
                             reason: str) -> TradingDecision:
        """
        创建跳过决策
        
        参数:
            signal: TradeSignal - 交易信号
            current_balance: float - 当前余额
            reason: str - 跳过原因
        
        返回:
            TradingDecision - 跳过决策
        """
        logger.info(f"⏭️ 跳过交易: {signal.token_symbol} - {reason}")
        
        return TradingDecision(
            should_trade=False,
            action=TradeAction.SKIP,
            token_mint=signal.token_mint,
            token_symbol=signal.token_symbol,
            amount=0.0,
            estimated_cost=0.0,
            reason=reason,
            current_balance=current_balance
        )
    
    # ==================== 配置更新方法 ====================
    
    def update_config(self):
        """
        动态更新配置（热重载）
        
        用途：运行时修改config.py后，调用此方法使配置生效
        """
        self.enable_filtering = TradingConfig.ENABLE_FILTERING
        self.min_liquidity = TradingConfig.MIN_LIQUIDITY
        self.min_market_cap = TradingConfig.MIN_MARKET_CAP
        self.max_market_cap = TradingConfig.MAX_MARKET_CAP
        self.blacklist_tokens = TradingConfig.BLACKLIST_TOKENS
        self.trade_ratio = TradingConfig.TRADE_RATIO
        self.min_trade_amount = TradingConfig.MIN_TRADE_AMOUNT
        
        logger.info("✅ 策略配置已更新")
    
    def get_config_summary(self) -> dict:
        """
        获取当前配置摘要
        
        返回:
            dict - 配置摘要
        """
        return {
            "enable_filtering": self.enable_filtering,
            "min_liquidity": self.min_liquidity,
            "min_market_cap": self.min_market_cap,
            "max_market_cap": self.max_market_cap,
            "blacklist_tokens": self.blacklist_tokens,
            "trade_ratio": self.trade_ratio,
            "min_trade_amount": self.min_trade_amount
        }
