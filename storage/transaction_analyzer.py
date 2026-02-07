"""
交易分析器

职责：
- 分析交易类型（买入/卖出/转账等）
- 计算捕获延迟
- 提取买卖方向
"""

import time


class TransactionAnalyzer:
    """
    交易分析器
    
    将链上原始交易分析成易懂的交易信息
    """
    
    @staticmethod
    def analyze(tx_data, captured_at=None):
        """
        分析交易
        
        参数:
            tx_data: dict - 原始交易数据
            captured_at: float - 捕获时间戳（可选）
        
        返回:
            dict - 增强的交易数据
        """
        if captured_at is None:
            captured_at = time.time()
        
        # 提取基础信息
        signature = tx_data.get('signature', 'N/A')
        timestamp = tx_data.get('timestamp', 0)
        raw_type = tx_data.get('type', 'UNKNOWN')
        description = tx_data.get('description', '')
        
        # 计算延迟
        delay = captured_at - timestamp if timestamp > 0 else 0
        
        # 分析交易类型
        analyzed_type = TransactionAnalyzer._analyze_type(raw_type, description)
        
        # 提取代币变化
        tokens_bought, tokens_sold = TransactionAnalyzer._extract_tokens(tx_data, description)
        
        # 计算SOL变化
        sol_change = TransactionAnalyzer._calculate_sol_change(tx_data)
        
        # 构造增强的交易数据
        analyzed_tx = {
            # 基础信息
            "signature": signature,
            "timestamp": timestamp,
            "captured_at": captured_at,
            "delay": round(delay, 2),
            
            # 类型信息
            "raw_type": raw_type,
            "analyzed_type": analyzed_type,
            "description": description,
            
            # 代币变化
            "sol_change": sol_change,
            "tokens": {
                "bought": tokens_bought,
                "sold": tokens_sold
            },
            
            # 原始数据（保留完整信息）
            "raw_data": tx_data
        }
        
        return analyzed_tx
    
    @staticmethod
    def _analyze_type(raw_type, description):
        """
        分析交易类型
        
        参数:
            raw_type: str - 链上原始类型
            description: str - 交易描述
        
        返回:
            str - 分析后的类型（买入/卖出/转账/铸造/未知）
        """
        raw_type = raw_type.upper()
        description_lower = description.lower()
        
        # SWAP类型
        if raw_type == 'SWAP' or 'swap' in description_lower:
            if 'bought' in description_lower or '买入' in description_lower:
                return '买入'
            elif 'sold' in description_lower or '卖出' in description_lower:
                return '卖出'
            else:
                return '交换'
        
        # 转账类型
        elif raw_type == 'TRANSFER' or 'transfer' in description_lower:
            if 'bought' in description_lower:
                return '买入'
            elif 'sold' in description_lower:
                return '卖出'
            else:
                return '转账'
        
        # NFT相关
        elif 'nft' in raw_type.lower() or 'nft' in description_lower:
            if 'mint' in description_lower:
                return 'NFT铸造'
            elif 'bought' in description_lower:
                return 'NFT买入'
            elif 'sold' in description_lower:
                return 'NFT卖出'
            else:
                return 'NFT交易'
        
        # 其他明确类型
        elif 'bought' in description_lower or '买入' in description_lower:
            return '买入'
        elif 'sold' in description_lower or '卖出' in description_lower:
            return '卖出'
        
        else:
            return '未知'
    
    @staticmethod
    def _extract_tokens(tx_data, description):
        """
        提取买入和卖出的代币
        
        参数:
            tx_data: dict - 交易数据
            description: str - 交易描述
        
        返回:
            tuple - (bought_tokens, sold_tokens)
        """
        bought = []
        sold = []
        
        # 从描述中提取（简化版，可以更复杂）
        description_lower = description.lower()
        
        if 'bought' in description_lower:
            # 尝试从描述提取代币符号
            # 例如: "Bought 100 USDC for 1 SOL"
            parts = description.split()
            for i, word in enumerate(parts):
                if word.lower() == 'bought' and i+2 < len(parts):
                    token = parts[i+2]  # "Bought 100 USDC"
                    bought.append(token)
        
        if 'sold' in description_lower or 'for' in description_lower:
            parts = description.split()
            for i, word in enumerate(parts):
                if word.lower() == 'for' and i+1 < len(parts):
                    token = parts[i+1]  # "for 1 SOL"
                    sold.append(token)
        
        # 从tokenTransfers提取（更准确）
        token_transfers = tx_data.get('tokenTransfers', [])
        for transfer in token_transfers:
            token_symbol = transfer.get('tokenSymbol', transfer.get('mint', 'Unknown'))
            # 这里需要根据实际API返回判断方向
            # 暂时简化处理
        
        return bought, sold
    
    @staticmethod
    def _calculate_sol_change(tx_data):
        """
        计算SOL变化
        
        参数:
            tx_data: dict - 交易数据
        
        返回:
            float - SOL变化量
        """
        native_transfers = tx_data.get('nativeTransfers', [])
        sol_change = sum(t.get('amount', 0) for t in native_transfers) / 1e9
        return round(sol_change, 6)


# 便捷导出
__all__ = ['TransactionAnalyzer']
