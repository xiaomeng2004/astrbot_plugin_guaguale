# scratch_server.py
from datetime import datetime, timezone
from typing import List

from astrbot.api import logger
import random





# class ScratchServer:
#     def __init__(self, db_path='./data/scratch.db'):
#         self.db_path = db_path
#         self.config_path = "./data/plugins/astrbot_plugin_guaguale/guacfg.yaml"
#         self.initConfig()  # 初始化时自动加载配置

#         self.events = {
#             'jackpot': {
#                 'name': '💎 天降横财', 
#                 'prob': 2,
#                 'effect': lambda uid,reward: random.randint(100, 200)  # 使用参数uid
#             },
#             'double_next': {
#                 'name': '🔥 暴击时刻', 
#                 'prob': 5,
#                 'effect': lambda uid,reward: reward * 2  # 本次收益双倍
#             },
#             'ghost': {
#                 'name': '👻 见鬼了！',
#                 'prob': 3,
#                 'effect': lambda uid,reward: -abs(reward)  # 反转收益
#             },
#         }

#         self.ITEM_EFFECTS = {
#             1: {  # 改名卡
#                 'use': lambda user_id: 0,  # 什么都不用做 单独处理
#             },
#             2: {  # 刮卡券
#                 'effect': lambda user_id: self._add_scratch_chance(user_id, 5)
#             },
#             3: {  # 护身符
#                 'effect': lambda user_id: self._add_protection(user_id, 86400)  # 24小时
#             }
#         }
#         self._init_db()

#         self.bossname = '水脚脚'
#         self._init_boss()  # 新增老板初始化

#         # 初始化商店商品
#         self.default_items = [
#             (1, "改名卡", 50, "修改你的昵称", 999),
#             (2, "刮卡券", 300, "额外增加5次刮卡次数", 99),
#             (3, "护身符", 1000, "24小时防抢劫保护", 10)
#         ]

#         self._init_shop()


#     def initConfig(self):
#         """ 读取并解析YAML配置文件 """
#         try:
#             # 检查配置文件是否存在
#             if not os.path.exists(self.config_path):
#                 self._create_default_config()  # 创建默认配置
                
#             with open(self.config_path, 'r', encoding='utf-8') as f:
#                 config = yaml.safe_load(f)  # 安全加载[1,3](@ref)
                
#             # 参数映射到类属性
#             self.prizes = config['lottery']['prizes']
#             self.weights = config['lottery']['weights']
#             self.cost = config['lottery']['cost']
#             self.max_daily_scratch = config['lottery']['max_daily_scratch']

#             self.rob_cooldown = config['robbery']['cooldown']
#             self.rob_success_rate = config['robbery']['success_rate']
#             self.rob_base_amount = config['robbery']['base_amount']
#             self.rob_max_ratio = config['robbery']['max_ratio']
#             self.rob_penalty = config['robbery']['penalty']

#             self.event_chance = config['events']['chance']

            
#         except (FileNotFoundError, yaml.YAMLError) as e:
#             print(f"配置加载失败: {str(e)}")
#             raise

#     def _create_default_config(self):
#         """ 生成默认配置文件 """
#         default_config = {
#             'lottery': {
#                 'prizes': [0, 5, 10, 20, 50, 100],
#                 'weights': [70, 15, 10, 3, 1.6, 0.4],
#                 'cost': 25,
#                 'max_daily_scratch': 10
#             },
#             'robbery': {
#                 'cooldown': 300,
#                 'success_rate': 35,
#                 'base_amount': 30,
#                 'max_ratio': 0.2,
#                 'penalty': 50
#             },
#             'events': {
#                 'chance': 15
#             }
#         }
#         with open(self.config_path, 'w', encoding='utf-8') as f:
#             yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)  # 美观格式输出[4](@ref)

#     def use_item(self, user_id: str, item_id: int) -> dict:
#         """使用道具"""
#         with sqlite3.connect(self.db_path) as conn:
#             conn.isolation_level = 'IMMEDIATE'
#             cur = conn.cursor()
            
#             try:
#                 # 验证道具存在且可用
#                 item = cur.execute(
#                     'SELECT quantity FROM user_inventory WHERE user_id=? AND item_id=?',
#                     (user_id, item_id)
#                 ).fetchone()
                
#                 if not item or item[0] < 1:
#                     return {'success': False, 'msg': '道具不存在或数量不足'}
                
#                 # 减少库存
#                 cur.execute('''
#                     UPDATE user_inventory SET quantity = quantity - 1 
#                     WHERE user_id=? AND item_id=?
#                 ''', (user_id, item_id))
                
#                 # 执行道具效果
#                 effect = self.ITEM_EFFECTS.get(item_id)
#                 if not effect:
#                     return {'success': False, 'msg': '无效的道具'}
#                 conn.commit()
#                 if 'effect' in effect:
#                     result = effect['effect'](user_id)
#                     return result
#                 if 'use' in effect:
#                     return {'success': True, 'msg': ''}
                    
#                 return {'success': False, 'msg': '道具功能暂未实现'}
                
#             except Exception as e:
#                 conn.rollback()
#                 logger.error(f"使用道具失败: {str(e)}")
#                 return {'success': False, 'msg': '使用道具失败'}

#     # 补充相关功能方法
#     def _add_scratch_chance(self, user_id: str, count: int):
#         """增加刮卡次数"""
#         with sqlite3.connect(self.db_path) as conn:
#             conn.execute('''
#                 UPDATE users SET daily_scratch_count = daily_scratch_count - ?
#                 WHERE user_id = ?
#             ''', (count, user_id))
#             conn.commit()
#         return {'success': True, 'msg': f"成功增加{count}次刮卡机会"}

#     def _check_protection(self, user_id: str) -> bool:
#         """检查用户是否处于保护状态（同时清理过期记录）"""
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 current_time = int(time.time())
                
#                 # 先清理过期记录
#                 conn.execute('DELETE FROM user_protection WHERE expire_time < ?', (current_time,))
                
#                 # 检查剩余保护
#                 protected = conn.execute(
#                     'SELECT expire_time FROM user_protection WHERE user_id = ?',
#                     (user_id,)
#                 ).fetchone()
                
#                 return protected is not None and protected[0] > current_time
                
#         except Exception as e:
#             logger.error(f"保护检查失败: {str(e)}")
#             return False

#     def _add_protection(self, user_id: str, duration: int):
#         """添加保护（duration单位：秒）"""
#         try:
#             expire_time = int(time.time()) + duration
#             with sqlite3.connect(self.db_path) as conn:
#                 conn.execute('''
#                     INSERT OR REPLACE INTO user_protection 
#                     (user_id, expire_time) VALUES (?, ?)
#                 ''', (user_id, expire_time))
#                 conn.commit()
#             return {'success': True, 'msg': f"保护卡使用成功"}
#         except Exception as e:
#             logger.error(f"添加保护失败: {str(e)}")
#             return {'success': False, 'msg': f"保护卡使用失败"}



#     def _init_db(self):
#         """初始化数据库并添加新字段"""
#         with sqlite3.connect(self.db_path) as conn:
#             conn.execute('''CREATE TABLE IF NOT EXISTS users
#                          (user_id TEXT PRIMARY KEY,
#                           nickname TEXT,
#                           balance INTEGER DEFAULT 100,
#                           last_sign_date DATE,
#                           last_scratch_date DATE,
#                           daily_scratch_count INTEGER DEFAULT 0)''')
#             # 尝试添加可能缺失的字段
#             try:
#                 conn.execute('ALTER TABLE users ADD COLUMN last_scratch_date DATE;')
#             except sqlite3.OperationalError:
#                 pass
#             try:
#                 conn.execute('ALTER TABLE users ADD COLUMN daily_scratch_count INTEGER DEFAULT 0;')
#             except sqlite3.OperationalError:
#                 pass
#             # 新增抢劫时间字段
#             try:
#                 conn.execute('ALTER TABLE users ADD COLUMN last_rob_time INTEGER;')
#             except sqlite3.OperationalError:
#                 pass
#             # 新增商店表
#             conn.execute('''CREATE TABLE IF NOT EXISTS shop_items
#                         (item_id INTEGER PRIMARY KEY,
#                         item_name TEXT,
#                         price INTEGER,
#                         description TEXT,
#                         stock INTEGER)''')
            
#             # 新增用户库存表
#             conn.execute('''CREATE TABLE IF NOT EXISTS user_inventory
#                         (user_id TEXT,
#                         item_id INTEGER,
#                         quantity INTEGER,
#                         PRIMARY KEY (user_id, item_id))''')   
#             conn.execute('''CREATE TABLE IF NOT EXISTS user_protection
#                  (user_id TEXT PRIMARY KEY,
#                   expire_time INTEGER)''')

#     def _init_boss(self):
#         """初始化老板账户"""
#         boss_id = "boss"
#         with sqlite3.connect(self.db_path) as conn:
#             # 如果不存在则创建老板账户
#             conn.execute('''
#                 INSERT OR IGNORE INTO users 
#                 (user_id, nickname, balance) 
#                 VALUES (?, ?, ?)
#             ''', (boss_id, "💰 系统老板"+ self.bossname, 10000))
#             conn.commit()

#     def _get_user(self, user_id: str) -> Optional[dict]:
#         """获取用户信息"""
#         with sqlite3.connect(self.db_path) as conn:
#             cur = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
#             row = cur.fetchone()
#             if row:
#                 return {
#                     'user_id': row[0],
#                     'nickname': row[1],
#                     'balance': row[2],
#                     'last_sign_date': row[3]
#                 }
#             return None

#     def _update_balance(self, user_id: str, amount: int):
#         """更新用户余额"""
#         with sqlite3.connect(self.db_path) as conn:
#             conn.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
#                         (amount, user_id))
#             conn.commit()

#     def register_user(self, user_id: str, nickname: str):
#         """注册新用户"""
#         with sqlite3.connect(self.db_path) as conn:
#             try:
#                 conn.execute('INSERT INTO users (user_id, nickname) VALUES (?, ?)',
#                             (user_id, nickname))
#                 return True
#             except sqlite3.IntegrityError:
#                 return False

#     def get_balance(self, user_id: str) -> dict:
#         """查询余额"""
#         user = self._get_user(user_id)
#         if not user:
#             return {'success': False, 'msg': '用户不存在'}
#         return {'success': True, 'balance': user['balance']}

#     def sign_in(self, user_id: str) -> dict:
#         """每日签到"""
#         user = self._get_user(user_id)
#         if not user:
#             return {'success': False, 'msg': '用户不存在'}
        
#         today = datetime.now(tz=timezone.utc).date()
#         last_sign = user['last_sign_date']
        
#         if last_sign and datetime.strptime(last_sign, '%Y-%m-%d').date() == today:
#             return {'success': False, 'msg': '今日已签到'}
        
#         with sqlite3.connect(self.db_path) as conn:
#             conn.execute('''UPDATE users 
#                          SET balance = balance + 100,
#                              last_sign_date = ?
#                          WHERE user_id = ?''',
#                          (today.isoformat(), user_id))
#             conn.commit()
#         return {'success': True, 'balance': user['balance'] + 100}

#     def generate_ticket(self) -> List[int]:
#         """生成刮刮乐"""
#         return random.choices(self.prizes, weights=self.weights, k=7)

    
#     def play_game(self, user_id: str) -> dict:
#         """带每日次数限制的游戏逻辑"""
#         with sqlite3.connect(self.db_path) as conn:
#             conn.isolation_level = 'IMMEDIATE'  # 开启事务
#             cur = conn.cursor()
            
#             try:
#                 # 获取并锁定用户数据
#                 user = cur.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
#                 if not user:
#                     return {'success': False, 'msg': '用户不存在'}
                
#                 user_dict = {
#                     'balance': user[2],
#                     'last_scratch_date': user[4],
#                     'daily_scratch_count': user[5] or 0
#                 }

#                 # 检查余额
#                 if user_dict['balance'] < self.cost:
#                     return {'success': False, 'msg': '余额不足'}

#                 # 检查次数限制
#                 today = datetime.now(tz=timezone.utc).date()
#                 last_date = (datetime.strptime(user_dict['last_scratch_date'], '%Y-%m-%d').date()
#                             if user_dict['last_scratch_date'] else None)
                
#                 if last_date == today:
#                     if user_dict['daily_scratch_count'] >= self.max_daily_scratch:
#                         return {'success': False, 'msg': '今日次数已用完'}
#                     new_count = user_dict['daily_scratch_count'] + 1
#                 else:
#                     new_count = 1

#                 # 生成彩票结果
#                 ticket = self.generate_ticket()
#                 reward = sum(ticket)

#                 # 在计算reward后添加事件处理
#                 original_reward = reward
#                 event_result = None
                
#                 # 事件处理（新增异常捕获）
#                 event_result = None
#                 try:
#                     if random.randint(1, 100) <= self.event_chance:
#                         event = self._select_random_event()
#                         effect_output = event['effect'](user_id, reward)  # 传入当前用户ID
                        
#                         # 处理不同类型事件
#                         if event['name'] == '💎 天降横财':
#                             reward += effect_output
#                             event_result = event | {'detail': f"额外获得 {effect_output}元"}
#                         elif event['name'] == '🔥 暴击时刻':
#                             reward = effect_output
#                             event_result = event | {'detail': f"本次收益翻倍！获得 {effect_output}元"}
#                         # elif event['name'] == '🔄 乾坤大挪移':
#                         #     event_result = event | {'detail': effect_output}
#                         elif event['name'] == '👻 见鬼了！':
#                             reward = effect_output
#                             event_result = event | {'detail': "收益被鬼吃掉啦！"}
#                     else:
#                         event_result = None    
#                 except Exception as e:
#                     logger.error(f"Event handling error: {e}")
#                     event_result = {'name': '⚡ 系统异常', 'detail': '事件处理失败'}            
#                     reward = original_reward  # 回退到原始奖励
#                 # 更新最终收益（确保事件影响后的计算）
#                 net_gain = reward - self.cost
#                 new_balance = user_dict['balance'] + net_gain
                
#                 # 更新玩家数据
#                 cur.execute('''UPDATE users SET
#                             balance = ?,
#                             last_scratch_date = ?,
#                             daily_scratch_count = ?
#                             WHERE user_id = ?''',
#                             (new_balance, today.isoformat(), new_count, user_id))
#                 # 更新老板余额（反向操作）
#                 cur.execute('UPDATE users SET balance = balance - ? WHERE user_id = "boss"',
#                    (net_gain,))
#                 conn.commit()
#                 return {
#                     'success': True,
#                     'balance': new_balance,
#                     'ticket': ticket,
#                     'net_gain': net_gain,
#                     'event': event_result,
#                     'original_reward': original_reward,
#                     'final_reward': reward,
#                     'msg': f"获得 {reward}元 {'(盈利)' if net_gain > 0 else '(亏损)'}"
#                 }
#             except sqlite3.Error as e:
#                 return {'success': False, 'msg': '数据库错误'}
    
#     def update_nickname(self, user_id: str, new_nickname: str) -> dict:
#         """更新用户昵称"""
#         # 清理前后空格
#         new_nickname = new_nickname.strip()
        
#         # 验证基础格式
#         if len(new_nickname) < 2 or len(new_nickname) > 10:
#             return {'success': False, 'msg': '昵称长度需为2-10个字符'}
#         if not re.match(r'^[\w\u4e00-\u9fa5]+$', new_nickname):
#             return {'success': False, 'msg': '昵称仅支持中英文、数字和下划线'}
        
#         with sqlite3.connect(self.db_path) as conn:
#             conn.isolation_level = 'IMMEDIATE'
#             cur = conn.cursor()
            
#             try:
#                 # 检查昵称是否已存在
#                 existing = cur.execute(
#                     'SELECT user_id FROM users WHERE nickname = ?',
#                     (new_nickname,)
#                 ).fetchone()
                
#                 if existing and existing[0] != user_id:
#                     return {'success': False, 'msg': '昵称已被其他用户使用'}
                
#                 # 执行更新
#                 cur.execute(
#                     'UPDATE users SET nickname = ? WHERE user_id = ?',
#                     (new_nickname, user_id)
#                 )
                
#                 if cur.rowcount == 0:
#                     return {'success': False, 'msg': '用户不存在'}
                    
#                 conn.commit()
#                 return {'success': True, 'msg': '昵称修改成功'}
                
#             except Exception as e:
#                 conn.rollback()
#                 logger.error(f"更新昵称失败: {str(e)}")
#                 return {'success': False, 'msg': '昵称更新失败'}


#     def rob_balance(self, robber_id: str, victim_id: str) -> dict:
#         """
#         抢劫逻辑核心方法
#         返回格式:
#         {
#             "success": bool,
#             "msg": str,
#             "balance": int,      # 抢劫者最新余额
#             "stolen": int,       # 实际抢到金额
#             "cooldown": int      # 剩余冷却时间
#         }
#         """
#         if robber_id == victim_id:
#             return {"success": False, "msg": "不能抢劫自己"}
        
#         # 在抢劫逻辑开始处添加
#         protection = self._check_protection(victim_id)
#         if protection:
#             return {"success": False, "msg": "目标处于保护状态"}

#         with sqlite3.connect(self.db_path) as conn:
#             conn.isolation_level = 'IMMEDIATE'
#             cur = conn.cursor()

#             try:
#                 # 获取抢劫者信息（带行锁）
#                 robber = cur.execute(
#                     'SELECT balance, last_rob_time FROM users WHERE user_id = ?',
#                     (robber_id,)
#                 ).fetchone()
#                 if not robber:
#                     return {"success": False, "msg": "抢劫者未注册"}
                
#                 # 检查冷却时间
#                 current_time = int(datetime.now(tz=timezone.utc).timestamp())
#                 last_rob_time = robber[1] or 0
#                 cooldown_left = self.rob_cooldown - (current_time - last_rob_time)
                
#                 if cooldown_left > 0:
#                     return {
#                         "success": False,
#                         "msg": f"抢劫技能冷却中（剩余{cooldown_left}秒）",
#                         "cooldown": cooldown_left
#                     }

#                 # 获取受害者信息（带行锁）
#                 victim = cur.execute(
#                     'SELECT balance FROM users WHERE user_id = ?',
#                     (victim_id,)
#                 ).fetchone()
#                 if not victim:
#                     return {"success": False, "msg": "受害者不存在"}
                
#                 victim_balance = victim[0]
#                 if victim_balance <= 0:
#                     return {"success": False, "msg": "对方是个穷光蛋"}

#                 # 计算可抢金额
#                 steal_amount = min(
#                     self.rob_base_amount + int(victim_balance * random.uniform(0.1, self.rob_max_ratio)),
#                     victim_balance
#                 )
                
#                 # 判断抢劫是否成功
#                 is_success = random.randint(1, 100) <= self.rob_success_rate
                
#                 if is_success:
#                     # 抢劫成功逻辑
#                     # 转移金额
#                     cur.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?',
#                                (steal_amount, victim_id))
#                     cur.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
#                                (steal_amount, robber_id))
#                     msg = f"成功抢劫了 {steal_amount}元！"
#                 else:
#                     # 抢劫失败逻辑
#                     penalty = min(robber[0], self.rob_penalty)
#                     cur.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', # 抢劫者扣钱
#                     (penalty, robber_id))
#                     cur.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', # 受害者加钱
#                     (penalty, victim_id))
#                     steal_amount = -penalty
#                     msg = f"抢劫失败，赔偿对方 {penalty}元！"

#                 # 更新抢劫时间
#                 cur.execute('UPDATE users SET last_rob_time = ? WHERE user_id = ?',
#                            (current_time, robber_id))
                
#                 # 获取最新余额
#                 new_balance = cur.execute(
#                     'SELECT balance FROM users WHERE user_id = ?',
#                     (robber_id,)
#                 ).fetchone()[0]
                
#                 conn.commit()
#                 return {
#                     "success": True,
#                     "msg": msg,
#                     "balance": new_balance,
#                     "stolen": steal_amount,
#                     "cooldown": self.rob_cooldown
#                 }

#             except Exception as e:
#                 conn.rollback()
#                 return {"success": False, "msg": "系统错误：抢劫失败"}


#     def get_rankings(self, top_n: int = 10) -> dict:
#         """
#         获取全局排行榜
#         返回格式:
#         {
#             "success": bool,
#             "rankings": [
#                 {
#                     "rank": int,
#                     "nickname": str,
#                     "balance": int,
#                     "user_id": str
#                 },
#                 ...
#             ]
#         }
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 conn.row_factory = sqlite3.Row
#                 cur = conn.execute('''
#                     SELECT user_id, nickname, balance 
#                     FROM users 
#                     ORDER BY balance DESC, user_id ASC
#                     LIMIT ?
#                 ''', (top_n,))
                
#                 rankings = []
#                 for rank, row in enumerate(cur.fetchall(), start=1):
#                     rankings.append({
#                         "rank": rank,
#                         "nickname": row['nickname'],
#                         "balance": row['balance'],
#                         "user_id": row['user_id']
#                     })
                
#                 return {"success": True, "rankings": rankings}
        
#         except Exception as e:
#             return {"success": False, "error": str(e)}

#     def get_user_ranking(self, user_id: str) -> dict:
#         """
#         获取用户个人排名信息
#         返回格式:
#         {
#             "success": bool,
#             "user_rank": int,
#             "total_users": int,
#             "user_info": {
#                 "nickname": str,
#                 "balance": int
#             }
#         }
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 # 获取用户信息
#                 user_info = conn.execute('''
#                     SELECT nickname, balance 
#                     FROM users 
#                     WHERE user_id = ?
#                 ''', (user_id,)).fetchone()
                
#                 if not user_info:
#                     return {"success": False, "error": "用户不存在"}
                
#                 # 计算用户排名
#                 rank = conn.execute('''
#                     SELECT COUNT(*) + 1 as rank 
#                     FROM users 
#                     WHERE balance > ?
#                 ''', (user_info[1],)).fetchone()[0]
                
#                 # 获取总用户数
#                 total_users = conn.execute('''
#                     SELECT COUNT(*) FROM users
#                 ''').fetchone()[0]
                
#                 return {
#                     "success": True,
#                     "user_rank": rank,
#                     "total_users": total_users,
#                     "user_info": {
#                         "nickname": user_info[0],
#                         "balance": user_info[1]
#                     }
#                 }
        
#         except Exception as e:
#             return {"success": False, "error": str(e)}

#     def _select_random_event(self):
#         """加权随机选择事件"""
#         total = sum(e['prob'] for e in self.events.values())
#         r = random.uniform(0, total)
#         upto = 0
#         for event in self.events.values():
#             if upto + event['prob'] >= r:
#                 return event
#             upto += event['prob']
#         return list(self.events.values())[0]




# scratch_server.py（主入口，整合所有模块）
from .config.settings import ConfigManager
from .database.manager import DatabaseManager
from .systems.event_system import EventSystem
from .systems.shop_system import ShopSystem
from .systems.robbery_system import RobberySystem
# from .systems.robbery_system import RobberySystem

class ScratchServer:
    def __init__(self, db_path='./data/scratch.db'):
        self.db_manager = DatabaseManager(db_path)
        self.cfg_mgr = ConfigManager()
        self.event_system = EventSystem()
        self.shop_system = ShopSystem(self.db_manager)
        self.robbery_system = RobberySystem(self.db_manager)
        
        # 初始化基础组件
        self._init_core_components()
        
    def _init_core_components(self):
        """初始化核心组件"""
        self.cfg_mgr.initConfig()
        self.db_manager.initialize()
        # self.shop_system.initialize_shop()
        self.db_manager.initialize_boss_account()
        self.shop_system._initialize_shop()

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
        return {'success': True, 'msg': f"签到成功，当前余额{self.db_manager.get_balance(user_id)['balance']}"}  

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

        ticket_str = " ".join(f"{n}元" for n in ticket)
        outputMsg = f"刮奖结果：{ticket_str}\n"
        
        if event_result:
            outputMsg += f"✨ {event_result['name']} ✨\n{event_result['detail']}\n"

        outputMsg += f"净收益：{net_gain}元\n余额：{new_balance}元"
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