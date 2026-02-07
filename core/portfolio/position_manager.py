"""
持仓管理器

职责：
- 管理所有虚拟持仓
- 增加/减少持仓
- 计算盈亏
- 持久化存储
"""

import time
import logging
from typing import List, Optional, Dict
from core.data_models import Position

logger = logging.getLogger(__name__)


class PositionManager:
    """
    持仓管理器
    
    功能：
    - 管理所有持仓
    - 买入时增加持仓
    - 卖出时减少持仓并计算利润
    - 更新持仓价格
    - 持久化到storage
    """
    
    def __init__(self, storage):
        """
        初始化持仓管理器
        
        参数:
            storage: Storage - 存储器
        """
        self.storage = storage
        self.positions: Dict[str, Position] = {}  # {mint: Position对象}
        
        # 启动时加载持仓数据
        self._load()
        logger.info(f"✅ 持仓管理器初始化完成，已加载 {len(self.positions)} 个持仓")
    
    def add_position(self, mint: str, symbol: str, amount: float, cost: float):
        """
        增加持仓（买入）
        
        参数:
            mint: str - 代币地址
            symbol: str - 代币符号
            amount: float - 买入数量
            cost: float - 买入总成本（USD）
        
        逻辑：
        - 如果是新持仓：直接创建
        - 如果已有持仓：累加数量，重新计算平均成本
        """
        if amount <= 0:
            logger.warning(f"⚠️ 买入数量无效: {amount}")
            return
        
        current_time = int(time.time())
        cost_per_token = cost / amount  # 本次买入的单价
        
        if mint in self.positions:
            # 已有持仓，计算平均成本
            old_position = self.positions[mint]
            
            # 总成本 = 旧成本 + 新成本
            total_cost = old_position.total_cost + cost
            # 总数量 = 旧数量 + 新数量
            total_amount = old_position.amount + amount
            # 新的平均成本
            new_cost_basis = total_cost / total_amount
            
            # 更新持仓
            self.positions[mint] = Position(
                mint=mint,
                symbol=symbol,
                amount=total_amount,
                cost_basis=new_cost_basis,
                total_cost=total_cost,
                current_price=old_position.current_price,  # 保持当前价格
                unrealized_pnl=0.0,  # 稍后计算
                unrealized_pnl_percent=0.0,
                entry_time=old_position.entry_time,  # 保持原入场时间
                last_update_time=current_time
            )
            
            # 重新计算盈亏
            self._recalculate_pnl(mint)
            
            logger.info(
                f"📈 加仓 {symbol}: "
                f"+{amount:.4f} (总持仓 {total_amount:.4f}), "
                f"平均成本 ${new_cost_basis:.6f}"
            )
        else:
            # 新持仓
            self.positions[mint] = Position(
                mint=mint,
                symbol=symbol,
                amount=amount,
                cost_basis=cost_per_token,
                total_cost=cost,
                current_price=cost_per_token,  # 初始价格等于成本
                unrealized_pnl=0.0,
                unrealized_pnl_percent=0.0,
                entry_time=current_time,
                last_update_time=current_time
            )
            
            logger.info(
                f"🆕 新建持仓 {symbol}: "
                f"{amount:.4f} @ ${cost_per_token:.6f}"
            )
        
        # 保存到storage
        self._save()
    
    def reduce_position(self, mint: str, amount: float, exit_price: float) -> float:
        """
        减少持仓（卖出）
        
        参数:
            mint: str - 代币地址
            amount: float - 卖出数量
            exit_price: float - 卖出价格（USD/token）
        
        返回:
            float - 实现利润（USD），如果卖出失败返回0
        
        逻辑：
        - 检查持仓是否足够
        - 计算实现利润
        - 减少持仓数量（如果全部卖出则删除持仓）
        """
        if mint not in self.positions:
            logger.warning(f"⚠️ 持仓不存在: {mint}")
            return 0.0
        
        position = self.positions[mint]
        
        # 检查数量
        if amount > position.amount:
            logger.warning(
                f"⚠️ 卖出数量超过持仓: "
                f"尝试卖出 {amount:.4f}, 实际持有 {position.amount:.4f}"
            )
            return 0.0
        
        # 计算实现利润
        cost_basis = position.cost_basis
        profit_per_token = exit_price - cost_basis
        realized_pnl = profit_per_token * amount
        realized_pnl_percent = (profit_per_token / cost_basis) * 100 if cost_basis > 0 else 0
        
        logger.info(
            f"📉 卖出 {position.symbol}: "
            f"-{amount:.4f} @ ${exit_price:.6f}, "
            f"利润 ${realized_pnl:.2f} ({realized_pnl_percent:+.2f}%)"
        )
        
        # 更新持仓
        if amount >= position.amount:
            # 全部卖出，删除持仓
            del self.positions[mint]
            logger.info(f"🗑️ 清空持仓 {position.symbol}")
        else:
            # 部分卖出，减少数量
            new_amount = position.amount - amount
            new_total_cost = position.total_cost - (cost_basis * amount)
            
            self.positions[mint] = Position(
                mint=mint,
                symbol=position.symbol,
                amount=new_amount,
                cost_basis=cost_basis,  # 平均成本不变
                total_cost=new_total_cost,
                current_price=exit_price,  # 更新当前价格
                unrealized_pnl=0.0,  # 稍后计算
                unrealized_pnl_percent=0.0,
                entry_time=position.entry_time,
                last_update_time=int(time.time())
            )
            
            # 重新计算未实现盈亏
            self._recalculate_pnl(mint)
        
        # 保存到storage
        self._save()
        
        return realized_pnl
    
    def get_position(self, mint: str) -> Optional[Position]:
        """
        获取单个持仓
        
        参数:
            mint: str - 代币地址
        
        返回:
            Position - 持仓对象，如果不存在返回None
        """
        return self.positions.get(mint)
    
    def get_all_positions(self) -> List[Position]:
        """
        获取所有持仓
        
        返回:
            List[Position] - 持仓列表
        """
        return list(self.positions.values())
    
    def update_prices(self, price_dict: Dict[str, float]):
        """
        批量更新持仓价格
        
        参数:
            price_dict: dict - {mint: current_price_usd}
        
        用途：
        - 定期更新所有持仓的当前价格
        - 重新计算未实现盈亏
        """
        updated_count = 0
        
        for mint, current_price in price_dict.items():
            if mint in self.positions:
                position = self.positions[mint]
                
                # 更新价格
                self.positions[mint] = Position(
                    mint=position.mint,
                    symbol=position.symbol,
                    amount=position.amount,
                    cost_basis=position.cost_basis,
                    total_cost=position.total_cost,
                    current_price=current_price,
                    unrealized_pnl=0.0,  # 稍后计算
                    unrealized_pnl_percent=0.0,
                    entry_time=position.entry_time,
                    last_update_time=int(time.time())
                )
                
                # 重新计算盈亏
                self._recalculate_pnl(mint)
                updated_count += 1
        
        if updated_count > 0:
            logger.debug(f"🔄 更新了 {updated_count} 个持仓的价格")
            self._save()
    
    def calculate_total_value(self) -> float:
        """
        计算所有持仓的总价值
        
        返回:
            float - 总价值（USD）
        """
        total = 0.0
        for position in self.positions.values():
            total += position.amount * position.current_price
        return total
    
    def get_position_count(self) -> int:
        """获取持仓数量"""
        return len(self.positions)
    
    def has_position(self, mint: str) -> bool:
        """检查是否持有某个代币"""
        return mint in self.positions
    
    # ========== 内部辅助方法 ==========
    
    def _recalculate_pnl(self, mint: str):
        """
        重新计算单个持仓的盈亏
        
        参数:
            mint: str - 代币地址
        """
        if mint not in self.positions:
            return
        
        position = self.positions[mint]
        
        # 未实现盈亏 = (当前价格 - 成本价格) * 数量
        unrealized_pnl = (position.current_price - position.cost_basis) * position.amount
        
        # 未实现盈亏百分比
        if position.cost_basis > 0:
            unrealized_pnl_percent = ((position.current_price - position.cost_basis) / position.cost_basis) * 100
        else:
            unrealized_pnl_percent = 0.0
        
        # 更新持仓对象
        self.positions[mint] = Position(
            mint=position.mint,
            symbol=position.symbol,
            amount=position.amount,
            cost_basis=position.cost_basis,
            total_cost=position.total_cost,
            current_price=position.current_price,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_percent=unrealized_pnl_percent,
            entry_time=position.entry_time,
            last_update_time=position.last_update_time
        )
    
    def _save(self):
        """保存所有持仓到storage"""
        try:
            # 将Position对象转换为字典
            positions_dict = {}
            for mint, position in self.positions.items():
                positions_dict[mint] = {
                    'mint': position.mint,
                    'symbol': position.symbol,
                    'amount': position.amount,
                    'cost_basis': position.cost_basis,
                    'total_cost': position.total_cost,
                    'current_price': position.current_price,
                    'unrealized_pnl': position.unrealized_pnl,
                    'unrealized_pnl_percent': position.unrealized_pnl_percent,
                    'entry_time': position.entry_time,
                    'last_update_time': position.last_update_time
                }
            
            self.storage.save_positions(positions_dict)
            logger.debug(f"💾 持仓已保存 ({len(positions_dict)} 个)")
        
        except Exception as e:
            logger.error(f"❌ 保存持仓失败: {e}", exc_info=True)
    
    def _load(self):
        """从storage加载所有持仓"""
        try:
            positions_dict = self.storage.load_positions()
            
            # 将字典转换为Position对象
            for mint, data in positions_dict.items():
                self.positions[mint] = Position(
                    mint=data['mint'],
                    symbol=data['symbol'],
                    amount=data['amount'],
                    cost_basis=data['cost_basis'],
                    total_cost=data['total_cost'],
                    current_price=data['current_price'],
                    unrealized_pnl=data['unrealized_pnl'],
                    unrealized_pnl_percent=data['unrealized_pnl_percent'],
                    entry_time=data['entry_time'],
                    last_update_time=data['last_update_time']
                )
            
            if positions_dict:
                logger.debug(f"📂 加载了 {len(positions_dict)} 个持仓")
        
        except Exception as e:
            logger.error(f"❌ 加载持仓失败: {e}", exc_info=True)
            self.positions = {}
