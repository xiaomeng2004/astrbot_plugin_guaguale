# scratch_server.py
from datetime import datetime, timezone
from typing import List

from astrbot.api import logger
import random

# scratch_server.py（主入口，整合所有模块）
from .config.settings import ConfigManager
from .database.manager import DatabaseManager
from .systems.event_system import EventSystem
from .systems.shop_system import ShopSystem
from .systems.robbery_system import RobberySystem
# from .systems.robbery_system import RobberySystem

class ScratchServer:
    def __init__(self, db_path='./data/scratch.db', config=None):
        if config:
            # 如果传入了配置，使用传入的配置创建ConfigManager
            self.cfg_mgr = ConfigManager(external_config=config)
        else:
            # 否则使用默认的文件配置
            self.cfg_mgr = ConfigManager()
        
        # 初始化基础组件
        self._init_core_components()
        
        # 在配置加载后初始化其他系统，这样可以传入货币单位
        self.db_manager = DatabaseManager(db_path, currency_unit=self.cfg_mgr.currency_unit)
        self.event_system = EventSystem(currency_unit=self.cfg_mgr.currency_unit)
        self.shop_system = ShopSystem(self.db_manager)
        self.robbery_system = RobberySystem(self.db_manager)
        
        # 完成数据库和商店的初始化
        self.db_manager.initialize()
        self.db_manager.initialize_boss_account()
        self.shop_system._initialize_shop()
        
    def _init_core_components(self):
        """初始化核心组件"""
        self.cfg_mgr.initConfig()

    # 以下是游戏内部的方法
    def generate_ticket(self) -> List[int]:
        """生成刮刮乐"""
        return random.choices(self.cfg_mgr.prizes, weights=self.cfg_mgr.weights, k=self.cfg_mgr.num)

    # 以下是保持原有接口的方法（委托给各子系统）
    def isUseridExist(self, user_id: str):
        return self.db_manager.isUseridExist(user_id)
    
    def register_user(self, user_id: str, nickname: str):
        return self.db_manager.add_register_user(user_id, nickname)

    def get_balance(self, user_id: str):
        return self.db_manager.get_balance(user_id)
    
    def get_user_info(self, user_id: str):
        return self.db_manager.get_user_info(user_id)

    def sign_in(self, user_id: str):
        user_info= self.db_manager.get_user_info(user_id)
        today = datetime.now(tz=timezone.utc).date()
        last_sign = user_info['last_sign_date']
        
        if last_sign and datetime.strptime(last_sign, '%Y-%m-%d').date() == today:
            return {'success': False, 'msg': '今日已签到'}
        
        self.db_manager.sign_in(user_id, 150)
        return {'success': True, 'msg': f"签到成功，当前余额{self.db_manager.get_balance(user_id)['balance']}{self.cfg_mgr.currency_unit}"}  

    def play_game(self, user_id: str):
        """刮奖"""
        result_info= self.db_manager.get_user_info(user_id)
        user_balance = 0
        if result_info:
            user_balance = result_info['balance']
        else:
            outputMsg = f"用户信息错误"
            return outputMsg
        
        if(user_balance < self.cfg_mgr.cost):
            outputMsg = f"刮刮乐余额不足"
            return outputMsg
        
        
        # 检查次数限制
        today = datetime.now(tz=timezone.utc).date()
        last_date = (datetime.strptime(result_info['last_scratch_date'], '%Y-%m-%d').date()
                    if result_info['last_scratch_date'] else None)
        
        if last_date == today:
            if result_info['daily_scratch_count'] >= self.cfg_mgr.max_daily_scratch and self.cfg_mgr.max_daily_scratch > 0:
                return {'success': False, 'msg': '今日次数已用完'}
            new_count = result_info['daily_scratch_count'] + 1
        else:
            new_count = 1

        # 生成彩票结果
        ticket = self.generate_ticket()
        reward = sum(ticket)

        # 在计算reward后添加事件处理
        original_reward = reward
        event_result = None
        
        # 事件处理（新增异常捕获）
        try:
            if random.random() <= self.cfg_mgr.event_chance:
                event = self.event_system.trigger_random_event(original_reward)
                reward = original_reward + event['delta']
                event_result = {'name': f"⚡ 触发事件:{event['message']}", 'detail': f" 最终收益: {reward}"}
            else:
                event_result = None    
        except Exception as e:
            logger.error(f"Event handling error: {e}")
            event_result = {'name': '⚡ 系统异常', 'detail': '事件处理失败'}            
            reward = original_reward  # 回退到原始奖励
        # 更新最终收益（确保事件影响后的计算）
        net_gain = reward - self.cfg_mgr.cost
        new_balance = result_info['balance'] + net_gain
        self.db_manager.update_balance(user_id, net_gain)
        self.db_manager.update_boss_balance(net_gain)
        self.db_manager.update_scratch_count(user_id, new_count, today.isoformat())

        ticket_str = " ".join(f"{n}{self.cfg_mgr.currency_unit}" for n in ticket)
        outputMsg = f"刮奖结果：{ticket_str}\n"
        
        if event_result:
            outputMsg += f"✨ {event_result['name']} ✨\n{event_result['detail']}\n"

        outputMsg += f"净收益：{net_gain}{self.cfg_mgr.currency_unit}\n余额：{new_balance}{self.cfg_mgr.currency_unit}"
        return outputMsg

    def update_nickname(self, *args, **kwargs): 
        return self.db_manager.update_nickname(*args, **kwargs)

    def get_rankings(self, *args, **kwargs):
        return self.db_manager.get_rankings(*args, **kwargs)

    def get_user_ranking(self, *args, **kwargs):
        return self.db_manager.get_user_ranking(*args, **kwargs)

    def get_shop_items(self, *args, **kwargs):
        return self.shop_system.get_shop_items(*args, **kwargs)
    
    def rob_balance(self, *args, **kwargs):
        return self.robbery_system.rob_balance(*args, **kwargs)

    def purchase_item(self, *args, **kwargs):
        return self.shop_system.purchase_item(*args, **kwargs)

    def get_user_inventory(self, *args, **kwargs):
        return self.db_manager.get_user_inventory(*args, **kwargs)

    def use_item(self, *args, **kwargs):
        return self.db_manager.use_item(*args, **kwargs)