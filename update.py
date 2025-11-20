#!/usr/bin/env python3
"""
PricePilot rates updater

هر اجرا:
- از API رایگان fawazahmed0/currency-api آخرین نرخ‌های USD می‌گیرد
- تومان هر واحد: USD, EUR, AED, CNY را حساب می‌کند
- قیمت طلا (XAU) را بر اساس تومان محاسبه می‌کند
- خروجی را در فایل rates.json در ریشه ریپو می‌نویسد
"""

import json
import sys
import math
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# دو آدرس برای فِچ کردن؛ یکی اصلی، یکی فالی‌بک
USD_BASE_URLS = [
    "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
    "https://latest.currency-api.pages.dev/v1/currencies/usd.json",
]

RATES_FILE = "rates.json"


def fetch_json(url: str) -> dict:
    """GET ساده با یوزر-ایجنت سفارشی و تبدیل به JSON."""
    req = Request(url, headers={"User-Agent": "PricePilotRatesBot/1.0"})
    with urlopen(req, timeout=20) as resp:
        status = resp.getcode()
        if status != 200:
            raise RuntimeError(f"HTTP {status} for {url}")
        body = resp.read().decode("utf-8")
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON decode error for {url}: {e}") from e
    return data


def fetch_usd_rates() -> dict:
    """
    سعی می‌کند از چند URL پشت‌سرهم دیتا بگیرد تا یکی جواب بدهد.
    خروجی: dict کامل JSON مربوط به usd.json
    """
    last_err = None
    for url in USD_BASE_URLS:
        try:
            print(f"[INFO] Fetching: {url}")
            data = fetch_json(url)
            # شکل دیتا باید شبیه { "date": "...", "usd": { "eur": ..., "irr": ... } }
            if not isinstance(data, dict) or "usd" not in data:
                raise RuntimeError("Unexpected JSON structure (no 'usd' key)")
            return data
        except (URLError, HTTPError, RuntimeError) as e:
            print(f"[WARN] Failed {url}: {e}", file=sys.stderr)
            last_err = e
    raise RuntimeError(f"All USD_BASE_URLS failed. Last error: {last_err}")


def build_pricepilot_payload() -> dict:
    """دیتا را از API می‌گیرد و به فرمت مخصوص افزونه تبدیل می‌کند."""
    data = fetch_usd_rates()
    usd_block = data.get("usd") or data.get("USD")
    if not isinstance(usd_block, dict):
        raise RuntimeError("Missing 'usd' rates object in JSON")

    def get_rate(code: str) -> float:
        v = usd_block.get(code.lower()) or usd_block.get(code.upper())
        if v is None:
            raise RuntimeError(f"Missing rate for {code}")
        return float(v)

    # 1) تومان هر دلار از نرخ USD -> IRR
    irr = get_rate("irr")  # مثلا 420000 ریال برای هر دلار
    toman_per_usd = irr / 10.0
    print(f"[INFO] IRR per USD: {irr}  ->  TOMAN per USD: {toman_per_usd}")

    rates_out = {}

    # USD
    rates_out["USD"] = round(toman_per_usd, 2)

    # 2) EUR / AED / CNY
    # در JSON داریم: 1 USD = X EUR  (usd_block["eur"] = x)
    # پس 1 EUR = 1/x USD → تومان هر یورو = toman_per_usd / x
    for code in ("eur", "aed", "cny"):
        try:
            per_unit_of_code = get_rate(code)  # X = code per 1 USD
            if per_unit_of_code <= 0:
                raise RuntimeError("non-positive")
            toman_per_code = toman_per_usd / per_unit_of_code
            rates_out[code.upper()] = round(toman_per_code, 2)
            print(f"[INFO] TOMAN per {code.upper()}: {toman_per_code}")
        except Exception as e:
            print(f"[WARN] Could not compute {code.upper()}: {e}", file=sys.stderr)
            rates_out[code.upper()] = 0.0

    # 3) طلا XAU
    xau_struct = None
    try:
        xau_per_usd = get_rate("xau")  # 1 USD = x XAU
        if xau_per_usd <= 0:
            raise RuntimeError("XAU rate non-positive")
        usd_per_ounce = 1.0 / xau_per_usd
        local_per_ounce = usd_per_ounce * toman_per_usd
        per_gram_24k = local_per_ounce / 31.1034768
        per_gram_18k = per_gram_24k * (18.0 / 24.0)

        xau_struct = {
            "usd_per_ounce": round(usd_per_ounce, 6),
            "local_per_ounce": round(local_per_ounce, 2),
            "local_per_gram_24k": round(per_gram_24k, 2),
            "local_per_gram_18k": round(per_gram_18k, 2),
        }

        print("[INFO] XAU computed:", xau_struct)
    except Exception as e:
        print(f"[WARN] Could not compute XAU: {e}", file=sys.stderr)
        xau_struct = None

    payload = {"success": True, "rates": rates_out}
    if xau_struct is not None:
        payload["rates"]["XAU"] = xau_struct

    return payload


def main() -> int:
    try:
        payload = build_pricepilot_payload()
    except Exception as e:
        print(f"[ERROR] Failed to build rates payload: {e}", file=sys.stderr)
        # اگر دوست داری موقع خطا هم یک فایل مینیمال ساخته شود:
        error_payload = {
            "success": False,
            "error": str(e),
        }
        with open(RATES_FILE, "w", encoding="utf-8") as f:
            json.dump(error_payload, f, ensure_ascii=False, indent=2)
        return 1

    # نوشتن در rates.json
    with open(RATES_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[OK] Rates written to {RATES_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
