import json
import urllib.request
import urllib.error
import time

# آدرس منبع داده از سایت TGJU
TGJU_JSON_URL = "https://call1.tgju.org/ajax.json"
# ضریب رایج مثقال شرعی (تقریباً) برای fallback در صورتی که قیمت مستقیم مثقال دریافت نشود
MESGHAL_TO_GRAM_APPROX = 4.6083

def get_symbol_price(current, symbol_key):
    """
    این تابع وظیفه دارد قیمت یک نماد را از دیکشنری داده‌ها پیدا کرده و به صورت عدد اعشاری (float) برگرداند.
    اگر به جای یک کلید، لیستی از کلیدهای احتمالی داده شود، به ترتیب بررسی می‌کند تا اولین مقدار معتبر را پیدا کند.
    """
    # اگر آرگومان دریافتی یک لیست یا تاپل از کلیدها باشد
    if isinstance(symbol_key, (list, tuple)):
        for key in symbol_key:
            val = get_symbol_price(current, key)
            if val is not None:
                return val
        return None
    
    # در حالت عادی که فقط یک رشته به عنوان کلید ارسال شده است
    item = current.get(symbol_key)
    if not item:
        return None
    
    # بررسی کلیدهای مختلفی که ممکن است قیمت داخل آن‌ها باشد (p یا pn یا price)
    for key in ["p", "pn", "price"]:
        if key in item and item[key]:
            # حذف کاما از قیمت (مثلا 50,000 تبدیل می‌شود به 50000)
            s = str(item[key]).replace(",", "").strip()
            try:
                return float(s)
            except ValueError:
                pass
    
    return None

def to_toman(value):
    """
    تبدیل مقدار خام دریافتی از tgju به تومان.
    اعداد در tgju معمولا با یک صفر اضافه (ریال) هستند، بنابراین بر 10 یا 100 (بسته به واحد) تقسیم می‌کنیم.
    اینجا طبق منطق قبلی شما بر 100 تقسیم شده است.
    """
    if value is None:
        return None
    return value / 100.0

def main():
    print("Fetching data from TGJU ...")
    
    # ---------------------------------------------------------------------------------
    # بخش اصلاح شده: ایجاد هدرهای مرورگر برای جلوگیری از مسدود شدن توسط فایروال سرور
    # ---------------------------------------------------------------------------------
    req = urllib.request.Request(
        TGJU_JSON_URL,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9,fa;q=0.8',
            'Referer': 'https://tgju.org/' # این هدر به سرور می‌گوید که ما از خود سایت ارجاع داده شده‌ایم
        }
    )
    
    max_retries = 3 # تعداد دفعات تلاش در صورت بروز خطای شبکه یا تایم‌اوت
    data = None
    
    # حلقه تلاش مجدد برای هندل کردن قطعی‌های لحظه‌ای یا خطاهای DNS
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status == 200:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    print("✅ Data fetched successfully!")
                    break # خروج از حلقه در صورت موفقیت
                else:
                    print(f"⚠️ Attempt {attempt+1} failed: HTTP Status {resp.status}")
        except urllib.error.URLError as e:
            # مدیریت خطاهای شبکه مانند [Errno -2] Name or service not known
            print(f"❌ Attempt {attempt+1} failed: Network or DNS Error ({getattr(e, 'reason', e)})")
        except Exception as e:
            # مدیریت سایر خطاهای غیر پیش‌بینی شده
            print(f"❌ Attempt {attempt+1} failed: Unknown Error ({e})")
        
        # در صورت شکست، ۵ ثانیه وقفه قبل از تلاش بعدی (به جز تلاش آخر)
        if attempt < max_retries - 1:
            print("⏳ Retrying in 5 seconds...")
            time.sleep(5)
            
    # اگر پس از تمامی تلاش‌ها باز هم دیتایی دریافت نشد، اجرای اسکریپت متوقف می‌شود
    if data is None:
        raise RuntimeError("Failed to fetch data from TGJU after multiple attempts. IP might be blocked by firewall.")
    # ---------------------------------------------------------------------------------
    
    # گرفتن دیتای اصلی (معمولاً داخل کلید current است)
    current = data.get("current") or data
    
    # استخراج قیمت ارزها بر اساس کلیدهای احتمالی
    usd_rial = get_symbol_price(current, ["price_dollar_rl", "price_dollar", "price_dollar_rl2"])
    eur_rial = get_symbol_price(current, ["price_eur", "price_euro", "price_eur_rl"])
    aed_rial = get_symbol_price(current, ["price_aed", "price_dirham", "price_aed_rl"])
    cny_rial = get_symbol_price(current, ["price_cny", "price_yuan", "price_cny_rl"])
    try_rial = get_symbol_price(current, ["price_try", "price_tl", "price_toman_try", "price_tl_rl"])
    
    # استخراج قیمت طلا 18 عیار و مثقال
    gram18_rial = get_symbol_price(current, ["geram18", "gram18", "geram_18", "gram18_rl"])
    mesghal_rial = get_symbol_price(
        current,
        [
            "mesghal", "mesghal_tala", "mesghal_gold", "mesghal18",
            "mazanne", "mozanne", "mozanneh", "mashghal",
            "price_mesghal", "price_mesghal_rl", "mesghal_rl"
        ]
    )
    
    # اگر قیمت دلار پیدا نشد، اسکریپت متوقف شود چون پایه محاسبات است
    if usd_rial is None:
        raise RuntimeError("Could not read USD price from TGJU (check symbol_key for USD).")
    
    # تبدیل همه قیمت‌های ریالی استخراج شده به تومان
    usd_local = to_toman(usd_rial)
    eur_local = to_toman(eur_rial)
    aed_local = to_toman(aed_rial)
    cny_local = to_toman(cny_rial)
    try_local = to_toman(try_rial)
    gram18_local = to_toman(gram18_rial)
    mesghal_local = to_toman(mesghal_rial)
    
    # سیستم Fallback (جایگزین اضطراری): اگر مثقال یافت نشد اما طلای 18 بود، مثقال را تقریبی حساب کن
    mesghal_from_fallback = False
    if (mesghal_local is None or mesghal_local <= 0) and (gram18_local and gram18_local > 0):
        mesghal_local = gram18_local * MESGHAL_TO_GRAM_APPROX
        mesghal_from_fallback = True
    
    # محاسبه انس جهانی و نسبت‌های طلای 18 عیار به دلار
    xau_struct = None
    if gram18_local and gram18_local > 0:
        per_gram_18k = gram18_local
        # محاسبه قیمت طلای 24 عیار داخلی از روی 18 عیار (نسبت 24 به 18)
        per_gram_24k_internal = per_gram_18k * (24.0 / 18.0)
        # محاسبه قیمت هر انس طلا به تومان
        per_ounce_local = per_gram_24k_internal * 31.1034768 
        usd_per_ounce = per_ounce_local / usd_local
        
        xau_struct = {
            "usd_per_ounce": round(usd_per_ounce, 2),       # انس بر حسب دلار
            "local_per_ounce": round(per_ounce_local, 2),   # انس بر حسب تومان
            "local_per_mesghal": round(mesghal_local, 2) if mesghal_local else None, # قیمت مثقال
            "local_per_gram_18k": round(per_gram_18k, 2),   # قیمت گرم 18 عیار
            "mesghal_source": "ajax.json" if not mesghal_from_fallback else f"fallback_from_gram18*{MESGHAL_TO_GRAM_APPROX}",
        }
    
    # تولید نسبت‌های تبدیل ارزها به دلار (FX)
    fx = {}
    if eur_local and eur_local > 0:
        fx["EURUSD"] = round(eur_local / usd_local, 6)
    if aed_local and aed_local > 0:
        fx["AEDUSD"] = round(aed_local / usd_local, 6)
    if try_local and try_local > 0:
        fx["TRYUSD"] = round(try_local / usd_local, 6)
    if xau_struct and xau_struct.get("local_per_ounce"):
        fx["XAUUSD"] = round(xau_struct["local_per_ounce"] / usd_local, 4)
    
    # ساختن خروجی نهایی برای ذخیره در فایل JSON (نرخ‌ها بر اساس تومان است)
    rates = {
        "USD": round(usd_local, 2),
    }
    
    # افزودن ارزهای دیگر به خروجی در صورت وجود
    if eur_local and eur_local > 0:
        rates["EUR"] = round(eur_local, 2)
    if aed_local and aed_local > 0:
        rates["AED"] = round(aed_local, 2)
    if cny_local and cny_local > 0:
        rates["CNY"] = round(cny_local, 2)
    if try_local and try_local > 0:
        rates["TRY"] = round(try_local, 2)
    
    # افزودن نرخ طلا 18 عیار به صورت مستقل به خروجی
    if gram18_local and gram18_local > 0:
        rates["GRAM18"] = round(gram18_local, 2)  
    
    # افزودن نرخ مثقال طلا به صورت مستقل به خروجی
    if mesghal_local and mesghal_local > 0:
        rates["MESGHAL"] = round(mesghal_local, 2)
    
    if xau_struct:
        rates["XAU"] = xau_struct
    
    if fx:
        rates["FX"] = fx 
    
    # آماده‌سازی پکیج نهایی JSON
    payload = {
        "success": True,
        "source": "tgju.org unofficial ajax.json (Toman)",
        "rates": rates,
    }
    
    # ذخیره در فایل rates.json
    with open("rates.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    
    print("rates.json updated successfully.")

if __name__ == "__main__":
    main()
