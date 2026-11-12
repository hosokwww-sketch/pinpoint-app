# Рекомендуется Python 3.12/3.13. Зависимости:
# pip install "aiogram>=3.20,<4" "aiohttp>=3.10,<4" "aiosqlite>=0.20,<1"
# Запуск: python bot.py
import asyncio
import base64
import hashlib
import hmac
import html
import json
import logging
import os
import re
import sqlite3
import time
import urllib.parse
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import aiohttp
import aiosqlite
from aiohttp import web
from aiogram import BaseMiddleware, Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

# ==========================================
# 1. КОНФИГУРАЦИЯ И ТАРИФНАЯ СЕТКА
# ==========================================
BOT_TOKEN = os.getenv('BOT_TOKEN', '8956105587:AAGIMXM6mbufTkYus-wGe-4urYsBOXgkd4Y')
WEBAPP_URL = os.getenv('WEBAPP_URL', 'https://skaddy112312.github.io/pinpoint-app/')

REQUIRED_CHANNEL_ID = '@PinPoint_Channel'
REQUIRED_CHANNEL_URL = 'https://t.me/PinPoint_Channel'

MAIN_ADMIN_ID = int(os.getenv('MAIN_ADMIN_ID', 8974529077))
DEFAULT_ADMIN_IDS = [MAIN_ADMIN_ID, 8797606012]

ADMIN_LOGIN = os.getenv('ADMIN_LOGIN', 'agaru')
ADMIN_PASS = os.getenv('ADMIN_PASS', 'danilkaromaD5')
MAX_ATTEMPTS = 5

REF_BASE_PERCENT = 5
REF_MAX_PERCENT = 25

PLATEGA_MERCHANT_ID = os.getenv('PLATEGA_MERCHANT_ID', '120b4d06-4b46-4b74-adfd-3bd2a0c5d6ee')
PLATEGA_SECRET = os.getenv(
    'PLATEGA_SECRET',
    'vaeAoCl0aSOxfk8G23j5nhKZO73aYmxfOkej2OVaCSg0C8ZUVHJkodNpgua4RTgdsgiejxyq7CKQQga9ERPmKHYJDHSacREZpSPx',
)

H1CLOUD_PANEL_URL = os.getenv('H1CLOUD_PANEL_URL', 'https://api.pinpoint-vpn.shop/api').rstrip('/')
H1CLOUD_API_TOKEN = os.getenv('H1CLOUD_API_TOKEN', '109d5888bf3843f596df99c1cf5bd6e51b7c18feacd3435fb548fdcc26291a46')

WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', 25571))
API_PUBLIC_URL = os.getenv('API_PUBLIC_URL', '').rstrip('/')
H1CLOUD_UPDATE_URL = os.getenv('H1CLOUD_UPDATE_URL', '')

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / 'database.db')

EMOJI_STAR = '<tg-emoji emoji-id="5460704257168665046">✨</tg-emoji>'
EMOJI_WARN = '<tg-emoji emoji-id="5220197908342648622">❗</tg-emoji>'

TARIFFS = {
    'start': {'name': '🚀 Старт', 'days': 14, 'devices': 1, 'price': 79, 'limit_gb': 50},
    'base': {'name': '⚡️ Базовый', 'days': 30, 'devices': 1, 'price': 149, 'limit_gb': 150},
    'pro': {'name': '💎 Продвинутый', 'days': 30, 'devices': 3, 'price': 199, 'limit_gb': 300},
    'hit': {'name': '🔥 ХИТ СЕЗОНА', 'days': 90, 'devices': 3, 'price': 499, 'limit_gb': 900},
}

BOOSTERS = {
    15: {'gb': 15, 'price': 45, 'name': '+15 ГБ'},
    50: {'gb': 50, 'price': 99, 'name': '+50 ГБ'},
    150: {'gb': 150, 'price': 165, 'name': '+150 ГБ'},
}

SUPPORTED_APPS = {
    'happ': {
        'title': 'Happ',
        'steps': (
            '1. Установите приложение <b>Happ</b> из магазина вашей платформы.\n'
            '2. Откройте <b>«👤 Личный кабинет»</b> и скопируйте ваш ключ подписки.\n'
            '3. В Happ нажмите <code>+</code> → <b>«Импорт из буфера обмена»</b> и активируйте соединение.'
        ),
    },
    'hiddify': {
        'title': 'Hiddify',
        'steps': (
            '1. Скачайте и установите клиент <b>Hiddify</b>.\n'
            '2. Перейдите в <b>«👤 Личный кабинет»</b> и скопируйте ссылку подписки.\n'
            '3. В Hiddify нажмите <b>«Новый профиль»</b> → <b>«Добавить из буфера обмена»</b> и нажмите большую кнопку подключения.'
        ),
    },
    'incy': {
        'title': 'Incy',
        'steps': (
            '1. Установите приложение <b>Incy</b> на ваше устройство.\n'
            '2. Скопируйте ключ подписки в разделе <b>«👤 Личный кабинет»</b>.\n'
            '3. Откройте Incy, импортируйте профиль из буфера обмена и включите соединение.'
        ),
    },
    'v2raytun': {
        'title': 'V2raytun',
        'steps': (
            '1. Установите <b>V2raytun</b> из App Store, Google Play или для Windows.\n'
            '2. Скопируйте ключ в разделе <b>«👤 Личный кабинет»</b>.\n'
            '3. В V2raytun нажмите <code>+</code> в верхнем углу → <b>«Импорт из буфера обмена»</b> и запустите подключение.'
        ),
    },
}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
http_session: aiohttp.ClientSession | None = None
_bot_username_cache: str | None = None
_user_locks: dict[int, asyncio.Lock] = {}


def get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in _user_locks:
        if len(_user_locks) > 5000:
            _user_locks.clear()
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


async def get_bot_username() -> str:
    global _bot_username_cache
    if not _bot_username_cache:
        me = await bot.get_me()
        _bot_username_cache = me.username
    return _bot_username_cache


# ==========================================
# 2. УТИЛИТЫ И ПАРСИНГ ДАТ
# ==========================================
def styled_btn(
    text: str,
    callback_data: str | None = None,
    url: str | None = None,
    web_app: WebAppInfo | None = None,
    style: str | None = None,
) -> InlineKeyboardButton:
    kwargs: dict = {'text': text}
    if callback_data:
        kwargs['callback_data'] = callback_data
    if url:
        kwargs['url'] = url
    if web_app:
        kwargs['web_app'] = web_app
    if style:
        kwargs['style'] = style
    try:
        return InlineKeyboardButton(**kwargs)
    except Exception:
        kwargs.pop('style', None)
        return InlineKeyboardButton(**kwargs)


def make_progress_bar(current: float, total: float, length: int = 8) -> str:
    if total <= 0:
        return '▱' * length
    ratio = max(0.0, min(1.0, current / total))
    filled = int(round(ratio * length))
    return '▰' * filled + '▱' * (length - filled)


def parse_any_datetime(val) -> datetime | None:
    if val is None or val == '':
        return None
    if isinstance(val, datetime):
        return val.astimezone().replace(tzinfo=None) if val.tzinfo else val.replace(tzinfo=None)
    if isinstance(val, (int, float)):
        try:
            ts = float(val)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts)
        except Exception:
            return None

    s = str(val).strip()
    if not s:
        return None
    if s.isdigit():
        try:
            ts = float(s)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts)
        except Exception:
            pass

    try:
        parsed = datetime.fromisoformat(s.replace('Z', '+00:00'))
        return parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError:
        pass

    if '+' in s:
        s = s.split('+')[0].strip()
    if s.endswith('Z'):
        s = s[:-1].strip()
    for fmt in (
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
        '%d.%m.%Y %H:%M:%S',
        '%d.%m.%Y %H:%M',
        '%d.%m.%Y',
        '%Y-%m-%d',
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def resolve_html_file() -> Path:
    for candidate in ('index.html', 'index (2).html'):
        p = BASE_DIR / candidate
        if p.exists():
            return p
    return BASE_DIR / 'index.html'


# ==========================================
# 3. МЕНЕДЖЕР БАЗЫ ДАННЫХ
# ==========================================
_raw_sqlite_connect = aiosqlite.connect


def _patched_connect(database, *args, **kwargs):
    target = DB_PATH if database == 'database.db' else database
    return _raw_sqlite_connect(target, *args, timeout=30, **kwargs)


aiosqlite.connect = _patched_connect


class DBManager:
    @staticmethod
    async def ensure_column(db: aiosqlite.Connection, table: str, col_name: str, col_def: str):
        async with db.execute(f'PRAGMA table_info({table})') as cursor:
            cols = [row[1] for row in await cursor.fetchall()]
        if col_name not in cols:
            await db.execute(f'ALTER TABLE {table} ADD COLUMN {col_name} {col_def}')

    @classmethod
    async def init(cls):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            await db.execute('PRAGMA synchronous=NORMAL')
            await db.execute('PRAGMA busy_timeout=30000')

            await db.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                active_until TIMESTAMP,
                gb_limit INTEGER,
                devices INTEGER,
                vpn_key TEXT
            )''')

            await db.execute('''CREATE TABLE IF NOT EXISTS payments (
                invoice_id TEXT PRIMARY KEY,
                user_id INTEGER,
                amount INTEGER,
                status TEXT,
                created_at TEXT,
                target_action TEXT DEFAULT ''
            )''')

            await db.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                tariff_name TEXT,
                active_until TIMESTAMP,
                gb_limit INTEGER,
                used_gb REAL DEFAULT 0,
                devices INTEGER,
                vpn_key TEXT,
                sub_type TEXT DEFAULT 'paid',
                notified_exp INTEGER DEFAULT 0,
                notified_traffic INTEGER DEFAULT 0
            )''')

            await db.execute('CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)')
            await cls.ensure_column(db, 'admins', 'is_authenticated', 'INTEGER DEFAULT 0')
            for adm_id in DEFAULT_ADMIN_IDS:
                await db.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (adm_id,))

            await db.execute('''CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                reward_rub INTEGER DEFAULT 0,
                discount_pct INTEGER DEFAULT 0,
                max_uses INTEGER DEFAULT 100,
                max_per_user INTEGER DEFAULT 1,
                used_count INTEGER DEFAULT 0
            )''')

            await db.execute('''CREATE TABLE IF NOT EXISTS promo_uses (
                user_id INTEGER,
                code TEXT,
                use_count INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, code)
            )''')

            user_cols = [
                ('username', 'TEXT'),
                ('agreed_to_tos', 'INTEGER DEFAULT 0'),
                ('balance', 'INTEGER DEFAULT 0'),
                ('discount_pct', 'INTEGER DEFAULT 0'),
                ('custom_ref_pct', 'INTEGER DEFAULT NULL'),
                ('active_promo_code', 'TEXT'),
                ('discount_target_tariff', "TEXT DEFAULT 'all'"),
                ('referrer_id', 'INTEGER'),
                ('ref_earned', 'INTEGER DEFAULT 0'),
                ('ref_paid_count', 'INTEGER DEFAULT 0'),
                ('has_paid', 'INTEGER DEFAULT 0'),
                ('used_test', 'INTEGER DEFAULT 0'),
                ('failed_attempts', 'INTEGER DEFAULT 0'),
                ('is_banned', 'INTEGER DEFAULT 0'),
                ('bot_notifications', 'INTEGER DEFAULT 1'),
                ('sub_type', 'TEXT DEFAULT "none"'),
            ]
            for c_name, c_def in user_cols:
                await cls.ensure_column(db, 'users', c_name, c_def)

            for c_name, c_def in [
                ('reward_rub', 'INTEGER DEFAULT 0'),
                ('discount_pct', 'INTEGER DEFAULT 0'),
                ('max_uses', 'INTEGER DEFAULT 100'),
                ('max_per_user', 'INTEGER DEFAULT 1'),
                ('used_count', 'INTEGER DEFAULT 0'),
            ]:
                await cls.ensure_column(db, 'promocodes', c_name, c_def)

            await cls.ensure_column(db, 'promocodes', 'promo_type', 'TEXT')
            await cls.ensure_column(db, 'promocodes', 'target_tariff', "TEXT DEFAULT 'all'")
            await db.execute("UPDATE promocodes SET promo_type = CASE WHEN reward_rub > 0 THEN 'rub' ELSE 'discount' END WHERE promo_type IS NULL")
            await db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
            await db.executemany('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                                 [('ref_base_pct', str(REF_BASE_PERCENT)), ('ref_max_pct', str(REF_MAX_PERCENT))])
            await db.execute("""CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, username TEXT, author_name TEXT,
                is_anon INTEGER DEFAULT 0, rating INTEGER DEFAULT 5,
                text TEXT, status TEXT DEFAULT 'pending', created_at TEXT
            )""")
            await db.execute('CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status, id)')
            await cls.ensure_column(db, 'promo_uses', 'use_count', 'INTEGER DEFAULT 1')

            for c_name, c_def in [
                ('used_gb', 'REAL DEFAULT 0'),
                ('notified_exp', 'INTEGER DEFAULT 0'),
                ('notified_traffic', 'INTEGER DEFAULT 0'),
            ]:
                await cls.ensure_column(db, 'subscriptions', c_name, c_def)

            await cls.ensure_column(db, 'payments', 'amount', 'INTEGER DEFAULT 0')
            await cls.ensure_column(db, 'payments', 'created_at', 'TEXT')
            await cls.ensure_column(db, 'payments', 'target_action', 'TEXT DEFAULT ""')
            async with db.execute('PRAGMA table_info(payments)') as cursor:
                payment_columns = {row[1] for row in await cursor.fetchall()}
            if 'target_fulfillment_status' not in payment_columns:
                await cls.ensure_column(db, 'payments', 'target_fulfillment_status', "TEXT DEFAULT 'pending'")
                await db.execute("UPDATE payments SET target_fulfillment_status = 'fulfilled' WHERE status = 'paid'")


            await db.execute('CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_pay_status ON payments(status)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_pay_user ON payments(user_id)')

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            await db.execute('UPDATE payments SET created_at = ? WHERE created_at IS NULL OR created_at = ""', (now_str,))
            await db.commit()

    @staticmethod
    async def upsert_user(user_id: int, username: str = '', referrer_id: int | None = None):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                'INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 0)',
                (user_id, username or ''),
            )
            if username:
                await db.execute('UPDATE users SET username = ? WHERE user_id = ?', (username, user_id))
            if referrer_id and referrer_id != user_id:
                await db.execute(
                    'UPDATE users SET referrer_id = ? WHERE user_id = ? AND referrer_id IS NULL AND COALESCE(has_paid, 0) = 0',
                    (referrer_id, user_id),
                )
            await db.commit()

    @staticmethod
    async def get_user_summary(user_id: int) -> dict:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                '''SELECT username, COALESCE(balance, 0), COALESCE(ref_paid_count, 0),
                          COALESCE(ref_earned, 0), COALESCE(bot_notifications, 1),
                          COALESCE(agreed_to_tos, 0), COALESCE(used_test, 0), COALESCE(is_banned, 0),
                          COALESCE(discount_pct, 0), custom_ref_pct, active_promo_code,
                          COALESCE(discount_target_tariff, 'all')
                   FROM users WHERE user_id = ?''',
                (user_id,),
            ) as c:
                row = await c.fetchone()
        if not row:
            base_pct, _ = await get_referral_settings()
            return {
                'username': '',
                'balance': 0,
                'ref_cnt': 0,
                'ref_pct': base_pct,
                'custom_ref_pct': None,
                'ref_earn': 0,
                'notifications': 1,
                'agreed_to_tos': 0,
                'used_test': 0,
                'is_banned': 0,
                'discount_pct': 0,
                'active_promo_code': None,
                'discount_target_tariff': 'all',
            }
        ref_cnt = int(row[2])
        custom_pct = row[9]
        if custom_pct is not None:
            effective_pct = int(custom_pct)
        else:
            base_pct, max_pct = await get_referral_settings()
            effective_pct = min(max_pct, base_pct + ref_cnt)

        return {
            'username': row[0] or '',
            'balance': int(row[1]),
            'ref_cnt': ref_cnt,
            'ref_pct': effective_pct,
            'custom_ref_pct': int(custom_pct) if custom_pct is not None else None,
            'ref_earn': int(row[3]),
            'notifications': int(row[4]),
            'agreed_to_tos': int(row[5]),
            'used_test': int(row[6]),
            'is_banned': int(row[7]),
            'discount_pct': int(row[8]),
            'active_promo_code': row[10],
            'discount_target_tariff': row[11],
        }

    @staticmethod
    async def get_active_subscriptions(user_id: int) -> list[dict]:
        now = datetime.now()
        active_list = []
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                '''SELECT id, tariff_name, active_until, gb_limit, used_gb, devices, vpn_key, sub_type
                   FROM subscriptions WHERE user_id = ? ORDER BY id ASC''',
                (user_id,),
            ) as cursor:
                rows = await cursor.fetchall()

        for sub_id, t_name, act_until, gb, used_gb, dev, v_key, s_type in rows:
            d = parse_any_datetime(act_until)
            if d and d > now:
                active_list.append({
                    'id': sub_id,
                    'tariff_name': t_name or '💎 Подписка',
                    'active_until_dt': d,
                    'active_until_str': d.strftime('%d.%m.%Y %H:%M'),
                    'gb_limit': int(gb or 150),
                    'used_gb': round(float(used_gb or 0.0), 1),
                    'devices': int(dev or 1),
                    'vpn_key': v_key or f'https://api.pinpoint-vpn.shop/sub/{user_id}_{sub_id}',
                    'sub_type': s_type or 'paid',
                })
        return active_list

    @staticmethod
    async def is_admin(user_id: int) -> bool:
        if user_id in DEFAULT_ADMIN_IDS:
            return True
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,)) as c:
                return bool(await c.fetchone())

    @staticmethod
    async def get_all_admin_ids() -> set[int]:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute('SELECT user_id FROM admins') as c:
                rows = await c.fetchall()
        return {r[0] for r in rows} | set(DEFAULT_ADMIN_IDS)


def resolve_tariff_id(value) -> str | None:
    return value if isinstance(value, str) and value in TARIFFS else None


def tariff_target(value) -> str | None:
    return resolve_tariff_id(value)


async def get_referral_settings(db=None) -> tuple[int, int]:
    if db is None:
        async with aiosqlite.connect(DB_PATH) as connection:
            return await get_referral_settings(connection)
    async with db.execute("SELECT key, value FROM settings WHERE key IN ('ref_base_pct', 'ref_max_pct')") as cursor:
        values = dict(await cursor.fetchall())
    base = int(values.get('ref_base_pct', REF_BASE_PERCENT))
    maximum = int(values.get('ref_max_pct', REF_MAX_PERCENT))
    return max(1, min(base, 100)), max(1, min(maximum, 100))


async def get_active_subscriptions(user_id: int):
    return await DBManager.get_active_subscriptions(user_id)


async def get_user_ref_stats(user_id: int) -> tuple[int, int, int]:
    info = await DBManager.get_user_summary(user_id)
    return info['ref_cnt'], info['ref_pct'], info['ref_earn']


async def is_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT is_authenticated FROM admins WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
    return bool(row and row[0] == 1)


# ==========================================
# 4. СЕРВИСЫ ИНТЕГРАЦИЙ (H1CLOUD + PLATEGA)
# ==========================================
class H1CloudService:
    @staticmethod
    async def create_key(user_id: int, days: int, devices: int, limit_gb: int) -> str:
        if not all(isinstance(value, int) and value > 0 for value in (user_id, days, devices, limit_gb)):
            raise ValueError('Invalid subscription parameters')
        if http_session is None or http_session.closed:
            raise RuntimeError('H1Cloud HTTP session is unavailable')
        url = f'{H1CLOUD_PANEL_URL}/create'
        headers = {'Authorization': f'Bearer {H1CLOUD_API_TOKEN}', 'Content-Type': 'application/json'}
        payload = {
            'name': f'tg_{user_id}_{int(datetime.now().timestamp())}',
            'uuid': str(uuid.uuid4()),
            'days': days,
            'device_limit': devices,
            'traffic_limit_gb': limit_gb,
            'manual': False,
        }
        try:
            async with http_session.post(url, json=payload, headers=headers, timeout=15) as response:
                data = await response.json(content_type=None)
                if response.status < 200 or response.status >= 300 or not isinstance(data, dict):
                    raise RuntimeError(f'H1Cloud key creation failed with HTTP {response.status}')
                client_data = data.get('client') if isinstance(data.get('client'), dict) else data
                sub_url = (
                    client_data.get('sub_url')
                    or client_data.get('subscription_url')
                    or data.get('sub_url')
                    or data.get('subscription_url')
                    or data.get('url')
                )
                if not isinstance(sub_url, str) or not sub_url.strip():
                    raise RuntimeError('H1Cloud response did not contain a subscription URL')
                return urllib.parse.unquote(sub_url.strip())
        except Exception as exc:
            logging.error('H1Cloud key creation failed for user %s: %s', user_id, exc)
            raise RuntimeError('Unable to create VPN subscription key') from exc

    @staticmethod
    async def update_subscription(sub: dict, **changes) -> bool:
        if not H1CLOUD_UPDATE_URL:
            return True
        try:
            async with http_session.post(
                H1CLOUD_UPDATE_URL,
                json={'subscription_url': sub['vpn_key'], **changes},
                headers={'Authorization': f'Bearer {H1CLOUD_API_TOKEN}'},
                timeout=14,
            ) as response:
                if response.status < 300:
                    return True
        except Exception as e:
            logging.warning('Предупреждение H1Cloud update: %s', e)
        return False


class PlategaService:
    @staticmethod
    async def create_invoice(
        user_id: int, amount: int, username: str = 'user', target_action: str = ''
    ) -> tuple[str | None, str | None]:
        url = 'https://app.platega.io/v2/transaction/process'
        headers = {
            'X-MerchantId': PLATEGA_MERCHANT_ID,
            'X-Secret': PLATEGA_SECRET,
            'Content-Type': 'application/json',
        }
        bot_uname = await get_bot_username()
        payload = {
            'paymentDetails': {'amount': amount, 'currency': 'RUB'},
            'description': f'PinPoint VPN ({user_id})',
            'return': f'https://t.me/{bot_uname}',
            'failedUrl': f'https://t.me/{bot_uname}',
            'payload': str(user_id),
            'metadata': {
                'userId': str(user_id),
                'userName': f'@{username}' if username else f'id_{user_id}',
                'action': target_action,
            },
        }
        try:
            async with http_session.post(url, json=payload, headers=headers, timeout=15) as resp:
                data = await resp.json(content_type=None)
                if resp.status < 300 and isinstance(data, dict):
                    invoice_id = data.get('transactionId') or data.get('id') or data.get('Id')
                    pay_url = data.get('url') or data.get('redirect') or data.get('paymentUrl')
                    if invoice_id and pay_url:
                        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        async with aiosqlite.connect(DB_PATH) as db:
                            await db.execute(
                                '''INSERT INTO payments (invoice_id, user_id, amount, status, created_at, target_action)
                                   VALUES (?, ?, ?, ?, ?, ?)''',
                                (str(invoice_id), user_id, amount, 'pending', now_str, target_action or ''),
                            )
                            await db.commit()
                        return str(pay_url), str(invoice_id)
                else:
                    logging.error('Ответ Platega (%s): %s', resp.status, data)
        except Exception as e:
            logging.error('Ошибка создания счета Platega: %s', e)
        return None, None

    @staticmethod
    async def check_status(invoice_id: str) -> bool:
        if not invoice_id:
            return False
        urls = [
            f'https://app.platega.io/transaction/{invoice_id}',
            f'https://app.platega.io/v2/transaction/{invoice_id}',
        ]
        headers = {
            'X-MerchantId': PLATEGA_MERCHANT_ID,
            'X-Secret': PLATEGA_SECRET,
            'Accept': 'application/json',
        }
        for url in urls:
            try:
                async with http_session.get(url, headers=headers, timeout=10) as resp:
                    if 200 <= resp.status < 300:
                        data = await resp.json(content_type=None)
                        if not isinstance(data, dict):
                            continue
                        status = str(data.get('status') or data.get('Status') or '').upper()
                        if status in ('CONFIRMED', 'PAID', 'SUCCESS', 'COMPLETED'):
                            details = data.get('paymentDetails') or {}
                            amount = details.get('amount', data.get('amount'))
                            async with aiosqlite.connect(DB_PATH) as db:
                                async with db.execute(
                                    'SELECT amount FROM payments WHERE invoice_id = ?', (invoice_id,)
                                ) as c:
                                    local = await c.fetchone()
                            if not local:
                                return False
                            if amount is None:
                                return True
                            try:
                                return Decimal(str(amount)) >= Decimal(str(local[0]))
                            except InvalidOperation:
                                return True
            except Exception:
                pass
        return False


# ==========================================
# 5. СИНХРОНИЗАЦИЯ WEBAPP И АВТО-АКТИВАЦИЯ
# ==========================================
async def build_webapp_url(user_id: int) -> str:
    snapshot = await build_profile_data(user_id, snapshot=True)
    snap_b64 = base64.urlsafe_b64encode(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).decode('ascii')
    parts = urllib.parse.urlsplit(WEBAPP_URL)
    query = dict(urllib.parse.parse_qsl(parts.query))
    query['v'] = str(int(time.time()))
    if API_PUBLIC_URL:
        query['api'] = API_PUBLIC_URL
    query['snap'] = snap_b64
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


async def sync_user_menu_button(user_id: int) -> str:
    personal_url = await build_webapp_url(user_id)
    try:
        await bot.set_chat_menu_button(
            chat_id=user_id,
            menu_button=MenuButtonWebApp(text='📱 Открыть PinPoint', web_app=WebAppInfo(url=personal_url)),
        )
    except Exception:
        pass
    return personal_url


async def check_channel_subscription(user_id: int) -> bool:
    if await DBManager.is_admin(user_id):
        return True
    if not REQUIRED_CHANNEL_ID:
        return True

    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
        status = getattr(member, 'status', None)
        if hasattr(status, 'value'):
            status = status.value

        if status in ('member', 'administrator', 'creator'):
            return True
        if status == 'restricted' and getattr(member, 'is_member', False):
            return True
        return False

    except TelegramBadRequest as e:
        err_text = str(e).lower()
        if any(msg in err_text for msg in ('member list is inaccessible', 'chat not found', 'user not found')):
            logging.error(
                'ВНИМАНИЕ: Назначьте бота администратором канала %s! Ошибка Telegram API: %s',
                REQUIRED_CHANNEL_ID,
                e,
            )
            return True
        return False
    except TelegramForbiddenError:
        return True
    except Exception:
        return True


def calculate_discounted_price(original_price: int, discount_pct: int) -> int:
    if discount_pct <= 0:
        return original_price
    pct = min(99, max(1, discount_pct))
    final = original_price * (100 - pct) // 100
    return max(10, final)


async def _fulfill_target_action_locked(user_id: int, target_action: str) -> str | None:
    if not target_action:
        return None
    if target_action.startswith('buy_'):
        requested_id = target_action[4:].strip()
        result = await _activate_tariff_locked(user_id, requested_id)
        if not result.get('ok'):
            if result.get('reason') == 'slots_full':
                return 'Оплата получена, но свободного слота для тарифа нет. Средства зачислены на баланс.'
            if result.get('reason') == 'insufficient_balance':
                return 'Оплата получена, но тариф не активирован из-за недостатка средств на балансе. Средства зачислены на баланс.'
            if result.get('reason') == 'key_creation_failed':
                return 'Оплата получена, но создать VPN-ключ временно не удалось. Средства зачислены на баланс; повторите покупку позже.'
            return None
        tariff = result['tariff']
        suffix = f" (скидка {result['discount_pct']}%)" if result['discount_pct'] else ''
        await sync_user_menu_button(user_id)
        return (
            f"{EMOJI_STAR} <b>Тариф «{tariff['name']}» автоматически подключен!</b>{suffix}\n\n"
            f"Срок: <b>{tariff['days']} дн.</b> • Лимит: <b>{tariff['limit_gb']} ГБ</b> ({tariff['devices']} устр.)\n\n"
            f"🔑 Ваш ключ подписки:\n<code>{html.escape(result['key'])}</code>"
        )

    if target_action.startswith('boost_'):
        parts = target_action.split('_')
        if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
            return None
        gb_val, slot_idx = int(parts[1]), int(parts[2]) - 1
        if gb_val not in BOOSTERS:
            return None
        booster = BOOSTERS[gb_val]
        active_subs = await DBManager.get_active_subscriptions(user_id)
        if not 0 <= slot_idx < len(active_subs):
            return 'Оплата получена, но активный слот для пакета трафика не найден. Средства зачислены на баланс.'
        target_sub = active_subs[slot_idx]
        summary = await DBManager.get_user_summary(user_id)
        if summary['balance'] < booster['price']:
            return 'Оплата получена, но средств недостаточно для пакета трафика. Средства зачислены на баланс.'
        new_limit = int(target_sub['gb_limit']) + int(booster['gb'])
        if not await H1CloudService.update_subscription(target_sub, traffic_limit_gb=new_limit):
            return 'Оплата получена, но обновить лимит трафика не удалось. Средства зачислены на баланс.'
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('BEGIN IMMEDIATE')
            async with db.execute(
                'UPDATE users SET balance = COALESCE(balance, 0) - ? WHERE user_id = ? AND COALESCE(balance, 0) >= ?',
                (booster['price'], user_id, booster['price']),
            ) as cursor:
                if cursor.rowcount != 1:
                    await db.rollback()
                    return 'Оплата получена, но пакет трафика не списан из-за изменения баланса. Средства зачислены на баланс.'
            await db.execute(
                'UPDATE subscriptions SET gb_limit = gb_limit + ?, notified_traffic = 0 WHERE id = ? AND user_id = ?',
                (booster['gb'], target_sub['id'], user_id),
            )
            await db.commit()
        await sync_user_menu_button(user_id)
        return (
            f"{EMOJI_STAR} <b>Пакет {booster['name']} автоматически добавлен!</b>\n\n"
            f"Новый лимит слота «{html.escape(str(target_sub['tariff_name']))}»: <b>{new_limit} ГБ</b>."
        )
    return None



async def _activate_tariff_locked(user_id: int, tariff_id: str, *, charge_price: int | None = None) -> dict:
    '''Activate a tariff while the caller owns get_user_lock(user_id).'''
    resolved_id = resolve_tariff_id(tariff_id)
    if not resolved_id or resolved_id not in TARIFFS:
        return {'ok': False, 'reason': 'invalid_tariff'}
    tariff = TARIFFS[resolved_id]
    active_subs = await DBManager.get_active_subscriptions(user_id)
    if len(active_subs) >= 2:
        return {'ok': False, 'reason': 'slots_full'}
    summary = await DBManager.get_user_summary(user_id)
    canonical_target = tariff_target(tariff_id) or tariff_target(resolved_id)
    discount_target = str(summary.get('discount_target_tariff') or 'all').lower()
    discount_pct = max(0, min(99, int(summary.get('discount_pct') or 0)))
    if discount_target not in ('', 'all', canonical_target):
        discount_pct = 0
    total_price = calculate_discounted_price(tariff['price'], discount_pct)
    price = total_price if charge_price is None else charge_price
    if not isinstance(price, int) or price < 0:
        return {'ok': False, 'reason': 'invalid_price'}
    if int(summary.get('balance', 0)) < price:
        return {'ok': False, 'reason': 'insufficient_balance', 'price': price, 'balance': int(summary.get('balance', 0))}

    try:
        vpn_key = await H1CloudService.create_key(user_id, tariff['days'], tariff['devices'], tariff['limit_gb'])
    except Exception:
        logging.exception('Could not create tariff key for user %s', user_id)
        return {'ok': False, 'reason': 'key_creation_failed'}
    if not isinstance(vpn_key, str) or not vpn_key.strip():
        return {'ok': False, 'reason': 'key_creation_failed'}

    until = (datetime.now() + timedelta(days=tariff['days'])).strftime('%Y-%m-%d %H:%M:%S')
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('BEGIN IMMEDIATE')
            async with db.execute(
                'SELECT COUNT(*) FROM subscriptions WHERE user_id = ? AND datetime(active_until) > datetime(?)',
                (user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ) as cursor:
                slot_count = int((await cursor.fetchone())[0])
            if slot_count >= 2:
                await db.rollback()
                return {'ok': False, 'reason': 'slots_full'}
            async with db.execute(
                'UPDATE users SET balance = COALESCE(balance, 0) - ? WHERE user_id = ? AND COALESCE(balance, 0) >= ?',
                (price, user_id, price),
            ) as cursor:
                if cursor.rowcount != 1:
                    await db.rollback()
                    return {'ok': False, 'reason': 'insufficient_balance', 'price': price}
            await db.execute(
                '''INSERT INTO subscriptions (user_id, tariff_name, active_until, gb_limit, devices, vpn_key, sub_type)
                   VALUES (?, ?, ?, ?, ?, ?, 'paid')''',
                (user_id, tariff['name'], until, tariff['limit_gb'], tariff['devices'], vpn_key),
            )
            await db.commit()
    except Exception:
        logging.exception('Could not save tariff activation for user %s', user_id)
        raise
    return {
        'ok': True, 'tariff_id': resolved_id, 'tariff': tariff, 'key': vpn_key,
        'discount_pct': discount_pct, 'price': price, 'active_until': until,
    }

async def fulfill_target_action_after_payment(user_id: int, target_action: str) -> str | None:
    async with get_user_lock(user_id):
        return await _fulfill_target_action_locked(user_id, target_action)


async def credit_user_payment(
    user_id: int, amount: int, invoice_id: str, provider: str = 'Platega', suppress_user_msg: bool = False
) -> tuple[bool, str | None]:
    if not invoice_id:
        return False, None
    async with aiosqlite.connect(DB_PATH) as lookup_db:
        async with lookup_db.execute('SELECT user_id FROM payments WHERE invoice_id = ?', (invoice_id,)) as cursor:
            payment_owner = await cursor.fetchone()
    if not payment_owner:
        return False, None
    actual_user_id = int(payment_owner[0])

    ref_id = None
    ref_bonus = 0
    applied_pct = REF_BASE_PERCENT
    new_ref_cnt = 0
    uname = ''
    user_notifications = 1
    target_action = ''
    newly_credited = False
    auto_activation_text = None

    async with get_user_lock(actual_user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('BEGIN IMMEDIATE')
            async with db.execute(
                '''SELECT user_id, amount, status, COALESCE(target_action, ''),
                          COALESCE(target_fulfillment_status, 'pending')
                   FROM payments WHERE invoice_id = ?''',
                (invoice_id,),
            ) as cursor:
                payment = await cursor.fetchone()
            if not payment:
                await db.rollback()
                return False, None
            actual_user_id, paid_amount = int(payment[0]), int(payment[1] or 0)
            status, target_action, fulfillment_status = str(payment[2] or ''), str(payment[3] or ''), str(payment[4] or 'pending')
            if actual_user_id != int(payment_owner[0]) or paid_amount <= 0:
                await db.rollback()
                return False, None
            if status != 'paid':
                if status.lower() not in ('pending', 'processing', 'confirmed', 'success'):
                    await db.rollback()
                    return False, None
                async with db.execute(
                    "UPDATE payments SET status = 'paid', target_fulfillment_status = ? WHERE invoice_id = ? AND status != 'paid'",
                    ('pending' if target_action else 'fulfilled', invoice_id),
                ) as cursor:
                    if cursor.rowcount != 1:
                        await db.rollback()
                        return False, None
                async with db.execute(
                    'UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE user_id = ?',
                    (paid_amount, actual_user_id),
                ) as cursor:
                    if cursor.rowcount != 1:
                        await db.rollback()
                        return False, None
                newly_credited = True
                async with db.execute(
                    '''SELECT referrer_id, username, COALESCE(has_paid, 0), COALESCE(bot_notifications, 1)
                       FROM users WHERE user_id = ?''',
                    (actual_user_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                if row:
                    ref_id, uname, has_paid, user_notifications = row[0], row[1] or '', int(row[2]), int(row[3])
                else:
                    ref_id, uname, has_paid, user_notifications = None, '', 0, 1
                if not has_paid:
                    await db.execute('UPDATE users SET has_paid = 1 WHERE user_id = ?', (actual_user_id,))
                if ref_id and int(ref_id) != actual_user_id:
                    if not has_paid:
                        await db.execute(
                            'UPDATE users SET ref_paid_count = COALESCE(ref_paid_count, 0) + 1 WHERE user_id = ?',
                            (ref_id,),
                        )
                    async with db.execute(
                        'SELECT COALESCE(ref_paid_count, 0), custom_ref_pct FROM users WHERE user_id = ?', (ref_id,)
                    ) as cursor:
                        ref_row = await cursor.fetchone()
                    new_ref_cnt = int(ref_row[0]) if ref_row else 0
                    custom_pct = ref_row[1] if ref_row else None
                    try:
                        base_pct, max_pct = await get_referral_settings(db)
                    except Exception:
                        base_pct, max_pct = REF_BASE_PERCENT, REF_MAX_PERCENT
                    base_pct = max(0, min(100, int(base_pct)))
                    max_pct = max(base_pct, min(100, int(max_pct)))
                    applied_pct = max(1, min(100, int(custom_pct))) if custom_pct is not None else min(max_pct, base_pct + new_ref_cnt)
                    ref_bonus = paid_amount * applied_pct // 100
                    await db.execute(
                        '''UPDATE users SET balance = COALESCE(balance, 0) + ?,
                                  ref_earned = COALESCE(ref_earned, 0) + ? WHERE user_id = ?''',
                        (ref_bonus, ref_bonus, ref_id),
                    )
            else:
                async with db.execute(
                    'SELECT username, COALESCE(bot_notifications, 1) FROM users WHERE user_id = ?', (actual_user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                if row:
                    uname, user_notifications = row[0] or '', int(row[1])
            should_fulfill = bool(target_action) and fulfillment_status != 'fulfilled'
            if should_fulfill:
                await db.execute(
                    "UPDATE payments SET target_fulfillment_status = 'processing' WHERE invoice_id = ?",
                    (invoice_id,),
                )
            await db.commit()

        if should_fulfill:
            try:
                auto_activation_text = await _fulfill_target_action_locked(actual_user_id, target_action)
            except Exception:
                logging.exception('Payment action fulfillment failed for invoice %s', invoice_id)
                auto_activation_text = 'Оплата зачислена на баланс, автоматическая активация временно не удалась.'
            async with aiosqlite.connect(DB_PATH) as db:
                state = 'fulfilled' if auto_activation_text and not auto_activation_text.startswith('Оплата получена, но') and not auto_activation_text.startswith('Оплата зачислена,') else 'failed'
                await db.execute(
                    'UPDATE payments SET target_fulfillment_status = ? WHERE invoice_id = ?', (state, invoice_id)
                )
                await db.commit()

    # An already-paid callback may retry only an unfulfilled target action; never repeat credits or notices.
    if not newly_credited:
        return False, auto_activation_text

    webapp_url = await sync_user_menu_button(actual_user_id)
    if ref_id and ref_bonus > 0:
        await sync_user_menu_button(int(ref_id))
        bar = make_progress_bar(new_ref_cnt, 20, 8)
        try:
            await bot.send_message(
                int(ref_id),
                f'🎁 <b>Партнерское вознаграждение +{ref_bonus} ₽!</b>\n\n'
                f'Ваш друг пополнил баланс на <code>{paid_amount} ₽</code>.\n'
                f'Ваша ставка: <b>{applied_pct}%</b>\n<code>{bar}</code>',
                parse_mode='HTML',
            )
        except Exception:
            pass
    if not suppress_user_msg and (user_notifications == 1 or auto_activation_text):
        msg_body = (
            f'{EMOJI_STAR} <b>Оплата {paid_amount} ₽ получена!</b>\n\n{auto_activation_text}'
            if auto_activation_text
            else f'{EMOJI_STAR} <b>Баланс пополнен на {paid_amount} ₽!</b>\n\nОткройте приложение PinPoint для управления подписками.'
        )
        try:
            await bot.send_message(
                actual_user_id, msg_body,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [styled_btn('📱 Открыть PinPoint', web_app=WebAppInfo(url=webapp_url), style='success')],
                    [styled_btn('👤 В кабинет', callback_data='profile', style='primary')],
                ]),
                parse_mode='HTML',
            )
        except Exception:
            pass
    uname_disp = f'@{html.escape(str(uname))}' if uname else 'Без @username'
    msg_text = (
        f'{EMOJI_STAR} <b>Новое пополнение ({html.escape(provider)})</b>\n\n'
        f'👤 Клиент: {uname_disp} (<code>{actual_user_id}</code>)\n'
        f'💳 Сумма: <code>{paid_amount} ₽</code>\n'
        f'🎯 Действие Mini App: <code>{html.escape(target_action or "Пополнение кошелька")}</code>\n'
        f'🤝 Реф. бонус ({applied_pct}%): <code>{ref_bonus} ₽</code>\n'
        f'🧾 Чек: <code>{html.escape(str(invoice_id))}</code>'
    )
    for admin_id in await DBManager.get_all_admin_ids():
        try:
            await bot.send_message(admin_id, msg_text, parse_mode='HTML')
        except Exception:
            pass
    return True, auto_activation_text


# ==========================================
# 6. СОСТОЯНИЯ FSM И КЛАВИАТУРЫ
# ==========================================
class AdminAuth(StatesGroup):
    login = State()
    password = State()


class AdminActions(StatesGroup):
    broadcast_text = State()
    search_user = State()
    sub_add_days = State()
    balance_amount = State()
    user_ref_pct = State()
    user_ref_count = State()
    create_promo_code = State()
    create_promo_type = State()
    create_promo_value = State()
    create_promo_uses = State()
    create_promo_per_user = State()
    edit_promo_uses = State()
    edit_promo_per_user = State()
    referral_setting = State()
    reply_ticket = State()


    review_reply = State()


class UserStates(StatesGroup):
    waiting_for_ticket = State()


async def get_main_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    webapp_target = await sync_user_menu_button(user_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [styled_btn('📱 Open PinPoint', web_app=WebAppInfo(url=webapp_target), style='success')],
            [
                styled_btn('👤 Personal Account', callback_data='profile', style='primary'),
                styled_btn('📲 How to Connect', callback_data='help_connect', style='primary'),
            ],
            [
                styled_btn('💬 Support Chat', callback_data='support_ticket', style='primary'),
                styled_btn('📢 Project News', url=REQUIRED_CHANNEL_URL, style='primary'),
            ],
            [styled_btn('⚖️ Legal Information', callback_data='legal_menu', style='danger')],
        ]
    )


async def build_main_menu_text(user_id: int, is_updated: bool = False) -> str:
    summary = await DBManager.get_user_summary(user_id)
    active_subs = await DBManager.get_active_subscriptions(user_id)

    if active_subs:
        sub_lines = []
        for i, s in enumerate(active_subs[:2], 1):
            left_gb = max(0.0, s['gb_limit'] - s['used_gb'])
            bar = make_progress_bar(left_gb, s['gb_limit'], 8)
            sub_lines.append(
                f"🟢 <b>Слот #{i} — {html.escape(str(s['tariff_name']))}</b>\n"
                f"╰ <code>{bar}</code> <b>{left_gb} ГБ</b> • до <code>{s['active_until_str']}</code>"
            )
        subs_summary = '\n\n'.join(sub_lines)
    else:
        subs_summary = (
            f'{EMOJI_WARN} <b>Нет активных подключений</b>\n'
            '╰ Нажмите зеленую кнопку <b>«📱 Открыть PinPoint»</b> ниже для выбора тарифа или активации 24ч теста.'
        )

    discount_badge = f'🏷 Ваша скидка: <b>{summary["discount_pct"]}%</b>   •   ' if summary['discount_pct'] > 0 else ''
    update_badge = f'{EMOJI_STAR} <i>Данные кабинета синхронизированы.</i>\n\n' if is_updated else ''
    return (
        f'{update_badge}'
        f'{EMOJI_STAR} <b>PinPoint VPN — Доступ в свободный интернет</b>\n\n'
        f"💳 Баланс: <b>{summary['balance']} ₽</b>   •   {discount_badge}🤝 Бонус: <b>{summary['ref_pct']}%</b>\n\n"
        f'{subs_summary}'
    )


def get_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [styled_btn('📊 Статистика сервиса', callback_data='admin_stats', style='primary')],
            [styled_btn('👥 Список всех клиентов', callback_data='admin_clients_0', style='primary')],
            [styled_btn('🔍 Управление по ID / Поиск', callback_data='admin_search_client', style='success')],
            [styled_btn('🎟 Manage Promo Codes', callback_data='admin_promos', style='primary')],
            [styled_btn('📢 Рассылка по сегментам', callback_data='admin_broadcast_menu', style='primary')],
            [styled_btn('🤝 Referral Settings', callback_data='admin_referral_settings')],
            [styled_btn('⭐️ Review Moderation', callback_data='review_list_pending_0')],
            [styled_btn('🔒 Log Out', callback_data='admin_logout')],
            [styled_btn('📦 Резервная копия БД', callback_data='admin_backup_db', style='primary')],
            [styled_btn('⬅️ Выход в меню', callback_data='start_menu', style='danger')],
        ]
    )


# ==========================================
# 7. ОБРАБОТКА ДЕЙСТВИЙ ИЗ MINI APP
# ==========================================
async def _send_or_edit(target, text: str, reply_markup: InlineKeyboardMarkup | None = None):
    if isinstance(target, CallbackQuery):
        try:
            return await target.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
        except TelegramBadRequest:
            return await target.message.answer(text, reply_markup=reply_markup, parse_mode='HTML')
    return await target.answer(text, reply_markup=reply_markup, parse_mode='HTML')


async def execute_topup_flow(target, user_id: int, username: str, amount: int, target_action: str = ''):
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return await _send_or_edit(target, '❌ Укажите корректную сумму пополнения.')
    if not 10 <= amount <= 100000:
        return await _send_or_edit(target, '❌ Сумма пополнения должна быть от 10 до 100 000 ₽.')
    if target_action:
        return await _send_or_edit(target, '❌ Для пополнения баланса действие покупки не допускается.')
    is_cb = isinstance(target, CallbackQuery)
    wait_msg = await (
        target.message.edit_text('⏳ Формирую счет на оплату...') if is_cb
        else target.answer('⏳ Формирую счет на оплату...')
    )
    edit_fn = target.message.edit_text if is_cb else wait_msg.edit_text
    pay_url, invoice_id = await PlategaService.create_invoice(user_id, amount, username, target_action='')
    webapp_url = await sync_user_menu_button(user_id)
    if pay_url and invoice_id:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [styled_btn(f'💳 Оплатить {amount} ₽ (СБП / Карта)', url=pay_url, style='success')],
            [styled_btn('🔄 Проверить оплату', callback_data=f'check_pay_{invoice_id}', style='primary')],
            [styled_btn('📱 Вернуться в PinPoint', web_app=WebAppInfo(url=webapp_url), style='primary')],
            [styled_btn('⬅️ В главное меню', callback_data='start_menu', style='danger')],
        ])
        return await edit_fn(
            f'💳 <b>Счет на сумму {amount} ₽ сформирован:</b>\n\n'
            'Оплатите по СБП или банковской картой по кнопке ниже. Сразу после оплаты баланс в приложении обновится автоматически.',
            reply_markup=kb, parse_mode='HTML',
        )
    menu_kb = await get_main_menu_kb(user_id)
    return await edit_fn(
        f'{EMOJI_WARN} Не удалось создать платежную ссылку. Попробуйте повторить запрос из приложения через минуту.',
        reply_markup=menu_kb, parse_mode='HTML',
    )


async def execute_buy_booster(message_or_cb, user_id: int, username: str, gb_val: int, slot_idx: int):
    async with get_user_lock(user_id):
        if gb_val not in BOOSTERS:
            return await _send_or_edit(message_or_cb, '❌ Выбран неверный пакет трафика.')
        booster = BOOSTERS[gb_val]
        active_subs = await DBManager.get_active_subscriptions(user_id)
        if not active_subs:
            return await _send_or_edit(
                message_or_cb,
                f'{EMOJI_WARN} <b>У вас нет активных подписок для докупки гигабайтов.</b>\n'
                'Выберите и подключите тариф в приложении PinPoint.',
                reply_markup=await get_main_menu_kb(user_id),
            )
        if not 0 <= slot_idx < len(active_subs):
            return await _send_or_edit(message_or_cb, '❌ Выбранный слот не найден.')
        target_sub = active_subs[slot_idx]
        summary = await DBManager.get_user_summary(user_id)
        balance = int(summary['balance'])
        if balance < booster['price']:
            missing = booster['price'] - balance
            pay_url, invoice_id = await PlategaService.create_invoice(
                user_id, missing, username, target_action=f'boost_{gb_val}_{slot_idx + 1}'
            )
            if pay_url and invoice_id:
                webapp_url = await sync_user_menu_button(user_id)
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [styled_btn(f'💳 Оплатить {missing} ₽ (СБП / Карта)', url=pay_url, style='success')],
                    [styled_btn('🔄 Проверить оплату', callback_data=f'check_pay_{invoice_id}', style='primary')],
                    [styled_btn('📱 Вернуться в PinPoint', web_app=WebAppInfo(url=webapp_url), style='primary')],
                    [styled_btn('⬅️ В главное меню', callback_data='start_menu', style='danger')],
                ])
                return await _send_or_edit(
                    message_or_cb,
                    f"➕ <b>Добавление пакета {booster['name']}</b>\n\n"
                    f"Ваш баланс: <code>{balance} ₽</code> • Стоимость: <code>{booster['price']} ₽</code>\n"
                    f"К оплате: <b>{missing} ₽</b> (пакет добавится автоматически сразу после оплаты)",
                    reply_markup=kb,
                )
            return await _send_or_edit(message_or_cb, '⚠️ Не удалось сформировать счет на оплату.')
        new_limit = int(target_sub['gb_limit']) + booster['gb']
        if not await H1CloudService.update_subscription(target_sub, traffic_limit_gb=new_limit):
            return await _send_or_edit(message_or_cb, '⚠️ Не удалось обновить лимит в VPN-панели. Баланс не списан.')
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('BEGIN IMMEDIATE')
            async with db.execute(
                'UPDATE users SET balance = COALESCE(balance, 0) - ? WHERE user_id = ? AND COALESCE(balance, 0) >= ?',
                (booster['price'], user_id, booster['price']),
            ) as cursor:
                if cursor.rowcount != 1:
                    await db.rollback()
                    return await _send_or_edit(message_or_cb, '❌ Баланс изменился; пакет не оплачен.')
            await db.execute(
                'UPDATE subscriptions SET gb_limit = gb_limit + ?, notified_traffic = 0 WHERE id = ? AND user_id = ?',
                (booster['gb'], target_sub['id'], user_id),
            )
            await db.commit()
        await _send_or_edit(
            message_or_cb,
            f"{EMOJI_STAR} <b>Пакет {booster['name']} успешно подключен!</b>\n\n"
            f"Новый лимит слота «{html.escape(str(target_sub['tariff_name']))}»: <b>{new_limit} ГБ</b>.",
            reply_markup=await get_main_menu_kb(user_id),
        )


async def execute_buy_tariff(message_or_cb, user_id: int, username: str, t_id: str):
    async with get_user_lock(user_id):
        is_cb = isinstance(message_or_cb, CallbackQuery)
        active_subs = await DBManager.get_active_subscriptions(user_id)
        menu_kb = await get_main_menu_kb(user_id)
        if len(active_subs) >= 2:
            return await _send_or_edit(
                message_or_cb,
                f'{EMOJI_WARN} <b>У вас уже активны оба доступных слота (2 из 2).</b>\n'
                'Откройте приложение PinPoint для управления вашими подключениями.', reply_markup=menu_kb,
            )
        summary = await DBManager.get_user_summary(user_id)
        if t_id == 'test':
            if summary['used_test']:
                return await _send_or_edit(
                    message_or_cb,
                    f'{EMOJI_WARN} <b>Бесплатный тестовый период уже был использован ранее.</b>\n'
                    'Выберите подходящий тариф в приложении PinPoint.', reply_markup=menu_kb,
                )
            wait_msg = await (
                message_or_cb.message.edit_text('⏳ Создаю тестовое подключение на 24 часа...') if is_cb
                else message_or_cb.answer('⏳ Создаю тестовое подключение на 24 часа...')
            )
            edit_target = message_or_cb.message.edit_text if is_cb else wait_msg.edit_text
            try:
                vpn_key = await H1CloudService.create_key(user_id, 1, 1, 10)
            except Exception:
                return await edit_target('⚠️ Не удалось создать тестовый ключ. Попробуйте позже.')
            new_until = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute('BEGIN IMMEDIATE')
                async with db.execute('SELECT COALESCE(used_test, 0) FROM users WHERE user_id = ?', (user_id,)) as cursor:
                    used_test = await cursor.fetchone()
                async with db.execute(
                    'SELECT COUNT(*) FROM subscriptions WHERE user_id = ? AND datetime(active_until) > datetime(?)',
                    (user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                ) as cursor:
                    slot_count = int((await cursor.fetchone())[0])
                if (used_test and int(used_test[0])) or slot_count >= 2:
                    await db.rollback()
                    return await edit_target('❌ Тест уже использован или нет свободного слота.')
                await db.execute('UPDATE users SET used_test = 1 WHERE user_id = ?', (user_id,))
                await db.execute(
                    '''INSERT INTO subscriptions (user_id, tariff_name, active_until, gb_limit, devices, vpn_key, sub_type)
                       VALUES (?, ?, ?, ?, ?, ?, 'test')''',
                    (user_id, '🆓 Тест 24ч', new_until, 10, 1, vpn_key),
                )
                await db.commit()
            await sync_user_menu_button(user_id)
            return await edit_target(
                f'{EMOJI_STAR} <b>Тестовый доступ на 24 часа активирован!</b>\n\n'
                'Откройте приложение PinPoint и нажмите <b>«Подключить устройство в 1 клик»</b>.\n\n'
                f'🔑 Ваш ключ подписки:\n<code>{html.escape(vpn_key)}</code>',
                parse_mode='HTML', reply_markup=await get_main_menu_kb(user_id),
            )
        resolved = resolve_tariff_id(t_id)
        if not resolved or resolved not in TARIFFS:
            return await _send_or_edit(message_or_cb, '❌ Выбранный тариф не найден.', reply_markup=menu_kb)
        result = await _activate_tariff_locked(user_id, t_id)
        if not result.get('ok') and result.get('reason') == 'insufficient_balance':
            tariff = TARIFFS[resolved]
            balance = int(result.get('balance', summary['balance']))
            due = max(10, int(result.get('price', tariff['price'])) - balance)
            pay_url, invoice_id = await PlategaService.create_invoice(
                user_id, due, username, target_action=f'buy_{resolved}'
            )
            if not pay_url or not invoice_id:
                return await _send_or_edit(message_or_cb, '⚠️ Не удалось сформировать счет на оплату. Попробуйте позже.')
            webapp_url = await sync_user_menu_button(user_id)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [styled_btn(f'💳 Оплатить {due} ₽ (СБП / Карта)', url=pay_url, style='success')],
                [styled_btn('🔄 Проверить оплату', callback_data=f'check_pay_{invoice_id}', style='primary')],
                [styled_btn('📱 Вернуться в PinPoint', web_app=WebAppInfo(url=webapp_url), style='primary')],
                [styled_btn('⬅️ В главное меню', callback_data='start_menu', style='danger')],
            ])
            return await _send_or_edit(
                message_or_cb,
                f"💎 <b>Оформление тарифа «{TARIFFS[resolved]['name']}»</b>\n\n"
                f"Баланс: <code>{balance} ₽</code> • К оплате: <b>{due} ₽</b>\n"
                '<i>Сразу после оплаты тариф подключится автоматически!</i>', reply_markup=kb,
            )
        if not result.get('ok'):
            text = '❌ Нет свободного слота.' if result.get('reason') == 'slots_full' else '⚠️ Не удалось активировать тариф. Попробуйте позже.'
            return await _send_or_edit(message_or_cb, text, reply_markup=menu_kb)
        tariff = result['tariff']
        when = parse_any_datetime(result['active_until'])
        until_text = when.strftime('%d.%m.%Y %H:%M') if when else result['active_until']
        note = f" (скидка <b>{result['discount_pct']}%</b>: <code>{result['price']} ₽</code>)" if result['discount_pct'] else ''
        await sync_user_menu_button(user_id)
        await _send_or_edit(
            message_or_cb,
            f"{EMOJI_STAR} <b>Тариф «{tariff['name']}» успешно подключен!</b>{note}\n\n"
            f"Срок: <b>{tariff['days']} дн.</b> (до <code>{until_text}</code>)\n"
            f"Лимит: <b>{tariff['limit_gb']} ГБ</b> • Устройств: <b>{tariff['devices']}</b>\n\n"
            f'🔑 Ваш ключ подписки:\n<code>{html.escape(result["key"])}</code>',
            reply_markup=await get_main_menu_kb(user_id),
        )




# ==========================================
# 8. МАРШРУТИЗАТОР /START
# ==========================================
async def dispatch_start_payload(target, user_id: int, username: str, arg: str | None) -> bool:
    if not arg:
        return False
    if arg.startswith('topup_'):
        amount_str = arg.replace('topup_', '')
        if amount_str.isascii() and amount_str.isdigit():
            await execute_topup_flow(target, user_id, username, int(amount_str))
            return True
    elif arg.startswith('promo_'):
        code = arg.replace('promo_', '').strip().upper()
        await execute_promo_code(target, user_id, code)
        return True
    elif arg.startswith('boost_'):
        parts = arg.split('_')
        if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
            await execute_buy_booster(target, user_id, username, int(parts[1]), int(parts[2]) - 1)
            return True
    elif arg.startswith('buy_'):
        plan_id = arg.replace('buy_', '').strip()
        await execute_buy_tariff(target, user_id, username, plan_id)
        return True
    return False


async def verify_onboarding_gates(target, user_id: int, state: FSMContext, pending_arg: str | None = None) -> bool:
    if pending_arg and not pending_arg.isdigit():
        await state.update_data(pending_arg=pending_arg)

    if not await check_channel_subscription(user_id):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [styled_btn('📢 Project News', url=REQUIRED_CHANNEL_URL, style='primary')],
                [styled_btn('🔄 Проверить подписку', callback_data='check_subscription_join', style='success')],
            ]
        )
        await _send_or_edit(
            target,
            f'{EMOJI_STAR} <b>Добро пожаловать в PinPoint VPN!</b>\n\n'
            'Для использования сервиса и доступа к подключениям подпишитесь на наш официальный новостной канал:',
            reply_markup=kb,
        )
        return False

    summary = await DBManager.get_user_summary(user_id)
    if not summary['agreed_to_tos']:
        if pending_arg and pending_arg.startswith(('buy_', 'topup_', 'boost_', 'promo_')):
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute('UPDATE users SET agreed_to_tos = 1 WHERE user_id = ?', (user_id,))
                await db.commit()
            return True

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    styled_btn(
                        '📜 Пользовательское соглашение',
                        url='https://telegra.ph/Polzovatelskoe-soglashenie-10-15-51',
                        style='danger',
                    )
                ],
                [
                    styled_btn(
                        '🛡 Политика конфиденциальности',
                        url='https://telegra.ph/Politika-konfidencialnosti-10-15-99',
                        style='danger',
                    )
                ],
                [styled_btn('✅ Принять и продолжить', callback_data='accept_tos', style='success')],
            ]
        )
        await _send_or_edit(
            target,
            f'{EMOJI_STAR} <b>PinPoint VPN — Доступ в свободный интернет</b>\n\n'
            'Пожалуйста, подтвердите согласие с правилами сервиса для входа в личный кабинет:',
            reply_markup=kb,
        )
        return False

    return True


@dp.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or ''
    arg = (command.args or '').strip()

    ref_id = int(arg) if arg.isdigit() and int(arg) != user_id else None
    await DBManager.upsert_user(user_id, username, ref_id)

    await state.clear()
    can_proceed = await verify_onboarding_gates(message, user_id, state, pending_arg=arg)
    if not can_proceed:
        return

    if await dispatch_start_payload(message, user_id, username, arg):
        return

    menu_kb = await get_main_menu_kb(user_id)
    menu_text = await build_main_menu_text(user_id, is_updated=True)
    await message.answer(menu_text, reply_markup=menu_kb, parse_mode='HTML')


@dp.callback_query(F.data == 'check_subscription_join')
async def check_subscription_join_cb(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_channel_subscription(user_id):
        return await callback.answer('❌ Вы еще не подписались на новостной канал!', show_alert=True)

    await callback.answer('✅ Подписка подтверждена!')
    data = await state.get_data()
    pending_arg = data.get('pending_arg')

    if not await verify_onboarding_gates(callback, user_id, state, pending_arg=pending_arg):
        return

    await state.clear()
    if pending_arg and await dispatch_start_payload(callback, user_id, callback.from_user.username or '', pending_arg):
        return

    menu_kb = await get_main_menu_kb(user_id)
    menu_text = await build_main_menu_text(user_id, is_updated=True)
    await callback.message.edit_text(menu_text, reply_markup=menu_kb, parse_mode='HTML')


@dp.callback_query(F.data == 'accept_tos')
async def accept_tos_cb(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET agreed_to_tos = 1 WHERE user_id = ?', (user_id,))
        await db.commit()

    data = await state.get_data()
    pending_arg = data.get('pending_arg')

    if not await verify_onboarding_gates(callback, user_id, state, pending_arg=pending_arg):
        return

    await state.clear()
    if pending_arg and await dispatch_start_payload(callback, user_id, callback.from_user.username or '', pending_arg):
        return

    menu_kb = await get_main_menu_kb(user_id)
    menu_text = await build_main_menu_text(user_id)
    await callback.message.edit_text(menu_text, reply_markup=menu_kb, parse_mode='HTML')


# ==========================================
# 9. ПОЛЬЗОВАТЕЛЬСКИЕ РАЗДЕЛЫ И ИНСТРУКЦИИ
# ==========================================
@dp.callback_query(F.data == 'start_menu')
async def back_to_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    menu_kb = await get_main_menu_kb(callback.from_user.id)
    menu_text = await build_main_menu_text(callback.from_user.id, is_updated=True)
    await _send_or_edit(callback, menu_text, reply_markup=menu_kb)


@dp.callback_query(F.data == 'legal_menu')
async def show_legal_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                styled_btn(
                    '📜 Пользовательское соглашение',
                    url='https://telegra.ph/Polzovatelskoe-soglashenie-10-15-51',
                    style='danger',
                )
            ],
            [
                styled_btn(
                    '🛡 Политика конфиденциальности',
                    url='https://telegra.ph/Politika-konfidencialnosti-10-15-99',
                    style='danger',
                )
            ],
            [styled_btn('⬅️ Назад в меню', callback_data='start_menu', style='primary')],
        ]
    )
    await _send_or_edit(
        callback,
        '⚖️ <b>Юридическая информация PinPoint VPN</b>\n\n'
        'Ознакомьтесь с официальными правилами предоставления услуг и политикой обработки данных:',
        reply_markup=kb,
    )


@dp.callback_query(F.data == 'help_connect')
async def show_help_devices(callback: CallbackQuery):
    webapp_url = await build_webapp_url(callback.from_user.id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [styled_btn('📱 Подключить в 1 клик в приложении', web_app=WebAppInfo(url=webapp_url), style='success')],
            [
                styled_btn('🤖 Android', callback_data='device_android', style='primary'),
                styled_btn('🍏 iPhone / iPad', callback_data='device_ios', style='primary'),
            ],
            [
                styled_btn('🪟 Windows', callback_data='device_windows', style='primary'),
                styled_btn('💻 macOS', callback_data='device_macos', style='primary'),
            ],
            [styled_btn('⬅️ Назад в меню', callback_data='start_menu', style='danger')],
        ]
    )
    await _send_or_edit(
        callback,
        '📲 <b>Как подключить PinPoint VPN:</b>\n\n'
        'Вы можете настроить подключение автоматически в 1 клик через наше приложение или выбрать ваше устройство для пошаговой инструкции:',
        reply_markup=kb,
    )


@dp.callback_query(F.data.startswith('device_'))
async def show_app_selection(callback: CallbackQuery):
    device = callback.data.split('_')[1]
    os_names = {
        'android': '🤖 Android',
        'ios': '🍏 iPhone / iPad',
        'windows': '🪟 Windows',
        'macos': '💻 macOS',
    }
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                styled_btn('Happ', callback_data=f'app_{device}_happ', style='success'),
                styled_btn('Hiddify', callback_data=f'app_{device}_hiddify', style='success'),
            ],
            [
                styled_btn('Incy', callback_data=f'app_{device}_incy', style='primary'),
                styled_btn('V2raytun', callback_data=f'app_{device}_v2raytun', style='primary'),
            ],
            [styled_btn('⬅️ Выбрать другое устройство', callback_data='help_connect', style='primary')],
            [styled_btn('⬅️ В главное меню', callback_data='start_menu', style='danger')],
        ]
    )
    await _send_or_edit(
        callback,
        f"Платформа: <b>{os_names.get(device, 'Устройство')}</b>\n"
        'Выберите поддерживаемое приложение для подключения:',
        reply_markup=kb,
    )


@dp.callback_query(F.data.startswith('app_'))
async def show_app_instruction(callback: CallbackQuery):
    parts = callback.data.split('_')
    device = parts[1] if len(parts) > 1 else 'android'
    app_id = parts[2] if len(parts) > 2 else 'happ'
    app_info = SUPPORTED_APPS.get(app_id, SUPPORTED_APPS['happ'])

    text = f"⚙️ <b>Настройка через {app_info['title']}:</b>\n\n{app_info['steps']}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [styled_btn('👤 Скопировать ключ в кабинете', callback_data='profile', style='success')],
            [styled_btn('⬅️ К выбору приложения', callback_data=f'device_{device}', style='primary')],
            [styled_btn('⬅️ В главное меню', callback_data='start_menu', style='danger')],
        ]
    )
    await _send_or_edit(callback, text, reply_markup=kb)


@dp.callback_query(F.data == 'profile')
async def show_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    summary = await DBManager.get_user_summary(user_id)
    ref_bar = make_progress_bar(summary['ref_cnt'], 20, 8)
    active_subs = await DBManager.get_active_subscriptions(user_id)

    if active_subs:
        subs_blocks = []
        for idx, s in enumerate(active_subs[:2], start=1):
            left_gb = max(0.0, s['gb_limit'] - s['used_gb'])
            t_bar = make_progress_bar(left_gb, s['gb_limit'], 8)
            subs_blocks.append(
                f"🟢 <b>Слот #{idx}: {html.escape(str(s['tariff_name']))}</b> (до <code>{s['active_until_str']}</code>)\n"
                f"📦 Трафик: <code>{t_bar}</code> <b>{left_gb} / {s['gb_limit']} ГБ</b> • Устройств: <b>{s['devices']}</b>\n"
                f"🔑 Ключ (нажмите для копирования):\n<code>{html.escape(str(s['vpn_key']))}</code>"
            )
        sub_text = '\n\n'.join(subs_blocks)
    else:
        sub_text = '⚪️ <b>Нет активных подписок.</b> Откройте приложение PinPoint для выбора тарифа.'

    discount_line = f"🏷 <b>Ваша скидка на тарифы:</b> <code>{summary['discount_pct']}%</code>\n" if summary['discount_pct'] > 0 else ""
    bot_uname = await get_bot_username()
    text = (
        f'👤 <b>Ваш личный кабинет</b>\n\n'
        f"💳 <b>Баланс:</b> <code>{summary['balance']} ₽</code>\n"
        f'{discount_line}'
        f'🤝 <b>Партнерская программа:</b>\n'
        f"• Ваша ставка: <b>{summary['ref_pct']}%</b>"
        f"{' (фиксированная)' if summary['custom_ref_pct'] is not None else ' (+1% за каждого друга)'}\n"
        f"• Прогресс: <code>{ref_bar}</code> ({summary['ref_cnt']}/20 друзей)\n"
        f"• Заработано: <b>{summary['ref_earn']} ₽</b>\n"
        f'• Ссылка для друзей:\n<code>https://t.me/{bot_uname}?start={user_id}</code>\n\n'
        f'{EMOJI_STAR} <b>Ваши подключения ({len(active_subs)}/2):</b>\n{sub_text}'
    )

    webapp_url_user = await sync_user_menu_button(user_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [styled_btn('📱 Открыть PinPoint (Тарифы и Кошелек)', web_app=WebAppInfo(url=webapp_url_user), style='success')],
            [styled_btn('⬅️ Назад в меню', callback_data='start_menu', style='danger')],
        ]
    )
    await _send_or_edit(callback, text, reply_markup=kb)


@dp.callback_query(F.data.startswith('check_pay_'))
async def check_payment_callback(callback: CallbackQuery):
    invoice_id = callback.data.replace('check_pay_', '')
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT amount, status FROM payments WHERE invoice_id = ? AND user_id = ?', (invoice_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()

    if not row:
        return await callback.answer('Счет не найден.', show_alert=True)

    amount, status = row
    if status == 'paid':
        await callback.answer('✅ Счет уже оплачен и обработан!', show_alert=False)
        return await show_profile(callback)

    if await PlategaService.check_status(invoice_id):
        credited, auto_text = await credit_user_payment(user_id, amount, invoice_id, suppress_user_msg=True)
        webapp_url = await sync_user_menu_button(user_id)
        result_msg = (
            f'🎉 <b>Оплата {amount} ₽ подтверждена!</b>\n\n{auto_text}'
            if auto_text
            else f'🎉 <b>Оплата подтверждена!</b>\nВаш баланс пополнен на <b>{amount} ₽</b>.'
        )
        await _send_or_edit(
            callback,
            result_msg,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [styled_btn('📱 Open PinPoint', web_app=WebAppInfo(url=webapp_url), style='success')],
                    [styled_btn('👤 Перейти в кабинет', callback_data='profile', style='primary')],
                ]
            ),
        )
    else:
        await callback.answer('⏳ Платеж еще обрабатывается банком. Повторите через несколько секунд.', show_alert=True)


# ==========================================
# 10. ЧАТ ПОДДЕРЖКИ (ТИКЕТЫ)
# ==========================================
@dp.callback_query(F.data == 'support_ticket')
async def support_ticket_start(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[[styled_btn('⬅️ Отмена', callback_data='start_menu', style='danger')]])
    await _send_or_edit(
        callback,
        '💬 <b>Чат поддержки PinPoint</b>\n\n'
        'Опишите ваш вопрос или проблему одним сообщением. Оператор ответит вам прямо в этом диалоге:',
        reply_markup=kb,
    )
    await state.set_state(UserStates.waiting_for_ticket)


@dp.message(UserStates.waiting_for_ticket)
async def support_ticket_send(message: Message, state: FSMContext):
    if not message.text or len(message.text) > 2500:
        return await message.answer('Пожалуйста, отправьте текстовое сообщение длиной до 2500 символов.')
    await state.clear()
    user_id = message.from_user.id
    username_str = f'@{html.escape(message.from_user.username)}' if message.from_user.username else 'Без @username'
    safe_text = html.escape(message.text)

    ticket_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [styled_btn('✉️ Ответить клиенту', callback_data=f'adm_reply_{user_id}', style='success')],
            [styled_btn('👤 Управление клиентом', callback_data=f'usr_view_{user_id}', style='primary')],
        ]
    )

    admin_msg_text = (
        f'📩 <b>Новое обращение в поддержку!</b>\n\n'
        f'👤 <b>От:</b> {username_str} (<code>{user_id}</code>)\n'
        f"📅 <b>Время:</b> <code>{datetime.now().strftime('%d.%m.%Y %H:%M')}</code>\n"
        f'━━━━━━━━━━━━━━━━━━\n'
        f'{safe_text}\n'
        f'━━━━━━━━━━━━━━━━━━\n'
        f'💡 <i>Нажмите кнопку ниже или ответьте через Reply на это сообщение.</i>'
    )

    sent_count = 0
    for adm_id in await DBManager.get_all_admin_ids():
        try:
            await bot.send_message(adm_id, admin_msg_text, reply_markup=ticket_kb, parse_mode='HTML')
            sent_count += 1
        except Exception:
            pass

    menu_kb = await get_main_menu_kb(user_id)
    if sent_count > 0:
        await message.answer(
            f'{EMOJI_STAR} <b>Ваше сообщение передано в поддержку!</b> Ожидайте ответа в этом чате.',
            reply_markup=menu_kb,
            parse_mode='HTML',
        )
    else:
        await message.answer(
            f'{EMOJI_WARN} Ваше обращение зарегистрировано. Мы ответим вам при первой возможности.',
            reply_markup=menu_kb,
            parse_mode='HTML',
        )


@dp.message(StateFilter(None), F.reply_to_message)
async def admin_reply_via_native_quote(message: Message):
    if not await is_admin(message.from_user.id):
        return
    quoted_text = message.reply_to_message.text or ''
    if (
        message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == bot.id
        and 'Новое обращение в поддержку!' in quoted_text
        and '(' in quoted_text
    ):
        try:
            target_id = int(quoted_text.split('(')[1].split(')')[0])
            safe_reply = html.escape(message.text or '')
            await bot.send_message(
                target_id,
                f'{EMOJI_STAR} <b>Ответ поддержки PinPoint:</b>\n\n{safe_reply}',
                parse_mode='HTML',
            )
            await message.reply(f'✅ Ответ доставлен пользователю <code>{target_id}</code>.', parse_mode='HTML')
        except Exception as e:
            await message.reply(f'❌ Ошибка отправки ответа: {e}')


# ==========================================
# 11. АДМИН-ПАНЕЛЬ: УПРАВЛЕНИЕ РЕФЕРАЛАМИ И ПРОМОКОДАМИ
# ==========================================
async def send_database_backup(message: Message):
    def snapshot():
        with sqlite3.connect(DB_PATH) as source, sqlite3.connect(':memory:') as target:
            source.backup(target)
            return target.serialize()

    content = await asyncio.to_thread(snapshot)
    await message.answer_document(
        BufferedInputFile(content, filename='database.db'),
        caption='📦 Резервная копия базы данных PinPoint',
    )


async def handle_failed_attempt(message: Message, state: FSMContext):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE users SET failed_attempts = COALESCE(failed_attempts, 0) + 1 WHERE user_id = ?', (user_id,)
        )
        await db.commit()
        async with db.execute('SELECT failed_attempts FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            attempts = row[0] if row else 1

    if attempts >= MAX_ATTEMPTS:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
            await db.commit()
        await message.answer('🚫 Превышен лимит попыток. Аккаунт заморожен.')
        await state.clear()
    else:
        await message.answer(f'❌ Неверные данные. Осталось попыток: {MAX_ATTEMPTS - attempts}\nПовторите ввод:')


@dp.message(Command('admin'))
async def admin_start(message: Message, state: FSMContext):
    if not await DBManager.is_admin(message.from_user.id):
        return await message.answer('Доступ запрещён.')
    await state.clear()
    await DBManager.upsert_user(message.from_user.id, message.from_user.username or '')
    if await is_admin(message.from_user.id):
        return await message.answer('Панель администратора', reply_markup=get_admin_kb())
    await message.answer('🔐 Введите логин администратора:')
    await state.set_state(AdminAuth.login)


@dp.message(AdminAuth.login)
async def admin_login(message: Message, state: FSMContext):
    if message.text and hmac.compare_digest(message.text.strip().lower().encode(), ADMIN_LOGIN.lower().encode()):
        await message.answer('🔑 Введите пароль администратора:')
        await state.set_state(AdminAuth.password)
    else:
        await handle_failed_attempt(message, state)


@dp.message(AdminAuth.password)
async def admin_password(message: Message, state: FSMContext):
    if message.text and hmac.compare_digest(message.text.strip().encode(), ADMIN_PASS.encode()):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('UPDATE users SET failed_attempts = 0 WHERE user_id = ?', (message.from_user.id,))
            await db.execute('UPDATE admins SET is_authenticated = 1 WHERE user_id = ?', (message.from_user.id,))
            await db.commit()
        await message.answer(
            '✅ <b>Доступ в панель управления открыт.</b>', reply_markup=get_admin_kb(), parse_mode='HTML'
        )
        await state.clear()
    else:
        await handle_failed_attempt(message, state)


@dp.message(Command('backup'))
async def cmd_backup(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await send_database_backup(message)


@dp.callback_query(F.data == 'admin_backup_db')
async def cb_backup(callback: CallbackQuery):
    await send_database_backup(callback.message)
    await callback.answer('Резервная копия отправлена!')


@dp.callback_query(F.data == 'admin_menu')
async def back_to_admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _send_or_edit(callback, '🛠 <b>Панель управления администратора</b>', reply_markup=get_admin_kb())




@dp.callback_query(F.data == 'admin_logout')
async def admin_logout(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return await callback.answer('Доступ запрещён.', show_alert=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE admins SET is_authenticated = 0 WHERE user_id = ?', (callback.from_user.id,))
        await db.commit()
    await state.clear()
    await _send_or_edit(callback, '🔒 Вы вышли из панели администратора. Для входа используйте /admin.')


@dp.callback_query(F.data == 'admin_referral_settings')
async def admin_referral_settings(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()
    base, maximum = await get_referral_settings()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [styled_btn('Базовый процент', callback_data='admin_refset_base')],
        [styled_btn('Максимальный процент', callback_data='admin_refset_max')],
        [styled_btn('⬅️ Назад', callback_data='admin_menu')],
    ])
    await _send_or_edit(callback, f'🤝 Базовый процент: {base}%\nМаксимальный процент: {maximum}%', kb)


@dp.callback_query(F.data.in_({'admin_refset_base', 'admin_refset_max'}))
async def admin_referral_edit(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.update_data(referral_key='ref_base_pct' if callback.data.endswith('_base') else 'ref_max_pct')
    await state.set_state(AdminActions.referral_setting)
    await _send_or_edit(callback, 'Введите целый процент от 1 до 100. Базовый процент не может превышать максимальный.',
                        InlineKeyboardMarkup(inline_keyboard=[[styled_btn('Отмена', callback_data='admin_referral_settings')]]))


@dp.message(AdminActions.referral_setting)
async def admin_referral_save(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    raw = (message.text or '').strip()
    if not raw.isascii() or not raw.isdigit() or not 1 <= int(raw) <= 100:
        return await message.answer('Введите целое число от 1 до 100.')
    key = (await state.get_data()).get('referral_key')
    if key not in ('ref_base_pct', 'ref_max_pct'):
        return await state.clear()
    value = int(raw)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('BEGIN IMMEDIATE')
        base, maximum = await get_referral_settings(db)
        if (key == 'ref_base_pct' and value > maximum) or (key == 'ref_max_pct' and value < base):
            await db.rollback()
            return await message.answer('Базовый процент не может превышать максимальный.')
        await db.execute('INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, str(value)))
        await db.commit()
    await state.clear()
    await message.answer('✅ Реферальные настройки сохранены.', reply_markup=get_admin_kb())


@dp.callback_query(F.data == 'admin_stats')
async def show_admin_stats(callback: CallbackQuery):
    now = datetime.now()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id, used_test, is_banned, balance FROM users') as cursor:
            users = await cursor.fetchall()
        async with db.execute('SELECT active_until, sub_type FROM subscriptions') as s_cursor:
            subs = await s_cursor.fetchall()
        async with db.execute('SELECT SUM(amount) FROM payments WHERE status = "paid"') as p_cursor:
            p_row = await p_cursor.fetchone()
            total_revenue = p_row[0] if p_row and p_row[0] else 0

    total_users = len(users)
    banned_count = sum(1 for u in users if u[2])
    total_balances = sum((u[3] or 0) for u in users)
    total_used_test = sum(1 for u in users if u[1])

    active_paid = sum(1 for act, st in subs if (d := parse_any_datetime(act)) and d > now and st != 'test')
    active_test = sum(1 for act, st in subs if (d := parse_any_datetime(act)) and d > now and st == 'test')

    text = (
        '📊 <b>Статистика сервиса PinPoint</b>\n\n'
        f'👥 Всего пользователей: <b>{total_users}</b>\n'
        f'💎 Активных платных подписок: <b>{active_paid}</b>\n'
        f'🆓 Активных тестов: <b>{active_test}</b>\n'
        f'🧪 Всего брали тест: <b>{total_used_test}</b>\n'
        f'❄️ Заморожено аккаунтов: <b>{banned_count}</b>\n\n'
        f'💳 Средств на балансах: <b>{total_balances} ₽</b>\n'
        f'💰 Сумма всех пополнений: <b>{total_revenue} ₽</b>'
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [styled_btn('🔄 Обновить данные', callback_data='admin_stats', style='primary')],
            [styled_btn('⬅️ Назад в админку', callback_data='admin_menu', style='danger')],
        ]
    )
    await _send_or_edit(callback, text, reply_markup=kb)


# --- УПРАВЛЕНИЕ КЛИЕНТАМИ И ИНДИВИДУАЛЬНОЙ РЕФЕРАЛКОЙ ---
@dp.callback_query(F.data.startswith('admin_clients_'))
async def admin_list_clients(callback: CallbackQuery):
    page = int(callback.data.split('_')[2])
    per_page = 8
    offset = page * per_page

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT COUNT(*) FROM users') as c:
            total_count = (await c.fetchone())[0]
        async with db.execute(
            'SELECT user_id, username, is_banned, balance FROM users ORDER BY user_id DESC LIMIT ? OFFSET ?',
            (per_page, offset),
        ) as cursor:
            users = await cursor.fetchall()

    if not users:
        return await callback.answer('Список клиентов пуст.', show_alert=True)

    kb = []
    for u_id, uname, is_banned, bal in users:
        ban_icon = '❄️ ' if is_banned else '👤 '
        uname_str = f'@{uname}' if uname else 'Без имени'
        kb.append(
            [
                styled_btn(
                    f'{ban_icon}{u_id} | {uname_str} ({bal or 0}₽)',
                    callback_data=f'usr_view_{u_id}',
                    style='primary',
                )
            ]
        )

    nav_row = []
    if page > 0:
        nav_row.append(styled_btn('⬅️ Назад', callback_data=f'admin_clients_{page - 1}', style='primary'))
    if offset + per_page < total_count:
        nav_row.append(styled_btn('Вперед ➡️', callback_data=f'admin_clients_{page + 1}', style='primary'))
    if nav_row:
        kb.append(nav_row)

    kb.append([styled_btn('⬅️ В админку', callback_data='admin_menu', style='danger')])
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    await _send_or_edit(
        callback,
        f'👥 <b>Клиенты сервиса (Всего: {total_count})</b>\nСтраница {page + 1} из {total_pages}',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
    )


@dp.callback_query(F.data == 'admin_search_client')
async def ask_search_client(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[[styled_btn('⬅️ Отмена', callback_data='admin_menu', style='danger')]])
    await _send_or_edit(
        callback,
        '🔍 <b>Управление по ID / Поиск клиента</b>\n\n'
        'Введите Telegram ID (можно ввести ID для настройки подписки/рефералки) или @username:',
        reply_markup=kb,
    )
    await state.set_state(AdminActions.search_user)


@dp.message(AdminActions.search_user)
async def process_search_client(message: Message, state: FSMContext):
    query = (message.text or '').strip().lstrip('@')
    row = None
    async with aiosqlite.connect(DB_PATH) as db:
        if query.isdigit():
            uid_int = int(query)
            await db.execute('INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, "", 0)', (uid_int,))
            await db.commit()
            row = (uid_int,)
        else:
            async with db.execute('SELECT user_id FROM users WHERE LOWER(username) = LOWER(?)', (query,)) as cursor:
                row = await cursor.fetchone()

    if not row:
        return await message.answer('❌ Клиент с таким @username не найден в базе.', reply_markup=get_admin_kb())

    await state.clear()
    text, kb = await render_user_card(row[0])
    await message.answer(text, reply_markup=kb, parse_mode='HTML')


async def render_user_card(target_id: int):
    summary = await DBManager.get_user_summary(target_id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT COALESCE(amount, 0), COALESCE(created_at, "") FROM payments WHERE user_id = ? AND status = "paid" ORDER BY rowid DESC LIMIT 3',
            (target_id,),
        ) as c2:
            pays = await c2.fetchall()

    active_subs = await DBManager.get_active_subscriptions(target_id)
    if active_subs:
        status_str = '\n'.join(
            [
                f"• Слот #{i}: {html.escape(str(s['tariff_name']))} ({s['gb_limit']} ГБ, до {s['active_until_str']})"
                for i, s in enumerate(active_subs, 1)
            ]
        )
    else:
        status_str = '⚪️ Нет активных подписок'

    pay_str = (
        '\n'.join([f"• <code>{p[0]} ₽</code> ({str(p[1])[:10] if p[1] else 'Ранее'})" for p in pays])
        if pays
        else 'Нет платежей'
    )
    ban_str = '❄️ ЗАМОРОЖЕН' if summary['is_banned'] else '🟢 Активен'
    uname_disp = f"@{html.escape(summary['username'])}" if summary['username'] else 'Не указан'
    discount_str = f" • <b>Скидка:</b> <code>{summary['discount_pct']}%</code>" if summary['discount_pct'] > 0 else ""

    if summary['custom_ref_pct'] is not None:
        ref_status_desc = f"<b>{summary['custom_ref_pct']}%</b> <i>(индивидуальная фиксированная)</i>"
    else:
        ref_status_desc = f"<b>{summary['ref_pct']}%</b> <i>(стандартная по прогрессу)</i>"

    text = (
        f'👤 <b>Управление клиентом <code>{target_id}</code></b>\n'
        f'🏷 <b>Username:</b> {uname_disp} • <b>Статус:</b> {ban_str}{discount_str}\n\n'
        f"💳 <b>Баланс:</b> <code>{summary['balance']} ₽</code>\n"
        f"🤝 <b>Реферальная ставка:</b> {ref_status_desc}\n"
        f"👥 <b>Рефералов (оплативших):</b> <code>{summary['ref_cnt']}</code> • <b>Заработано:</b> <code>{summary['ref_earn']} ₽</code>\n\n"
        f'{EMOJI_STAR} <b>Подписки ({len(active_subs)}/2):</b>\n{status_str}\n\n'
        f'🧾 <b>Последние платежи:</b>\n{pay_str}'
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                styled_btn('💰 Баланс', callback_data=f'usr_bal_{target_id}', style='primary'),
                styled_btn('✉️ Написать', callback_data=f'adm_reply_{target_id}', style='primary'),
            ],
            [
                styled_btn('🤝 Изменить реф. %', callback_data=f'usr_refpct_{target_id}', style='success'),
                styled_btn('👥 Изменить кол-во рефералов', callback_data=f'usr_refcnt_{target_id}', style='primary'),
            ],
            [styled_btn('➕ Выдать / изменить дни подписки', callback_data=f'usr_days_{target_id}', style='success')],
            [
                styled_btn('🚀 Выдать Базовый (30д)', callback_data=f'usr_give_{target_id}_base', style='success'),
                styled_btn('🔥 Выдать ХИТ (90д)', callback_data=f'usr_give_{target_id}_hit', style='success'),
            ],
            [styled_btn('❄️ Заморозить / Разморозить', callback_data=f'usr_ban_{target_id}', style='primary')],
            [styled_btn('🗑 Аннулировать подписки', callback_data=f'usr_reset_{target_id}', style='danger')],
            [styled_btn('👥 К списку клиентов', callback_data='admin_clients_0', style='primary')],
            [styled_btn('⬅️ В админку', callback_data='admin_menu', style='danger')],
        ]
    )
    return text, kb


@dp.callback_query(F.data.startswith('usr_refpct_'))
async def ask_usr_refpct(callback: CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split('_')[2])
    await state.update_data(target_id=target_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [styled_btn('🔄 Сбросить на глобальные настройки', callback_data=f'usr_refreset_{target_id}', style='primary')],
            [styled_btn('⬅️ Отмена', callback_data=f'usr_view_{target_id}', style='danger')],
        ]
    )
    await _send_or_edit(
        callback,
        f'🤝 <b>Настройка индивидуального процента отчислений</b> для ID <code>{target_id}</code>\n\n'
        'Введите целое число от <b>1</b> до <b>100</b> (например <code>25</code>, <code>40</code> или <code>50</code>) '
        'либо нажмите кнопку ниже, чтобы вернуть стандартную шкалу прогресса:',
        reply_markup=kb,
    )
    await state.set_state(AdminActions.user_ref_pct)


@dp.callback_query(F.data.startswith('usr_refreset_'))
async def process_usr_refreset(callback: CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split('_')[2])
    await state.clear()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET custom_ref_pct = NULL WHERE user_id = ?', (target_id,))
        await db.commit()
    await sync_user_menu_button(target_id)
    await callback.answer('Реферальная ставка сброшена на стандартную!', show_alert=True)
    text, kb = await render_user_card(target_id)
    await _send_or_edit(callback, text, reply_markup=kb)


@dp.message(AdminActions.user_ref_pct)
async def process_usr_refpct_msg(message: Message, state: FSMContext):
    val_str = (message.text or '').strip()
    if not val_str.isdigit() or not 1 <= int(val_str) <= 100:
        return await message.answer('⚠️ Введите целое число от 1 до 100.')
    pct = int(val_str)
    data = await state.get_data()
    target_id = int(data['target_id'])
    await state.clear()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET custom_ref_pct = ? WHERE user_id = ?', (pct, target_id))
        await db.commit()

    await sync_user_menu_button(target_id)
    await message.answer(f'✅ Индивидуальная ставка <b>{pct}%</b> установлена для ID <code>{target_id}</code>!', parse_mode='HTML')
    text, kb = await render_user_card(target_id)
    await message.answer(text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith('usr_refcnt_'))
async def ask_usr_refcnt(callback: CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split('_')[2])
    await state.update_data(target_id=target_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[styled_btn('⬅️ Отмена', callback_data=f'usr_view_{target_id}', style='danger')]])
    await _send_or_edit(
        callback,
        f'👥 Введите новое <b>количество оплативших рефералов</b> для ID <code>{target_id}</code> (например <code>10</code> или <code>20</code>):',
        reply_markup=kb,
    )
    await state.set_state(AdminActions.user_ref_count)


@dp.message(AdminActions.user_ref_count)
async def process_usr_refcnt_msg(message: Message, state: FSMContext):
    val_str = (message.text or '').strip()
    if not val_str.isascii() or not val_str.isdigit() or not 0 <= int(val_str) <= 1000000000:
        return await message.answer('⚠️ Введите целое неотрицательное число.')
    cnt = int(val_str)
    data = await state.get_data()
    target_id = int(data['target_id'])
    await state.clear()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET ref_paid_count = ? WHERE user_id = ?', (cnt, target_id))
        await db.commit()

    await sync_user_menu_button(target_id)
    await message.answer(f'✅ Счетчик рефералов изменен на <b>{cnt}</b> для ID <code>{target_id}</code>!', parse_mode='HTML')
    text, kb = await render_user_card(target_id)
    await message.answer(text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith('usr_give_'))
async def admin_quick_give_tariff(callback: CallbackQuery):
    parts = callback.data.split('_')
    target_id = int(parts[2])
    plan_key = parts[3]
    if plan_key not in TARIFFS:
        return await callback.answer('Тариф не найден', show_alert=True)
    async with get_user_lock(target_id):
        if len(await get_active_subscriptions(target_id)) >= 2:
            return await callback.answer('Заняты все 2 слота.', show_alert=True)
        t = TARIFFS[plan_key]
        vpn_key = await H1CloudService.create_key(target_id, t['days'], t['devices'], t['limit_gb'])
        new_date = (datetime.now() + timedelta(days=t['days'])).strftime('%Y-%m-%d %H:%M:%S')
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                '''INSERT INTO subscriptions (user_id, tariff_name, active_until, gb_limit, devices, vpn_key, sub_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (target_id, t['name'], new_date, t['limit_gb'], t['devices'], vpn_key, 'paid'),
            )
            await db.commit()
    await sync_user_menu_button(target_id)
    await callback.answer(f"✅ Тариф {t['name']} выдан!", show_alert=True)
    text, kb = await render_user_card(target_id)
    await _send_or_edit(callback, text, reply_markup=kb)


@dp.callback_query(F.data.startswith('usr_view_'))
async def view_usr_card_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    target_id = int(callback.data.split('_')[2])
    await DBManager.upsert_user(target_id)
    text, kb = await render_user_card(target_id)
    await _send_or_edit(callback, text, reply_markup=kb)


@dp.callback_query(F.data.startswith('usr_bal_'))
async def ask_usr_balance(callback: CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split('_')[2])
    await state.update_data(target_id=target_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[styled_btn('⬅️ Отмена', callback_data=f'usr_view_{target_id}', style='danger')]]
    )
    await _send_or_edit(
        callback,
        f'💰 Введите сумму изменения баланса (например <code>149</code> или <code>-50</code>) для ID <code>{target_id}</code>:',
        reply_markup=kb,
    )
    await state.set_state(AdminActions.balance_amount)


@dp.message(AdminActions.balance_amount)
async def process_usr_balance(message: Message, state: FSMContext):
    try:
        amount = int((message.text or '').strip())
    except Exception:
        return await message.answer('⚠️ Введите целое число.')

    if abs(amount) > 1000000:
        return await message.answer('⚠️ Слишком большая сумма изменения.')

    data = await state.get_data()
    target_id = int(data['target_id'])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE users SET balance = MAX(0, COALESCE(balance, 0) + ?) WHERE user_id = ?', (amount, target_id)
        )
        await db.commit()

    await sync_user_menu_button(target_id)
    await state.clear()
    text, kb = await render_user_card(target_id)
    await message.answer(f'✅ Баланс успешно обновлен.\n\n{text}', reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith('usr_days_'))
async def ask_usr_days(callback: CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split('_')[2])
    await state.update_data(target_id=target_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[styled_btn('⬅️ Отмена', callback_data=f'usr_view_{target_id}', style='danger')]]
    )
    await _send_or_edit(
        callback,
        f'📅 Введите количество дней подписки (например <code>30</code> или <code>-5</code>) для ID <code>{target_id}</code>:',
        reply_markup=kb,
    )
    await state.set_state(AdminActions.sub_add_days)


@dp.message(AdminActions.sub_add_days)
async def process_usr_days(message: Message, state: FSMContext):
    try:
        days = int((message.text or '').strip())
    except Exception:
        return await message.answer('⚠️ Введите целое число.')

    data = await state.get_data()
    target_id = int(data['target_id'])
    active_subs = await DBManager.get_active_subscriptions(target_id)

    async with aiosqlite.connect(DB_PATH) as db:
        if active_subs:
            sub = active_subs[0]
            new_date = (sub['active_until_dt'] + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            await H1CloudService.update_subscription(sub, active_until=new_date)
            await db.execute(
                'UPDATE subscriptions SET active_until = ?, notified_exp = 0 WHERE id = ?', (new_date, sub['id'])
            )
        elif days > 0:
            new_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            vpn_key = await H1CloudService.create_key(target_id, days, 3, 300)
            await db.execute(
                '''INSERT INTO subscriptions (user_id, tariff_name, active_until, gb_limit, devices, vpn_key, sub_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (target_id, '💎 Подписка', new_date, 300, 3, vpn_key, 'paid'),
            )
        await db.commit()

    await sync_user_menu_button(target_id)
    await state.clear()
    text, kb = await render_user_card(target_id)
    await message.answer(f'✅ Подписка клиента обновлена.\n\n{text}', reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data.startswith('usr_reset_'))
async def reset_user_sub(callback: CallbackQuery):
    target_id = int(callback.data.split('_')[2])
    for sub in await DBManager.get_active_subscriptions(target_id):
        await H1CloudService.update_subscription(sub, enabled=False)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM subscriptions WHERE user_id = ?', (target_id,))
        await db.execute('UPDATE users SET active_until = NULL, vpn_key = NULL WHERE user_id = ?', (target_id,))
        await db.commit()
    await sync_user_menu_button(target_id)
    await callback.answer('Подписки аннулированы!', show_alert=True)
    text, kb = await render_user_card(target_id)
    await _send_or_edit(callback, text, reply_markup=kb)


@dp.callback_query(F.data.startswith('usr_ban_'))
async def toggle_ban_user_sub(callback: CallbackQuery):
    target_id = int(callback.data.split('_')[2])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT COALESCE(is_banned, 0) FROM users WHERE user_id = ?', (target_id,)) as cursor:
            row = await cursor.fetchone()
            is_banned = row[0] if row else 0
        new_ban = 0 if is_banned else 1
        await db.execute(
            'UPDATE users SET is_banned = ?, failed_attempts = 0 WHERE user_id = ?', (new_ban, target_id)
        )
        await db.commit()
    await callback.answer('❄️ Аккаунт заморожен!' if new_ban else '🟢 Аккаунт разморожен!', show_alert=True)
    text, kb = await render_user_card(target_id)
    await _send_or_edit(callback, text, reply_markup=kb)


# --- ПРОМОКОДЫ: СКИДКА / БЕСПЛАТНЫЙ ТАРИФ / БАЛАНС ---
_PROMO_TARIFF_TARGETS = {'all', 'start', 'base', 'pro', 'hit'}
_PROMO_TYPES = {'discount', 'free_tariff', 'rub'}


def _promo_target(value: str | None) -> str:
    raw = str(value or 'all').strip().lower()
    if raw == 'all':
        return raw
    try:
        canonical = tariff_target(raw)
    except (KeyError, TypeError, ValueError):
        return ''
    return canonical if canonical in _PROMO_TARIFF_TARGETS - {'all'} else ''


def _promo_target_label(value: str) -> str:
    target = _promo_target(value)
    tariff_id = resolve_tariff_id(target) if target and target != 'all' else None
    return str(TARIFFS.get(tariff_id, {}).get('name', target or value))


async def _promo_admin_allowed(user_id: int) -> bool:
    return await is_admin(user_id)


async def active_discount_for_tariff(user_id: int, tariff_id: str) -> tuple[int, str | None, str]:
    try:
        selected = tariff_target(tariff_id)
    except (TypeError, ValueError):
        return 0, None, 'all'
    if selected not in _PROMO_TARIFF_TARGETS - {'all'}:
        return 0, None, 'all'
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT COALESCE(discount_pct, 0), active_promo_code, COALESCE(discount_target_tariff, "all") '
            'FROM users WHERE user_id = ?',
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        return 0, None, 'all'
    pct, code, target = int(row[0] or 0), row[1], _promo_target(row[2])
    if target not in ('all', selected):
        return 0, None, target or 'all'
    return max(0, min(99, pct)), code, target or 'all'


async def redeem_promo(user_id: int, code: str) -> dict:
    code = str(code or '').strip().upper()
    if type(user_id) is not int or user_id <= 0:
        raise ValueError('Некорректный пользователь.')
    if not re.fullmatch(r'[A-Z0-9_-]{1,32}', code):
        raise ValueError('Некорректный формат промокода.')

    async with get_user_lock(user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('BEGIN IMMEDIATE')
            try:
                async with db.execute(
                    '''SELECT COALESCE(promo_type, ''), COALESCE(target_tariff, 'all'),
                              COALESCE(reward_rub, 0), COALESCE(discount_pct, 0),
                              COALESCE(max_uses, 100), COALESCE(max_per_user, 1),
                              COALESCE(used_count, 0)
                       FROM promocodes WHERE code = ?''',
                    (code,),
                ) as cursor:
                    row = await cursor.fetchone()
                if not row:
                    raise ValueError('Такой промокод не найден.')
                promo_type, target, reward, discount_pct, max_uses, max_per_user, used_count = row
                promo_type = str(promo_type or '').strip().lower()
                target = _promo_target(target)
                reward, discount_pct = int(reward or 0), int(discount_pct or 0)
                max_uses, max_per_user, used_count = int(max_uses or 0), int(max_per_user or 0), int(used_count or 0)
                if not promo_type:
                    promo_type = 'rub' if reward > 0 else 'discount'
                if promo_type not in _PROMO_TYPES:
                    raise ValueError('Промокод настроен некорректно.')
                if not target or (promo_type == 'free_tariff' and target == 'all'):
                    raise ValueError('Тариф промокода настроен некорректно.')
                if max_uses <= 0 or used_count >= max_uses:
                    raise ValueError('Общий лимит активаций этого промокода исчерпан.')

                async with db.execute(
                    'SELECT COALESCE(use_count, 1) FROM promo_uses WHERE user_id = ? AND code = ?',
                    (user_id, code),
                ) as cursor:
                    use_row = await cursor.fetchone()
                user_uses = int(use_row[0]) if use_row else 0
                if max_per_user <= 0 or user_uses >= max_per_user:
                    raise ValueError(
                        f'Вы уже использовали лимит активаций для этого промокода ({user_uses}/{max_per_user}).'
                    )

                # Old rows could legitimately carry both a ruble reward and discount.
                legacy_combo = reward > 0 and discount_pct > 0
                grant_rub = (promo_type == 'rub' or legacy_combo) and reward > 0
                grant_discount = (promo_type == 'discount' or legacy_combo) and discount_pct > 0
                key = None
                tariff = None
                if promo_type == 'free_tariff':
                    tariff_id = resolve_tariff_id(target)
                    if not tariff_id or tariff_id not in TARIFFS:
                        raise ValueError('Тариф промокода недоступен.')
                    tariff = TARIFFS[tariff_id]
                    async with db.execute('SELECT active_until FROM subscriptions WHERE user_id = ?', (user_id,)) as cursor:
                        subscriptions = await cursor.fetchall()
                    now = datetime.now()
                    active_slots = sum(
                        1 for (active_until,) in subscriptions
                        if (expiry := parse_any_datetime(active_until)) is not None and expiry > now
                    )
                    if active_slots >= 2:
                        raise ValueError('У вас уже заняты оба слота подписки. Освободите слот и попробуйте снова.')
                    key = await asyncio.wait_for(
                        H1CloudService.create_key(
                            user_id, tariff['days'], tariff['devices'], tariff['limit_gb']
                        ),
                        timeout=20,
                    )
                    if not key:
                        raise ValueError('Не удалось создать VPN-ключ. Попробуйте позже.')
                    expires = datetime.now() + timedelta(days=tariff['days'])
                    await db.execute(
                        '''INSERT INTO subscriptions
                           (user_id, tariff_name, active_until, gb_limit, devices, vpn_key, sub_type)
                           VALUES (?, ?, ?, ?, ?, ?, 'promo')''',
                        (user_id, tariff['name'], expires.strftime('%Y-%m-%d %H:%M:%S'),
                         tariff['limit_gb'], tariff['devices'], key),
                    )

                if grant_rub:
                    await db.execute(
                        'UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE user_id = ?',
                        (reward, user_id),
                    )
                if grant_discount:
                    await db.execute(
                        '''UPDATE users SET discount_pct = ?, active_promo_code = ?,
                                  discount_target_tariff = ? WHERE user_id = ?''',
                        (discount_pct, code, target, user_id),
                    )

                if use_row:
                    await db.execute(
                        'UPDATE promo_uses SET use_count = use_count + 1 WHERE user_id = ? AND code = ?',
                        (user_id, code),
                    )
                else:
                    await db.execute(
                        'INSERT INTO promo_uses (user_id, code, use_count) VALUES (?, ?, 1)',
                        (user_id, code),
                    )
                await db.execute('UPDATE promocodes SET used_count = used_count + 1 WHERE code = ?', (code,))
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    parts = []
    if grant_rub:
        parts.append(f'на баланс зачислено +{reward} ₽')
    if grant_discount:
        parts.append(f'активирована скидка {discount_pct}% на {"все тарифы" if target == "all" else "тариф «" + html.escape(_promo_target_label(target)) + "»"}')
    if promo_type == 'free_tariff' and tariff:
        parts.append(f'бесплатно подключен тариф «{html.escape(tariff["name"])}»')
    return {
        'ok': True,
        'code': code,
        'promo_type': promo_type,
        'target_tariff': target,
        'discount_pct': discount_pct if grant_discount else 0,
        'reward_rub': reward if grant_rub else 0,
        'vpn_key': key,
        'message': '; '.join(parts) or 'Промокод активирован.',
    }


async def execute_promo_code(target, user_id: int, code: str):
    menu_kb = await get_main_menu_kb(user_id)
    try:
        result = await redeem_promo(user_id, code)
    except ValueError as exc:
        return await _send_or_edit(target, f'❌ <b>{html.escape(str(exc))}</b>', reply_markup=menu_kb)
    except Exception as exc:
        logging.error('Promo redemption failed for user %s (%s)', user_id, type(exc).__name__)
        return await _send_or_edit(target, '❌ <b>Не удалось активировать промокод. Попробуйте позже.</b>', reply_markup=menu_kb)
    message = f'✅ <b>{html.escape(result["message"])}</b>'
    if result.get('vpn_key'):
        message += f'\n\n🔑 Ваш ключ подписки:\n<code>{html.escape(result["vpn_key"])}</code>'
    return await _send_or_edit(target, message, parse_mode='HTML', reply_markup=menu_kb)


@dp.callback_query((F.data == 'admin_promos') | F.data.startswith('admin_promos_page_'))
async def admin_promos_list(callback: CallbackQuery, state: FSMContext):
    if not await _promo_admin_allowed(callback.from_user.id):
        return await callback.answer('Доступ запрещён.', show_alert=True)
    await state.clear()

    page_size = 8
    page = 0
    if callback.data.startswith('admin_promos_page_'):
        page_text = callback.data.removeprefix('admin_promos_page_')
        if not page_text.isdigit():
            return await callback.answer('Некорректная страница.', show_alert=True)
        page = int(page_text)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT COUNT(*) FROM promocodes') as cursor:
            total = int((await cursor.fetchone())[0] or 0)
        page_count = max(1, (total + page_size - 1) // page_size)
        page = min(page, page_count - 1)
        async with db.execute(
            '''SELECT code, COALESCE(promo_type, ''), COALESCE(target_tariff, 'all'),
                      COALESCE(reward_rub, 0), COALESCE(discount_pct, 0),
                      COALESCE(max_uses, 100), COALESCE(max_per_user, 1), COALESCE(used_count, 0)
               FROM promocodes ORDER BY code ASC LIMIT ? OFFSET ?''',
            (page_size, page * page_size),
        ) as cursor:
            promos = await cursor.fetchall()

    keyboard = [[styled_btn('➕ Создать промокод', callback_data='admin_create_promo', style='success')]]
    lines = []
    for code, kind, target, rub, discount, max_uses, per_user, used in promos:
        kind = kind or ('rub' if rub else 'discount')
        if kind == 'free_tariff':
            desc = f'Бесплатный тариф: {html.escape(str(target))}'
        elif kind == 'rub':
            desc = f'+{rub} ₽'
        else:
            desc = f'Скидка {discount}% ({html.escape(str(target))})'
        lines.append(
            f'• <code>{html.escape(str(code))}</code>: {desc} — '
            f'{used}/{max_uses}, на пользователя: {per_user}'
        )
        keyboard.append([
            styled_btn(f'⚙️ {code} · {desc[:22]}', callback_data=f'adm_pr_view_{code}', style='primary')
        ])

    if total:
        keyboard.append([
            styled_btn('⬅️ Предыдущая', callback_data=f'admin_promos_page_{page - 1}', style='primary')
            if page > 0 else styled_btn('·', callback_data='admin_promos', style='primary'),
            styled_btn(f'{page + 1}/{page_count}', callback_data=f'admin_promos_page_{page}', style='primary'),
            styled_btn('Следующая ➡️', callback_data=f'admin_promos_page_{page + 1}', style='primary')
            if page + 1 < page_count else styled_btn('·', callback_data=f'admin_promos_page_{page}', style='primary'),
        ])
    keyboard.append([styled_btn('⬅️ Назад в админку', callback_data='admin_menu', style='danger')])
    text = '\n'.join(lines) if lines else '<i>Промокодов пока нет</i>'
    await _send_or_edit(
        callback,
        f'🎟 <b>Управление промокодами</b> · страница {page + 1}/{page_count}\n\n{text}',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )

@dp.callback_query(F.data.startswith('adm_pr_view_'))
async def admin_promo_view_card(callback: CallbackQuery, state: FSMContext):
    if not await _promo_admin_allowed(callback.from_user.id):
        return await callback.answer('Доступ запрещён.', show_alert=True)
    await state.clear()
    code = callback.data.replace('adm_pr_view_', '', 1).strip().upper()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            '''SELECT code, COALESCE(promo_type, ''), COALESCE(target_tariff, 'all'),
                      COALESCE(reward_rub, 0), COALESCE(discount_pct, 0),
                      COALESCE(max_uses, 100), COALESCE(max_per_user, 1), COALESCE(used_count, 0)
               FROM promocodes WHERE code = ?''', (code,)
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        return await callback.answer('Промокод не найден.', show_alert=True)
    code, kind, target, rub, discount, max_uses, per_user, used = row
    kind = kind or ('rub' if rub else 'discount')
    if kind == 'free_tariff':
        description = f'🎁 Бесплатный тариф: <code>{html.escape(str(target))}</code>'
    elif kind == 'rub':
        description = f'💰 Бонус: <code>+{rub} ₽</code>'
    else:
        description = f'🏷 Скидка: <code>{discount}%</code> · тариф: <code>{html.escape(str(target))}</code>'
    text = (
        f'🎟 <b>Промокод <code>{html.escape(code)}</code></b>\n\n{description}\n'
        f'👥 Общий лимит: <code>{used} / {max_uses}</code>\n'
        f'👤 На пользователя: <code>{per_user}</code>\n'
        f'📊 Осталось: <code>{max(0, max_uses - used)}</code>'
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [styled_btn('👥 Изменить общий лимит', callback_data=f'adm_pr_edituses_{code}', style='primary')],
        [styled_btn('👤 Изменить лимит на пользователя', callback_data=f'adm_pr_editperuser_{code}', style='primary')],
        [styled_btn('🗑 Удалить промокод', callback_data=f'adm_pr_del_{code}', style='danger')],
        [styled_btn('⬅️ К списку', callback_data='admin_promos', style='primary')],
    ])
    await _send_or_edit(callback, text, reply_markup=keyboard)


@dp.callback_query(F.data.startswith('adm_pr_del_'))
async def admin_promo_delete(callback: CallbackQuery, state: FSMContext):
    if not await _promo_admin_allowed(callback.from_user.id):
        return await callback.answer('Доступ запрещён.', show_alert=True)
    code = callback.data.replace('adm_pr_del_', '', 1).strip().upper()
    async with aiosqlite.connect(DB_PATH) as db:
        # Keep promo_uses as historical counters so recreating a code cannot reset its limits.
        await db.execute('DELETE FROM promocodes WHERE code = ?', (code,))
        await db.commit()
    await callback.answer('Промокод удален.', show_alert=True)
    await admin_promos_list(callback, state)


@dp.callback_query(F.data.startswith('adm_pr_edituses_'))
async def admin_promo_edit_uses_ask(callback: CallbackQuery, state: FSMContext):
    if not await _promo_admin_allowed(callback.from_user.id):
        return await callback.answer('Доступ запрещён.', show_alert=True)
    code = callback.data.replace('adm_pr_edituses_', '', 1).strip().upper()
    await state.update_data(target_promo=code)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[styled_btn('⬅️ Отмена', callback_data=f'adm_pr_view_{code}', style='danger')]])
    await _send_or_edit(callback, f'Введите новый общий лимит для <code>{html.escape(code)}</code>:', reply_markup=keyboard)
    await state.set_state(AdminActions.edit_promo_uses)


@dp.message(AdminActions.edit_promo_uses)
async def admin_promo_edit_uses_finish(message: Message, state: FSMContext):
    if not await _promo_admin_allowed(message.from_user.id):
        await state.clear()
        return await message.answer('Доступ запрещён.')
    value = (message.text or '').strip()
    if not value.isdigit() or not 1 <= int(value) <= 1_000_000:
        return await message.answer('Введите целое число от 1 до 1 000 000.')
    code = (await state.get_data()).get('target_promo')
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE promocodes SET max_uses = ? WHERE code = ?', (int(value), code))
        await db.commit()
    await state.clear()
    await message.answer(f'✅ Общий лимит промокода <code>{html.escape(str(code))}</code>: <b>{int(value)}</b>.', parse_mode='HTML')


@dp.callback_query(F.data.startswith('adm_pr_editperuser_'))
async def admin_promo_edit_per_user_ask(callback: CallbackQuery, state: FSMContext):
    if not await _promo_admin_allowed(callback.from_user.id):
        return await callback.answer('Доступ запрещён.', show_alert=True)
    code = callback.data.replace('adm_pr_editperuser_', '', 1).strip().upper()
    await state.update_data(target_promo=code)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[styled_btn('⬅️ Отмена', callback_data=f'adm_pr_view_{code}', style='danger')]])
    await _send_or_edit(callback, f'Введите лимит активаций на пользователя для <code>{html.escape(code)}</code>:', reply_markup=keyboard)
    await state.set_state(AdminActions.edit_promo_per_user)


@dp.message(AdminActions.edit_promo_per_user)
async def admin_promo_edit_per_user_finish(message: Message, state: FSMContext):
    if not await _promo_admin_allowed(message.from_user.id):
        await state.clear()
        return await message.answer('Доступ запрещён.')
    value = (message.text or '').strip()
    if not value.isdigit() or not 1 <= int(value) <= 100_000:
        return await message.answer('Введите целое число от 1 до 100 000.')
    code = (await state.get_data()).get('target_promo')
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE promocodes SET max_per_user = ? WHERE code = ?', (int(value), code))
        await db.commit()
    await state.clear()
    await message.answer(f'✅ Лимит на пользователя для <code>{html.escape(str(code))}</code>: <b>{int(value)}</b>.', parse_mode='HTML')


@dp.callback_query(F.data == 'admin_create_promo')
async def adm_promo_step1(callback: CallbackQuery, state: FSMContext):
    if not await _promo_admin_allowed(callback.from_user.id):
        return await callback.answer('Доступ запрещён.', show_alert=True)
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[styled_btn('⬅️ Отмена', callback_data='admin_promos', style='danger')]])
    await _send_or_edit(callback, 'Введите промокод (1–32 символа: A–Z, 0–9, _ или -):', reply_markup=keyboard)
    await state.set_state(AdminActions.create_promo_code)


@dp.message(AdminActions.create_promo_code)
async def adm_promo_step2(message: Message, state: FSMContext):
    if not await _promo_admin_allowed(message.from_user.id):
        await state.clear()
        return await message.answer('Доступ запрещён.')
    code = (message.text or '').strip().upper()
    if not re.fullmatch(r'[A-Z0-9_-]{1,32}', code):
        return await message.answer('Используйте от 1 до 32 символов: A–Z, 0–9, _ или -.')
    await state.update_data(code=code)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [styled_btn('🏷 Процентная скидка', callback_data='adm_pr_type_discount', style='success')],
        [styled_btn('🎁 Бесплатный тариф', callback_data='adm_pr_type_free', style='primary')],
        [styled_btn('💰 Бонус в рублях', callback_data='adm_pr_type_rub', style='primary')],
        [styled_btn('⬅️ Отмена', callback_data='admin_promos', style='danger')],
    ])
    await message.answer(f'Промокод <code>{html.escape(code)}</code>\n\nВыберите тип:', reply_markup=keyboard, parse_mode='HTML')
    await state.set_state(AdminActions.create_promo_type)


async def _promo_ask_value_or_limits(callback: CallbackQuery, state: FSMContext, promo_type: str):
    if promo_type == 'discount':
        await callback.message.answer('Выберите тариф для скидки:', reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [styled_btn('Все тарифы', callback_data='adm_pr_target_all', style='primary')],
            [styled_btn('Старт', callback_data='adm_pr_target_start'), styled_btn('Базовый', callback_data='adm_pr_target_base')],
            [styled_btn('Продвинутый', callback_data='adm_pr_target_pro'), styled_btn('ХИТ СЕЗОНА', callback_data='adm_pr_target_hit')],
        ]))
    elif promo_type == 'free_tariff':
        await callback.message.answer('Выберите тариф для бесплатной активации:', reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [styled_btn('Старт', callback_data='adm_pr_target_start'), styled_btn('Базовый', callback_data='adm_pr_target_base')],
            [styled_btn('Продвинутый', callback_data='adm_pr_target_pro'), styled_btn('ХИТ СЕЗОНА', callback_data='adm_pr_target_hit')],
        ]))
    else:
        await callback.message.answer('Введите сумму бонуса в рублях (1–100 000):')
        await state.set_state(AdminActions.create_promo_value)


@dp.callback_query(F.data.in_({'adm_pr_type_discount', 'adm_pr_type_free', 'adm_pr_type_rub'}))
async def adm_promo_step3_type(callback: CallbackQuery, state: FSMContext):
    if not await _promo_admin_allowed(callback.from_user.id):
        return await callback.answer('Доступ запрещён.', show_alert=True)
    kind = {'adm_pr_type_discount': 'discount', 'adm_pr_type_free': 'free_tariff', 'adm_pr_type_rub': 'rub'}[callback.data]
    await state.update_data(promo_type=kind, target_tariff='all')
    await callback.answer()
    await _promo_ask_value_or_limits(callback, state, kind)


@dp.callback_query(F.data.startswith('adm_pr_target_'))
async def adm_promo_target_selected(callback: CallbackQuery, state: FSMContext):
    if not await _promo_admin_allowed(callback.from_user.id):
        return await callback.answer('Доступ запрещён.', show_alert=True)
    target = callback.data.replace('adm_pr_target_', '', 1)
    if target not in _PROMO_TARIFF_TARGETS:
        return await callback.answer('Неизвестный тариф.', show_alert=True)
    data = await state.get_data()
    kind = data.get('promo_type')
    if kind not in ('discount', 'free_tariff') or (kind == 'free_tariff' and target == 'all'):
        return await callback.answer('Выбор тарифа недоступен.', show_alert=True)
    await state.update_data(target_tariff=target)
    await callback.answer()
    if kind == 'discount':
        await callback.message.answer('Введите процент скидки (1–99):')
        await state.set_state(AdminActions.create_promo_value)
    else:
        await state.update_data(val=0)
        await callback.message.answer('Введите общий лимит активаций (1–1 000 000):')
        await state.set_state(AdminActions.create_promo_uses)


@dp.message(AdminActions.create_promo_value)
async def adm_promo_step4_val(message: Message, state: FSMContext):
    if not await _promo_admin_allowed(message.from_user.id):
        await state.clear()
        return await message.answer('Доступ запрещён.')
    raw = (message.text or '').strip()
    if not raw.isdigit():
        return await message.answer('Введите целое положительное число.')
    value = int(raw)
    data = await state.get_data()
    kind = data.get('promo_type', 'discount')
    if kind == 'discount' and not 1 <= value <= 99:
        return await message.answer('Процент скидки должен быть от 1 до 99.')
    if kind == 'rub' and not 1 <= value <= 100_000:
        return await message.answer('Сумма должна быть от 1 до 100 000 ₽.')
    await state.update_data(val=value)
    await message.answer('Введите общий лимит активаций (1–1 000 000):')
    await state.set_state(AdminActions.create_promo_uses)


@dp.message(AdminActions.create_promo_uses)
async def adm_promo_step5_uses(message: Message, state: FSMContext):
    if not await _promo_admin_allowed(message.from_user.id):
        await state.clear()
        return await message.answer('Доступ запрещён.')
    raw = (message.text or '').strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 1_000_000:
        return await message.answer('Общий лимит: целое число от 1 до 1 000 000.')
    await state.update_data(max_uses=int(raw))
    await message.answer('Введите лимит активаций на пользователя (1–100 000):')
    await state.set_state(AdminActions.create_promo_per_user)


@dp.message(AdminActions.create_promo_per_user)
async def adm_promo_finish(message: Message, state: FSMContext):
    if not await _promo_admin_allowed(message.from_user.id):
        await state.clear()
        return await message.answer('Доступ запрещён.')
    raw = (message.text or '').strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 100_000:
        return await message.answer('Лимит на пользователя: целое число от 1 до 100 000.')
    data = await state.get_data()
    code = data.get('code')
    kind = data.get('promo_type')
    target = data.get('target_tariff', 'all')
    value = int(data.get('val', 0))
    max_uses = int(data.get('max_uses', 0))
    per_user = int(raw)
    if not code or kind not in _PROMO_TYPES or target not in _PROMO_TARIFF_TARGETS:
        await state.clear()
        return await message.answer('Не удалось сохранить промокод: данные формы некорректны.')
    if kind == 'free_tariff' and target == 'all':
        await state.clear()
        return await message.answer('Для бесплатного тарифа нужно выбрать конкретный план.')
    discount = value if kind == 'discount' else 0
    reward = value if kind == 'rub' else 0
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('BEGIN IMMEDIATE')
        try:
            async with db.execute('SELECT COALESCE(SUM(use_count), 0) FROM promo_uses WHERE code = ?', (code,)) as cursor:
                history = int((await cursor.fetchone())[0] or 0)
            await db.execute(
                '''INSERT INTO promocodes
                   (code, reward_rub, discount_pct, max_uses, max_per_user, used_count, promo_type, target_tariff)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(code) DO UPDATE SET reward_rub = excluded.reward_rub,
                     discount_pct = excluded.discount_pct, max_uses = excluded.max_uses,
                     max_per_user = excluded.max_per_user, promo_type = excluded.promo_type,
                     target_tariff = excluded.target_tariff''',
                (code, reward, discount, max_uses, per_user, history, kind, target),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    await state.clear()
    details = (f'скидка {discount}% на {target}' if kind == 'discount' else
               f'бесплатный тариф {target}' if kind == 'free_tariff' else f'+{reward} ₽')
    await message.answer(
        f'✅ Промокод <code>{html.escape(code)}</code> ({html.escape(details)}) сохранен.\n'
        f'Общий лимит: <b>{max_uses}</b>; на пользователя: <b>{per_user}</b>.',
        reply_markup=get_admin_kb(), parse_mode='HTML',
    )


async def api_redeem_promo(request: web.Request):
    data = await request.json()
    if not isinstance(data, dict) or not isinstance(data.get('code'), str):
        raise ValueError('Передайте промокод в поле code.')
    result = await redeem_promo(request['user']['id'], data['code'])
    result.pop('vpn_key', None)
    return web.json_response(result)


# ==========================================
# 12. ФОНОВЫЕ ЗАДАЧИ
# ==========================================
async def auto_check_pending_payments():
    while True:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT invoice_id, user_id, amount FROM payments "
                    "WHERE status IN ('pending', 'processing') "
                    "OR (status = 'paid' AND COALESCE(target_action, '') != '' "
                    "AND COALESCE(target_fulfillment_status, 'pending') IN ('pending', 'processing', 'failed')) "
                    "ORDER BY rowid DESC LIMIT 100"
                ) as cursor:
                    pending_rows = await cursor.fetchall()
            for invoice_id, user_id, amount in pending_rows:
                if await PlategaService.check_status(invoice_id):
                    await credit_user_payment(user_id, amount, invoice_id)
                await asyncio.sleep(0.8)
        except Exception:
            logging.exception('Ошибка фонового чекера оплат')
        await asyncio.sleep(10)


async def smart_expiration_notifier():
    while True:
        try:
            now = datetime.now()
            warn_threshold = now + timedelta(hours=24)
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    '''SELECT s.id, s.user_id, s.tariff_name, s.active_until, s.gb_limit, s.used_gb,
                              s.notified_exp, s.notified_traffic
                       FROM subscriptions s
                       JOIN users u ON u.user_id = s.user_id
                       WHERE u.bot_notifications = 1
                         AND COALESCE(u.is_banned, 0) = 0
                         AND (s.notified_exp = 0 OR s.notified_traffic = 0)'''
                ) as cursor:
                    rows = await cursor.fetchall()

                for sub_id, u_id, t_name, act_until, limit_gb, used_gb, notif_exp, notif_traf in rows:
                    d = parse_any_datetime(act_until)
                    webapp_url = await build_webapp_url(u_id)
                    kb = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [styled_btn('📱 Продлить в приложении', web_app=WebAppInfo(url=webapp_url), style='success')],
                            [styled_btn('👤 Открыть кабинет', callback_data='profile', style='primary')],
                        ]
                    )

                    if d and notif_exp == 0 and now < d <= warn_threshold:
                        await db.execute('UPDATE subscriptions SET notified_exp = 1 WHERE id = ?', (sub_id,))
                        await db.commit()
                        try:
                            await bot.send_message(
                                u_id,
                                f'{EMOJI_WARN} <b>Подписка «{html.escape(str(t_name))}» истекает менее чем через 24 часа.</b>\n\n'
                                'Продлите доступ заранее в приложении PinPoint.',
                                reply_markup=kb,
                                parse_mode='HTML',
                            )
                        except Exception:
                            pass

                    if limit_gb and limit_gb > 0 and notif_traf == 0 and (float(used_gb or 0) / limit_gb) >= 0.9:
                        await db.execute('UPDATE subscriptions SET notified_traffic = 1 WHERE id = ?', (sub_id,))
                        await db.commit()
                        left_gb = round(max(0.0, limit_gb - float(used_gb or 0)), 1)
                        try:
                            await bot.send_message(
                                u_id,
                                f'{EMOJI_WARN} <b>Заканчивается трафик:</b> на слоте «{html.escape(str(t_name))}» осталось <b>{left_gb} ГБ</b>.\n\n'
                                'Добавьте гигабайты в приложении PinPoint.',
                                reply_markup=kb,
                                parse_mode='HTML',
                            )
                        except Exception:
                            pass
        except Exception as e:
            logging.error('Ошибка фоновых уведомлений: %s', e)
        await asyncio.sleep(1800)


# ==========================================
# 13. MIDDLEWARE ДОСТУПА И ВЕБ-СЕРВЕР (API)
# ==========================================
class AccessMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = getattr(event, 'from_user', None)
        if not user:
            return
        chat = event.chat if isinstance(event, Message) else getattr(event.message, 'chat', None)
        if not chat or chat.type != 'private':
            return

        state = data.get('state')
        current_state = await state.get_state() if state else ''
        action = (event.data or '') if isinstance(event, CallbackQuery) else ''
        auth_command = isinstance(event, Message) and (event.text or '').split('@', 1)[0].split(' ', 1)[0] == '/admin'
        authenticating = str(current_state).startswith('AdminAuth:') or auth_command
        privileged = action.startswith(('admin_', 'adm_', 'usr_', 'bcast_', 'review_')) or str(current_state).startswith('AdminActions:')
        user_is_admin = await is_admin(user.id)
        member = await DBManager.is_admin(user.id)
        if (authenticating and not member) or (privileged and not user_is_admin and not auth_command):
            if isinstance(event, CallbackQuery):
                await event.answer('Доступ запрещён.', show_alert=True)
            return

        summary = await DBManager.get_user_summary(user.id)
        if summary['is_banned'] and not user_is_admin:
            if isinstance(event, CallbackQuery):
                await event.answer('❄️ Ваш аккаунт заморожен администратором.', show_alert=True)
            else:
                await event.answer(f'{EMOJI_WARN} <b>Ваш аккаунт заморожен администратором.</b>', parse_mode='HTML')
            return

        if isinstance(event, Message) and (event.text or '').startswith('/start'):
            parts = (event.text or '').split(maxsplit=1)
            argument = parts[1] if len(parts) > 1 else ''
            if argument.startswith('topup_'):
                amount = argument[6:]
                if not amount.isascii() or not amount.isdigit() or not 10 <= int(amount) <= 100000:
                    return await event.answer('Сумма пополнения должна быть целым числом от 10 до 100 000 ₽.')

        try:
            return await handler(event, data)
        except TelegramBadRequest as exc:
            if 'message is not modified' not in str(exc):
                logging.error('TelegramBadRequest (%s): %s', type(exc).__name__, exc)
        except Exception as exc:
            logging.error('Ошибка в обработчике (%s): %s', type(exc).__name__, exc)
            if isinstance(event, Message):
                await event.answer('Операция не завершена. Обновите меню (/start) или обратитесь в поддержку.')
        finally:
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer()
                except (TelegramBadRequest, TelegramForbiddenError):
                    pass


dp.message.outer_middleware(AccessMiddleware())
dp.callback_query.outer_middleware(AccessMiddleware())


def validate_init_data(raw: str, now: float | None = None) -> dict:
    if not raw or len(raw) > 16384:
        raise ValueError('Откройте приложение через кнопку в Telegram-боте.')
    pairs = urllib.parse.parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError('Дублирующиеся поля авторизации.')
    received = fields.pop('hash', '')
    check = '\n'.join(f'{k}={v}' for k, v in sorted(fields.items()))
    secret = hmac.new(b'WebAppData', BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise ValueError('Неверная подпись Telegram.')
    age = (time.time() if now is None else now) - int(fields.get('auth_date', '0'))
    if not -300 <= age <= 604800:
        raise ValueError('Сессия истекла. Переоткройте приложение из бота.')
    user = json.loads(fields['user'])
    if not isinstance(user, dict):
        raise ValueError('Некорректный пользователь Telegram.')
    if type(user.get('id')) is not int or user['id'] <= 0:
        raise ValueError('Некорректный идентификатор пользователя.')
    return user


def allowed_origins() -> set[str]:
    urls = [WEBAPP_URL, API_PUBLIC_URL]
    return {f'{p.scheme}://{p.netloc}' for u in urls if (p := urllib.parse.urlsplit(u)).netloc}


@web.middleware
async def api_guard(request: web.Request, handler):
    origin = request.headers.get('Origin')
    if origin and origin not in allowed_origins():
        if urllib.parse.urlsplit(origin).netloc != request.host:
            return web.json_response({'ok': False, 'error': 'Origin запрещён'}, status=403)
    try:
        if request.path.startswith('/api/') and request.path not in ('/api/reviews', '/api/reviews/stats') and request.method != 'OPTIONS':
            user = validate_init_data(request.headers.get('X-Telegram-Init-Data', ''))
            request['user'] = user
            await DBManager.upsert_user(user['id'], user.get('username') or '')
            summary = await DBManager.get_user_summary(user['id'])
            if summary['is_banned']:
                raise web.HTTPForbidden(reason='Ваш аккаунт заморожен администратором')
        response = await handler(request)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        response = web.json_response({'ok': False, 'error': str(exc) or 'Ошибка сессии Telegram.'}, status=400)
    except web.HTTPException as exc:
        response = web.json_response({'ok': False, 'error': exc.reason}, status=exc.status)
    except Exception as exc:
        logging.error('Ошибка веб-сервера API (%s): %s', type(exc).__name__, exc)
        response = web.json_response({'ok': False, 'error': 'Сервис временно недоступен'}, status=503)

    response.headers.update(
        {
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer',
            'Access-Control-Allow-Origin': origin or '*',
            'Vary': 'Origin',
            'Access-Control-Allow-Headers': 'Content-Type, X-Telegram-Init-Data',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        }
    )
    return response


async def build_profile_data(user_id: int, snapshot: bool = False) -> dict:
    summary = await DBManager.get_user_summary(user_id)
    subs = await DBManager.get_active_subscriptions(user_id)
    reviews = await get_public_reviews(limit=3 if snapshot else 5)
    stats = await get_review_stats()
    slots = []
    for sub in subs[:2]:
        slot = {'id': sub['id'], 'name': sub['tariff_name'], 'until': sub['active_until_str'],
                'gb': sub['gb_limit'], 'used_gb': sub['used_gb'], 'dev': sub['devices']}
        if not snapshot:
            slot['key'] = sub['vpn_key']
        slots.append(slot)
    if snapshot:
        reviews = [{**review, 'text': review['text'][:240]} for review in reviews]
    return {
        'user_id': user_id, 'balance': summary['balance'],
        'active_promo_code': summary['active_promo_code'],
        'discount_pct': summary['discount_pct'],
        'discount_target_tariff': summary['discount_target_tariff'],
        'ref_cnt': summary['ref_cnt'], 'ref_pct': summary['ref_pct'],
        'ref_earn': summary['ref_earn'], 'notifications': bool(summary['notifications']),
        'bot_username': await get_bot_username(), 'subs': slots,
        'reviews': reviews, 'average_rating': stats['average_rating'], 'review_count': stats['count'],
    }



async def api_create_invoice(request: web.Request):
    user = request['user']
    user_id = int(user['id'])
    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text='Invalid JSON')
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text='JSON object required')
    tariff_input = data.get('tariff') or data.get('tariff_id')
    target_action = str(data.get('target_action') or '')
    if tariff_input is not None:
        tariff_id = resolve_tariff_id(str(tariff_input))
        if not tariff_id or tariff_id not in TARIFFS:
            raise web.HTTPBadRequest(text='Unknown tariff')
        target_action = f'buy_{tariff_id}'
        summary = await DBManager.get_user_summary(user_id)
        canonical = tariff_target(str(tariff_input)) or tariff_target(tariff_id)
        discount_target = str(summary.get('discount_target_tariff') or 'all').lower()
        pct = max(0, min(99, int(summary.get('discount_pct') or 0)))
        if discount_target not in ('', 'all', canonical):
            pct = 0
        amount = max(10, calculate_discounted_price(TARIFFS[tariff_id]['price'], pct) - int(summary['balance']))
    else:
        amount_value = data.get('amount')
        try:
            amount = int(amount_value)
        except (TypeError, ValueError):
            raise web.HTTPBadRequest(text='amount must be an integer')
        if not 10 <= amount <= 100000:
            raise web.HTTPBadRequest(text='amount must be between 10 and 100000')
        if target_action not in ('', 'topup', 'balance'):
            raise web.HTTPBadRequest(text='Unsupported target_action')
        target_action = ''
    if not 10 <= amount <= 100000:
        raise web.HTTPBadRequest(text='Invoice amount is outside allowed range')
    username = str(user.get('username') or 'user')[:64]
    pay_url, invoice_id = await PlategaService.create_invoice(
        user_id, amount, username, target_action=target_action
    )
    if not pay_url or not invoice_id:
        raise web.HTTPServiceUnavailable(text='Unable to create payment invoice')
    return web.json_response({'ok': True, 'payment_url': pay_url, 'invoice_id': invoice_id, 'amount': amount, 'target_action': target_action})


async def api_buy_tariff(request: web.Request):
    user = request['user']
    user_id = int(user['id'])
    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text='Invalid JSON')
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text='JSON object required')
    requested = str(data.get('tariff') or data.get('tariff_id') or '')
    tariff_id = resolve_tariff_id(requested)
    if not tariff_id or tariff_id not in TARIFFS:
        raise web.HTTPBadRequest(text='Unknown tariff')
    async with get_user_lock(user_id):
        summary = await DBManager.get_user_summary(user_id)
        canonical = tariff_target(requested) or tariff_target(tariff_id)
        discount_target = str(summary.get('discount_target_tariff') or 'all').lower()
        discount_pct = max(0, min(99, int(summary.get('discount_pct') or 0)))
        if discount_target not in ('', 'all', canonical):
            discount_pct = 0
        price = calculate_discounted_price(TARIFFS[tariff_id]['price'], discount_pct)
        active = await DBManager.get_active_subscriptions(user_id)
        if len(active) >= 2:
            raise web.HTTPConflict(text='No subscription slots available')
        if int(summary['balance']) < price:
            due = max(10, price - int(summary['balance']))
            pay_url, invoice_id = await PlategaService.create_invoice(
                user_id, due, str(user.get('username') or 'user')[:64], target_action=f'buy_{tariff_id}'
            )
            if not pay_url or not invoice_id:
                raise web.HTTPServiceUnavailable(text='Unable to create payment invoice')
            return web.json_response({
                'ok': True, 'activated': False, 'payment_url': pay_url, 'invoice_id': invoice_id,
                'amount': due, 'target_action': f'buy_{tariff_id}',
            })
        result = await _activate_tariff_locked(user_id, requested)
        if not result.get('ok'):
            if result.get('reason') == 'slots_full':
                raise web.HTTPConflict(text='No subscription slots available')
            if result.get('reason') == 'insufficient_balance':
                raise web.HTTPConflict(text='Balance changed; retry purchase')
            if result.get('reason') == 'key_creation_failed':
                raise web.HTTPBadGateway(text='Could not create VPN subscription')
            raise web.HTTPBadRequest(text='Could not activate tariff')
    await sync_user_menu_button(user_id)
    return web.json_response({
        'ok': True, 'activated': True, 'tariff_id': result['tariff_id'], 'balance': int(summary['balance']) - result['price'],
        'subscription': {
            'name': result['tariff']['name'], 'active_until': result['active_until'],
            'gb_limit': result['tariff']['limit_gb'], 'devices': result['tariff']['devices'], 'key': result['key'],
        },
    })

async def api_topup(request: web.Request):
    user = request['user']
    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text='Invalid JSON')
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text='JSON object required')
    try:
        amount = int(data.get('amount'))
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text='amount must be an integer')
    if not 10 <= amount <= 100000:
        raise web.HTTPBadRequest(text='amount must be between 10 and 100000')
    username = str(user.get('username') or 'user')[:64]
    pay_url, invoice_id = await PlategaService.create_invoice(int(user['id']), amount, username, target_action='')
    if not pay_url or not invoice_id:
        raise web.HTTPServiceUnavailable(text='Unable to create payment invoice')
    return web.json_response({'ok': True, 'payment_url': pay_url, 'invoice_id': invoice_id, 'amount': amount, 'target_action': ''})


async def api_purchase(request: web.Request):
    return await api_buy_tariff(request)


async def api_boosters(request: web.Request):
    user = request['user']
    user_id = int(user['id'])
    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text='Invalid JSON')
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text='JSON object required')
    try:
        gb_val = int(data.get('gb') if data.get('gb') is not None else data.get('booster_gb'))
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text='gb must be an integer')
    if gb_val not in BOOSTERS:
        raise web.HTTPBadRequest(text='Unknown booster')

    async with get_user_lock(user_id):
        active_subs = await DBManager.get_active_subscriptions(user_id)
        if not active_subs:
            raise web.HTTPConflict(text='No active subscriptions')
        requested_sub_id = data.get('subscription_id')
        if requested_sub_id is not None:
            try:
                requested_sub_id = int(requested_sub_id)
            except (TypeError, ValueError):
                raise web.HTTPBadRequest(text='subscription_id must be an integer')
            slot_idx = next((i for i, sub in enumerate(active_subs) if int(sub['id']) == requested_sub_id), -1)
        else:
            try:
                slot_idx = int(data.get('slot', 0))
            except (TypeError, ValueError):
                raise web.HTTPBadRequest(text='slot must be an integer')
        if not 0 <= slot_idx < len(active_subs):
            raise web.HTTPBadRequest(text='Unknown subscription slot')
        target_sub = active_subs[slot_idx]
        booster = BOOSTERS[gb_val]
        summary = await DBManager.get_user_summary(user_id)
        balance = int(summary['balance'])
        if balance < int(booster['price']):
            due = max(10, int(booster['price']) - balance)
            pay_url, invoice_id = await PlategaService.create_invoice(
                user_id, due, str(user.get('username') or 'user')[:64],
                target_action=f'boost_{gb_val}_{slot_idx + 1}',
            )
            if not pay_url or not invoice_id:
                raise web.HTTPServiceUnavailable(text='Unable to create payment invoice')
            return web.json_response({
                'ok': True, 'activated': False, 'payment_url': pay_url, 'invoice_id': invoice_id,
                'amount': due, 'target_action': f'boost_{gb_val}_{slot_idx + 1}',
            })
        new_limit = int(target_sub['gb_limit']) + int(booster['gb'])
        if not await H1CloudService.update_subscription(target_sub, traffic_limit_gb=new_limit):
            raise web.HTTPBadGateway(text='Could not update subscription traffic limit')
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('BEGIN IMMEDIATE')
            async with db.execute(
                'UPDATE users SET balance = COALESCE(balance, 0) - ? WHERE user_id = ? AND COALESCE(balance, 0) >= ?',
                (booster['price'], user_id, booster['price']),
            ) as cursor:
                if cursor.rowcount != 1:
                    await db.rollback()
                    raise web.HTTPConflict(text='Balance changed; retry purchase')
            async with db.execute(
                'UPDATE subscriptions SET gb_limit = gb_limit + ?, notified_traffic = 0 WHERE id = ? AND user_id = ?',
                (booster['gb'], target_sub['id'], user_id),
            ) as cursor:
                if cursor.rowcount != 1:
                    await db.rollback()
                    raise web.HTTPConflict(text='Subscription changed; retry purchase')
            await db.commit()
    await sync_user_menu_button(user_id)
    return web.json_response({
        'ok': True, 'activated': True, 'balance': balance - int(booster['price']),
        'subscription_id': int(target_sub['id']), 'gb_added': int(booster['gb']), 'gb_limit': new_limit,
    })

async def api_profile(request: web.Request):
    return web.json_response({'ok': True, **await build_profile_data(request['user']['id'])})


async def api_transactions_secure(request: web.Request):
    user_id = request['user']['id']
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT amount, created_at FROM payments WHERE user_id = ? AND status = 'paid' ORDER BY rowid DESC LIMIT 20",
            (user_id,),
        ) as c:
            rows = await c.fetchall()
    return web.json_response({'ok': True, 'txs': [{'amount': r[0], 'date': str(r[1] or '')[:16]} for r in rows]})


async def api_settings_secure(request: web.Request):
    data = await request.json()
    value = data.get('notifications')
    if type(value) is not bool:
        raise ValueError('Параметр notifications должен быть bool')
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET bot_notifications = ? WHERE user_id = ?', (int(value), request['user']['id']))
        await db.commit()
    return web.json_response({'ok': True, 'notifications': value})


async def platega_webhook(request: web.Request):
    try:
        if not (
            hmac.compare_digest(request.headers.get('X-MerchantId', ''), PLATEGA_MERCHANT_ID)
            and hmac.compare_digest(request.headers.get('X-Secret', ''), PLATEGA_SECRET)
        ):
            return web.Response(status=403)
        data = await request.json()
        if not isinstance(data, dict):
            return web.Response(text='Invalid payload', status=400)
        invoice_id = data.get('id') or data.get('Id') or data.get('transactionId')
        if invoice_id and await PlategaService.check_status(str(invoice_id)):
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT amount, user_id FROM payments WHERE invoice_id = ? "
                    "AND (status IN ('pending', 'processing') OR "
                    "(status = 'paid' AND COALESCE(target_action, '') != '' "
                    "AND COALESCE(target_fulfillment_status, 'pending') IN ('pending', 'processing', 'failed')))",
                    (str(invoice_id),),
                ) as cursor:
                    row = await cursor.fetchone()
            if row:
                await credit_user_payment(int(row[1]), int(row[0]), str(invoice_id))
        return web.Response(text='OK', status=200)
    except Exception:
        logging.exception('Platega webhook processing failed')
        return web.Response(text='Error', status=400)


async def serve_html(request: web.Request):
    html_file = resolve_html_file()
    if not html_file.exists():
        return web.Response(text='Mini App HTML file not found', status=404)
    return web.FileResponse(html_file)


async def start_web_server():
    app = web.Application(middlewares=[api_guard], client_max_size=32768)
    app.router.add_get('/', serve_html)
    app.router.add_route('OPTIONS', '/{tail:.*}', lambda r: web.Response(status=204))
    app.router.add_post('/webhook/platega', platega_webhook)
    app.router.add_post('/api/user/invoice', api_create_invoice)
    app.router.add_post('/api/user/buy-tariff', api_buy_tariff)
    app.router.add_post('/api/user/purchase', api_purchase)
    app.router.add_post('/api/user/topup', api_topup)
    app.router.add_post('/api/user/boosters', api_boosters)
    app.router.add_get('/api/user/profile', api_profile)
    app.router.add_post('/api/user/reviews', api_submit_review)
    app.router.add_get('/api/reviews', api_public_reviews)
    app.router.add_get('/api/reviews/stats', api_review_statistics)
    app.router.add_get('/api/user/balance', api_profile)
    app.router.add_get('/api/user/transactions', api_transactions_secure)
    app.router.add_post('/api/user/settings', api_settings_secure)
    app.router.add_post('/api/user/promocodes', api_redeem_promo)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        await web.TCPSite(runner, '0.0.0.0', WEBHOOK_PORT).start()
    except BaseException:
        await runner.cleanup()
        raise
    return runner


# ==========================================
# 14. ТОЧКА ВХОДА
# ==========================================
async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    global http_session
    http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))
    runner = None
    tasks = []
    try:
        await DBManager.init()
        runner = await start_web_server()
        tasks = [
            asyncio.create_task(auto_check_pending_payments()),
            asyncio.create_task(smart_expiration_notifier()),
        ]
        logging.info('PinPoint VPN запущен. HTTP/API порт: %s', WEBHOOK_PORT)
        await dp.start_polling(bot)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if runner:
            await runner.cleanup()
        if http_session:
            await http_session.close()
        await bot.session.close()




# Review helpers and public Mini App API.
async def get_public_reviews(limit=5, offset=0):
    limit = max(1, min(int(limit), 50))
    offset = max(0, int(offset))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, author_name, is_anon, rating, text, created_at "
            "FROM reviews WHERE status = 'approved' "
            "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        {
            'id': row['id'],
            'author_name': 'Anonymous Customer' if row['is_anon'] else (row['author_name'] or 'Customer'),
            'rating': row['rating'],
            'text': row['text'] or '',
            'created_at': row['created_at'],
        }
        for row in rows
    ]


async def get_review_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*), COALESCE(AVG(rating), 0) FROM reviews WHERE status = 'approved'"
        ) as cursor:
            row = await cursor.fetchone()
    return {'count': int(row[0] or 0), 'average_rating': round(float(row[1] or 0), 2)}


async def api_submit_review(request: web.Request):
    user = request['user']
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, aiohttp.ContentTypeError):
        return web.json_response({'ok': False, 'error': 'Invalid JSON'}, status=400)
    if not isinstance(payload, dict):
        return web.json_response({'ok': False, 'error': 'A JSON object is required'}, status=400)

    rating = payload.get('rating')
    if type(rating) is not int or not 1 <= rating <= 5:
        return web.json_response({'ok': False, 'error': 'rating must be an integer from 1 to 5'}, status=400)
    review_text = payload.get('text')
    if not isinstance(review_text, str):
        return web.json_response({'ok': False, 'error': 'text must be a string'}, status=400)
    review_text = review_text.strip()
    if not review_text or len(review_text) > 2000 or len(review_text.encode('utf-16-le')) > 6000:
        return web.json_response({'ok': False, 'error': 'text must contain 1 to 2000 characters'}, status=400)
    is_anon = payload.get('is_anon', False)
    if type(is_anon) is bool:
        is_anon = int(is_anon)
    elif type(is_anon) is int and is_anon in (0, 1):
        pass
    else:
        return web.json_response({'ok': False, 'error': 'is_anon must be a boolean or 0/1'}, status=400)

    user_id = user['id']
    username = user.get('username') if isinstance(user.get('username'), str) else None
    name_parts = [user.get('first_name'), user.get('last_name')]
    author_name = ' '.join(part.strip() for part in name_parts if isinstance(part, str) and part.strip())
    author_name = author_name or (f'@{username}' if username else 'Telegram user')
    created_at = datetime.now().isoformat(timespec='seconds')
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO reviews (user_id, username, author_name, is_anon, rating, text, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
            (user_id, username, author_name, is_anon, rating, review_text, created_at),
        )
        review_id = cursor.lastrowid
        await db.commit()

    username_label = f"@{html.escape(username)}" if username else 'No @username'
    notification = (
        '⭐ <b>New review awaiting moderation</b>\n'
        f'Rating: <b>{rating}/5</b>\n'
        f'User ID: <code>{user_id}</code> • {username_label}\n'
        f'Author: {html.escape(author_name)} • Published as: '
        f'{"Anonymous Customer" if is_anon else html.escape(author_name)}\n\n'
        f'{html.escape(review_text)}'
    )
    moderation_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text='✅ Approve', callback_data=f'review_approve_{review_id}'),
            InlineKeyboardButton(text='❌ Reject', callback_data=f'review_reject_{review_id}'),
        ],
        [InlineKeyboardButton(text='✉️ Message Customer', callback_data=f'review_contact_{review_id}')],
    ])
    delivered = 0
    try:
        admin_ids = await DBManager.get_all_admin_ids()
    except Exception:
        logging.exception('Could not load administrator IDs for review notification')
        admin_ids = set()
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, notification, reply_markup=moderation_kb, parse_mode='HTML')
            delivered += 1
        except (TelegramBadRequest, TelegramForbiddenError):
            logging.info('Could not deliver review notification to administrator %s', admin_id)
        except Exception:
            logging.exception('Review notification delivery failed for administrator %s', admin_id)
    return web.json_response({'ok': True, 'review_id': review_id, 'status': 'pending', 'notified_admins': delivered}, status=201)


async def api_public_reviews(request: web.Request):
    try:
        limit = int(request.query.get('limit', '5'))
        offset = int(request.query.get('offset', '0'))
    except (TypeError, ValueError):
        return web.json_response({'ok': False, 'error': 'limit and offset must be integers'}, status=400)
    reviews = await get_public_reviews(limit=limit, offset=offset)
    return web.json_response({'ok': True, 'reviews': reviews})


async def api_review_statistics(request: web.Request):
    stats = await get_review_stats()
    return web.json_response({'ok': True, **stats})


async def _review_admin_allowed(callback: CallbackQuery) -> bool:
    if not await is_admin(callback.from_user.id):
        await callback.answer('Access denied.', show_alert=True)
        return False
    return True


async def _show_review_admin_page(callback: CallbackQuery, status: str, offset: int = 0):
    offset = max(0, offset)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT COUNT(*) FROM reviews WHERE status = ?', (status,)) as cursor:
            count_row = await cursor.fetchone()
        total = int(count_row[0] or 0)
        async with db.execute(
            'SELECT id, user_id, username, author_name, is_anon, rating, text, created_at '
            'FROM reviews WHERE status = ? ORDER BY created_at DESC, id DESC LIMIT 1 OFFSET ?',
            (status, offset),
        ) as cursor:
            review = await cursor.fetchone()
    title = 'Pending' if status == 'pending' else 'Approved'
    if not review:
        other_status = 'approved' if status == 'pending' else 'pending'
        other_label = '✅ Approved reviews' if status == 'pending' else '🕓 Pending reviews'
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='⬅️ Previous', callback_data=f'review_list_{status}_{max(0, offset - 1)}'),
             InlineKeyboardButton(text='Next ➡️', callback_data=f'review_list_{status}_{offset + 1}')],
            [InlineKeyboardButton(text=other_label, callback_data=f'review_list_{other_status}_0')],
            [InlineKeyboardButton(text='⬅️ Admin menu', callback_data='admin_menu')],
        ])
        await _send_or_edit(callback, f'⭐ <b>{title} reviews</b>\nNo reviews on this page. Total: {total}.', kb)
        return

    public_name = 'Anonymous Customer' if review['is_anon'] else (review['author_name'] or 'Customer')
    username_label = f"@{review['username']}" if review['username'] else 'No @username'
    text = (
        f'⭐ <b>{title} review {offset + 1}/{total}</b> • ID <code>{review["id"]}</code>\n'
        f'Rating: <b>{review["rating"]}/5</b> • Published as: {html.escape(public_name)}\n'
        f'Customer: <code>{review["user_id"]}</code> • {html.escape(username_label)}\n'
        f'Date: <code>{html.escape(review["created_at"] or "")}</code>\n\n'
        f'{html.escape(review["text"] or "")}'
    )
    rows = []
    other_status = 'approved' if status == 'pending' else 'pending'
    other_label = '✅ Approved reviews' if status == 'pending' else '🕓 Pending reviews'
    if status == 'pending':
        rows.append([InlineKeyboardButton(text='✅ Approve', callback_data=f'review_approve_{review["id"]}')])
    rows.extend([
        [InlineKeyboardButton(text='❌ Reject', callback_data=f'review_reject_{review["id"]}'),
         InlineKeyboardButton(text='🗑 Delete', callback_data=f'review_delete_{review["id"]}')],
        [InlineKeyboardButton(text='✉️ Message Customer', callback_data=f'review_contact_{review["id"]}')],
        [InlineKeyboardButton(text='⬅️ Previous', callback_data=f'review_list_{status}_{max(0, offset - 1)}'),
         InlineKeyboardButton(text='Next ➡️', callback_data=f'review_list_{status}_{offset + 1}')],
        [InlineKeyboardButton(text=other_label, callback_data=f'review_list_{other_status}_0')],
        [InlineKeyboardButton(text='⬅️ Admin menu', callback_data='admin_menu')],
    ])
    await _send_or_edit(callback, text, InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith('review_list_'))
async def review_admin_list(callback: CallbackQuery):
    if not await _review_admin_allowed(callback):
        return
    try:
        _, _, status, raw_offset = callback.data.split('_', 3)
        offset = int(raw_offset)
    except (AttributeError, ValueError):
        await callback.answer('Invalid review page.', show_alert=True)
        return
    if status not in {'pending', 'approved'} or offset < 0:
        await callback.answer('Invalid review page.', show_alert=True)
        return
    await _show_review_admin_page(callback, status, offset)
    await callback.answer()


@dp.callback_query(F.data.startswith('review_approve_'))
async def review_admin_approve(callback: CallbackQuery):
    if not await _review_admin_allowed(callback):
        return
    try:
        review_id = int(callback.data.rsplit('_', 1)[1])
    except (AttributeError, ValueError):
        await callback.answer('Invalid review.', show_alert=True)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("UPDATE reviews SET status = 'approved' WHERE id = ?", (review_id,))
        await db.commit()
    if cursor.rowcount == 0:
        await callback.answer('Review not found.', show_alert=True)
        return
    await callback.answer('Review approved.')
    await _show_review_admin_page(callback, 'pending', 0)


@dp.callback_query(F.data.startswith('review_reject_'))
async def review_admin_reject(callback: CallbackQuery):
    if not await _review_admin_allowed(callback):
        return
    try:
        review_id = int(callback.data.rsplit('_', 1)[1])
    except (AttributeError, ValueError):
        await callback.answer('Invalid review.', show_alert=True)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("UPDATE reviews SET status = 'rejected' WHERE id = ?", (review_id,))
        await db.commit()
    if cursor.rowcount == 0:
        await callback.answer('Review not found.', show_alert=True)
        return
    await callback.answer('Review rejected.')
    await _show_review_admin_page(callback, 'pending', 0)


@dp.callback_query(F.data.startswith('review_delete_'))
async def review_admin_delete(callback: CallbackQuery):
    if not await _review_admin_allowed(callback):
        return
    try:
        review_id = int(callback.data.rsplit('_', 1)[1])
    except (AttributeError, ValueError):
        await callback.answer('Invalid review.', show_alert=True)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
        await db.commit()
    if cursor.rowcount == 0:
        await callback.answer('Review not found.', show_alert=True)
        return
    await callback.answer('Review deleted.')
    await _show_review_admin_page(callback, 'approved', 0)


@dp.callback_query(F.data.startswith('review_contact_'))
async def review_admin_contact(callback: CallbackQuery, state: FSMContext):
    if not await _review_admin_allowed(callback):
        return
    try:
        review_id = int(callback.data.rsplit('_', 1)[1])
    except (AttributeError, ValueError):
        await callback.answer('Invalid review.', show_alert=True)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id FROM reviews WHERE id = ?', (review_id,)) as cursor:
            row = await cursor.fetchone()
    if not row or not row[0]:
        await callback.answer('Customer not found.', show_alert=True)
        return
    await state.update_data(review_contact_user_id=int(row[0]))
    await state.set_state(AdminActions.review_reply)
    await callback.message.answer(
        f'✉️ Send your message to customer <code>{int(row[0])}</code>. '
        'They can reply through the bot’s Support Chat.',
        parse_mode='HTML',
    )
    await callback.answer()


@dp.message(AdminActions.review_reply)
async def review_admin_send_message(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return await message.answer('Access denied.')
    if not message.text or not message.text.strip() or len(message.text.encode('utf-16-le')) > 7000:
        return await message.answer('Send a text message of 1 to 3500 characters (emoji count as two).')
    data = await state.get_data()
    target_id = data.get('review_contact_user_id')
    if not isinstance(target_id, int) or target_id <= 0:
        await state.clear()
        return await message.answer('Customer contact session expired. Please open the review again.')
    try:
        await bot.send_message(
            target_id,
            '💬 <b>Message from PinPoint Support:</b>\n\n'
            f'{html.escape(message.text.strip())}\n\n'
            'To reply, open the bot’s Support Chat.',
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='💬 Support Chat', callback_data='support_ticket')]
            ]),
        )
        await message.answer(f'✅ Message sent to customer <code>{target_id}</code>.', parse_mode='HTML')
    except TelegramForbiddenError:
        await message.answer('❌ The customer has not started the bot or blocked it.')
    except Exception:
        logging.exception('Failed to send review follow-up to customer %s', target_id)
        await message.answer('❌ Could not send the message. Please try again later.')
    await state.clear()


if __name__ == '__main__':
    asyncio.run(main())
