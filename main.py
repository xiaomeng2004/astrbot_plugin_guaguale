import re
import time
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
        self.weights = [70, 15, 10, 3, 1.6, 0.4]    # 相应概率 %
        self.cost = 25                              # 每张票价   每张刮七个  中奖期望在24.85 元  爽死狗群友
        self.max_daily_scratch = 10                 # 每日限制次数

         # 新增抢劫配置
        self.rob_cooldown = 300         # 抢劫冷却时间（秒）
        self.rob_success_rate = 35      # 成功率%
        self.rob_base_amount = 30       # 基础抢劫金额
        self.rob_max_ratio = 0.2        # 最大可抢对方余额的20%
        self.rob_penalty = 50           # 失败赔偿金额

        # 新增事件配置
        self.event_chance = 15         # 触发概率15%

        self.events = {
            'jackpot': {
                'name': '💎 天降横财', 
                'prob': 2,
                'effect': lambda uid,reward: random.randint(100, 200)  # 使用参数uid
            },
            'double_next': {
                'name': '🔥 暴击时刻', 
                'prob': 5,
                'effect': lambda uid,reward: reward * 2  # 本次收益双倍
            },
            'ghost': {
                'name': '👻 见鬼了！',
                'prob': 3,
                'effect': lambda uid,reward: -abs(reward)  # 反转收益
            },
        }

        self.ITEM_EFFECTS = {
            1: {  # 改名卡
                'use': lambda user_id: 0,  # 什么都不用做 单独处理
            },
            2: {  # 刮卡券
                'effect': lambda user_id: self._add_scratch_chance(user_id, 5)
            },
            3: {  # 护身符
                'effect': lambda user_id: self._add_protection(user_id, 86400)  # 24小时
            }
        }
        self._init_db()

        self.bossname = '水脚脚'
        self._init_boss()  # 新增老板初始化

        # 初始化商店商品
        self.default_items = [
            (1, "改名卡", 50, "修改你的昵称", 999),
            (2, "刮卡券", 300, "额外增加5次刮卡次数", 99),
            (3, "护身符", 1000, "24小时防抢劫保护", 10)
        ]

        self._init_shop()

    def use_item(self, user_id: str, item_id: int) -> dict:
        """使用道具"""
        with sqlite3.connect(self.db_path) as conn:
            conn.isolation_level = 'IMMEDIATE'
            cur = conn.cursor()
            
            try:
                # 验证道具存在且可用
                item = cur.execute(
                    'SELECT quantity FROM user_inventory WHERE user_id=? AND item_id=?',
                    (user_id, item_id)
                ).fetchone()
                
                if not item or item[0] < 1:
                    return {'success': False, 'msg': '道具不存在或数量不足'}
                
                # 减少库存
                cur.execute('''
                    UPDATE user_inventory SET quantity = quantity - 1 
                    WHERE user_id=? AND item_id=?
                ''', (user_id, item_id))
                
                # 执行道具效果
                effect = self.ITEM_EFFECTS.get(item_id)
                if not effect:
                    return {'success': False, 'msg': '无效的道具'}
                conn.commit()
                if 'effect' in effect:
                    result = effect['effect'](user_id)
                    return result
                if 'use' in effect:
                    return {'success': True, 'msg': ''}
                    
                return {'success': False, 'msg': '道具功能暂未实现'}
                
            except Exception as e:
                conn.rollback()
                logger.error(f"使用道具失败: {str(e)}")
                return {'success': False, 'msg': '使用道具失败'}

    # 补充相关功能方法
    def _add_scratch_chance(self, user_id: str, count: int):
        """增加刮卡次数"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE users SET daily_scratch_count = daily_scratch_count - ?
                WHERE user_id = ?
            ''', (count, user_id))
            conn.commit()
        return {'success': True, 'msg': f"成功增加{count}次刮卡机会"}

    def _check_protection(self, user_id: str) -> bool:
        """检查用户是否处于保护状态（同时清理过期记录）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                current_time = int(time.time())
                
                # 先清理过期记录
                conn.execute('DELETE FROM user_protection WHERE expire_time < ?', (current_time,))
                
                # 检查剩余保护
                protected = conn.execute(
                    'SELECT expire_time FROM user_protection WHERE user_id = ?',
                    (user_id,)
                ).fetchone()
                
                return protected is not None and protected[0] > current_time
                
        except Exception as e:
            logger.error(f"保护检查失败: {str(e)}")
            return False

    def _add_protection(self, user_id: str, duration: int):
        """添加保护（duration单位：秒）"""
        try:
            expire_time = int(time.time()) + duration
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO user_protection 
                    (user_id, expire_time) VALUES (?, ?)
                ''', (user_id, expire_time))
                conn.commit()
            return {'success': True, 'msg': f"保护卡使用成功"}
        except Exception as e:
            logger.error(f"添加保护失败: {str(e)}")
            return {'success': False, 'msg': f"保护卡使用失败"}



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
            # 新增商店表
            conn.execute('''CREATE TABLE IF NOT EXISTS shop_items
                        (item_id INTEGER PRIMARY KEY,
                        item_name TEXT,
                        price INTEGER,
                        description TEXT,
                        stock INTEGER)''')
            
            # 新增用户库存表
            conn.execute('''CREATE TABLE IF NOT EXISTS user_inventory
                        (user_id TEXT,
                        item_id INTEGER,
                        quantity INTEGER,
                        PRIMARY KEY (user_id, item_id))''')   
            conn.execute('''CREATE TABLE IF NOT EXISTS user_protection
                 (user_id TEXT PRIMARY KEY,
                  expire_time INTEGER)''')

    def _init_boss(self):
        """初始化老板账户"""
        boss_id = "boss"
        with sqlite3.connect(self.db_path) as conn:
            # 如果不存在则创建老板账户
            conn.execute('''
                INSERT OR IGNORE INTO users 
                (user_id, nickname, balance) 
                VALUES (?, ?, ?)
            ''', (boss_id, "💰 系统老板"+ self.bossname, 10000))
            conn.commit()

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

                # 在计算reward后添加事件处理
                original_reward = reward
                event_result = None
                
                # 事件处理（新增异常捕获）
                event_result = None
                try:
                    if random.randint(1, 100) <= self.event_chance:
                        event = self._select_random_event()
                        effect_output = event['effect'](user_id, reward)  # 传入当前用户ID
                        
                        # 处理不同类型事件
                        if event['name'] == '💎 天降横财':
                            reward += effect_output
                            event_result = event | {'detail': f"额外获得 {effect_output}元"}
                        elif event['name'] == '🔥 暴击时刻':
                            reward = effect_output
                            event_result = event | {'detail': f"本次收益翻倍！获得 {effect_output}元"}
                        # elif event['name'] == '🔄 乾坤大挪移':
                        #     event_result = event | {'detail': effect_output}
                        elif event['name'] == '👻 见鬼了！':
                            reward = effect_output
                            event_result = event | {'detail': "收益被鬼吃掉啦！"}
                    else:
                        event_result = None    
                except Exception as e:
                    logger.error(f"Event handling error: {e}")
                    event_result = {'name': '⚡ 系统异常', 'detail': '事件处理失败'}            
                    reward = original_reward  # 回退到原始奖励
                # 更新最终收益（确保事件影响后的计算）
                net_gain = reward - self.cost
                new_balance = user_dict['balance'] + net_gain
                
                # 更新玩家数据
                cur.execute('''UPDATE users SET
                            balance = ?,
                            last_scratch_date = ?,
                            daily_scratch_count = ?
                            WHERE user_id = ?''',
                            (new_balance, today.isoformat(), new_count, user_id))
                # 更新老板余额（反向操作）
                cur.execute('UPDATE users SET balance = balance - ? WHERE user_id = "boss"',
                   (net_gain,))
                conn.commit()
                return {
                    'success': True,
                    'balance': new_balance,
                    'ticket': ticket,
                    'net_gain': net_gain,
                    'event': event_result,
                    'original_reward': original_reward,
                    'final_reward': reward,
                    'msg': f"获得 {reward}元 {'(盈利)' if net_gain > 0 else '(亏损)'}"
                }
            except sqlite3.Error as e:
                return {'success': False, 'msg': '数据库错误'}
    
    def update_nickname(self, user_id: str, new_nickname: str) -> dict:
        """更新用户昵称"""
        # 清理前后空格
        new_nickname = new_nickname.strip()
        
        # 验证基础格式
        if len(new_nickname) < 2 or len(new_nickname) > 10:
            return {'success': False, 'msg': '昵称长度需为2-10个字符'}
        if not re.match(r'^[\w\u4e00-\u9fa5]+$', new_nickname):
            return {'success': False, 'msg': '昵称仅支持中英文、数字和下划线'}
        
        with sqlite3.connect(self.db_path) as conn:
            conn.isolation_level = 'IMMEDIATE'
            cur = conn.cursor()
            
            try:
                # 检查昵称是否已存在
                existing = cur.execute(
                    'SELECT user_id FROM users WHERE nickname = ?',
                    (new_nickname,)
                ).fetchone()
                
                if existing and existing[0] != user_id:
                    return {'success': False, 'msg': '昵称已被其他用户使用'}
                
                # 执行更新
                cur.execute(
                    'UPDATE users SET nickname = ? WHERE user_id = ?',
                    (new_nickname, user_id)
                )
                
                if cur.rowcount == 0:
                    return {'success': False, 'msg': '用户不存在'}
                    
                conn.commit()
                return {'success': True, 'msg': '昵称修改成功'}
                
            except Exception as e:
                conn.rollback()
                logger.error(f"更新昵称失败: {str(e)}")
                return {'success': False, 'msg': '昵称更新失败'}


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
        
        # 在抢劫逻辑开始处添加
        protection = self._check_protection(victim_id)
        if protection:
            return {"success": False, "msg": "目标处于保护状态"}

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
                    cur.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', # 抢劫者扣钱
                    (penalty, robber_id))
                    cur.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', # 受害者加钱
                    (penalty, victim_id))
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

    def _select_random_event(self):
        """加权随机选择事件"""
        total = sum(e['prob'] for e in self.events.values())
        r = random.uniform(0, total)
        upto = 0
        for event in self.events.values():
            if upto + event['prob'] >= r:
                return event
            upto += event['prob']
        return list(self.events.values())[0]

    def _init_shop(self):
        """初始化商店商品"""
        with sqlite3.connect(self.db_path) as conn:
            # 插入或更新默认商品
            for item in self.default_items:
                conn.execute('''
                    INSERT OR REPLACE INTO shop_items 
                    (item_id, item_name, price, description, stock)
                    VALUES (?, ?, ?, ?, ?)
                ''', item)
            conn.commit()

    def get_shop_items(self):
        """获取商店商品列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute('SELECT * FROM shop_items ORDER BY item_id')
                return {
                    "success": True,
                    "items": [dict(row) for row in cur.fetchall()]
                }
        except Exception as e:
            logger.error(f"获取商品列表失败: {str(e)}")
            return {
                "success": False,
                "error": "获取商品列表失败，请稍后重试"
            }
            
    def purchase_item(self, user_id: str, item_id: int):
        """购买商品逻辑"""
        with sqlite3.connect(self.db_path) as conn:
            conn.isolation_level = 'IMMEDIATE'
            cur = conn.cursor()
            
            try:
                # 获取商品信息
                item = cur.execute(
                    'SELECT * FROM shop_items WHERE item_id = ?',
                    (item_id,)
                ).fetchone()
                
                if not item:
                    return {'success': False, 'msg': '商品不存在'}
                    
                # 检查用户余额
                user_balance = cur.execute(
                    'SELECT balance FROM users WHERE user_id = ?',
                    (user_id,)
                ).fetchone()[0]
                
                if user_balance < item[2]:
                    return {'success': False, 'msg': '余额不足'}
                
                # 更新库存和余额
                cur.execute('UPDATE shop_items SET stock = stock - 1 WHERE item_id = ?', (item_id,))
                cur.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (item[2], user_id))
                cur.execute('''INSERT OR REPLACE INTO user_inventory 
                             VALUES (?, ?, COALESCE((SELECT quantity FROM user_inventory 
                             WHERE user_id = ? AND item_id = ?), 0) + 1)''',
                             (user_id, item_id, user_id, item_id))
                
                # 转账给老板
                cur.execute('UPDATE users SET balance = balance + ? WHERE user_id = "boss"', (item[2],))
                
                conn.commit()
                return {'success': True, 'item_name': item[1], 'balance': user_balance - item[2]}
                
            except Exception as e:
                conn.rollback()
                return {'success': False, 'msg': '购买失败'}
    def get_user_inventory(self, user_id: str) -> dict:
        """获取用户库存"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute('''
                    SELECT i.item_id, i.item_name, i.description, inv.quantity 
                    FROM user_inventory inv
                    JOIN shop_items i ON inv.item_id = i.item_id
                    WHERE inv.user_id = ?
                ''', (user_id,))
                
                items = []
                for row in cur.fetchall():
                    items.append({
                        "id": row['item_id'],
                        "name": row['item_name'],
                        "desc": row['description'],
                        "quantity": row['quantity']
                    })
                    
                return {'success': True, 'items': items}
                
        except Exception as e:
            logger.error(f"获取库存失败: {str(e)}")
            return {'success': False, 'error': '获取库存失败'}


@register("guaguale", "WaterFeet", "刮刮乐插件，试试运气如何", "1.0.0", "https://github.com/waterfeet/astrbot_plugin_guaguale")
class MyPlugin(Star):
    server = ScratchServer()
    def __init__(self, context: Context):
        super().__init__(context)
        self.admins = self._load_admins()  # 加载管理员列表
    def _load_admins(self):
        """加载管理员列表"""
        try:
            with open(os.path.join('data', 'cmd_config.json'), 'r', encoding='utf-8-sig') as f:
                config = json.load(f)
                return config.get('admins_id', [])
        except Exception as e:
            self.context.logger.error(f"加载管理员列表失败: {str(e)}")
            return []
        
    def is_admin(self, user_id):
        """检查用户是否为管理员"""
        return str(user_id) in self.admins  
    
    @filter.command("刮刮乐")
    async def guaguale_play(self, event: AstrMessageEvent):
        '''抽一次刮刮乐''' 
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()
        # 自动注册用户
        if not self.server.get_balance(user_id)['success']:
            self.server.register_user(user_id, user_name)

        result = self.server.play_game(user_id)

        if result['success']:
            ticket_str = " ".join(f"{n}元" for n in result['ticket'])
            outputMsg = f"刮奖结果：{ticket_str}\n"
        
            if result.get('event'):
                gglevent = result['event']
                outputMsg += f"✨ {gglevent['name']} ✨\n{gglevent['detail']}\n"
                if gglevent['name'] == '👻 见鬼了！':
                    outputMsg += f"原应获得：{result['original_reward']}元 → 实际获得：{result['final_reward']}元\n"
            
            outputMsg += f"净收益：{result['net_gain']}元\n余额：{result['balance']}元"
        else:
            outputMsg = f"{result['msg']}"
        yield event.plain_result(f"{outputMsg}")

    @filter.command("刮刮乐帮助")
    async def guaguale_help(self, event: AstrMessageEvent):
        '''查看刮刮乐指令''' 

        help_msg = """
        🎮 刮刮乐游戏系统 🎮
        1. 【刮刮乐】- 消耗25元刮奖（每日限10次）
        2. 【刮刮乐每日签到】- 每日领取100元
        3. 【刮刮乐余额】- 查询当前余额
        4. 【打劫@某人】- 尝试抢劫对方余额
        5. 【刮刮乐排行榜】- 查看财富排行榜
        6. 【商店】- 显示商品列表
        7. 【购买】- 如：购买 2
        8. 【使用道具】- 如：使用道具 2
        9. 【改名】- 如：改名 哪吒
        10.【老板状态】- 查看可恶的老板有多少钱
        11.【老板补款】- [admin]老板太穷了，给老板补一万
        12.【我的仓库】- 显示自己的道具列表
        """
        yield event.plain_result(help_msg.strip()) 

    @filter.command("刮刮乐余额")
    async def guaguale_balance(self, event: AstrMessageEvent):
        '''查询个人余额''' 
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
        '''每日签到获取100元''' 
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
        '''查看全局排名''' 
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
        victim_id = None
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

    @filter.command("老板补款")
    async def boss_topup(self, event: AstrMessageEvent):
        '''为老板账户补充资金'''
        user_id = event.get_sender_id()
        if not self.is_admin(user_id):
            event.set_result(MessageEventResult().message("❌ 只有管理员才能使用此指令").use_t2i(False))
            return
        self.server._update_balance("boss", 10000)
        boss_balance = self.server.get_balance("boss")['balance']
        yield event.plain_result(f"老板资金已补充！当前老板账户余额：{boss_balance}元")    

    @filter.command("老板状态")
    async def boss_status(self, event: AstrMessageEvent):
        '''查看系统老板的当前状态'''
        boss_info = self.server.get_balance("boss")
        if boss_info['success']:
            yield event.plain_result(f"💰 系统老板{self.server.bossname}当前资金：{boss_info['balance']}元")
        else:
            yield event.plain_result("系统老板暂时不在线")

    @filter.command("商店")
    async def shop_command(self, event: AstrMessageEvent):
        '''查看虚拟商店'''
        result = self.server.get_shop_items()
        
        if not result['success']:
            yield event.plain_result("⚠️ 商店暂时无法访问")
            return

        items = result['items']
        if not items:
            yield event.plain_result("🛒 商店暂时没有商品")
            return

        msg = "🛒 虚拟商店 🛒\n"
        for item in items:
            msg += (
                f"【{item['item_id']}】{item['item_name']}\n"
                f"💰 价格：{item['price']}元 | 📦 库存：{item['stock']}\n"
                f"📝 说明：{item['description']}\n\n"
            )
        yield event.plain_result(msg.strip())

    @filter.command("购买")
    async def buy_command(self, event: AstrMessageEvent, oper1: str = None ):
        '''购买商品 格式：购买 [商品ID]'''
        user_id = event.get_sender_id()
        item_id = oper1
        result = self.server.purchase_item(user_id, item_id)
        
        if result['success']:
            msg = (
                f"🎁 成功购买 {result['item_name']}！\n"
                f"💰 当前余额：{result['balance']}元"
            )
        else:
            msg = f"❌ {result['msg']}"
            
        yield event.plain_result(msg)     
        
    @filter.command("我的仓库")
    async def view_inventory(self, event: AstrMessageEvent):
        '''查看拥有的道具'''
        user_id = event.get_sender_id()
        result = self.server.get_user_inventory(user_id)
        
        if not result['success']:
            yield event.plain_result("❌ 暂时无法查看仓库")
            return
            
        if not result['items']:
            yield event.plain_result("👜 您的仓库空空如也")
            return
        
        msg = "📦 您的仓库\n"
        for item in result['items']:
            msg += f"【{item['id']}】{item['name']} ×{item['quantity']}\n"
            msg += f"▸ {item['desc']}\n\n"
        
        yield event.plain_result(msg.strip())    

    @filter.command("使用道具")
    async def use_item_cmd(self, event: AstrMessageEvent, oper1: str = None):
        '''使用道具 格式：使用道具 [ID]'''
        user_id = event.get_sender_id()
        item_id = oper1
        result = self.server.use_item(user_id, item_id)
        if result['success']:
            yield event.plain_result(f"✅ 使用成功！{result['msg']}")
        else:
            yield event.plain_result(f"❌ {result['msg']}")

    # 处理改名卡输入
    @filter.command("改名")
    async def handle_rename(self, event: AstrMessageEvent,  new_name: str = None):
        user_id = event.get_sender_id()
        result = self.server.use_item(user_id, 1)
        if not result['success']:
            yield event.plain_result(f"❌ {result['msg']}")
            return
        if  2 <= len(new_name) <= 10:
            # 实际更新昵称
            self.server.update_nickname(event.get_sender_id(), new_name)
            yield event.plain_result(f"✅ 昵称已修改为：{new_name}")
        else:
            yield event.plain_result("❌ 昵称长度需为2-10个字符")    