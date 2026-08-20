PLANS = {
    3:  {"months": 3,  "price": 10.0, "stars": 1000, "label": "3个月"},
    6:  {"months": 6,  "price": 19.0, "stars": 1500, "label": "6个月"},
    12: {"months": 12, "price": 26.0, "stars": 2500, "label": "1年"},
}

def get_plan(months: int):
    if months not in PLANS:
        raise ValueError("Unsupported plan")
    return PLANS[months]
