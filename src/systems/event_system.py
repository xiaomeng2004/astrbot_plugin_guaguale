# systems/event_system.py
import random
from typing import Callable, Dict

class EventSystem:
    def __init__(self):
        self.events = self._load_default_events()

    def _load_default_events(self) -> Dict:
        return {
            'jackpot': {
                'name': '天降横财',
                'weight': 2,
                'handler': self._handle_jackpot
            },
            'double_next': {
                'name': '暴击时刻',
                'weight': 5,
                'handler': self._handle_double
            },
            'ghost': {
                'name': '大慈善家',
                'weight': 3,
                'handler': self._handle_ghost
            }
        }
    
    def register_event(self, name: str, handler: Callable, weight: int):
        self.events[name] = {
            'name': name,
            'handler': handler,
            'weight': weight
        }
    
    def trigger_random_event(self, base_reward: int) -> Dict:
        total_weight = sum(e['weight'] for e in self.events.values())
        rand = random.uniform(0, total_weight)
        
        current = 0
        for event in self.events.values():
            current += event['weight']
            if rand <= current:
                return event['handler'](base_reward)
        return {
            'type': '事件获取错误',
            'message': f"额外获得 {0}元",
            'delta': 0    
        }
    
    def _handle_jackpot(self, base_reward: int) -> Dict:
        bonus = random.randint(100, 200)
        return {
            'type': 'jackpot',
            'message': f"💎 天降横财，额外获得 {bonus}元",
            'delta': bonus
        }
    
    def _handle_double(self, base_reward: int) -> Dict:
        return {
            'type': 'double',
            'message': "🔥 暴击时刻，收益翻倍！",
            'delta': base_reward
        }
    
    def _handle_ghost(self, base_reward: int) -> Dict:
        return {
            'type': 'ghost',
            'message': "❤️ 大慈善家，收益全部捐出",
            'delta': base_reward * (-1)
        }