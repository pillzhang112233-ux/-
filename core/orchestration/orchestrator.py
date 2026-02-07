"""
协调器模块

职责：
- 初始化所有组件
- 启动和管理所有线程
- 协调线程间通信
- 优雅停止所有线程
- 处理系统信号

不做：
- 不执行具体业务逻辑
- 不直接处理数据
"""

import signal
import sys
import logging
from queue import Queue

from config import Config
from monitors.helius_monitor import HeliusMonitor

from core.assets.asset_manager import AssetManager
from core.orchestration.processor import TransactionProcessor
# from core.trading.deprecated.virtual_trader_deprecated import VirtualTrader  # ← 已废弃
from core.assets.asset_updater import AssetUpdater
from core.assets.price_updater import PriceUpdater
from core.monitoring.transaction_tracker import TransactionTracker
from presentation import ConsolePresenter

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    系统协调器
    
    功能：
    - 初始化所有组件和线程
    - 管理线程生命周期
    - 协调线程间通信
    - 优雅停止系统
    """
    
    def __init__(self):
        """初始化协调器"""
        logger.info("🚀 初始化系统协调器...")
        
        # 1. 初始化共享组件
        self.monitor = HeliusMonitor(Config.HELIUS_API_KEY, Config.TARGET_WALLET)
        self.assets = AssetManager(self.monitor)
        self.processor = TransactionProcessor(Config.TARGET_WALLET)
        self.presenter = ConsolePresenter()
        
        # 2. 线程间通信队列
        self.update_queue = Queue()  # 交易追踪 → 资产更新
        
        # 3. 初始化线程（✅ 修复：先创建 asset_updater，再创建 tracker）
        self.asset_updater = AssetUpdater(
            asset_manager=self.assets,
            presenter=self.presenter,
            update_queue=self.update_queue
        )
        
        self.tracker = TransactionTracker(
            monitor=self.monitor,
            processor=self.processor,
            presenter=self.presenter,
            update_queue=self.update_queue,
            asset_updater=self.asset_updater  # ✅ 现在 asset_updater 已经存在了
        )
        
        self.price_updater = PriceUpdater(
            asset_manager=self.assets,
            presenter=self.presenter
        )
        
        # 4. 信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("✅ 系统协调器初始化完成")
    
    def _signal_handler(self, sig, frame):
        """
        信号处理器
        
        参数:
            sig: 信号类型
            frame: 栈帧
        """
        logger.info("\n🛑 收到停止信号，正在优雅停止...")
        self.stop()
        sys.exit(0)
    
    def initialize(self):
        """
        初始化流程
        
        - 显示启动信息
        - 初始化资产数据
        - 初始化交易锚点
        """
        # 显示启动信息
        self.presenter.show_header(
            "Smart Money Tracker v5.0 (异步架构)",
            Config.TARGET_WALLET
        )
        
        # 初始化资产数据（在资产更新线程中）
        logger.info("📊 初始化资产数据...")
        self.asset_updater.initialize()
        
        # 初始化交易锚点（在交易追踪线程中）
        logger.info("🔗 初始化交易锚点...")
        self.tracker.initialize()
        
        logger.info("✅ 系统初始化完成")
    
    def start(self):
        """
        启动所有线程
        
        顺序：
        1. 资产更新线程（后台）
        2. 价格更新线程（后台，暂时禁用）
        3. 交易追踪线程（主要任务）
        """
        logger.info("🚀 启动所有线程...")
        
        # 1. 启动资产更新线程
        self.asset_updater.start()
        logger.info("✅ 资产更新线程已启动")
        
        # 2. 启动价格更新线程（暂时禁用，避免与资产更新冲突）
        # self.price_updater.start()
        # logger.info("✅ 价格更新线程已启动")
        
        # 3. 启动交易追踪线程
        self.tracker.start()
        logger.info("✅ 交易追踪线程已启动")
        
        logger.info("🎉 所有线程启动完成！")
    
    def wait(self):
        """
        等待所有线程结束
        
        主线程阻塞在这里，直到所有工作线程结束
        """
        try:
            # 等待交易追踪线程
            self.tracker.join()
            
            # 等待资产更新线程
            self.asset_updater.join()
            
            # 等待价格更新线程（如果启动了）
            # self.price_updater.join()
            
        except KeyboardInterrupt:
            logger.info("\n🛑 收到中断信号...")
            self.stop()
    
    def stop(self):
        """
        优雅停止所有线程
        
        顺序：
        1. 停止交易追踪（停止新任务）
        2. 停止资产更新
        3. 停止价格更新
        4. 等待所有线程结束
        """
        logger.info("🛑 正在停止所有线程...")
        
        # 1. 停止交易追踪线程
        self.tracker.stop()
        
        # 2. 停止资产更新线程
        self.asset_updater.stop()
        
        # 3. 停止价格更新线程（如果启动了）
        # self.price_updater.stop()
        
        # 4. 等待线程结束（最多等待5秒）
        self.tracker.join(timeout=5)
        self.asset_updater.join(timeout=5)
        # self.price_updater.join(timeout=5)
        
        logger.info("✅ 所有线程已停止")
    
    def run(self):
        """
        完整运行流程
        
        - 初始化
        - 启动线程
        - 等待结束
        """
        try:
            # 初始化
            self.initialize()
            
            # 启动线程
            self.start()
            
            # 等待结束
            self.wait()
            
        except Exception as e:
            logger.error(f"💥 系统崩溃: {e}", exc_info=True)
            self.stop()
            raise


# 便捷导出
__all__ = ['Orchestrator']
