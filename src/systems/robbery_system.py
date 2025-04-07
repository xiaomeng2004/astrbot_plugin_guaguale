# systems/RobberySystem.py
from typing import Dict, List
from ..database.manager import DatabaseManager
from datetime import datetime, timezone

class RobberySystem:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.rob_cooldown = 30         # 抢劫冷却时间（秒）


    def rob_balance(self, robber_id: str, victim_id: str) -> dict:
        if robber_id == victim_id:
            return {"success": False, "msg": "不能抢劫自己"}
        
        # 在抢劫逻辑开始处添加
        protection = self.db.check_protection(victim_id)
        if protection:
            return {"success": False, "msg": "目标处于保护状态"}
        
        robber_info= self.db.get_user_info(robber_id)
        victim_info= self.db.get_user_info(victim_id)
        # 检查冷却时间
        current_time = int(datetime.now(tz=timezone.utc).timestamp())
        last_rob_time = robber_info['last_rob_time'] or 0
        cooldown_left = self.rob_cooldown - (current_time - last_rob_time)
        
        if cooldown_left > 0:
            return {
                "success": False,
                "msg": f"抢劫技能冷却中（剩余{cooldown_left}秒）",
                "cooldown": cooldown_left
            }
        
        return self.db.rob_balance(robber_id, victim_id)