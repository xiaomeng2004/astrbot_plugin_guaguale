# database_manager.py
import random
import sqlite3
import re
import time
from typing import Optional, Dict, List
from datetime import datetime, timezone
from astrbot.api import logger

class DatabaseManager:
    def __init__(self, db_path, currency_unit: str = "元"):
        self.db_path = db_path
        self.currency_unit = currency_unit
        self.boss_name = ''
        self.rob_success_rate = 35      # 成功率%
        self.rob_base_amount = 30       # 基础抢劫金额
        self.rob_max_ratio = 0.2        # 最大可抢对方余额的20%
        self.rob_penalty = 50           # 失败赔偿金额
        self.rob_cooldown = 30           # 抢劫冷却时间（秒）
        
        self.ITEM_EFFECTS = {
            1: {  # 改名卡
                'use': lambda user_id:0
            },
            2: {  # 刮卡券
                'effect': lambda user_id: self._add_scratch_chance(user_id, 5)
            },
            3: {  # 护身符
                'effect': lambda user_id: self._add_protection(user_id, 86400)  # 24小时
            }
        }    
            
    def initialize(self):
        """初始化数据库并添加新字段"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS users
                         (user_id TEXT PRIMARY KEY,
                          nickname TEXT,
                          balance INTEGER DEFAULT 100,
                          last_sign_date DATE,
                          last_scratch_date DATE,
                          daily_scratch_count INTEGER DEFAULT 0,
                          last_rob_time INTEGER)''')

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

    def initialize_boss_account(self):
        """初始化老板账户"""
        boss_id = "boss"
        with sqlite3.connect(self.db_path) as conn:
            # 如果不存在则创建老板账户
            conn.execute('''
                INSERT OR IGNORE INTO users 
                (user_id, nickname, balance) 
                VALUES (?, ?, ?)
            ''', (boss_id, "💰 系统老板"+ self.boss_name, 1000))
            conn.commit()

    def isUseridExist(self, user_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.isolation_level = 'IMMEDIATE'  # 开启事务
            cur = conn.cursor()
            user = cur.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
            if not user:
                return {'success': False, 'msg': '用户不存在'}
            else:
                return {'success': True, 'msg': '用户存在'}

    def get_user_info(self, user_id: str) -> Optional[dict]:
        """获取用户信息"""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cur.fetchone()
            if row:
                return {
                    'user_id': row[0],
                    'nickname': row[1],
                    'balance': row[2],
                    'last_sign_date': row[3],
                    'last_scratch_date': row[4],
                    'daily_scratch_count': row[5],
                    'last_rob_time': row[6]
                }
            return None
        
    def update_balance(self, user_id: str, amount: int):
        """更新用户余额""" 
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                        (amount, user_id))
            conn.commit()

    def update_boss_balance(self, amount: int):
        # 更新老板余额（反向操作）,减法
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('UPDATE users SET balance = balance - ? WHERE user_id = "boss"',
                        (amount,))
            conn.commit()

    def add_register_user(self, user_id: str, nickname: str):
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
        user = self.get_user_info(user_id)
        if not user:
            return {'success': False, 'msg': '用户不存在'}
        return {'success': True, 'balance': user['balance']}

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



    def sign_in(self, user_id: str, amount: int) -> dict:
        """每日签到"""
        today = datetime.now(tz=timezone.utc).date()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''UPDATE users 
                         SET balance = balance + ?,
                             last_sign_date = ?
                         WHERE user_id = ?''',
                         (amount, today.isoformat(), user_id))
            conn.commit()
          
    def _validate_item(self,user_id:str ,item_id:int)->dict:
        with self.get_connection() as conn:
            conn.isolation_level = 'IMMEDIATE'
            cur = conn.cursor()
            item = cur.execute(
                    'SELECT quantity FROM user_inventory WHERE user_id=? AND item_id=?',
                    (user_id, item_id)
                ).fetchone()
                
            if not item or item[0] < 1:
                return {'success': False, 'msg': '道具不存在或数量不足'}
            else:
                return {'success': True, 'msg': '道具存在且数量足够'}
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
            
            
    def _add_scratch_chance(self, user_id: str, count: int):
        """增加刮卡次数"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE users SET daily_scratch_count = daily_scratch_count - ?
                WHERE user_id = ?
            ''', (count, user_id))
            conn.commit()
        return {'success': True, 'msg': f"成功增加{count}次刮卡机会"}

    def check_protection(self, user_id: str) -> bool:
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
        
    
        

    def update_scratch_count(self, user_id: str, daily_scratch_count: int, last_scratch_date :str) -> dict:
        """带每日次数限制的游戏逻辑"""
        with sqlite3.connect(self.db_path) as conn:
            conn.isolation_level = 'IMMEDIATE'  # 开启事务
            cur = conn.cursor()
            # 更新玩家数据
            cur.execute('''UPDATE users SET
                        last_scratch_date = ?,
                        daily_scratch_count = ?
                        WHERE user_id = ?''',
                        ( last_scratch_date, daily_scratch_count, user_id))
            conn.commit()
            
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
        with sqlite3.connect(self.db_path) as conn:
            current_time = int(time.time())
            conn.isolation_level = 'IMMEDIATE'
            cur = conn.cursor()

            try:
                # 获取抢劫者信息（带行锁）
                robber = cur.execute(
                    'SELECT balance, last_rob_time FROM users WHERE user_id = ?',
                    (robber_id,)
                ).fetchone()
                
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
                    msg = f"成功抢劫了 {steal_amount}{self.currency_unit}！"
                else:
                    # 抢劫失败逻辑
                    penalty = min(robber[0], self.rob_penalty)
                    cur.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', # 抢劫者扣钱
                    (penalty, robber_id))
                    cur.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', # 受害者加钱
                    (penalty, victim_id))
                    steal_amount = -penalty
                    msg = f"抢劫失败，赔偿对方 {penalty}{self.currency_unit}！"

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
        
    # def _init_shop(self):
    #     """初始化商店商品"""
    #     with sqlite3.connect(self.db_path) as conn:
    #         # 插入或更新默认商品
    #         for item in self.default_items:
    #             conn.execute('''
    #                 INSERT OR REPLACE INTO shop_items 
    #                 (item_id, item_name, price, description, stock)
    #                 VALUES (?, ?, ?, ?, ?)
    #             ''', item)
    #         conn.commit()

    def initialize_shop(self, items: List[tuple]):
        """初始化商店商品（去重更新）"""
        self._validate_shop_items(items)
        with self.get_connection() as conn:
            conn.executemany('''
                INSERT OR REPLACE INTO shop_items 
                (item_id, item_name, price, description, stock)
                VALUES (?, ?, ?, ?, ?)
            ''', items)
            conn.commit()

    @staticmethod
    def _validate_shop_items(items: List[tuple]):
        """校验商品数据格式"""
        for idx, item in enumerate(items):
            if len(item) != 5:
                raise ValueError(f"Invalid item format at index {idx}")
            if item[2] < 0:
                raise ValueError(f"Negative price at index {idx}")

    def get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)

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
            
    # def Check_shop_item(self, item_id: int):
    #      with sqlite3.connect(self.db_path) as conn:
    #         conn.isolation_level = 'IMMEDIATE'
    #         cur = conn.cursor()
            
    #         # 获取商品信息
    #         item = cur.execute(
    #             'SELECT * FROM shop_items WHERE item_id = ?',
    #             (item_id,)
    #         ).fetchone()
            
    #         if not item:
    #             return {'success': False, 'msg': '商品不存在'}
            


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
                
                if (user_balance < item[2] or item[4] == 0):
                    return {'success': False, 'msg': '余额不足或商品数量不足'}
                
                else:
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