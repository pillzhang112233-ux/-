"""
交易轮询器

职责：
- 从Monitor获取交易
- 管理锚点（last_known_sig）
- 筛选新交易
- 检测断层
"""

import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class TransactionPoller:
    """
    交易轮询器
    
    职责：负责从Monitor获取交易，并根据上次的锚点（Signature）筛选出真正的新交易。
    """
    
    def __init__(self, monitor):
        """
        初始化轮询器
        
        参数:
            monitor: HeliusMonitor - 监控器实例
        """
        self.monitor = monitor
        self.last_known_sig = None  # 上一次处理过的最新交易签名（锚点）
        
        logger.info("✅ 交易轮询器初始化完成")
    
    def set_anchor(self, signature: str):
        """
        手动设置锚点（通常在初始化时从存储读取）
        
        参数:
            signature: str - 交易签名
        """
        self.last_known_sig = signature
        logger.info(f"📍 设置锚点: {signature[:8]}...")
    
    def poll(self, limit: int = 20) -> Tuple[List[Dict], bool]:
        """
        轮询新交易
        
        参数:
            limit: int - 每次抓取的数量（建议20-50以防止漏单）
        
        返回:
            tuple: (new_transactions_list, is_gap_detected)
                - new_transactions_list: 新交易列表 [最新, 次新, ...]
                - is_gap_detected: 是否检测到断层
                
        注意：返回的列表是 [最新, 次新, ...]
              Engine处理时通常需要 reversed() 反转
        """
        # 1. 从API获取最近的交易
        recent_txs = self.monitor.get_recent_transactions(limit=limit)
        
        if not recent_txs:
            return [], False
        
        new_txs = []
        gap_detected = False
        
        # 2. 如果没有锚点（第一次运行且无历史记录），只取最新的一笔作为锚点
        if not self.last_known_sig:
            # 将最新的一笔设为锚点，但不作为"新交易"处理（避免重复处理历史）
            latest_tx = recent_txs[0]
            self.last_known_sig = latest_tx['signature']
            logger.info(f"🔖 首次运行，建立锚点: {self.last_known_sig[:8]}...")
            logger.info(f"   不处理历史交易，等待新交易产生")
            # 返回空列表，因为我们只是建立了锚点，还没产生"新"交易
            return [], False
        
        # 3. 有锚点，开始比对
        found_anchor = False
        for tx in recent_txs:
            if tx['signature'] == self.last_known_sig:
                found_anchor = True
                break
            new_txs.append(tx)
        
        # 4. 安全检查：如果抓满了limit数量还没找到锚点，说明中间有断层（漏单风险）
        if not found_anchor and len(new_txs) == limit:
            gap_detected = True
            logger.warning(f"⚠️ 检测到交易断层！抓取{limit}笔仍未找到锚点")
            logger.warning(f"   可能有遗漏的交易，建议增大limit或减少扫描间隔")
            # 在这种情况下，我们只能把这limit笔都当做新交易
            # 并且更新锚点为这批里最新的那个
            if new_txs:
                self.last_known_sig = new_txs[0]['signature']
                logger.info(f"   更新锚点: {self.last_known_sig[:8]}...")
        elif new_txs:
            # 正常找到了锚点，更新锚点为最新的那笔
            self.last_known_sig = new_txs[0]['signature']
            logger.debug(f"✅ 发现 {len(new_txs)} 笔新交易，更新锚点")
        
        return new_txs, gap_detected
    
    def get_anchor(self) -> Optional[str]:
        """
        获取当前锚点
        
        返回:
            str - 当前锚点签名
        """
        return self.last_known_sig


# 便捷导出
__all__ = ['TransactionPoller']
