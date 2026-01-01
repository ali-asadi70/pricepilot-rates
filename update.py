import json
import urllib.request
import urllib.error
import time
import os  # برای چک وجود فایل قبلی

TGJU_JSON_URL = "https://call1.tgju.org/ajax.json"

# ضریب رایج مثقال شرعی (تقریباً) برای fallback
MESGHAL_TO_GRAM_APPROX = 4.6083

# API جایگزین برای طلا (metals.live - رایگان و real-time)
METALS_API_URL = "https://api.metals.live/v1/spot/all"
GOLD_TOLERANCE_PERCENT = 0.1  # اگر تغییر کمتر از ۰.۱% باشه، به عنوان "ثابت" در نظر بگیر

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
                status = getattr(resp, "status", 200)
                if status != 200:
                    raise RuntimeError(f"TGJU HTTP status {status}")
                return resp.read().decode("utf-8")

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(retry_delay_sec)
            else:
                raise RuntimeError(f"Failed to fetch TGJU JSON after {retries} attempts. Last error: {e}") from e

    raise RuntimeError(f"Failed to fetch TGJU JSON. Last error: {last_err}")


def fetch_metals_gold(timeout: int = 10, retries: int = 2) -> dict:
    """
    دریافت قیمت طلا از API جایگزین (metals.live) با urllib (بدون requests).
    برمی‌گرداند: {'usd_per_ounce': float, 'source': 'metals.live'} یا None اگر fail.
    """
    last_err = None

    for attempt in range(1, retries + 1):
        # Cache busting برای API جدید هم
        cache_bust = str(int(time.time() * 1000))
        sep = "&" if "?" in METALS_API_URL else "?"
        final_url = f"{METALS_API_URL}{sep}v={cache_bust}"

        req = urllib.request.Request(
            final_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; RatesUpdater/1.0)",
                "Cache-Control": "no-cache",
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = getattr(resp, "status", 200)
                if status != 200:
                    raise RuntimeError(f"Metals API HTTP status {status}")
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                xau_data = data.get("XAU", {})
                xau_usd = xau_data.get("price", 0)
                if xau_usd > 0:
                    print("Using fallback API for gold: metals.live")
                    return {
                        "usd_per_ounce": round(xau_usd, 2),
                        "source": "metals.live",
                    }
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, RuntimeError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(0.5)
            else:
                print(f"Fallback API error after {retries} attempts: {e} - using local calculation")
                return None

    return None


def get_symbol_price(current, symbol_key):
    """
    قیمت یک نماد از tgju را (به صورت float) برمی‌گرداند.
    اگر symbol_key لیست باشد، به ترتیب هر کلید را امتحان می‌کند
    و اولین مقداری که پیدا شد را برمی‌گرداند.
    """
    if isinstance(symbol_key, (list, tuple)):
        for key in symbol_key:
            val = get_symbol_price(current, key)
            if val is not None:
                return val
        return None

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


def load_previous_rates():
    """بارگذاری rates.json قبلی برای مقایسه تغییر قیمت طلا."""
    if os.path.exists("rates.json"):
        try:
            with open("rates.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                prev_rates = data.get("rates", {})
                prev_xau = prev_rates.get("XAU", {})
                return {
                    "gram18": prev_rates.get("GRAM18"),
                    "mesghal": prev_rates.get("MESGHAL"),
                    "xau_usd": prev_xau.get("usd_per_ounce") if prev_xau else None,
                }
        except:
            pass
    return {}


def has_gold_changed(new_gram18, prev_data, tolerance_percent=0.1):
    """
    چک می‌کنه آیا قیمت gram18 تغییر کرده یا نه (با tolerance برای نوسانهای ریز).
    اگر None باشه یا تغییر کمتر از tolerance، False برمی‌گردونه (یعنی "تغییر نکرده").
    """
    prev_gram18 = prev_data.get("gram18")
    if new_gram18 is None or prev_gram18 is None:
        return False  # بدون تغییر (یا موجود نیست)
    
    change_percent = abs((new_gram18 - prev_gram18) / prev_gram18 * 100)
    return change_percent >= tolerance_percent  # اگر تغییر >= tolerance، True (تغییر کرده)


def main():
    print("Fetching data from TGJU ...")
    # ۱) گرفتن JSON از tgju (مثل قبل)
    raw = fetch_tgju_json(TGJU_JSON_URL, timeout=20, retries=3, retry_delay_sec=1.5)
    data = json.loads(raw)
    current = data.get("current") or data

    # بارگذاری rates قبلی برای مقایسه طلا
    prev_rates = load_previous_rates()
    print(f"Previous gold prices: GRAM18={prev_rates.get('gram18')}, XAUUSD={prev_rates.get('xau_usd')}")

    # گرفتن نرخ‌های ارزها از TGJU (بدون تغییر)
    usd_rial = get_symbol_price(current, ["price_dollar_rls", "price_dollar_rl", "price_dollar", "price_dollar_rl2"])
    eur_rial = get_symbol_price(current, ["price_eur", "price_euro", "price_eur_rl"])
    aed_rial = get_symbol_price(current, ["price_aed", "price_dirham", "price_aed_rl"])
    cny_rial = get_symbol_price(current, ["price_cny", "price_yuan", "price_cny_rl"])
    try_rial = get_symbol_price(current, ["price_try", "price_tl", "price_toman_try", "price_tl_rl"])

    # طلا از TGJU
    gram18_rial = get_symbol_price(current, ["geram18_rl", "tala_geram18", "price_geram18", "geram18", "gram18", "geram_18", "gram18_rl"])
    mesghal_rial = get_symbol_price(
        current,
        [
            "mesghal_rl", "tala_mesghal", "price_mesghal", "mesghal", "mazanne", "mozanne", "mozanneh", "mashghal",
            "mesghal_tala", "mesghal_gold", "mesghal18", "price_mesghal_rl", "mesghal_rl"
        ]
    )

    if usd_rial is None:
        raise RuntimeError("Could not read USD price from TGJU (check symbol_key for USD).")

    # تبدیل همه‌چیز به تومان (بدون تغییر برای غیرطلا)
    usd_local = to_toman(usd_rial)
    eur_local = to_toman(eur_rial)
    aed_local = to_toman(aed_rial)
    cny_local = to_toman(cny_rial)
    try_local = to_toman(try_rial)

    # چک شرط برای طلا: اگر gram18 تغییر نکرده، از API جدید بگیر
    gram18_local = to_toman(gram18_rial)
    use_fallback = not has_gold_changed(gram18_local, prev_rates)
    print(f"GRAM18 from TGJU: {gram18_local}, Changed? {not use_fallback}")

    # اگر شرط برقرار (تغییر نکرده)، از API جایگزین بگیر
    fallback_gold = None
    if use_fallback:
        fallback_gold = fetch_metals_gold(timeout=10, retries=2)
        if fallback_gold:
            # محاسبه محلی بر اساس XAUUSD جدید (برای سازگاری با ساختار)
            usd_per_ounce_new = fallback_gold["usd_per_ounce"]
            # local_per_ounce = usd_per_ounce * usd_local (تومان برای اونس)
            per_ounce_local_new = usd_per_ounce_new * usd_local
            # back-calculate gram24k و gram18k (برای GRAM18 و MESGHAL)
            per_gram_24k_new = per_ounce_local_new / 31.1034768
            per_gram_18k_new = per_gram_24k_new * (18.0 / 24.0)
            mesghal_local_new = per_gram_18k_new * MESGHAL_TO_GRAM_APPROX  # تقریبی

            # override مقادیر طلا
            gram18_local = per_gram_18k_new
            # mesghal_local رو بعداً set می‌کنیم

    # fallback مثقال اگر مستقیم پیدا نشد
    mesghal_local = to_toman(mesghal_rial)
    mesghal_from_fallback = False
    if (mesghal_local is None or mesghal_local <= 0) and (gram18_local and gram18_local > 0):
        mesghal_local = gram18_local * MESGHAL_TO_GRAM_APPROX
        mesghal_from_fallback = True
    elif fallback_gold:  # اگر fallback استفاده شد، mesghal رو هم ازش محاسبه کن
        mesghal_local = gram18_local * MESGHAL_TO_GRAM_APPROX  # بر اساس gram18 جدید

    # محاسبه XAU (با استفاده از مقادیر آپدیت‌شده)
    xau_struct = None
    if gram18_local and gram18_local > 0:
        per_gram_18k = gram18_local
        per_gram_24k_internal = per_gram_18k * (24.0 / 18.0)
        per_ounce_local = per_gram_24k_internal * 31.1034768
        usd_per_ounce = per_ounce_local / usd_local

        xau_struct = {
            "usd_per_ounce": round(usd_per_ounce, 2),
            "local_per_ounce": round(per_ounce_local, 2),
            "local_per_mesghal": round(mesghal_local, 2) if mesghal_local else None,
            "local_per_gram_18k": round(per_gram_18k, 2),
            "mesghal_source": fallback_gold.get("source", "ajax.json") if fallback_gold else ("ajax.json" if not mesghal_from_fallback else f"fallback_from_gram18*{MESGHAL_TO_GRAM_APPROX}"),
        }
        # اگر fallback استفاده شد، usd_per_ounce رو از API جدید override کن
        if fallback_gold:
            xau_struct["usd_per_ounce"] = fallback_gold["usd_per_ounce"]

    # نسبت‌های تبدیل (بدون تغییر)
    fx = {}
    if eur_local and eur_local > 0:
        fx["EURUSD"] = round(eur_local / usd_local, 6)
    if aed_local and aed_local > 0:
        fx["AEDUSD"] = round(aed_local / usd_local, 6)
    if try_local and try_local > 0:
        fx["TRYUSD"] = round(try_local / usd_local, 6)
    if xau_struct and xau_struct.get("local_per_ounce"):
        fx["XAUUSD"] = round(xau_struct["local_per_ounce"] / usd_local, 4)

    # ساختار rates (بدون تغییر برای غیرطلا)
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

    if gram18_local and gram18_local > 0:
        rates["GRAM18"] = round(gram18_local, 2)

    if mesghal_local and mesghal_local > 0:
        rates["MESGHAL"] = round(mesghal_local, 2)

    if xau_struct:
        rates["XAU"] = xau_struct
    if fx:
        rates["FX"] = fx

    payload = {
        "success": True,
        "source": "tgju.org unofficial ajax.json (Toman) + metals.live fallback for gold",
        "rates": rates,
    }

    with open("rates.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("rates.json updated successfully.")
    if fallback_gold:
        print("Gold updated from fallback API!")


if __name__ == "__main__":
    main()
