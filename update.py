import json
import urllib.request
import urllib.error
import time

TGJU_JSON_URL = "https://call1.tgju.org/ajax.json"

# ضریب رایج مثقال شرعی (تقریباً) برای fallback
MESGHAL_TO_GRAM_APPROX = 4.6083


def fetch_tgju_json(url: str, timeout: int = 20, retries: int = 3, retry_delay_sec: float = 1.5) -> str:
    """
    دریافت JSON از TGJU با:
    - cache-busting (پارامتر v با timestamp)
    - هدرهای ضد کش + User-Agent
    - retry در صورت خطا/timeout
    """
    last_err = None

    for attempt in range(1, retries + 1):
        # Cache busting: پارامتر v برای جلوگیری از پاسخ کش‌شده توسط CDN/Proxy
        cache_bust = str(int(time.time() * 1000))
        sep = "&" if "?" in url else "?"
        final_url = f"{url}{sep}v={cache_bust}"

        req = urllib.request.Request(
            final_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; RatesUpdater/1.0)",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Accept": "application/json,text/plain,*/*",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                # resp.status در urllib همیشه نیست، ولی در CPython معمولاً هست
                status = getattr(resp, "status", 200)
                if status != 200:
                    raise RuntimeError(f"TGJU HTTP status {status}")
                return resp.read().decode("utf-8")

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError) as e:
            last_err = e
            # اگر آخرین تلاش نیست، کمی صبر کن و دوباره امتحان کن
            if attempt < retries:
                time.sleep(retry_delay_sec)
            else:
                raise RuntimeError(f"Failed to fetch TGJU JSON after {retries} attempts. Last error: {e}") from e

    # عملاً به اینجا نمی‌رسیم، ولی برای اطمینان:
    raise RuntimeError(f"Failed to fetch TGJU JSON. Last error: {last_err}")


def get_symbol_price(current, symbol_key):
    """
    قیمت یک نماد از tgju را (به صورت float) برمی‌گرداند.
    اگر symbol_key لیست باشد، به ترتیب هر کلید را امتحان می‌کند
    و اولین مقداری که پیدا شد را برمی‌گرداند.
    """
    # اگر symbol_key یک iterable از کلیدهاست، آنها را یکی‌یکی امتحان کن
    if isinstance(symbol_key, (list, tuple)):
        for key in symbol_key:
            val = get_symbol_price(current, key)
            if val is not None:
                return val
        return None

    # در حالت عادی symbol_key یک رشته است
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
    # ۱) گرفتن JSON از tgju (با cache-busting + headers + retry)
    raw = fetch_tgju_json(TGJU_JSON_URL, timeout=20, retries=3, retry_delay_sec=1.5)

    data = json.loads(raw)

    # معمولاً data["current"] داریم
    current = data.get("current") or data

    # ⚠ اگر اسم کلیدها فرق داشت، ما چند گزینه را امتحان می‌کنیم
    usd_rial = get_symbol_price(current, ["price_dollar_rl", "price_dollar", "price_dollar_rl2"])
    eur_rial = get_symbol_price(current, ["price_eur", "price_euro", "price_eur_rl"])
    aed_rial = get_symbol_price(current, ["price_aed", "price_dirham", "price_aed_rl"])
    cny_rial = get_symbol_price(current, ["price_cny", "price_yuan", "price_cny_rl"])
    # اضافه: تلاش برای پیدا کردن قیمت لیر (TRY) با چند کلید محتمل
    try_rial = get_symbol_price(current, ["price_try", "price_tl", "price_toman_try", "price_tl_rl"])

    # طلا ۱۸ عیار (باید بماند)
    gram18_rial = get_symbol_price(current, ["geram18", "gram18", "geram_18", "gram18_rl"])

    # ✅ مثقال طلا (جایگزین ۲۴ عیار در خروجی)
    # چون کلید دقیق ممکن است بسته به نسخه‌ها متفاوت باشد، چند حالت محتمل:
    mesghal_rial = get_symbol_price(
        current,
        [
            "mesghal", "mesghal_tala", "mesghal_gold", "mesghal18",
            "mazanne", "mozanne", "mozanneh", "mashghal",
            "price_mesghal", "price_mesghal_rl", "mesghal_rl"
        ]
    )

    if usd_rial is None:
        raise RuntimeError("Could not read USD price from TGJU (check symbol_key for USD).")

    # تبدیل همه‌چیز به تومان
    usd_local = to_toman(usd_rial)
    eur_local = to_toman(eur_rial)
    aed_local = to_toman(aed_rial)
    cny_local = to_toman(cny_rial)
    try_local = to_toman(try_rial)
    gram18_local = to_toman(gram18_rial)
    mesghal_local = to_toman(mesghal_rial)

    # اگر مثقال مستقیم از TGJU پیدا نشد، برای اینکه سیستم از کار نیفته،
    # یک fallback تقریباً نزدیک از روی گرم ۱۸ عیار می‌سازیم.
    # (مسیر اصلی همچنان ajax.json است؛ این فقط کمک اضطراری است.)
    mesghal_from_fallback = False
    if (mesghal_local is None or mesghal_local <= 0) and (gram18_local and gram18_local > 0):
        mesghal_local = gram18_local * MESGHAL_TO_GRAM_APPROX
        mesghal_from_fallback = True

    # محاسبه طلا بر اساس قیمت ۱۸ عیار به تومان (برای اونس و XAUUSD و ...)
    xau_struct = None
    if gram18_local and gram18_local > 0:
        per_gram_18k = gram18_local
        # همچنان برای محاسبه اونس نیاز داریم 24k را "داخلی" حساب کنیم،
        # اما دیگر در خروجی به عنوان نرخ/واحد نمایش داده نمی‌شود.
        per_gram_24k_internal = per_gram_18k * (24.0 / 18.0)
        per_ounce_local = per_gram_24k_internal * 31.1034768  # تومان برای هر اونس
        usd_per_ounce = per_ounce_local / usd_local  # قیمت اونس به دلار

        xau_struct = {
            "usd_per_ounce": round(usd_per_ounce, 2),       # اونس بر حسب دلار
            "local_per_ounce": round(per_ounce_local, 2),   # اونس بر حسب تومان
            # ✅ ۲۴ عیار حذف شد و به جایش مثقال آمد
            "local_per_mesghal": round(mesghal_local, 2) if mesghal_local else None,
            # ۱۸ عیار باید بماند
            "local_per_gram_18k": round(per_gram_18k, 2),   # گرم ۱۸ عیار (تومان)
            # کمک به دیباگ (هیچ چیزی از امکانات کم نمی‌کند)
            "mesghal_source": "ajax.json" if not mesghal_from_fallback else f"fallback_from_gram18*{MESGHAL_TO_GRAM_APPROX}",
        }

    # نسبت‌های تبدیل (برای بعداً، اگر لازم شد)
    fx = {}
    if eur_local and eur_local > 0:
        fx["EURUSD"] = round(eur_local / usd_local, 6)
    if aed_local and aed_local > 0:
        fx["AEDUSD"] = round(aed_local / usd_local, 6)
    if try_local and try_local > 0:
        fx["TRYUSD"] = round(try_local / usd_local, 6)
    if xau_struct and xau_struct.get("local_per_ounce"):
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
    if try_local and try_local > 0:
        rates["TRY"] = round(try_local, 2)

    # ✅ ۱۸ عیار را حذف نمی‌کنیم: هم داخل XAU_struct هست، هم می‌توانیم جداگانه نگه داریم
    if gram18_local and gram18_local > 0:
        rates["GRAM18"] = round(gram18_local, 2)  # تومان برای هر گرم ۱۸ عیار (اختیاری اما مفید)

    # ✅ مثقال به عنوان یک نرخ مستقل (برای مصرف ساده‌تر در افزونه)
    if mesghal_local and mesghal_local > 0:
        rates["MESGHAL"] = round(mesghal_local, 2)

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
