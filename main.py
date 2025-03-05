from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.all import *
import sqlite3
import random
from datetime import datetime, timezone
import json
from typing import Optional, Dict, List

from collections import defaultdict



class ScratchServer:
    def __init__(self, db_path='./data/scratch.db'):
        self.db_path = db_path
        
        # 彩票配置
        self.prizes = [0, 5, 10, 20, 50, 100]       # 可能开出的价值
        self.weights = [70, 15, 10, 3, 1.6, 0.4]    #相应概率 %
        self.cost = 25                              #每张票价   每张刮七个  中奖期望在24.85 元  爽死狗群友
        self.max_daily_scratch = 10                 # 每日限制次数

         # 新增抢劫配置
        self.rob_cooldown = 300         # 抢劫冷却时间（秒）
        self.rob_success_rate = 35      # 成功率%
        self.rob_base_amount = 30       # 基础抢劫金额
        self.rob_max_ratio = 0.2        # 最大可抢对方余额的20%
        self.rob_penalty = 30           # 失败赔偿金额

        self._init_db()


    def _init_db(self):
        """初始化数据库并添加新字段"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS users
                         (user_id TEXT PRIMARY KEY,
                          nickname TEXT,
                          balance INTEGER DEFAULT 100,
                          last_sign_date DATE,
                          last_scratch_date DATE,
                          daily_scratch_count INTEGER DEFAULT 0)''')
            # 尝试添加可能缺失的字段
            try:
                conn.execute('ALTER TABLE users ADD COLUMN last_scratch_date DATE;')
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute('ALTER TABLE users ADD COLUMN daily_scratch_count INTEGER DEFAULT 0;')
            except sqlite3.OperationalError:
                pass
            # 新增抢劫时间字段
            try:
                conn.execute('ALTER TABLE users ADD COLUMN last_rob_time INTEGER;')
            except sqlite3.OperationalError:
                pass    



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
        
        today = datetime.now(tz=timezone.utc).date()
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
        """带每日次数限制的游戏逻辑"""
        with sqlite3.connect(self.db_path) as conn:
            conn.isolation_level = 'IMMEDIATE'  # 开启事务
            cur = conn.cursor()
            
            try:
                # 获取并锁定用户数据
                user = cur.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
                if not user:
                    return {'success': False, 'msg': '用户不存在'}
                
                user_dict = {
                    'balance': user[2],
                    'last_scratch_date': user[4],
                    'daily_scratch_count': user[5] or 0
                }

                # 检查余额
                if user_dict['balance'] < self.cost:
                    return {'success': False, 'msg': '余额不足'}

                # 检查次数限制
                today = datetime.now(tz=timezone.utc).date()
                last_date = (datetime.strptime(user_dict['last_scratch_date'], '%Y-%m-%d').date()
                            if user_dict['last_scratch_date'] else None)
                
                if last_date == today:
                    if user_dict['daily_scratch_count'] >= self.max_daily_scratch:
                        return {'success': False, 'msg': '今日次数已用完'}
                    new_count = user_dict['daily_scratch_count'] + 1
                else:
                    new_count = 1

                # 生成彩票结果
                ticket = self.generate_ticket()
                reward = sum(ticket)
                net_gain = reward - self.cost
                new_balance = user_dict['balance'] + net_gain

                # 更新数据库
                cur.execute('''UPDATE users SET
                            balance = ?,
                            last_scratch_date = ?,
                            daily_scratch_count = ?
                            WHERE user_id = ?''',
                            (new_balance, today.isoformat(), new_count, user_id))
                
                conn.commit()
                return {
                    'success': True,
                    'balance': new_balance,
                    'ticket': ticket,
                    'reward': reward,
                    'net_gain': net_gain,
                    'msg': f"获得 {reward}元 {'(盈利)' if net_gain > 0 else '(亏损)'}"
                }

            except Exception as e:
                conn.rollback()
                return {'success': False, 'msg': '系统错误'}
    
    def rob_balance(self, robber_id: str, victim_id: str) -> dict:
        """
        抢劫逻辑核心方法
        返回格式:
        {
            "success": bool,
            "msg": str,
            "balance": int,      # 抢劫者最新余额
            "stolen": int,       # 实际抢到金额
            "cooldown": int      # 剩余冷却时间
        }
        """
        if robber_id == victim_id:
            return {"success": False, "msg": "不能抢劫自己"}

        with sqlite3.connect(self.db_path) as conn:
            conn.isolation_level = 'IMMEDIATE'
            cur = conn.cursor()

            try:
                # 获取抢劫者信息（带行锁）
                robber = cur.execute(
                    'SELECT balance, last_rob_time FROM users WHERE user_id = ?',
                    (robber_id,)
                ).fetchone()
                if not robber:
                    return {"success": False, "msg": "抢劫者未注册"}
                
                # 检查冷却时间
                current_time = int(datetime.now(tz=timezone.utc).timestamp())
                last_rob_time = robber[1] or 0
                cooldown_left = self.rob_cooldown - (current_time - last_rob_time)
                
                if cooldown_left > 0:
                    return {
                        "success": False,
                        "msg": f"抢劫技能冷却中（剩余{cooldown_left}秒）",
                        "cooldown": cooldown_left
                    }

                # 获取受害者信息（带行锁）
                victim = cur.execute(
                    'SELECT balance FROM users WHERE user_id = ?',
                    (victim_id,)
                ).fetchone()
                if not victim:
                    return {"success": False, "msg": "受害者不存在"}
                
                victim_balance = victim[0]
                if victim_balance <= 0:
                    return {"success": False, "msg": "对方是个穷光蛋"}

                # 计算可抢金额
                steal_amount = min(
                    self.rob_base_amount + int(victim_balance * random.uniform(0.1, self.rob_max_ratio)),
                    victim_balance
                )
                
                # 判断抢劫是否成功
                is_success = random.randint(1, 100) <= self.rob_success_rate
                
                if is_success:
                    # 抢劫成功逻辑
                    # 转移金额
                    cur.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?',
                               (steal_amount, victim_id))
                    cur.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                               (steal_amount, robber_id))
                    msg = f"成功抢劫了 {steal_amount}元！"
                else:
                    # 抢劫失败逻辑
                    penalty = min(robber[0], self.rob_penalty)
                    cur.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?',
                               (penalty, robber_id))
                    steal_amount = -penalty
                    msg = f"抢劫失败，赔偿对方 {penalty}元！"

                # 更新抢劫时间
                cur.execute('UPDATE users SET last_rob_time = ? WHERE user_id = ?',
                           (current_time, robber_id))
                
                # 获取最新余额
                new_balance = cur.execute(
                    'SELECT balance FROM users WHERE user_id = ?',
                    (robber_id,)
                ).fetchone()[0]
                
                conn.commit()
                return {
                    "success": True,
                    "msg": msg,
                    "balance": new_balance,
                    "stolen": steal_amount,
                    "cooldown": self.rob_cooldown
                }

            except Exception as e:
                conn.rollback()
                return {"success": False, "msg": "系统错误：抢劫失败"}


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

        outputMsg = "刮刮乐游戏,快来试试运气吧：\n"
        outputMsg += "【刮刮乐】购买一张刮刮乐并刮开，计算得失\n"
        outputMsg += "【刮刮乐余额】查询当前余额\n"
        outputMsg += "【刮刮乐每日签到】获得100元\n"
        outputMsg += "【刮刮乐排行榜】获取全局排行榜（暂不分群统计）"
        outputMsg += "【打劫@XXX】抢对方余额，若失败需赔付"
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
        msg = "🏆 土豪排行榜 🏆\n"
        for item in global_rank['rankings']:
            msg += (f"{item['rank']}. {item['nickname']} : {item['balance']}元\n")
        
        if my_rank['success']:
            msg += (f"\n👤 您的排名: {my_rank['user_rank']}/{my_rank['total_users']}")
            msg+=(f"💰 当前余额: {my_rank['user_info']['balance']}元")
        
        yield event.plain_result(f"{msg}")


    @filter.command("打劫")
    async def rob_command(self, event: AstrMessageEvent):
        '''抢劫其他用户的余额'''
        robber_id = event.get_sender_id()
        robber_name = event.get_sender_name()
        for comp in event.message_obj.message:
            if isinstance(comp, At):
                victim_id = comp.qq
                break
        # 解析被抢者ID（适配@消息）
        
        if not victim_id:
            yield event.plain_result("请指定抢劫目标，例如：抢余额 @某人")
            return
            
        # victim_id = victim_id[0]
        victim_info = self.server._get_user(victim_id)
        if not victim_info:
            yield event.plain_result("受害者不存在")
            return
        
        # 执行抢劫
        result = self.server.rob_balance(robber_id, victim_id)
        
        # 构建响应消息
        if result['success']:
            msg = (
                f"🏴‍☠️ {robber_name} 对 {victim_info['nickname']} 发动了抢劫！\n"
                f"▸ {result['msg']}\n"
                f"▸ 当前余额：{result['balance']}元\n"
                f"⏳ 冷却时间：{result['cooldown']}秒"
            )
        else:
            msg = f"❌ 抢劫失败：{result['msg']}"
            
        yield event.plain_result(msg)