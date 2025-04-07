# systems/shop_system.py
from typing import Dict, List
from ..database.manager import DatabaseManager

class ShopSystem:
    DEFAULT_SHOP_ITEMS = [
        (1, "改名卡", 50, "修改你的昵称", 999),
        (2, "刮卡券", 300, "额外增加5次刮卡次数", 99),
        (3, "护身符", 1000, "保护自己24小时内不被抢劫", 9999)
    ]
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        


    def _initialize_shop(self):
        """初始化商店商品"""
        try:
            self.db.initialize_shop(self.DEFAULT_SHOP_ITEMS)
            print("默认商品加载成功")
        except ValueError as e:
            print(f"加载失败: {e}")

    def get_shop_items(self) -> List[Dict]:
        """获取所有商品"""
        return self.db.get_shop_items()
    
    def purchase_item(self, user_id: str, item_id: int) -> Dict:
        # 实现购买逻辑...
        return self.db.purchase_item(user_id, item_id)