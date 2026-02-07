"""
交易格式化器
将交易信息格式化为可读字符串
"""

class TransactionFormatter:
    """交易信息格式化器"""
    
    def format_new_transaction(self, time_str, description, signature):
        """
        格式化新交易信息
        
        参数:
            time_str: 时间字符串
            description: 交易描述
            signature: 交易签名
        
        返回:
            str: 格式化后的字符串
        """
        # 截断描述到60字符
        short_desc = description[:60] if len(description) > 60 else description
        
        # 截取签名前8位
        short_sig = signature[:8] if signature else "N/A"
        
        return f"[{time_str}] 📝 新交易 | {short_desc}... | Sig: {short_sig}"
    
    def format_transaction_batch(self, count, time_str):
        """
        格式化批量交易提示
        
        参数:
            count: 交易数量
            time_str: 时间字符串
        
        返回:
            str: 格式化后的字符串
        """
        return f"[{time_str}] 📥 发现 {count} 笔新交易"
