import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    api_id: int
    api_hash: str
    trongrid_api_key: str
    db_path: str
    payment_address: str
    usdt_contract: str
    banner_path: str
    payment_poll_seconds: int

def load_config() -> Config:
    required = ["BOT_TOKEN", "API_ID", "API_HASH", "TRONGRID_API_KEY"]
    missing = [x for x in required if not os.getenv(x)]
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))

    return Config(
        bot_token=os.environ["BOT_TOKEN"],
        api_id=int(os.environ["API_ID"]),
        api_hash=os.environ["API_HASH"],
        trongrid_api_key=os.environ["TRONGRID_API_KEY"],
        db_path=os.getenv("DB_PATH", "data/bot.db"),
        payment_address=os.getenv(
            "PAYMENT_ADDRESS",
            "TJ8GZSrsoQLa1ie7bxdayFdHgJK2pn4p27",
        ),
        usdt_contract=os.getenv(
            "USDT_CONTRACT",
            "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
        ),
        banner_path=os.getenv("BANNER_PATH", "assets/banner.jpg"),
        payment_poll_seconds=int(os.getenv("PAYMENT_POLL_SECONDS", "8")),
    )
