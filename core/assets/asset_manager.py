import logging
from storage.json_storage import JsonStorage

logger = logging.getLogger(__name__)

class AssetManager:
    """
    资产管理器
    职责：协调 Monitor 和 Storage，维护内存中的资产状态
    """
    def __init__(self, monitor):
        self.monitor = monitor
        self.storage = JsonStorage(monitor.target_wallet)
        self.local_assets = []
        self.total_value = 0.0

    def load_local(self):
        """加载本地缓存"""
        # load_assets 返回的就是处理好的扁平数据
        self.local_assets, self.total_value = self.storage.load_assets()
        return self.local_assets, self.total_value

    def update_from_chain(self, force=False):
        """
        从链上同步最新资产
        """
        try:
            # 1. 从 Monitor 获取【原始数据】
            raw_assets = self.monitor.get_assets_raw()
            
            if raw_assets is None:
                logger.warning("API 返回资产数据为空 (None)")
                return False
            
            if not isinstance(raw_assets, list):
                logger.error(f"API 返回格式错误，期望 list，实际: {type(raw_assets)}")
                return False

            # 2. 交给 Storage 进行【清洗、计算、存储】
            # 关键点：接收 storage 返回的处理后的数据！
            processed_assets, total_value = self.storage.save_assets(raw_assets, self.local_assets)

            # 3. 更新内存状态为【处理后的数据】
            self.local_assets = processed_assets
            self.total_value = total_value
            
            return True

        except Exception as e:
            logger.error(f"资产更新失败: {e}", exc_info=True)
            return False

    # 删除：print_summary() 方法
    # def print_summary(self):
    #     """打印资产详情表格"""
    #     ui.print_asset_details(self.local_assets, self.total_value)
    
    # 新增：返回数据的方法
    def get_summary_data(self):
        """
        获取资产摘要数据（不打印）
        
        返回:
            dict: {
                'assets': list,      # 资产列表
                'total_value': float # 总价值
            }
        """
        return {
            'assets': self.local_assets,
            'total_value': self.total_value
        }

    def get_total_value(self):
        return self.total_value
