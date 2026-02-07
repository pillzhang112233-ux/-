from abc import ABC, abstractmethod

class BaseMonitor(ABC):
    def __init__(self, target_wallet):
        self.target_wallet = target_wallet

    @abstractmethod
    def get_latest_transaction(self):
        """获取最新一笔交易，返回统一格式"""
        pass
