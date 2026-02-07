"""
风险控制器

职责：
- 基础风控：连续亏损、总回撤
- 单持仓风控：止损止盈（可开关）
- 风控状态管理
- 预留策略扩展接口
"""

import logging
import time
from typing import List, Optional
from datetime import datetime, timedelta
from core.data_models import Position, RiskAction, RiskActionType
from core.portfolio.position_manager import PositionManager
from storage.json_storage import JsonStorage
from config import RiskConfig

logger = logging.getLogger(__name__)


class RiskController:
    """
    风险控制器
    
    功能：
    - 检查连续亏损次数
    - 检查总体回撤
    - 检查单持仓止损/止盈（可关闭）
    - 管理风控暂停期
    - 提供手动恢复接口
    """
    
    def __init__(self, position_manager: PositionManager, storage: JsonStorage):
        """
        初始化风控器
        
        参数:
            position_manager: PositionManager - 持仓管理器
            storage: JsonStorage - 存储器
        """
        self.position_manager = position_manager
        self.storage = storage
        
        # 加载风控配置
        self.max_consecutive_losses = RiskConfig.MAX_CONSECUTIVE_LOSSES
        self.stop_after_trigger_hours = RiskConfig.STOP_AFTER_TRIGGER_HOURS
        self.max_drawdown = RiskConfig.MAX_DRAWDOWN
        
        # 单持仓风控配置
        self.enable_stop_loss = RiskConfig.ENABLE_POSITION_STOP_LOSS
        self.enable_take_profit = RiskConfig.ENABLE_POSITION_TAKE_PROFIT
        self.stop_loss_percent = RiskConfig.STOP_LOSS_PERCENT
        self.take_profit_percent = RiskConfig.TAKE_PROFIT_PERCENT
        self.max_hold_time = RiskConfig.MAX_HOLD_TIME
        
        # 风控状态
        self.consecutive_losses = 0       # 当前连续亏损次数
        self.is_paused = False            # 是否暂停交易
        self.pause_until = None           # 暂停截止时间
        self.pause_reason = ""            # 暂停原因
        
        # 加载风控状态
        self._load_risk_state()
        
        logger.info("✅ 风险控制器初始化完成")
        logger.info(f"   连续亏损限制: {self.max_consecutive_losses}次")
        logger.info(f"   最大回撤: {self.max_drawdown*100:.0f}%")
        logger.info(f"   单持仓止损: {'启用' if self.enable_stop_loss else '禁用'}")
        logger.info(f"   单持仓止盈: {'启用' if self.enable_take_profit else '禁用'}")
        
        if self.is_paused:
            logger.warning(f"⚠️ 风控暂停中，截止时间: {self.pause_until}")
    
    def record_trade_result(self, is_profit: bool):
        """
        记录交易结果，更新连续亏损统计
        
        参数:
            is_profit: bool - 是否盈利
        """
        if is_profit:
            # 盈利，重置连续亏损
            if self.consecutive_losses > 0:
                logger.info(f"✅ 盈利交易，重置连续亏损计数（之前{self.consecutive_losses}次）")
            self.consecutive_losses = 0
        else:
            # 亏损，增加计数
            self.consecutive_losses += 1
            logger.warning(f"📉 亏损交易，连续亏损: {self.consecutive_losses}次")
            
            # 检查是否触发风控
            if self.consecutive_losses >= self.max_consecutive_losses:
                self._trigger_pause("连续亏损达到限制")
        
        # 保存状态
        self._save_risk_state()
    
    def check_trading_allowed(self) -> tuple:
        """
        检查是否允许交易
        
        返回:
            tuple - (allowed: bool, reason: str)
        """
        # 检查是否在暂停期
        if self.is_paused:
            # 检查暂停期是否结束
            if self.pause_until and datetime.now() >= self.pause_until:
                logger.info("⏰ 暂停期已结束，但需要手动恢复")
                return False, f"风控暂停中（{self.pause_reason}），需要手动恢复"
            else:
                remaining = self.pause_until - datetime.now() if self.pause_until else None
                if remaining:
                    hours = remaining.total_seconds() / 3600
                    return False, f"风控暂停中，剩余{hours:.1f}小时"
                else:
                    return False, f"风控暂停中（{self.pause_reason}），需要手动恢复"
        
        return True, ""
    
    def check_all_positions(self) -> List[RiskAction]:
        """
        检查所有持仓的风控（仅在启用时）
        
        返回:
            List[RiskAction] - 需要执行的风控动作列表
        """
        risk_actions = []
        
        # 如果单持仓风控未启用，直接返回
        if not self.enable_stop_loss and not self.enable_take_profit:
            return risk_actions
        
        # 获取所有持仓
        positions = self.position_manager.get_all_positions()
        
        if not positions:
            return risk_actions
        
        # 逐个检查
        for position in positions:
            # 1. 检查止损（如果启用）
            if self.enable_stop_loss:
                action = self._check_stop_loss(position)
                if action:
                    risk_actions.append(action)
                    continue
            
            # 2. 检查止盈（如果启用）
            if self.enable_take_profit:
                action = self._check_take_profit(position)
                if action:
                    risk_actions.append(action)
                    continue
            
            # 3. 检查时间止损（如果启用）
            if self.enable_stop_loss:  # 时间止损归入止损功能
                action = self._check_time_stop(position)
                if action:
                    risk_actions.append(action)
                    continue
        
        return risk_actions
    
    def _check_stop_loss(self, position: Position) -> Optional[RiskAction]:
        """检查止损"""
        pnl_percent = position.unrealized_pnl_percent
        
        if pnl_percent <= self.stop_loss_percent:
            logger.warning(
                f"🛑 触发止损: {position.symbol} "
                f"({pnl_percent*100:.2f}% <= {self.stop_loss_percent*100:.0f}%)"
            )
            
            return RiskAction(
                action_type=RiskActionType.STOP_LOSS,
                mint=position.mint,
                symbol=position.symbol,
                reason=f"亏损达到止损线 ({pnl_percent*100:.2f}%)",
                current_pnl_percent=pnl_percent,
                holding_duration=position.holding_duration,
                suggested_amount=position.amount
            )
        
        return None
    
    def _check_take_profit(self, position: Position) -> Optional[RiskAction]:
        """检查止盈"""
        pnl_percent = position.unrealized_pnl_percent
        
        if pnl_percent >= self.take_profit_percent:
            logger.info(
                f"🎯 触发止盈: {position.symbol} "
                f"({pnl_percent*100:.2f}% >= {self.take_profit_percent*100:.0f}%)"
            )
            
            return RiskAction(
                action_type=RiskActionType.TAKE_PROFIT,
                mint=position.mint,
                symbol=position.symbol,
                reason=f"盈利达到止盈线 ({pnl_percent*100:.2f}%)",
                current_pnl_percent=pnl_percent,
                holding_duration=position.holding_duration,
                suggested_amount=position.amount
            )
        
        return None
    
    def _check_time_stop(self, position: Position) -> Optional[RiskAction]:
        """检查时间止损"""
        holding_duration = position.holding_duration
        
        if holding_duration >= self.max_hold_time:
            logger.warning(
                f"⏰ 触发时间止损: {position.symbol} "
                f"(持仓 {holding_duration/3600:.1f}小时 >= {self.max_hold_time/3600:.1f}小时)"
            )
            
            return RiskAction(
                action_type=RiskActionType.TIME_STOP,
                mint=position.mint,
                symbol=position.symbol,
                reason=f"持仓时间过长 ({holding_duration/3600:.1f}小时)",
                current_pnl_percent=position.unrealized_pnl_percent,
                holding_duration=holding_duration,
                suggested_amount=position.amount
            )
        
        return None
    
    def check_max_drawdown(self, current_total_value: float, max_balance: float) -> bool:
        """
        检查最大回撤
        
        参数:
            current_total_value: float - 当前总资产
            max_balance: float - 历史最高余额
        
        返回:
            bool - 是否触发最大回撤限制
        """
        if max_balance <= 0:
            return False
        
        drawdown_percent = (current_total_value - max_balance) / max_balance
        
        if drawdown_percent <= self.max_drawdown:
            logger.error(
                f"🚨 触发最大回撤限制: "
                f"{drawdown_percent*100:.2f}% <= {self.max_drawdown*100:.0f}% "
                f"(峰值${max_balance:.2f} -> 当前${current_total_value:.2f})"
            )
            self._trigger_pause(f"最大回撤 ({drawdown_percent*100:.2f}%)")
            return True
        
        return False
    
    def _trigger_pause(self, reason: str):
        """
        触发风控暂停
        
        参数:
            reason: str - 暂停原因
        """
        self.is_paused = True
        self.pause_reason = reason
        self.pause_until = datetime.now() + timedelta(hours=self.stop_after_trigger_hours)
        
        # 保存状态
        self._save_risk_state()
        
        # 高亮日志
        logger.error("=" * 60)
        logger.error("🚨🚨🚨 风控触发！交易已暂停 🚨🚨🚨")
        logger.error(f"原因: {reason}")
        logger.error(f"暂停时长: {self.stop_after_trigger_hours}小时")
        logger.error(f"恢复时间: {self.pause_until.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error("需要手动调用 resume_trading() 恢复")
        logger.error("=" * 60)
        
        # 记录到会话元数据
        self.storage.record_operation(
            operation_type="risk_pause",
            amount=0.0,
            note=f"风控触发暂停: {reason}，截止{self.pause_until.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    def resume_trading(self, manual_note: str = "手动恢复"):
        """
        手动恢复交易
        
        参数:
            manual_note: str - 恢复备注
        """
        if not self.is_paused:
            logger.warning("⚠️ 交易未暂停，无需恢复")
            return False
        
        self.is_paused = False
        self.pause_until = None
        self.consecutive_losses = 0  # 恢复时重置连续亏损
        
        # 保存状态
        self._save_risk_state()
        
        logger.info("=" * 60)
        logger.info("✅ 交易已恢复")
        logger.info(f"恢复原因: {manual_note}")
        logger.info(f"之前暂停原因: {self.pause_reason}")
        logger.info("=" * 60)
        
        # 记录到会话元数据
        self.storage.record_operation(
            operation_type="risk_resume",
            amount=0.0,
            note=f"手动恢复交易: {manual_note}"
        )
        
        return True
    
    def _load_risk_state(self):
        """从会话元数据加载风控状态"""
        metadata = self.storage.load_session_metadata()
        if not metadata:
            return
        
        risk_state = metadata.get('risk_state', {})
        self.consecutive_losses = risk_state.get('consecutive_losses', 0)
        self.is_paused = risk_state.get('is_paused', False)
        
        pause_until_str = risk_state.get('pause_until')
        if pause_until_str:
            try:
                self.pause_until = datetime.fromisoformat(pause_until_str)
            except:
                self.pause_until = None
        
        self.pause_reason = risk_state.get('pause_reason', '')
    
    def _save_risk_state(self):
        """保存风控状态到会话元数据"""
        metadata = self.storage.load_session_metadata()
        if not metadata:
            return
        
        metadata['risk_state'] = {
            'consecutive_losses': self.consecutive_losses,
            'is_paused': self.is_paused,
            'pause_until': self.pause_until.isoformat() if self.pause_until else None,
            'pause_reason': self.pause_reason
        }
        
        self.storage.save_session_metadata(metadata)
    
    def get_risk_summary(self) -> dict:
        """获取风控摘要"""
        return {
            "consecutive_losses": self.consecutive_losses,
            "max_consecutive_losses": self.max_consecutive_losses,
            "is_paused": self.is_paused,
            "pause_until": self.pause_until.isoformat() if self.pause_until else None,
            "pause_reason": self.pause_reason,
            "max_drawdown": self.max_drawdown,
            "enable_stop_loss": self.enable_stop_loss,
            "enable_take_profit": self.enable_take_profit
        }
    
    def update_config(self):
        """动态更新配置（热重载）"""
        self.max_consecutive_losses = RiskConfig.MAX_CONSECUTIVE_LOSSES
        self.stop_after_trigger_hours = RiskConfig.STOP_AFTER_TRIGGER_HOURS
        self.max_drawdown = RiskConfig.MAX_DRAWDOWN
        self.enable_stop_loss = RiskConfig.ENABLE_POSITION_STOP_LOSS
        self.enable_take_profit = RiskConfig.ENABLE_POSITION_TAKE_PROFIT
        self.stop_loss_percent = RiskConfig.STOP_LOSS_PERCENT
        self.take_profit_percent = RiskConfig.TAKE_PROFIT_PERCENT
        self.max_hold_time = RiskConfig.MAX_HOLD_TIME
        
        logger.info("✅ 风控配置已更新")


# 便捷导出
__all__ = ['RiskController']
