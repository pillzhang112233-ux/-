"""
============================================================
⚠️ 此文件已废弃 - DEPRECATED ⚠️
============================================================

最后使用时间: 2026-01-30
废弃原因: 新的虚拟跟单系统已上线，功能更完善

替代方案:
  - 策略决策: core/trading_strategy.py
  - 虚拟执行: core/virtual_executor.py
  - 持仓管理: core/position_manager.py

保留目的:
  - 参考 Phase 1 回测系统的实现逻辑
  - 如果新系统出现问题，可参考旧代码

❌ 请勿在新代码中引用此文件
============================================================
"""
import json
import os
import random
from datetime import datetime
from config import Config  # 引入配置
from utils.logger import logger

class VirtualTrader:
    def __init__(self):
        self.file_path = os.path.join("database", "paper_trading.json")
        self.balance = 1000.0  # 初始虚拟资金 (USD)
        self.positions = {}    
        self.trade_history = []
        self._load_data()

    def on_signal(self, signal, sol_price_usd):
        """接收信号并执行虚拟交易"""
        if signal.type == "BUY":
            self._execute_buy(signal, sol_price_usd)
        elif signal.type == "SELL":
            self._execute_sell(signal, sol_price_usd)
        
        self._save_data()

    def _get_random_slippage(self):
        """生成随机滑点"""
        # 1. 从配置里取整数，比如 10 到 100 之间的一个数 (例如随机到了 50)
        bps_int = random.uniform(Config.SLIPPAGE_MIN_BPS, Config.SLIPPAGE_MAX_BPS)
        
        # 2. 【关键定义在这里】将整数转换为百分比小数
        # 50 / 10000 = 0.005 (即 0.5%)
        slippage_decimal = bps_int / 10000.0 
        
        return slippage_decimal

    def _execute_buy(self, signal, sol_price):
        # 1. 理论成本
        base_cost_usd = signal.sol_amount * sol_price
        
        # 2. 获取滑点 (比如 0.005)
        slippage = self._get_random_slippage()
        
        # 3. 计算实际成本 (成本变高了)
        # 实际花费 = 理论花费 * (1 + 0.005)
        actual_cost_usd = base_cost_usd * (1 + slippage)
        slippage_cost = actual_cost_usd - base_cost_usd

        if actual_cost_usd > self.balance:
            logger.warning(f"❌ [虚拟交易] 余额不足! 需 ${actual_cost_usd:.2f}, 仅有 ${self.balance:.2f}")
            return

        self.balance -= actual_cost_usd
        
        # 更新持仓数据
        mint = signal.token_mint
        if mint not in self.positions:
            self.positions[mint] = {'symbol': signal.token_symbol, 'amount': 0.0, 'cost_basis': 0.0}
        
        current_amt = self.positions[mint]['amount']
        current_cost = self.positions[mint]['cost_basis']
        
        new_amt = current_amt + signal.token_amount
        total_spent = (current_amt * current_cost) + actual_cost_usd
        new_avg_price = total_spent / new_amt if new_amt > 0 else 0

        self.positions[mint]['amount'] = new_amt
        self.positions[mint]['cost_basis'] = new_avg_price

        print(f"📈 [虚拟买入] {signal.token_symbol}")
        print(f"   ├─ 数量: {signal.token_amount:,.2f}")
        print(f"   ├─ SOL价: ${sol_price:.2f}")
        print(f"   ├─ 滑点: {slippage*100:.3f}% (额外损耗 ${slippage_cost:.4f})")
        print(f"   └─ 总花费: ${actual_cost_usd:.2f}")
        
        self._log_trade("BUY", signal, actual_cost_usd, 0, slippage)

    def _execute_sell(self, signal, sol_price):
        mint = signal.token_mint
        if mint not in self.positions or self.positions[mint]['amount'] <= 0:
            print(f"⚠️ [虚拟卖出] 无法卖出 {signal.token_symbol}: 无持仓")
            return

        holding = self.positions[mint]
        sell_amt = min(signal.token_amount, holding['amount'])
        
        # 1. 理论收入
        base_revenue_usd = signal.sol_amount * sol_price
        
        # 2. 获取滑点
        slippage = self._get_random_slippage()
        
        # 3. 计算实际收入 (到手变少了)
        # 实际收入 = 理论收入 * (1 - 0.005)
        actual_revenue_usd = base_revenue_usd * (1 - slippage)
        
        cost_of_sold_tokens = sell_amt * holding['cost_basis']
        profit_usd = actual_revenue_usd - cost_of_sold_tokens
        
        self.balance += actual_revenue_usd
        holding['amount'] -= sell_amt
        
        if holding['amount'] <= 0:
            del self.positions[mint]

        emoji = "🟢 止盈" if profit_usd > 0 else "🔴 止损"
        print(f"{emoji} [虚拟卖出] {signal.token_symbol}")
        print(f"   ├─ 数量: {sell_amt:,.2f}")
        print(f"   ├─ 滑点: {slippage*100:.3f}%")
        print(f"   ├─ 到手: ${actual_revenue_usd:.2f}")
        print(f"   └─ 净利: ${profit_usd:+.2f} (余额: ${self.balance:.2f})")
        
        self._log_trade("SELL", signal, actual_revenue_usd, profit_usd, slippage)

    def _log_trade(self, type, signal, value_usd, pnl, slippage):
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": type,
            "symbol": signal.token_symbol,
            "amount": signal.token_amount,
            "price_usd": value_usd,
            "slippage_bps": int(slippage * 10000), # 存数据时，我们再把它乘回整数，方便阅读
            "pnl": pnl,
            "balance_after": self.balance
        }
        self.trade_history.append(record)

    def _load_data(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    data = json.load(f)
                    self.balance = data.get('balance', 1000.0)
                    self.positions = data.get('positions', {})
                    self.trade_history = data.get('history', [])
            except:
                print("⚠️ 读取虚拟账本失败，重置数据")

    def _save_data(self):
        data = {
            "balance": self.balance,
            "positions": self.positions,
            "history": self.trade_history
        }
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=2)
