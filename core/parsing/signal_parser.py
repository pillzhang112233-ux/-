"""
信号解析器

职责：
- 解析Helius交易数据
- 提取买入/卖出信号
- 生成TradeSignal对象

使用旧版识别逻辑（基于SOL和Token余额变动）
"""

import logging
import time
from typing import List, Optional
from core.data_models import TradeSignal

logger = logging.getLogger(__name__)


class SignalParser:
    """
    信号解析器
    
    将Helius交易数据解析为交易信号
    使用余额变动判断买入/卖出
    """
    
    def __init__(self, target_wallet: str):
        """
        初始化解析器
        
        参数:
            target_wallet: str - 目标钱包地址
        """
        self.target_wallet = target_wallet
        self.wsol_mint = "So11111111111111111111111111111111111111112"
        
        logger.debug(f"✅ 信号解析器初始化完成，目标钱包: {target_wallet[:8]}...")
    
    def parse(self, tx_data: dict) -> List[TradeSignal]:
        """
        解析交易数据，返回 TradeSignal 列表
        
        参数:
            tx_data: dict - Helius交易数据
        
        返回:
            List[TradeSignal] - 交易信号列表（可能为空）
        """
        try:
            # 1. 初步过滤：只处理SWAP交易
            if not self._is_swap_transaction(tx_data):
                return []
            
            # 2. 提取交易数据
            sol_change = self._calculate_sol_change(tx_data.get('nativeTransfers', []))
            token_change, token_mint, token_symbol = self._calculate_token_change(
                tx_data.get('tokenTransfers', [])
            )
            
            # 3. 判定交易方向并生成信号
            signal = self._create_signal(
                sol_change, 
                token_change, 
                token_mint, 
                token_symbol,
                tx_data.get('signature'),
                tx_data.get('timestamp', int(time.time()))
            )
            
            # 4. 返回列表格式
            if signal:
                return [signal]
            else:
                return []
            
        except Exception as e:
            logger.error(f"⚠️ 解析信号出错: {e}")
            return []
    
    def _is_swap_transaction(self, tx_data: dict) -> bool:
        """
        判断是否为 SWAP 交易
        
        参数:
            tx_data: dict - 交易数据
        
        返回:
            bool - 是否为SWAP
        """
        tx_type = tx_data.get('type', 'UNKNOWN')
        return "SWAP" in tx_type
    
    def _calculate_sol_change(self, native_transfers: list) -> float:
        """
        计算 SOL 余额变动
        
        参数:
            native_transfers: list - 原生代币转账列表
        
        返回:
            float - SOL变动量（正数=收入，负数=支出）
        """
        sol_change = 0.0
        
        for transfer in native_transfers:
            amount = transfer.get('amount', 0) / 1e9  # lamports转SOL
            
            if transfer.get('fromUserAccount') == self.target_wallet:
                sol_change -= amount  # 转出（花钱）
            elif transfer.get('toUserAccount') == self.target_wallet:
                sol_change += amount  # 转入（收钱）
        
        return sol_change
    
    def _calculate_token_change(self, token_transfers: list) -> tuple:
        """
        计算 Token 余额变动
        
        参数:
            token_transfers: list - 代币转账列表
        
        返回:
            tuple - (token_change, token_mint, token_symbol)
        """
        token_change = 0.0
        target_token_mint = None
        target_token_symbol = "Unknown"
        
        for transfer in token_transfers:
            mint = transfer.get('mint')
            
            # 忽略 WSOL 包装过程
            if mint == self.wsol_mint:
                continue
            
            if transfer.get('toUserAccount') == self.target_wallet:
                # 收到 Token -> 买入
                target_token_mint = mint
                token_change = transfer.get('tokenAmount', 0)
                target_token_symbol = transfer.get('mint', 'Unknown')[:8]  # 取前8位作为符号
                
            elif transfer.get('fromUserAccount') == self.target_wallet:
                # 发出 Token -> 卖出
                target_token_mint = mint
                token_change = -transfer.get('tokenAmount', 0)
                target_token_symbol = transfer.get('mint', 'Unknown')[:8]
        
        return token_change, target_token_mint, target_token_symbol
    
    def _create_signal(self, sol_change: float, token_change: float, 
                      token_mint: str, token_symbol: str, 
                      signature: str, timestamp: int) -> Optional[TradeSignal]:
        """
        根据余额变动创建交易信号
        
        参数:
            sol_change: float - SOL变动
            token_change: float - Token变动
            token_mint: str - 代币mint
            token_symbol: str - 代币符号
            signature: str - 交易签名
            timestamp: int - 时间戳
        
        返回:
            TradeSignal - 交易信号（可能为None）
        """
        if token_change > 0:
            # 买入: Token 增加，SOL 减少
            return self._create_buy_signal(
                token_mint, token_symbol, token_change, sol_change, signature, timestamp
            )
        
        elif token_change < 0:
            # 卖出: Token 减少，SOL 增加
            return self._create_sell_signal(
                token_mint, token_symbol, token_change, sol_change, signature, timestamp
            )
        
        return None
    
    def _create_buy_signal(self, token_mint: str, token_symbol: str, 
                          token_change: float, sol_change: float,
                          signature: str, timestamp: int) -> TradeSignal:
        """
        创建买入信号
        
        参数:
            token_mint: str - 代币mint
            token_symbol: str - 代币符号
            token_change: float - Token变动量
            sol_change: float - SOL变动量
            signature: str - 交易签名
            timestamp: int - 时间戳
        
        返回:
            TradeSignal - 买入信号
        """
        return TradeSignal(
            signature=signature,
            action="BUY",
            token_mint=token_mint,
            token_symbol=token_symbol,
            amount=token_change,           # Token数量（正数）
            sol_amount=abs(sol_change),    # SOL花费（正数）
            timestamp=timestamp
        )
    
    def _create_sell_signal(self, token_mint: str, token_symbol: str,
                           token_change: float, sol_change: float,
                           signature: str, timestamp: int) -> TradeSignal:
        """
        创建卖出信号
        
        参数:
            token_mint: str - 代币mint
            token_symbol: str - 代币符号
            token_change: float - Token变动量
            sol_change: float - SOL变动量
            signature: str - 交易签名
            timestamp: int - 时间戳
        
        返回:
            TradeSignal - 卖出信号
        """
        return TradeSignal(
            signature=signature,
            action="SELL",
            token_mint=token_mint,
            token_symbol=token_symbol,
            amount=abs(token_change),      # Token数量（正数）
            sol_amount=abs(sol_change),    # SOL收入（正数）
            timestamp=timestamp
        )


# 便捷导出
__all__ = ['SignalParser']
