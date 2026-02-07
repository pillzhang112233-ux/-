"""
价格源基类

定义所有价格源必须实现的接口
"""

from abc import ABC, abstractmethod
from typing import Optional
from core.data_models import PriceInfo


class BasePriceSource(ABC):
    """
    价格源基类
    
    所有价格源必须继承此类并实现query方法
    """
    
    @abstractmethod
    def query(self, mint: str) -> Optional[PriceInfo]:
        """
        查询单个代币价格
        
        参数:
            mint: str - 代币地址
        
        返回:
            PriceInfo - 价格信息，失败返回None
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        获取价格源名称
        
        返回:
            str - 价格源名称（如"Helius"、"Jupiter"）
        """
        pass
