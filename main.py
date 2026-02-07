"""
虚拟跟单交易系统 - 主程序

功能：
- 监控聪明钱交易
- 虚拟执行跟单
- 风险控制
- 性能统计
"""

import logging
import time
import sys
from datetime import datetime

from config import BaseConfig, SystemConfig
from monitors.helius_monitor import HeliusMonitor
from core.orchestration.trading_coordinator import TradingCoordinator
from storage.json_storage import JsonStorage
from core.parsing.signal_parser import SignalParser

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # ← 改成 DEBUG 显示详细信息
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class VirtualTradingSystem:
    """
    虚拟跟单交易系统
    
    主程序：协调所有模块运行
    """
    
    def __init__(self):
        """初始化系统"""
        logger.info("=" * 60)
        logger.info("🚀 虚拟跟单交易系统启动中...")
        logger.info("=" * 60)
        
        # 检查配置
        self._check_config()
        
        # 初始化存储
        self.storage = JsonStorage(BaseConfig.TARGET_WALLET)
        logger.info(f"✅ 存储系统已加载")
        logger.info(f"   目标钱包: {BaseConfig.TARGET_WALLET[:8]}...{BaseConfig.TARGET_WALLET[-6:]}")

        # 初始化交易处理器（新增）
        from core.orchestration.processor import TransactionProcessor
        self.processor = TransactionProcessor(BaseConfig.TARGET_WALLET)
        logger.info(f"✅ 交易处理器已加载")
        
        # 初始化交易协调器
        self.coordinator = TradingCoordinator(self.storage)
        logger.info(f"✅ 交易协调器已加载")
        
        # 初始化信号解析器
        self.signal_parser = SignalParser(BaseConfig.TARGET_WALLET)
        logger.info(f"✅ 信号解析器已加载")
        
        # 初始化监控器
        self.monitor = HeliusMonitor(
            api_key=BaseConfig.HELIUS_API_KEY,
            target_wallet=BaseConfig.TARGET_WALLET  
        )
        logger.info(f"✅ Helius监控器已加载")
        # 初始化轮询器
        from core.monitoring.poller import TransactionPoller
        self.poller = TransactionPoller(self.monitor)
        logger.info(f"✅ 交易轮询器已加载")
                
        # 运行状态
        self.is_running = False
        self.start_time = None
        
        # 统计数据
        self.total_scans = 0
        self.total_transactions = 0
        
        logger.info("=" * 60)
        logger.info("🎉 系统初始化完成！")
        logger.info("=" * 60)
    
    def _check_config(self):
        """检查配置"""
        if not BaseConfig.HELIUS_API_KEY:
            logger.error("❌ 缺少 HELIUS_API_KEY，请在 .env 中配置")
            sys.exit(1)
        
        if not BaseConfig.TARGET_WALLET:
            logger.error("❌ 缺少 TARGET_WALLET，请在 .env 中配置")
            sys.exit(1)
        
        logger.info("✅ 配置检查通过")
    
    def start(self):
        """启动系统"""
        if self.is_running:
            logger.warning("⚠️ 系统已经在运行中")
            return
        
        self.is_running = True
        self.start_time = datetime.now()
        
        logger.info("=" * 60)
        logger.info("🎬 开始监控交易...")
        logger.info(f"   监控钱包: {BaseConfig.TARGET_WALLET[:8]}...{BaseConfig.TARGET_WALLET[-6:]}")
        logger.info(f"   扫描间隔: {SystemConfig.IDLE_INTERVAL}秒")
        logger.info(f"   初始余额: ${self.coordinator.executor.get_balance():.2f}")
        logger.info("=" * 60)
        
        try:
            while self.is_running:
                self._scan_and_process()
                time.sleep(SystemConfig.IDLE_INTERVAL)
        
        except KeyboardInterrupt:
            logger.info("\n⚠️ 收到中断信号，正在停止...")
            self.stop()
        
        except Exception as e:
            logger.error(f"💥 系统运行出错: {e}", exc_info=True)
            self.stop()
    
    def _scan_and_process(self):
        """扫描并处理交易"""
        self.total_scans += 1
        
        try:
            # 1. 检查风控状态
            allowed, reason = self.coordinator.risk_controller.check_trading_allowed()
            if not allowed:
                logger.warning(f"🚫 风控禁止交易: {reason}")
                return
            
            # 2. 扫描新交易
            logger.debug(f"🔍 扫描 #{self.total_scans}...")
            new_transactions, gap_detected = self.poller.poll(limit=20)
            
            # 检测断层
            if gap_detected:
                logger.error(f"🚨 检测到交易断层！可能有遗漏")
                logger.error(f"   建议：增大扫描频率或limit值")
            
            if not new_transactions:
                logger.debug("   无新交易")
                return
            
            self.total_transactions += len(new_transactions)
            logger.info(f"📨 发现 {len(new_transactions)} 笔新交易")
            
            # 反转顺序（从旧到新）
            transactions = list(reversed(new_transactions))
            
            # 2.5. 保存原始交易到追踪地址交易记录（新增）
            from datetime import datetime
            time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updates_needed, processed_txs = self.processor.process_batch(transactions, time_str)
            
            if processed_txs:
                logger.info(f"✅ 已保存 {len(processed_txs)} 笔原始交易到追踪地址交易记录")
            
            # 3. 解析交易信号
            for tx in transactions:
                try:
                    # 解析信号
                    signals = self.signal_parser.parse(tx)
                    
                    if not signals:
                        logger.debug(f"   跳过非交易型交易: {tx.get('signature', 'N/A')[:8]}...")
                        continue
                    
                    # 处理每个信号
                    for signal in signals:
                        logger.info(f"\n🔔 交易信号: {signal.action} {signal.token_symbol}")
                        
                        # 交易协调器处理
                        result = self.coordinator.process_signal(signal)
                        
                        # 记录结果
                        if result['success']:
                            logger.info(f"✅ 交易执行成功")
                        else:
                            logger.info(f"⏭️ 跳过: {result['reason']}")
                
                except Exception as e:
                    logger.error(f"❌ 处理交易失败: {e}")
                    continue
            
            # 4. 检查持仓风控
            self._check_position_risks()
            
            # 5. 更新持仓价格
            self.coordinator.update_position_prices()
        
        except Exception as e:
            logger.error(f"❌ 扫描处理失败: {e}", exc_info=True)
    
    def _check_position_risks(self):
        """检查持仓风控"""
        try:
            risk_results = self.coordinator.check_risk_actions()
            
            if risk_results:
                logger.warning(f"⚠️ 执行了 {len(risk_results)} 个风控动作")
                
                for result in risk_results:
                    if result['success']:
                        logger.info(f"✅ 风控卖出: {result['action'].symbol}")
                    else:
                        logger.error(f"❌ 风控卖出失败: {result['reason']}")
        
        except Exception as e:
            logger.error(f"❌ 风控检查失败: {e}")
    
    def stop(self):
        """停止系统"""
        if not self.is_running:
            logger.warning("⚠️ 系统未运行")
            return
        
        self.is_running = False
        
        logger.info("=" * 60)
        logger.info("🛑 系统正在停止...")
        
        # 显示运行统计
        if self.start_time:
            runtime = datetime.now() - self.start_time
            hours = runtime.total_seconds() / 3600
            
            logger.info(f"📊 运行统计:")
            logger.info(f"   运行时长: {hours:.2f}小时")
            logger.info(f"   总扫描次数: {self.total_scans}")
            logger.info(f"   发现交易: {self.total_transactions}笔")
        
        # 显示交易统计
        stats = self.coordinator.get_statistics()
        logger.info(f"\n💰 交易统计:")
        logger.info(f"   处理信号: {stats['total_signals']}")
        logger.info(f"   执行交易: {stats['executed_trades']}")
        logger.info(f"   跳过交易: {stats['skipped_trades']}")
        logger.info(f"   失败交易: {stats['failed_trades']}")
        logger.info(f"   执行率: {stats['execution_rate']*100:.1f}%")
        
        logger.info(f"\n📈 账户状态:")
        logger.info(f"   当前余额: ${stats['current_balance']:.2f}")
        logger.info(f"   持仓价值: ${stats['total_value'] - stats['current_balance']:.2f}")
        logger.info(f"   总资产: ${stats['total_value']:.2f}")
        logger.info(f"   持仓数: {stats['position_count']}")
        
        logger.info("=" * 60)
        logger.info("👋 系统已停止")
        logger.info("=" * 60)
    
    def show_status(self):
        """显示系统状态"""
        logger.info("=" * 60)
        logger.info("📊 系统状态")
        logger.info("=" * 60)
        
        # 运行状态
        status = "运行中 🟢" if self.is_running else "已停止 🔴"
        logger.info(f"运行状态: {status}")
        
        if self.start_time and self.is_running:
            runtime = datetime.now() - self.start_time
            logger.info(f"运行时长: {runtime}")
        
        # 交易统计
        stats = self.coordinator.get_statistics()
        logger.info(f"\n💰 交易统计:")
        logger.info(f"   处理信号: {stats['total_signals']}")
        logger.info(f"   执行交易: {stats['executed_trades']}")
        logger.info(f"   跳过交易: {stats['skipped_trades']}")
        logger.info(f"   执行率: {stats['execution_rate']*100:.1f}%")
        
        # 账户状态
        logger.info(f"\n📈 账户状态:")
        logger.info(f"   当前余额: ${stats['current_balance']:.2f}")
        logger.info(f"   总资产: ${stats['total_value']:.2f}")
        logger.info(f"   持仓数: {stats['position_count']}")
        
        # 风控状态
        risk = stats['risk_status']
        logger.info(f"\n🛡️ 风控状态:")
        logger.info(f"   连续亏损: {risk['consecutive_losses']}/{risk['max_consecutive_losses']}")
        logger.info(f"   是否暂停: {'是 ⚠️' if risk['is_paused'] else '否 ✅'}")
        
        if risk['is_paused']:
            logger.info(f"   暂停原因: {risk['pause_reason']}")
            logger.info(f"   暂停截止: {risk['pause_until']}")
        
        logger.info("=" * 60)
    
    def resume_trading(self, note: str = "手动恢复"):
        """恢复交易"""
        success = self.coordinator.resume_trading(note)
        
        if success:
            logger.info("✅ 交易已恢复")
        else:
            logger.warning("⚠️ 交易未暂停，无需恢复")
    
    def reset_session(self, reason: str = "手动重置"):
        """重置会话"""
        self.coordinator.reset_session(reason)
        logger.info("✅ 会话已重置")


def show_menu():
    """显示菜单"""
    print("\n" + "=" * 60)
    print("🎮 虚拟跟单交易系统")
    print("=" * 60)
    print("1. 启动监控")
    print("2. 查看状态")
    print("3. 恢复交易（风控暂停后）")
    print("4. 重置会话")
    print("5. 退出")
    print("=" * 60)


def main():
    """主函数"""
    # 初始化系统
    system = VirtualTradingSystem()
    
    # 交互式菜单
    while True:
        show_menu()
        choice = input("请选择操作 (1-5): ").strip()
        
        if choice == "1":
            print("\n🎬 启动监控（按 Ctrl+C 停止）...\n")
            system.start()
        
        elif choice == "2":
            system.show_status()
        
        elif choice == "3":
            note = input("恢复原因: ").strip() or "手动恢复"
            system.resume_trading(note)
        
        elif choice == "4":
            confirm = input("确认重置会话？所有数据将归档 (y/N): ").strip().lower()
            if confirm == 'y':
                reason = input("重置原因: ").strip() or "手动重置"
                system.reset_session(reason)
            else:
                print("❌ 已取消")
        
        elif choice == "5":
            print("\n👋 退出系统")
            if system.is_running:
                system.stop()
            break
        
        else:
            print("❌ 无效选择，请重新输入")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 程序被中断")
    except Exception as e:
        logger.error(f"💥 程序出错: {e}", exc_info=True)
