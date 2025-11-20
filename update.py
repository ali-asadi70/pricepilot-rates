import json
from datetime import datetime

# TODO: در آینده اینجا کد واقعی دریافت نرخ‌ها قرار می‌گیرد
def fetch_rates():
    return {
        "USD": 75200,
        "EUR": 81200,
        "AED": 21100,
        "CNY": 10600,
        "XUA": {
            "local_per_ounce": 131000000,
            "local_per_gram_24k": 4250000,
            "local_per_gram_18k": 3187500
        }
    }

def save_rates(data):
    payload = {
        "success": True,
        "updated_at": datetime.utcnow().isoformat(),
        "rates": data
    }

    with open("rates.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

rates = fetch_rates()
save_rates(rates)
