"""
状态格式化器
将系统状态信息格式化为可读字符串
"""

class StatusFormatter:
    """系统状态格式化器"""
    
    def format_header(self, version, target_wallet):
        """
        格式化启动头部信息
        
        参数:
            version: 版本信息
            target_wallet: 目标钱包地址
        
        返回:
            str: 格式化后的字符串
        """
        return f"\n🚀 {version}\n🎯 监控目标: {target_wallet}"
    
    def format_idle_status(self, time_str, count, total_value, mode_status=None):
        """
        格式化空闲状态（无新交易）
        
        参数:
            time_str: 时间字符串
            count: 扫描次数
            total_value: 总资产价值
            mode_status: 轮询模式状态（可选）
        
        返回:
            str: 格式化后的字符串
        """
        base = f"[{time_str}] 扫描 #{count:<3} | 资产: ${total_value:,.2f} | 无新交易"
        
        # 添加轮询模式状态
        if mode_status:
            base += f" | {mode_status}"
        
        return base
    
    def format_scanning_status(self, time_str, count, total_value, status_msg, tracker_info=None):
        """
        格式化扫描状态
        
        参数:
            time_str: 时间字符串
            count: 扫描次数
            total_value: 总资产价值
            status_msg: 状态消息（如 "(价格更新)"）
            tracker_info: 追踪器信息（可选）
        
        返回:
            str: 格式化后的字符串
        """
        base = f"[{time_str}] 扫描 #{count:<3} | 资产: ${total_value:,.2f} {status_msg}"
        
        if tracker_info:
            base += f" | {tracker_info}"
        
        return base
    
    def format_main_loop_start(self, time_str):
        """
        格式化主循环启动消息
        
        参数:
            time_str: 时间字符串
        
        返回:
            str: 格式化后的字符串
        """
        return f"{time_str} - 🟢 主循环开始运行"
