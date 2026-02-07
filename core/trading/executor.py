"""
虚拟交易执行器

职责：
- 执行虚拟买入/卖出
- 模拟滑点
- 更新持仓和余额
- 记录完整交易日志
- 集成会话管理
"""

import time
import random
import logging
from typing import Optional
from core.data_models import ExecutionResult, TradingDecision, PriceInfo, TradeAction
from core.portfolio.position_manager import PositionManager
from storage.json_storage import JsonStorage
from config import SystemConfig, TradingConfig

logger = logging.getLogger(__name__)


class VirtualExecutor:
    """
    虚拟交易执行器
    
    功能：
    - 模拟真实交易执行
    - 计算滑点
    - 更新持仓管理器
    - 维护虚拟余额
    - 记录完整交易数据
    """
    
    def __init__(self, position_manager: PositionManager, storage: JsonStorage):
        """
        初始化执行器
        
        参数:
            position_manager: PositionManager - 持仓管理器
            storage: JsonStorage - 存储器
        """
        self.position_manager = position_manager
        self.storage = storage
        
        # 加载虚拟余额
        self.balance = self.storage.load_balance()
        
        # 如果是首次运行（新会话），初始化余额
        if self.balance == 0.0:
            self.balance = TradingConfig.INITIAL_BALANCE
            self.storage.save_balance(self.balance)
            logger.info(f"💰 初始化虚拟余额: ${self.balance:.2f}")
        else:
            logger.info(f"💰 加载虚拟余额: ${self.balance:.2f}")
        
        # 加载会话信息
        self.session_id = self.storage.get_current_session()
        logger.info(f"📋 当前会话: {self.session_id}")
        
        logger.info("✅ 虚拟执行器初始化完成")
    
    def execute(self, decision: TradingDecision, price_info: PriceInfo) -> ExecutionResult:
        """
        执行虚拟交易
        
        参数:
            decision: TradingDecision - 交易决策
            price_info: PriceInfo - 价格信息
        
        返回:
            ExecutionResult - 执行结果
        """
        if not decision.should_trade:
            return self._create_skip_result(decision, "决策不交易")
        
        # 根据动作类型执行
        if decision.action == TradeAction.BUY:
            return self.execute_buy(decision, price_info)
        elif decision.action == TradeAction.SELL:
            return self.execute_sell(decision, price_info)
        else:
            return self._create_error_result(decision, f"未知的交易动作: {decision.action}")
    
    def execute_buy(self, decision: TradingDecision, price_info: PriceInfo) -> ExecutionResult:
        """
        执行虚拟买入
        
        参数:
            decision: TradingDecision - 交易决策
            price_info: PriceInfo - 价格信息
        
        返回:
            ExecutionResult - 执行结果
        """
        # 计算滑点
        slippage_percent = self._calculate_slippage(price_info.liquidity)
        slippage_bps = int(slippage_percent * 10000)
        
        # 实际执行价格（买入时价格变高）
        executed_price = price_info.price_usd * (1 + slippage_percent)
        
        # 计算实际数量
        executed_amount = decision.amount
        
        # 计算实际成本
        actual_cost = executed_price * executed_amount
        
        # 检查余额是否足够
        if actual_cost > self.balance:
            logger.warning(
                f"⚠️ 余额不足: 需要 ${actual_cost:.2f}, 当前 ${self.balance:.2f}"
            )
            return self._create_error_result(
                decision, 
                f"余额不足（需要${actual_cost:.2f}，当前${self.balance:.2f}）"
            )
        
        # 记录执行前状态
        balance_before = self.balance
        position_before = self.position_manager.get_position(decision.token_mint)
        
        # 扣除余额
        self.balance -= actual_cost
        
        # 更新持仓
        self.position_manager.add_position(
            mint=decision.token_mint,
            symbol=decision.token_symbol,
            amount=executed_amount,
            cost=actual_cost
        )
        
        # 获取更新后的持仓
        position_after = self.position_manager.get_position(decision.token_mint)
        
        # 保存余额
        self.storage.save_balance(self.balance)
        
        # 生成交易ID
        trade_id = self._generate_trade_id()
        
        # 记录余额历史
        position_value = self.position_manager.calculate_total_value()
        self.storage.save_balance_history_entry(
            balance=self.balance,
            change=-actual_cost,
            reason="buy",
            position_value=position_value,
            related_trade_id=trade_id,
            note=f"买入 {decision.token_symbol}"
        )
        
        # 保存完整的交易记录
        self._save_detailed_trade(
            trade_id=trade_id,
            action="BUY",
            decision=decision,
            price_info=price_info,
            executed_price=executed_price,
            executed_amount=executed_amount,
            cost=actual_cost,
            slippage=slippage_percent,
            slippage_bps=slippage_bps,
            balance_before=balance_before,
            balance_after=self.balance,
            position_before=position_before,
            position_after=position_after
        )
        
        # 更新会话统计
        self._update_session_stats_after_buy()
        
        logger.info(
            f"✅ 买入成功: {executed_amount:.4f} {decision.token_symbol} "
            f"@ ${executed_price:.6f} (滑点 {slippage_percent*100:.2f}%), "
            f"花费 ${actual_cost:.2f}, 余额 ${self.balance:.2f}"
        )
        
        # 返回执行结果
        return ExecutionResult(
            success=True,
            action=TradeAction.BUY,
            token_mint=decision.token_mint,
            token_symbol=decision.token_symbol,
            executed_price=executed_price,
            executed_amount=executed_amount,
            cost=actual_cost,
            slippage=slippage_percent,
            balance_before=balance_before,
            balance_after=self.balance,
            timestamp=int(time.time())
        )
    
    def execute_sell(self, decision: TradingDecision, price_info: PriceInfo) -> ExecutionResult:
        """
        执行虚拟卖出
        
        参数:
            decision: TradingDecision - 交易决策
            price_info: PriceInfo - 价格信息
        
        返回:
            ExecutionResult - 执行结果
        """
        # 检查持仓
        position = self.position_manager.get_position(decision.token_mint)
        if not position:
            logger.warning(f"⚠️ 没有持仓: {decision.token_symbol}")
            return self._create_error_result(decision, "没有持仓")
        
        # 检查持仓数量
        if decision.amount > position.amount:
            logger.warning(
                f"⚠️ 持仓不足: 尝试卖出 {decision.amount:.4f}, "
                f"实际持有 {position.amount:.4f}"
            )
            return self._create_error_result(
                decision, 
                f"持仓不足（需要{decision.amount:.4f}，实际{position.amount:.4f}）"
            )
        
        # 计算滑点
        slippage_percent = self._calculate_slippage(price_info.liquidity)
        slippage_bps = int(slippage_percent * 10000)
        
        # 实际执行价格（卖出时价格变低）
        executed_price = price_info.price_usd * (1 - slippage_percent)
        
        # 实际数量
        executed_amount = decision.amount
        
        # 实际收入
        actual_income = executed_price * executed_amount
        
        # 记录执行前状态
        balance_before = self.balance
        position_before = self.position_manager.get_position(decision.token_mint)
        
        # 增加余额
        self.balance += actual_income
        
        # 减少持仓并计算利润
        realized_pnl = self.position_manager.reduce_position(
            mint=decision.token_mint,
            amount=executed_amount,
            exit_price=executed_price
        )
        
        # 获取更新后的持仓（可能为None）
        position_after = self.position_manager.get_position(decision.token_mint)
        
        # 计算盈亏百分比
        pnl_percent = (executed_price - position_before.cost_basis) / position_before.cost_basis if position_before.cost_basis > 0 else 0.0
        
        # 计算持仓时间
        holding_time = int(time.time()) - position_before.entry_time
        
        # 保存余额
        self.storage.save_balance(self.balance)
        
        # 生成交易ID
        trade_id = self._generate_trade_id()
        
        # 记录余额历史
        position_value = self.position_manager.calculate_total_value()
        self.storage.save_balance_history_entry(
            balance=self.balance,
            change=actual_income,
            reason="sell",
            position_value=position_value,
            related_trade_id=trade_id,
            note=f"卖出 {decision.token_symbol}，获利 ${realized_pnl:.2f}"
        )
        
        # 保存完整的交易记录
        self._save_detailed_trade(
            trade_id=trade_id,
            action="SELL",
            decision=decision,
            price_info=price_info,
            executed_price=executed_price,
            executed_amount=executed_amount,
            cost=-actual_income,  # 卖出时收入为负成本
            slippage=slippage_percent,
            slippage_bps=slippage_bps,
            balance_before=balance_before,
            balance_after=self.balance,
            position_before=position_before,
            position_after=position_after,
            realized_pnl=realized_pnl,
            pnl_percent=pnl_percent,
            holding_time=holding_time
        )
        
        # 更新会话统计
        self._update_session_stats_after_sell(realized_pnl)
        
        logger.info(
            f"✅ 卖出成功: {executed_amount:.4f} {decision.token_symbol} "
            f"@ ${executed_price:.6f} (滑点 {slippage_percent*100:.2f}%), "
            f"收入 ${actual_income:.2f}, 利润 ${realized_pnl:.2f} ({pnl_percent*100:+.2f}%), "
            f"余额 ${self.balance:.2f}"
        )
        
        # 返回执行结果
        return ExecutionResult(
            success=True,
            action=TradeAction.SELL,
            token_mint=decision.token_mint,
            token_symbol=decision.token_symbol,
            executed_price=executed_price,
            executed_amount=executed_amount,
            cost=-actual_income,
            slippage=slippage_percent,
            balance_before=balance_before,
            balance_after=self.balance,
            timestamp=int(time.time()),
            realized_pnl=realized_pnl
        )
    
    def deposit(self, amount: float, note: str = "虚拟入金"):
        """
        虚拟入金
        
        参数:
            amount: float - 入金金额
            note: str - 备注
        """
        if not TradingConfig.ALLOW_VIRTUAL_DEPOSIT:
            logger.warning("⚠️ 虚拟入金功能已禁用")
            return False
        
        if amount <= 0:
            logger.warning("⚠️ 入金金额必须大于0")
            return False
        
        balance_before = self.balance
        self.balance += amount
        self.storage.save_balance(self.balance)
        
        # 记录操作
        self.storage.record_operation(
            operation_type="deposit",
            amount=amount,
            note=note,
            balance_before=balance_before,
            balance_after=self.balance
        )
        
        # 记录余额历史
        position_value = self.position_manager.calculate_total_value()
        self.storage.save_balance_history_entry(
            balance=self.balance,
            change=amount,
            reason="deposit",
            position_value=position_value,
            note=note
        )
        
        logger.info(f"💰 虚拟入金: ${amount:.2f}, 余额 ${self.balance:.2f}")
        return True
    
    def withdraw(self, amount: float, note: str = "虚拟出金"):
        """
        虚拟出金
        
        参数:
            amount: float - 出金金额
            note: str - 备注
        """
        if not TradingConfig.ALLOW_VIRTUAL_WITHDRAWAL:
            logger.warning("⚠️ 虚拟出金功能已禁用")
            return False
        
        if amount <= 0:
            logger.warning("⚠️ 出金金额必须大于0")
            return False
        
        if amount > self.balance:
            logger.warning(f"⚠️ 余额不足: 需要 ${amount:.2f}, 当前 ${self.balance:.2f}")
            return False
        
        balance_before = self.balance
        self.balance -= amount
        self.storage.save_balance(self.balance)
        
        # 记录操作
        self.storage.record_operation(
            operation_type="withdraw",
            amount=amount,
            note=note,
            balance_before=balance_before,
            balance_after=self.balance
        )
        
        # 记录余额历史
        position_value = self.position_manager.calculate_total_value()
        self.storage.save_balance_history_entry(
            balance=self.balance,
            change=-amount,
            reason="withdraw",
            position_value=position_value,
            note=note
        )
        
        logger.info(f"💸 虚拟出金: ${amount:.2f}, 余额 ${self.balance:.2f}")
        return True
    
    def reset_session(self, reason: str = "手动重置"):
        """
        重置会话
        
        参数:
            reason: str - 重置原因
        """
        logger.info(f"🔄 重置会话: {reason}")
        
        # 调用storage的重置方法
        new_session_id = self.storage.reset_session(reason)
        
        # 重新初始化余额
        self.balance = TradingConfig.INITIAL_BALANCE
        self.storage.save_balance(self.balance)
        
        # 更新会话ID
        self.session_id = new_session_id
        
        logger.info(f"✅ 会话重置完成，新余额: ${self.balance:.2f}")
    
    def _calculate_slippage(self, liquidity: float) -> float:
        """
        计算滑点
        
        参数:
            liquidity: float - 流动性（USD）
        
        返回:
            float - 滑点百分比
        """
        min_bps = SystemConfig.SLIPPAGE_MIN_BPS
        max_bps = SystemConfig.SLIPPAGE_MAX_BPS
        
        slippage_bps = random.uniform(min_bps, max_bps)
        slippage_percent = slippage_bps / 10000
        
        return slippage_percent
    
    def _generate_trade_id(self) -> str:
        """
        生成交易ID
        
        返回:
            str - 交易ID (时间戳_序号)
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        # 从当前会话的交易记录中获取序号
        trades = self.storage.load_trades()
        sequence = len(trades) + 1
        return f"{timestamp}_{sequence:03d}"
    
    def _save_detailed_trade(self, trade_id, action, decision, price_info, 
                            executed_price, executed_amount, cost, slippage, slippage_bps,
                            balance_before, balance_after, position_before, position_after,
                            realized_pnl=None, pnl_percent=None, holding_time=None):
        """
        保存完整的交易记录
        
        按照任务2.3.1定义的完整格式保存
        """
        # 构造完整的交易记录
        trade_data = {
            "trade_id": trade_id,
            "session_id": self.session_id,
            
            "basic_info": {
                "action": action,
                "timestamp": int(time.time()),
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            
            "token": {
                "mint": decision.token_mint,
                "symbol": decision.token_symbol,
                "name": decision.token_symbol  # 暂时用symbol代替，未来可从其他地方获取
            },
            
            "market_data": {
                "price_usd": price_info.price_usd,
                "price_sol": price_info.price_sol,
                "liquidity": price_info.liquidity,
                "market_cap": price_info.market_cap,
                "price_source": price_info.source,
                "query_timestamp": price_info.timestamp
            },
            
            "filtering": {
                "enabled": TradingConfig.ENABLE_FILTERING,
                "passed": decision.should_trade,
                "checks": {
                    # 这里简化处理，实际应该从decision中获取详细筛选结果
                    # 未来在TradingStrategy中会提供完整信息
                }
            },
            
            "decision": {
                "should_trade": decision.should_trade,
                "reason": decision.reason,
                "estimated_cost": decision.estimated_cost,
                "signal_delay_ms": 0  # 暂时为0，未来可以计算实际延迟
            },
            
            "execution": {
                "amount": executed_amount,
                "price": executed_price,
                "cost": abs(cost),
                "slippage": slippage,
                "slippage_bps": slippage_bps
            },
            
            "balance": {
                "before": balance_before,
                "after": balance_after,
                "change": balance_after - balance_before
            },
            
            "position": {
                "before": {
                    "amount": position_before.amount if position_before else 0.0,
                    "avg_cost": position_before.cost_basis if position_before else 0.0
                },
                "after": {
                    "amount": position_after.amount if position_after else 0.0,
                    "avg_cost": position_after.cost_basis if position_after else 0.0,
                    "total_cost": position_after.total_cost if position_after else 0.0
                }
            },
            
            "performance": {
                "realized_pnl": realized_pnl,
                "pnl_percent": pnl_percent,
                "holding_time": holding_time,
                "entry_price": position_before.cost_basis if position_before else 0.0,
                "exit_price": executed_price if action == "SELL" else None
            }
        }
        
        # 保存交易记录
        self.storage.save_trade(trade_data)
    
    def _update_session_stats_after_buy(self):
        """买入后更新会话统计"""
        metadata = self.storage.load_session_metadata()
        if not metadata:
            return
        
        stats_update = {
            "total_trades": metadata['statistics']['total_trades'] + 1,
            "buy_trades": metadata['statistics']['buy_trades'] + 1,
            "current_balance": self.balance,
            "current_position_value": self.position_manager.calculate_total_value(),
            "current_total_value": self.balance + self.position_manager.calculate_total_value(),
            "current_positions": self.position_manager.get_position_count()
        }
        
        # 更新最大/最小余额
        if self.balance > metadata['statistics']['max_balance']:
            stats_update['max_balance'] = self.balance
        if self.balance < metadata['statistics']['min_balance']:
            stats_update['min_balance'] = self.balance
        
        self.storage.update_session_statistics(stats_update)
    
    def _update_session_stats_after_sell(self, realized_pnl):
        """卖出后更新会话统计"""
        metadata = self.storage.load_session_metadata()
        if not metadata:
            return
        
        # 判断盈亏
        is_winning = realized_pnl > 0
        
        stats = metadata['statistics']
        total_trades = stats['total_trades'] + 1
        winning_trades = stats['winning_trades'] + (1 if is_winning else 0)
        losing_trades = stats['losing_trades'] + (0 if is_winning else 1)
        
        stats_update = {
            "total_trades": total_trades,
            "sell_trades": stats['sell_trades'] + 1,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": winning_trades / total_trades if total_trades > 0 else 0.0,
            "total_pnl": stats['total_pnl'] + realized_pnl,
            "current_balance": self.balance,
            "current_position_value": self.position_manager.calculate_total_value(),
            "current_total_value": self.balance + self.position_manager.calculate_total_value(),
            "current_positions": self.position_manager.get_position_count()
        }
        
        # 更新总收益率
        initial_balance = metadata['initial_balance']
        stats_update['total_return'] = (stats_update['current_total_value'] - initial_balance) / initial_balance
        
        # 更新最大/最小余额
        if self.balance > stats['max_balance']:
            stats_update['max_balance'] = self.balance
        if self.balance < stats['min_balance']:
            stats_update['min_balance'] = self.balance
        
        self.storage.update_session_statistics(stats_update)
    
    def get_balance(self) -> float:
        """获取当前余额"""
        return self.balance
    
    def get_total_value(self) -> float:
        """获取总资产价值"""
        position_value = self.position_manager.calculate_total_value()
        return self.balance + position_value
    
    def _create_skip_result(self, decision: TradingDecision, reason: str) -> ExecutionResult:
        """创建跳过执行的结果"""
        return ExecutionResult(
            success=False,
            action=TradeAction.SKIP,
            token_mint=decision.token_mint,
            token_symbol=decision.token_symbol,
            executed_price=0.0,
            executed_amount=0.0,
            cost=0.0,
            slippage=0.0,
            balance_before=self.balance,
            balance_after=self.balance,
            timestamp=int(time.time()),
            error_message=reason
        )
    
    def _create_error_result(self, decision: TradingDecision, error_message: str) -> ExecutionResult:
        """创建错误结果"""
        logger.error(f"❌ 执行失败: {error_message}")
        
        return ExecutionResult(
            success=False,
            action=decision.action,
            token_mint=decision.token_mint,
            token_symbol=decision.token_symbol,
            executed_price=0.0,
            executed_amount=0.0,
            cost=0.0,
            slippage=0.0,
            balance_before=self.balance,
            balance_after=self.balance,
            timestamp=int(time.time()),
            error_message=error_message
        )
