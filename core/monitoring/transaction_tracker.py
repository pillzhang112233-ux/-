"""
交易追踪线程模块

职责：
- 持续轮询新交易（最高优先级）
- 处理和显示交易
- 通知其他模块更新
- 独立线程运行，不被阻塞

不做：
- 不更新资产
- 不更新价格
"""

import threading
import time
import logging
from datetime import datetime
from queue import Queue

from config import Config
from core.monitoring.poller import TransactionPoller
from core.orchestration.processor import TransactionProcessor
from core.monitoring.polling_strategy import PollingStrategy
from utils.cost_tracker import tracker

logger = logging.getLogger(__name__)


class TransactionTracker(threading.Thread):
    """
    交易追踪线程
    
    功能：
    - 使用智能轮询策略（空闲30秒，爆发5秒）
    - 独立线程运行，不阻塞其他任务
    - 发现交易后通知资产更新线程
    """
        
    def __init__(self, monitor, processor, presenter, update_queue, asset_updater):
        """
        初始化交易追踪线程
        
        参数:
            monitor: HeliusMonitor 实例
            processor: TransactionProcessor 实例
            presenter: ConsolePresenter 实例
            update_queue: 通知资产更新的队列
            asset_updater: AssetUpdater 实例
        """
        super().__init__()
        self.name = "TransactionTracker"
        self.daemon = False  # 非守护线程，需要优雅停止
        
        # 核心组件
        self.monitor = monitor
        self.processor = processor
        self.presenter = presenter
        self.poller = TransactionPoller(monitor)
        self.strategy = PollingStrategy()
        self.asset_updater = asset_updater  # 🆕 添加这行
        
        # 线程间通信
        self.update_queue = update_queue
        
        # 控制标志
        self.running = True
        self.initialized = False
        
        logger.info("✅ 交易追踪线程初始化完成")
        
    def initialize(self):
        """
        初始化交易锚点
        
        - 恢复上次的交易锚点
        - 或回溯最近的交易
        """
        logger.info("🔗 初始化交易锚点...")
        
        saved_sig = self.processor.get_last_stored_signature()
        
        if saved_sig:
            logger.info(f"🔗 恢复交易锚点: {saved_sig[:8]}...")
            self.poller.set_anchor(saved_sig)
        else:
            logger.info(f"🆕 无历史数据，开始回溯最近 {Config.INIT_BACKFILL_LIMIT} 笔交易...")
            recent_txs, _ = self.poller.poll(limit=Config.INIT_BACKFILL_LIMIT)
            
            if recent_txs:
                logger.info(f"📥 抓取到 {len(recent_txs)} 笔历史交易，正在处理...")
                ordered_txs = list(reversed(recent_txs))
                
                _, processed_txs = self.processor.process_batch(
                    ordered_txs, 
                    datetime.now().strftime("%H:%M:%S")
                )
                
                last_tx = ordered_txs[-1]
                self.poller.set_anchor(last_tx['signature'])
                logger.info("✅ 历史交易回溯完成")
            else:
                logger.info("📭 未发现近期交易")
        
        self.initialized = True
    
    def run(self):
        """
        主循环（线程入口）
        
        流程：
        1. 等待初始化完成
        2. 使用智能轮询策略获取间隔
        3. 轮询交易
        4. 处理和显示交易
        5. 通知资产更新
        """
        # 等待初始化
        while not self.initialized and self.running:
            time.sleep(0.1)
        
        if not self.running:
            return
        
        # 显示启动消息
        time_str = datetime.now().strftime('%H:%M:%S')
        self.presenter.show_main_loop_start(time_str)
        
        check_count = 0
        
        # 主循环
        while self.running:
            try:
                check_count += 1
                self._tick(check_count)
                
                # 使用智能轮询策略
                interval = self.strategy.get_interval()
                time.sleep(interval)
                
            except Exception as e:
                logger.error(f"💥 交易追踪线程崩溃: {e}", exc_info=True)
                time.sleep(5)  # 错误后等待5秒再继续
    
    def _tick(self, check_count):
        """
        单次轮询逻辑
        
        参数:
            check_count: 扫描次数
        """
        current_time = datetime.now().strftime("%H:%M:%S")
        tracker.add(1)
        
        # 1. 轮询交易
        new_txs, gap_detected = self.poller.poll(limit=Config.POLL_TRANSACTION_LIMIT)
        
        if gap_detected:
            logger.warning("⚠️ 警告: 交易量激增，检测到可能的断层！")
        
        # 2. 处理交易
        if new_txs:
            # 通知智能轮询器：进入爆发模式
            self.strategy.on_transaction_detected()
            
            # 处理交易
            ordered_txs = list(reversed(new_txs))
            updates_needed, processed_txs = self.processor.process_batch(
                ordered_txs, 
                current_time
            )
            
            # 显示每笔交易
            for tx_info in processed_txs:
                self.presenter.show_new_transaction(
                    tx_info['time_str'],
                    tx_info['description'],
                    tx_info['signature']
                )
            
            # 通知资产更新线程
            if updates_needed:
                self.update_queue.put({
                    'type': 'transaction_update',
                    'time': current_time,
                    'count': len(new_txs)
                })
                logger.debug(f"📬 通知资产更新线程（{len(new_txs)} 笔交易）")
        
        else:
            # 无新交易，显示空闲状态
            mode_status = self.strategy.get_status()
            total_value = self.asset_updater.get_total_value()  # 🆕 修改这行
            self.presenter.show_idle_status(
                time_str=current_time,
                count=check_count,
                total_value=total_value,  # 🆕 修改这行
                mode_status=mode_status
            )
    
    def stop(self):
        """优雅停止线程"""
        logger.info("🛑 正在停止交易追踪线程...")
        self.running = False
    
    def get_strategy(self):
        """获取轮询策略（供外部查询）"""
        return self.strategy
