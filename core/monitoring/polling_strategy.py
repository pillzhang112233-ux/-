"""
轮询策略模块

职责：
- 管理轮询模式（空闲/爆发）
- 计算轮询间隔
- 提供状态信息

不包含：
- 业务逻辑
- 交易处理
- 资产管理
"""

from enum import Enum
from datetime import datetime, timedelta
from config import Config
import logging

logger = logging.getLogger(__name__)


class PollingMode(Enum):
    """轮询模式枚举"""
    IDLE = "空闲模式"
    BURST = "爆发模式"


class PollingStrategy:
    """
    轮询策略管理器
    
    职责：
    - 管理轮询模式切换（空闲 ↔ 爆发）
    - 计算当前应使用的轮询间隔
    - 提供状态信息用于显示
    
    使用场景：
    - 空闲时：使用较长间隔节省 API Credits
    - 发现交易：切换到密集轮询
    - 持续活跃：自动延长爆发模式
    - 恢复平静：自动回到空闲模式
    """
    
    def __init__(self):
        """初始化为空闲模式"""
        self.mode = PollingMode.IDLE
        self.burst_end_time = None
        logger.debug("轮询策略初始化：空闲模式")
        
    def on_transaction_detected(self):
        """
        通知策略：检测到新交易
        
        行为：
        - 如果在空闲模式：切换到爆发模式
        - 如果在爆发模式：延长爆发时间
        """
        if self.mode == PollingMode.IDLE:
            # 从空闲切换到爆发
            self.mode = PollingMode.BURST
            self.burst_end_time = datetime.now() + timedelta(
                seconds=Config.BURST_DURATION
            )
            logger.info(
                f"⚡ 进入爆发模式（间隔 {Config.BURST_INTERVAL}秒，"
                f"持续 {Config.BURST_DURATION}秒）"
            )
        else:
            # 已在爆发模式，延长时间
            old_end = self.burst_end_time
            self.burst_end_time = datetime.now() + timedelta(
                seconds=Config.BURST_DURATION
            )
            
            # 只在显著延长时打印日志（避免日志过多）
            extension = (self.burst_end_time - old_end).seconds
            if extension > 60:
                logger.info(f"⚡ 延长爆发模式（延长 {extension}秒）")
    
    def get_interval(self) -> int:
        """
        获取当前应使用的轮询间隔
        
        返回：
            int: 轮询间隔（秒）
        
        副作用：
            如果爆发模式超时，自动切换回空闲模式
        """
        if self.mode == PollingMode.BURST:
            # 检查是否应该结束爆发模式
            if datetime.now() >= self.burst_end_time:
                self._switch_to_idle()
                return Config.IDLE_INTERVAL
            
            return Config.BURST_INTERVAL
        
        return Config.IDLE_INTERVAL
    
    def get_status(self) -> str:
        """
        获取当前状态描述（用于显示）
        
        返回：
            str: 状态描述
            - 空闲模式：如 "空闲 30s"
            - 爆发模式：如 "爆发 5s (剩余 295s)"
        """
        if self.mode == PollingMode.BURST:
            remaining = max(0, (self.burst_end_time - datetime.now()).seconds)
            return f"爆发 {Config.BURST_INTERVAL}s (剩余 {remaining}s)"
        
        return f"空闲 {Config.IDLE_INTERVAL}s"
    
    def _switch_to_idle(self):
        """切换到空闲模式（内部方法）"""
        self.mode = PollingMode.IDLE
        self.burst_end_time = None
        logger.info(f"💤 回到空闲模式（间隔 {Config.IDLE_INTERVAL}秒）")
    
    def get_mode(self) -> PollingMode:
        """
        获取当前模式（用于调试）
        
        返回：
            PollingMode: 当前模式
        """
        return self.mode
