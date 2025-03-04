from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

import sqlite3
import random
from datetime import datetime, timedelta
import json
from typing import Optional, Dict, List

class ScratchServer:
    def __init__(self, db_path='./data/plugins/astrbot_plugin_guaguale/scratch.db'):
        self.db_path = db_path
        self._init_db()
        
        # 彩票配置
        self.prizes = [0, 5, 10, 20, 50, 100]       # 可能开出的价值
        self.weights = [70, 15, 10, 3, 1.6, 0.4]    #相应概率 %
        self.cost = 25                              #每张票价   每张刮七个  中奖期望在24.85 元  爽死狗群友



    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS users
                         (user_id TEXT PRIMARY KEY,
                          nickname TEXT,
                          balance INTEGER DEFAULT 100,
                          last_sign_date DATE)''')

    def _get_user(self, user_id: str) -> Optional[dict]:
        """获取用户信息"""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cur.fetchone()
            if row:
                return {
                    'user_id': row[0],
                    'nickname': row[1],
                    'balance': row[2],
                    'last_sign_date': row[3]
                }
            return None

    def _update_balance(self, user_id: str, amount: int):
        """更新用户余额"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                        (amount, user_id))
            conn.commit()

    def register_user(self, user_id: str, nickname: str):
        """注册新用户"""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute('INSERT INTO users (user_id, nickname) VALUES (?, ?)',
                            (user_id, nickname))
                return True
            except sqlite3.IntegrityError:
                return False

    def get_balance(self, user_id: str) -> dict:
        """查询余额"""
        user = self._get_user(user_id)
        if not user:
            return {'success': False, 'msg': '用户不存在'}
        return {'success': True, 'balance': user['balance']}

    def sign_in(self, user_id: str) -> dict:
        """每日签到"""
        user = self._get_user(user_id)
        if not user:
            return {'success': False, 'msg': '用户不存在'}
        
        today = datetime.now().date()
        last_sign = user['last_sign_date']
        
        if last_sign and datetime.strptime(last_sign, '%Y-%m-%d').date() == today:
            return {'success': False, 'msg': '今日已签到'}
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''UPDATE users 
                         SET balance = balance + 100,
                             last_sign_date = ?
                         WHERE user_id = ?''',
                         (today.isoformat(), user_id))
            conn.commit()
        return {'success': True, 'balance': user['balance'] + 100}

    def generate_ticket(self) -> List[int]:
        """生成刮刮乐"""
        return random.choices(self.prizes, weights=self.weights, k=7)

    def play_game(self, user_id: str) -> dict:
        """
        开始游戏并立即结算
        返回格式:
        {
            "success": bool,
            "balance": int,
            "ticket": List[int],
            "reward": int,
            "msg": str
        }
        """
        user = self._get_user(user_id)
        if not user:
            return {'success': False, 'msg': '用户不存在'}
        
        if user['balance'] < self.cost:
            return {'success': False, 'msg': '余额不足'}
        
        # 生成彩票
        ticket = self.generate_ticket()
        reward = sum(ticket)
        
        # 更新余额
        self._update_balance(user_id, reward - self.cost)
        
        # 获取最新余额
        new_balance = user['balance'] + (reward - self.cost)
        
        return {
            'success': True,
            'balance': new_balance,
            'ticket': ticket,
            'reward': reward,
            'net_gain': reward - self.cost,
            'msg': f"获得 {reward}元 {'(盈利)' if reward > self.cost else '(亏损)'}"
        }
    
    def get_rankings(self, top_n: int = 10) -> dict:
        """
        获取全局排行榜
        返回格式:
        {
            "success": bool,
            "rankings": [
                {
                    "rank": int,
                    "nickname": str,
                    "balance": int,
                    "user_id": str
                },
                ...
            ]
        }
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute('''
                    SELECT user_id, nickname, balance 
                    FROM users 
                    ORDER BY balance DESC, user_id ASC
                    LIMIT ?
                ''', (top_n,))
                
                rankings = []
                for rank, row in enumerate(cur.fetchall(), start=1):
                    rankings.append({
                        "rank": rank,
                        "nickname": row['nickname'],
                        "balance": row['balance'],
                        "user_id": row['user_id']
                    })
                
                return {"success": True, "rankings": rankings}
        
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_user_ranking(self, user_id: str) -> dict:
        """
        获取用户个人排名信息
        返回格式:
        {
            "success": bool,
            "user_rank": int,
            "total_users": int,
            "user_info": {
                "nickname": str,
                "balance": int
            }
        }
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 获取用户信息
                user_info = conn.execute('''
                    SELECT nickname, balance 
                    FROM users 
                    WHERE user_id = ?
                ''', (user_id,)).fetchone()
                
                if not user_info:
                    return {"success": False, "error": "用户不存在"}
                
                # 计算用户排名
                rank = conn.execute('''
                    SELECT COUNT(*) + 1 as rank 
                    FROM users 
                    WHERE balance > ?
                ''', (user_info[1],)).fetchone()[0]
                
                # 获取总用户数
                total_users = conn.execute('''
                    SELECT COUNT(*) FROM users
                ''').fetchone()[0]
                
                return {
                    "success": True,
                    "user_rank": rank,
                    "total_users": total_users,
                    "user_info": {
                        "nickname": user_info[0],
                        "balance": user_info[1]
                    }
                }
        
        except Exception as e:
            return {"success": False, "error": str(e)}




@register("guaguale", "WaterFeet", "刮刮乐插件，试试运气如何", "1.0.0", "https://github.com/waterfeet/astrbot_plugin_guaguale")
class MyPlugin(Star):
    server = ScratchServer()
    def __init__(self, context: Context):
        super().__init__(context)
        

    @filter.command("刮刮乐")
    async def guaguale_play(self, event: AstrMessageEvent):
        '''这是一个 刮刮乐 指令 用于抽一次刮刮乐''' 
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()
        # 自动注册用户
        if not self.server.get_balance(user_id)['success']:
            self.server.register_user(user_id, user_name)

        result = self.server.play_game(user_id)
        if result['success']:
            ticket_str = " ".join(f"{n}元" for n in result['ticket'])
            outputMsg =  f'''中奖结果：{ticket_str}\n净收益：{result['net_gain']}元\n余额：{result['balance']}元'''
        else:
            outputMsg = result['msg'] 
        yield event.plain_result(f"{outputMsg}")

    @filter.command("刮刮乐帮助")
    async def guaguale_help(self, event: AstrMessageEvent):
        '''这是一个 刮刮乐帮助 指令 用于查看刮刮乐指令''' 

        outputMsg = f("刮刮乐游戏,快来试试运气吧：\n【刮刮乐】购买一张刮刮乐并刮开，计算得失\n【刮刮乐余额】查询当前余额\n【刮刮乐每日签到】获得100元\n【刮刮乐排行榜】获取全局排行榜（暂不分群统计）")
        yield event.plain_result(f"{outputMsg}")    

    @filter.command("刮刮乐余额")
    async def guaguale_balance(self, event: AstrMessageEvent):
        '''这是一个 刮刮乐 余额 指令 用于查询余额''' 
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()
        # 自动注册用户
        if not self.server.get_balance(user_id)['success']:
            self.server.register_user(user_id, user_name)

        reset = self.server.get_balance(user_id)
        if reset["success"]:
            yield event.plain_result(f"{reset['balance']}")
        else:
            yield event.plain_result(f"{reset['msg']}")

    @filter.command("刮刮乐每日签到")
    async def guaguale_signin(self, event: AstrMessageEvent):
        '''这是一个 刮刮乐 每日签到 指令 用于每日签到获取100元''' 
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()
        # 自动注册用户
        if not self.server.get_balance(user_id)['success']:
            self.server.register_user(user_id, user_name)

        reset = self.server.sign_in(user_id)
        if reset["success"]:
            yield event.plain_result(f"{reset['balance']}")
        else:
            yield event.plain_result(f"{reset['msg']}")
   

    @filter.command("刮刮乐排行榜")
    async def guaguale_ranking(self, event: AstrMessageEvent):

        user_name = event.get_sender_name()
        user_id = event.get_sender_id()
        # 未注册用户
        if not self.server.get_balance(user_id)['success']:
            return
        
        # 获取全局排行榜
        global_rank = self.server.get_rankings(10)
        if not global_rank['success']:
            yield event.plain_result(f"获取排行榜失败")
            return
        
        # 获取个人排名
        my_rank = self.server.get_user_ranking(user_id)
        
        # 构建响应消息
        msg = "🏆 土豪排行榜 🏆"
        for item in global_rank['rankings']:
            msg += (f"{item['rank']}. {item['nickname']} : {item['balance']}元")
        
        if my_rank['success']:
            msg += (f"\n👤 您的排名: {my_rank['user_rank']}/{my_rank['total_users']}")
            msg+=(f"💰 当前余额: {my_rank['user_info']['balance']}元")
        
        yield event.plain_result(f"{msg}")

        # todu  好运卡   用户可以购买好运卡提升概率
