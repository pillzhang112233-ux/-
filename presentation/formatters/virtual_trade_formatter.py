"""
虚拟交易格式化器
将虚拟交易结果格式化为可读字符串
"""

class VirtualTradeFormatter:
    """虚拟交易格式化器"""
    
    def format_buy_result(self, buy_info):
        """
        格式化买入结果
        
        参数:
            buy_info: 买入信息字典，包含：
                - symbol: 代币符号
                - amount: 数量
                - sol_price: SOL价格
                - slippage: 滑点
                - slippage_cost: 滑点成本
                - cost: 总花费
        
        返回:
            str: 格式化后的字符串
        """
        lines = []
        lines.append(f"📈 [虚拟买入] {buy_info['symbol']}")
        lines.append(f"   ├─ 数量: {buy_info['amount']:,.2f}")
        lines.append(f"   ├─ SOL价: ${buy_info['sol_price']:.2f}")
        lines.append(f"   ├─ 滑点: {buy_info['slippage']*100:.3f}% (额外损耗 ${buy_info['slippage_cost']:.4f})")
        lines.append(f"   └─ 总花费: ${buy_info['cost']:.2f}")
        
        return "\n".join(lines)
    
    def format_sell_result(self, sell_info):
        """
        格式化卖出结果
        
        参数:
            sell_info: 卖出信息字典，包含：
                - symbol: 代币符号
                - amount: 数量
                - slippage: 滑点
                - revenue: 到手金额
                - profit: 净利润
                - balance: 余额
        
        返回:
            str: 格式化后的字符串
        """
        emoji = "🟢 止盈" if sell_info['profit'] > 0 else "🔴 止损"
        
        lines = []
        lines.append(f"{emoji} [虚拟卖出] {sell_info['symbol']}")
        lines.append(f"   ├─ 数量: {sell_info['amount']:,.2f}")
        lines.append(f"   ├─ 滑点: {sell_info['slippage']*100:.3f}%")
        lines.append(f"   ├─ 到手: ${sell_info['revenue']:.2f}")
        lines.append(f"   └─ 净利: ${sell_info['profit']:+.2f} (余额: ${sell_info['balance']:.2f})")
        
        return "\n".join(lines)
    
    def format_insufficient_balance(self, required, available):
        """
        格式化余额不足警告
        
        参数:
            required: 需要的金额
            available: 可用金额
        
        返回:
            str: 格式化后的字符串
        """
        return f"❌ [虚拟交易] 余额不足! 需 ${required:.2f}, 仅有 ${available:.2f}"
    
    def format_no_position(self, symbol):
        """
        格式化无持仓警告
        
        参数:
            symbol: 代币符号
        
        返回:
            str: 格式化后的字符串
        """
        return f"⚠️ [虚拟卖出] 无法卖出 {symbol}: 无持仓"
