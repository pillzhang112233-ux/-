"""
资产格式化器
将资产数据格式化为表格
"""
from config import Config

class AssetFormatter:
    """资产数据格式化器"""
    
    def format(self, assets_list, total_value):
        """
        格式化资产数据为表格字符串
        
        参数:
            assets_list: 资产列表
            total_value: 总价值
        
        返回:
            str: 格式化后的字符串
        """
        lines = []
        
        # 分离 SOL 和其他代币
        sol_asset = next((item for item in assets_list if item['symbol'] == 'SOL'), None)
        tokens = [item for item in assets_list if item['symbol'] != 'SOL']
        
        # 顶部分隔线
        lines.append("\n" + "=" * 90)
        
        # SOL 余额
        if sol_asset:
            lines.append(
                f"💎 SOL 余额: {sol_asset['balance']:,.4f} SOL  "
                f"(≈ ${sol_asset['value_usd']:,.2f}) | "
                f"现价: ${sol_asset.get('price_per_token', 0):.2f}"
            )
        else:
            lines.append("💎 SOL 余额: 0.0000 SOL")
        
        # 账户总值
        lines.append(f"💰 账户总值: ${total_value:,.2f} (含代币)")
        lines.append("=" * 90)
        
        # 代币列表
        if tokens:
            # 表头
            lines.append(
                f"{'SYMBOL':<10} | {'BALANCE':<12} | {'VALUE($)':<10} | "
                f"{'MINT (Contract)':<15} | {'NAME'}"
            )
            lines.append("-" * 90)
            
            # 每个代币（使用配置的过滤阈值）
            for item in tokens:
                # 过滤小额资产（使用 Config.MIN_ASSET_DISPLAY_VALUE）
                if item['value_usd'] < Config.MIN_ASSET_DISPLAY_VALUE:
                    continue
                
                # 处理mint地址
                mint_short = f"{item['mint'][:4]}...{item['mint'][-4:]}" if item['mint'] else "N/A"
                
                # 处理symbol
                sym = item['symbol']
                if sym == "Unknown" and item.get('name') != "Unknown":
                    sym = item['name'][:9]
                
                # 格式化行
                lines.append(
                    f"{sym[:9]:<10} | "
                    f"{item['balance']:<12,.2f} | "
                    f"${item['value_usd']:<9,.2f} | "
                    f"{mint_short:<15} | "
                    f"{item['name'][:20]}"
                )
        else:
            lines.append("(无其他代币持仓)")
        
        # 底部分隔线
        lines.append("=" * 90 + "\n")
        
        return "\n".join(lines)
