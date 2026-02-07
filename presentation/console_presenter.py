"""
控制台展示器
这是唯一负责控制台输出的类
所有的 print 语句都应该通过这个类进行
"""

from .formatters.asset_formatter import AssetFormatter
from .formatters.transaction_formatter import TransactionFormatter
from .formatters.status_formatter import StatusFormatter
from .formatters.virtual_trade_formatter import VirtualTradeFormatter


class ConsolePresenter:
    """
    控制台展示器 - 统一的展示入口
    
    职责：
    1. 接收业务层传来的数据
    2. 调用格式化器格式化数据
    3. 输出到控制台
    
    注意：不包含任何业务逻辑，只负责展示
    """
    
    def __init__(self):
        # 初始化各种格式化器
        self.asset_formatter = AssetFormatter()
        self.tx_formatter = TransactionFormatter()
        self.status_formatter = StatusFormatter()
        self.trade_formatter = VirtualTradeFormatter()
    
    # ==================== 启动信息 ====================
    
    def show_header(self, version, target_wallet):
        """
        显示启动头部信息
        
        参数:
            version: 版本字符串
            target_wallet: 目标钱包地址
        """
        formatted = self.status_formatter.format_header(version, target_wallet)
        print(formatted)
    
    # ==================== 资产信息 ====================
    
    def show_assets(self, assets_list, total_value):
        """
        显示资产详情表格
        
        参数:
            assets_list: 资产列表
            total_value: 总价值
        """
        formatted = self.asset_formatter.format(assets_list, total_value)
        print(formatted)
    
    # ==================== 交易信息 ====================
    
    def show_new_transaction(self, time_str, description, signature):
        """
        显示新交易信息
        
        参数:
            time_str: 时间字符串
            description: 交易描述
            signature: 交易签名
        """
        formatted = self.tx_formatter.format_new_transaction(time_str, description, signature)
        print(formatted)
    
    def show_transaction_batch(self, count, time_str):
        """
        显示批量交易提示
        
        参数:
            count: 交易数量
            time_str: 时间字符串
        """
        formatted = self.tx_formatter.format_transaction_batch(count, time_str)
        print(formatted)
    
    # ==================== 系统状态 ====================
    
    def show_main_loop_start(self, time_str):
        """
        显示主循环启动消息
        
        参数:
            time_str: 时间字符串
        """
        formatted = self.status_formatter.format_main_loop_start(time_str)
        print(formatted)
    
    def show_idle_status(self, time_str, count, total_value, mode_status=None):
        """
        显示空闲状态（无新交易时）
        
        参数:
            time_str: 时间字符串
            count: 扫描次数
            total_value: 总资产价值
        """
        message = self.status_formatter.format_idle_status(time_str, count, total_value,mode_status)
        # 传递给 formatter    
        print(message)
        
    def show_scanning_status(self, time_str, count, total_value, status_msg="", tracker_info=None):
        """
        显示扫描状态（定期更新时）
        
        参数:
            time_str: 时间字符串
            count: 扫描次数
            total_value: 总资产价值
            status_msg: 状态消息（如 "(价格更新)"）
            tracker_info: 追踪器信息（可选）
        """
        formatted = self.status_formatter.format_scanning_status(
            time_str, count, total_value, status_msg, tracker_info
        )
        print(formatted)
    
    # ==================== 虚拟交易 ====================
    
    def show_buy_result(self, buy_info):
        """
        显示虚拟买入结果
        
        参数:
            buy_info: 买入信息字典，包含：
                {
                    'symbol': str,
                    'amount': float,
                    'sol_price': float,
                    'slippage': float,
                    'slippage_cost': float,
                    'cost': float
                }
        """
        formatted = self.trade_formatter.format_buy_result(buy_info)
        print(formatted)
    
    def show_sell_result(self, sell_info):
        """
        显示虚拟卖出结果
        
        参数:
            sell_info: 卖出信息字典，包含：
                {
                    'symbol': str,
                    'amount': float,
                    'slippage': float,
                    'revenue': float,
                    'profit': float,
                    'balance': float
                }
        """
        formatted = self.trade_formatter.format_sell_result(sell_info)
        print(formatted)
    
    def show_insufficient_balance_warning(self, required, available):
        """
        显示余额不足警告
        
        参数:
            required: 需要的金额
            available: 可用金额
        """
        formatted = self.trade_formatter.format_insufficient_balance(required, available)
        print(formatted)
    
    def show_no_position_warning(self, symbol):
        """
        显示无持仓警告
        
        参数:
            symbol: 代币符号
        """
        formatted = self.trade_formatter.format_no_position(symbol)
        print(formatted)
    
    # ==================== 通用消息 ====================
    
    def show_message(self, message):
        """
        显示通用消息（简单print的替代）
        
        参数:
            message: 要显示的消息
        """
        print(message)
    
    def show_error(self, error_message):
        """
        显示错误消息
        
        参数:
            error_message: 错误消息
        """
        print(f"❌ {error_message}")
    
    def show_warning(self, warning_message):
        """
        显示警告消息
        
        参数:
            warning_message: 警告消息
        """
        print(f"⚠️ {warning_message}")
    
    def show_success(self, success_message):
        """
        显示成功消息
        
        参数:
            success_message: 成功消息
        """
        print(f"✅ {success_message}")
    
    def show_info(self, info_message):
        """
        显示信息消息
        
        参数:
            info_message: 信息消息
        """
        print(f"ℹ️ {info_message}")
