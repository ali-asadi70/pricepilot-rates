#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update.py: به‌روزرسانی نرخ‌های ارز و طلا (ساده‌شده اولیه).
فقط approx محلی + fallback API برای XAU. بدون scraping TGJU برای stability.
نویسنده: نسخه اولیه (2026-01-03).
"""

import json
import time
import os
import datetime
import urllib.request
import urllib.error
from http.client import RemoteDisconnected
import ssl
import gzip

# Constants
GOLDAPI_URL = "https://www.goldapi.io/api/XAU/USD"
RATES_FILE = "rates.json"
APPROX_GRAM18 = 14428000.0  # IRR/gram 18k (manual update daily from tgju.org)
APPROX_USD_LOCAL = 135650.0  # IRR/USD sell (manual update daily)
APPROX_XAU = 4431.0  # USD/oz spot (fallback)

def log_message(message, level="INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")

def create_ssl_context():
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context

class RedirectHandler(urllib.request.HTTPRedirectHandler):
    max_redirects = 10
    def http_error_301(self, req, fp, code, msg, headers):
        if 'Location' not in headers:
            raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)
        new_url = headers['Location']
        if new_url.startswith('/'):
            new_url = 'https://www.goldapi.io' + new_url
        log_message(f"Redirecting to: {new_url}")
        if self.max_redirects <= 0:
            raise urllib.error.HTTPError(req.full_url, code, "Infinite redirect", headers, fp)
        self.max_redirects -= 1
        new_req = urllib.request.Request(new_url, headers=req.headers)
        return self.parent.open(new_req)

def fetch_gold_fallback():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate',
        'Cache-Control': 'no-cache'
    }
    context = create_ssl_context()
    opener = urllib.request.build_opener(RedirectHandler(), urllib.request.HTTPSHandler(context=context))
    try:
        log_message("Fetching XAU from fallback API...")
        req = urllib.request.Request(GOLDAPI_URL, headers=headers)
        with opener.open(req, timeout=30) as resp:
            if resp.status == 200:
                raw = resp.read()
                if 'gzip' in resp.headers.get('Content-Encoding', ''):
                    raw = gzip.decompress(raw)
                import json
                data = json.loads(raw.decode('utf-8'))
                if "price" in data:
                    price = float(data["price"])
                    log_message(f"XAU from API: {price}")
                    return price
    except Exception as e:
        log_message(f"API failed: {str(e)}")
    log_message("Using approximate XAU.")
    return APPROX_XAU

def load_previous_rates():
    if os.path.exists(RATES_FILE):
        with open(RATES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"XAU": {"usd_per_ounce": APPROX_XAU}, "USD": {"irr": APPROX_USD_LOCAL}, "GRAM18": {"irr_per_gram": APPROX_GRAM18}}

def calculate_mesghal(gram18_price):
    return gram18_price * 8.133

def save_rates(rates):
    with open(RATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(rates, f, indent=2, ensure_ascii=False)
    log_message(f"{RATES_FILE} updated successfully.")

def main():
    log_message("Starting simple rates update (initial version)...")
    
    prev_rates = load_previous_rates()
    prev_gram18 = prev_rates.get("GRAM18", {}).get("irr_per_gram", APPROX_GRAM18)
    prev_xau = prev_rates.get("XAU", {}).get("usd_per_ounce", APPROX_XAU)
    prev_usd = prev_rates.get("USD", {}).get("irr", APPROX_USD_LOCAL)
    
    log_message(f"Previous: GRAM18={prev_gram18}, XAUUSD={prev_xau}, USD={prev_usd}")
    log_message(f"Using approx: GRAM18={APPROX_GRAM18}, USD={APPROX_USD_LOCAL}")
    
    # Get real XAU from API
    xau_usd = fetch_gold_fallback()
    
    mesghal_price = calculate_mesghal(APPROX_GRAM18)
    log_message(f"Mesghal calculated: {mesghal_price:.2f}")
    
    new_rates = {
        "timestamp": datetime.datetime.now().isoformat(),
        "XAU": {"usd_per_ounce": xau_usd},
        "USD": {"irr": APPROX_USD_LOCAL},
        "GRAM18": {"irr_per_gram": APPROX_GRAM18},
        "MESGHAL": {"irr": round(mesghal_price, 2)}
    }
    
    save_rates(new_rates)
    log_message("Update complete! (XAU real, others approx - manual update GRAM18/USD if needed)")

if __name__ == "__main__":
    main()
