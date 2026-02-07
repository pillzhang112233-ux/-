"""
资产更新线程模块

职责：
- 后台更新钱包资产（不阻塞交易追踪）
- 响应交易更新通知
- 定期刷新资产数据
- 显示资产状态

不做：
- 不追踪交易
- 不处理交易逻辑
"""

import threading
import time
import logging
from datetime import datetime
from queue import Queue, Empty

from config import Config

logger = logging.getLogger(__name__)


class AssetUpdater(threading.Thread):
    """
    资产更新线程
    
    功能：
    - 后台运行，不阻塞交易追踪
    - 接收交易通知后更新资产
    - 定期刷新（防止价格过期）
    - 线程安全的资产管理
    """
    
    def __init__(self, asset_manager, presenter, update_queue):
        """
        初始化资产更新线程
        
        参数:
            asset_manager: AssetManager 实例
            presenter: ConsolePresenter 实例
            update_queue: 接收更新通知的队列
        """
        super().__init__()
        self.name = "AssetUpdater"
        self.daemon = False
        
        # 核心组件
        self.assets = asset_manager
        self.presenter = presenter
        self.update_queue = update_queue
        
        # 控制标志
        self.running = True
        self.initialized = False
        
        # 更新控制
        self.last_update_time = 0
        self.update_interval = 30  # 最小更新间隔（秒）
        
        # 线程安全锁
        self.lock = threading.Lock()
        
        logger.info("✅ 资产更新线程初始化完成")
    
    def initialize(self):
        """
        初始化资产数据
        
        - 加载本地缓存
        - 从链上同步初始数据
        - 显示初始资产
        """
        logger.info("💰 加载资产数据...")
        
        with self.lock:
            self.assets.load_local()
        
        # 增加重试逻辑
        logger.info("🔄 正在初始化链上资产数据...")
        success = False
        
        for i in range(Config.ASSET_SYNC_MAX_RETRIES):
            with self.lock:
                if self.assets.update_from_chain():
                    success = True
                    logger.info("✅ 资产同步完成")
                    break
            
            logger.warning(
                f"⚠️ 第 {i+1}/{Config.ASSET_SYNC_MAX_RETRIES} 次资产同步失败，"
                f"{Config.ASSET_SYNC_RETRY_DELAY}秒后重试..."
            )
            time.sleep(Config.ASSET_SYNC_RETRY_DELAY)
        
        if success:
            with self.lock:
                summary = self.assets.get_summary_data()
            
            self.presenter.show_assets(summary['assets'], summary['total_value'])
            self.last_update_time = time.time()
        else:
            logger.error("❌ 经过多次尝试，无法获取链上资产数据。")
            logger.error("⚠️ 资产更新线程将继续运行，但初始数据不可用。")
        
        self.initialized = True
    
    def run(self):
        """
        主循环（线程入口）
        
        流程：
        1. 等待初始化完成
        2. 监听更新队列
        3. 处理更新请求
        4. 定期刷新
        """
        # 等待初始化
        while not self.initialized and self.running:
            time.sleep(0.1)
        
        if not self.running:
            return
        
        # 主循环
        while self.running:
            try:
                # 检查更新队列（非阻塞，超时1秒）
                try:
                    msg = self.update_queue.get(timeout=1.0)
                    
                    if msg['type'] == 'transaction_update':
                        logger.debug(f"📬 收到交易更新通知")
                        self._handle_transaction_update(msg)
                    
                except Empty:
                    # 队列为空，检查是否需要定期刷新
                    self._check_periodic_refresh()
                
            except Exception as e:
                logger.error(f"💥 资产更新线程崩溃: {e}", exc_info=True)
                time.sleep(5)
    
    def _handle_transaction_update(self, msg):
        """
        处理交易更新通知
        
        参数:
            msg: 更新消息
                - type: 消息类型
                - time: 交易时间
                - count: 交易数量
        """
        # 检查是否需要限流（避免频繁更新）
        current_time = time.time()
        time_since_last = current_time - self.last_update_time
        
        if time_since_last < self.update_interval:
            logger.debug(
                f"⏳ 距离上次更新仅 {time_since_last:.1f}秒，"
                f"跳过更新（最小间隔 {self.update_interval}秒）"
            )
            return
        
        # 更新资产
        logger.info(f"🔄 交易触发资产更新...")
        
        with self.lock:
            if self.assets.update_from_chain():
                summary = self.assets.get_summary_data()
                self.presenter.show_assets(summary['assets'], summary['total_value'])
                self.last_update_time = current_time
                logger.debug("✅ 资产更新完成")
            else:
                logger.warning("⚠️ 资产更新失败")
    
    def _check_periodic_refresh(self):
        """
        检查是否需要定期刷新
        
        - 每60秒刷新一次（防止价格过期）
        """
        current_time = time.time()
        time_since_last = current_time - self.last_update_time
        
        # 每60秒刷新一次
        if time_since_last >= 60:
            logger.debug("🔄 定期刷新资产数据...")
            
            with self.lock:
                if self.assets.update_from_chain():
                    summary = self.assets.get_summary_data()
                    # 定期刷新不显示资产表格，只更新数据
                    self.last_update_time = current_time
                    logger.debug("✅ 定期刷新完成")
    
    def get_total_value(self):
        """
        获取总资产价值（线程安全）
        
        返回:
            float: 总资产价值
        """
        with self.lock:
            return self.assets.get_total_value()
    
    def get_summary(self):
        """
        获取资产摘要（线程安全）
        
        返回:
            dict: 资产摘要数据
        """
        with self.lock:
            return self.assets.get_summary_data()
    
    def stop(self):
        """优雅停止线程"""
        logger.info("🛑 正在停止资产更新线程...")
        self.running = False
