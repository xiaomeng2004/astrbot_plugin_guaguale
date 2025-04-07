# database/models.py
from typing import TypedDict

class User(TypedDict):
    user_id: str
    nickname: str
    balance: int
    last_sign_date: str
    daily_scratch_count: int

class ShopItem(TypedDict):
    item_id: int
    item_name: str
    price: int
    description: str
    stock: int