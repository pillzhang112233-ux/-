"""
交易协调器

职责：
- 协调完整交易流程
- 管理各个模块的交互
- 统一错误处理
- 记录交易日志
"""

import logging
import time
from typing import Optional
from core.data_models import TradeSignal, TradingDecision, ExecutionResult, RiskAction, TradeAction
from core.trading.strategy import TradingStrategy
from core.trading.risk_controller import RiskController
from core.trading.executor import VirtualExecutor
from core.portfolio.position_manager import PositionManager
from core.market.price_oracle import PriceOracle
from storage.json_storage import JsonStorage

logger = logging.getLogger(__name__)


class TradingCoordinator:
    """
    交易协调器
    
    功能：
    - 接收交易信号
    - 协调策略、风控、执行
    - 统一错误处理
    - 记录完整流程
    """
    
    def __init__(self, storage: JsonStorage):
        """
        初始化协调器
        
        参数:
            storage: JsonStorage - 存储器
        """
        self.storage = storage
        
        # 初始化各个模块
        logger.info("🚀 初始化交易协调器...")
        
        # 价格查询器
        self.price_oracle = PriceOracle()
        logger.info("✅ 价格查询器已加载")
        
        # 持仓管理器
        self.position_manager = PositionManager(storage)
        logger.info("✅ 持仓管理器已加载")
        
        # 虚拟执行器
        self.executor = VirtualExecutor(self.position_manager, storage)
        logger.info("✅ 虚拟执行器已加载")
        
        # 策略决策器
        self.strategy = TradingStrategy(self.price_oracle, self.position_manager)
        logger.info("✅ 策略决策器已加载")
        
        # 风险控制器
        self.risk_controller = RiskController(self.position_manager, storage)
        logger.info("✅ 风险控制器已加载")
        
        # 统计数据
        self.total_signals = 0
        self.executed_trades = 0
        self.skipped_trades = 0
        self.failed_trades = 0
        
        logger.info("🎉 交易协调器初始化完成")
    
    def process_signal(self, signal: TradeSignal) -> dict:
        """
        处理交易信号（主流程）
        
        参数:
            signal: TradeSignal - 交易信号
        
        返回:
            dict - 处理结果
        """
        self.total_signals += 1
        
        logger.info("=" * 60)
        logger.info(f"📨 收到交易信号 #{self.total_signals}")
        logger.info(f"   动作: {signal.action}")
        logger.info(f"   代币: {signal.token_symbol}")
        logger.info(f"   数量: {signal.amount:.4f}")
        logger.info("=" * 60)
        
        try:
            # 步骤1：检查风控状态
            allowed, reason = self.risk_controller.check_trading_allowed()
            if not allowed:
                logger.warning(f"🚫 风控禁止交易: {reason}")
                self.skipped_trades += 1
                return self._create_result(
                    success=False,
                    stage="风控检查",
                    reason=reason,
                    signal=signal
                )
            
            # 步骤2：策略决策
            current_balance = self.executor.get_balance()
            decision = self.strategy.decide(signal, current_balance)
            
            logger.info(f"🎯 策略决策: {'执行' if decision.should_trade else '跳过'}")
            logger.info(f"   理由: {decision.reason}")
            
            if not decision.should_trade:
                self.skipped_trades += 1
                return self._create_result(
                    success=False,
                    stage="策略决策",
                    reason=decision.reason,
                    signal=signal,
                    decision=decision
                )
            
            # 步骤3：风控检查（持仓级别）
            if signal.action == "SELL":
                # 卖出时不需要检查持仓风控，因为是跟随聪明钱
                pass
            
            # 步骤4：执行交易
            price_info = self.price_oracle.get_price(signal.token_mint)
            if not price_info:
                logger.error(f"❌ 无法获取价格信息: {signal.token_symbol}")
                self.failed_trades += 1
                return self._create_result(
                    success=False,
                    stage="价格查询",
                    reason="无法获取价格信息",
                    signal=signal,
                    decision=decision
                )
            
            execution_result = self.executor.execute(decision, price_info)
            
            # 步骤5：记录交易结果（用于风控统计）
            if execution_result.success:
                # 只有卖出才能判断盈亏
                if execution_result.action == TradeAction.SELL and execution_result.realized_pnl is not None:
                    is_profit = execution_result.realized_pnl > 0
                    self.risk_controller.record_trade_result(is_profit)
                
                self.executed_trades += 1
                
                logger.info("=" * 60)
                logger.info(f"✅ 交易执行成功")
                logger.info(f"   代币: {execution_result.token_symbol}")
                logger.info(f"   动作: {execution_result.action.value}")
                logger.info(f"   价格: ${execution_result.executed_price:.6f}")
                logger.info(f"   数量: {execution_result.executed_amount:.4f}")
                logger.info(f"   余额: ${execution_result.balance_after:.2f}")
                if execution_result.realized_pnl is not None:
                    logger.info(f"   盈亏: ${execution_result.realized_pnl:+.2f}")
                logger.info("=" * 60)
                
                return self._create_result(
                    success=True,
                    stage="执行完成",
                    reason="交易成功",
                    signal=signal,
                    decision=decision,
                    execution=execution_result
                )
            else:
                self.failed_trades += 1
                logger.error(f"❌ 交易执行失败: {execution_result.error_message}")
                
                return self._create_result(
                    success=False,
                    stage="执行交易",
                    reason=execution_result.error_message or "执行失败",
                    signal=signal,
                    decision=decision,
                    execution=execution_result
                )
        
        except Exception as e:
            self.failed_trades += 1
            logger.error(f"💥 处理信号时出错: {e}", exc_info=True)
            
            return self._create_result(
                success=False,
                stage="异常",
                reason=f"系统错误: {str(e)}",
                signal=signal
            )
    
    def check_risk_actions(self) -> list:
        """
        检查是否有风控动作需要执行
        
        返回:
            list - 执行结果列表
        """
        # 获取所有需要执行的风控动作
        risk_actions = self.risk_controller.check_all_positions()
        
        if not risk_actions:
            return []
        
        results = []
        
        for action in risk_actions:
            logger.warning("=" * 60)
            logger.warning(f"⚠️ 风控动作触发")
            logger.warning(f"   类型: {action.action_type.value}")
            logger.warning(f"   代币: {action.symbol}")
            logger.warning(f"   原因: {action.reason}")
            logger.warning("=" * 60)
            
            try:
                # 创建卖出决策
                decision = TradingDecision(
                    should_trade=True,
                    action=TradeAction.SELL,
                    token_mint=action.mint,
                    token_symbol=action.symbol,
                    amount=action.suggested_amount,
                    estimated_cost=0.0,
                    reason=f"风控触发: {action.reason}",
                    current_balance=self.executor.get_balance(),
                    position_amount=action.suggested_amount
                )
                
                # 获取价格
                price_info = self.price_oracle.get_price(action.mint)
                if not price_info:
                    logger.error(f"❌ 无法获取价格: {action.symbol}")
                    results.append({
                        'success': False,
                        'action': action,
                        'reason': '无法获取价格'
                    })
                    continue
                
                # 执行卖出
                execution_result = self.executor.execute_sell(decision, price_info)
                
                if execution_result.success:
                    # 记录交易结果
                    if execution_result.realized_pnl is not None:
                        is_profit = execution_result.realized_pnl > 0
                        self.risk_controller.record_trade_result(is_profit)
                    
                    logger.info(f"✅ 风控卖出成功: {action.symbol}")
                    results.append({
                        'success': True,
                        'action': action,
                        'execution': execution_result
                    })
                else:
                    logger.error(f"❌ 风控卖出失败: {execution_result.error_message}")
                    results.append({
                        'success': False,
                        'action': action,
                        'reason': execution_result.error_message
                    })
            
            except Exception as e:
                logger.error(f"💥 执行风控动作时出错: {e}", exc_info=True)
                results.append({
                    'success': False,
                    'action': action,
                    'reason': f"系统错误: {str(e)}"
                })
        
        return results
    
    def update_position_prices(self):
        """更新所有持仓价格"""
        try:
            positions = self.position_manager.get_all_positions()
            if not positions:
                return
            
            # 批量查询价格
            mints = [pos.mint for pos in positions]
            prices = self.price_oracle.get_prices_batch(mints)
            
            # 更新价格
            price_map = {}
            for mint, price_info in zip(mints, prices):
                if price_info:
                    price_map[mint] = price_info.price_usd
            
            if price_map:
                self.position_manager.update_prices(price_map)
                logger.debug(f"📊 更新了 {len(price_map)} 个持仓的价格")
        
        except Exception as e:
            logger.error(f"❌ 更新持仓价格失败: {e}")
    
    def get_statistics(self) -> dict:
        """
        获取协调器统计信息
        
        返回:
            dict - 统计信息
        """
        return {
            "total_signals": self.total_signals,
            "executed_trades": self.executed_trades,
            "skipped_trades": self.skipped_trades,
            "failed_trades": self.failed_trades,
            "execution_rate": self.executed_trades / self.total_signals if self.total_signals > 0 else 0,
            "current_balance": self.executor.get_balance(),
            "total_value": self.executor.get_total_value(),
            "position_count": self.position_manager.get_position_count(),
            "risk_status": self.risk_controller.get_risk_summary()
        }
    
    def _create_result(self, success: bool, stage: str, reason: str, 
                      signal: TradeSignal, decision=None, execution=None) -> dict:
        """
        创建统一的处理结果
        
        参数:
            success: bool - 是否成功
            stage: str - 处理阶段
            reason: str - 原因
            signal: TradeSignal - 交易信号
            decision: TradingDecision - 决策（可选）
            execution: ExecutionResult - 执行结果（可选）
        
        返回:
            dict - 处理结果
        """
        result = {
            "success": success,
            "stage": stage,
            "reason": reason,
            "signal": {
                "action": signal.action,
                "token_mint": signal.token_mint,
                "token_symbol": signal.token_symbol,
                "amount": signal.amount,
                "timestamp": signal.timestamp
            },
            "timestamp": int(time.time())
        }
        
        if decision:
            result["decision"] = {
                "should_trade": decision.should_trade,
                "action": decision.action.value if hasattr(decision.action, 'value') else str(decision.action),
                "amount": decision.amount,
                "reason": decision.reason
            }
        
        if execution:
            result["execution"] = {
                "success": execution.success,
                "executed_price": execution.executed_price,
                "executed_amount": execution.executed_amount,
                "cost": execution.cost,
                "balance_after": execution.balance_after,
                "realized_pnl": execution.realized_pnl
            }
        
        return result
    
    def resume_trading(self, note: str = "手动恢复"):
        """
        恢复交易（风控暂停后）
        
        参数:
            note: str - 恢复备注
        """
        return self.risk_controller.resume_trading(note)
    
    def reset_session(self, reason: str = "手动重置"):
        """
        重置会话
        
        参数:
            reason: str - 重置原因
        """
        logger.info(f"🔄 重置会话: {reason}")
        self.executor.reset_session(reason)
        
        # 重新初始化统计
        self.total_signals = 0
        self.executed_trades = 0
        self.skipped_trades = 0
        self.failed_trades = 0
        
        logger.info("✅ 会话重置完成")


# 便捷导出
__all__ = ['TradingCoordinator']
