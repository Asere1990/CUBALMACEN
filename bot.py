import os
import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Set, Tuple

import httpx
import stripe
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.channels import GetParticipantRequest, EditBannedRequest
from telethon.tl.types import (
    ChannelParticipantAdmin,
    ChannelParticipantCreator,
    ChatBannedRights,
    User,
)

# =========================
# CONFIG GENERAL
# =========================

TIMEZONE = ZoneInfo("America/New_York")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("telethon-auditor")

# =========================
# VARIABLES DE ENTORNO
# =========================

TG_API_ID = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH = os.getenv("TG_API_HASH", "")
TG_PHONE = os.getenv("TG_PHONE", "")
TG_PASSWORD = os.getenv("TG_PASSWORD") or None

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_TABLE = os.getenv("SUPABASE_TABLE", "stripe_telegram_customers")

STRIPE_KEY = os.getenv("STRIPE_KEY", "")
if STRIPE_KEY:
    stripe.api_key = STRIPE_KEY

PANEL_CHAT_ID = int(os.getenv("PANEL", "-1003208307392"))
SESSION_PATH = os.getenv("SESSION_PATH", "/var/data/telethon_auditor")

# Ejecutar automaticamente cada X horas. 24 recomendado.
RUN_EVERY_HOURS = float(os.getenv("RUN_EVERY_HOURS", "24"))
RUN_ON_START = os.getenv("RUN_ON_START", "1") == "1"

# Pausas anti FloodWait / anti scraping agresivo.
MEMBER_BATCH_SIZE = int(os.getenv("MEMBER_BATCH_SIZE", "100"))
PAUSE_BETWEEN_MEMBER_BATCHES = float(os.getenv("PAUSE_BETWEEN_MEMBER_BATCHES", "5"))
PAUSE_EVERY_500_MEMBERS = float(os.getenv("PAUSE_EVERY_500_MEMBERS", "20"))
PAUSE_BETWEEN_GROUPS = float(os.getenv("PAUSE_BETWEEN_GROUPS", "240"))  # 4 min
PAUSE_BETWEEN_KICKS = float(os.getenv("PAUSE_BETWEEN_KICKS", "7"))
PAUSE_EVERY_20_KICKS = float(os.getenv("PAUSE_EVERY_20_KICKS", "180"))

# Si esta en 1, NO expulsa. Solo reporta lo que haria.
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"
STRIPE_MATCH_SECONDS = int(os.getenv("STRIPE_MATCH_SECONDS", "60"))

# =========================
# MEMBRESIAS / STRIPE
# =========================

MEMBERSHIP_COLUMNS = ["aguacero", "cubalseros", "vaqueria", "viva_cuba", "galeria"]

MEMBERSHIP_LABELS = {
    "aguacero": "☔️𝐀𝐆𝐔𝐀𝐂𝐄𝐑𝐎",
    "cubalseros": "🐊𝐂𝐔𝐁𝐀𝐋𝐒𝐄𝐑𝐎𝐒",
    "vaqueria": "🐮𝐕𝐀𝐐𝐔𝐄𝐑𝐈𝐀",
    "viva_cuba": "🇨🇺𝐕𝐈𝐕𝐀 𝐂𝐔𝐁𝐀",
    "galeria": "📸𝐆𝐀𝐋𝐄𝐑𝐈𝐀",
}

JOIN_REQUEST_LINKS = {
    "aguacero": "https://t.me/+KanDcefFZcphMWVh",
    "cubalseros": "https://t.me/+6z07JGJ_2qMwZWRh",
    "vaqueria": "https://t.me/+uwCkZOiTY04wNGQx",
    "viva_cuba": "https://t.me/+nrCbPwMT32lmMjFh",
    "galeria": "https://t.me/+w3HlhhUg3odjN2Ix",
}

PRICE_TO_MEMBERSHIP = {
    "price_1SXLDlKjV2vzEefKnDr3fmRm": "viva_cuba",
    "price_1SPiQXKjV2vzEefKBiAUBbOw": "vaqueria",
    "price_1S3yhOKjV2vzEefKGSYL20uc": "cubalseros",
    "price_1RtnnWKjV2vzEefK65MeZRaR": "aguacero",
    "price_1TOfswKjV2vzEefKpD3N6QH5": "galeria",
}

STATUS_PRIORITY = {
    "Activa": 3,
    "Vencida": 2,
    "Cancelada": 1,
    "-": 0,
    None: 0,
}

# =========================
# GRUPOS
# =========================

AGUACERO_CHAT_ID = -1003720427589
CUBALSEROS_CHAT_ID = -1003716284604
VAQUERIA_CHAT_ID = -1003886874628
VIVA_CUBA_CHAT_ID = -1003816370471
GALERIA_CHAT_ID = -1003711183473

MAIN_TO_DERIVED = {
    GALERIA_CHAT_ID: [-1003431747248],
    AGUACERO_CHAT_ID: [
        -1002644698709,
        -1003238413148,
        -1003279295849,
        -1002641640398,
        -1003406066304,
        -1002561621755,
    ],
    CUBALSEROS_CHAT_ID: [
        -1003916053009,
        -1003482795001,
        -1003381170605,
        -1003153267514,
        -1003484699520,
        -1003293684959,
    ],
    VAQUERIA_CHAT_ID: [
        -1003019391474,
        -1003449370256,
        -1003432967322,
        -1003205377675,
        -1003205423598,
        -1003395084214,
        -1003488300663,
        -1003281699302,
    ],
    VIVA_CUBA_CHAT_ID: [
        -1003363576347,
        -1003621086826,
        -1003751804239,
        -1003180960156,
        -1003715472779,
    ],
}

SUBS_BY_MAIN_CHAT_ID = {
    AGUACERO_CHAT_ID: "aguacero",
    CUBALSEROS_CHAT_ID: "cubalseros",
    VAQUERIA_CHAT_ID: "vaqueria",
    VIVA_CUBA_CHAT_ID: "viva_cuba",
    GALERIA_CHAT_ID: "galeria",
}

DERIVED_TO_MAIN = {d: main for main, derived in MAIN_TO_DERIVED.items() for d in derived}

# chat_id -> membresia requerida
CHAT_TO_MEMBERSHIP: Dict[int, str] = {}
for main_id, membership in SUBS_BY_MAIN_CHAT_ID.items():
    CHAT_TO_MEMBERSHIP[main_id] = membership
    for d in MAIN_TO_DERIVED.get(main_id, []):
        CHAT_TO_MEMBERSHIP[d] = membership

CHAT_ALIASES = {
    -1002644698709: "🇨🇺𝐂𝐔𝐁𝐀𝐍𝐀𝐒 𝐄𝐍 𝐌𝐈𝐀𝐌𝐈®🇺🇸",
    -1003916053009: "𝐏𝐈𝐍𝐀𝐑 𝐃𝐄𝐋 𝐑𝐈𝐎 𝐄𝐗𝐂𝐋𝐔𝐒𝐈𝐕𝐎",
    -1003019391474: "𝐒𝐀𝐍𝐂𝐓𝐈 𝐒𝐏𝐈𝐑𝐈𝐓𝐔𝐒 𝐄𝐗𝐂𝐋𝐔𝐒𝐈𝐕𝐎",
    -1002641640398: "𝐃𝐈𝐎𝐒𝐀𝐒 𝐃𝐄 𝐀𝐑𝐓𝐄𝐌𝐈𝐒𝐀🇨🇺",
    -1003406066304: "☔️𝐀𝐆𝐔𝐀𝐂𝐄𝐑𝐎",
    -1002561621755: "𝐂𝐈𝐄𝐍𝐅𝐔𝐄𝐆𝐎𝐒 𝐄𝐗𝐂𝐋𝐔𝐒𝐈𝐕𝐎®",
    -1003482795001: "𝐓𝐎𝐑𝐓𝐈𝐋𝐋𝐄𝐑𝐀𝐒 𝐂𝐔𝐁𝐀𝐍𝐀𝐒🇨🇺",
    -1003238413148: "𝐅𝐀𝐑𝐀𝐍𝐃𝐔𝐋𝐀 𝐇𝐀𝐁𝐀𝐍𝐀®",
    -1003720427589: "𝑻𝒆𝒍𝒆𝒈𝒓𝒂𝒎",
    -1003716284604: "𝗧𝗘𝗟𝗘𝗚𝗥𝗔𝗠",
    -1003381170605: "𝐂𝐔𝐁𝐀𝐋𝐌𝐀𝐂𝐄𝐍𝐕𝐈𝐏®🇨🇺",
    -1003153267514: "𝐓𝐔𝐍𝐄𝐑𝐀𝐒 𝐄𝐗𝐂𝐋𝐔𝐒𝐈𝐕𝐀𝐒",
    -1003484699520: "𝐉𝐈𝐍𝐄𝐓𝐄𝐑𝐀𝐒🇨🇺",
    -1003886874628: "𝑻𝑬𝑳𝑬𝑮𝑹𝑨𝑴",
    -1003449370256: "𝐋𝐀 𝐓𝐀𝐁𝐄𝐑𝐍𝐀 𝐂𝐔𝐁𝐀𝐍𝐀",
    -1003432967322: "𝐋𝐀 𝐕𝐀𝐐𝐔𝐄𝐑𝐈𝐀",
    -1003205377675: "𝐇𝐎𝐋𝐆𝐔𝐈𝐍𝐄𝐑𝐀𝐒",
    -1003205423598: "𝐀𝐕𝐈𝐋𝐄Ñ𝐀𝐒 𝐕𝐈𝐏",
    -1003395084214: "𝐌𝐀𝐓𝐀𝐍𝐂𝐄𝐑𝐀𝐒 𝐕𝐈𝐏",
    -1003488300663: "𝐆𝐑𝐀𝐍𝐌𝐀 𝐕𝐈𝐏",
    -1003281699302: "𝐂𝐀𝐌𝐀𝐆𝐔𝐄𝐘 𝐕𝐈𝐏",
    -1003816370471: "𝐕𝐈𝐕𝐀 𝐂𝐔𝐁𝐀🇨🇺",
    -1003363576347: "𝐂𝐔𝐁𝐀𝐍𝐄𝐀𝐍𝐃𝐎",
    -1003715472779: "𝐁𝐄𝐂𝐀𝐃𝐀𝐒",
    -1003751804239: "𝐂𝐔𝐁𝐀 𝐄𝐍 𝐋𝐀 𝐂𝐀𝐒𝐀",
    -1003180960156: "𝐂𝐔𝐁𝐀 𝐁𝐄𝐋𝐋𝐀",
    -1003279295849: "𝐑𝐄𝐕𝐎𝐋𝐈𝐂𝐎 𝐗𝐗𝐗",
    -1003293684959: "𝐂𝐔𝐁𝐀𝐋𝐒𝐄𝐑𝐎𝐒🇨🇺",
    -1003621086826: "𝐓𝐈𝐄𝐑𝐑𝐀 𝐂𝐀𝐋𝐈𝐄𝐍𝐓𝐄",
    -1003711183473: "𝐆𝐀𝐋𝐄𝐑𝐈𝐀",
    -1003431747248: "𝐆𝐀𝐋𝐄𝐑𝐈𝐀 𝐂𝐔𝐁𝐀𝐍𝐀",
}

# =========================
# CLIENTES
# =========================

client = TelegramClient(SESSION_PATH, TG_API_ID, TG_API_HASH)

# Cache para no consultar Stripe 10 veces por el mismo email en una corrida.
stripe_cache: Dict[str, dict] = {}

# =========================
# HELPERS
# =========================

def now_txt() -> Tuple[str, str]:
    dt = datetime.now(TIMEZONE)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")


def chat_name(chat_id: int) -> str:
    return CHAT_ALIASES.get(chat_id, str(chat_id))


def user_name(user: User) -> str:
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(p for p in parts if p).strip()
    if user.username:
        name = f"{name} (@{user.username})" if name else f"@{user.username}"
    return name or str(user.id)


def status_from_stripe_status(status: str) -> str:
    return "Activa" if (status or "").lower().strip() in {"active", "trialing"} else "Vencida"


async def safe_sleep(seconds: float):
    if seconds > 0:
        await asyncio.sleep(seconds)


async def report(text: str):
    log.info(text.replace("\n", " | "))
    try:
        await client.send_message(PANEL_CHAT_ID, text)
    except Exception as e:
        log.warning("No pude reportar al panel: %s", e)

# =========================
# SUPABASE REST
# =========================

async def supabase_select(filters: dict, select: str = "*") -> List[dict]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_KEY")

    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_TABLE}"
    params = {"select": select}
    for col, value in filters.items():
        params[col] = f"eq.{value}"

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=20) as http:
        resp = await http.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()

async def supabase_select_all(select: str = "*", page_size: int = 1000) -> List[dict]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_KEY")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    }

    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_TABLE}"

    rows = []
    offset = 0

    async with httpx.AsyncClient(timeout=60) as http:
        while True:
            params = {
                "select": select,
                "limit": str(page_size),
                "offset": str(offset),
            }

            resp = await http.get(url, params=params, headers=headers)
            resp.raise_for_status()

            batch = resp.json()

            if not batch:
                break

            rows.extend(batch)

            if len(batch) < page_size:
                break

            offset += page_size

    return rows

async def supabase_update_by_id(row_id: int, updates: dict):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_KEY")

    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_TABLE}"
    params = {"id": f"eq.{row_id}"}
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    # Proteccion: nunca borrar datos criticos con valores vacios.
    for critical in ("email", "stripe_name", "stripe_id"):
        if critical in updates and not updates.get(critical):
            updates.pop(critical, None)

    async with httpx.AsyncClient(timeout=20) as http:
        resp = await http.patch(url, params=params, headers=headers, json=updates)
        if resp.status_code not in (200, 204):
            raise RuntimeError(f"Supabase update error {resp.status_code}: {resp.text}")


async def get_db_row_by_telegram_id(telegram_id: int) -> Optional[dict]:
    rows = await supabase_select({"telegram_id": str(telegram_id)})
    return rows[0] if rows else None

async def get_db_row_by_id(row_id: int) -> Optional[dict]:
    rows = await supabase_select({"id": str(row_id)})
    return rows[0] if rows else None


async def sync_all_memberships_from_email(row: dict):
    emails = get_all_row_emails(row)

    if not emails:
        return

    merged = {
        "statuses": {},
        "active_cols": [],
        "expires": {},
        "cancel_at_period_end": {},
        "customer_ids": [],
    }

    for email in emails:
        data = await stripe_collect_subs(email)

        for col, status in data.get("statuses", {}).items():
            current = merged["statuses"].get(col)

            if STATUS_PRIORITY.get(status, 0) > STATUS_PRIORITY.get(current, 0):
                merged["statuses"][col] = status

        for col in data.get("active_cols", []):
            if col not in merged["active_cols"]:
                merged["active_cols"].append(col)

        merged["expires"].update(data.get("expires", {}))
        merged["cancel_at_period_end"].update(data.get("cancel_at_period_end", {}))

        for cid in data.get("customer_ids", []):
            if cid not in merged["customer_ids"]:
                merged["customer_ids"].append(cid)

    await sync_db_memberships_from_stripe(row, merged)

# =========================
# STRIPE
# =========================

def _stripe_collect_subs_sync(email: str) -> dict:
    result = {
        "statuses": {},
        "active_cols": [],
        "expires": {},
        "cancel_at_period_end": {},
        "customer_ids": [],
    }
    if not STRIPE_KEY or not email:
        return result

    customers = stripe.Customer.list(email=email, limit=10)
    for customer in customers.data:
        result["customer_ids"].append(customer.id)
        subs = stripe.Subscription.list(
            customer=customer.id,
            status="all",
            limit=100,
            expand=["data.items.data.price"],
        )
        for sub in subs.data:
            sub_status = status_from_stripe_status(getattr(sub, "status", ""))
            period_end = getattr(sub, "current_period_end", None)
            expire_date = None
            if period_end:
                expire_date = datetime.fromtimestamp(period_end, tz=TIMEZONE).strftime("%Y-%m-%d")

            for item in sub["items"]["data"]:
                price_id = item["price"]["id"]
                membership = PRICE_TO_MEMBERSHIP.get(price_id)
                if not membership:
                    continue

                current = result["statuses"].get(membership)
                if STATUS_PRIORITY.get(sub_status, 0) > STATUS_PRIORITY.get(current, 0):
                    result["statuses"][membership] = sub_status
                    if expire_date:
                        result["expires"][membership] = expire_date
                    result["cancel_at_period_end"][membership] = bool(getattr(sub, "cancel_at_period_end", False))

                if sub_status == "Activa" and membership not in result["active_cols"]:
                    result["active_cols"].append(membership)

    return result


async def stripe_collect_subs(email: str) -> dict:
    key = (email or "").strip().lower()
    if not key:
        return {"statuses": {}, "active_cols": [], "expires": {}, "customer_ids": []}
    if key in stripe_cache:
        return stripe_cache[key]
    data = await asyncio.to_thread(_stripe_collect_subs_sync, key)
    stripe_cache[key] = data
    return data

async def sync_db_memberships_from_stripe(row: dict, stripe_data: dict):
    updates = {}
    today, hour = now_txt()

    statuses = stripe_data.get("statuses", {})
    expires = stripe_data.get("expires", {})
    customer_ids = stripe_data.get("customer_ids", [])

    for col in MEMBERSHIP_COLUMNS:
        current_db_status = (row.get(col) or "").strip()

        if col in statuses:
            new_status = statuses[col]
            updates[col] = new_status

            if new_status == "Activa":
                updates[f"{col}_cancel"] = None
            else:
                updates[f"{col}_cancel"] = today

            if col in expires:
                updates[f"{col}_expire"] = expires[col]

        else:
            if current_db_status in ("Activa", "Vencida"):
                updates[col] = "Vencida"
                updates[f"{col}_cancel"] = today

    if customer_ids and not row.get("stripe_id"):
        updates["stripe_id"] = customer_ids[0]

    if updates:
        updates["cancel_fecha"] = today
        updates["cancel_hora"] = hour
        await supabase_update_by_id(row["id"], updates)

# =========================
# TELEGRAM MODERACION
# =========================

async def is_protected_member(chat_id: int, user: User, self_id: int) -> Tuple[bool, str]:
    if user.id == self_id:
        return True, "propia cuenta Telethon"
    if getattr(user, "bot", False):
        return True, "bot"

    try:
        participant = await client(GetParticipantRequest(chat_id, user.id))
        p = participant.participant
        if isinstance(p, ChannelParticipantCreator):
            return True, "owner/creador"
        if isinstance(p, ChannelParticipantAdmin):
            return True, "administrador"
    except FloodWaitError as e:
        await report(f"⏳ FloodWait revisando admin: dormir {e.seconds}s")
        await asyncio.sleep(e.seconds)
        return await is_protected_member(chat_id, user, self_id)
    except Exception:
        # Si falla la lectura del rol, NO lo protegemos automaticamente.
        pass

    return False, ""

async def kick_user(chat_id: int, user_id: int) -> bool:
    if DRY_RUN:
        return True

    rights = ChatBannedRights(until_date=None, view_messages=True)
    unban_rights = ChatBannedRights(until_date=None, view_messages=False)

    try:
        # Ban para sacarlo.
        await client(EditBannedRequest(chat_id, user_id, rights))
        await asyncio.sleep(1)
        # Unban inmediato para que pueda volver a pedir entrada con el link correcto.
        await client(EditBannedRequest(chat_id, user_id, unban_rights))
        return True
    except FloodWaitError as e:
        await report(f"⏳ FloodWait expulsando: dormir {e.seconds}s")
        await asyncio.sleep(e.seconds)
        return await kick_user(chat_id, user_id)
    except Exception as e:
        await report(f"❌ Error expulsando {user_id} de {chat_name(chat_id)}: {e}")
        return False

# =========================
# AUDITORIA
# =========================
def get_all_row_emails(row: dict) -> List[str]:
    found = []

    main_email = (row.get("email") or "").strip().lower()
    if main_email:
        found.append(main_email)

    extra = row.get("emails")

    if isinstance(extra, list):
        for item in extra:
            if isinstance(item, str):
                e = item.strip().lower()
                if e:
                    found.append(e)
            elif isinstance(item, dict):
                e = (item.get("email") or "").strip().lower()
                if e:
                    found.append(e)

    elif isinstance(extra, dict):
        for value in extra.values():
            if isinstance(value, str):
                e = value.strip().lower()
                if "@" in e:
                    found.append(e)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        e = item.strip().lower()
                        if e:
                            found.append(e)

    return list(dict.fromkeys(found))

def parse_db_datetime(row: dict) -> Optional[datetime]:
    fecha = (row.get("fecha") or "").strip()
    hora = (row.get("hora") or "").strip()

    if not fecha or not hora:
        return None

    try:
        return datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=TIMEZONE)
    except Exception:
        return None


def get_candidate_memberships_from_row(row: dict) -> List[str]:
    found = []

    for col in MEMBERSHIP_COLUMNS:
        status = (row.get(col) or "").strip()
        if status in ("Activa", "Vencida"):
            found.append(col)

    return found


def add_email_to_emails_json(row: dict, email: str):
    current = row.get("emails")
    email = (email or "").strip().lower()

    if not email:
        return current

    emails = []

    if isinstance(current, list):
        emails = current
    elif isinstance(current, dict):
        emails = current.get("emails") or []
    elif current is None:
        emails = []

    normalized = set()

    for item in emails:
        if isinstance(item, str):
            normalized.add(item.strip().lower())
        elif isinstance(item, dict):
            e = (item.get("email") or "").strip().lower()
            if e:
                normalized.add(e)

    normalized.add(email)

    return sorted(normalized)


def _stripe_find_invoice_matches_sync(target_dt: datetime, memberships: List[str]) -> List[dict]:
    matches = []

    start_ts = int((target_dt - timedelta(seconds=STRIPE_MATCH_SECONDS)).timestamp())
    end_ts = int((target_dt + timedelta(seconds=STRIPE_MATCH_SECONDS)).timestamp())

    invoices = stripe.Invoice.list(
        limit=100,
        created={"gte": start_ts, "lte": end_ts},
        expand=["data.customer", "data.lines.data.price"],
    )

    for inv in invoices.data:
        inv_dt = datetime.fromtimestamp(inv.created, tz=TIMEZONE)

        if inv_dt.strftime("%Y-%m-%d %H:%M") != target_dt.strftime("%Y-%m-%d %H:%M"):
            continue

        diff = abs((inv_dt - target_dt).total_seconds())
        if diff > STRIPE_MATCH_SECONDS:
            continue

        found_membership = None

        for line in inv.lines.data:
            price = getattr(line, "price", None)
            price_id = getattr(price, "id", None) if price else None
            m = PRICE_TO_MEMBERSHIP.get(price_id)

            if m in memberships:
                found_membership = m
                break

        if not found_membership:
            continue

        customer = inv.customer
        email = getattr(customer, "email", None)
        stripe_name = getattr(customer, "name", None)
        stripe_id = getattr(customer, "id", None)

        if not email or not stripe_id:
            continue

        matches.append({
            "email": email.strip().lower(),
            "stripe_name": stripe_name,
            "stripe_id": stripe_id,
            "membership": found_membership,
            "invoice_id": inv.id,
            "created": inv.created,
            "diff": diff,
        })

    return matches

async def find_stripe_match_by_db_time(row: dict, user_id: int) -> Optional[dict]:
    target_dt = parse_db_datetime(row)

    if not target_dt:
        return None

    memberships = get_candidate_memberships_from_row(row)

    if not memberships:
        return None

    matches = await asyncio.to_thread(
        _stripe_find_invoice_matches_sync,
        target_dt,
        memberships,
    )

    if len(matches) == 0:
        return None

    if len(matches) == 1:
        return matches[0]

    raise RuntimeError(
        "Coincidencia ambigua entre Stripe y la base de datos."
    )

async def repair_row_from_stripe_match(row: dict, match: dict):
    email = match["email"]
    updates = {}

    if not row.get("email"):
        updates["email"] = email

    if match.get("stripe_name") and not row.get("stripe_name"):
        updates["stripe_name"] = match["stripe_name"]

    if match.get("stripe_id") and not row.get("stripe_id"):
        updates["stripe_id"] = match["stripe_id"]

    updates["emails"] = add_email_to_emails_json(row, email)

    await supabase_update_by_id(row["id"], updates)

async def audit_database():
    await report("🗄️ Iniciando auditoría completa de la base de datos...")

    rows = await supabase_select_all()

    repaired = 0
    synced = 0
    missing_email = 0
    missing_telegram = 0
    ambiguous = 0
    errors = 0

    for row in rows:
        try:
            telegram_id = row.get("telegram_id")
            emails = get_all_row_emails(row)

            # -----------------------------
            # CASO 1: Tiene Telegram ID pero no tiene email
            # -----------------------------
            if telegram_id and not emails:

                match = await find_stripe_match_by_db_time(row, int(telegram_id))

                if match:
                    await repair_row_from_stripe_match(row, match)

                    row = await get_db_row_by_id(row["id"])

                    if row:
                        await sync_all_memberships_from_email(row)

                    repaired += 1

                    await report(
                        "✅ DB reparada\n"
                        f"ID DB: {row.get('id') if row else 'desconocido'}\n"
                        f"Telegram ID: {telegram_id}\n"
                        f"Email: {match['email']}\n"
                        "Acción: email reparado y membresías sincronizadas con Stripe."
                    )

                else:
                    missing_email += 1

                    await report(
                        "⚠️ No fue posible reparar el registro\n"
                        f"ID DB: {row.get('id')}\n"
                        f"Telegram ID: {telegram_id}\n"
                        "Motivo: no se encontró una coincidencia válida en Stripe usando fecha/hora."
                    )

            # -----------------------------
            # CASO 2: Tiene email
            # -----------------------------
            elif emails:

                await sync_all_memberships_from_email(row)
                synced += 1

                if not telegram_id:
                    missing_telegram += 1

                    active_text = []
                    for col in MEMBERSHIP_COLUMNS:
                        status = (row.get(col) or "").strip()
                        if status in ("Activa", "Vencida"):
                            active_text.append(f"{col}: {status}")

                    await report(
                        "📧 Email sin Telegram ID\n"
                        f"ID DB: {row.get('id')}\n"
                        f"Emails: {', '.join(emails)}\n"
                        f"Membresías DB: {', '.join(active_text) if active_text else 'ninguna registrada'}\n"
                        "Acción: membresías sincronizadas con Stripe, pero falta asociar Telegram ID."
                    )

            await safe_sleep(0.2)

        except Exception as e:
            errors += 1

            text = str(e)

            if "Coincidencia ambigua" in text:
                ambiguous += 1

                await report(
                    "⚠️ Coincidencia ambigua\n"
                    f"ID DB: {row.get('id')}\n"
                    f"Telegram ID: {row.get('telegram_id')}\n"
                    "Acción: no se actualizó el email porque Stripe devolvió más de una posible coincidencia."
                )
            else:
                await report(
                    "❌ Error auditando DB\n"
                    f"ID DB: {row.get('id')}\n"
                    f"Telegram ID: {row.get('telegram_id')}\n"
                    f"Error: {e}"
                )

    await report(
        "🏁 Auditoría DB finalizada\n"
        f"Reparados: {repaired}\n"
        f"Sincronizados: {synced}\n"
        f"Sin email: {missing_email}\n"
        f"Sin Telegram ID: {missing_telegram}\n"
        f"Coincidencias ambiguas: {ambiguous}\n"
        f"Errores: {errors}"
    )

async def process_user(chat_id: int, membership: str, user: User, self_id: int, counters: dict):
    protected, reason = await is_protected_member(chat_id, user, self_id)
    if protected:
        counters["protected"] += 1
        return

    row = None
    try:
        row = await get_db_row_by_telegram_id(user.id)
    except Exception as e:
        counters["errors"] += 1
        await report(f"❌ Error DB buscando {user.id}: {e}")
        return

    if not row:
        kick_ok = await kick_user(chat_id, user.id)
        counters["kicked_no_db"] += 1 if kick_ok else 0

        await report(
            "🚫 Usuario fuera de DB\n"
            f"Grupo: {chat_name(chat_id)}\n"
            f"Membresía requerida: {MEMBERSHIP_LABELS.get(membership, membership)}\n"
            f"Usuario: {user_name(user)}\n"
            f"Telegram ID: {user.id}\n"
            "Privado enviado: desactivado\n"
            f"Expulsado: {'sí' if kick_ok else 'no'}"
        )

        await safe_sleep(PAUSE_BETWEEN_KICKS)
        return

    emails = get_all_row_emails(row)

    if not emails:
        match = await find_stripe_match_by_db_time(row, user.id)

        if match:
            await repair_row_from_stripe_match(row, match)

            emails = [match["email"]]
            row["email"] = match["email"]
            row["emails"] = add_email_to_emails_json(row, match["email"])

            await report(
                "✅ Usuario reparado usando fecha/hora DB + Stripe\n"
                f"Grupo: {chat_name(chat_id)}\n"
                f"Usuario: {user_name(user)}\n"
                f"Telegram ID: {user.id}\n"
                f"Email encontrado: {match['email']}\n"
                f"Membresía detectada: {match['membership']}"
            )
        else:
            kick_ok = await kick_user(chat_id, user.id)
            counters["kicked_no_email"] += 1 if kick_ok else 0

            await report(
                "🚫 Usuario en DB pero sin email\n"
                f"Grupo: {chat_name(chat_id)}\n"
                f"Usuario: {user_name(user)}\n"
                f"Telegram ID: {user.id}\n"
                "Reparación por fecha/hora: no encontrada\n"
                "Privado enviado: desactivado\n"
                f"Expulsado: {'sí' if kick_ok else 'no'}"
            )

            await safe_sleep(PAUSE_BETWEEN_KICKS)
            return

    try:
        merged_stripe_data = {
            "statuses": {},
            "active_cols": [],
            "expires": {},
            "cancel_at_period_end": {},
            "customer_ids": [],
        }

        for email in emails:
            data = await stripe_collect_subs(email)

            for col, status in data.get("statuses", {}).items():
                current = merged_stripe_data["statuses"].get(col)
                if STATUS_PRIORITY.get(status, 0) > STATUS_PRIORITY.get(current, 0):
                    merged_stripe_data["statuses"][col] = status

            for col in data.get("active_cols", []):
                if col not in merged_stripe_data["active_cols"]:
                    merged_stripe_data["active_cols"].append(col)

            merged_stripe_data["expires"].update(data.get("expires", {}))
            merged_stripe_data["cancel_at_period_end"].update(data.get("cancel_at_period_end", {}))

            for cid in data.get("customer_ids", []):
                if cid not in merged_stripe_data["customer_ids"]:
                    merged_stripe_data["customer_ids"].append(cid)

        stripe_data = merged_stripe_data
        await sync_db_memberships_from_stripe(row, stripe_data)

    except Exception as e:
        counters["errors"] += 1
        await report(f"❌ Error Stripe/Supabase para {', '.join(emails)} / {user.id}: {e}")
        return

    active_cols = set(stripe_data.get("active_cols", []))

    if membership in active_cols:
        counters["valid"] += 1
        return

    kick_ok = await kick_user(chat_id, user.id)
    counters["kicked_expired"] += 1 if kick_ok else 0

    await report(
        "🚫 Membresía vencida/cancelada en Stripe\n"
        f"Grupo: {chat_name(chat_id)}\n"
        f"Membresía requerida: {MEMBERSHIP_LABELS.get(membership, membership)}\n"
        f"Usuario: {user_name(user)}\n"
        f"Telegram ID: {user.id}\n"
        f"Emails revisados: {', '.join(emails)}\n"
        f"Activas en Stripe: {', '.join(active_cols) if active_cols else 'ninguna'}\n"
        "Privado enviado: desactivado\n"
        f"Expulsado: {'sí' if kick_ok else 'no'}"
    )

    await safe_sleep(PAUSE_BETWEEN_KICKS)

async def audit_group(chat_id: int, membership: str, self_id: int) -> dict:
    counters = {
        "seen": 0,
        "protected": 0,
        "valid": 0,
        "kicked_no_db": 0,
        "kicked_no_email": 0,
        "kicked_expired": 0,
        "errors": 0,
    }

    await report(f"🔎 Iniciando revisión: {chat_name(chat_id)} | {membership}")

    batch_count = 0
    kick_counter_start = counters["kicked_no_db"] + counters["kicked_no_email"] + counters["kicked_expired"]

    try:
        async for user in client.iter_participants(chat_id):
            if not isinstance(user, User):
                continue

            counters["seen"] += 1
            batch_count += 1

            await process_user(chat_id, membership, user, self_id, counters)

            kicks_now = counters["kicked_no_db"] + counters["kicked_no_email"] + counters["kicked_expired"]
            if kicks_now > kick_counter_start and kicks_now % 20 == 0:
                await safe_sleep(PAUSE_EVERY_20_KICKS)

            if batch_count >= MEMBER_BATCH_SIZE:
                batch_count = 0
                await safe_sleep(PAUSE_BETWEEN_MEMBER_BATCHES)

            if counters["seen"] % 500 == 0:
                await safe_sleep(PAUSE_EVERY_500_MEMBERS)

    except FloodWaitError as e:
        await report(f"⏳ FloodWait leyendo {chat_name(chat_id)}: dormir {e.seconds}s")
        await asyncio.sleep(e.seconds)
    except Exception as e:
        counters["errors"] += 1
        await report(f"❌ Error revisando {chat_name(chat_id)}: {e}")

    await report(
        "✅ Revisión terminada\n"
        f"Grupo: {chat_name(chat_id)}\n"
        f"Vistos: {counters['seen']}\n"
        f"Protegidos admin/bot/self: {counters['protected']}\n"
        f"Válidos: {counters['valid']}\n"
        f"Expulsados no DB: {counters['kicked_no_db']}\n"
        f"Expulsados sin email: {counters['kicked_no_email']}\n"
        f"Expulsados vencidos: {counters['kicked_expired']}\n"
        f"Errores: {counters['errors']}"
    )
    return counters

async def audit_all_groups():
    global stripe_cache
    stripe_cache = {}

    # Primero audita y repara toda la base de datos.
    await audit_database()

    # Limpia nuevamente el cache para comenzar la auditoría de grupos.
    stripe_cache = {}

    me = await client.get_me()
    self_id = me.id
    inicio_fecha, inicio_hora = now_txt()

    await report(
        "🚀 Auditor Telethon iniciado\n"
        f"Fecha: {inicio_fecha} {inicio_hora}\n"
        f"Modo prueba DRY_RUN: {'sí' if DRY_RUN else 'no'}\n"
        f"Grupos a revisar: {len(CHAT_TO_MEMBERSHIP)}"
    )

    totals = {
        "seen": 0,
        "protected": 0,
        "valid": 0,
        "kicked_no_db": 0,
        "kicked_no_email": 0,
        "kicked_expired": 0,
        "errors": 0,
    }

    for chat_id, membership in CHAT_TO_MEMBERSHIP.items():
        c = await audit_group(chat_id, membership, self_id)

        for k in totals:
            totals[k] += c.get(k, 0)

        await safe_sleep(PAUSE_BETWEEN_GROUPS)

    fin_fecha, fin_hora = now_txt()

    await report(
        "🏁 Auditoría completa\n"
        f"Fecha fin: {fin_fecha} {fin_hora}\n"
        f"Usuarios vistos: {totals['seen']}\n"
        f"Protegidos: {totals['protected']}\n"
        f"Válidos: {totals['valid']}\n"
        f"Expulsados no DB: {totals['kicked_no_db']}\n"
        f"Expulsados sin email: {totals['kicked_no_email']}\n"
        f"Expulsados vencidos: {totals['kicked_expired']}\n"
        f"Errores: {totals['errors']}"
    )

async def scheduler_loop():
    if RUN_ON_START:
        await audit_all_groups()

    while True:
        await asyncio.sleep(RUN_EVERY_HOURS * 3600)
        await audit_all_groups()


async def main():
    missing = []
    if not TG_API_ID:
        missing.append("TG_API_ID")
    if not TG_API_HASH:
        missing.append("TG_API_HASH")
    if not TG_PHONE:
        missing.append("TG_PHONE")
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_KEY")
    if not STRIPE_KEY:
        missing.append("STRIPE_KEY")
    if missing:
        raise SystemExit("Faltan variables de entorno: " + ", ".join(missing))

    TG_CODE = os.getenv("TG_CODE")

    def code_callback():
        if not TG_CODE:
            raise RuntimeError(
                "Falta TG_CODE. Agrega la variable TG_CODE en Render con el código de Telegram y reinicia."
            )
        return TG_CODE

    await client.start(
        phone=TG_PHONE,
        password=TG_PASSWORD,
        code_callback=code_callback,
    )
    
    await client.get_dialogs()
    
    await report("✅ Cuenta Telethon conectada correctamente.")
    await scheduler_loop()


if __name__ == "__main__":
    asyncio.run(main())
