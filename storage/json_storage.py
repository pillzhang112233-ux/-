import json
import os
import time

class JsonStorage:
    def __init__(self, wallet_address):
        """初始化存储（支持会话管理）"""
        # 保存钱包地址信息
        self.wallet_address = wallet_address
        self.wallet_short = self._format_wallet_short(wallet_address)
        
        # Phase 1 资产文件路径
        short_addr = f"{wallet_address[:6]}_{wallet_address[-4:]}"
        assets_dir = os.path.join("database", "追踪地址代币记录")
        if not os.path.exists(assets_dir):
            os.makedirs(assets_dir)
        self.assets_file = os.path.join(assets_dir, f"wallet_{short_addr}_current.json")
        
        # Phase 2 会话管理路径
        self.base_dir = os.path.join("database", "会话记录")
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
        
        # Phase 2 会话管理文件
        self.sessions_config_file = os.path.join(self.base_dir, "current_sessions.json")
        
        # 获取或创建当前会话
        self.current_session = self._get_or_create_session()
        self.session_dir = os.path.join(self.base_dir, self.current_session)
        
        # 确保会话目录存在
        if not os.path.exists(self.session_dir):
            os.makedirs(self.session_dir)
        
        # 会话内的文件路径
        self.metadata_file = os.path.join(self.session_dir, "metadata.json")
        self.balance_file = os.path.join(self.session_dir, "balance.json")
        self.balance_history_file = os.path.join(self.session_dir, "balance_history.json")
        self.positions_file = os.path.join(self.session_dir, "positions.json")
        self.trades_file = os.path.join(self.session_dir, "trades.json")

    def load_assets(self):
        """加载资产数据"""
        if not os.path.exists(self.assets_file):
            return [], 0.0
        try:
            with open(self.assets_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('items', []), data.get('total_value', 0.0)
        except:
            return [], 0.0

    def save_assets(self, raw_assets_list, old_assets_list=[]):
        """
        智能保存资产
        raw_assets_list: 这次从 API 抓回来的原始数据
        old_assets_list: 上一次保存的旧数据 (用于填补缺失的价格)
        """
        try:
            # 1. 建立价格记忆
            price_memory = self._build_price_memory(old_assets_list)
            
            # 2. 处理每个资产
            processed_assets = []
            total_value = 0.0
            
            for item in raw_assets_list:
                asset = self._process_single_asset(item, price_memory)
                if asset and asset['balance'] > 0:
                    processed_assets.append(asset)
                    total_value += asset['value_usd']
            
            # 3. 排序（按价值降序）
            processed_assets.sort(key=lambda x: x['value_usd'], reverse=True)
            
            # 4. 保存到文件
            self._save_to_file(processed_assets, total_value)
            
            return processed_assets, total_value

        except Exception as e:
            print(f"❌ 保存资产失败: {e}")
            return [], 0.0

    def _build_price_memory(self, old_assets_list):
        """
        从旧数据建立价格记忆字典
        返回: {mint: price}
        """
        price_memory = {}
        if old_assets_list:
            for old in old_assets_list:
                # 只记忆有效价格
                if old.get('price_per_token', 0) > 0:
                    price_memory[old['mint']] = old['price_per_token']
        return price_memory

    def _process_single_asset(self, item, price_memory):
        """
        处理单个资产数据
        返回: 标准化的资产字典 或 None
        """
        interface = item.get('interface', '')
        
        if interface == "ManualSOL":
            return self._extract_sol_asset(item, price_memory)
        else:
            return self._extract_token_asset(item, price_memory)

    def _extract_sol_asset(self, item, price_memory):
        """提取 SOL 资产信息"""
        token_info = item.get('token_info', {})
        price_info = token_info.get('price_info', {}) or {}
        mint = item.get('id', '')
        
        # 获取余额
        balance = item.get('nativeBalance', {}).get('lamports', 0) / 1e9
        
        # 获取价格（带记忆）
        price_per_token = price_info.get('price_per_token', 0)
        if price_per_token <= 0 and mint in price_memory:
            price_per_token = price_memory[mint]
        
        return {
            "symbol": "SOL",
            "name": "Solana (Native)",
            "balance": balance,
            "value_usd": balance * price_per_token,
            "price_per_token": price_per_token,
            "mint": mint
        }

    def _extract_token_asset(self, item, price_memory):
        """提取 Token 资产信息"""
        token_info = item.get('token_info', {})
        content = item.get('content', {})
        metadata = content.get('metadata', {})
        price_info = token_info.get('price_info', {}) or {}
        mint = item.get('id', '')
        
        # 获取基础信息
        symbol = token_info.get('symbol', 'Unknown')
        name = metadata.get('name', 'Unknown')
        
        # 计算余额
        decimals = token_info.get('decimals', 0)
        raw_balance = token_info.get('balance', 0)
        balance = raw_balance / (10 ** decimals) if decimals else 0
        
        # 获取价格（带记忆）
        price_per_token = price_info.get('price_per_token', 0)
        if price_per_token <= 0 and mint in price_memory:
            price_per_token = price_memory[mint]
        
        return {
            "symbol": symbol,
            "name": name,
            "balance": balance,
            "value_usd": balance * price_per_token,
            "price_per_token": price_per_token,
            "mint": mint
        }

    def _save_to_file(self, processed_assets, total_value):
        """保存数据到JSON文件"""
        save_data = {
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_value": total_value,
            "items": processed_assets
        }
        
        with open(self.assets_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
            
    # ========== 持仓管理 ==========
    
    def load_positions(self):
        """
        加载所有持仓
        
        返回:
            dict - {mint: position_dict}
        """
        if not os.path.exists(self.positions_file):
            return {}
        
        try:
            with open(self.positions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 加载持仓失败: {e}")
            return {}
    
    def save_positions(self, positions_dict):
        """
        保存所有持仓
        
        参数:
            positions_dict: dict - {mint: position_dict}
        """
        try:
            with open(self.positions_file, 'w', encoding='utf-8') as f:
                json.dump(positions_dict, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 保存持仓失败: {e}")
    
    def save_position(self, mint, position_data):
        """
        保存单个持仓
        
        参数:
            mint: str - 代币地址
            position_data: dict - 持仓数据
        """
        positions = self.load_positions()
        positions[mint] = position_data
        self.save_positions(positions)
    
    def delete_position(self, mint):
        """
        删除单个持仓
        
        参数:
            mint: str - 代币地址
        """
        positions = self.load_positions()
        if mint in positions:
            del positions[mint]
            self.save_positions(positions)
    
    # ========== 交易记录管理 ==========
    
    def load_trades(self, filters=None):
        """
        加载虚拟交易历史
        
        参数:
            filters: dict - 筛选条件（可选）
                例如: {'action': 'BUY', 'mint': 'xxx'}
        
        返回:
            list - 交易记录列表
        """
        if not os.path.exists(self.trades_file):
            return []
        
        try:
            with open(self.trades_file, 'r', encoding='utf-8') as f:
                trades = json.load(f)
            
            # 应用筛选条件
            if filters:
                filtered = []
                for trade in trades:
                    match = True
                    for key, value in filters.items():
                        if trade.get(key) != value:
                            match = False
                            break
                    if match:
                        filtered.append(trade)
                return filtered
            
            return trades
        
        except Exception as e:
            print(f"❌ 加载交易记录失败: {e}")
            return []
    
    def save_trade(self, trade_data):
        """
        保存单笔虚拟交易
        
        参数:
            trade_data: dict - 交易数据
        """
        try:
            # 加载现有记录
            trades = self.load_trades()
            
            # 添加时间戳和ID
            trade_data['saved_at'] = time.strftime("%Y-%m-%d %H:%M:%S")
            trade_data.setdefault('trade_id', f"{int(time.time())}_{len(trades)}")
            
            # 追加新记录
            trades.append(trade_data)
            
            # 保存
            with open(self.trades_file, 'w', encoding='utf-8') as f:
                json.dump(trades, f, ensure_ascii=False, indent=2)
        
        except Exception as e:
            print(f"❌ 保存交易记录失败: {e}")
    
    # ========== 余额管理 ==========
    
    def load_balance(self):
        """
        加载虚拟余额
        
        返回:
            float - 当前余额，如果文件不存在返回配置的初始余额
        """
        if not os.path.exists(self.balance_file):
            # 首次运行，返回初始余额
            from config import TradingConfig
            return TradingConfig.INITIAL_BALANCE
        
        try:
            with open(self.balance_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('balance', 0.0)
        except Exception as e:
            print(f"❌ 加载余额失败: {e}")
            from config import TradingConfig
            return TradingConfig.INITIAL_BALANCE
    
    def save_balance(self, balance):
        """
        保存虚拟余额
        
        参数:
            balance: float - 当前余额
        """
        try:
            data = {
                'balance': balance,
                'updated_at': time.strftime("%Y-%m-%d %H:%M:%S"),
                'timestamp': int(time.time())
            }
            with open(self.balance_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 保存余额失败: {e}")
    
    # ========== 性能统计辅助方法 ==========
    
    def get_trade_statistics(self):
        """
        获取交易统计摘要
        
        返回:
            dict - 统计数据
        """
        trades = self.load_trades()
        
        if not trades:
            return {
                'total_trades': 0,
                'buy_trades': 0,
                'sell_trades': 0,
            }
        
        buy_count = sum(1 for t in trades if t.get('basic_info', {}).get('action') == 'BUY')
        sell_count = sum(1 for t in trades if t.get('basic_info', {}).get('action') == 'SELL')
        
        return {
            'total_trades': len(trades),
            'buy_trades': buy_count,
            'sell_trades': sell_count,
        }
    # ==================== 会话管理方法 ====================

    def _format_wallet_short(self, wallet_address):
        """
        格式化钱包地址为短名称
        
        参数:
            wallet_address: str - 完整钱包地址
        
        返回:
            str - 短名称 (前6位_后4位)
        """
        if len(wallet_address) < 10:
            return wallet_address
        return f"{wallet_address[:6]}_{wallet_address[-4:]}"

    def _get_or_create_session(self):
        """
        获取当前会话ID，如果不存在则创建新会话
        
        返回:
            str - 会话ID
        """
        # 加载会话配置
        sessions_config = self._load_sessions_config()
        
        # 检查当前钱包是否有活跃会话
        if self.wallet_short in sessions_config:
            session_info = sessions_config[self.wallet_short]
            if session_info.get('status') == 'active':
                return session_info['current_session']
        
        # 没有活跃会话，创建新会话
        return self.create_new_session()

    def _load_sessions_config(self):
        """
        加载会话配置文件
        
        返回:
            dict - 会话配置
        """
        if not os.path.exists(self.sessions_config_file):
            return {}
        
        try:
            with open(self.sessions_config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 加载会话配置失败: {e}")
            return {}

    def _save_sessions_config(self, sessions_config):
        """
        保存会话配置文件
        
        参数:
            sessions_config: dict - 会话配置
        """
        try:
            with open(self.sessions_config_file, 'w', encoding='utf-8') as f:
                json.dump(sessions_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 保存会话配置失败: {e}")

    def create_new_session(self, nickname=None):
        """
        创建新会话
        
        参数:
            nickname: str - 可选的会话昵称
        
        返回:
            str - 新会话ID
        """
        from config import SystemConfig
        
        # 生成会话ID：virtual_时间戳_钱包短名_序号
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        prefix = SystemConfig.VIRTUAL_SESSION_PREFIX
        
        # 查找同一时间戳的会话数量（防止重复）
        existing_sessions = self.list_sessions_by_wallet(self.wallet_address)
        sequence = 1
        
        for session_id in existing_sessions:
            if timestamp in session_id:
                # 提取序号
                parts = session_id.split('_')
                if len(parts) >= 4:
                    try:
                        seq_num = int(parts[-1])
                        if seq_num >= sequence:
                            sequence = seq_num + 1
                    except:
                        pass
        
        # 生成完整会话ID
        session_id = f"{prefix}_{timestamp}_{self.wallet_short}_{sequence:03d}"
        
        # 创建会话目录
        session_dir = os.path.join(self.base_dir, session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        # 更新会话配置
        sessions_config = self._load_sessions_config()
        sessions_config[self.wallet_short] = {
            "wallet_address": self.wallet_address,
            "current_session": session_id,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "active",
            "nickname": nickname
        }
        self._save_sessions_config(sessions_config)
        
        # 初始化会话元数据
        self._initialize_session_metadata(session_id)
        
        print(f"✅ 创建新会话: {session_id}")
        return session_id

    def _initialize_session_metadata(self, session_id):
        """
        初始化会话元数据
        
        参数:
            session_id: str - 会话ID
        """
        from config import BaseConfig, TradingConfig, RiskConfig, SystemConfig
        
        # 获取会话配置
        sessions_config = self._load_sessions_config()
        session_info = sessions_config.get(self.wallet_short, {})
        
        # 创建元数据
        metadata = {
            "session_id": session_id,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "created_timestamp": int(time.time()),
            "status": "active",
            
            "wallet_info": {
                "address": self.wallet_address,
                "short_name": self.wallet_short,
                "nickname": session_info.get("nickname", "")
            },
            
            "initial_balance": TradingConfig.INITIAL_BALANCE,
            "current_balance": TradingConfig.INITIAL_BALANCE,
            "current_position_value": 0.0,
            "current_total_value": TradingConfig.INITIAL_BALANCE,
            
            "config_snapshot": {
                "base_config": {
                    "target_wallet": BaseConfig.TARGET_WALLET,
                    "helius_api_configured": bool(BaseConfig.HELIUS_API_KEY)
                },
                
                "trading_config": {
                    "initial_balance": TradingConfig.INITIAL_BALANCE,
                    "trade_ratio": TradingConfig.TRADE_RATIO,
                    "min_trade_amount": TradingConfig.MIN_TRADE_AMOUNT,
                    "enable_filtering": TradingConfig.ENABLE_FILTERING,
                    "min_liquidity": TradingConfig.MIN_LIQUIDITY,
                    "min_market_cap": TradingConfig.MIN_MARKET_CAP,
                    "max_market_cap": TradingConfig.MAX_MARKET_CAP,
                    "blacklist_tokens": TradingConfig.BLACKLIST_TOKENS,
                    "allow_virtual_deposit": TradingConfig.ALLOW_VIRTUAL_DEPOSIT,
                    "allow_virtual_withdrawal": TradingConfig.ALLOW_VIRTUAL_WITHDRAWAL
                },
                
                "risk_config": {
                    "stop_loss_percent": RiskConfig.STOP_LOSS_PERCENT,
                    "take_profit_percent": RiskConfig.TAKE_PROFIT_PERCENT,
                    "max_hold_time": RiskConfig.MAX_HOLD_TIME,
                    "max_drawdown": RiskConfig.MAX_DRAWDOWN,
                    
                },
                
                "system_config": {
                    "mode": SystemConfig.MODE,
                    "slippage_min_bps": SystemConfig.SLIPPAGE_MIN_BPS,
                    "slippage_max_bps": SystemConfig.SLIPPAGE_MAX_BPS,
                    "price_cache_ttl": SystemConfig.PRICE_CACHE_TTL,
                    "price_source_strategy": SystemConfig.PRICE_SOURCE_STRATEGY,
                    "price_sources": SystemConfig.PRICE_SOURCES,
                    "price_source_timeout": SystemConfig.PRICE_SOURCE_TIMEOUT,
                    "poll_interval": SystemConfig.POLL_INTERVAL,
                    "virtual_session_auto_backup": SystemConfig.VIRTUAL_SESSION_AUTO_BACKUP,
                    "enable_balance_history": SystemConfig.ENABLE_BALANCE_HISTORY,
                    "enable_session_metadata": SystemConfig.ENABLE_SESSION_METADATA
                }
            },
            
            "operations": [
                {
                    "type": "init",
                    "timestamp": int(time.time()),
                    "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "amount": TradingConfig.INITIAL_BALANCE,
                    "note": "初始化会话"
                }
            ],
            
            "statistics": {
                "total_trades": 0,
                "buy_trades": 0,
                "sell_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "total_return": 0.0,
                "avg_profit": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "max_balance": TradingConfig.INITIAL_BALANCE,
                "min_balance": TradingConfig.INITIAL_BALANCE,
                "max_drawdown": 0.0,
                "max_drawdown_percent": 0.0,
                "current_positions": 0,
                "last_updated": int(time.time())
            }
        }
        
        # 保存元数据
        metadata_file = os.path.join(self.base_dir, session_id, "metadata.json")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 初始化余额历史
        balance_history = [
            {
                "timestamp": int(time.time()),
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
                "balance": TradingConfig.INITIAL_BALANCE,
                "change": 0.0,
                "change_percent": 0.0,
                "reason": "init",
                "position_value": 0.0,
                "total_value": TradingConfig.INITIAL_BALANCE,
                "related_trade_id": None,
                "note": "初始化"
            }
        ]
        
        balance_history_file = os.path.join(self.base_dir, session_id, "balance_history.json")
        with open(balance_history_file, 'w', encoding='utf-8') as f:
            json.dump(balance_history, f, ensure_ascii=False, indent=2)

    def list_sessions_by_wallet(self, wallet_address):
        """
        列出某个钱包的所有会话
        
        参数:
            wallet_address: str - 钱包地址
        
        返回:
            list - 会话ID列表
        """
        wallet_short = self._format_wallet_short(wallet_address)
        sessions = []
        
        try:
            for item in os.listdir(self.base_dir):
                item_path = os.path.join(self.base_dir, item)
                if os.path.isdir(item_path) and wallet_short in item:
                    sessions.append(item)
            
            # 按时间排序
            sessions.sort()
            return sessions
        
        except Exception as e:
            print(f"❌ 列出会话失败: {e}")
            return []

    def get_current_session(self):
        """获取当前会话ID"""
        return self.current_session

    def load_session_metadata(self):
        """
        加载当前会话元数据
        
        返回:
            dict - 元数据
        """
        if not os.path.exists(self.metadata_file):
            return None
        
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 加载会话元数据失败: {e}")
            return None

    def save_session_metadata(self, metadata):
        """
        保存会话元数据
        
        参数:
            metadata: dict - 元数据
        """
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 保存会话元数据失败: {e}")
            
    def save_balance_history_entry(self, balance, change, reason, position_value=0.0, related_trade_id=None, note=""):
        """
        添加余额历史记录
        
        参数:
            balance: float - 当前余额
            change: float - 变化金额
            reason: str - 变化原因 (buy/sell/deposit/withdraw)
            position_value: float - 持仓价值
            related_trade_id: str - 关联的交易ID
            note: str - 备注
        """
        from config import SystemConfig
        
        if not SystemConfig.ENABLE_BALANCE_HISTORY:
            return
        
        # 加载现有历史
        history = []
        if os.path.exists(self.balance_history_file):
            try:
                with open(self.balance_history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except:
                history = []
        
        # 计算变化百分比
        if len(history) > 0:
            previous_balance = history[-1]['balance']
            change_percent = (change / previous_balance) if previous_balance > 0 else 0.0
        else:
            change_percent = 0.0
        
        # 创建新记录
        entry = {
            "timestamp": int(time.time()),
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
            "balance": balance,
            "change": change,
            "change_percent": change_percent,
            "reason": reason,
            "position_value": position_value,
            "total_value": balance + position_value,
            "related_trade_id": related_trade_id,
            "note": note
        }
        
        # 如果是交易相关，添加额外信息
        if reason in ["buy", "sell"] and related_trade_id:
            # 可以从trades.json读取更多信息
            entry["token_symbol"] = note.split()[0] if note else ""
        
        # 追加记录
        history.append(entry)
        
        # 保存
        try:
            with open(self.balance_history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 保存余额历史失败: {e}")

    def update_session_statistics(self, stats_update):
        """
        更新会话统计数据
        
        参数:
            stats_update: dict - 要更新的统计数据
        """
        metadata = self.load_session_metadata()
        if not metadata:
            return
        
        # 更新统计
        for key, value in stats_update.items():
            if key in metadata['statistics']:
                metadata['statistics'][key] = value
        
        # 更新时间戳
        metadata['statistics']['last_updated'] = int(time.time())
        
        # 保存
        self.save_session_metadata(metadata)

    def record_operation(self, operation_type, amount=0.0, note="", **kwargs):
        """
        记录会话操作
        
        参数:
            operation_type: str - 操作类型 (init/deposit/withdraw/reset)
            amount: float - 金额
            note: str - 备注
            **kwargs: 其他参数
        """
        metadata = self.load_session_metadata()
        if not metadata:
            return
        
        # 创建操作记录
        operation = {
            "type": operation_type,
            "timestamp": int(time.time()),
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
            "amount": amount,
            "note": note
        }
        
        # 添加额外信息
        if operation_type in ["deposit", "withdraw"]:
            operation["balance_before"] = kwargs.get("balance_before", 0.0)
            operation["balance_after"] = kwargs.get("balance_after", 0.0)
        
        # 追加操作记录
        metadata['operations'].append(operation)
        
        # 保存
        self.save_session_metadata(metadata)

    def archive_session(self, reason="手动归档"):
        """
        归档当前会话
        
        参数:
            reason: str - 归档原因
        """
        from config import SystemConfig
        
        if not SystemConfig.VIRTUAL_SESSION_AUTO_BACKUP:
            print("⚠️ 自动备份已禁用，跳过归档")
            return
        
        # 加载元数据
        metadata = self.load_session_metadata()
        if not metadata:
            return
        
        # 更新状态
        metadata['status'] = 'completed'
        metadata['completed_at'] = time.strftime("%Y-%m-%d %H:%M:%S")
        metadata['completed_timestamp'] = int(time.time())
        
        # 记录归档操作
        metadata['operations'].append({
            "type": "archive",
            "timestamp": int(time.time()),
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reason": reason,
            "note": f"会话归档: {reason}"
        })
        
        # 保存元数据
        self.save_session_metadata(metadata)
        
        # 更新会话配置（将状态改为completed）
        sessions_config = self._load_sessions_config()
        if self.wallet_short in sessions_config:
            sessions_config[self.wallet_short]['status'] = 'completed'
            self._save_sessions_config(sessions_config)
        
        print(f"✅ 会话已归档: {self.current_session}")

    def reset_session(self, reason="手动重置"):
        """
        重置会话（归档当前会话，创建新会话）
        
        参数:
            reason: str - 重置原因
        
        返回:
            str - 新会话ID
        """
        # 1. 归档当前会话
        print(f"📦 归档旧会话: {self.current_session}")
        self.archive_session(reason)
        
        # 2. 创建新会话
        print(f"🆕 创建新会话...")
        new_session_id = self.create_new_session()
        
        # 3. 更新当前会话引用
        self.current_session = new_session_id
        self.session_dir = os.path.join(self.base_dir, new_session_id)
        
        # 更新文件路径
        self.metadata_file = os.path.join(self.session_dir, "metadata.json")
        self.balance_file = os.path.join(self.session_dir, "balance.json")
        self.balance_history_file = os.path.join(self.session_dir, "balance_history.json")
        self.positions_file = os.path.join(self.session_dir, "positions.json")
        self.trades_file = os.path.join(self.session_dir, "trades.json")
        
        print(f"✅ 会话重置完成，新会话: {new_session_id}")
        return new_session_id

    def get_session_summary(self):
        """
        获取当前会话摘要
        
        返回:
            dict - 会话摘要信息
        """
        metadata = self.load_session_metadata()
        if not metadata:
            return {}
        
        return {
            "session_id": metadata['session_id'],
            "wallet_short": metadata['wallet_info']['short_name'],
            "nickname": metadata['wallet_info'].get('nickname', ''),
            "created_at": metadata['created_at'],
            "status": metadata['status'],
            "initial_balance": metadata['initial_balance'],
            "current_balance": metadata['current_balance'],
            "current_total_value": metadata['current_total_value'],
            "total_trades": metadata['statistics']['total_trades'],
            "win_rate": metadata['statistics']['win_rate'],
            "total_pnl": metadata['statistics']['total_pnl'],
            "total_return": metadata['statistics']['total_return']
        }

    def list_all_sessions(self):
        """
        列出所有会话
        
        返回:
            list - 会话摘要列表
        """
        sessions = []
        
        try:
            for item in os.listdir(self.base_dir):
                item_path = os.path.join(self.base_dir, item)
                if os.path.isdir(item_path) and item.startswith("virtual_"):
                    # 尝试读取元数据
                    metadata_file = os.path.join(item_path, "metadata.json")
                    if os.path.exists(metadata_file):
                        try:
                            with open(metadata_file, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                                sessions.append({
                                    "session_id": metadata['session_id'],
                                    "wallet_short": metadata['wallet_info']['short_name'],
                                    "created_at": metadata['created_at'],
                                    "status": metadata['status'],
                                    "total_trades": metadata['statistics']['total_trades'],
                                    "total_pnl": metadata['statistics']['total_pnl']
                                })
                        except:
                            pass
            
            # 按创建时间排序
            sessions.sort(key=lambda x: x['created_at'], reverse=True)
            return sessions
        
        except Exception as e:
            print(f"❌ 列出会话失败: {e}")
            return []
