import requests
import time
from utils.logger import logger

class HeliusMonitor:
    def __init__(self, api_key, target_wallet):
        print(f"DEBUG: [HeliusMonitor] 初始化完成 (v4.3 Fix)")
        self.api_key = api_key
        self.target_wallet = target_wallet
        self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={api_key}"
        self.wsol_mint = "So11111111111111111111111111111111111111112"
        
    def get_recent_transactions(self, limit=10):
        """
        获取最近交易，并包含完整解析详情。
        Poller 调用此方法。
        """
        try:
            # 第一步：获取签名列表 (Signatures)
            payload = {
                "jsonrpc": "2.0", "id": 1, "method": "getSignaturesForAddress",
                "params": [self.target_wallet, {"limit": int(limit)}]
            }
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            data = response.json()
            
            if "result" not in data or not data["result"]:
                # 如果确实没交易，返回空
                return []

            # 提取所有签名
            signatures = [item['signature'] for item in data['result']]
            
            # 第二步：批量解析交易详情 (Parsed Transactions)
            # 这一步是之前缺失的，必须把签名换成详细数据
            parse_url = f"https://api.helius.xyz/v0/transactions?api-key={self.api_key}"
            parse_res = requests.post(parse_url, json={"transactions": signatures}, timeout=15)
            
            if parse_res.status_code == 200:
                parsed_data = parse_res.json()
                # 简单验证一下数据有效性
                if parsed_data and isinstance(parsed_data, list):
                    return parsed_data
                else:
                    print(f"DEBUG: 解析返回数据格式异常: {parsed_data}")
            else:
                logger.error(f"解析交易详情失败: {parse_res.status_code} - {parse_res.text}")
                
        except Exception as e:
            logger.error(f"获取交易列表失败: {e}")
            
        return []

    def get_transaction_detail(self, signature):
        """获取单笔交易详情 (保留备用)"""
        try:
            url = f"https://api.helius.xyz/v0/transactions/?api-key={self.api_key}"
            res = requests.post(url, json={"transactions": [signature]}, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data and isinstance(data, list):
                    return data[0]
        except Exception as e:
            logger.error(f"获取交易详情失败 [{signature}]: {e}")
        return None

    def get_sol_price(self):
        """从Helius获取SOL价格"""
        try:
            payload = {
                "jsonrpc": "2.0", "id": "sol-price", "method": "getAsset",
                "params": {"id": self.wsol_mint}
            }
            res = requests.post(self.rpc_url, json=payload, timeout=5)
            data = res.json()
            if "result" in data:
                return float(data["result"]["token_info"]["price_info"]["price_per_token"])
        except Exception as e:
            logger.error(f"获取SOL价格失败: {e}")
        
        return 0.0

    def get_assets_raw(self):
        """
        获取资产列表
        """
        final_assets = []

        # 1. SOL
        try:
            payload = {"jsonrpc": "2.0", "id": "sol", "method": "getBalance", "params": [self.target_wallet]}
            res = requests.post(self.rpc_url, json=payload, timeout=5).json()
            sol_bal = res.get("result", {}).get("value", 0) / 1e9 if isinstance(res.get("result"), dict) else res.get("result", 0) / 1e9
            
            if sol_bal > 0:
                sol_price = self.get_sol_price()
                final_assets.append({
                    "interface": "ManualSOL",
                    "id": self.wsol_mint,
                    "token_info": {
                        "symbol": "SOL", "balance": sol_bal, "decimals": 9,
                        "price_info": {"price_per_token": sol_price}
                    },
                    "nativeBalance": {"lamports": int(sol_bal * 1e9)}
                })
        except:
            pass

        # 2. Tokens
        try:
            payload = {
                "jsonrpc": "2.0", "id": "assets", "method": "getAssetsByOwner",
                "params": {
                    "ownerAddress": self.target_wallet, "page": 1, "limit": 1000,
                    "displayOptions": {"showFungible": True}
                }
            }
            res = requests.post(self.rpc_url, json=payload, timeout=10).json()
            if "result" in res and "items" in res["result"]:
                final_assets.extend(res["result"]["items"])
        except Exception as e:
            logger.error(f"获取资产失败: {e}")
            return None 

        return final_assets
