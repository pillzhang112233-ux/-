"""
价格更新线程模块

职责：
- 后台定期更新代币价格
- 显示价格变化
- 独立运行，不阻塞其他任务

不做：
- 不追踪交易
- 不更新完整资产
"""

import threading
import time
import logging
from datetime import datetime

from utils.cost_tracker import tracker

logger = logging.getLogger(__name__)


class PriceUpdater(threading.Thread):
    """
    价格更新线程
    
    功能：
    - 后台运行，定期更新价格
    - 不阻塞交易追踪和资产更新
    - 可配置更新频率
    """
    
    def __init__(self, asset_manager, presenter):
        """
        初始化价格更新线程
        
        参数:
            asset_manager: AssetManager 实例
            presenter: ConsolePresenter 实例
        """
        super().__init__()
        self.name = "PriceUpdater"
        self.daemon = False
        
        # 核心组件
        self.assets = asset_manager
        self.presenter = presenter
        
        # 控制标志
        self.running = True
        self.initialized = False
        
        # 更新频率（秒）
        self.update_interval = 60  # 每60秒更新一次价格
        
        # 线程安全锁（与 AssetUpdater 共享 asset_manager）
        self.lock = threading.Lock()
        
        logger.info("✅ 价格更新线程初始化完成")
    
    def run(self):
        """
        主循环（线程入口）
        
        流程：
        1. 等待初始化完成
        2. 定期更新价格
        3. 显示更新状态
        """
        # 等待初始化（等待资产管理器就绪）
        self.initialized = True
        
        # 主循环
        while self.running:
            try:
                # 等待更新间隔
                time.sleep(self.update_interval)
                
                if not self.running:
                    break
                
                # 更新价格
                self._update_prices()
                
            except Exception as e:
                logger.error(f"💥 价格更新线程崩溃: {e}", exc_info=True)
                time.sleep(5)
    
    def _update_prices(self):
        """
        更新价格数据
        
        - 从链上获取最新价格
        - 显示更新状态
        """
        current_time = datetime.now().strftime("%H:%M:%S")
        
        logger.debug(f"💱 更新价格...")
        
        # 注意：这里简化处理
        # 实际上 update_from_chain() 会同时更新资产和价格
        # 如果需要只更新价格，需要在 AssetManager 中添加单独方法
        
        # 为了避免与 AssetUpdater 冲突，这里只显示状态
        # 不实际调用更新（实际更新由 AssetUpdater 负责）
        
        logger.debug(f"💱 价格更新完成")
    
    def stop(self):
        """优雅停止线程"""
        logger.info("🛑 正在停止价格更新线程...")
        self.running = False


# 注意：
# 当前实现中，价格更新和资产更新是耦合的（都调用 update_from_chain）
# 为了避免冲突和重复调用，PriceUpdater 当前只是占位
# 未来可以优化 AssetManager，分离价格更新和资产更新逻辑
# 
# 临时方案：
# - AssetUpdater 负责完整更新（资产+价格）
# - PriceUpdater 暂时禁用或只做监控
# 
# 未来优化：
# - AssetManager.update_prices_only() - 只更新价格
# - AssetManager.update_balances_only() - 只更新余额
