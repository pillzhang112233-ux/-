"""
交易记录存储器

职责：
- 保存交易记录到JSON
- 追加模式写入
- 去重处理
"""

import os
import json


class TransactionLogger:
    """
    交易记录存储器
    
    将分析后的交易保存到JSON文件
    """
    
    def __init__(self, wallet_address):
        """
        初始化存储器
        
        参数:
            wallet_address: str - 钱包地址
        """
        self.wallet_address = wallet_address
        
        # 创建目录
        self.transactions_dir = os.path.join("database", "追踪地址交易记录")
        if not os.path.exists(self.transactions_dir):
            os.makedirs(self.transactions_dir)
        
        # 文件路径
        short_addr = f"{wallet_address[:6]}_{wallet_address[-4:]}"
        self.transactions_file = os.path.join(
            self.transactions_dir, 
            f"wallet_{short_addr}_transactions.json"
        )
        
        # 初始化文件
        self._initialize_file()
    
    def _initialize_file(self):
        """初始化JSON文件（如果不存在）"""
        if not os.path.exists(self.transactions_file):
            try:
                with open(self.transactions_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                print(f"✅ 创建交易记录文件: {self.transactions_file}")
            except Exception as e:
                print(f"❌ 初始化交易记录文件失败: {e}")
    
    def save_transaction(self, analyzed_tx):
        """
        保存交易记录
        
        参数:
            analyzed_tx: dict - 分析后的交易数据
        
        返回:
            bool - 是否保存成功
        """
        signature = analyzed_tx.get('signature')
        if not signature:
            print("⚠️ 交易缺少signature，跳过保存")
            return False
        
        try:
            # 读取现有数据
            transactions = self._load_transactions()
            
            # 去重检查
            if self._is_duplicate(transactions, signature):
                return False
            
            # 追加新交易（放在最前面，保持最新的在上）
            transactions.insert(0, analyzed_tx)
            
            # 保存
            with open(self.transactions_file, 'w', encoding='utf-8') as f:
                json.dump(transactions, f, ensure_ascii=False, indent=2)
            
            print(f"💾 [交易记录] 已保存: {signature[:8]}... ({analyzed_tx['analyzed_type']})")
            return True
        
        except Exception as e:
            print(f"❌ 保存交易记录失败: {e}")
            return False
    
    def _load_transactions(self):
        """加载现有交易记录"""
        if not os.path.exists(self.transactions_file):
            return []
        
        try:
            with open(self.transactions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 读取交易记录失败: {e}")
            return []
    
    def _is_duplicate(self, transactions, signature):
        """检查是否重复"""
        for tx in transactions:
            if tx.get('signature') == signature:
                return True
        return False
    
    def get_latest_signature(self):
        """获取最新的交易签名（用于初始化）"""
        transactions = self._load_transactions()
        if transactions:
            return transactions[0].get('signature')
        return None
    
    def get_transaction_count(self):
        """获取交易总数"""
        transactions = self._load_transactions()
        return len(transactions)


# 便捷导出
__all__ = ['TransactionLogger']
