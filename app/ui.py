from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def plans_keyboard():
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="💎 3个月 · 10 USDT", callback_data="plan:3"),
        InlineKeyboardButton(text="💎 6个月 · 19 USDT", callback_data="plan:6"),
    )
    b.row(
        InlineKeyboardButton(text="💎 1年 · 26 USDT", callback_data="plan:12"),
    )
    return b.as_markup()

def target_confirm_keyboard():
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ 是这个账号，继续", callback_data="target:yes"),
        InlineKeyboardButton(text="❌ 不是，重新输入", callback_data="target:no"),
    )
    return b.as_markup()

def payment_keyboard(order_no: str):
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="🔎 我已支付 / 检测到款",
            callback_data=f"paycheck:{order_no}",
        )
    )
    b.row(
        InlineKeyboardButton(
            text="🔄 重新输入用户名",
            callback_data="restart",
        )
    )
    return b.as_markup()
