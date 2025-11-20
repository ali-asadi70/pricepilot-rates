import json
import urllib.request

TGJU_JSON_URL = "https://call1.tgju.org/ajax.json"


def get_symbol_price(current, symbol_key):
    """قیمت یک نماد از tgju را (به صورت float) برمی‌گرداند."""
    item = current.get(symbol_key)
    if not item:
        return None

    for key in ["p", "pn", "price"]:
        if key in item and item[key]:
            s = str(item[key]).replace(",", "").strip()
            try:
                return float(s)
            except ValueError:
                pass
    return None


def to_toman(value):
    """تبدیل مقدار خام tgju به تومان (این‌جا /100 می‌کنیم چون یک صفر اضافه داریم)."""
    if value is None:
        return None
    return value / 100.0



def main():
    print("Fetching data from TGJU ...")
    # ۱) گرفتن JSON از tgju
    with urllib.request.urlopen(TGJU_JSON_URL, timeout=20) as resp:
        if resp.status != 200:
            raise RuntimeError(f"TGJU HTTP status {resp.status}")
        raw = resp.read().decode("utf-8")

    data = json.loads(raw)

    # معمولاً data["current"] داریم
    current = data.get("current") or data

    # ⚠ اگر اسم کلیدها فرق داشت، فقط این رشته‌ها را عوض کن
    usd_rial = get_symbol_price(current, "price_dollar_rl")
    eur_rial = get_symbol_price(current, "price_eur")
    aed_rial = get_symbol_price(current, "price_aed")
    cny_rial = get_symbol_price(current, "price_cny")
    gram18_rial = get_symbol_price(current, "geram18")

    if usd_rial is None:
        raise RuntimeError("Could not read USD price from TGJU (check symbol_key for USD).")

    # تبدیل همه‌چیز به تومان
    usd_local = to_toman(usd_rial)
    eur_local = to_toman(eur_rial)
    aed_local = to_toman(aed_rial)
    cny_local = to_toman(cny_rial)
    gram18_local = to_toman(gram18_rial)

    # محاسبه طلا بر اساس قیمت ۱۸ عیار به تومان
    xau_struct = None
    if gram18_local and gram18_local > 0:
        per_gram_18k = gram18_local
        per_gram_24k = per_gram_18k * (24.0 / 18.0)
        per_ounce_local = per_gram_24k * 31.1034768  # تومان برای هر اونس
        usd_per_ounce = per_ounce_local / usd_local  # قیمت اونس به دلار

        xau_struct = {
            "usd_per_ounce": round(usd_per_ounce, 2),       # اونس بر حسب دلار
            "local_per_ounce": round(per_ounce_local, 2),   # اونس بر حسب تومان
            "local_per_gram_24k": round(per_gram_24k, 2),   # گرم ۲۴ عیار (تومان)
            "local_per_gram_18k": round(per_gram_18k, 2),   # گرم ۱۸ عیار (تومان)
        }

    # نسبت‌های تبدیل (برای بعداً، اگر لازم شد)
    fx = {}
    if eur_local and eur_local > 0:
        fx["EURUSD"] = round(eur_local / usd_local, 6)
    if aed_local and aed_local > 0:
        fx["AEDUSD"] = round(aed_local / usd_local, 6)
    if xau_struct:
        fx["XAUUSD"] = round(xau_struct["local_per_ounce"] / usd_local, 4)

    # ساختار rates بر پایه تومان
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
        rates["FX"] = fx  # فعلاً افزونه استفاده نمی‌کند، ولی برای آینده خوب است

    payload = {
        "success": True,
        "source": "tgju.org unofficial ajax.json (Toman)",
        "rates": rates,
    }

    with open("rates.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("rates.json updated successfully.")


if __name__ == "__main__":
    main()
