"""
Helius价格源

使用Helius DAS API的getAsset方法查询价格
"""

import time
import logging
import requests
from typing import Optional
from core.data_models import PriceInfo
from config import BaseConfig
from .base_source import BasePriceSource

logger = logging.getLogger(__name__)


class HeliusSource(BasePriceSource):
    """
    Helius价格源
    
    使用Helius DAS API查询代币价格
    """
    
    def __init__(self):
        """初始化Helius价格源"""
        self.api_key = BaseConfig.HELIUS_API_KEY
        self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={self.api_key}"
        
        if not self.api_key:
            raise ValueError("❌ HELIUS_API_KEY 未配置")
        
        logger.debug("✅ Helius价格源初始化完成")
    
    def get_name(self) -> str:
        """获取价格源名称"""
        return "Helius"
    
    def query(self, mint: str) -> Optional[PriceInfo]:
        """
        查询单个代币价格
        
        参数:
            mint: str - 代币地址
        
        返回:
            PriceInfo - 价格信息，失败返回None
        """
        try:
            # 构造请求
            payload = {
                "jsonrpc": "2.0",
                "id": f"price-{mint[:8]}",
                "method": "getAsset",
                "params": {"id": mint}
            }
            
            # 发送请求
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            response.raise_for_status()
            
            # 解析响应
            data = response.json()
            
            if "result" not in data:
                logger.warning(f"⚠️ Helius未返回result: {mint[:8]}...")
                return None
            
            result = data["result"]
            
            # 提取token_info
            token_info = result.get("token_info", {})
            if not token_info:
                logger.warning(f"⚠️ 无token_info: {mint[:8]}...")
                return None
            
            # 提取价格信息
            price_info_data = token_info.get("price_info", {})
            if not price_info_data:
                logger.warning(f"⚠️ 无price_info: {mint[:8]}...")
                return None
            
            price_usd = price_info_data.get("price_per_token", 0.0)
            
            if price_usd <= 0:
                logger.warning(f"⚠️ 价格无效: {mint[:8]}... = ${price_usd}")
                return None
            
            # 构造PriceInfo对象
            price_info = PriceInfo(
                mint=mint,
                price_sol=0.0,  # Helius返回USD价格
                price_usd=price_usd,
                liquidity=0.0,  # Helius getAsset不返回流动性
                market_cap=0.0,  # Helius getAsset不返回市值
                timestamp=int(time.time()),
                source="Helius"
            )
            
            return price_info
        
        except requests.exceptions.Timeout:
            logger.error(f"❌ Helius API超时: {mint[:8]}...")
            return None
        
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Helius API请求失败: {e}")
            return None
        
        except Exception as e:
            logger.error(f"❌ 解析Helius响应失败: {e}", exc_info=True)
            return None
