"""
价格查询器（协调器）

职责：
- 管理多个价格源
- 提供统一的查询接口
- 缓存机制
- 自动切换价格源
"""

import time
import logging
from typing import Optional, Dict, List
from core.data_models import PriceInfo
from config import SystemConfig
from .sources import HeliusSource
# 未来导入其他源:
# from .sources import JupiterSource, RaydiumSource

logger = logging.getLogger(__name__)


class PriceOracle:
    """
    价格查询器（协调器）
    
    功能：
    - 管理多个价格源
    - 统一查询接口
    - 缓存机制
    - 源失败时自动切换
    """
    
    def __init__(self):
        """初始化价格查询器"""
        # 从配置读取策略
        self.strategy = SystemConfig.PRICE_SOURCE_STRATEGY
        
        # 根据配置初始化价格源
        self.sources = []
        source_map = {
            "Helius": HeliusSource,
            # 未来添加:
            # "Jupiter": JupiterSource,
            # "Raydium": RaydiumSource,
        }
        
        for source_name in SystemConfig.PRICE_SOURCES:
            if source_name in source_map:
                try:
                    source_instance = source_map[source_name]()
                    self.sources.append(source_instance)
                    logger.info(f"   ✅ 加载价格源: {source_name}")
                except Exception as e:
                    logger.error(f"   ❌ 加载价格源失败 [{source_name}]: {e}")
            else:
                logger.warning(f"   ⚠️ 未知的价格源: {source_name}")
        
        if not self.sources:
            raise ValueError("❌ 没有可用的价格源，请检查配置")
        
        # 缓存
        self.cache: Dict[str, tuple] = {}  # {mint: (PriceInfo, timestamp)}
        self.cache_ttl = SystemConfig.PRICE_CACHE_TTL
        
        logger.info(
            f"✅ 价格查询器初始化完成 "
            f"[策略: {self.strategy}, 源数量: {len(self.sources)}]"
        )
    
    def get_price(self, mint: str) -> Optional[PriceInfo]:
        """
        查询单个代币价格
        
        参数:
            mint: str - 代币地址
        
        返回:
            PriceInfo - 价格信息，失败返回None
        
        流程：
        1. 检查缓存
        2. 按优先级依次尝试各个价格源
        3. 更新缓存
        """
        # 检查缓存
        if self._is_cached(mint):
            cached_price, _ = self.cache[mint]
            logger.debug(f"🔄 使用缓存价格: {mint[:8]}...")
            return cached_price
        
        # 根据策略查询
        if self.strategy == "single":
            # 单一源模式：只用第一个
            source = self.sources[0]
            try:
                price_info = source.query(mint)
                if price_info:
                    self.cache[mint] = (price_info, int(time.time()))
                    logger.debug(
                        f"💰 [{source.get_name()}] 查询成功: "
                        f"{mint[:8]}... = ${price_info.price_usd:.6f}"
                    )
                    return price_info
            except Exception as e:
                logger.error(f"❌ [{source.get_name()}] 查询异常: {e}")
            
            logger.warning(f"❌ 价格查询失败: {mint[:8]}...")
            return None

        elif self.strategy == "fallback":
            # 失败切换模式：依次尝试
            for source in self.sources:
                try:
                    price_info = source.query(mint)
                    
                    if price_info:
                        self.cache[mint] = (price_info, int(time.time()))
                        logger.debug(
                            f"💰 [{source.get_name()}] 查询成功: "
                            f"{mint[:8]}... = ${price_info.price_usd:.6f}"
                        )
                        return price_info
                    else:
                        logger.debug(f"⚠️ [{source.get_name()}] 查询失败，尝试下一个源...")
                        continue
                
                except Exception as e:
                    logger.error(f"❌ [{source.get_name()}] 查询异常: {e}")
                    continue
            
            logger.warning(f"❌ 所有价格源都无法查询: {mint[:8]}...")
            return None

        else:
            logger.error(f"❌ 未知的价格源策略: {self.strategy}")
            return None
    
    def get_batch_prices(self, mints: List[str]) -> Dict[str, PriceInfo]:
        """
        批量查询价格
        
        参数:
            mints: List[str] - 代币地址列表
        
        返回:
            dict - {mint: PriceInfo}
        """
        result = {}
        uncached_mints = []
        
        # 1. 先从缓存获取
        for mint in mints:
            if self._is_cached(mint):
                cached_price, _ = self.cache[mint]
                result[mint] = cached_price
            else:
                uncached_mints.append(mint)
        
        logger.debug(
            f"📊 批量查询: 总数 {len(mints)}, "
            f"缓存命中 {len(result)}, 需查询 {len(uncached_mints)}"
        )
        
        # 2. 查询未缓存的
        current_time = int(time.time())
        for mint in uncached_mints:
            price_info = self.get_price(mint)  # 使用统一接口
            if price_info:
                result[mint] = price_info
        
        return result
    
    def _is_cached(self, mint: str) -> bool:
        """
        检查是否有有效缓存
        
        参数:
            mint: str - 代币地址
        
        返回:
            bool - 是否有有效缓存
        """
        if mint not in self.cache:
            return False
        
        _, cached_time = self.cache[mint]
        current_time = int(time.time())
        
        # 检查是否过期
        if current_time - cached_time > self.cache_ttl:
            del self.cache[mint]
            return False
        
        return True
    
    def clear_cache(self):
        """清空所有缓存"""
        self.cache.clear()
        logger.info("🗑️ 价格缓存已清空")
    
    def get_cache_stats(self) -> dict:
        """
        获取缓存统计
        
        返回:
            dict - 缓存统计信息
        """
        current_time = int(time.time())
        valid_count = 0
        expired_count = 0
        
        for mint, (_, cached_time) in self.cache.items():
            if current_time - cached_time <= self.cache_ttl:
                valid_count += 1
            else:
                expired_count += 1
        
        return {
            'total': len(self.cache),
            'valid': valid_count,
            'expired': expired_count,
            'ttl': self.cache_ttl,
            'sources': [s.get_name() for s in self.sources]
        }
    
    def add_source(self, source):
        """
        添加新的价格源
        
        参数:
            source: BasePriceSource - 价格源实例
        """
        self.sources.append(source)
        logger.info(f"➕ 添加价格源: {source.get_name()}")
    
    def set_source_priority(self, source_names: List[str]):
        """
        设置价格源优先级
        
        参数:
            source_names: List[str] - 价格源名称列表（按优先级）
        """
        # TODO: 实现优先级调整
        pass
