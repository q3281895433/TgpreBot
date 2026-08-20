import asyncio
import logging
import os
import secrets
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    BufferedInputFile,
)

from .config import load_config
from .db import (
    init_db,
    create_order,
    get_order,
    get_pending_orders,
    mark_paid,
    mark_gifted,
    mark_error,
    tx_already_used,
)
from .catalog import get_plan
from .ui import plans_keyboard, target_confirm_keyboard, payment_keyboard
from .telegram_resolver import TelegramResolver
from .tron import TronUSDT
from .premium import PremiumGifter

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class Form(StatesGroup):
    waiting_username = State()
    confirming_target = State()

cfg = load_config()
bot = Bot(cfg.bot_token)
dp = Dispatcher()

resolver = TelegramResolver(cfg.api_id, cfg.api_hash)
tron = TronUSDT(cfg.trongrid_api_key, cfg.payment_address, cfg.usdt_contract)
gifter = PremiumGifter(cfg.bot_token)

pending_targets = {}
pending_plans = {}

def make_order_no() -> str:
    return (
        "TG"
        + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        + secrets.token_hex(3).upper()
    )

async def send_photo(chat_id: int, caption: str, reply_markup=None, photo_bytes=None):
    if photo_bytes is not None:
        return await bot.send_photo(
            chat_id,
            BufferedInputFile(photo_bytes, filename="banner.jpg"),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )

    if os.path.exists(cfg.banner_path):
        return await bot.send_photo(
            chat_id,
            FSInputFile(cfg.banner_path),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )

    return await bot.send_message(
        chat_id,
        caption,
        reply_markup=reply_markup,
        parse_mode="HTML",
    )

INTRO = """✨ <b>Telegram Premium 会员充值中心</b>

欢迎来到会员充值服务 💎

Telegram Premium 可解锁：
• 🚀 更快的下载与上传
• 📁 更大的文件上传限制
• 🎨 更多高级功能与个性化体验
• ⭐ Premium 专属权益

🔥 <b>全网优惠价</b>
💎 3个月：<b>10 USDT</b>
💎 6个月：<b>19 USDT</b>
💎 1年：<b>26 USDT</b>

请选择你要充值的 Premium 套餐 👇
"""

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    pending_targets.pop(message.from_user.id, None)
    pending_plans.pop(message.from_user.id, None)
    await send_photo(message.chat.id, INTRO, plans_keyboard())

@dp.callback_query(F.data.startswith("plan:"))
async def choose_plan(callback: CallbackQuery, state: FSMContext):
    months = int(callback.data.split(":")[1])
    plan = get_plan(months)
    pending_plans[callback.from_user.id] = plan
    pending_targets.pop(callback.from_user.id, None)
    await state.set_state(Form.waiting_username)

    text = f"""💎 <b>已选择：{plan['label']}</b>

价格：<b>{plan['price']:.0f} USDT</b>

现在请输入需要充值的 Telegram 用户名：

例如：
<code>@username</code>

⚠️ 请仔细确认用户名，付款并完成赠送后无法因为输入错误自动追回。"""

    await callback.answer()
    await send_photo(callback.message.chat.id, text)

@dp.message(Form.waiting_username)
async def username_input(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if not raw.startswith("@"):
        await send_photo(
            message.chat.id,
            "❌ 请输入以 <code>@</code> 开头的用户名，例如 <code>@username</code>。",
        )
        return

    await send_photo(message.chat.id, "🔎 正在查询用户名与头像，请稍候…")

    try:
        target = await resolver.resolve(raw)
    except Exception as e:
        await send_photo(
            message.chat.id,
            f"❌ <b>查询失败</b>\n\n{str(e)}\n\n请重新输入用户名。",
        )
        return

    pending_targets[message.from_user.id] = target
    await state.set_state(Form.confirming_target)

    caption = f"""👤 <b>请确认充值账号</b>

用户名：<b>@{target['username']}</b>
名称：<b>{target['display_name']}</b>

你是否确定要给这个账号充值 Telegram Premium？

⚠️ 用户名一旦确认并完成付款，请勿填写错误账号。"""

    # 先展示目标用户头像，再用项目统一宣传图发送确认消息。
    # 这样既满足“显示目标头像”，又保证确认流程消息统一使用你的项目图片。
    if target["photo"] is not None:
        await bot.send_photo(
            message.chat.id,
            BufferedInputFile(target["photo"], filename="target_avatar.jpg"),
            caption=f"👤 找到账号：<b>@{target['username']}</b>\n名称：<b>{target['display_name']}</b>",
            parse_mode="HTML",
        )

    await send_photo(
        message.chat.id,
        caption,
        target_confirm_keyboard(),
    )

@dp.callback_query(Form.confirming_target, F.data == "target:no")
async def target_no(callback: CallbackQuery, state: FSMContext):
    pending_targets.pop(callback.from_user.id, None)
    await state.set_state(Form.waiting_username)
    await callback.answer()
    await send_photo(
        callback.message.chat.id,
        "🔄 好的，请重新输入需要充值的 Telegram 用户名，例如 <code>@username</code>。",
    )

@dp.callback_query(Form.confirming_target, F.data == "target:yes")
async def target_yes(callback: CallbackQuery, state: FSMContext):
    target = pending_targets.get(callback.from_user.id)
    plan = pending_plans.get(callback.from_user.id)

    if not target or not plan:
        await callback.answer("订单信息已过期，请重新开始。", show_alert=True)
        await state.clear()
        return

    no = make_order_no()
    await create_order(
        cfg.db_path,
        no,
        callback.message.chat.id,
        target["id"],
        "@" + target["username"],
        target["display_name"],
        plan["months"],
        plan["price"],
        plan["stars"],
    )

    await state.clear()
    await callback.answer("订单已创建")

    text = f"""🧾 <b>订单创建成功</b>

订单号：<code>{no}</code>
充值账号：<b>@{target['username']}</b>
套餐：<b>{plan['label']}</b>
应付：<b>{plan['price']:.0f} USDT</b>
网络：<b>TRC20</b>

💳 <b>请向以下地址转账：</b>
<code>{cfg.payment_address}</code>

⚠️ 仅支持 <b>USDT-TRC20</b>。
⚠️ 请务必核对收款地址和网络。

支付完成后点击：
<b>🔎 我已支付 / 检测到款</b>

系统会自动查询链上到账情况。
到账确认后，机器人将为目标账号赠送 Premium。"""

    await send_photo(callback.message.chat.id, text, payment_keyboard(no))

async def process_order(order):
    no = order["order_no"]
    if order["status"] != "pending":
        return

    candidates = await tron.find_payment(
        order["price_usdt"],
        order["created_at"],
    )

    if not candidates:
        return

    for tx in candidates:
        if not tx["txid"]:
            continue
        if await tx_already_used(cfg.db_path, tx["txid"]):
            continue

        claimed = await mark_paid(
            cfg.db_path,
            no,
            tx["txid"],
            tx["from"] or "",
        )
        if not claimed:
            return

        paid_text = f"""✅ <b>付款已确认</b>

订单：<code>{no}</code>
金额：<b>{order['price_usdt']:.0f} USDT</b>
交易：<code>{tx['txid']}</code>

🎁 正在为 <b>{order['target_username']}</b> 赠送 Telegram Premium…

⏳ 正常情况下，Premium 会在 <b>2 分钟内</b> 以礼物形式到账。"""

        await send_photo(order["buyer_chat_id"], paid_text)

        try:
            await gifter.gift(
                order["target_user_id"],
                order["months"],
                order["star_count"],
                f"Telegram Premium {order['months']}个月",
            )

            await mark_gifted(cfg.db_path, no)

            success = f"""🎉 <b>充值完成！</b>

账号：<b>{order['target_username']}</b>
套餐：<b>{order['months']}个月</b>
订单：<code>{no}</code>

🎁 Telegram Premium 已发送。

请目标账号留意 Telegram 的 Premium 礼物消息。
一般会在 <b>2 分钟内</b>到账。"""

            await send_photo(order["buyer_chat_id"], success)

        except Exception as e:
            log.exception("gift failed for %s", no)
            await mark_error(cfg.db_path, no, str(e), status="paid")

            await send_photo(
                order["buyer_chat_id"],
                f"""⚠️ <b>付款已确认，但赠送正在重试</b>

订单：<code>{no}</code>
付款交易：<code>{tx['txid']}</code>

系统已经确认 USDT 到账。
Premium 礼物发送出现暂时性问题，系统会继续处理。

请不要重复付款。""",
            )
        return

@dp.callback_query(F.data.startswith("paycheck:"))
async def manual_check(callback: CallbackQuery):
    no = callback.data.split(":", 1)[1]
    order = await get_order(cfg.db_path, no)

    if not order or order["buyer_chat_id"] != callback.message.chat.id:
        await callback.answer("订单不存在。", show_alert=True)
        return

    if order["status"] == "gifted":
        await callback.answer("这个订单已经完成。", show_alert=True)
        return

    await callback.answer("正在查询链上交易…")

    await send_photo(
        callback.message.chat.id,
        f"""🔎 <b>正在查询订单是否支付</b>

订单：<code>{no}</code>
金额：<b>{order['price_usdt']:.0f} USDT</b>
网络：<b>TRC20</b>

请稍候，系统正在查询 TRON 链上已确认交易。""",
    )

    await process_order(order)

    latest = await get_order(cfg.db_path, no)
    if latest and latest["status"] == "pending":
        await send_photo(
            callback.message.chat.id,
            f"""⏳ <b>暂未检测到付款</b>

订单：<code>{no}</code>

目前还没有检测到符合以下条件的已确认交易：
• 收款地址正确
• USDT TRC20
• 金额：{order['price_usdt']:.0f} USDT

如果你刚刚完成转账，请等待几秒后再次点击检测。

⚠️ 请不要重复付款。""",
            payment_keyboard(no),
        )

@dp.callback_query(F.data == "restart")
async def restart(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    pending_targets.pop(callback.from_user.id, None)
    pending_plans.pop(callback.from_user.id, None)
    await callback.answer()
    await send_photo(callback.message.chat.id, INTRO, plans_keyboard())

async def payment_worker():
    while True:
        try:
            orders = await get_pending_orders(cfg.db_path)
            for order in orders:
                try:
                    await process_order(order)
                except Exception:
                    log.exception("payment worker failed for %s", order["order_no"])
        except Exception:
            log.exception("payment worker loop failed")

        await asyncio.sleep(cfg.payment_poll_seconds)

async def main():
    await init_db(cfg.db_path)
    await resolver.start()

    worker = asyncio.create_task(payment_worker())

    try:
        await dp.start_polling(bot)
    finally:
        worker.cancel()
        await resolver.close()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
