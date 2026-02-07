import logging
import time
from storage.transaction_logger import TransactionLogger
from storage.transaction_analyzer import TransactionAnalyzer

logger = logging.getLogger(__name__)

class TransactionProcessor:
    """
    交易处理器
    
    职责：
    1. 接收交易列表
    2. 分析交易（类型、延迟等）
    3. 保存交易记录到JSON
    4. 返回交易信息
    """
    def __init__(self, target_wallet):
        self.target_wallet = target_wallet
        # 初始化交易记录存储器
        self.transaction_logger = TransactionLogger(target_wallet)

    def get_last_stored_signature(self):
        """获取最后一条交易签名，供Engine初始化使用"""
        return self.transaction_logger.get_latest_signature()

    def process_batch(self, transactions, time_str):
        """
        处理一批交易
        
        参数:
            transactions: 交易列表 (建议按时间正序排列：旧 -> 新)
            time_str: 当前扫描时间字符串
        
        返回:
            tuple: (updates_needed: bool, processed_txs: list)
                - updates_needed: 是否需要更新资产
                - processed_txs: 处理后的交易信息列表
        """
        if not transactions:
            return False, []

        updates_needed = False
        processed_txs = []
        
        # 记录捕获时间（批次统一时间）
        captured_at = time.time()
        
        # 遍历每一笔交易
        for tx in transactions:
            try:
                # 1. 分析交易
                analyzed_tx = TransactionAnalyzer.analyze(tx, captured_at)
                
                # 2. 保存到JSON
                success = self.transaction_logger.save_transaction(analyzed_tx)
                
                if success:
                    # 3. 收集交易信息（用于返回）
                    processed_txs.append({
                        'time_str': time_str,
                        'description': analyzed_tx['description'],
                        'signature': analyzed_tx['signature'],
                        'analyzed_type': analyzed_tx['analyzed_type'],
                        'delay': analyzed_tx['delay']
                    })
                    
                    # 4. 标记需要更新资产
                    updates_needed = True

            except Exception as e:
                logger.error(f"处理交易出错: {e} | Sig: {tx.get('signature')}")
                continue

        return updates_needed, processed_txs
