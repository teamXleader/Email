import requests
import os
import re
import sys
import json
import time
import urllib.parse
import base64
import hashlib
import urllib3
import sqlite3
import io
import string
import random
import concurrent.futures
import threading
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, PreCheckoutQueryHandler
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
BOT_TOKEN = "8956981859:AAEjxBcufq6_7CtMx5_WakVuHaoZOQtPDz4"
OWNER_IDS = [8679993003, 8290865241]
CHANNEL_USERNAME = "@FREEFlRECODE"
CHANNEL_LINK = "https://t.me/FREEFlRECODE"
SUPPORT_LINK = "https://t.me/FREEFlRECODE"
DEV_CONTACT = "@FounderOfKrishna"
DB_PATH = "krishna_bot.db"
TOKENS_JSON_PATH = "access_tokens.json"
AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV = b'6oyZDr22E3ychjM%'
STARS_PRICE = 10
success_event = threading.Event()
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
def write_varint(value):
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)
def read_varint(data, offset):
    res = 0
    shift = 0
    while True:
        if offset >= len(data):
            break
        b = data[offset]
        offset += 1
        res |= (b & 0x7f) << shift
        if not (b & 0x80):
            break
        shift += 7
    return res, offset
def enc(data):
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(data if isinstance(data, bytes) else data.encode(), 16))
def dec(data):
    return unpad(AES.new(AES_KEY, AES.MODE_CBC, AES_IV).decrypt(data), 16)
def parse_protobuf_manually(data: bytes) -> dict:
    fields = {}
    stream = io.BytesIO(data)
    def read_varint_from_stream():
        v, shift = 0, 0
        while True:
            byte = stream.read(1)
            if not byte: break
            b = ord(byte)
            v |= (b & 0x7F) << shift
            shift += 7
            if not (b & 0x80): break
        return v
    while True:
        tag = read_varint_from_stream()
        if tag == 0: break
        fn, wt = tag >> 3, tag & 0x07
        if wt == 2:
            length = read_varint_from_stream()
            value = stream.read(length)
            fields[fn] = value.decode(errors='ignore')
        elif wt == 0:
            fields[fn] = read_varint_from_stream()
    return fields
def dict_to_protobuf_bytes(data: dict) -> bytes:
    def encode_varint(n: int) -> bytes:
        buf = bytearray()
        while True:
            towrite = n & 0x7F
            n >>= 7
            buf.append(towrite | 0x80 if n else towrite)
            if not n: break
        return bytes(buf)
    p = bytearray()
    for k, v in sorted(data.items()):
        f = int(k)
        if isinstance(v, int):
            p += encode_varint((f << 3)) + encode_varint(v)
        else:
            val = v.encode() if isinstance(v, str) else v
            p += encode_varint((f << 3) | 2) + encode_varint(len(val)) + val
    return bytes(p)
def encrypt_message(b: bytes) -> bytes:
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(b, AES.block_size))
def decrypt_message(b: bytes):
    try:
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        return unpad(cipher.decrypt(b), AES.block_size)
    except:
        return b
def convert_seconds(s):
    d = s // 86400
    h = (s % 86400) // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{d} Days {h} Hours {m} Min {sec} Sec"
PLATFORM_MAP = {1: "Garena", 3: "Facebook", 4: "Guest", 5: "VK", 6: "Huawei", 7: "Apple", 8: "Google", 10: "GameCenter / Line", 11: "X (Twitter)", 13: "Apple ID", 28: "Line", 35: "TikTok"}
def check_token_valid(access_token):
    try:
        api_url = f"https://api-otrss.garena.com/support/callback/?access_token={access_token}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(api_url, headers=headers, allow_redirects=True, timeout=15)
        parsed = urllib.parse.urlparse(res.url)
        params = urllib.parse.parse_qs(parsed.query)
        if 'access_token' in params:
            uid = params.get('account_id', ['Unknown'])[0]
            nickname = urllib.parse.unquote(params.get('nickname', ['Unknown'])[0])
            region = params.get('region', ['Unknown'])[0]
            return True, {"uid": uid, "nickname": nickname, "region": region}
        else:
            return False, None
    except:
        return False, None
def get_bind_info(access_token):
    try:
        url = "https://100067.connect.garena.com/game/account_security/bind:get_bind_info"
        payload = {'app_id': "100067", 'access_token': access_token}
        headers = {'User-Agent': "GarenaMSDK/4.0.19P9(Redmi Note 5 ;Android 9;en;US;)", 'Connection': "Keep-Alive"}
        response = requests.get(url, params=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None
def get_platform_info(access_token):
    try:
        url = "https://100067.connect.garena.com/bind/app/platform/info/get"
        params = {"access_token": access_token}
        headers = {"User-Agent": "GarenaMSDK/4.0.19P9(Redmi Note 5 ;Android 9;en;US;)", "Connection": "Keep-Alive"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None
def get_main_platform(access_token):
    try:
        url = "https://100067.connect.garena.com/oauth/token/inspect"
        params = {"token": access_token}
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, params=params, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            ext_type = data.get("external_type", 0)
            return PLATFORM_MAP.get(ext_type, f"Platform({ext_type})")
    except:
        pass
    return "Unknown"
def get_token_info(access_token):
    url = f"https://ffmconnect.live.gop.garenanow.com/oauth/token/inspect?token={access_token}"
    try:
        r = requests.get(url, verify=False, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("open_id"), str(data.get("platform"))
    except:
        pass
    return None, None
def try_generate_majortoken(input_token):
    callback_result = get_AccessToken_and_OpenID(input_token)
    if not callback_result.get("success"):
        return {"status": "callback_failed", "error": callback_result.get("error", "Callback failed")}    
    real_access_token = callback_result["real_access_token"]
    open_id, platform = get_token_info(real_access_token)    
    if not open_id:
        return {"status": "inspect_failed", "error": "Could not get open_id from inspect"}    
    data = {"7": "2.127.3", "22": open_id, "29": real_access_token, "99": platform}
    encrypted = encrypt_message(dict_to_protobuf_bytes(data))    
    headers = {
        'User-Agent': 'UnityPlayer/2022.3.47f1',
        'X-Ga': 'v1 1',
        'Releaseversion': 'ob54',
        'Content-Type': 'application/octet-stream',
        'X-Unity-Version': '2022.3.47f1',
    }    
    try:
        r = requests.post("https://loginbp.ggblueshark.com/MajorLogin",
                          data=encrypted, headers=headers, verify=False, timeout=15)        
        if r.status_code == 200 and r.content:
            decrypted = decrypt_message(r.content)
            parsed = parse_protobuf_manually(decrypted)
            token = parsed.get(8)            
            if token:
                return {
                    "status": "success",
                    "token": token,
                    "real_access_token": real_access_token,
                    "account_id": callback_result.get("account_id"),
                    "nickname": callback_result.get("nickname"),
                    "region": callback_result.get("region"),
                    "open_id": open_id,
                    "platform": platform
                }
            else:
                return {"status": "parse_failed", "error": "Could not parse MajorLogin token"}                
    except Exception as e:
        return {"status": "request_failed", "error": str(e)}    
    return {"status": "failed", "error": "MajorLogin request returned empty response"}
def get_AccessToken_and_OpenID(input_token):
    try:
        callback_url = f"https://api-otrss.garena.com/support/callback/?access_token={input_token}"
        headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 10)", "Accept": "*/*"}
        response = requests.get(callback_url, headers=headers, allow_redirects=False, timeout=10)        
        if 300 <= response.status_code < 400 and "Location" in response.headers:
            redirect_url = response.headers["Location"]
            parsed_url = urlparse(redirect_url)
            query_params = parse_qs(parsed_url.query)            
            real_access_token = query_params.get("access_token", [None])[0]
            account_id = query_params.get("account_id", [None])[0]
            nickname = query_params.get("nickname", [None])[0]
            region = query_params.get("region", [None])[0]            
            if not real_access_token or not account_id:
                return {"success": False, "error": "Token extraction failed"}            
            return {
                "success": True,
                "real_access_token": real_access_token,
                "account_id": account_id,
                "nickname": nickname,
                "region": region
            }
    except Exception as e:
        return {"success": False, "error": str(e)}
    return {"success": False, "error": "Redirect not received"}
def get_update_url(region):
    if region == "IND":
        return "https://client.ind.freefiremobile.com/UpdateSocialBasicInfo"
    elif region in {"BR", "US", "SAC", "NA"}:
        return "https://client.us.freefiremobile.com/UpdateSocialBasicInfo"
    else:
        return "https://clientbp.ggpolarbear.com/UpdateSocialBasicInfo"
def encrypt_api(plain_text):
    plain_text = bytes.fromhex(plain_text)
    key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
    iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(plain_text, AES.block_size)).hex()
def create_dynamic_protobuf():
    try:
        from google.protobuf.descriptor_pb2 import DescriptorProto, FieldDescriptorProto, FileDescriptorProto
        from google.protobuf.message_factory import GetMessages        
        descriptor = DescriptorProto()
        descriptor.name = "DynamicMessage"
        field = descriptor.field.add()
        field.name = "field_8"
        field.number = 8
        field.label = FieldDescriptorProto.LABEL_OPTIONAL
        field.type = FieldDescriptorProto.TYPE_STRING
        file_descriptor = FileDescriptorProto()
        file_descriptor.name = "dynamic.proto"
        file_descriptor.message_type.append(descriptor)
        messages = GetMessages([file_descriptor])
        return messages["DynamicMessage"]
    except:
        return None
def encode_protobuf(field_8_value):
    try:
        message_class = create_dynamic_protobuf()
        if message_class:
            message = message_class()
            message.field_8 = field_8_value
            return message.SerializeToString().hex()
    except:
        pass
    field_8_bytes = field_8_value.encode('utf-8')
    tag = (8 << 3) | 2
    result = write_varint(tag) + write_varint(len(field_8_bytes)) + field_8_bytes
    return result.hex()
def update_bio_api(main_token, user_bio, region="IND"):
    if not main_token or not user_bio:
        return "Both token and bio are required."
    encoded_bio = encode_protobuf(user_bio)
    encrypted_data = encrypt_api(f'1011{encoded_bio}5a006200')
    url = get_update_url(region)
    headers = {
        'Expect': '100-continue',
        'Authorization': f'Bearer {main_token}',
        'X-Unity-Version': '2018.4.11f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB54',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; Redmi Note 5 MIUI/V11.0.3.0.PEIMIXM)',
        'Host': 'clientbp.ggblueshark.com',
        'Connection': 'Keep-Alive',
        'Accept-Encoding': 'gzip'
    }
    try:
        response = requests.post(url, data=bytes.fromhex(encrypted_data), headers=headers, verify=False, timeout=15)
        if response.status_code == 200:
            return "success"
        else:
            return f"Request failed: {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"
def revoke_token_api(access_token, refresh_token=None):
    if not access_token:
        return "Access token is required."
    if not refresh_token:
        refresh_token = "1380dcb63ab3a077dc05bdf0b25ba4497c403a5b4eae96d7203010eafa6c83a8"
    logout_url = f"https://100067.connect.garena.com/oauth/logout?access_token={access_token}&refresh_token={refresh_token}"
    headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 10)", "Accept": "*/*"}
    try:
        r = requests.get(logout_url, headers=headers, verify=False, timeout=10)
        if r.status_code in [200, 204]:
            return "success"
        else:
            return f"Logout request sent. Status: {r.status_code}"
    except Exception as e:
        return f"Error: {e}"
def is_valid_email(email: str) -> bool:
    if not email or len(email.strip()) > 254:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))    
def generate_username(length=12):
    letters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters) for _ in range(length))
def get_timestamp_id():
    return int(time.time() * 1000)        
def get_fresh_datadome():
    url = "https://datadome.garena.com/js/"    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://sso.garena.com/universal/register?locale=en-SG"
    }    
    payload = {
        "jsType": "le",
        "eventCounters": '{"mousemove":1,"click":1,"keydown":11}',
        "ddk": "AE3F04AD3F0D3A462481A337485081",
        "Referer": "https://sso.garena.com/universal/register?locale=en-SG",
        "request": "/universal/register?locale=en-SG",
        "responsePage": "origin",
        "ddv": "5.7.0"
    }
    try:
        r = requests.post(url, headers=headers, data=payload, timeout=15, verify=False)
        result = r.json()
        cookie_string = result.get('cookie', '')
        if 'datadome=' in cookie_string:
            for part in cookie_string.split(';'):
                if 'datadome=' in part:
                    cookie = part.replace('datadome=', '').strip()
                    return cookie
    except:
        pass
    return None
def send_otp_api(email: str):
    email = email.strip()
    if not is_valid_email(email):
        return None, "Invalid email format"            
    datadome = get_fresh_datadome()
    if not datadome:
        return None, "No DataDome cookie"        
    cookies = [
        "_ga=GA1.1.868059803.1775926376",
        "_ga_XB5PSHEQB4=GS2.1.s1775926375$o1$g1$t1775926378$j57$l0$h0",
        f"datadome={datadome}"
    ]    
    cookie_header = "; ".join(cookies)
    headers = {
        "Host": "authgop.garena.com",
        "Connection": "keep-alive",
        "sec-ch-ua-platform": "Linux",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "sec-ch-ua-mobile": "?0",
        "Origin": "https://authgop.garena.com",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://authgop.garena.com/universal/register?redirect_uri=https://authgop.garena.com/universal/register",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en-IN;q=0.9,en;q=0.8,hi;q=0.7,vi;q=0.6",
        "Cookie": cookie_header
    }
    username = generate_username()
    request_id = get_timestamp_id()
    payload = {
        "username": username,
        "email": email,
        "locale": "en-SG",
        "format": "json",
        "id": request_id
    }

    try:
        response = requests.post(
            "https://authgop.garena.com/api/send_register_code_email",
            data=payload,
            headers=headers,
            verify=False,
            timeout=15
        )
        return response, None
    except Exception as e:
        return None, str(e)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        access_token TEXT, last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        access_token TEXT UNIQUE, account_info TEXT,
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS banned (
        user_id INTEGER PRIMARY KEY, reason TEXT,
        banned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS maintenance (
        id INTEGER PRIMARY KEY CHECK(id = 1), status INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS all_chats (
        chat_id INTEGER PRIMARY KEY, chat_type TEXT, title TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS pending_revoke (
        user_id INTEGER PRIMARY KEY, access_token TEXT, nickname TEXT, 
        account_id TEXT, timestamp TEXT)''')
    c.execute('''INSERT OR IGNORE INTO maintenance (id, status) VALUES (1, 0)''')
    conn.commit()
    conn.close()
def is_banned(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM banned WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None
def is_maintenance():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT status FROM maintenance WHERE id = 1")
    result = c.fetchone()
    conn.close()
    return result and result[0] == 1
def set_maintenance(status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE maintenance SET status = ? WHERE id = 1", (1 if status else 0,))
    conn.commit()
    conn.close()
def ban_user(user_id, reason="No reason"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO banned (user_id, reason) VALUES (?, ?)", (user_id, reason))
    conn.commit()
    conn.close()
def unban_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM banned WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
def add_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)''', (user_id, username, first_name))
    conn.commit()
    conn.close()
def add_chat(chat_id, chat_type, title=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO all_chats (chat_id, chat_type, title) VALUES (?, ?, ?)''', (chat_id, chat_type, title))
    conn.commit()
    conn.close()
def save_token_json(tokens_data):
    try:
        with open(TOKENS_JSON_PATH, 'w') as f:
            json.dump(tokens_data, f, indent=2)
    except:
        pass
def add_token_entry(user_id, access_token, account_info=""):
    if token_exists(access_token):
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''INSERT OR IGNORE INTO tokens (user_id, access_token, account_info) VALUES (?, ?, ?)''', (user_id, access_token, account_info))
        conn.commit()
        conn.close()
        update_tokens_json()
        return True
    except:
        conn.close()
        return False
def update_tokens_json():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM tokens ORDER BY added_date DESC")
    rows = c.fetchall()
    conn.close()
    tokens_data = []
    for row in rows:
        tokens_data.append({"id": row[0], "user_id": row[1], "access_token": row[2], "account_info": row[3], "added_date": row[4] if len(row) > 4 else ""})
    save_token_json(tokens_data)
def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, username, first_name, join_date, last_active FROM users ORDER BY join_date DESC")
    rows = c.fetchall()
    conn.close()
    return rows
def get_all_tokens():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM tokens ORDER BY added_date DESC")
    rows = c.fetchall()
    conn.close()
    return rows
def get_all_chats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT chat_id, chat_type, title FROM all_chats")
    rows = c.fetchall()
    conn.close()
    return rows
def get_banned_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, reason, banned_date FROM banned ORDER BY banned_date DESC")
    rows = c.fetchall()
    conn.close()
    return rows
def is_owner(user_id):
    return user_id in OWNER_IDS
def token_exists(access_token):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM tokens WHERE access_token = ?", (access_token,))
    result = c.fetchone()
    conn.close()
    return result is not None
def save_pending_revoke(user_id, access_token, nickname, account_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO pending_revoke (user_id, access_token, nickname, account_id, timestamp) VALUES (?, ?, ?, ?, ?)",
              (user_id, access_token, nickname, account_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
def get_pending_revoke(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT access_token, nickname, account_id FROM pending_revoke WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row
def delete_pending_revoke(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM pending_revoke WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
def get_main_keyboard(is_owner_user=False):
    buttons = [
        ["Check Recovery Email", "Add Recovery Email"],
        ["Check Platform", "Cancel Recovery Email"],
        ["Unbind Email", "Change Bind Email"],
        ["Update Bio", "Eat Token Website"],
        ["Revoke Access Token"], 
        ["Send Single Unsubscribe OTP"],
        ["Contact Owner"]
    ]
    if is_owner_user:
        buttons.append(["Bot Management"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
def get_owner_keyboard():
    buttons = [
        ["View Users", "View Tokens"],
        ["Ban User", "Unban User"],
        ["Broadcast"],        
        ["Download Tokens JSON"],        
        ["Toggle Maintenance"],
        ["Back to Main"]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
def get_unbind_keyboard():
    return ReplyKeyboardMarkup([
        ["Via Email OTP", "Via Security Code"],
        ["Back to Main"]
    ], resize_keyboard=True)
def get_change_keyboard():
    return ReplyKeyboardMarkup([
        ["Via Email OTP", "Via Security Code"],
        ["Back to Main"]
    ], resize_keyboard=True)
def get_back_keyboard():
    return ReplyKeyboardMarkup([["Back to Main"]], resize_keyboard=True)
def get_support_inline():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Support Channel", url=SUPPORT_LINK)]
    ])
def get_user_state(context, user_id):
    if 'user_states' not in context.bot_data:
        context.bot_data['user_states'] = {}
    return context.bot_data['user_states'].get(user_id)
def set_user_state(context, user_id, action, step=0, data=None):
    if 'user_states' not in context.bot_data:
        context.bot_data['user_states'] = {}
    state = {'action': action, 'step': step}
    if data:
        state.update(data)
    context.bot_data['user_states'][user_id] = state
async def show_main_menu_after(update, context, custom_text=None):
    user = update.effective_user
    text = custom_text or "Main Menu - Please select an option:"
    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard(is_owner(user.id))
    )
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    add_chat(chat.id, chat.type, chat.title or user.full_name or "")
    add_user(user.id, user.username, user.first_name)
    if is_banned(user.id):
        await update.message.reply_text(
            f"🚫 *You are banned from using this bot!*\n\nContact: {DEV_CONTACT}",
            parse_mode="Markdown"
        )
        return
    try:
        member = await context.bot.get_chat_member(
            chat_id=CHANNEL_USERNAME,
            user_id=user.id
        )
        if member.status in ["left", "kicked"]:
            raise Exception("Not joined")
    except Exception:
        join_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Leader Updates", url=CHANNEL_LINK)],
            [InlineKeyboardButton("I Have Joined", callback_data="check_join")]
        ])
        await update.message.reply_text(
            "*Join Verification Required*\n\n"
            "To use this bot, you must join the following channel first:\n\n"
            "• Leader Updates ✞\n\n"
            "After joining, click the button below to verify.",
            parse_mode="Markdown",
            reply_markup=join_keyboard
        )
        return
    await update.message.reply_text(
        f"*Welcome {user.first_name}!*\n\n"
        "*You have successfully verified!*\n\n"
        "*Select an option from the menu below to get started:*",
        parse_mode="Markdown",
        reply_markup=get_support_inline()
    )
    await show_main_menu_after(
        update,
        context,
        "Main Menu - Please select an option:"
    )
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    add_chat(chat.id, chat.type, chat.title or user.full_name or "")
    add_user(user.id, user.username, user.first_name)
    if is_banned(user.id):
        await update.message.reply_text(
            f"🚫 *You are banned from using this bot!*\n\nContact: {DEV_CONTACT}",
            parse_mode="Markdown"
        )
        return
    try:
        member = await context.bot.get_chat_member(
            chat_id=CHANNEL_USERNAME,
            user_id=user.id
        )
        if member.status in ["left", "kicked"]:
            raise Exception("Not joined")
    except Exception:
        join_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Leader Updates", url=CHANNEL_LINK)],
            [InlineKeyboardButton("I Have Joined", callback_data="check_join")]
        ])
        await update.message.reply_text(
            "*Join Verification Required*\n\n"
            "To use this bot, you must join the following channel first:\n\n"
            "~ Leader Updates ✞\n\n"
            "After joining, click the button below to verify.",
            parse_mode="Markdown",
            reply_markup=join_keyboard
        )
        return
    await update.message.reply_text(
        f"*Please select an option from the menu first.*",
        parse_mode="Markdown",
        reply_markup=get_support_inline()
    )
    await show_main_menu_after(
        update,
        context,
        "Main Menu - Please select an option:"
    )    
async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user    
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user.id)
        if member.status in ['left', 'kicked']:
            await query.answer("You haven't joined all channel yet!", show_alert=True)
            return
    except:
        await query.answer("Could not verify. Make sure you've joined!", show_alert=True)
        return    
    await query.answer("Verification! successful!")
    await query.message.delete()
    await query.message.reply_text(
        "Main Menu - Please select an option:",
        reply_markup=get_main_keyboard(is_owner(user.id))
    )
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data    
    if data == "check_join":
        await check_join_callback(update, context)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()    
    add_user(user.id, user.username, user.first_name)    
    if is_banned(user.id):
        await update.message.reply_text("🚫 *You are banned from using this bot!*\n\nContact: " + DEV_CONTACT, parse_mode='Markdown')
        return    
    if is_maintenance() and not is_owner(user.id):
        await update.message.reply_text("🔧 *Bot is under maintenance!*\n\nPlease contact: " + DEV_CONTACT, parse_mode='Markdown')
        return
    if not is_owner(user.id):
        try:
            member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user.id)
            if member.status in ['left', 'kicked']:
                raise Exception("Not joined")
        except:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Join Leader Updates", url=CHANNEL_LINK)],
                [InlineKeyboardButton("I Have Joined", callback_data="check_join")]
            ])
            await update.message.reply_text(
            "*Join Verification Required*\n\n"
            "To use this bot, you must join the following channel first:\n\n"
            "~ Leader Updates ✞\n\n"
            "After joining, click the button below to verify.",
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            return
    state = get_user_state(context, user.id)
    if state:
        await handle_state(update, context, state, text)
        return
    clean_text = text
    if text.startswith("@"):
        clean_text = text[1:]
    if clean_text in ["Check Recovery Email", "Check Recovery Email"]:
        set_user_state(context, user.id, 'check_recovery', 0)
        await update.message.reply_text(
            "*Check Recovery Email*\n\nPlease enter your access token:",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )    
    elif clean_text in ["Add Recovery Email", "Add Recovery Email"]:
        set_user_state(context, user.id, 'add_recovery', 0)
        await update.message.reply_text(
            "*Add Recovery Email*\n\nPlease enter your email address:",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )    
    elif clean_text in ["Check Platform", "Check Platform"]:
        set_user_state(context, user.id, 'check_platform', 0)
        await update.message.reply_text(
            "*Check Platform*\n\nPlease enter your access token:",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )    
    elif clean_text in ["Cancel Recovery Email", "Cancel Recovery Email"]:
        set_user_state(context, user.id, 'cancel_recovery', 0)
        await update.message.reply_text(
            "*Cancel Recovery Email*\n\nPlease enter your access token:",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )   
    elif clean_text in ["Unbind Email", "Unbind Email"]:
        set_user_state(context, user.id, 'unbind_method', 'method_select')
        await update.message.reply_text(
            "*Unbind Email - Select Method:*",
            parse_mode='Markdown',
            reply_markup=get_unbind_keyboard()
        )    
    elif clean_text in ["Change Bind Email", "Change Bind Email"]:
        set_user_state(context, user.id, 'change_bind', 'method_select')
        await update.message.reply_text(
            "*Change Bind Email - Select Method:*",
            parse_mode='Markdown',
            reply_markup=get_change_keyboard()
        )    
    elif clean_text in ["Update Bio", "Update Bio"]:
        set_user_state(context, user.id, 'update_bio_token', 0)
        await update.message.reply_text(
            "*Update Bio*\n\nPlease enter your access token:",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )    
    elif clean_text in ["Eat Token Website", "Eat Token Website"]:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Visit Eat Token Website", url="https://discstore.recargajogo.com.br/")]
        ])
        await update.message.reply_text(
            "*Eat Token Website*\n\n"
            "Click the button below to visit the website to get your Eat Token/Access Token.\n\n"
            "Then enter your access token below:",
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        set_user_state(context, user.id, 'eat_token', 0)    
    elif clean_text in ["Revoke Access Token", "Revoke Access Token"]:
        set_user_state(context, user.id, 'revoke_token', 0)
        await update.message.reply_text(
            "*Revoke Access Token*\n\nPlease enter your access token:",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )    
    elif clean_text in ["Send Single Unsubscribe OTP", "Unsubscribe OTP"]:
        set_user_state(context, user.id, 'unsubscribe_otp', 0)
        await update.message.reply_text(
            "*Send Single Unsubscribe OTP*\n\nPlease enter your email address:",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )    
    elif clean_text == "Contact Owner":
        info = (
            "├ *Developer:* `Krishna Coder`\n"
            "├ *Telegram:* @FounderOfKrishna\n"
            "├ *Channel:* t.me/FREEFlRECODE\n"
            "└ Version: `v2.0 (Premium)`\n\n"
            "📝 *Note:*\n"
            "Thank you for using Krishna Coder Bind Tool!\n"
            "Report bugs on Telegram."
        )
        await update.message.reply_text(info, parse_mode='Markdown', reply_markup=get_support_inline())
        await show_main_menu_after(update, context)    
    elif clean_text == "Bot Management" and is_owner(user.id):
        await update.message.reply_text(
            "⚙️ *OWNER PANEL*\n\nSelect an option:",
            parse_mode='Markdown',
            reply_markup=get_owner_keyboard()
        )    
    elif clean_text == "Back to Main":
        await show_main_menu_after(update, context)
    elif clean_text == "View Users" and is_owner(user.id):
        users = get_all_users()
        msg = f"👥 *All Users ({len(users)})*\n\n"
        if not users:
            msg += "No users yet."
        else:
            for i, u in enumerate(users[:30], 1):
                uid, username, fname, join_date, last_active = u
                msg += f"*{i}.* `{uid}` | @{username} | {fname}\n├ Joined: `{join_date}`\n└ Active: `{last_active}`\n\n"
        if len(users) > 30:
            msg += f"...and {len(users) - 30} more"
        await update.message.reply_text(msg[:4000], parse_mode='Markdown', reply_markup=get_owner_keyboard())    
    elif clean_text == "View Tokens" and is_owner(user.id):
        tokens = get_all_tokens()
        msg = f"🔑 *All Stored Tokens ({len(tokens)})*\n\n"
        if not tokens:
            msg += "No tokens stored yet."
        else:
            for i, t in enumerate(tokens[:20], 1):
                tid, uid, token, info, date = t
                msg += f"*{i}.* User: `{uid}`\n├ Token: `{token[:30]}...`\n├ Info: `{info[:50] if info else 'N/A'}`\n└ Date: `{date}`\n\n"
        if len(tokens) > 20:
            msg += f"...and {len(tokens) - 20} more"
        await update.message.reply_text(msg[:4000], parse_mode='Markdown', reply_markup=get_owner_keyboard())    
    elif clean_text == "Download Tokens JSON" and is_owner(user.id):
        update_tokens_json()
        try:
            with open(TOKENS_JSON_PATH, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=TOKENS_JSON_PATH,
                    caption="📥 *Tokens JSON file*",
                    parse_mode='Markdown'
                )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
        await update.message.reply_text("⚙️ *OWNER PANEL*", parse_mode='Markdown', reply_markup=get_owner_keyboard())    
    elif clean_text == "Broadcast" and is_owner(user.id):
        set_user_state(context, user.id, 'owner_broadcast', 0)
        await update.message.reply_text(
            "📢 *Broadcast Mode*\n\nSend the message you want to broadcast to all users and chats.\n\n*Note:* Sends to all users, groups, and channels the bot has seen.",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )    
    elif clean_text == "Ban User" and is_owner(user.id):
        bans = get_banned_users()
        ban_text = ""
        if bans:
            ban_text = "\n*Currently Banned:*\n"
            for u in bans:
                ban_text += f"├ `{u[0]}` - {u[1][:30]}\n"        
        set_user_state(context, user.id, 'owner_ban', 0)
        await update.message.reply_text(
            f"🚫 *Ban / Unban Management*\n\nSend:\n`ban USER_ID REASON` (to ban)\n`unban USER_ID` (to unban)\n\nExample: `ban 123456789 Spam`{ban_text}",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )    
    elif clean_text == "Unban User" and is_owner(user.id):
        set_user_state(context, user.id, 'owner_unban', 0)
        await update.message.reply_text(
            "✅ *Unban User*\n\nEnter the User ID to unban:\n\nExample: `123456789`",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )    
    elif clean_text == "Toggle Maintenance" and is_owner(user.id):
        current = is_maintenance()
        new_status = 0 if current else 1
        set_maintenance(new_status)
        status_text = "🟢 ON" if new_status else "🔴 OFF"
        await update.message.reply_text(
            f"🔧 *Maintenance Mode*\n\nCurrent status: *{status_text}*",
            parse_mode='Markdown',
            reply_markup=get_owner_keyboard()
        )    
    else:
        await update.message.reply_text(
            "❌ Invalid option! Use the keyboard buttons below.",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(is_owner(user.id))
        )
async def handle_state(update, context, state, text):
    user = update.effective_user
    action = state['action']
    step = state['step']
    if text == "Back to Main":
        if user.id in context.bot_data.get('user_states', {}):
            del context.bot_data['user_states'][user.id]
        await show_main_menu_after(update, context)
        return
    if action == "check_recovery" and step == 0:
        access_token = text
        valid, info = check_token_valid(access_token)
        if not valid:
            await update.message.reply_text(
                "*Invalid access token:* Missing parameters in redirect",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            await show_main_menu_after(update, context, "Main Menu - Please select an option:")
            del context.bot_data['user_states'][user.id]
            return        
        nickname = info['nickname']
        bind_data = get_bind_info(access_token)        
        if bind_data:
            email = bind_data.get("email", "")
            email_to_be = bind_data.get("email_to_be", "")
            countdown = bind_data.get("request_exec_countdown", 0)            
            if email_to_be and not email:
                result = (
                    f"*Email Status for {nickname}*\n\n"
                    f"Confirmed Email: `No Email Bound`\n"
                    f"Pending Email: `{email_to_be}`\n"
                    f"Confirm After: `{convert_seconds(countdown)}`\n"
                    f"Status: *Pending Change*"
                )
            elif email:
                result = (
                    f"*Email Status for {nickname}*\n\n"
                    f"Confirmed Email: `{email}`\n"
                    f"Status: *Email Confirmed*"
                )
            else:
                result = (
                    f"*Email Status for {nickname}*\n\n"
                    f"Confirmed Email: `No Email Bound`\n"
                    f"Status: *No Email*"
                )
        else:
            result = f"*Email Status for {nickname}*\n\nNo bind information available."        
        add_token_entry(user.id, access_token, f"Check Email: {nickname}")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=get_support_inline())
        await show_main_menu_after(update, context)
        del context.bot_data['user_states'][user.id]
    elif action == "add_recovery" and step == 0:
        email = text
        if '@' not in email or '.' not in email:
            await update.message.reply_text(
                "*Invalid email format.* Please enter a valid email address:",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            return        
        set_user_state(context, user.id, 'add_recovery', 1, {'email': email})
        await update.message.reply_text(
            f"*Email saved.* Now please enter your access token:",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )    
    elif action == "add_recovery" and step == 1:
        access_token = text
        email = state['email']        
        valid, info = check_token_valid(access_token)
        if not valid:
            await update.message.reply_text(
                "*Invalid access token:* Missing parameters in redirect",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            await show_main_menu_after(update, context, "Main Menu - Please select an option:")
            del context.bot_data['user_states'][user.id]
            return        
        nickname = info['nickname']
        uid = info['uid']
        bind_data = get_bind_info(access_token)
        if bind_data and bind_data.get("email", ""):
            bound_email = bind_data["email"]
            result = (
                f"*Email Already Bound!*\n\n"
                f"Account: `{nickname}`\n"
                f"ID: `{uid}`\n"
                f"Bound Email: `{bound_email}`\n\n"
                f"Status: This account already has a recovery email bound.\n"
                f"Use 'Unbind Email' or 'Change Bind Email' options instead."
            )
            await update.message.reply_text(result, parse_mode='Markdown', reply_markup=get_support_inline())
            await show_main_menu_after(update, context)
            del context.bot_data['user_states'][user.id]
            return
        set_user_state(context, user.id, 'add_recovery', 2, {
            'access_token': access_token, 
            'email': email, 
            'info': info
        })
        await update.message.reply_text(
            f"*Token validated!*\n\n"
            f"Account: `{nickname}`\n"
            f"ID: `{uid}`\n"
            f"Region: `{info['region']}`\n\n"
            f"Please enter your *6-digit security code*:",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )    
    elif action == "add_recovery" and step == 2:
        security_code = text
        access_token = state['access_token']
        email = state['email']
        info = state['info']
        nickname = info['nickname']        
        hashed_sec = hashlib.sha256(security_code.encode('utf-8')).hexdigest()
        headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}        
        try:
            send_url = "https://100067.connect.garena.com/game/account_security/bind:send_otp"
            send_data = {"email": email, "locale": "en_PK", "region": "PK", "app_id": "100067", "access_token": access_token}
            resp = requests.post(send_url, headers=headers, data=send_data, timeout=15)
            if resp.status_code != 200 or '"result":0' not in resp.text.replace(" ", ""):
                await update.message.reply_text(
                    f"*Failed to send OTP:* {resp.text[:100]}",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                await show_main_menu_after(update, context, "Main Menu - Please select an option:")
                del context.bot_data['user_states'][user.id]
                return            
            set_user_state(context, user.id, 'add_recovery', 3, {
                'access_token': access_token,
                'email': email,
                'info': info,
                'security_code': hashed_sec
            })            
            await update.message.reply_text(
                f"*Security code verified!*\n\n"
                f"*Sending OTP to* `{email}`*...*",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            await update.message.reply_text(
                f"*OTP sent to* `{email}`\n\nPlease enter the OTP:",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
        except Exception as e:
            await update.message.reply_text(
                f"*Error:* {str(e)}",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            await show_main_menu_after(update, context, "Main Menu - Please select an option:")
            del context.bot_data['user_states'][user.id]    
    elif action == "add_recovery" and step == 3:
        # Step 3: Verify OTP and bind
        otp = text
        access_token = state['access_token']
        email = state['email']
        info = state['info']
        hashed_sec = state['security_code']
        nickname = info['nickname']        
        await update.message.reply_text("*Verifying OTP and binding email...*", parse_mode='Markdown')
        headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}        
        try:
            verify_url = "https://100067.connect.garena.com/game/account_security/bind:verify_otp"
            verify_data = {"app_id": "100067", "access_token": access_token, "email": email, "code": otp, "otp": otp, "type": "1"}
            resp = requests.post(verify_url, headers=headers, data=verify_data, timeout=15)
            verifier_token = ""
            try:
                verifier_token = resp.json().get("verifier_token", "")
            except:
                pass            
            if not verifier_token:
                await update.message.reply_text(
                    "❌ *OTP verification failed!* Invalid OTP.",
                    parse_mode='Markdown',
                    reply_markup=get_main_keyboard(is_owner(user.id))
                )
                del context.bot_data['user_states'][user.id]
                return            
            bind_url = "https://100067.connect.garena.com/game/account_security/bind:create_bind_request"
            bind_data = {"email": email, "app_id": "100067", "access_token": access_token, "verifier_token": verifier_token, "secondary_password": hashed_sec}
            resp = requests.post(bind_url, headers=headers, data=bind_data, timeout=15)            
            if resp.status_code == 200 and '"result":0' in resp.text.replace(" ", ""):
                await update.message.reply_text(
                    f"✅ *Recovery email added successfully!*\n\n"
                    f"Email: `{email}`\n"
                    f"Account: `{nickname}`",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                add_token_entry(user.id, access_token, f"Added Email: {email} for {nickname}")
            else:
                await update.message.reply_text(
                    f"❌ *Failed to bind email:* {resp.text[:200]}",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
        except Exception as e:
            await update.message.reply_text(
                f"❌ *Error:* {str(e)}",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )        
        await show_main_menu_after(update, context)
        del context.bot_data['user_states'][user.id]
    elif action == "check_platform" and step == 0:
        access_token = text
        valid, info = check_token_valid(access_token)
        if not valid:
            await update.message.reply_text(
                "*Invalid access token:* Missing parameters in redirect",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            await show_main_menu_after(update, context, "Main Menu - Please select an option:")
            del context.bot_data['user_states'][user.id]
            return        
        nickname = info['nickname']
        platform_data = get_platform_info(access_token)
        main_platform = get_main_platform(access_token)        
        result = f"*Platform Info for {nickname}*\n\n*Secondary Links:*\n"
        if platform_data:
            bounded = platform_data.get("bounded_accounts", [])
            if not bounded:
                result += "No Secondary Links Found!\n"
            else:
                for p_id in bounded:
                    p_name = PLATFORM_MAP.get(p_id, f"Unknown ({p_id})")
                    if p_name.lower() != main_platform.lower():
                        result += f"├ `{p_name}`\n"
        else:
            result += "No Secondary Links Found!\n"
        result += f"\n*Main Platform:* `{main_platform}`"        
        add_token_entry(user.id, access_token, f"Check Platform: {nickname}")
        await update.message.reply_text(result, parse_mode='Markdown', reply_markup=get_support_inline())
        await show_main_menu_after(update, context)
        del context.bot_data['user_states'][user.id]
    elif action == "cancel_recovery" and step == 0:
        access_token = text
        valid, info = check_token_valid(access_token)
        if not valid:
            await update.message.reply_text(
                "*Invalid access token:* Missing parameters in redirect",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            await show_main_menu_after(update, context)
            del context.bot_data['user_states'][user.id]
            return        
        nickname = info['nickname']
        uid = info['uid']        
        bind_data = get_bind_info(access_token)
        email_to_be = bind_data.get("email_to_be", "") if bind_data else ""        
        if email_to_be:
            await update.message.reply_text(
                f"*Pending Email Found!*\n\n"
                f"Account: `{nickname}`\n"
                f"ID: `{uid}`\n"
                f"Pending Email: `{email_to_be}`\n\n"
                f"*Cancelling pending request...*",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            try:
                url = "https://100067.connect.garena.com/game/account_security/bind:cancel_request"
                headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
                data = {"app_id": "100067", "access_token": access_token}
                resp = requests.post(url, headers=headers, data=data, timeout=15)                
                if resp.status_code == 200 and '"result":0' in resp.text.replace(" ", ""):
                    await update.message.reply_text(
                        f"*Success: Recovery email request cancelled for account {nickname}!*",
                        parse_mode='Markdown',
                        reply_markup=get_support_inline()
                    )
                else:
                    await update.message.reply_text(
                        f"*Failed to cancel:* {resp.text[:200]}",
                        parse_mode='Markdown',
                        reply_markup=get_support_inline()
                    )
            except Exception as e:
                await update.message.reply_text(
                    f"*Error:* {str(e)}",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
        else:
            await update.message.reply_text(
                f"*No Pending Email Found!*\n\n"
                f"Account: `{nickname}`\n"
                f"ID: `{uid}`\n\n"
                f"Status: No pending email change request to cancel.",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )        
        add_token_entry(user.id, access_token, f"Cancel Recovery: {nickname}")
        await show_main_menu_after(update, context)
        del context.bot_data['user_states'][user.id]
    elif action == "unbind_method" and step == 'method_select':
        if text in ["Via Email OTP", "OTP Method"]:
            set_user_state(context, user.id, 'unbind_token', 0, {'method': 'otp'})
            await update.message.reply_text(
                "*Unbind via Email OTP*\n\nPlease enter your access token:",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
        elif text in ["Via Security Code", "Security Code Method"]:
            set_user_state(context, user.id, 'unbind_token', 0, {'method': 'security'})
            await update.message.reply_text(
                "*Unbind via Security Code*\n\nPlease enter your access token:",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
        else:
            await update.message.reply_text(
                "Invalid! Use the keyboard buttons.",
                reply_markup=get_unbind_keyboard()
            )    
    elif action == "unbind_token" and step == 0:
        access_token = text
        method = state.get('method', 'otp')       
        valid, info = check_token_valid(access_token)
        if not valid:
            await update.message.reply_text(
                "*Invalid access token:* Missing parameters in redirect",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            await show_main_menu_after(update, context)
            del context.bot_data['user_states'][user.id]
            return        
        nickname = info['nickname']
        uid = info['uid']        
        bind_data = get_bind_info(access_token)
        bound_email = bind_data.get("email", "") if bind_data else ""        
        if not bound_email:
            await update.message.reply_text(
                f"*No Email Bound!*\n\n"
                f"Account: `{nickname}`\n"
                f"ID: `{uid}`\n\n"
                f"Status: This account has no recovery email bound.\n"
                f"Use 'Add Recovery Email' option to bind an email first.",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            await show_main_menu_after(update, context)
            del context.bot_data['user_states'][user.id]
            return        
        await update.message.reply_text(
            f"*Email Found!*\n\n"
            f"Account: `{nickname}`\n"
            f"ID: `{uid}`\n"
            f"Bound Email: `{bound_email}`\n\n"
            f"Proceeding with unbind process...",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )        
        if method == 'otp':
            try:
                headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
                send_url = "https://100067.connect.garena.com/game/account_security/bind:send_otp"
                send_data = {"email": bound_email, "locale": "en_PK", "region": "PK", "app_id": "100067", "access_token": access_token}
                resp = requests.post(send_url, headers=headers, data=send_data, timeout=15)
                if resp.status_code == 200 and '"result":0' in resp.text.replace(" ", ""):
                    set_user_state(context, user.id, 'unbind_otp_verify', 0, {
                        'access_token': access_token,
                        'email': bound_email,
                        'info': info
                    })
                    await update.message.reply_text(
                        f"*OTP sent to* `{bound_email}`\n\n"
                        f"Account: `{nickname}`\n\nPlease enter the OTP:",
                        parse_mode='Markdown',
                        reply_markup=get_support_inline()
                    )
                else:
                    await update.message.reply_text(
                        f"*Failed to send OTP:* {resp.text[:100]}",
                        parse_mode='Markdown',
                        reply_markup=get_support_inline()
                    )
                    del context.bot_data['user_states'][user.id]
            except Exception as e:
                await update.message.reply_text(
                    f" *Error:* {str(e)}",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                del context.bot_data['user_states'][user.id]
        else:
            set_user_state(context, user.id, 'unbind_security', 0, {
                'access_token': access_token,
                'email': bound_email,
                'info': info
            })
            await update.message.reply_text(
                f"Account: `{nickname}`\n\nPlease enter your security code:",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )    
    elif action == "unbind_otp_verify" and step == 0:
        otp = text
        access_token = state['access_token']
        email = state['email']
        info = state['info']
        nickname = info['nickname']
        try:
            headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
            verify_url = "https://100067.connect.garena.com/game/account_security/bind:verify_identity"
            verify_data = {"email": email, "app_id": "100067", "access_token": access_token, "otp": otp}
            resp = requests.post(verify_url, headers=headers, data=verify_data, timeout=15)
            identity_token = ""
            try:
                identity_token = resp.json().get("identity_token", "")
            except:
                pass            
            if not identity_token:
                await update.message.reply_text(
                    "*Failed to verify OTP*",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                await show_main_menu_after(update, context)
                del context.bot_data['user_states'][user.id]
                return            
            unbind_url = "https://100067.connect.garena.com/game/account_security/bind:create_unbind_request"
            unbind_data = {"app_id": "100067", "access_token": access_token, "identity_token": identity_token}
            resp = requests.post(unbind_url, headers=headers, data=unbind_data, timeout=15)
            
            if resp.status_code == 200 and '"result":0' in resp.text.replace(" ", ""):
                await update.message.reply_text(
                    f"*Email unbound successfully!*\n\nAccount: `{nickname}`",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                add_token_entry(user.id, access_token, f"Unbound via OTP for {nickname}")
            else:
                await update.message.reply_text(
                    f"*Unbind failed:* {resp.text[:200]}",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
        except Exception as e:
            await update.message.reply_text(
                f"*Error:* {str(e)}",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )        
        await show_main_menu_after(update, context)
        del context.bot_data['user_states'][user.id]    
    elif action == "unbind_security" and step == 0:
        sec_code = text
        access_token = state['access_token']
        email = state['email']
        info = state['info']
        nickname = info['nickname']       
        try:
            hashed = hashlib.sha256(sec_code.encode('utf-8')).hexdigest()
            headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
            verify_url = "https://100067.connect.garena.com/game/account_security/bind:verify_identity"
            verify_data = {"email": email, "app_id": "100067", "access_token": access_token, "secondary_password": hashed}
            resp = requests.post(verify_url, headers=headers, data=verify_data, timeout=15)
            identity_token = ""
            try:
                identity_token = resp.json().get("identity_token", "")
            except:
                pass            
            if not identity_token:
                await update.message.reply_text(
                    "*Security code verification failed!*",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                await show_main_menu_after(update, context)
                del context.bot_data['user_states'][user.id]
                return            
            unbind_url = "https://100067.connect.garena.com/game/account_security/bind:create_unbind_request"
            unbind_data = {"app_id": "100067", "access_token": access_token, "identity_token": identity_token}
            resp = requests.post(unbind_url, headers=headers, data=unbind_data, timeout=15)
            if resp.status_code == 200 and '"result":0' in resp.text.replace(" ", ""):
                await update.message.reply_text(
                    f"*Email unbound successfully!*\n\nAccount: `{nickname}`",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                add_token_entry(user.id, access_token, f"Unbound via Security for {nickname}")
            else:
                await update.message.reply_text(
                    f"*Unbind failed:* {resp.text[:200]}",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
        except Exception as e:
            await update.message.reply_text(
                f"*Error:* {str(e)}",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )       
        await show_main_menu_after(update, context)
        del context.bot_data['user_states'][user.id]
    elif action == "change_bind" and step == 'method_select':
        if text in ["Via Email OTP", "OTP Method"]:
            set_user_state(context, user.id, 'change_token', 0, {'method': 'otp'})
            await update.message.reply_text(
                "*Change via Email OTP*\n\nPlease enter your access token:",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
        elif text in ["Via Security Code", "Security Code Method"]:
            set_user_state(context, user.id, 'change_token', 0, {'method': 'security'})
            await update.message.reply_text(
                "*Change via Security Code*\n\nPlease enter your access token:",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
        else:
            await update.message.reply_text(
                " Invalid! Use the keyboard buttons.",
                reply_markup=get_change_keyboard()
            )    
    elif action == "change_token" and step == 0:
        access_token = text
        valid, info = check_token_valid(access_token)
        if not valid:
            await update.message.reply_text(
                "*Invalid access token:* Missing parameters in redirect",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            await show_main_menu_after(update, context)
            del context.bot_data['user_states'][user.id]
            return        
        nickname = info['nickname']
        uid = info['uid']        
        bind_data = get_bind_info(access_token)
        bound_email = bind_data.get("email", "") if bind_data else ""        
        if not bound_email:
            await update.message.reply_text(
                f"*No Email Bound!*\n\n"
                f"Account: `{nickname}`\n"
                f"ID: `{uid}`\n\n"
                f"Status: This account has no recovery email bound.\n"
                f"Use 'Add Recovery Email' option to bind an email first.",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            await show_main_menu_after(update, context)
            del context.bot_data['user_states'][user.id]
            return        
        await update.message.reply_text(
            f"*Email Found!*\n\n"
            f"Account: `{nickname}`\n"
            f"ID: `{uid}`\n"
            f"Bound Email: `{bound_email}`\n\n"
            f"Proceeding with email change process...",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )        
        method = state.get('method', 'otp')        
        if method == 'otp':
            try:
                headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
                send_url = "https://100067.connect.garena.com/game/account_security/bind:send_otp"
                send_data = {"email": bound_email, "locale": "en_PK", "region": "PK", "app_id": "100067", "access_token": access_token}
                resp = requests.post(send_url, headers=headers, data=send_data, timeout=15)
                if resp.status_code == 200 and '"result":0' in resp.text.replace(" ", ""):
                    set_user_state(context, user.id, 'change_otp', 0, {
                        'access_token': access_token,
                        'email': bound_email,
                        'info': info
                    })
                    await update.message.reply_text(
                        f"*OTP sent to* `{bound_email}`\n\nPlease enter the OTP:",
                        parse_mode='Markdown',
                        reply_markup=get_support_inline()
                    )
                else:
                    await update.message.reply_text(
                        f"*Failed to send OTP:* {resp.text[:100]}",
                        parse_mode='Markdown',
                        reply_markup=get_support_inline()
                    )
                    await show_main_menu_after(update, context)
                    del context.bot_data['user_states'][user.id]
            except Exception as e:
                await update.message.reply_text(
                    f"*Error:* {str(e)}",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                await show_main_menu_after(update, context)
                del context.bot_data['user_states'][user.id]
        else:
            set_user_state(context, user.id, 'change_security', 0, {
                'access_token': access_token,
                'email': bound_email,
                'info': info
            })
            await update.message.reply_text(
                f"Please enter your security code:",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )    
    elif action == "change_otp" and step == 0:
        otp = text
        access_token = state['access_token']
        email = state['email']
        info = state['info']
        nickname = info['nickname']
        try:
            headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
            verify_url = "https://100067.connect.garena.com/game/account_security/bind:verify_identity"
            verify_data = {"email": email, "app_id": "100067", "access_token": access_token, "otp": otp}
            resp = requests.post(verify_url, headers=headers, data=verify_data, timeout=15)
            identity_token = ""
            try:
                identity_token = resp.json().get("identity_token", "")
            except:
                pass            
            if not identity_token:
                await update.message.reply_text(
                    "*Identity verification failed!* Invalid OTP.",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                await show_main_menu_after(update, context)
                del context.bot_data['user_states'][user.id]
                return            
            set_user_state(context, user.id, 'change_new', 0, {
                'access_token': access_token,
                'identity_token': identity_token,
                'info': info
            })
            await update.message.reply_text(
                f"*Identity verified!*\n\nPlease enter the *new email* address:",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
        except Exception as e:
            await update.message.reply_text(
                f"*Error:* {str(e)}",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            await show_main_menu_after(update, context)
            del context.bot_data['user_states'][user.id]    
    elif action == "change_security" and step == 0:
        sec_code = text
        access_token = state['access_token']
        email = state['email']
        info = state['info']
        nickname = info['nickname']
        try:
            hashed = hashlib.sha256(sec_code.encode('utf-8')).hexdigest()
            headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
            verify_url = "https://100067.connect.garena.com/game/account_security/bind:verify_identity"
            verify_data = {"email": email, "app_id": "100067", "access_token": access_token, "secondary_password": hashed}
            resp = requests.post(verify_url, headers=headers, data=verify_data, timeout=15)
            identity_token = ""
            try:
                identity_token = resp.json().get("identity_token", "")
            except:
                pass            
            if not identity_token:
                await update.message.reply_text(
                    " *Security code verification failed!*",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                await show_main_menu_after(update, context)
                del context.bot_data['user_states'][user.id]
                return            
            set_user_state(context, user.id, 'change_new', 0, {
                'access_token': access_token,
                'identity_token': identity_token,
                'info': info
            })
            await update.message.reply_text(
                f"*Identity verified!*\n\nPlease enter the *new email* address:",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ *Error:* {str(e)}",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(is_owner(user.id))
            )
            del context.bot_data['user_states'][user.id]    
    elif action == "change_new" and step == 0:
        new_email = text
        access_token = state['access_token']
        identity_token = state['identity_token']
        info = state['info']
        nickname = info['nickname']        
        await update.message.reply_text(f"*Sending OTP to* `{new_email}`*...*", parse_mode='Markdown')        
        try:
            headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
            send_url = "https://100067.connect.garena.com/game/account_security/bind:send_otp"
            send_data = {"email": new_email, "locale": "en_PK", "region": "PK", "app_id": "100067", "access_token": access_token}
            resp = requests.post(send_url, headers=headers, data=send_data, timeout=15)
            
            if resp.status_code != 200 or '"result":0' not in resp.text.replace(" ", ""):
                await update.message.reply_text(
                    f"*Failed to send OTP:* {resp.text[:100]}",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                await show_main_menu_after(update, context)
                del context.bot_data['user_states'][user.id]
                return            
            set_user_state(context, user.id, 'change_verify', 0, {
                'access_token': access_token,
                'identity_token': identity_token,
                'new_email': new_email,
                'info': info
            })
            await update.message.reply_text(
                f"*OTP sent to* `{new_email}`\n\nPlease enter the OTP:",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
        except Exception as e:
            await update.message.reply_text(
                f"*Error:* {str(e)}",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(is_owner(user.id))
            )
            await show_main_menu_after(update, context)
            del context.bot_data['user_states'][user.id]    
    elif action == "change_verify" and step == 0:
        otp_new = text
        access_token = state['access_token']
        identity_token = state['identity_token']
        new_email = state['new_email']
        info = state['info']
        nickname = info['nickname']        
        try:
            headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
            verify_url = "https://100067.connect.garena.com/game/account_security/bind:verify_otp"
            verify_data = {"email": new_email, "app_id": "100067", "access_token": access_token, "otp": otp_new}
            resp = requests.post(verify_url, headers=headers, data=verify_data, timeout=15)
            verifier_token = ""
            try:
                verifier_token = resp.json().get("verifier_token", "")
            except:
                pass            
            if not verifier_token:
                await update.message.reply_text(
                    "*OTP verification failed!* Invalid OTP.",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                await show_main_menu_after(update, context)
                del context.bot_data['user_states'][user.id]
                return            
            rebind_url = "https://100067.connect.garena.com/game/account_security/bind:create_rebind_request"
            rebind_data = {"identity_token": identity_token, "email": new_email, "app_id": "100067", "verifier_token": verifier_token, "access_token": access_token}
            resp = requests.post(rebind_url, headers=headers, data=rebind_data, timeout=15)
            if resp.status_code == 200 and '"result":0' in resp.text.replace(" ", ""):
                await update.message.reply_text(
                    f"*Email changed successfully!*\n\n"
                    f"New Email: `{new_email}`\n"
                    f"Account: `{nickname}`",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                add_token_entry(user.id, access_token, f"Changed Email to: {new_email} for {nickname}")
            else:
                await update.message.reply_text(
                    f"*Change failed:* {resp.text[:200]}",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
        except Exception as e:
            await update.message.reply_text(
                f"*Error:* {str(e)}",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )        
        await show_main_menu_after(update, context)
        del context.bot_data['user_states'][user.id]
    elif action == "update_bio_token" and step == 0:
        access_token = text
        try:
            cb = get_AccessToken_and_OpenID(access_token)
            if not cb.get("success"):
                await update.message.reply_text(
                    "*Invalid access token:* Missing parameters in redirect",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                await show_main_menu_after(update, context)
                del context.bot_data['user_states'][user.id]
                return            
            nickname = cb.get("nickname", "Unknown")
            success_event.clear()
            result = None
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(try_generate_majortoken, access_token) for _ in range(5)]
                for future in concurrent.futures.as_completed(futures):
                    res = future.result()
                    if res and res.get("status") == "success":
                        result = res
                        break            
            if not result or result.get("status") != "success":
                await update.message.reply_text(
                    "*Invalid access token: Missing parameters in redirect*",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                await show_main_menu_after(update, context)
                del context.bot_data['user_states'][user.id]
                return            
            set_user_state(context, user.id, 'update_bio_text', 0, {
                'main_token': result['token'],
                'region': result.get('region', 'IND'),
                'nickname': nickname,
                'access_token': access_token
            })            
            await update.message.reply_text(
                f"*Token Verified Successfully!*\n\n"
                f"Account: `{nickname}`\n\n"
                f"Now please send your new bio message:\n\n"
                f"*Note:* Max 256 characters recommended",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
        except Exception as e:
            await update.message.reply_text(
                f"*Error:* {str(e)}",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            await show_main_menu_after(update, context)
            del context.bot_data['user_states'][user.id]    
    elif action == "update_bio_text" and step == 0:
        bio_text = text
        main_token = state['main_token']
        region = state['region']
        nickname = state['nickname']
        access_token = state['access_token']        
        if len(bio_text) > 256:
            await update.message.reply_text(
                "⚠️ *Bio too long!* Max 256 characters recommended.\n\nPlease send a shorter bio:",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            return        
        result = update_bio_api(main_token, bio_text, region)        
        if result == "success":
            await update.message.reply_text(
                f"*Bio updated successfully!*\n\n"
                f"Account: `{nickname}`\n"
                f"New Bio: `{bio_text}`",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            add_token_entry(user.id, access_token, f"Updated Bio for {nickname}: {bio_text[:50]}")
        else:
            await update.message.reply_text(
                f"*Bio update failed:*\n`{result}`",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )       
        await show_main_menu_after(update, context)
        del context.bot_data['user_states'][user.id]
    elif action == "eat_token" and step == 0:
        access_token = text.strip()
        try:
            result = try_generate_majortoken(access_token)            
            if result and result.get("status") == "success":
                await update.message.reply_text(
                    f"**Account ID:** `{result.get('account_id', 'N/A')}`\n"
                    f"**Nickname:** `{result.get('nickname', 'Unknown')}`\n"
                    f"**Region:** `{result.get('region', 'N/A')}`\n"
                    f"**Platform:** `{result.get('platform', 'N/A')}`\n"
                    f"**Open ID:** `{result.get('open_id', 'N/A')}`\n"
                    f"**Token:** `{result.get('token', 'N/A')}`\n"
                    f"**Access Token:** `{result.get('real_access_token', 'N/A')}`" ,
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )               
                nickname = result.get('nickname', 'Unknown')
                add_token_entry(user.id, access_token, f"Major Token for {nickname}")                
            else:
                error = result.get("error", "Unknown error") if result else "No result returned"
                status = result.get("status") if result else "None"
                
                await update.message.reply_text(
                    f"*Invalid access token: Missing parameters in redirect*",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )                
        except Exception as e:
            await update.message.reply_text(
                f"*Failed to generate token.*\n\n"
                f"Error: `{str(e)}`",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )        
        await show_main_menu_after(update, context)
        del context.bot_data['user_states'][user.id]
    elif action == "revoke_token" and step == 0:
        access_token = text        
        try:
            cb = get_AccessToken_and_OpenID(access_token)
            if not cb.get("success"):
                await update.message.reply_text(
                    "*Invalid access token:* Missing parameters in redirect",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
                await show_main_menu_after(update, context)
                del context.bot_data['user_states'][user.id]
                return            
            nickname = cb.get('nickname', 'Unknown')
            account_id = cb.get('account_id', 'Unknown')
            save_pending_revoke(user.id, access_token, nickname, account_id)
            await context.bot.send_invoice(
                chat_id=update.effective_chat.id,
                title=f"Revoke Token - {nickname}",
                description=f"Revoke token for account:\n {nickname} (ID: {account_id})",
                payload=f"revoke_{user.id}_{int(time.time())}",
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(f"Revoke {nickname}", STARS_PRICE)],
            )
        except Exception as e:
            await update.message.reply_text(
                f"*Error:* {str(e)}",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            await show_main_menu_after(update, context)
            del context.bot_data['user_states'][user.id]
    elif action == "unsubscribe_otp" and step == 0:
        email = text.strip()        
        if not is_valid_email(email):
            await update.message.reply_text(
                "*Invalid Email! Please send a valid email address.*",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
            return        
        await update.message.reply_text(
            f"*Sending Single Unsubscribe OTP to* {email}...",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )        
        try:            
            resp, error = send_otp_api(email)            
            if resp and resp.status_code == 200:
                await update.message.reply_text(
                    f"*Single Unsubscribe OTP Sent Successfully!*\n\n"
                    f"Email: `{email}`\n"
                    f"Status: OTP has been sent to your email",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
            elif resp:
                await update.message.reply_text(
                    f"*OTP Send Status:*\n"
                    f"Status: `{resp.status_code}`\n"
                    f"Response: `{resp.text[:200]}`",
                    parse_mode='Markdown',
                    reply_markup=get_support_inline()
                )
            else:
                await update.message.reply_text(
                    f"*Failed to send OTP:* {error}",
                    parse_mode='Markdown',
                    reply_markup=get_main_keyboard(is_owner(user.id))
                )
        except Exception as e:
            await update.message.reply_text(
                f"*Error:* {str(e)}",
                parse_mode='Markdown',
                reply_markup=get_support_inline()
            )
        await show_main_menu_after(update, context)
        del context.bot_data['user_states'][user.id]
    elif action == "owner_ban" and step == 0:
        if text.lower().startswith("ban "):
            parts = text.split(" ", 2)
            if len(parts) >= 2:
                user_id_str = parts[1]
                reason = parts[2] if len(parts) > 2 else "No reason"
                try:
                    target_id = int(user_id_str)
                    ban_user(target_id, reason)
                    await update.message.reply_text(
                        f"*Banned* `{target_id}`\nReason: {reason}",
                        parse_mode='Markdown',
                        reply_markup=get_owner_keyboard()
                    )
                except ValueError:
                    await update.message.reply_text(" Invalid User ID format.")
                else:
                    await update.message.reply_text(" Format: `ban USER_ID REASON`", parse_mode='Markdown')
            else:
                await update.message.reply_text(" Format: `ban USER_ID REASON`", parse_mode='Markdown')
            del context.bot_data['user_states'][user.id]
        elif text.lower().startswith("unban "):
            parts = text.split(" ", 1)
            if len(parts) >= 2:
                try:
                    target_id = int(parts[1].strip())
                    unban_user(target_id)
                    await update.message.reply_text(
                        f"*Unbanned* `{target_id}`",
                        parse_mode='Markdown',
                        reply_markup=get_owner_keyboard()
                    )
                except ValueError:
                    await update.message.reply_text(" Invalid User ID format.")
                del context.bot_data['user_states'][user.id]
            else:
                await update.message.reply_text(" Format: `unban USER_ID`", parse_mode='Markdown')
                del context.bot_data['user_states'][user.id]
        else:
            await update.message.reply_text("Use: `ban USER_ID REASON` or `unban USER_ID`", parse_mode='Markdown')
    elif action == "owner_unban" and step == 0:
        try:
            target_id = int(text.strip())
            unban_user(target_id)
            await update.message.reply_text(
                f"*Unbanned* `{target_id}`",
                parse_mode='Markdown',
                reply_markup=get_owner_keyboard()
            )
        except ValueError:
            await update.message.reply_text(" Invalid User ID. Please enter a numeric ID.")
        del context.bot_data['user_states'][user.id]
    elif action == "owner_broadcast" and step == 0:
        broadcast_text = text
        await update.message.reply_text(
            "*Broadcasting...*\n\nThis may take a while.",
            parse_mode='Markdown'
        )        
        users = get_all_users()
        chats = get_all_chats()        
        target_ids = set()
        for u in users:
            target_ids.add(u[0])
        for c in chats:
            target_ids.add(c[0])        
        sent_count = 0
        fail_count = 0        
        for chat_id in target_ids:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"📢 *Broadcast Message*\n\n{broadcast_text}",
                    parse_mode='Markdown'
                )
                sent_count += 1
                time.sleep(0.05)
            except:
                fail_count += 1        
        await update.message.reply_text(
            f"📢 *Broadcast Complete!*\n\n"
            f"✅ Sent: `{sent_count}`\n"
            f"❌ Failed: `{fail_count}`\n"
            f"📊 Total targets: `{len(target_ids)}`",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )
        await update.message.reply_text("⚙️ *OWNER PANEL*", parse_mode='Markdown', reply_markup=get_owner_keyboard())
        del context.bot_data['user_states'][user.id]    
    else:
        await update.message.reply_text(
            "Session expired. Please start again.",
            reply_markup=get_main_keyboard(is_owner(user.id))
        )
        if user.id in context.bot_data.get('user_states', {}):
            del context.bot_data['user_states'][user.id]
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)
async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    try:
        parts = payload.split("_")
        if len(parts) >= 2:
            user_id = int(parts[1])
        else:
            user_id = user.id
    except (ValueError, IndexError):
        user_id = user.id
    pending = get_pending_revoke(user_id)    
    if not pending:
        await update.message.reply_text(
            "*{STARS_PRICE} Stars Payment Received!*\n\n"
            "But no pending revoke request found. Contact support.",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )
        await show_main_menu_after(update, context)
        return    
    access_token, nickname, account_id = pending    
    await update.message.reply_text(
        f"✅ *{STARS_PRICE} Stars Payment Received!*\n\n"
        f"🔄 Now revoking token for: `{nickname}`...",
        parse_mode='Markdown'
    )
    result = revoke_token_api(access_token)    
    if result == "success":
        await update.message.reply_text(
            f"*Token revoked successfully!*\n\n"
            f"Account: `{nickname}`\n"
            f"ID: `{account_id}`\n"
            f"Status: Logged out from all sessions.\n\n"
            f"⭐ *{STARS_PRICE} Stars Charged*",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )
        add_token_entry(user_id, access_token, f"Revoked Token for {nickname} (Stars: {STARS_PRICE})")
    else:
        await update.message.reply_text(
            f"⚠️ *Revoke result:* `{result}`\n\n"
            f"Stars were charged. Contact support if needed.",
            parse_mode='Markdown',
            reply_markup=get_support_inline()
        )
    delete_pending_revoke(user_id)
    if user_id in context.bot_data.get('user_states', {}):
        del context.bot_data['user_states'][user_id]    
    await show_main_menu_after(update, context)
def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build() 
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print(f"📝 All features active")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped.")
    except Exception as e:
        import traceback
        traceback.print_exc()