from io import BytesIO
from telethon import TelegramClient
from telethon.errors import UsernameInvalidError, UsernameNotOccupiedError

class TelegramResolver:
    def __init__(self, api_id: int, api_hash: str):
        self.client = TelegramClient("data/resolver", api_id, api_hash)

    async def start(self):
        await self.client.start()

    async def close(self):
        await self.client.disconnect()

    async def resolve(self, username: str):
        username = username.strip()
        if username.startswith("@"):
            username = username[1:]
        if not username:
            raise ValueError("用户名不能为空")

        try:
            entity = await self.client.get_entity(username)
        except (UsernameInvalidError, UsernameNotOccupiedError):
            raise ValueError("找不到这个 Telegram 用户名")

        if getattr(entity, "bot", False):
            raise ValueError("这个用户名是机器人账号，不能充值 Premium")

        if not getattr(entity, "id", None):
            raise ValueError("无法获取目标用户 ID")

        first = getattr(entity, "first_name", "") or ""
        last = getattr(entity, "last_name", "") or ""
        display = (first + " " + last).strip() or username

        photo = None
        try:
            bio = BytesIO()
            result = await self.client.download_profile_photo(entity, file=bio)
            if result:
                bio.seek(0)
                photo = bio.getvalue()
        except Exception:
            photo = None

        return {
            "id": int(entity.id),
            "username": username,
            "display_name": display,
            "photo": photo,
        }
