import json
import urllib.request
import math

TGJU_JSON_URL = "https://call1.tgju.org/ajax.json"

# این تابع یک سیمبل از tgju را گرفته و قیمتش را به صورت float (بدون ویرگول) برمی‌گرداند
def get_symbol_price(current, symbol_key):
    item = current.get(symbol_key)
    if not item:
        return None

    # در اکثر اسکریپت‌ها قیمت در فیلد p یا pn است (مثل "1,234,567")
    for key in ["p", "pn", "price"]:
        if key in item and item[key]:
            s = str(item[key]).replace(",", "").strip()
            try:
                return float(s)
            except ValueError:
                pass
    return None


def main():
    print("Fetching data from TGJU ...")
    # ۱) گرفتن JSON از tgju
    with urllib.request.urlopen(TGJU_JSON_URL, timeout=20) as resp:
        if resp.status != 200:
            raise RuntimeError(f"TGJU HTTP status {resp.status}")
        raw = resp.read().decode("utf-8")

    data = json.loads(raw)

    # بسته به ساختار، ممکن است data["current"] یا data["results"]["other"]["current"] باشد.
    # رایج‌ترین حالت:
    current = data.get("current") or data

    # ⚠️⚠️ این اسم‌ها را اگر لازم شد با اسم دقیق سیمبل‌هایی که در JSON می‌بینی عوض کن ⚠️⚠️
    # دلار آزاد
    usd_local = get_symbol_price(current, "price_dollar_rl")
    # یورو
    eur_local = get_symbol_price(current, "price_eur")
    # درهم
    aed_local = get_symbol_price(current, "price_aed")
    # یوان چین (اگر نبود بعداً می‌تونیم حذفش کنیم)
    cny_local = get_symbol_price(current, "price_cny")

    # طلای ۱۸ عیار (گرمی)
    gram18_local = get_symbol_price(current, "geram18")

    if usd_local is None:
        raise RuntimeError("Could not read USD price from TGJU (check symbol_key for USD).")

    # اگر یورو یا درهم یا یوان پیدا نشد، None می‌مانند و بعد در JSON نمی‌گذاریم
    # محاسبه‌ی طلای ۲۴ عیار و اونس بر اساس طلای ۱۸ عیار بازار ایران:
    xau_struct = None
    if gram18_local and gram18_local > 0:
        per_gram_18k = gram18_local
        per_gram_24k = per_gram_18k * (24.0 / 18.0)
        per_ounce_local = per_gram_24k * 31.1034768
        xau_struct = {
            "usd_per_ounce": round(per_ounce_local / usd_local, 4),
            "local_per_ounce": round(per_ounce_local, 2),
            "local_per_gram_24k": round(per_gram_24k, 2),
            "local_per_gram_18k": round(per_gram_18k, 2),
        }

    # نرخ‌های تبدیل (بازار ایران → نسبت به دلار)
    fx = {}

    if eur_local and eur_local > 0:
        fx["EURUSD"] = round(eur_local / usd_local, 6)
    if aed_local and aed_local > 0:
        fx["AEDUSD"] = round(aed_local / usd_local, 6)
    if xau_struct:
        fx["XAUUSD"] = round(xau_struct["local_per_ounce"] / usd_local, 4)

    # ساختار خروجی‌ای که افزونه‌ی وردپرس ازش استفاده می‌کند
    rates = {
        "USD": round(usd_local, 2),
    }
    if eur_local and eur_local > 0:
        rates["EUR"] = round(eur_local, 2)
    if aed_local and aed_local > 0:
        rates["AED"] = round(aed_local, 2)
    if cny_local and cny_local > 0:
        rates["CNY"] = round(cny_local, 2)
    if xau_struct:
        rates["XAU"] = xau_struct
    if fx:
        rates["FX"] = fx  # فعلاً افزونه‌ات این رو استفاده نمی‌کند، ولی برای آینده خوبه

    payload = {
        "success": True,
        "source": "tgju.org unofficial ajax.json",
        "rates": rates,
    }

    # نوشتن در فایل rates.json
    with open("rates.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("rates.json updated successfully.")


if __name__ == "__main__":
    main()
