import aiohttp

class PremiumGifter:
    def __init__(self, bot_token: str):
        self.url = f"https://api.telegram.org/bot{bot_token}/giftPremiumSubscription"

    async def gift(self, user_id: int, months: int, star_count: int, text: str):
        payload = {
            "user_id": user_id,
            "month_count": months,
            "star_count": star_count,
            "text": text[:128],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, json=payload, timeout=30) as r:
                body = await r.json()
                if not body.get("ok"):
                    raise RuntimeError(str(body))
                return True
