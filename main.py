#刮刮乐插件---水脚脚
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.all import *

from datetime import datetime, timezone
import json

from collections import defaultdict
from .src.scratch_server import ScratchServer
from .src.systems import robbery_system


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
            logger.error(f"加载管理员列表失败: {str(e)}")
            return []
        
    def is_admin(self, user_id):
        """检查用户是否为管理员"""
        return str(user_id) in self.admins  
    
    @filter.command("刮刮乐") #  👌
    async def guaguale_play(self, event: AstrMessageEvent):
        '''抽一次刮刮乐''' 
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()
        # 自动注册用户
        if not self.server.isUseridExist(user_id)['success']:
            self.server.register_user(user_id, user_name)

        result = self.server.play_game(user_id)
        yield event.plain_result(f"{result}")

    @filter.command("刮刮乐帮助") #  👌
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

    @filter.command("刮刮乐余额") #  👌
    async def guaguale_balance(self, event: AstrMessageEvent):
        '''查询个人余额''' 
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()
        # 自动注册用户
        if not self.server.isUseridExist(user_id)['success']:
            self.server.register_user(user_id, user_name)

        reset = self.server.get_balance(user_id)
        user_name2 = self.server.get_user_info(user_id)
        if reset["success"]:
            yield event.plain_result(f"用户：{user_name2['nickname']} 刮刮乐余额{reset['balance']}")
        else:
            yield event.plain_result(f"{reset['msg']}")

    @filter.command("刮刮乐每日签到") #  👌
    async def guaguale_signin(self, event: AstrMessageEvent):
        '''每日签到获取100元''' 
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()
        # 自动注册用户
        if not self.server.isUseridExist(user_id)['success']:
            self.server.register_user(user_id, user_name)

        reset = self.server.sign_in(user_id)
        
        yield event.plain_result(f"{reset['msg']}")
   

    @filter.command("刮刮乐排行榜") #  👌
    async def guaguale_ranking(self, event: AstrMessageEvent):
        '''查看全局排名''' 
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()
        # 未注册用户
        if not self.server.isUseridExist(user_id)['success']:
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
            # msg += (f"第{item['rank']}名：{item['nickname']} \n 余额：{item['balance']}元\n")
            msg += (f"第{item['rank']}名：{item['nickname']} \n 余额：{item['balance']}元\n")
        
        if my_rank['success']:
            msg += (f"\n👤 您的排名: {my_rank['user_rank']}/{my_rank['total_users']}")
            msg+=(f"\n💰 当前余额: {my_rank['user_info']['balance']}元")
        
        yield event.plain_result(f"{msg}")


    @filter.command("打劫")
    async def rob_command(self, event: AstrMessageEvent):
        '''抢劫其他用户的余额'''
        robber_id = event.get_sender_id()
        robber_name = event.get_sender_name()
        victim_id = None
        for comp in event.message_obj.message:
            if isinstance(comp, At):
                victim_id = f"{comp.qq}"
                break
        # 解析被抢者ID（适配@消息）
        if not victim_id:
            yield event.plain_result("请指定抢劫目标，例如：抢余额 @某人")
            return
            
        if not self.server.isUseridExist(robber_id):
            yield event.plain_result("玩家未注册，建议先刮刮乐每日签到")
            return
        robber_info = self.server.get_user_info(robber_id)

        if not self.server.isUseridExist(victim_id):
            yield event.plain_result("受害者不存在")
            return
        victim_info = self.server.get_user_info(victim_id)
        
        
        # 执行抢劫
        result = self.server.robbery_system.rob_balance(robber_id,victim_id)
        
        # 构建响应消息
        if result['success']:
            msg = (
                f"🏴‍☠️ {robber_info['nickname']} 对 {victim_info['nickname']} 发动了抢劫！\n"
                f"▸ {result['msg']}\n"
                f"▸ {robber_info['nickname']}当前余额：{result['balance']}元\n"
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

    @filter.command("商店") #  👌
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

    @filter.command("购买")  #  👌
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
        
    @filter.command("我的仓库")  #  👌
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
        result = self.server.use_item(user_id, item_id,)
        if result['success']:
            yield event.plain_result(f"✅ 使用成功！{result['msg']}")
        else:
            yield event.plain_result(f"❌ {result['msg']}")

    # 处理改名卡输入
    @filter.command("改名")
    async def handle_rename(self, event: AstrMessageEvent,  new_name: str = None):
       user_id = event.get_sender_id()
       name = f"{new_name}"
       if  2 <= len(name) <= 10:
            result = self.server.db_manager._validate_item(user_id,1)
            if result['success']:
                result2 = self.server.update_nickname(event.get_sender_id(), name)
                if result2['success']:
                    self.server.use_item(user_id, 1)
                    yield event.plain_result(f"✅ 昵称已修改为：{name}") 
                else:
                    yield event.plain_result(f"❌ {result2['msg']}")
            else:
                 yield event.plain_result(f"❌ {result['msg']}")    
            # 实际更新昵称
            # result = self.server.use_item(user_id, 1)
            # if not result['success']:
            #     yield event.plain_result(f"❌ {result['msg']}")
            #     return
            # else:
            #     result2 = self.server.update_nickname(event.get_sender_id(), name)
            #     if result2['success']:
            #         yield event.plain_result(f"✅ 昵称已修改为：{name}")
            #     else:
            #         yield event.plain_result(f"❌ {result2['msg']}")
                
       else:
            yield event.plain_result("❌ 昵称长度需为2-10个字符")    