import aiohttp

class TronUSDT:
    def __init__(self, api_key: str, payment_address: str, usdt_contract: str):
        self.api_key = api_key
        self.payment_address = payment_address
        self.usdt_contract = usdt_contract
        self.base = "https://api.trongrid.io"

    async def recent_incoming(self, limit=200):
        url = f"{self.base}/v1/accounts/{self.payment_address}/transactions/trc20"
        headers = {"TRON-PRO-API-KEY": self.api_key}
        params = {
            "only_confirmed": "true",
            "only_to": "true",
            "limit": limit,
            "order_by": "block_timestamp,desc",
            "contract_address": self.usdt_contract,
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, params=params, timeout=20) as r:
                r.raise_for_status()
                data = await r.json()
                return data.get("data", [])

    async def find_payment(self, amount_usdt: float, created_at: int):
        expected = int(round(amount_usdt * 1_000_000))
        rows = await self.recent_incoming()
        candidates = []

        for row in rows:
            if row.get("to") != self.payment_address:
                continue

            token_info = row.get("token_info") or {}
            token_address = token_info.get("address")
            if token_address and token_address != self.usdt_contract:
                continue

            try:
                value = int(row.get("value", "0"))
            except (TypeError, ValueError):
                continue

            ts = int(row.get("block_timestamp", 0)) // 1000

            if ts < created_at:
                continue
            if value != expected:
                continue

            candidates.append({
                "txid": row.get("transaction_id"),
                "from": row.get("from"),
                "to": row.get("to"),
                "value": value / 1_000_000,
                "timestamp": ts,
            })

        candidates.sort(key=lambda x: x["timestamp"])
        return candidates
