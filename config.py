import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


# ==================== 基础配置 ====================
class BaseConfig:
    """基础配置：API密钥、钱包地址等"""
    
    # API 设置
    HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
    
    # 监控设置
    TARGET_WALLET = os.getenv("TARGET_WALLET")
    
    # 钱包设置（用于实盘）
    MY_PRIVATE_KEY = os.getenv("MY_PRIVATE_KEY")
    MY_WALLET_ADDRESS = os.getenv("MY_WALLET_ADDRESS")


# ==================== 交易策略配置 ====================
class TradingConfig:
    """交易策略配置：仓位、筛选条件等"""
    
    # 初始资金
    INITIAL_BALANCE = 1000.0  # USD
    
    # === 仓位管理（定额投入）===
    USE_FIXED_AMOUNT = True           # 使用定额投入
    FIXED_TRADE_AMOUNT = 50.0         # 每次固定投入 $50
    
    # 保留比例模式（未来可能需要）
    TRADE_RATIO = 0.10                # 比例模式：10%（USE_FIXED_AMOUNT=False时生效）
    MIN_TRADE_AMOUNT = 10.0           # 最小交易金额 $10
    MIN_TRADE_AMOUNT = 10.0  # 最小交易金额 $10
    
    # 筛选总开关
    ENABLE_FILTERING = False  # True=启用筛选, False=完全跟单不筛选
    
    # 筛选条件（仅在ENABLE_FILTERING=True时生效）
    MIN_LIQUIDITY = 5000.0  # 最小流动性 $5k (设为0则不筛选流动性)
    MIN_MARKET_CAP = 50000.0  # 最小市值 $50k (设为0则不筛选)
    MAX_MARKET_CAP = 5000000.0  # 最大市值 $5M (设为float('inf')则不限制)
    
    # 黑名单
    BLACKLIST_TOKENS = []  # 代币地址黑名单
    
    # 虚拟资金管理
    ALLOW_VIRTUAL_DEPOSIT = True  # 允许虚拟入金
    ALLOW_VIRTUAL_WITHDRAWAL = False  # 允许虚拟出金


# ==================== 风险控制配置 ====================
class RiskConfig:
    """风险控制配置：止盈止损等"""
    
    # === 聪明钱表现风控 ===
    MAX_CONSECUTIVE_LOSSES = 5        # 连续亏损5次触发风控
    STOP_AFTER_TRIGGER_HOURS = 24     # 触发后暂停24小时
    
    # === 总体保护 ===
    MAX_DRAWDOWN = -0.30              # 最大回撤 -30%
    
    # === 单持仓止损止盈（可开关）===
    ENABLE_POSITION_STOP_LOSS = False    # 是否启用单持仓止损
    ENABLE_POSITION_TAKE_PROFIT = False  # 是否启用单持仓止盈
    STOP_LOSS_PERCENT = -0.30            # 止损线（启用时生效）
    TAKE_PROFIT_PERCENT = 1.00           # 止盈线（启用时生效）
    MAX_HOLD_TIME = 86400                # 最大持仓时间（启用时生效）


class StrategyConfig:
    """策略配置（未来扩展）"""
    
    # === 出本金策略（未来实现）===
    ENABLE_RECOVER_PRINCIPAL = False
    RECOVER_PRINCIPAL_THRESHOLD = 0.50  # 涨50%时出本金
    
    # === 移动止损策略（未来实现）===
    ENABLE_TRAILING_STOP = False
    TRAILING_STOP_PERCENT = 0.10  # 从最高点回撤10%止损
    
    # === 分批止盈策略（未来实现）===
    ENABLE_PARTIAL_TAKE_PROFIT = False
    PARTIAL_LEVELS = [
        (0.50, 0.30),  # 涨50%卖30%
        (1.00, 0.50),  # 涨100%再卖50%
    ]
# ==================== 系统运行配置 ====================
class SystemConfig:
    """系统运行配置：模式切换、日志等"""
    
    # 运行模式
    MODE = "PHASE_2_LIVE"  # 选项: "PHASE_1_BACKTEST" 或 "PHASE_2_LIVE"
    
    # 滑点模拟（保持原有BPS逻辑）
    SLIPPAGE_MIN_BPS = 50   # 0.5%
    SLIPPAGE_MAX_BPS = 5000  # 50%
    
    # 价格缓存
    PRICE_CACHE_TTL = 5  # 价格缓存时间 5秒
    
    # 轮询设置
    POLL_INTERVAL = 20  # 轮询间隔（秒）
    POLL_TRANSACTION_LIMIT = 20  # 单次轮询获取的交易数量
    INIT_BACKFILL_LIMIT = 10  # 初始化回溯的交易数量
    
    # 爆发模式设置
    IDLE_INTERVAL = 30  # 平时空闲轮询间隔（秒）
    BURST_INTERVAL = 5  # 爆发模式轮询间隔（秒）
    BURST_DURATION = 300  # 爆发模式持续时间（秒）
    
    # 资产更新设置
    ASSET_SYNC_MAX_RETRIES = 5  # 资产同步最大重试次数
    ASSET_SYNC_RETRY_DELAY = 2  # 资产同步重试延迟（秒）
    PRICE_UPDATE_INTERVAL = 5  # 定期价格更新间隔
    
    # 资产过滤设置
    MIN_ASSET_DISPLAY_VALUE = 1.0  # 资产显示的最小价值阈值（USD）

    # 价格查询设置
    PRICE_SOURCE_STRATEGY = "fallback"  # 选项: "single"(仅用第一个) / "fallback"(失败切换)
    PRICE_SOURCES = ["Helius"]  # 价格源列表，按优先级排序。可选: "Helius", "Jupiter", "Raydium"
    PRICE_SOURCE_TIMEOUT = 10  # 每个源的超时时间（秒）

    # 虚拟交易会话管理
    VIRTUAL_SESSION_AUTO_BACKUP = True  # 重置时自动备份旧会话
    VIRTUAL_SESSION_PREFIX = "virtual"  # 会话文件夹前缀
    ENABLE_BALANCE_HISTORY = True  # 启用余额历史记录
    ENABLE_SESSION_METADATA = True  # 启用会话元数据记录
    
# ==================== 主配置类（向后兼容）====================
class Config:
    """主配置类 - 保持所有现有代码兼容"""
    
    # ==================== API 设置 ====================
    HELIUS_API_KEY = BaseConfig.HELIUS_API_KEY
    
    # ==================== 监控设置 ====================
    TARGET_WALLET = BaseConfig.TARGET_WALLET
    
    # ==================== 轮询设置 ====================
    POLL_INTERVAL = SystemConfig.POLL_INTERVAL
    POLL_TRANSACTION_LIMIT = SystemConfig.POLL_TRANSACTION_LIMIT
    INIT_BACKFILL_LIMIT = SystemConfig.INIT_BACKFILL_LIMIT
    
    # ==================== 资产更新设置 ====================
    ASSET_SYNC_MAX_RETRIES = SystemConfig.ASSET_SYNC_MAX_RETRIES
    ASSET_SYNC_RETRY_DELAY = SystemConfig.ASSET_SYNC_RETRY_DELAY
    PRICE_UPDATE_INTERVAL = SystemConfig.PRICE_UPDATE_INTERVAL
    
    # ==================== 资产过滤设置 ====================
    MIN_ASSET_DISPLAY_VALUE = SystemConfig.MIN_ASSET_DISPLAY_VALUE
    
    # ==================== 虚拟交易设置 ====================
    MY_PRIVATE_KEY = BaseConfig.MY_PRIVATE_KEY
    MY_WALLET_ADDRESS = BaseConfig.MY_WALLET_ADDRESS
    
    # === 滑点设置 ===
    SLIPPAGE_MAX_BPS = SystemConfig.SLIPPAGE_MAX_BPS
    SLIPPAGE_MIN_BPS = SystemConfig.SLIPPAGE_MIN_BPS
    
    # === 爆发模式设置 ===
    IDLE_INTERVAL = SystemConfig.IDLE_INTERVAL
    BURST_INTERVAL = SystemConfig.BURST_INTERVAL
    BURST_DURATION = SystemConfig.BURST_DURATION

    @staticmethod
    def validate():
        """启动前检查配置是否完整"""
        if not Config.HELIUS_API_KEY:
            raise ValueError("❌ 缺少 HELIUS_API_KEY，请检查 .env 文件")
        if not Config.TARGET_WALLET:
            raise ValueError("❌ 缺少 TARGET_WALLET，请检查 .env 文件")
        
        print("✅ 配置检查通过")
        return True

    # ==================== 价格查询设置 ====================
    PRICE_SOURCE_STRATEGY = SystemConfig.PRICE_SOURCE_STRATEGY
    PRICE_SOURCES = SystemConfig.PRICE_SOURCES
    PRICE_SOURCE_TIMEOUT = SystemConfig.PRICE_SOURCE_TIMEOUT

    # ==================== 交易策略设置 ====================
    ENABLE_FILTERING = TradingConfig.ENABLE_FILTERING
    MIN_LIQUIDITY = TradingConfig.MIN_LIQUIDITY
    MIN_MARKET_CAP = TradingConfig.MIN_MARKET_CAP
    MAX_MARKET_CAP = TradingConfig.MAX_MARKET_CAP
    BLACKLIST_TOKENS = TradingConfig.BLACKLIST_TOKENS
    ALLOW_VIRTUAL_DEPOSIT = TradingConfig.ALLOW_VIRTUAL_DEPOSIT
    ALLOW_VIRTUAL_WITHDRAWAL = TradingConfig.ALLOW_VIRTUAL_WITHDRAWAL
    
    # ==================== 风险控制设置 ====================
    STOP_LOSS_PERCENT = RiskConfig.STOP_LOSS_PERCENT
    TAKE_PROFIT_PERCENT = RiskConfig.TAKE_PROFIT_PERCENT
    MAX_HOLD_TIME = RiskConfig.MAX_HOLD_TIME
    MAX_DRAWDOWN = RiskConfig.MAX_DRAWDOWN
    
    # ==================== 会话管理设置 ====================
    VIRTUAL_SESSION_AUTO_BACKUP = SystemConfig.VIRTUAL_SESSION_AUTO_BACKUP
    VIRTUAL_SESSION_PREFIX = SystemConfig.VIRTUAL_SESSION_PREFIX
    ENABLE_BALANCE_HISTORY = SystemConfig.ENABLE_BALANCE_HISTORY
    ENABLE_SESSION_METADATA = SystemConfig.ENABLE_SESSION_METADATA

    # ==================== 策略配置（未来扩展）====================
    ENABLE_RECOVER_PRINCIPAL = StrategyConfig.ENABLE_RECOVER_PRINCIPAL
    RECOVER_PRINCIPAL_THRESHOLD = StrategyConfig.RECOVER_PRINCIPAL_THRESHOLD
    ENABLE_TRAILING_STOP = StrategyConfig.ENABLE_TRAILING_STOP
    TRAILING_STOP_PERCENT = StrategyConfig.TRAILING_STOP_PERCENT
    ENABLE_PARTIAL_TAKE_PROFIT = StrategyConfig.ENABLE_PARTIAL_TAKE_PROFIT
    PARTIAL_LEVELS = StrategyConfig.PARTIAL_LEVELS
    
    # ==================== 仓位管理 ====================
    USE_FIXED_AMOUNT = TradingConfig.USE_FIXED_AMOUNT
    FIXED_TRADE_AMOUNT = TradingConfig.FIXED_TRADE_AMOUNT
    
    # ==================== 更新风控配置 ====================
    MAX_CONSECUTIVE_LOSSES = RiskConfig.MAX_CONSECUTIVE_LOSSES
    STOP_AFTER_TRIGGER_HOURS = RiskConfig.STOP_AFTER_TRIGGER_HOURS
    ENABLE_POSITION_STOP_LOSS = RiskConfig.ENABLE_POSITION_STOP_LOSS
    ENABLE_POSITION_TAKE_PROFIT = RiskConfig.ENABLE_POSITION_TAKE_PROFIT
