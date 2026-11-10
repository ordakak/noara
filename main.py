#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نو آرا — بات مدیریت گروه تلگرام (تک‌فایلی)
اجرا: python main.py
نیازمندی‌ها: pip install -r requirements.txt
نکته: بات را در گروه ادمین کن و Group Privacy را در BotFather روی Disable بگذار.
همه تنظیمات در بخش ۱ همین فایل است (بدون .env).
"""
import os
import re
import json
import html
import time
import random
import shutil
import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from dataclasses import dataclass
import aiohttp
import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher, Router, BaseMiddleware, F
from aiogram.types import (
    Message, CallbackQuery, ChatPermissions, ChatMemberUpdated, ErrorEvent,
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile,
)
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramRetryAfter
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
# ==========================================================
# 1. تنظیمات (Config) — همه‌چیز همین‌جا، بدون نیاز به فایل .env
# ┌──────────────────────────────────────────────────────┐
# │  اینجا را ویرایش کن (مقدارها را بین "" یا عدد بگذار)    │
# └──────────────────────────────────────────────────────┘
# توکن جدید را از BotFather بگیر و اینجا بگذار (یا در متغیر محیطی BOT_TOKEN)
BOT_TOKEN = os.getenv("BOT_TOKEN", "") or "9075735753:AAEi8HTJiI9H876TX6DFKwstC8hIrLgISMg"
SUPER_OWNER_ID = 8906898119
VIP_USER_ID = 5958083910
LLM_ENABLED = False
LLM_API_URL = ""
LLM_API_KEY = ""
LLM_MODEL = ""
# --- افزوده‌ها (امنیت/اعتماد/تگ/واکنش) — همه در بخش ۱ ---
TAG_MAX_LEN = 16
TRUST_LOW_DEFAULT = 30
TRUST_HIGH_DEFAULT = 70
REPENT_DAYS_DEFAULT = 7
WATCH_DAYS = 7
PRESETS = {
    "calm": {"antilink": 0, "anti_username": 0, "anti_mention": 0, "anti_forward": 0, "lock_sticker": 0, "lock_gif": 0, "lock_emoji": 0, "lock_photo": 0, "lock_video": 0, "lock_voice": 0, "lock_file": 0, "lock_music": 0, "badword_filter": 1, "antiflood": 0, "antilong": 0, "antirepeat": 0, "verify_join": 0, "night_lock": 0, "trust_enforce": 0, "use_reaction": 1},
    "medium": {"antilink": 1, "anti_username": 0, "anti_mention": 1, "anti_forward": 0, "lock_sticker": 0, "lock_gif": 0, "lock_emoji": 0, "lock_photo": 0, "lock_video": 0, "lock_voice": 0, "lock_file": 0, "lock_music": 0, "badword_filter": 1, "antiflood": 1, "antiflood_max": 5, "antiflood_sec": 10, "antilong": 0, "antirepeat": 1, "verify_join": 1, "night_lock": 0, "trust_enforce": 1, "use_reaction": 1},
    "strict": {"antilink": 1, "anti_username": 1, "anti_mention": 1, "anti_forward": 1, "lock_sticker": 1, "lock_gif": 1, "lock_emoji": 1, "lock_photo": 1, "lock_video": 1, "lock_voice": 0, "lock_file": 1, "lock_music": 0, "badword_filter": 1, "antiflood": 1, "antiflood_max": 3, "antiflood_sec": 10, "antilong": 1, "antilong_max": 1000, "antirepeat": 1, "verify_join": 1, "night_lock": 1, "trust_enforce": 1, "use_reaction": 1},
}
EXPLAINS = {
    "antispam": "ضداسپم: لینک، یوزرنیم، منشن جمعی، فوروارد و رسانه‌ها را محدود می‌کند. برای گپ آرام همه را خاموش و برای گپ شلوغ روشن کن.",
    "badwords": "فحش‌ها: لیست آماده + لیست خودت. واکنش را از حذف ساده تا میوت/اخراج انتخاب کن.",
    "trust": "اعتماد ۰ تا ۱۰۰ است: پیام زیاد و عضویت طولانی بالا می‌برد، اخطار و گزارش پایین می‌آورد. کم‌اعتماد محدودتر می‌شود.",
    "tags": "تگ ۰ تا ۱۶ کاراکتر، بدون ایموجی، فقط عضو عادی. نیازمند دسترسی مدیریت تگ برای بات.",
    "speaker": "سخنگو: فقط با صدا زدن، گاهی خودجوش، یا تقریبا همیشه جواب می‌دهد.",
    "dashboard": "داشبورد: فعالیت ساعتی ۲۴ ساعت اخیر، حذف‌ها و پرخطرترین‌ها.",
    "repent": "توبه: اگر چند روز تخلف نکند یک اخطار کم می‌شود. تحت‌نظر تگ موقت است.",
}
@dataclass(frozen=True)
class Config:
    token: str
    super_owner_id: int
    vip_user_id: int
    db_path: str = "noara.db"
    backup_dir: str = "backups"
config = Config(
    token=BOT_TOKEN.strip(),
    super_owner_id=int(SUPER_OWNER_ID),
    vip_user_id=int(VIP_USER_ID),
)
try:
    import pytz
    TZ = pytz.timezone("Asia/Tehran")
except Exception:
    TZ = timezone(timedelta(hours=3, minutes=30))
GROUP_TYPES = ("group", "supergroup")
def validate():
    if not config.token or config.token == "PUT_NEW_TOKEN_HERE":
        raise RuntimeError("BOT_TOKEN را در بالای فایل main.py (یا متغیر محیطی BOT_TOKEN) تنظیم کن.")
    if config.super_owner_id == 0:
        raise RuntimeError("SUPER_OWNER_ID را در بالای فایل main.py تنظیم کن.")
def now_tz() -> datetime:
    return datetime.now(TZ)
# ==========================================================
# 2. متن‌ها (Texts)
# ==========================================================
class Texts:
    START_PV = ("سلام! من <b>نو آرا</b> هستم؛ مدیر هوشمند گپ شما. 🌿\n"
                "مرا به گروه اضافه کن و ادمینم کن (حذف پیام + محدودسازی اعضا) تا کمکت کنم.")
    HELP = """<b>راهنمای نو آرا</b>"""
    NO_ACCESS = "⛔️ دسترسی کافی نداری عزیز! این دستور مخصوص مدیران است."
    OWNER_ONLY = "⛔️ این بخش فقط دست مالک گپ و سوپرمالک است."
    NO_BOT_RIGHTS = ("🤖 عزیز! من دسترسی «حذف پیام» و «محدودسازی اعضا» ندارم.\n"
                     "لطفاً مرا ادمین کن و این دو دسترسی را بده.")
    HIERARCHY_ERR = "⚠️ نمی‌توانی روی هم‌سطح یا بالاتر از خودت مجازات اعمال کنی."
    NO_TARGET = "روی پیام کاربر ریپلای کن یا آیدی عددی/یوزرنیم او را بنویس."
    BAN_OK = "🔨 کاربر مسدود شد."
    UNBAN_OK = "✅ رفع مسدودیت انجام شد."
    MUTE_OK = "🔇 کاربر بی‌صدا شد."
    UNMUTE_OK = "🔊 بی‌صدایی برداشته شد."
    KICK_OK = "👢 کاربر اخراج شد."
    WARN_OK = "⚠️ اخطار {c} از {m} ثبت شد."
    WARN_PUNISH = "🚫 سقف اخطار پر شد؛ مجازات خودکار اعمال شد."
    REPORT_SENT = "📩 گزارشت به مدیران ارسال شد."
    VERIFY_TXT = ("سلام {mention}! برای این‌که مطمئن شویم ربات نیستی، ظرف ۶۰ ثانیه دکمه‌ی زیر را بزن:\n"
                  "<b>من ربات نیستم</b>")
    WELCOME_DEF = "به {title} خوش آمدی {mention}! 🌸\nلطفاً قوانین را بخوان."
    GOODBYE_TXT = "به‌درود {name}! امیدواریم دوباره ببینیمت. 🍃"
    RULES_DEF = "هنوز قانونی ثبت نشده است."
    RULES_OK = "📜 <b>قوانین گروه:</b>\n{rules}"
    OWNER_SET = "👑 مالک جدید گپ ثبت شد."
    ROLE_SET = "✅ نقش «{role}» به کاربر داده شد."
    PROMOTE_ERR = "فقط مالک و مدیر ارشد می‌توانند نقش بدهند."
    DAILY_SUMMARY = "📊 <b>خلاصه امروز {title}</b>\n{lines}\nمواظب گپت باش! 💚"
    LOTTERY_OK = "🎉 برنده قرعه‌کشی: {name}!"
    KEY_OK = "✅ پاسخ خودکار ذخیره شد."
    PV_ONLY_GROUP = "این دستور را داخل گروه بفرست."
# ==========================================================
# 2.5 فیلتر فحش
# ==========================================================
_STRONG_TOKENS_RAW = """
کیر کیری کیرم کیرمو کیرتو کیرخر کیرکش کص کصکش کسکش کسخل کصخل کسشر کصشر کسمغز کصمغز
کون کونی کونده کونکش کونگشاد کوس کوص جنده جندگی جندهخانه جاکش جاکشی
حرومزاده حرامزاده حرومزادگی مادرجنده مادرقحبه قحبه قحبگی فاحشه روسپی هرزه
دیوث دیوثی بیناموس کسننه کصنن کسننت کصننت کسمادر کصمادر کسمادرت
ریدم ریدی ریدن ریده ریدمو ریدند گه گوه گوهی گهی ممه ممهها سکس سکسی سکسیه
جلق جلقی جق جقی جقول فاک فاکر فاکینگ سیکتیر سیکتر
گاییدم گاییدی گایید گاییده گاییدن میگام میگامت بگام بگامت بگاییدمت
پدرسگ پدرسوخته ننهسگ ننهجنده ننهقحبه ننهکسخل ننهکیری
خارکسه خارکسده خارکصده خارکسته
kir kiri kiram kirmo kirkhar kos kose kosse koskesh kosskesh kosnanat kosenanat kosmadar kosmadaret kosnane
koon kooni kuni kooon koonkesh koonde koondeh
jende jendeh jakesh jaakesh jendegi
haroomzade haramzade haromzade haroomzadeh
madarjende madarghahbe pedarsag pedarsookhte nanesag
ghahbe ghahbeh ghahbegi lashi
gayidam gaidam gaiidam gayidan bgam begam bgamet
sikter sicktir dayus dayoos binamoos
fuck fucker fucking fucked fuk fck fucc motherfuck nigger nigga bitch asshole cunt whore slut bastard
shit bitch biatch dick
"""
_MILD_TOKENS_RAW = """
احمق ابله خنگ کودن نفهم بیشعور بیشرف بیحیا بیغیرت بیوجود عوضی عوضیا عنتر
اسکل اسگل گاگول گاگولی خرفت خرفتی ایکبیری اشغال آشغال زباله کثافت کثیف
الاغ گاو خر گمشو برودبمیر بمیر زهرمار تفو
پفیوز چاقال نامرد رذل پست لاشی مفنگی بیمصرف بیخاصیت ناتو حیوون حیوان
خفهشو خفهشید ببند
idiot stupid moron dumb loser retard jerk crap douche scum trash
"""
_STRONG_SUBSTR_RAW = """
کسکش کصکش کسخل کصخل کسشر کصشر کسننت کصننت کسنن کصنن کسمادر کصمادر
کیرخر کیرمو کیرتو کیرم کیرت جنده جندگی جاکش حرومزاده حرامزاده مادرجنده مادرقحبه قحبه
گایید پدرسگ ننهجنده ننهقحبه خارکس خارکص کونکش کونگشاد کونده سیکتیر سیکتر
fuck motherfuck nigger nigga bitch asshole cunt whore
koskesh kosnanat kosenanat kosmadar kosnane madarjende madarghahbe jakesh haroomzade haramzade haromzade
pedarsag pedarsookhte kirkhar kiram kirmo kharkos kharkose kosekesh gayidam gaidam gaiidam
"""
_STRONG_PHRASES = ["سیک تیر", "خفه شو", "مادر جنده", "مادر قحبه", "پدر سگ", "ننه جنده", "mader jende", "madar jende",
                   "pedar sag", "kos nanat", "kos nane", "kir to", "kiram to", "ke yer", "kir khar"]
_STRIP = dict.fromkeys(map(ord, "\u200c\u200d\u200e\u200f\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0640_ "), None)
_STRIP_KEEP_SPACE = dict.fromkeys(map(ord, "\u200c\u200d\u200e\u200f\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0640"), None)
def norm(s: str) -> str:
    s = (s or "").lower().replace("ي", "ی").replace("ك", "ک").replace("ة", "ه")
    return s.translate(_STRIP)
def norm_text(s: str) -> str:
    s = (s or "").lower().replace("ي", "ی").replace("ك", "ک").replace("ة", "ه")
    s = s.translate(_STRIP_KEEP_SPACE)
    return re.sub(r"(.)\1{2,}", r"\1", s)
def _words(raw: str):
    return {norm_text(w) for w in raw.split() if w.strip()}
_LEET = str.maketrans("@013457$", "aoieasst")
_SUFFIXES = sorted(set("ها های ی م ت ش و رو ا ه ای ان تو مو شو ام اش هم s es ed er ing y head".split()), key=len, reverse=True)
_SEP_BETWEEN = re.compile(r"(?<=\w)[\.\-_\*\+\|\~·•]+(?=\w)")
_SPACED_RUN = re.compile(r"(?<!\w)(?:\w[\s\.\-_\*]+){2,}\w(?!\w)")
BAD_NOTES = [
    "🧼 {m} جان، دهنت رو با آب و صابون بشور! پیامت پرید.",
    "🚫 {m} این حرف‌ها اینجا جا نداره؛ بیا با ادب‌تر حرف بزنیم. 🌸",
    "🙊 {m} زبانت رو نگه دار، مامانت هم این‌جا بود ناراحت می‌شد!",
    "🧹 {m} پیامت رو جارو کردم؛ دفعه‌ی بعد بی‌ادبی نکن. 😌",
    "📵 {m} این کلمه‌ها تو گپ ما ممنوعه؛ با قند حرف بزن! 🍬",
    "🕊 {m} آروم! گپ ما جای شیرین‌زبانیه، نه فحش. 💚",
]
def defuse(nt: str) -> str:
    d = _SEP_BETWEEN.sub("", nt)
    return _SPACED_RUN.sub(lambda m: re.sub(r"[\s\.\-_\*]+", "", m.group(0)), d)
def _tok_hit(tokens: set, bank: set):
    for t in tokens:
        if t in bank:
            return t
        for suf in _SUFFIXES:
            if t.endswith(suf) and len(t) > len(suf) + 1 and t[:-len(suf)] in bank:
                return t
    return None
def has_badword(text: str, custom, builtin: bool = True, mild: bool = True):
    nt = norm_text(text)
    if not nt.strip():
        return None
    variants = {nt, defuse(nt)}
    if re.search(r"[a-z]", nt):
        lt = nt.translate(_LEET)
        variants |= {lt, defuse(lt)}
    for v in variants:
        if builtin:
            for sub in STRONG_SUBSTR:
                if sub in v:
                    return sub
            for ph in STRONG_PHRASES:
                if ph in v:
                    return ph
        tokens = set(re.findall(r"\w+", v))
        if builtin:
            h = _tok_hit(tokens, STRONG_TOKENS)
            if h:
                return h
        if mild:
            h = _tok_hit(tokens, MILD_TOKENS)
            if h:
                return h
        for w in custom:
            if w and w in v:
                return w
    return None
STRONG_TOKENS = _words(_STRONG_TOKENS_RAW)
MILD_TOKENS = _words(_MILD_TOKENS_RAW)
STRONG_SUBSTR = sorted(_words(_STRONG_SUBSTR_RAW), key=len, reverse=True)
STRONG_PHRASES = [norm_text(p) for p in _STRONG_PHRASES]
BUILTIN_COUNT = len(STRONG_TOKENS) + len(STRONG_SUBSTR) + len(STRONG_PHRASES)
# ==========================================================
# 3. ابزارها (Helpers)
# ==========================================================
ROLE_LEVELS = {"user": 0, "moderator": 1, "admin": 2, "senior": 3, "owner": 4, "super": 5}
ROLE_FA = {"user": "کاربر", "moderator": "ناظر", "admin": "مدیر", "senior": "مدیر ارشد", "owner": "مالک گپ", "super": "سوپرمالک"}
DUR_FULL = re.compile(r"^(?:\d+[smhdw])+$", re.I)
DUR_PART = re.compile(r"(\d+)([smhdw])", re.I)
PERM_WORDS = {"دائم", "دایم", "permanent", "perm", "forever"}
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\U0001F000-\U0001F2FF]")
REPEAT_RE = re.compile(r"(.)\1{5,}", re.S)
USERNAME_RE = re.compile(r"@[A-Za-z][A-Za-z0-9_]{3,31}")
LINK_RE = re.compile(r"(?:https?://|www\.)[^\s]+|(?:[a-z0-9-]+\.)+(?:com|net|org|ir|io|me|info|biz|xyz|ly|co|tv|app|site|online|link|ai|dev|cc|gg)(?:/[^\s]*)?", re.I)
def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=False)
def mention(uid: int, name: str) -> str:
    return f'<a href="tg://user?id={uid}">{esc(name or "کاربر")}</a>'
def parse_duration(tok: str):
    if not tok or not DUR_FULL.match(tok.strip()):
        return None
    total = 0
    for n, u in DUR_PART.findall(tok.lower()):
        n = int(n)
        total += n * {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[u]
    return total or None
def parse_args(tokens):
    sec, perm, reason = None, False, []
    for tk in tokens:
        if sec is None and parse_duration(tk):
            sec = parse_duration(tk)
        elif norm(tk) in {norm(w) for w in PERM_WORDS}:
            perm = True
        else:
            reason.append(tk)
    return sec, perm, " ".join(reason)
def until_from_seconds(sec):
    if not sec:
        return None
    sec = max(sec, 31)
    return datetime.now(timezone.utc) + timedelta(seconds=sec)
def fmt_dur(sec) -> str:
    if not sec:
        return "دائمی"
    d, r = divmod(int(sec), 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d} روز")
    if h: parts.append(f"{h} ساعت")
    if m: parts.append(f"{m} دقیقه")
    if s and not parts: parts.append(f"{s} ثانیه")
    return " و ".join(parts)
def can_punish(actor_lv: int, target_lv: int) -> bool:
    return actor_lv > target_lv
def text_chart(data: dict, width: int = 12) -> str:
    if not data:
        return "داده‌ای نیست."
    mx = max(data.values()) or 1
    lines = []
    for k, v in data.items():
        n = max(1, round(v / mx * width)) if v else 0
        lines.append(f"{k}: {'▓' * n}{'░' * (width - n)} {v}")
    return "\n".join(lines)
def in_night(now_hm: str, start: str, end: str) -> bool:
    try:
        def to_m(x):
            h, m = map(int, x.split(":"))
            return h * 60 + m
        n, s, e = to_m(now_hm), to_m(start), to_m(end)
        if s <= e:
            return s <= n < e
        return n >= s or n < e
    except Exception:
        return False
def valid_hm(x: str) -> bool:
    return bool(re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", x or ""))
def valid_punish(x: str) -> bool:
    return bool(re.fullmatch(r"(kick|(mute|ban)(:\d+[smhdw])?)", x or "", re.I))
def tg_err(e: Exception) -> str:
    s = str(e).lower()
    if "not enough rights" in s or "admin_required" in s or "need to be admin" in s:
        return Texts.NO_BOT_RIGHTS
    if "administrator" in s or "owner" in s:
        return "نمی‌توانم روی مدیر/مالکِ تلگرامیِ گپ اقدام کنم؛ اول باید از مدیریت تلگرام برداشته شود."
    if "not found" in s or "invalid" in s:
        return "کاربر پیدا نشد یا آیدی نامعتبر است."
    return "⚠️ انجام نشد؛ دسترسی بات و معتبر بودن کاربر را بررسی کن."
BG: set = set()
def spawn(coro):
    t = asyncio.create_task(coro)
    BG.add(t)
    t.add_done_callback(BG.discard)
    return t
async def delayed_delete(bot: Bot, chat_id: int, msg_id: int, sec: int):
    await asyncio.sleep(sec)
    try:
        await bot.delete_message(chat_id, msg_id)
    except Exception:
        pass
async def notice(bot: Bot, chat_id: int, text: str, sec: int = 10):
    try:
        m = await bot.send_message(chat_id, text)
        spawn(delayed_delete(bot, chat_id, m.message_id, sec))
    except Exception:
        pass
async def bot_can(bot: Bot, chat_id: int, pin: bool = False) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, bot.id)
        if m.status != ChatMemberStatus.ADMINISTRATOR:
            return False
        ok = bool(getattr(m, "can_restrict_members", False) and getattr(m, "can_delete_messages", False))
        if pin:
            ok = ok and bool(getattr(m, "can_pin_messages", False))
        return ok
    except Exception:
        return False
FULL_PERMS = ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True, can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True, can_invite_users=True)
async def open_perms(bot: Bot, chat_id: int) -> ChatPermissions:
    try:
        ch = await bot.get_chat(chat_id)
        p = ch.permissions
        if p:
            return ChatPermissions(**{**p.model_dump(exclude_none=True), "can_send_messages": True})
    except Exception:
        pass
    return FULL_PERMS
def domain_of(u: str) -> str:
    u = (u or "").strip().lower()
    if not re.match(r"^\w+://", u):
        u = "http://" + u
    try:
        host = urlparse(u).hostname or ""
    except Exception:
        host = ""
    return host[4:] if host.startswith("www.") else host
def extract_domains(message: Message) -> set:
    text = message.text or message.caption or ""
    ents = message.entities or message.caption_entities or []
    found = set()
    for e in ents:
        try:
            if e.type == "url":
                found.add(domain_of(e.extract_from(text)) or "unknown")
            elif e.type == "text_link" and e.url:
                found.add(domain_of(e.url) or "unknown")
        except Exception:
            found.add("unknown")
    for m in LINK_RE.finditer(text):
        found.add(domain_of(m.group(0)) or "unknown")
    return found
def count_mentions(message: Message) -> int:
    text = message.text or message.caption or ""
    ents = message.entities or message.caption_entities or []
    n = sum(1 for e in ents if e.type in ("mention", "text_mention"))
    return max(n, len(USERNAME_RE.findall(text)))
def split_words(s: str, limit: int = 60):
    out = []
    for w in re.split(r"[،,\n|]+", s or ""):
        w = norm_text(w.strip())
        if w and len(w) <= 40 and w not in out:
            out.append(w)
    return out[:limit]
def to_jalali(gy: int, gm: int, gd: int):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_d_m[gm - 1]
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd
JMONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
WEEKDAYS = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
# --- کمک‌های اعتماد/تگ/واکنش/سلامت ---
def health_dot(s: dict) -> str:
    sc = sum(1 for k in ("antilink", "badword_filter", "antiflood", "verify_join", "night_lock", "anti_forward", "anti_mention", "trust_enforce") if s.get(k))
    if sc >= 6:
        return "🟢"
    if sc >= 3:
        return "🟡"
    return "🔴"
def status_summary(s: dict) -> str:
    d = health_dot(s)
    on = sum(1 for k in ("antilink", "badword_filter", "antiflood", "verify_join", "night_lock", "trust_enforce") if s.get(k))
    label = "سالم" if d == "🟢" else ("متوسط" if d == "🟡" else "آسیب‌پذیر")
    return f"{d} وضعیت: {label} ({on}/۶ محافظ فعال)"
def valid_tag_text(t: str) -> bool:
    t = (t or "").strip()
    if t == "":
        return True
    if len(t) > TAG_MAX_LEN:
        return False
    if EMOJI_RE.search(t):
        return False
    return True
async def try_react(bot: Bot, cid: int, mid: int, emoji: str = "👀"):
    try:
        if hasattr(bot, "set_message_reaction"):
            try:
                from aiogram.types import ReactionTypeEmoji
                await bot.set_message_reaction(chat_id=cid, message_id=mid, reaction=[ReactionTypeEmoji(emoji=emoji)])
                return
            except Exception:
                pass
            try:
                await bot.set_message_reaction(cid, mid, reaction=[{"type": "emoji", "emoji": emoji}])
            except Exception:
                pass
    except Exception:
        pass
async def set_member_tag(bot: Bot, cid: int, tid: int, tag: str):
    tag = (tag or "").strip()
    if not valid_tag_text(tag):
        return False, "تگ باید ۰ تا ۱۶ کاراکتر و بدون ایموجی باشد."
    try:
        bm = await bot.get_chat_member(cid, bot.id)
        if bm.status != ChatMemberStatus.ADMINISTRATOR:
            return False, "بات ادمین نیست؛ ابتدا بات را ادمین کن و دسترسی بده."
        if getattr(bm, "can_manage_tags", None) is False:
            return False, "بات دسترسی «مدیریت تگ» ندارد؛ در تنظیمات گروه به بات بده."
    except Exception:
        pass
    try:
        tm = await bot.get_chat_member(cid, tid)
        st = getattr(getattr(tm, "status", None), "value", str(getattr(tm, "status", "")))
        if st != "member":
            return False, "تگ فقط برای اعضای عادی است؛ ادمین/مالک تگ نمی‌گیرند."
    except Exception:
        pass
    try:
        if hasattr(bot, "set_chat_member_tag"):
            try:
                await bot.set_chat_member_tag(cid, tid, tag)  # type: ignore
                return True, ""
            except Exception:
                pass
    except Exception:
        pass
    try:
        url = f"https://api.telegram.org/bot{bot.token}/setChatMemberTag"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as ses:
            async with ses.post(url, data={"chat_id": str(cid), "user_id": str(tid), "tag": tag}) as r:
                try:
                    js = await r.json()
                except Exception:
                    return False, "پاسخ تلگرام خوانا نبود. نسخه aiogram را به ۳٫۱۵+ به‌روز کن."
                if js.get("ok"):
                    return True, ""
                desc = str(js.get("description", ""))
                low = desc.lower()
                if "manage_tags" in low or "not enough rights" in low or "rights" in low:
                    return False, "بات دسترسی مدیریت تگ ندارد (can_manage_tags). در مدیریت گروه به بات بده."
                if "tag" in low:
                    return False, f"تلگرام تگ را قبول نکرد: {desc}"
                return False, f"خطای تلگرام: {desc}"
    except Exception as e:
        return False, f"خطا در تنظیم تگ: {e}"
    return False, "متد تگ در نسخه فعلی aiogram نیست؛ requirements را به aiogram>=3.15 ببر یا API خام را بررسی کن."
COMMAND_ALIASES = {
    "start": ["start", "شروع"], "help": ["help", "راهنما"],
    "ban": ["ban", "بن"], "unban": ["unban", "آنبن", "انبن"],
    "mute": ["mute", "میوت"], "unmute": ["unmute", "آنمیوت", "انمیوت"],
    "kick": ["kick", "کیک"], "warn": ["warn", "اخطار"], "unwarn": ["unwarn", "حذف_اخطار"],
    "rules": ["rules", "قوانین"], "report": ["report", "گزارش"], "stats": ["stats", "آمار"],
    "top": ["top", "برترین‌ها"], "settings": ["settings", "تنظیمات"],
    "del": ["del", "حذف"], "pin": ["pin", "سنجاق"], "unpin": ["unpin", "حذف_سنجاق"],
    "timed": ["timed", "زمان‌دار"], "poll": ["poll", "نظرسنجی"],
    "closepoll": ["closepoll", "پایان_نظرسنجی"], "lottery": ["lottery", "قرعه‌کشی"],
    "setowner": ["setowner", "تنظیم_مالک"], "addadmin": ["addadmin", "افزودن_مدیر"],
    "deladmin": ["deladmin", "حذف_مدیر"], "admins": ["admins", "مدیران"],
    "setrules": ["setrules", "ثبت_قوانین"], "setwelcome": ["setwelcome", "ثبت_خوش‌آمد"],
    "addkey": ["addkey", "افزودن_پاسخ"], "delkey": ["delkey", "حذف_پاسخ"], "keys": ["keys", "پاسخ‌ها"],
    "addfilter": ["addfilter", "افزودن_فیلتر", "addbad", "افزودن_فحش"],
    "delfilter": ["delfilter", "حذف_فیلتر", "delbad", "حذف_فحش"],
    "filters": ["filters", "فیلترها", "bads", "فحش‌ها"],
    "addwhite": ["addwhite", "افزودن_سفید"], "delwhite": ["delwhite", "حذف_سفید"],
    "whites": ["whites", "سفیدها"],
    "set": ["set", "تنظیم"], "setnight": ["setnight", "ساعت_شبانه"],
    "backup": ["backup", "بکاپ"], "groups": ["groups", "گپ‌ها"], "id": ["id", "آیدی"],
    "manage": ["manage", "ادمین", "مدیر", "مدیریت"],
    "tag": ["tag", "تگ"], "untag": ["untag", "حذف_تگ"],
    "trust": ["trust", "اعتماد"], "dashboard": ["dashboard", "داشبورد"],
    "suggest": ["suggest", "پیشنهاد"],
    "support": ["support", "پشتیبانی"],
    "mention": ["mention", "منشن", "منشن_همه", "tagall"],
}
ALIAS = {norm(a): k for k, names in COMMAND_ALIASES.items() for a in names}
PUBLIC_CMDS = {"start", "help", "rules", "report", "stats", "top", "id", "admins", "groups"}
PERSIAN_RE = re.compile(r"[\u0600-\u06FF]")
def parse_cmd(text: str, bot_username: str = ""):
    t = (text or "").strip()
    if not t:
        return None
    slash = t[0] in "/!"
    body = t[1:] if slash else t
    m = re.match(r"(\S+)\s*(.*)", body, re.S)
    if not m:
        return None
    head, tail = m.group(1), m.group(2)
    if slash and "@" in head:
        head, _, mention_ = head.partition("@")
        if mention_ and bot_username and mention_.lower() != bot_username.lower():
            return None
    m2 = re.match(r"(\S+)\s+(\S+)\s*(.*)", body, re.S)
    if m2 and norm(m2.group(1) + m2.group(2)) in ALIAS:
        name = ALIAS[norm(m2.group(1) + m2.group(2))]
        if slash or PERSIAN_RE.search(m2.group(1)):
            return name, m2.group(3).strip(), slash
    name = ALIAS.get(norm(head))
    if not name:
        return None
    if not slash and not PERSIAN_RE.search(head):
        return None
    return name, tail.strip(), slash
# ==========================================================
# 4. دیتابیس (Database)
# ==========================================================
DEFAULT_SETTINGS = {
    "antilink": 0, "anti_username": 0, "anti_mention": 0, "anti_forward": 0,
    "lock_sticker": 0, "lock_gif": 0, "lock_emoji": 0,
    "lock_photo": 0, "lock_video": 0, "lock_voice": 0, "lock_file": 0, "lock_music": 0,
    "badword_filter": 1, "badword_builtin": 1, "badword_mild": 1, "badword_punish": "delete",
    "antiflood": 1, "antiflood_max": 5, "antiflood_sec": 10,
    "antiflood_punish": "mute:1h", "antilong": 0, "antilong_max": 2000,
    "antirepeat": 1, "verify_join": 1, "night_lock": 0,
    "night_start": "00:00", "night_end": "06:00", "night_silent": 1,
    "welcome_on": 1, "welcome_text": "", "goodbye_on": 1,
    "rules_text": "", "delete_service": 1, "autodelete_cmd": 0, "autodelete_sec": 10,
    "max_warn": 3, "warn_punish": "mute:1h",
    "speaker_on": 1, "speaker_level": "medium", "speaker_mode": "called",
    "trust_enforce": 1, "trust_low": 30, "trust_high": 70,
    "repent_enabled": 1, "repent_days": 7, "watch_on_warn": 1,
    "tag_enabled": 1, "tag_auto": 1,
    "tag_template_top": "برتر هفته", "tag_template_trusted": "فعال", "tag_template_watch": "تحت‌نظر",
    "use_reaction": 1, "dashboard_on": 1, "suggest_on": 1,
}
class Database:
    def __init__(self, path: str):
        self.path = path
        self.db = None
        self._settings: dict = {}
        self._users: dict = {}
        self._groups: set = set()
    async def connect(self):
        self.db = await aiosqlite.connect(self.path)
        await self.db.execute("PRAGMA journal_mode=WAL;")
        await self.db.execute("PRAGMA synchronous=NORMAL;")
        await self.create_tables()
    async def close(self):
        if self.db:
            await self.db.close()
    async def _run(self, sql, params=()):
        cur = await self.db.execute(sql, params)
        await self.db.commit()
        return cur
    async def _one(self, sql, params=()):
        cur = await self.db.execute(sql, params)
        return await cur.fetchone()
    async def _all(self, sql, params=()):
        cur = await self.db.execute(sql, params)
        return await cur.fetchall()
    async def create_tables(self):
        await self.db.executescript("""
        CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, msg_count INTEGER DEFAULT 0, last_active TEXT);
        CREATE TABLE IF NOT EXISTS groups(chat_id INTEGER PRIMARY KEY, title TEXT, owner_id INTEGER, welcome_text TEXT DEFAULT '', rules_text TEXT DEFAULT '', created_at TEXT);
        CREATE TABLE IF NOT EXISTS admins(chat_id INTEGER, user_id INTEGER, role TEXT, added_by INTEGER, PRIMARY KEY(chat_id,user_id));
        CREATE TABLE IF NOT EXISTS warns(chat_id INTEGER, user_id INTEGER, count INTEGER DEFAULT 0, updated_at TEXT, PRIMARY KEY(chat_id,user_id));
        CREATE TABLE IF NOT EXISTS filters(chat_id INTEGER, word TEXT, PRIMARY KEY(chat_id,word));
        CREATE TABLE IF NOT EXISTS whitelists(chat_id INTEGER, value TEXT, type TEXT, PRIMARY KEY(chat_id,value));
        CREATE TABLE IF NOT EXISTS settings(chat_id INTEGER PRIMARY KEY, data TEXT);
        CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, admin_id INTEGER, target_id INTEGER, action TEXT, reason TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS keyword_replies(chat_id INTEGER, keyword TEXT, reply_text TEXT, PRIMARY KEY(chat_id,keyword));
        CREATE TABLE IF NOT EXISTS polls(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, question TEXT, options TEXT, votes TEXT, msg_id INTEGER, is_open INTEGER DEFAULT 1, created_at TEXT);
        CREATE TABLE IF NOT EXISTS activity(chat_id INTEGER, user_id INTEGER, day TEXT, count INTEGER DEFAULT 0, PRIMARY KEY(chat_id,user_id,day));
        CREATE TABLE IF NOT EXISTS member_meta(chat_id INTEGER, user_id INTEGER, join_date TEXT, violations INTEGER DEFAULT 0, last_violation TEXT, watch_until TEXT, tag TEXT DEFAULT '', PRIMARY KEY(chat_id,user_id));
        CREATE TABLE IF NOT EXISTS activity_hours(chat_id INTEGER, user_id INTEGER, hour TEXT, count INTEGER DEFAULT 0, PRIMARY KEY(chat_id,user_id,hour));
        CREATE TABLE IF NOT EXISTS support_map(msg_id INTEGER PRIMARY KEY, user_id INTEGER);
        CREATE INDEX IF NOT EXISTS idx_admins_chat ON admins(chat_id);
        CREATE INDEX IF NOT EXISTS idx_admins_user ON admins(user_id);
        CREATE INDEX IF NOT EXISTS idx_warns_chat ON warns(chat_id);
        CREATE INDEX IF NOT EXISTS idx_warns_user ON warns(user_id);
        CREATE INDEX IF NOT EXISTS idx_logs_chat ON logs(chat_id);
        CREATE INDEX IF NOT EXISTS idx_activity_chat_day ON activity(chat_id, day);
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        CREATE INDEX IF NOT EXISTS idx_logs_time ON logs(chat_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_hours ON activity_hours(chat_id, hour);
        """)
        await self.db.commit()
    async def touch_user(self, u):
        key = (u.username or "", u.full_name or "")
        if self._users.get(u.id) == key:
            return
        self._users[u.id] = key
        await self._run("INSERT INTO users(user_id,username,full_name,msg_count,last_active) VALUES(?,?,?,0,?) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name, last_active=excluded.last_active", (u.id, key[0], key[1], datetime.now().isoformat()))
    async def get_name(self, uid: int) -> str:
        r = await self._one("SELECT full_name, username FROM users WHERE user_id=?", (uid,))
        if r:
            return r[0] or (("@" + r[1]) if r[1] else str(uid))
        return str(uid)
    async def find_username(self, name: str):
        r = await self._one("SELECT user_id FROM users WHERE lower(username)=?", (name.lstrip("@").lower(),))
        return int(r[0]) if r else None
    async def record_message(self, cid: int, uid: int):
        day = now_tz().date().isoformat()
        hour = now_tz().strftime("%Y-%m-%d %H:00")
        await self.db.execute("INSERT INTO activity(chat_id,user_id,day,count) VALUES(?,?,?,1) ON CONFLICT(chat_id,user_id,day) DO UPDATE SET count=count+1", (cid, uid, day))
        await self.db.execute("INSERT INTO activity_hours(chat_id,user_id,hour,count) VALUES(?,?,?,1) ON CONFLICT(chat_id,user_id,hour) DO UPDATE SET count=count+1", (cid, uid, hour))
        await self.db.execute("UPDATE users SET msg_count=msg_count+1, last_active=? WHERE user_id=?", (datetime.now().isoformat(), uid))
        await self.db.execute("INSERT OR IGNORE INTO member_meta(chat_id,user_id,join_date,violations) VALUES(?,?,?,0)", (cid, uid, datetime.now().isoformat()))
        await self.db.commit()
    async def top(self, cid: int, days: int, limit: int = 10):
        since = (now_tz().date() - timedelta(days=days - 1)).isoformat()
        return await self._all("SELECT a.user_id, COALESCE(NULLIF(u.full_name,''), NULLIF(u.username,''), CAST(a.user_id AS TEXT)), SUM(a.count) c FROM activity a LEFT JOIN users u ON u.user_id=a.user_id WHERE a.chat_id=? AND a.day>=? GROUP BY a.user_id ORDER BY c DESC LIMIT ?", (cid, since, limit))
    async def day_total(self, cid: int) -> int:
        r = await self._one("SELECT COALESCE(SUM(count),0) FROM activity WHERE chat_id=? AND day=?", (cid, now_tz().date().isoformat()))
        return int(r[0]) if r else 0
    async def lottery_pool(self, cid: int, limit: int = 100):
        since = (now_tz().date() - timedelta(days=30)).isoformat()
        return await self._all("SELECT DISTINCT a.user_id, COALESCE(NULLIF(u.full_name,''), CAST(a.user_id AS TEXT)) FROM activity a LEFT JOIN users u ON u.user_id=a.user_id WHERE a.chat_id=? AND a.day>=? LIMIT ?", (cid, since, limit))
    async def recent_members(self, cid: int, limit: int = 300):
        since = (now_tz().date() - timedelta(days=60)).isoformat()
        return await self._all("SELECT a.user_id, COALESCE(NULLIF(u.full_name,''), NULLIF(u.username,''), CAST(a.user_id AS TEXT)) FROM activity a LEFT JOIN users u ON u.user_id=a.user_id WHERE a.chat_id=? AND a.day>=? GROUP BY a.user_id ORDER BY MAX(a.day) DESC LIMIT ?", (cid, since, limit))
    async def add_support(self, msg_id: int, uid: int):
        await self._run("INSERT OR REPLACE INTO support_map(msg_id,user_id) VALUES(?,?)", (msg_id, uid))
    async def support_target(self, msg_id: int):
        r = await self._one("SELECT user_id FROM support_map WHERE msg_id=?", (msg_id,))
        return int(r[0]) if r else None
    async def ensure_group(self, chat):
        if chat.id in self._groups:
            return
        await self.upsert_group(chat.id, chat.title or "گپ")
    async def upsert_group(self, cid: int, title: str, owner_id: int = 0):
        r = await self._one("SELECT chat_id FROM groups WHERE chat_id=?", (cid,))
        if r:
            await self._run("UPDATE groups SET title=? WHERE chat_id=?", (title, cid))
        else:
            await self._run("INSERT INTO groups(chat_id,title,owner_id,created_at) VALUES(?,?,?,?)", (cid, title, owner_id, datetime.now().isoformat()))
        await self.get_settings(cid)
        self._groups.add(cid)
    async def remove_group(self, cid: int):
        await self._run("DELETE FROM groups WHERE chat_id=?", (cid,))
        self._groups.discard(cid)
    async def get_group(self, cid: int):
        r = await self._one("SELECT title, owner_id FROM groups WHERE chat_id=?", (cid,))
        return (r[0] or "گپ", int(r[1] or 0)) if r else ("گپ", 0)
    async def set_owner(self, cid: int, uid: int):
        await self._run("UPDATE groups SET owner_id=? WHERE chat_id=?", (uid, cid))
        await self._run("UPDATE admins SET role='senior' WHERE chat_id=? AND role='owner' AND user_id!=?", (cid, uid))
        await self.set_admin(cid, uid, "owner", uid)
    async def set_owner_id_only(self, cid: int, uid: int):
        await self._run("UPDATE groups SET owner_id=? WHERE chat_id=?", (uid, cid))
    async def get_owner(self, cid: int) -> int:
        r = await self._one("SELECT owner_id FROM groups WHERE chat_id=?", (cid,))
        return int(r[0] or 0) if r else 0
    async def get_all_groups(self):
        return await self._all("SELECT chat_id,title,owner_id FROM groups")
    async def groups_of(self, uid: int):
        return await self._all("SELECT g.chat_id, g.title FROM groups g WHERE g.owner_id=? OR EXISTS(SELECT 1 FROM admins a WHERE a.chat_id=g.chat_id AND a.user_id=? AND a.role='owner')", (uid, uid))
    async def owners_of(self, cid: int) -> set:
        ids = {await self.get_owner(cid)}
        for (u,) in await self._all("SELECT user_id FROM admins WHERE chat_id=? AND role='owner'", (cid,)):
            ids.add(int(u))
        ids.discard(0)
        return ids
    async def get_settings(self, cid: int) -> dict:
        if cid in self._settings:
            return self._settings[cid]
        r = await self._one("SELECT data FROM settings WHERE chat_id=?", (cid,))
        d = dict(DEFAULT_SETTINGS)
        if r:
            try:
                d.update(json.loads(r[0]))
            except Exception:
                pass
        else:
            await self._run("INSERT INTO settings(chat_id,data) VALUES(?,?)", (cid, json.dumps(d, ensure_ascii=False)))
        self._settings[cid] = d
        return d
    async def set_setting(self, cid: int, key: str, val):
        d = dict(await self.get_settings(cid))
        d[key] = val
        self._settings[cid] = d
        await self._run("INSERT INTO settings(chat_id,data) VALUES(?,?) ON CONFLICT(chat_id) DO UPDATE SET data=excluded.data", (cid, json.dumps(d, ensure_ascii=False)))
    async def set_admin(self, cid: int, uid: int, role: str, by: int):
        await self._run("INSERT INTO admins(chat_id,user_id,role,added_by) VALUES(?,?,?,?) ON CONFLICT(chat_id,user_id) DO UPDATE SET role=excluded.role", (cid, uid, role, by))
    async def del_admin(self, cid: int, uid: int):
        await self._run("DELETE FROM admins WHERE chat_id=? AND user_id=?", (cid, uid))
    async def get_admin_role(self, cid: int, uid: int):
        r = await self._one("SELECT role FROM admins WHERE chat_id=? AND user_id=?", (cid, uid))
        return r[0] if r else None
    async def get_admins(self, cid: int):
        return await self._all("SELECT user_id,role FROM admins WHERE chat_id=?", (cid,))
    async def get_warn(self, cid: int, uid: int) -> int:
        r = await self._one("SELECT count FROM warns WHERE chat_id=? AND user_id=?", (cid, uid))
        return int(r[0]) if r else 0
    async def _set_warn(self, cid, uid, c):
        await self._run("INSERT INTO warns(chat_id,user_id,count,updated_at) VALUES(?,?,?,?) ON CONFLICT(chat_id,user_id) DO UPDATE SET count=excluded.count, updated_at=excluded.updated_at", (cid, uid, c, datetime.now().isoformat()))
    async def add_warn(self, cid: int, uid: int) -> int:
        c = await self.get_warn(cid, uid) + 1
        await self._set_warn(cid, uid, c)
        return c
    async def dec_warn(self, cid: int, uid: int) -> int:
        c = max(0, await self.get_warn(cid, uid) - 1)
        await self._set_warn(cid, uid, c)
        return c
    async def clear_warn(self, cid: int, uid: int):
        await self._run("DELETE FROM warns WHERE chat_id=? AND user_id=?", (cid, uid))
    async def add_log(self, cid: int, admin_id: int, target_id: int, action: str, reason: str = ""):
        await self._run("INSERT INTO logs(chat_id,admin_id,target_id,action,reason,created_at) VALUES(?,?,?,?,?,?)", (cid, admin_id, target_id or 0, action, reason or "", datetime.now().isoformat()))
    async def today_logs(self, cid: int):
        day = datetime.now().date().isoformat()
        return await self._all("SELECT action,COUNT(*) FROM logs WHERE chat_id=? AND substr(created_at,1,10)=? GROUP BY action", (cid, day))
    async def add_filter(self, cid, word):
        await self._run("INSERT OR IGNORE INTO filters(chat_id,word) VALUES(?,?)", (cid, word.lower()))
    async def del_filter(self, cid, word):
        await self._run("DELETE FROM filters WHERE chat_id=? AND word=?", (cid, word.lower()))
    async def clear_filters(self, cid):
        await self._run("DELETE FROM filters WHERE chat_id=?", (cid,))
    async def get_filters(self, cid):
        return [r[0] for r in await self._all("SELECT word FROM filters WHERE chat_id=? ORDER BY rowid", (cid,))]
    async def add_white(self, cid, val, typ):
        await self._run("INSERT OR REPLACE INTO whitelists(chat_id,value,type) VALUES(?,?,?)", (cid, val.lower(), typ))
    async def del_white(self, cid, val):
        await self._run("DELETE FROM whitelists WHERE chat_id=? AND value=?", (cid, val.lower()))
    async def get_whites(self, cid):
        return await self._all("SELECT value,type FROM whitelists WHERE chat_id=?", (cid,))
    async def add_keyword(self, cid, kw, txt):
        await self._run("INSERT INTO keyword_replies(chat_id,keyword,reply_text) VALUES(?,?,?) ON CONFLICT(chat_id,keyword) DO UPDATE SET reply_text=excluded.reply_text", (cid, kw, txt))
    async def del_keyword(self, cid, kw):
        await self._run("DELETE FROM keyword_replies WHERE chat_id=? AND keyword=?", (cid, kw))
    async def get_keywords(self, cid):
        return await self._all("SELECT keyword,reply_text FROM keyword_replies WHERE chat_id=?", (cid,))
    async def create_poll(self, cid, q, opts) -> int:
        cur = await self._run("INSERT INTO polls(chat_id,question,options,votes,created_at) VALUES(?,?,?,?,?)", (cid, q, json.dumps(opts, ensure_ascii=False), "{}", datetime.now().isoformat()))
        return cur.lastrowid
    async def set_poll_msg(self, pid, msg_id):
        await self._run("UPDATE polls SET msg_id=? WHERE id=?", (msg_id, pid))
    async def get_poll(self, pid):
        r = await self._one("SELECT chat_id,question,options,votes,msg_id,is_open FROM polls WHERE id=?", (pid,))
        if not r:
            return None
        try:
            votes = json.loads(r[3] or "{}")
            if not isinstance(votes, dict):
                votes = {}
        except Exception:
            votes = {}
        return {"chat_id": r[0], "q": r[1], "opts": json.loads(r[2]), "votes": votes, "msg_id": r[4], "open": bool(r[5])}
    async def vote_poll(self, pid, uid, idx):
        p = await self.get_poll(pid)
        if not p or not p["open"] or not (0 <= idx < len(p["opts"])):
            return None
        p["votes"][str(uid)] = idx
        await self._run("UPDATE polls SET votes=? WHERE id=?", (json.dumps(p["votes"]), pid))
        return p
    async def close_poll(self, pid):
        await self._run("UPDATE polls SET is_open=0 WHERE id=?", (pid,))
    async def last_open_poll(self, cid):
        r = await self._one("SELECT id FROM polls WHERE chat_id=? AND is_open=1 ORDER BY id DESC LIMIT 1", (cid,))
        return int(r[0]) if r else None
    async def backup(self) -> str:
        try:
            await self.db.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            Path(config.backup_dir).mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dst = str(Path(config.backup_dir) / f"{Path(self.path).name}.bak_{ts}")
            await asyncio.to_thread(shutil.copy2, self.path, dst)
            old = sorted(Path(config.backup_dir).glob(f"{Path(self.path).name}.bak_*"))
            for f in old[:-7]:
                f.unlink(missing_ok=True)
            return dst
        except Exception as e:
            logging.warning(f"backup error: {e}")
            return ""
    # --- اعتماد/متا/داشبورد ---
    async def ensure_member(self, cid: int, uid: int):
        await self._run("INSERT OR IGNORE INTO member_meta(chat_id,user_id,join_date,violations) VALUES(?,?,?,0)", (cid, uid, datetime.now().isoformat()))
    async def get_member_meta(self, cid: int, uid: int) -> dict:
        await self.ensure_member(cid, uid)
        r = await self._one("SELECT join_date,violations,last_violation,watch_until,tag FROM member_meta WHERE chat_id=? AND user_id=?", (cid, uid))
        if not r:
            return {"join_date": datetime.now().isoformat(), "violations": 0, "last_violation": None, "watch_until": None, "tag": ""}
        return {"join_date": r[0], "violations": int(r[1] or 0), "last_violation": r[2], "watch_until": r[3], "tag": r[4] or ""}
    async def add_violation(self, cid: int, uid: int, reason: str = ""):
        await self.ensure_member(cid, uid)
        now = datetime.now().isoformat()
        s = await self.get_settings(cid)
        watch_until = None
        if s.get("watch_on_warn"):
            watch_until = (datetime.now() + timedelta(days=WATCH_DAYS)).isoformat()
        if watch_until:
            await self._run("UPDATE member_meta SET violations=violations+1, last_violation=?, watch_until=? WHERE chat_id=? AND user_id=?", (now, watch_until, cid, uid))
        else:
            await self._run("UPDATE member_meta SET violations=violations+1, last_violation=? WHERE chat_id=? AND user_id=?", (now, cid, uid))
        await self.add_log(cid, 0, uid, "violation", reason)
    async def set_member_tag_db(self, cid: int, uid: int, tag: str):
        await self.ensure_member(cid, uid)
        await self._run("UPDATE member_meta SET tag=? WHERE chat_id=? AND user_id=?", (tag or "", cid, uid))
    async def clear_watch(self, cid: int, uid: int):
        await self._run("UPDATE member_meta SET watch_until=NULL WHERE chat_id=? AND user_id=?", (cid, uid))
    async def get_report_count(self, cid: int, uid: int) -> int:
        r = await self._one("SELECT COUNT(*) FROM logs WHERE chat_id=? AND target_id=? AND action='report'", (cid, uid))
        return int(r[0] or 0) if r else 0
    async def get_trust(self, cid: int, uid: int) -> dict:
        s = await self.get_settings(cid)
        meta = await self.get_member_meta(cid, uid)
        r = await self._one("SELECT msg_count FROM users WHERE user_id=?", (uid,))
        msgs = int(r[0] or 0) if r else 0
        warns = await self.get_warn(cid, uid)
        reports = await self.get_report_count(cid, uid)
        try:
            jd = datetime.fromisoformat(meta["join_date"]) if meta["join_date"] else datetime.now()
            age = max(0, (datetime.now() - jd).days)
        except Exception:
            age = 0
        score = 50 + min(20, msgs // 20) + min(15, (age // 30) * 3) - warns * 12 - int(meta["violations"] or 0) * 8 - reports * 10
        score = max(0, min(100, score))
        low = int(s.get("trust_low", TRUST_LOW_DEFAULT))
        high = int(s.get("trust_high", TRUST_HIGH_DEFAULT))
        lvl = "low" if score < low else ("high" if score >= high else "mid")
        watch = False
        try:
            if meta["watch_until"]:
                watch = datetime.fromisoformat(meta["watch_until"]) > datetime.now()
        except Exception:
            watch = False
        lvl_fa = {"low": "کم‌اعتماد 🔴", "mid": "معمولی 🟡", "high": "معتمد 🟢"}[lvl]
        return {"score": score, "level": lvl, "level_fa": lvl_fa, "msgs": msgs, "warns": warns, "violations": int(meta["violations"] or 0), "reports": reports, "age": age, "watch": watch, "tag": meta["tag"] or "", "join": (meta["join_date"][:10] if meta["join_date"] else "-")}
    async def get_hourly_24h(self, cid: int) -> dict:
        rows = await self._all("SELECT hour, SUM(count) FROM activity_hours WHERE chat_id=? GROUP BY hour ORDER BY hour DESC LIMIT 24", (cid,))
        d = {r[0][-5:]: int(r[1] or 0) for r in reversed(rows)} if rows else {}
        return d
    async def get_deletions_24h(self, cid: int) -> int:
        since = (datetime.now() - timedelta(hours=24)).isoformat()
        r = await self._one("SELECT COUNT(*) FROM logs WHERE chat_id=? AND created_at>=? AND action IN ('delete','badword','flood','violation','mute','ban','kick')", (cid, since))
        return int(r[0] or 0) if r else 0
    async def get_risky_24h(self, cid: int, limit: int = 5):
        since = (datetime.now() - timedelta(hours=24)).isoformat()
        return await self._all("SELECT target_id, COUNT(*) c FROM logs WHERE chat_id=? AND created_at>=? AND target_id!=0 AND action IN ('badword','flood','violation','warn','mute','ban','report') GROUP BY target_id ORDER BY c DESC LIMIT ?", (cid, since, limit))
    async def get_logs_recent(self, cid: int, limit: int = 10, offset: int = 0):
        return await self._all("SELECT admin_id,target_id,action,reason,created_at FROM logs WHERE chat_id=? ORDER BY id DESC LIMIT ? OFFSET ?", (cid, limit, offset))
    async def repent_decay_all(self):
        try:
            rows = await self._all("SELECT chat_id,user_id,count,updated_at FROM warns WHERE count>0")
        except Exception:
            return 0
        n = 0
        for cid, uid, c, upd in rows:
            try:
                s = await self.get_settings(int(cid))
                if not s.get("repent_enabled"):
                    continue
                days = int(s.get("repent_days", REPENT_DAYS_DEFAULT))
                meta = await self.get_member_meta(int(cid), int(uid))
                lv = meta.get("last_violation")
                if not lv:
                    try:
                        last = datetime.fromisoformat(upd) if upd else datetime.now() - timedelta(days=days + 1)
                    except Exception:
                        last = datetime.now() - timedelta(days=days + 1)
                else:
                    try:
                        last = datetime.fromisoformat(lv)
                    except Exception:
                        continue
                if (datetime.now() - last).days >= days:
                    await self.dec_warn(int(cid), int(uid))
                    await self.clear_watch(int(cid), int(uid))
                    n += 1
            except Exception:
                continue
        return n
# ==========================================================
# 5. کیبوردها و پنل‌ها
# ==========================================================
def _t(on) -> str:
    return "✅" if on else "❌"
def btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)
def kb(rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)
LEVEL_FA = {"low": "کم", "medium": "متوسط", "high": "زیاد"}
MODE_FA = {"called": "فقط وقتی صدا بزنند", "sometimes": "گاهی خودش وارد می‌شود", "always": "تقریباً به همه جواب می‌دهد"}
PUNISH_FA = {"delete": "فقط حذف پیام", "warn": "حذف + اخطار", "mute:10m": "حذف + میوت ۱۰ دقیقه", "mute:1h": "حذف + میوت ۱ ساعت", "kick": "حذف + اخراج"}
BADWORD_PUNISH_ORDER = ["delete", "warn", "mute:10m", "mute:1h", "kick"]
ANTISPAM_TOGGLES = [("ضدلینک", "antilink"), ("ضد یوزرنیم", "anti_username"), ("ضد منشن جمعی", "anti_mention"), ("ضدفوروارد", "anti_forward"), ("قفل استیکر", "lock_sticker"), ("قفل گیف", "lock_gif"), ("ایموجی انبوه", "lock_emoji"), ("قفل عکس", "lock_photo"), ("قفل ویدیو", "lock_video"), ("قفل ویس", "lock_voice"), ("قفل فایل", "lock_file"), ("قفل موزیک", "lock_music"), ("فیلتر کلمات زشت", "badword_filter"), ("ضدفلود", "antiflood"), ("ضدپیام طولانی", "antilong"), ("ضد حروف تکراری", "antirepeat"), ("احراز ورود", "verify_join"), ("قفل شبانه", "night_lock"), ("اعتماد تطبیقی", "trust_enforce"), ("واکنش به‌جای هشدار", "use_reaction")]
SECTION_OF = {k: "antispam" for _, k in ANTISPAM_TOGGLES}
SECTION_OF.update({"welcome_on": "welcome", "goodbye_on": "welcome", "delete_service": "welcome", "speaker_on": "speaker", "autodelete_cmd": "settings", "night_silent": "settings", "badword_builtin": "badwords", "badword_mild": "badwords", "trust_enforce": "antispam", "use_reaction": "antispam", "repent_enabled": "settings", "watch_on_warn": "settings", "tag_enabled": "tags", "tag_auto": "tags", "dashboard_on": "dashboard", "suggest_on": "suggest"})
TOGGLE_KEYS = set(SECTION_OF)
CYCLES = {"speaker_level": ("speaker", ["low", "medium", "high"]), "speaker_mode": ("called", ["sometimes", "always"]), "badword_punish": ("badwords", BADWORD_PUNISH_ORDER), "warn_punish": ("settings", ["mute:1h", "mute:1d", "ban:1d", "ban:7d", "kick"]), "antiflood_punish": ("settings", ["mute:10m", "mute:1h", "mute:1d", "ban:1d", "kick"]), "antiflood_sec": ("settings", [5, 10, 20, 30, 60]), "antilong_max": ("settings", [500, 1000, 2000, 4000]), "autodelete_sec": ("settings", [5, 10, 30, 60])}
NUMERIC = {"max_warn": (1, 10, 1), "antiflood_max": (2, 30, 1), "trust_low": (0, 100, 5), "trust_high": (0, 100, 5), "repent_days": (1, 30, 1)}
SECTION_OF.update({k: v[0] for k, v in CYCLES.items()})
SECTION_OF.update({k: "settings" for k in NUMERIC})
LAST_CHANGE: dict = {}
def remember(cid: int, key: str, old):
    LAST_CHANGE[cid] = (key, old)
def warn_kb(target: int) -> InlineKeyboardMarkup:
    return kb([[btn("➕ اخطار", f"warn_plus:{target}"), btn("➖ حذف اخطار", f"warn_minus:{target}")]])
def verify_kb(uid: int) -> InlineKeyboardMarkup:
    return kb([[btn("من ربات نیستم 🤖", f"verify:{uid}")]])
def rules_kb() -> InlineKeyboardMarkup:
    return kb([[btn("قوانین را قبول می‌کنم ✅", "rules:accept")]])
def welcome_kb() -> InlineKeyboardMarkup:
    return kb([[btn("📜 قوانین", "rules:show"), btn("قبول می‌کنم ✅", "rules:accept")]])
def groups_kb(groups) -> InlineKeyboardMarkup:
    rows = [[btn(str(title or cid)[:30], f"p:{cid}:main")] for cid, title in groups]
    rows.append([btn("🏠 صفحه‌ی اصلی", "g:home"), btn("❌ بستن", "close")])
    return kb(rows)
async def render_panel(db: Database, cid: int, section: str, pv: bool, page: int = 0):
    s = await db.get_settings(cid)
    title, _ = await db.get_group(cid)
    back = [btn("◀️ بازگشت", f"p:{cid}:main")]
    head = f"{status_summary(s)}\n<b>{esc(title)}</b>\n"
    qbtn = btn("؟ راهنما", f"q:{cid}:{section}")
    undo_row = []
    if cid in LAST_CHANGE:
        undo_row = [[btn("↩ برگردان", f"undo:{cid}")]]
    if section == "members":
        per = 8
        admins = sorted(await db.get_admins(cid), key=lambda r: -ROLE_LEVELS.get(r[1], 0))
        total_pages = max(1, (len(admins) + per - 1) // per)
        page = max(0, min(page, total_pages - 1))
        rows = []
        for uid, role in admins[page * per:(page + 1) * per]:
            nm = await db.get_name(uid)
            rows.append([btn(f"{ROLE_FA.get(role, role)} • {nm}"[:45], f"u:{cid}:{uid}:m")])
        nav = []
        if total_pages > 1:
            if page > 0:
                nav.append(btn("‹ قبلی", f"pg:{cid}:members:{page-1}"))
            nav.append(btn(f"{page+1}/{total_pages}", "noop"))
            if page < total_pages - 1:
                nav.append(btn("بعدی ›", f"pg:{cid}:members:{page+1}"))
            rows.append(nav)
        rows.append([btn("🔎 افزودن / ویرایش با آیدی", f"bw:{cid}:pick"), btn("🔎 جستجو", f"bw:{cid}:search")])
        rows.append([btn("🔄 ثبت ادمین‌های تلگرام در بات", f"bw:{cid}:sync")])
        rows.append([qbtn])
        rows.append(back)
        text = head + "👑 <b>مدیران و دسترسی‌ها</b>\nروی هر نفر بزن تا نقش و دسترسی‌هایش را تنظیم کنی."
        if not admins:
            text += "\n\nهنوز مدیری ثبت نشده."
        text += "\n\n💡 داخل گروه: ریپلای روی عضو + نوشتن «مدیر»"
        return text, kb(rows)
    if section == "antispam":
        rows, row = [], []
        for label, key in ANTISPAM_TOGGLES:
            row.append(btn(f"{label}: {_t(s.get(key))}", f"t:{cid}:{key}"))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([btn("🚫 مدیریت فحش‌ها", f"p:{cid}:badwords")])
        rows.append([btn("🟢 آرام", f"preset:{cid}:calm"), btn("🟡 متوسط", f"preset:{cid}:medium"), btn("🔴 سخت‌گیر", f"preset:{cid}:strict")])
        rows += undo_row
        rows.append([qbtn])
        rows.append(back)
        return head + "🛡 <b>ضداسپم و امنیت</b>", kb(rows)
    if section == "badwords":
        custom = await db.get_filters(cid)
        shown = "، ".join(esc(w) for w in custom[:40]) or "—"
        more = f" … (+{len(custom) - 40} مورد دیگر)" if len(custom) > 40 else ""
        rows = [[btn(f"فیلتر فحش: {_t(s.get('badword_filter'))}", f"t:{cid}:badword_filter:badwords")], [btn(f"لیست آماده‌ی سنگین: {_t(s.get('badword_builtin'))}", f"t:{cid}:badword_builtin"), btn(f"توهین‌های سبک: {_t(s.get('badword_mild'))}", f"t:{cid}:badword_mild")], [btn(f"واکنش: {PUNISH_FA.get(s.get('badword_punish'), '؟')}", f"c:{cid}:badword_punish")], [btn("➕ افزودن کلمه", f"bw:{cid}:add"), btn("➖ حذف کلمه", f"bw:{cid}:del")], [btn("📋 لیست کامل من", f"bw:{cid}:list"), btn("🧹 پاک‌کردن لیست من", f"bw:{cid}:clear")]]
        rows += undo_row
        rows.append([qbtn])
        rows.append(back)
        text = (head + "🚫 <b>مدیریت فحش و کلمات ممنوعه</b>\n" f"• لیست آماده‌ی سنگین: {BUILTIN_COUNT} مورد\n" f"• توهین‌های سبک: {len(MILD_TOKENS)} مورد\n" f"• لیست اختصاصی شما ({len(custom)} مورد): {shown}{more}\n\n" "با «➕ افزودن کلمه» کلمه‌ها را بفرست (با «،» جدا کن).")
        return text, kb(rows)
    if section == "welcome":
        rows = [[btn(f"خوش‌آمد: {_t(s.get('welcome_on'))}", f"t:{cid}:welcome_on"), btn(f"خداحافظی: {_t(s.get('goodbye_on'))}", f"t:{cid}:goodbye_on")], [btn(f"حذف پیام ورود/خروج: {_t(s.get('delete_service'))}", f"t:{cid}:delete_service")], [btn("📜 دیدن قوانین", f"x:{cid}:rules")], [qbtn], back]
        return (head + "👋 <b>خوش‌آمد و قوانین</b>\nمتن قوانین: ثبت_قوانین — متن خوش‌آمد: ثبت_خوش‌آمد\n" "در متن از {name} و {mention} و {title} می‌توانی استفاده کنی."), kb(rows)
    if section == "stats":
        rows = [[btn("📈 آمار", f"x:{cid}:stats"), btn("🏆 برترین‌ها", f"x:{cid}:top")], [btn("📊 داشبورد زنده", f"p:{cid}:dashboard")], [btn("📜 لاگ اخیر", f"p:{cid}:logs")], [qbtn], back]
        return head + "📊 <b>تعامل و آمار</b>", kb(rows)
    if section == "dashboard":
        hourly = await db.get_hourly_24h(cid)
        dels = await db.get_deletions_24h(cid)
        risky = await db.get_risky_24h(cid, 5)
        chart = text_chart({k: v for k, v in list(hourly.items())[-8:]}) if hourly else "داده‌ای نیست."
        lines = []
        for uid, c in risky:
            nm = await db.get_name(int(uid))
            try:
                tr = await db.get_trust(cid, int(uid))
                lines.append(f"• {esc(nm)} — {c} تخلف — اعتماد {tr['score']}")
            except Exception:
                lines.append(f"• {esc(nm)} — {c}")
        risky_txt = "\n".join(lines) or "—"
        txt = (head + "📊 <b>داشبورد زنده (۲۴ ساعت)</b>\n" f"🗑 حذف‌ها: <b>{dels}</b>\n<pre>{esc(chart)}</pre>\n" f"⚠️ پرخطرترین‌ها:\n{risky_txt}")
        rows = [[btn(f"داشبورد: {_t(s.get('dashboard_on'))}", f"t:{cid}:dashboard_on:dashboard")], [btn("💡 پیشنهاد خودکار", f"p:{cid}:suggest")], [qbtn], back]
        return txt, kb(rows)
    if section == "suggest":
        sug = await build_suggestions(db, cid)
        if not sug:
            txt = head + "💡 <b>پیشنهاد خودکار</b>\nهمه‌چیز مرتب است؛ تنظیم فعلی مناسب است. ✅"
            rows = [[qbtn], back]
            return txt, kb(rows)
        rows = []
        txt = head + "💡 <b>پیشنهاد خودکار تنظیمات</b>\n"
        for i, (k, v, why) in enumerate(sug[:6]):
            txt += f"\n{i+1}. <code>{esc(k)} → {esc(str(v))}</code>\n{esc(why)}\n"
            rows.append([btn(f"[اعمال] {k} → {v}", f"sug:{cid}:{k}:{v}")])
        rows.append([btn(f"پیشنهاد خودکار: {_t(s.get('suggest_on'))}", f"t:{cid}:suggest_on:suggest")])
        rows.append([qbtn])
        rows.append(back)
        return txt, kb(rows)
    if section == "tags":
        top = await db.top(cid, 7, 1)
        topname = await db.get_name(int(top[0][0])) if top else "—"
        rows = [[btn(f"تگ فعال: {_t(s.get('tag_enabled'))}", f"t:{cid}:tag_enabled:tags"), btn(f"تگ خودکار: {_t(s.get('tag_auto'))}", f"t:{cid}:tag_auto:tags")], [btn(f"قالب برتر: {s.get('tag_template_top')}", f"bw:{cid}:tagtop"), btn(f"قالب معتمد: {s.get('tag_template_trusted')}", f"bw:{cid}:tagtrusted")], [btn(f"قالب تحت‌نظر: {s.get('tag_template_watch')}", f"bw:{cid}:tagwatch")], [btn("🏷 تنظیم تگ دستی (ریپلای)", "noop")], [qbtn], back]
        txt = (head + "🏷 <b>تگ اعضا</b>\n" f"• برتر هفته: {esc(topname)}\n" f"• قالب‌ها از پنل قابل تغییر است (۰ تا ۱۶ حرف، بدون ایموجی).\n" "• دستی: ریپلای + «تگ متن» یا دستور /tag\n" "• نیازمند دسترسی can_manage_tags برای بات؛ فقط عضو عادی.")
        return txt, kb(rows)
    if section == "logs":
        per = 8
        rows_data = await db.get_logs_recent(cid, per, page * per)
        txt = head + f"📜 <b>لاگ اخیر</b> (صفحه {page+1})\n"
        if not rows_data:
            txt += "خالی است."
        else:
            for a, t, act, rs, tm in rows_data:
                txt += f"\n• {esc(str(act))} — مدیر {a} → {t} <i>{esc(str(tm)[:16])}</i>"
        nav = []
        if page > 0:
            nav.append(btn("‹ قبلی", f"pg:{cid}:logs:{page-1}"))
        nav.append(btn("بعدی ›", f"pg:{cid}:logs:{page+1}"))
        rows = [nav, [qbtn], back]
        return txt, kb(rows)
    if section == "speaker":
        rows = [[btn(f"سخنگو: {_t(s.get('speaker_on'))}", f"t:{cid}:speaker_on")], [btn(f"شدت شوخی: {LEVEL_FA.get(s.get('speaker_level'), '؟')}", f"c:{cid}:speaker_level")], [btn(f"حالت: {MODE_FA.get(s.get('speaker_mode'), '؟')}", f"c:{cid}:speaker_mode")], [qbtn], back]
        return (head + "💬 <b>سخنگوی نو آرا</b>\n" "• «فقط وقتی صدا بزنند»: با اسم «نو آرا» یا ریپلای\n" "• «گاهی خودش وارد می‌شود»: واکنش گاه‌به‌گاه\n" "• «تقریباً به همه جواب می‌دهد»: پاسخ frequent"), kb(rows)
    if section == "wizard":
        steps = ["خوش‌آمد و قوانین", "ضداسپم پایه", "فحش‌ها", "سخنگو", "پایان"]
        idx = max(0, min(page, 4))
        descs = ["متن خوش‌آمد و قوانین را ثبت کن (ثبت_خوش‌آمد / ثبت_قوانین).", "ضدلینک و ضدفلود را روشن کن.", "فیلتر فحش و واکنش را انتخاب کن.", "حالت سخنگو را انتخاب کن.", "تمام شد! از پنل اصلی مدیریت کن."]
        rows = [[btn("✅ انجام شد / بعدی ›", f"pg:{cid}:wizard:{min(4, idx+1)}")], [qbtn], back]
        return head + f"🧙 <b>جادوگر راه‌اندازی ({idx+1}/۵): {steps[idx]}</b>\n{descs[idx]}", kb(rows)
    if section == "settings":
        rows = [[btn(f"سقف اخطار: {s.get('max_warn')}", "noop"), btn("➕", f"n:{cid}:max_warn:1"), btn("➖", f"n:{cid}:max_warn:-1")], [btn(f"مجازات اخطار: {s.get('warn_punish')}", f"c:{cid}:warn_punish")], [btn(f"فلود: {s.get('antiflood_max')} پیام", "noop"), btn("➕", f"n:{cid}:antiflood_max:1"), btn("➖", f"n:{cid}:antiflood_max:-1")], [btn(f"بازه‌ی فلود: {s.get('antiflood_sec')} ثانیه", f"c:{cid}:antiflood_sec")], [btn(f"مجازات فلود: {s.get('antiflood_punish')}", f"c:{cid}:antiflood_punish")], [btn(f"حداکثر طول پیام: {s.get('antilong_max')}", f"c:{cid}:antilong_max")], [btn(f"حذف خودکار دستور: {_t(s.get('autodelete_cmd'))}", f"t:{cid}:autodelete_cmd"), btn(f"پس از {s.get('autodelete_sec')} ثانیه", f"c:{cid}:autodelete_sec")], [btn(f"حالت آرام شبانه: {_t(s.get('night_silent'))}", f"t:{cid}:night_silent")], [btn(f"توبه (کاهش اخطار): {_t(s.get('repent_enabled'))}", f"t:{cid}:repent_enabled"), btn(f"هر {s.get('repent_days')} روز", "noop")], [btn("➕", f"n:{cid}:repent_days:1"), btn("➖", f"n:{cid}:repent_days:-1"), btn(f"تحت‌نظر خودکار: {_t(s.get('watch_on_warn'))}", f"t:{cid}:watch_on_warn")], [btn(f"آستانه کم‌اعتماد: {s.get('trust_low')}", "noop"), btn("➕", f"n:{cid}:trust_low:5"), btn("➖", f"n:{cid}:trust_low:-5")], [btn(f"آستانه معتمد: {s.get('trust_high')}", "noop"), btn("➕", f"n:{cid}:trust_high:5"), btn("➖", f"n:{cid}:trust_high:-5")]]
        rows += undo_row
        rows.append([qbtn])
        rows.append(back)
        return (head + f"⚙️ <b>تنظیمات</b>\n🌙 ساعت قفل شبانه: {s.get('night_start')} تا {s.get('night_end')}" "\n(تغییر: ساعت_شبانه 23:00 07:00)"), kb(rows)
    rows = [[btn("📊 داشبورد", f"p:{cid}:dashboard"), btn("💡 پیشنهاد", f"p:{cid}:suggest")], [btn("👑 مدیران و دسترسی", f"p:{cid}:members"), btn("🛡 ضداسپم", f"p:{cid}:antispam")], [btn("🚫 فحش‌ها", f"p:{cid}:badwords"), btn("🏷 تگ‌ها", f"p:{cid}:tags")], [btn("👋 خوش‌آمد و قوانین", f"p:{cid}:welcome"), btn("📊 تعامل و آمار", f"p:{cid}:stats")], [btn("💬 سخنگو", f"p:{cid}:speaker"), btn("⚙️ تنظیمات", f"p:{cid}:settings")], [btn("🧙 جادوگر راه‌اندازی", f"p:{cid}:wizard")]]
    if pv:
        rows.append([btn("🔙 فهرست گپ‌ها", "g:list")])
    rows.append([btn("❌ بستن", "close")])
    return head + "🌿 <b>پنل نو آرا</b>", kb(rows)
async def build_suggestions(db: Database, cid: int):
    try:
        s = await db.get_settings(cid)
        dels = await db.get_deletions_24h(cid)
        hourly = await db.get_hourly_24h(cid)
        total = sum(hourly.values()) if hourly else 0
        out = []
        if dels > 10 and not s.get("antilink"):
            out.append(("antilink", 1, "حذف‌های ۲۴ ساعت زیاد است؛ ضدلینک را روشن کن."))
        if dels > 15 and not s.get("antiflood"):
            out.append(("antiflood", 1, "فلود/اسپم زیاد است؛ ضدفلود را روشن کن."))
        if dels > 8 and s.get("badword_punish") == "delete":
            out.append(("badword_punish", "warn", "فحش تکراری است؛ واکنش را از حذف به اخطار ارتقا بده."))
        if total > 200 and s.get("speaker_mode") == "called":
            out.append(("speaker_mode", "sometimes", "گپ شلوغ است؛ سخنگو را گاهی خودجوش کن."))
        if total < 20 and s.get("night_lock"):
            out.append(("night_lock", 0, "گپ خلوت است؛ قفل شبانه لازم نیست."))
        if not s.get("trust_enforce"):
            out.append(("trust_enforce", 1, "اعتماد تطبیقی خاموش است؛ برای محدودیت هوشمند روشن کن."))
        return out
    except Exception:
        return []
# ==========================================================
# 6. نقش‌ها و میدل‌ور
# ==========================================================
class Roles:
    TTL = 120
    def __init__(self, db: Database):
        self.db = db
        self.cache: dict = {}
    def invalidate(self, cid: int, uid: int):
        self.cache.pop((cid, uid), None)
    async def status(self, bot: Bot, cid: int, uid: int):
        k = (cid, uid)
        c = self.cache.get(k)
        if c and time.time() - c[1] < self.TTL:
            return c[0]
        try:
            st = (await bot.get_chat_member(cid, uid)).status
        except Exception:
            st = None
        self.cache[k] = (st, time.time())
        return st
    async def get(self, bot: Bot, cid: int, uid: int):
        if uid == config.super_owner_id:
            return "super", 5, True
        if cid > 0:
            return "user", 0, False
        st = await self.status(bot, cid, uid)
        if st == ChatMemberStatus.CREATOR:
            if await self.db.get_admin_role(cid, uid) != "owner":
                await self.db.set_admin(cid, uid, "owner", uid)
            if not await self.db.get_owner(cid):
                await self.db.set_owner_id_only(cid, uid)
            return "owner", 4, True
        tg_admin = st == ChatMemberStatus.ADMINISTRATOR
        if uid == await self.db.get_owner(cid):
            return "owner", 4, tg_admin
        r = await self.db.get_admin_role(cid, uid)
        if r in ROLE_LEVELS and r not in ("user", "super"):
            return r, ROLE_LEVELS[r], tg_admin
        return "user", 0, tg_admin
class RoleMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        bot: Bot = data["bot"]
        db: Database = data["db"]
        roles: Roles = data["roles"]
        msg = event if isinstance(event, Message) else getattr(event, "message", None)
        chat = msg.chat if msg else None
        user = getattr(event, "from_user", None)
        role, lv, tg_admin = "user", 0, False
        if user:
            try:
                if not user.is_bot:
                    await db.touch_user(user)
                if chat and chat.type in GROUP_TYPES:
                    await db.ensure_group(chat)
                    anon = isinstance(event, Message) and event.sender_chat and event.sender_chat.id == chat.id
                    if anon:
                        role, lv, tg_admin = "admin", 2, True
                    else:
                        role, lv, tg_admin = await roles.get(bot, chat.id, user.id)
                elif user.id == config.super_owner_id:
                    role, lv, tg_admin = "super", 5, True
            except Exception as e:
                logging.warning(f"role middleware error: {e}")
        data["role"], data["role_level"], data["tg_admin"] = role, lv, tg_admin
        return await handler(event, data)
# ==========================================================
# 7. روتر و دستورها
# ==========================================================
router = Router()
SCHED: AsyncIOScheduler | None = None
BOT: Bot | None = None
PENDING_VERIFY: dict = {}
PENDING_INPUT: dict = {}
FLOOD: dict = defaultdict(deque)
NIGHT_NOTE: dict = {}
BW_NOTE: dict = {}
SPEAK_LAST: dict = {}
@dataclass
class Ctx:
    message: Message
    bot: Bot
    db: Database
    roles: Roles
    args: str
    role: str
    lv: int
    @property
    def cid(self) -> int:
        return self.message.chat.id
    @property
    def uid(self) -> int:
        return self.message.from_user.id
    async def reply(self, text: str, **kw):
        try:
            return await self.message.reply(text, **kw)
        except TelegramBadRequest:
            return await self.message.answer(text, **kw)
async def resolve_target(c: Ctx):
    m = c.message
    tokens = c.args.split()
    rep = m.reply_to_message
    if rep and rep.from_user and not getattr(rep, "forum_topic_created", None):
        return rep.from_user.id, tokens
    for e in (m.entities or []):
        if e.type == "text_mention" and e.user:
            return e.user.id, tokens[1:] if tokens else tokens
    for i, tk in enumerate(tokens):
        if re.fullmatch(r"-?\d{5,}", tk):
            return int(tk), tokens[:i] + tokens[i + 1:]
        if tk.startswith("@") and len(tk) > 2:
            uid = await c.db.find_username(tk)
            if uid:
                return uid, tokens[:i] + tokens[i + 1:]
            return None, tokens
    return None, tokens
async def prep(c: Ctx, min_lv: int, rights: bool = True, hier: bool = True):
    if c.lv < min_lv:
        await c.reply(Texts.NO_ACCESS)
        return None
    if rights and not await bot_can(c.bot, c.cid):
        await c.reply(Texts.NO_BOT_RIGHTS)
        return None
    tid, rest = await resolve_target(c)
    if not tid:
        await c.reply(Texts.NO_TARGET)
        return None
    if tid == c.bot.id:
        await c.reply("روی من که نمی‌شود! 😄")
        return None
    if tid == c.uid:
        await c.reply("روی خودت که نمی‌شود! 🙂")
        return None
    if hier:
        tlv = (await c.roles.get(c.bot, c.cid, tid))[1]
        if not can_punish(c.lv, tlv):
            await c.reply(Texts.HIERARCHY_ERR)
            return None
    return tid, rest
async def do_punish(bot: Bot, cid: int, tid: int, punish: str) -> bool:
    kind, _, d = (punish or "mute:1h").partition(":")
    sec = parse_duration(d) if d else None
    try:
        if kind == "mute":
            await bot.restrict_chat_member(cid, tid, permissions=ChatPermissions(can_send_messages=False), until_date=until_from_seconds(sec))
        elif kind == "ban":
            await bot.ban_chat_member(cid, tid, until_date=until_from_seconds(sec))
        elif kind == "kick":
            await bot.ban_chat_member(cid, tid)
            await bot.unban_chat_member(cid, tid, only_if_banned=True)
        return True
    except TelegramAPIError:
        return False
async def apply_warn(bot: Bot, db: Database, cid: int, tid: int, by: int, reason: str = ""):
    s = await db.get_settings(cid)
    mx = int(s.get("max_warn", 3))
    c = await db.add_warn(cid, tid)
    await db.add_log(cid, by, tid, "warn", reason)
    try:
        await db.add_violation(cid, tid, "warn:" + (reason or ""))
    except Exception:
        pass
    punished, ok = False, True
    if c >= mx:
        ok = await do_punish(bot, cid, tid, s.get("warn_punish", "mute:1h"))
        await db.clear_warn(cid, tid)
        punished = True
        await db.add_log(cid, by, tid, "warn_punish", s.get("warn_punish", ""))
    return c, mx, punished, ok
# ==========================================================
# 7.5 پنل راهنما، پنل نقش، شروع پیوی
# ==========================================================
ADMIN_RIGHTS_LINK = ("delete_messages+restrict_members+pin_messages+invite_users+"
                     "promote_members+manage_video_chats+change_info+manage_tags+manage_topics")
HELP_SECTIONS = {
    "member": ("👤 اعضا", 0, "• <b>قوانین</b> — مثال: <code>قوانین</code>\n• <b>گزارش</b> — ریپلای + <code>گزارش</code>\n• <b>آمار</b> — مثال: <code>آمار</code>\n• <b>برترین‌ها</b> — مثال: <code>برترین‌ها</code>\n• <b>آیدی</b> — مثال: <code>آیدی</code>\n• <b>پشتیبانی</b> — در پیوی بات: <code>/support</code>"),
    "mod": ("🛡 مدیران", 1, "• <b>میوت</b> — مثال: <code>میوت 30m</code> (ریپلای)\n• <b>آنمیوت</b> — مثال: <code>آنمیوت</code>\n• <b>اخطار</b> — مثال: <code>اخطار تبلیغ</code>\n• <b>حذف_اخطار</b> — مثال: <code>حذف_اخطار</code>\n• <b>حذف</b> — ریپلای + <code>حذف</code>\n• <b>منشن</b> — مثال: <code>منشن</code> (منوی تگ گروهی)"),
    "owner": ("👑 مالک", 4, "• <b>تنظیمات</b> — مثال: <code>تنظیمات</code>\n• <b>بن</b> — مثال: <code>بن 7d اسپم</code>\n• <b>آنبن/کیک</b> — مثال: <code>آنبن @user</code>\n• <b>سنجاق</b> — ریپلای + <code>سنجاق</code>\n• <b>زمان‌دار</b> — مثال: <code>/timed 30m سلام</code>\n• <b>نظرسنجی</b> — مثال: <code>/poll س؟ | الف | ب</code>\n• <b>ثبت_قوانین</b> — مثال: <code>ثبت_قوانین احترام</code>\n• <b>تنظیم</b> — مثال: <code>/set antilink on</code>\n• <b>ساعت_شبانه</b> — مثال: <code>/setnight 23:30 07:00</code>"),
    "speaker": ("💬 سخنگو", 0, "• صدا بزن: <code>نو آرا جوک بگو</code>\n• <code>نو آرا فال بگیر</code>\n• <code>نو آرا ساعت چنده</code>\n• <code>نو آرا سکه بنداز</code> / <code>تاس بنداز</code>\n• <code>پیتزا یا برگر؟</code>"),
    "badwords": ("🚫 فحش‌ها", 4, "• پنل ← 🚫 فحش‌ها\n• <b>افزودن_فحش</b> — مثال: <code>/addbad کلمه۱، کلمه۲</code>\n• <b>حذف_فحش</b> — مثال: <code>/delbad کلمه</code>\n• <b>فحش‌ها</b> — نمایش لیست"),
    "tags": ("🏷 تگ‌ها", 4, "• <b>تگ</b> — ریپلای + مثال: <code>تگ فعال برتر</code> (۰ تا ۱۶ حرف، بدون ایموجی)\n• <b>حذف_تگ</b> — ریپلای + <code>حذف_تگ</code>\n• پنل ← 🏷 تگ‌ها (قالب برتر/معتمد/تحت‌نظر + خودکار)\n• نیازمند can_manage_tags برای بات، فقط عضو عادی"),
}
HELP_ORDER = ["member", "mod", "owner", "speaker", "badwords", "tags"]
async def help_level(bot: Bot, db: Database, roles: Roles, chat, uid: int) -> int:
    if uid == config.super_owner_id:
        return 5
    if chat.type in GROUP_TYPES:
        return (await roles.get(bot, chat.id, uid))[1]
    return 4 if await db.groups_of(uid) else 0
def help_main_text(lv: int) -> str:
    t = "📖 <b>راهنمای نو آرا</b>\nیک دسته را انتخاب کن 👇"
    if lv < 1:
        t += "\n(بخش‌های مدیریتی فقط برای مدیران نمایش داده می‌شود)"
    return t
def help_kb(lv: int, sec: str = None) -> InlineKeyboardMarkup:
    if sec:
        return kb([[btn("◀️ بازگشت", "h:main"), btn("❌ بستن", "close")]])
    rows, row = [], []
    for k in HELP_ORDER:
        label, need, _ = HELP_SECTIONS[k]
        if lv < need:
            continue
        row.append(btn(label, f"h:{k}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([btn("❌ بستن", "close")])
    return kb(rows)
async def start_view(bot: Bot, db: Database, uid: int):
    me = await bot.me()
    groups = await (db.get_all_groups() if uid == config.super_owner_id else db.groups_of(uid))
    add_url = f"https://t.me/{me.username}?startgroup=true&admin={ADMIN_RIGHTS_LINK}"
    rows = [[InlineKeyboardButton(text="➕ افزودن بات به گپ من", url=add_url)], [btn(f"📂 گپ‌های من ({len(groups)})", "g:list")], [btn("🆘 پشتیبانی", "sup:start"), btn("📖 راهنما", "h:main")], [btn("❌ بستن", "close")]]
    head = "👑 <b>پنل سوپرمالک</b>" if uid == config.super_owner_id else "🌿 <b>سلام! من نو آرا هستم؛ مدیر هوشمند گپ شما</b>"
    text = (head + "\n\n<b>شروع سریع:</b>\n" "1️⃣ دکمه‌ی «➕ افزودن بات به گپ من» را بزن و گروهت را انتخاب کن\n" "2️⃣ دسترسی‌های ادمین را تأیید کن\n" "3️⃣ از «📂 گپ‌های من» همان گپ را مدیریت کن\n\n" "💡 داخل گروه با ریپلای روی یک عضو و نوشتن «مدیر»، نقش و دسترسی‌هایش را تنظیم می‌کنی.")
    return text, kb(rows)
TG_PERMS = [("can_delete_messages", "حذف پیام"), ("can_restrict_members", "محدودکردن اعضا"), ("can_pin_messages", "سنجاق پیام"), ("can_invite_users", "دعوت کاربر"), ("can_change_info", "تغییر اطلاعات گپ"), ("can_manage_video_chats", "مدیریت ویدیوچت"), ("can_manage_topics", "مدیریت تاپیک‌ها"), ("can_manage_tags", "مدیریت تگ"), ("can_promote_members", "افزودن ادمین")]
BASIC_PERMS = {"can_delete_messages", "can_restrict_members", "can_pin_messages", "can_invite_users"}
ROLE_PICK = [("moderator", "ناظر"), ("admin", "مدیر"), ("senior", "مدیر ارشد")]
STATUS_FA = {"creator": "سازنده‌ی گروه", "administrator": "ادمین تلگرام", "member": "عضو عادی", "restricted": "محدودشده", "left": "خارج‌شده", "kicked": "مسدود"}
async def _bot_rights(bot: Bot, cid: int) -> dict:
    try:
        m = await bot.get_chat_member(cid, bot.id)
    except TelegramAPIError:
        return {}
    if m.status != ChatMemberStatus.ADMINISTRATOR:
        return {}
    return {k: bool(getattr(m, k, False)) for k, _ in TG_PERMS}
def _cur_rights(m) -> dict:
    if m is not None and m.status == ChatMemberStatus.ADMINISTRATOR:
        return {k: bool(getattr(m, k, False)) for k, _ in TG_PERMS}
    return {k: False for k, _ in TG_PERMS}
async def _promote(bot: Bot, cid: int, tid: int, rights: dict):
    await bot.promote_chat_member(cid, tid, is_anonymous=False, can_manage_chat=any(rights.values()), **{k: bool(v) for k, v in rights.items()})
async def render_user_panel(bot: Bot, db: Database, roles: Roles, cid: int, tid: int, pv: bool, sub: str = "main"):
    name = await db.get_name(tid)
    role, _, _ = await roles.get(bot, cid, tid)
    try:
        m = await bot.get_chat_member(cid, tid)
    except TelegramAPIError:
        m = None
    st = getattr(getattr(m, "status", None), "value", getattr(m, "status", "")) or ""
    warns = await db.get_warn(cid, tid)
    try:
        tr = await db.get_trust(cid, tid)
        trust_line = f"⭐ اعتماد: <b>{tr['score']}</b> ({tr['level_fa']}) | پیام:{tr['msgs']} اخطار:{tr['warns']} تخلف:{tr['violations']} عضویت:{tr['age']}روز"
        tag_line = f"🏷 تگ: {esc(tr['tag']) or '—'}" + (" ⏳ تحت‌نظر" if tr["watch"] else "")
        join_line = f"📅 ورود: {esc(tr['join'])}"
    except Exception:
        trust_line = "⭐ اعتماد: —"
        tag_line = "🏷 تگ: —"
        join_line = ""
    head = (f"👤 <b>{esc(name)}</b>  <code>{tid}</code>\n" f"🎭 نقش در بات: <b>{ROLE_FA.get(role, role)}</b>\n" f"🔑 وضعیت تلگرام: {STATUS_FA.get(st, st or '؟')}\n" f"⚠️ اخطار: {warns}\n{trust_line}\n{tag_line}\n{join_line}\n")
    back = btn("◀️ بازگشت", f"p:{cid}:members") if pv else btn("❌ بستن", "close")
    if sub == "pm":
        br = await _bot_rights(bot, cid)
        cur = _cur_rights(m)
        rows = []
        for i, (k, label) in enumerate(TG_PERMS):
            if not br.get(k) and not cur[k]:
                rows.append([btn(f"🔒 {label} (بات ندارد)", "noop")])
            else:
                rows.append([btn(f"{label}: {_t(cur[k])}", f"u:{cid}:{tid}:t:{i}")])
        rows.append([btn("👑 همه", f"u:{cid}:{tid}:p:full"), btn("🛠 پایه", f"u:{cid}:{tid}:p:basic"), btn("🚫 هیچ", f"u:{cid}:{tid}:p:none")])
        rows.append([btn("◀️ برگشت به پروفایل", f"u:{cid}:{tid}:m")])
        warn_line = "" if br.get("can_promote_members") else "\n⚠️ بات «افزودن ادمین» ندارد؛ در تنظیمات تلگرام به بات بده."
        return (head + "\n🔑 <b>دسترسی‌های ادمین تلگرام</b>\nهر دکمه را بزنی همان لحظه اعمال می‌شود." + warn_line, kb(rows))
    rows = [[btn(("✅ " if role == k else "") + label, f"u:{cid}:{tid}:r:{k}") for k, label in ROLE_PICK], [btn("🧹 برداشتن نقش", f"u:{cid}:{tid}:r:user"), btn("🔑 دسترسی‌های تلگرام", f"u:{cid}:{tid}:pm")], [btn("⚠️ اخطار", f"u:{cid}:{tid}:a:warn"), btn("➖ اخطار", f"u:{cid}:{tid}:a:unwarn"), btn("🔇 میوت ۱ساعت", f"u:{cid}:{tid}:a:mute"), btn("🔊 آنمیوت", f"u:{cid}:{tid}:a:unmute")], [btn("👢 کیک", f"cf:{cid}:{tid}:kick"), btn("🔨 بن", f"cf:{cid}:{tid}:ban"), btn("✅ آنبن", f"u:{cid}:{tid}:a:unban")], [btn("🏷 تگ", f"u:{cid}:{tid}:tag"), btn("🧹 حذف تگ", f"u:{cid}:{tid}:a:untag"), btn("⭐ اعتماد", f"u:{cid}:{tid}:trust")], [back]]
    return head + "\nیک گزینه را انتخاب کن 👇 (دکمه‌ها فقط برای مالک کار می‌کند)", kb(rows)
async def cmd_manage(c: Ctx):
    slash = (c.message.text or "").lstrip().startswith(("/", "!"))
    if c.lv < 4:
        if slash:
            await c.reply(Texts.OWNER_ONLY)
        return
    tid, _ = await resolve_target(c)
    if not tid:
        if slash:
            await c.reply(Texts.NO_TARGET)
        return
    if tid == c.bot.id:
        return
    if tid == c.uid:
        if slash:
            await c.reply("روی خودت که نمی‌شود! 🙂")
        return
    text, markup = await render_user_panel(c.bot, c.db, c.roles, c.cid, tid, False)
    await c.reply(text, reply_markup=markup)
async def cmd_start(c: Ctx):
    m = c.message
    if m.chat.type == "private":
        text, markup = await start_view(c.bot, c.db, c.uid)
        await m.answer(text, reply_markup=markup)
    else:
        if c.lv >= 4:
            text, markup = await render_panel(c.db, c.cid, "main", False)
            await m.answer(text, reply_markup=markup)
        else:
            await cmd_help(c)
async def cmd_help(c: Ctx):
    lv = await help_level(c.bot, c.db, c.roles, c.message.chat, c.uid)
    await c.message.answer(help_main_text(lv), reply_markup=help_kb(lv))
async def cmd_settings(c: Ctx):
    if c.message.chat.type == "private":
        await cmd_start(c)
        return
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    text, markup = await render_panel(c.db, c.cid, "main", False)
    await c.message.answer(text, reply_markup=markup)
async def cmd_groups(c: Ctx):
    if c.message.chat.type != "private":
        await c.reply("این دستور را در پی‌وی بات بفرست.")
        return
    await cmd_start(c)
async def cmd_id(c: Ctx):
    m = c.message
    rep = m.reply_to_message
    txt = f"🆔 آیدی تو: <code>{c.uid}</code>\n💬 آیدی گپ: <code>{c.cid}</code>"
    if rep and rep.from_user:
        txt += f"\n👤 آیدی کاربر ریپلای‌شده: <code>{rep.from_user.id}</code>"
    await c.reply(txt)
async def cmd_rules(c: Ctx):
    s = await c.db.get_settings(c.cid)
    r = s.get("rules_text") or Texts.RULES_DEF
    await c.message.answer(Texts.RULES_OK.format(rules=esc(r)), reply_markup=rules_kb())
async def cmd_report(c: Ctx):
    m = c.message
    if not m.reply_to_message or not m.reply_to_message.from_user:
        await c.reply("روی پیام مشکوک ریپلای کن.")
        return
    t = m.reply_to_message.from_user
    ids = {int(u) for u, _ in await c.db.get_admins(c.cid)} | await c.db.owners_of(c.cid) | {config.super_owner_id}
    ids.discard(c.uid)
    try:
        link = m.reply_to_message.get_url() or "-"
    except Exception:
        link = "-"
    body = (m.reply_to_message.text or m.reply_to_message.caption or "-")[:300]
    txt = (f"📩 <b>گزارش جدید</b>\nگپ: {esc(m.chat.title)}\nگزارشگر: {esc(m.from_user.full_name)}\n" f"متخلف: {esc(t.full_name)} (@{esc(t.username or '-')})\nمتن: {esc(body)}\nپیام: {esc(link)}")
    sent = 0
    for uid in ids:
        try:
            await c.bot.send_message(uid, txt)
            sent += 1
        except Exception:
            continue
    await c.db.add_log(c.cid, c.uid, t.id, "report", "")
    await c.reply(Texts.REPORT_SENT if sent else "مدیران هنوز پی‌وی بات را استارت نکرده‌اند؛ گزارش ثبت شد.")
async def cmd_stats(c: Ctx):
    rows = await c.db.top(c.cid, 7, 8)
    data = {esc(r[1])[:10]: int(r[2]) for r in rows}
    total = await c.db.day_total(c.cid)
    await c.message.answer(f"📊 <b>آمار ۷ روز اخیر</b>\n<pre>{text_chart(data)}</pre>\nپیام‌های امروز: {total}")
async def top_text(db: Database, cid: int) -> str:
    def fmt(rows):
        return "\n".join(f"{i + 1}. {esc(r[1])} — {r[2]}" for i, r in enumerate(rows)) or "—"
    d, w, mth = await db.top(cid, 1, 5), await db.top(cid, 7, 5), await db.top(cid, 30, 5)
    return f"🏆 <b>برترین‌ها</b>\n<b>روزانه:</b>\n{fmt(d)}\n\n<b>هفتگی:</b>\n{fmt(w)}\n\n<b>ماهانه:</b>\n{fmt(mth)}"
async def cmd_top(c: Ctx):
    await c.message.answer(await top_text(c.db, c.cid))
async def cmd_admins(c: Ctx):
    admins = await c.db.get_admins(c.cid)
    lines = [f"• {esc(await c.db.get_name(u))} — {ROLE_FA.get(r, r)}" for u, r in sorted(admins, key=lambda x: -ROLE_LEVELS.get(x[1], 0))]
    await c.message.answer("👥 <b>مدیران نو آرا</b>\n" + ("\n".join(lines) or "هنوز مدیری ثبت نشده."))
async def cmd_ban(c: Ctx):
    r = await prep(c, 2)
    if not r:
        return
    tid, rest = r
    sec, _, reason = parse_args(rest)
    try:
        await c.bot.ban_chat_member(c.cid, tid, until_date=until_from_seconds(sec))
    except TelegramAPIError as e:
        await c.reply(tg_err(e))
        return
    await c.db.add_log(c.cid, c.uid, tid, "ban", f"{fmt_dur(sec)} {reason}".strip())
    await c.reply(f"{Texts.BAN_OK}\n👤 {mention(tid, await c.db.get_name(tid))}\n⏱ مدت: {fmt_dur(sec)}", reply_markup=warn_kb(tid))
async def cmd_unban(c: Ctx):
    r = await prep(c, 2, hier=False)
    if not r:
        return
    tid, _ = r
    try:
        await c.bot.unban_chat_member(c.cid, tid, only_if_banned=True)
    except TelegramAPIError as e:
        await c.reply(tg_err(e))
        return
    await c.db.add_log(c.cid, c.uid, tid, "unban", "")
    await c.reply(Texts.UNBAN_OK)
async def cmd_mute(c: Ctx):
    r = await prep(c, 1)
    if not r:
        return
    tid, rest = r
    sec, _, reason = parse_args(rest)
    if c.role == "moderator" and (not sec or sec > 3600):
        sec = 3600
    try:
        await c.bot.restrict_chat_member(c.cid, tid, permissions=ChatPermissions(can_send_messages=False), until_date=until_from_seconds(sec))
    except TelegramAPIError as e:
        await c.reply(tg_err(e))
        return
    await c.db.add_log(c.cid, c.uid, tid, "mute", f"{fmt_dur(sec)} {reason}".strip())
    await c.reply(f"{Texts.MUTE_OK}\n👤 {mention(tid, await c.db.get_name(tid))}\n⏱ مدت: {fmt_dur(sec)}", reply_markup=warn_kb(tid))
async def cmd_unmute(c: Ctx):
    r = await prep(c, 1, hier=False)
    if not r:
        return
    tid, _ = r
    try:
        await c.bot.restrict_chat_member(c.cid, tid, permissions=await open_perms(c.bot, c.cid))
    except TelegramAPIError as e:
        await c.reply(tg_err(e))
        return
    await c.db.add_log(c.cid, c.uid, tid, "unmute", "")
    await c.reply(Texts.UNMUTE_OK)
async def cmd_kick(c: Ctx):
    r = await prep(c, 2)
    if not r:
        return
    tid, rest = r
    try:
        await c.bot.ban_chat_member(c.cid, tid)
        await c.bot.unban_chat_member(c.cid, tid, only_if_banned=True)
    except TelegramAPIError as e:
        await c.reply(tg_err(e))
        return
    await c.db.add_log(c.cid, c.uid, tid, "kick", " ".join(rest))
    await c.reply(f"{Texts.KICK_OK}\n👤 {mention(tid, await c.db.get_name(tid))}")
async def cmd_warn(c: Ctx):
    r = await prep(c, 1, rights=False)
    if not r:
        return
    tid, rest = r
    cnt, mx, punished, ok = await apply_warn(c.bot, c.db, c.cid, tid, c.uid, " ".join(rest))
    await c.reply(f"{Texts.WARN_OK.format(c=cnt, m=mx)}\n👤 {mention(tid, await c.db.get_name(tid))}", reply_markup=warn_kb(tid))
    if punished:
        await c.message.answer(Texts.WARN_PUNISH if ok else Texts.NO_BOT_RIGHTS)
async def cmd_unwarn(c: Ctx):
    r = await prep(c, 1, rights=False, hier=False)
    if not r:
        return
    tid, _ = r
    n = await c.db.dec_warn(c.cid, tid)
    await c.db.add_log(c.cid, c.uid, tid, "unwarn", "")
    await c.reply(f"اخطار کم شد؛ باقی‌مانده: {n}")
async def cmd_del(c: Ctx):
    if c.lv < 1:
        await c.reply(Texts.NO_ACCESS)
        return
    rep = c.message.reply_to_message
    if not rep:
        await c.reply("روی پیامی که می‌خواهی پاک شود ریپلای کن.")
        return
    if not await bot_can(c.bot, c.cid):
        await c.reply(Texts.NO_BOT_RIGHTS)
        return
    try:
        await c.bot.delete_message(c.cid, rep.message_id)
        await c.message.delete()
    except TelegramAPIError as e:
        await c.reply(tg_err(e))
        return
    await c.db.add_log(c.cid, c.uid, rep.from_user.id if rep.from_user else 0, "delete", "")
async def cmd_pin(c: Ctx):
    if c.lv < 2:
        await c.reply(Texts.NO_ACCESS)
        return
    rep = c.message.reply_to_message
    if not rep:
        await c.reply("روی پیامی که می‌خواهی سنجاق شود ریپلای کن.")
        return
    try:
        await c.bot.pin_chat_message(c.cid, rep.message_id, disable_notification=True)
    except TelegramAPIError:
        await c.reply("📌 سنجاق نشد؛ دسترسی «سنجاق پیام» را به من بده.")
        return
    await c.db.add_log(c.cid, c.uid, 0, "pin", "")
async def cmd_unpin(c: Ctx):
    if c.lv < 2:
        await c.reply(Texts.NO_ACCESS)
        return
    try:
        rep = c.message.reply_to_message
        if rep:
            await c.bot.unpin_chat_message(c.cid, rep.message_id)
        else:
            await c.bot.unpin_chat_message(c.cid)
    except TelegramAPIError:
        await c.reply("سنجاق برداشته نشد؛ دسترسی «سنجاق پیام» را بررسی کن.")
        return
    await c.reply("✅ سنجاق برداشته شد.")
async def send_timed(chat_id: int, text: str):
    try:
        await BOT.send_message(chat_id, text)
    except Exception as e:
        logging.warning(f"timed message error: {e}")
async def cmd_timed(c: Ctx):
    if c.lv < 2:
        await c.reply(Texts.NO_ACCESS)
        return
    parts = c.args.split(None, 1)
    sec = parse_duration(parts[0]) if parts else None
    text = parts[1] if len(parts) > 1 else ((c.message.reply_to_message.text or c.message.reply_to_message.caption or "") if c.message.reply_to_message else "")
    if not sec or not text:
        await c.reply("مثال: /timed 30m متن پیام  (یا ریپلای روی یک پیام + /timed 2h)")
        return
    SCHED.add_job(send_timed, "date", run_date=datetime.now(timezone.utc) + timedelta(seconds=sec), args=[c.cid, esc(text)])
    await c.db.add_log(c.cid, c.uid, 0, "timed", fmt_dur(sec))
    await c.reply(f"⏰ پیام پس از {fmt_dur(sec)} ارسال می‌شود.")
async def cmd_setowner(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    r = await prep(c, 4, rights=False, hier=False)
    if not r:
        return
    tid, _ = r
    await c.db.set_owner(c.cid, tid)
    c.roles.invalidate(c.cid, tid)
    await c.db.add_log(c.cid, c.uid, tid, "setowner", "")
    await c.reply(Texts.OWNER_SET)
async def cmd_addadmin(c: Ctx):
    if c.lv < 3:
        await c.reply(Texts.PROMOTE_ERR)
        return
    r = await prep(c, 3, rights=False)
    if not r:
        return
    tid, rest = r
    role_map = {"senior": "senior", "مدیرارشد": "senior", "admin": "admin", "مدیر": "admin", "moderator": "moderator", "ناظر": "moderator"}
    word = norm(rest[0]) if rest else "admin"
    role = role_map.get(word, "admin")
    if ROLE_LEVELS[role] >= c.lv:
        await c.reply("نمی‌توانی نقشی هم‌سطح یا بالاتر از خودت بدهی.")
        return
    await c.db.set_admin(c.cid, tid, role, c.uid)
    c.roles.invalidate(c.cid, tid)
    await c.db.add_log(c.cid, c.uid, tid, f"promote:{role}", "")
    await c.reply(Texts.ROLE_SET.format(role=ROLE_FA[role]))
async def cmd_deladmin(c: Ctx):
    if c.lv < 3:
        await c.reply(Texts.PROMOTE_ERR)
        return
    r = await prep(c, 3, rights=False)
    if not r:
        return
    tid, _ = r
    await c.db.del_admin(c.cid, tid)
    c.roles.invalidate(c.cid, tid)
    await c.db.add_log(c.cid, c.uid, tid, "demote", "")
    await c.reply("✅ نقش مدیریتی حذف شد.")
def _text_arg(c: Ctx) -> str:
    rep = c.message.reply_to_message
    return c.args or ((rep.text or rep.caption or "") if rep else "")
async def cmd_setrules(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    txt = _text_arg(c)
    if not txt:
        await c.reply("متن قوانین را بنویس یا روی آن ریپلای کن.")
        return
    await c.db.set_setting(c.cid, "rules_text", txt)
    await c.reply("✅ قوانین ثبت شد.")
async def cmd_setwelcome(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    txt = _text_arg(c)
    if not txt:
        await c.reply("متن خوش‌آمد را بنویس. می‌توانی از {name} و {mention} و {title} استفاده کنی.")
        return
    await c.db.set_setting(c.cid, "welcome_text", txt)
    await c.reply("✅ متن خوش‌آمد ثبت شد.")
async def cmd_addkey(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    if "|" not in c.args:
        await c.reply("مثال: /addkey سلام | سلام عزیز! 🌸")
        return
    kw, rep = [p.strip() for p in c.args.split("|", 1)]
    if not kw or not rep:
        await c.reply("کلمه و پاسخ هر دو لازم است.")
        return
    await c.db.add_keyword(c.cid, kw, rep)
    await c.reply(Texts.KEY_OK)
async def cmd_delkey(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    await c.db.del_keyword(c.cid, c.args.strip())
    await c.reply("✅ حذف شد.")
async def cmd_keys(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    ks = await c.db.get_keywords(c.cid)
    await c.reply("\n".join(f"• {esc(k)} ⟵ {esc(v)[:40]}" for k, v in ks) or "پاسخ خودکاری ثبت نشده.")
async def cmd_addfilter(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    words = split_words(_text_arg(c))
    if not words:
        await c.reply("کلمه(ها) را بنویس؛ چند کلمه را با «،» جدا کن. مثال: /addbad کلمه۱، کلمه۲")
        return
    for w in words:
        await c.db.add_filter(c.cid, w)
    try:
        await c.message.delete()
    except Exception:
        pass
    await notice(c.bot, c.cid, f"✅ {len(words)} کلمه به لیست ممنوعه اضافه شد.")
async def cmd_delfilter(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    words = split_words(_text_arg(c))
    if not words:
        await c.reply("کلمه(ها) را بنویس.")
        return
    for w in words:
        await c.db.del_filter(c.cid, w)
    await c.reply(f"✅ {len(words)} کلمه از لیست سیاه حذف شد.")
async def cmd_filters(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    f = await c.db.get_filters(c.cid)
    await c.reply("🚫 لیست سیاه شما:\n" + ("، ".join(esc(x) for x in f) or "خالی") + f"\n\n(لیست آماده‌ی ربات: {BUILTIN_COUNT} مورد سنگین + {len(MILD_TOKENS)} توهین سبک)")
async def cmd_addwhite(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    rep = c.message.reply_to_message
    tok = c.args.split()[0] if c.args.split() else ""
    if rep and rep.from_user and not tok:
        val, typ = str(rep.from_user.id), "user"
    elif re.fullmatch(r"-?\d{5,}", tok):
        val, typ = tok, ("channel" if tok.startswith("-") else "user")
    elif tok:
        val, typ = domain_of(tok), "domain"
        if not val:
            await c.reply("دامنه نامعتبر است.")
            return
    else:
        await c.reply("مثال: /addwhite example.com  یا ریپلای روی کاربر  یا آیدی کاربر/کانال")
        return
    await c.db.add_white(c.cid, val, typ)
    await c.reply(f"✅ به وایت‌لیست اضافه شد ({typ}).")
async def cmd_delwhite(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    rep = c.message.reply_to_message
    tok = c.args.split()[0] if c.args.split() else (str(rep.from_user.id) if rep and rep.from_user else "")
    if not tok:
        await c.reply("مقدار را بنویس.")
        return
    await c.db.del_white(c.cid, domain_of(tok) if not re.fullmatch(r"-?\d{5,}", tok) else tok)
    await c.reply("✅ از وایت‌لیست حذف شد.")
async def cmd_whites(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    w = await c.db.get_whites(c.cid)
    await c.reply("✅ وایت‌لیست:\n" + ("\n".join(f"• {esc(v)} ({t})" for v, t in w) or "خالی"))
SET_RULES = {"max_warn": ("int", 1, 10), "antiflood_max": ("int", 2, 30), "antiflood_sec": ("int", 3, 120), "antilong_max": ("int", 100, 4000), "autodelete_sec": ("int", 3, 300), "warn_punish": ("punish",), "antiflood_punish": ("punish",), "night_start": ("time",), "night_end": ("time",), "badword_punish": ("choice", BADWORD_PUNISH_ORDER), "speaker_mode": ("choice", ["called", "sometimes", "always"]), "speaker_level": ("choice", ["low", "medium", "high"]), "trust_low": ("int", 0, 100), "trust_high": ("int", 0, 100), "repent_days": ("int", 1, 30)}
ON_WORDS = {"on", "1", "روشن", "فعال", "true"}
OFF_WORDS = {"off", "0", "خاموش", "غیرفعال", "false"}
async def cmd_set(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    parts = c.args.split()
    if len(parts) < 2:
        keys = "، ".join(sorted(TOGGLE_KEYS | set(SET_RULES) | {"tag_template_top", "tag_template_trusted", "tag_template_watch"}))
        await c.reply(f"مثال: /set antilink on  یا  /set max_warn 4\nکلیدها:\n<code>{keys}</code>")
        return
    key, val_raw = parts[0], " ".join(parts[1:])
    val = val_raw.lower()
    if key in ("tag_template_top", "tag_template_trusted", "tag_template_watch"):
        t = val_raw.strip()[:TAG_MAX_LEN]
        if t and not valid_tag_text(t):
            await c.reply("قالب تگ باید بدون ایموجی و حداکثر ۱۶ کاراکتر باشد.")
            return
        old = (await c.db.get_settings(c.cid)).get(key)
        remember(c.cid, key, old)
        await c.db.set_setting(c.cid, key, val_raw.strip())
        await c.reply(f"✅ {key} ثبت شد.")
        return
    if key in TOGGLE_KEYS:
        if val in ON_WORDS:
            v = 1
        elif val in OFF_WORDS:
            v = 0
        else:
            await c.reply("مقدار باید on یا off باشد.")
            return
    elif key in SET_RULES:
        rule = SET_RULES[key]
        if rule[0] == "int" and val.isdigit() and rule[1] <= int(val) <= rule[2]:
            v = int(val)
        elif rule[0] == "punish" and valid_punish(val):
            v = val
        elif rule[0] == "time" and valid_hm(val):
            v = val
        elif rule[0] == "choice" and val in rule[1]:
            v = val
        else:
            await c.reply("مقدار نامعتبر است." + (f"\nگزینه‌ها: <code>{'، '.join(rule[1])}</code>" if rule[0] == "choice" else ""))
            return
    else:
        await c.reply("کلید ناشناخته است.")
        return
    old = (await c.db.get_settings(c.cid)).get(key)
    remember(c.cid, key, old)
    await c.db.set_setting(c.cid, key, v)
    await c.reply(f"✅ {key} = {v}")
async def cmd_setnight(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    p = c.args.split()
    if len(p) != 2 or not (valid_hm(p[0]) and valid_hm(p[1])):
        await c.reply("مثال: /setnight 23:30 07:00")
        return
    await c.db.set_setting(c.cid, "night_start", p[0])
    await c.db.set_setting(c.cid, "night_end", p[1])
    await c.db.set_setting(c.cid, "night_lock", 1)
    await c.reply(f"🌙 قفل شبانه از {p[0]} تا {p[1]} فعال شد.")
async def cmd_backup(c: Ctx):
    if c.uid != config.super_owner_id:
        await c.reply(Texts.NO_ACCESS)
        return
    path = await c.db.backup()
    if not path:
        await c.reply("⚠️ بکاپ ناموفق بود.")
        return
    try:
        await c.bot.send_document(config.super_owner_id, FSInputFile(path), caption="🗄 بکاپ دیتابیس")
    except Exception:
        pass
    await c.reply(f"🗄 بکاپ گرفته شد: <code>{esc(path)}</code>")
async def cmd_tag(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    s = await c.db.get_settings(c.cid)
    if not s.get("tag_enabled"):
        await c.reply("تگ غیرفعال است؛ از پنل ← 🏷 تگ‌ها فعال کن.")
        return
    tid, rest = await resolve_target(c)
    if not tid:
        await c.reply("روی پیام عضو ریپلای کن یا آیدی/یوزرنیم بده. مثال: تگ فعال برتر")
        return
    tag = " ".join(rest).strip()[:TAG_MAX_LEN]
    if tag and not valid_tag_text(tag):
        await c.reply("تگ باید ۰ تا ۱۶ کاراکتر و بدون ایموجی باشد.")
        return
    ok, msg = await set_member_tag(c.bot, c.cid, tid, tag)
    if ok:
        await c.db.set_member_tag_db(c.cid, tid, tag)
        await c.db.add_log(c.cid, c.uid, tid, "tag", tag)
        await c.reply(f"🏷 تگ «{esc(tag) or '—'}» برای {mention(tid, await c.db.get_name(tid))} ثبت شد.")
    else:
        await c.reply(f"⚠️ {esc(msg)}")
async def cmd_untag(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    tid, _ = await resolve_target(c)
    if not tid:
        await c.reply(Texts.NO_TARGET)
        return
    ok, msg = await set_member_tag(c.bot, c.cid, tid, "")
    if ok:
        await c.db.set_member_tag_db(c.cid, tid, "")
        await c.db.add_log(c.cid, c.uid, tid, "untag", "")
        await c.reply("🧹 تگ حذف شد.")
    else:
        await c.reply(f"⚠️ {esc(msg)}")
async def cmd_trust(c: Ctx):
    tid, _ = await resolve_target(c)
    if not tid:
        tid = c.uid
    try:
        tr = await c.db.get_trust(c.cid, tid)
    except Exception:
        await c.reply("خطا در محاسبه اعتماد.")
        return
    nm = await c.db.get_name(tid)
    await c.reply(f"⭐ <b>اعتماد {esc(nm)}</b>\nامتیاز: <b>{tr['score']}</b> ({tr['level_fa']})\n💬 پیام: {tr['msgs']} | ⚠️ اخطار: {tr['warns']} | 🚫 تخلف: {tr['violations']} | 📩 گزارش: {tr['reports']}\n📅 عضویت: {tr['age']} روز | 🏷 تگ: {esc(tr['tag']) or '—'}" + (" ⏳ تحت‌نظر" if tr["watch"] else ""))
async def cmd_dashboard(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    text, markup = await render_panel(c.db, c.cid, "dashboard", c.message.chat.type == "private")
    await c.message.answer(text, reply_markup=markup)
async def cmd_suggest(c: Ctx):
    if c.lv < 4:
        await c.reply(Texts.OWNER_ONLY)
        return
    text, markup = await render_panel(c.db, c.cid, "suggest", c.message.chat.type == "private")
    await c.message.answer(text, reply_markup=markup)
def poll_text(p: dict) -> str:
    counts = [0] * len(p["opts"])
    for v in p["votes"].values():
        if 0 <= v < len(counts):
            counts[v] += 1
    total = sum(counts) or 1
    lines = [f"{esc(o)}\n{'▓' * round(n / total * 10)}{'░' * (10 - round(n / total * 10))} {n}" for o, n in zip(p["opts"], counts)]
    state = "" if p["open"] else "\n🔒 <i>نظرسنجی بسته شد</i>"
    return f"📊 <b>{esc(p['q'])}</b>\n\n" + "\n".join(lines) + f"\n\nمجموع آرا: {sum(counts)}{state}"
def poll_kb(pid: int, opts: list, votes: dict) -> InlineKeyboardMarkup:
    counts = [0] * len(opts)
    for v in votes.values():
        if 0 <= v < len(counts):
            counts[v] += 1
    return kb([[btn(f"{o} ({n})", f"pvote:{pid}:{i}")] for i, (o, n) in enumerate(zip(opts, counts))])
async def cmd_poll(c: Ctx):
    if c.lv < 2:
        await c.reply(Texts.NO_ACCESS)
        return
    parts = [p.strip() for p in c.args.split("|") if p.strip()]
    if len(parts) < 3 or len(parts) > 9:
        await c.reply("مثال: /poll بهترین زمان؟ | صبح | عصر | شب")
        return
    q, opts = parts[0], parts[1:]
    pid = await c.db.create_poll(c.cid, q, opts)
    p = await c.db.get_poll(pid)
    m = await c.message.answer(poll_text(p), reply_markup=poll_kb(pid, opts, {}))
    await c.db.set_poll_msg(pid, m.message_id)
async def cmd_closepoll(c: Ctx):
    if c.lv < 2:
        await c.reply(Texts.NO_ACCESS)
        return
    pid = await c.db.last_open_poll(c.cid)
    if not pid:
        await c.reply("نظرسنجی بازی وجود ندارد.")
        return
    await c.db.close_poll(pid)
    p = await c.db.get_poll(pid)
    try:
        await c.bot.edit_message_text(poll_text(p), chat_id=c.cid, message_id=p["msg_id"])
    except TelegramAPIError:
        pass
    await c.reply("🔒 نظرسنجی بسته شد.")
async def cmd_lottery(c: Ctx):
    if c.lv < 2:
        await c.reply(Texts.NO_ACCESS)
        return
    n = 1
    if c.args.split() and c.args.split()[0].isdigit():
        n = max(1, min(5, int(c.args.split()[0])))
    pool = [p for p in await c.db.lottery_pool(c.cid) if p[0] != c.bot.id]
    if not pool:
        await c.reply("هنوز شرکت‌کننده‌ای نیست.")
        return
    winners = random.sample(pool, min(n, len(pool)))
    await c.message.answer(Texts.LOTTERY_OK.format(name="، ".join(mention(w[0], w[1]) for w in winners)))
# ----------------------------------------------------------
# 7.6 سیستم پشتیبانی (پیوی بات ← سوپرمالک)
# ----------------------------------------------------------
SUPPORT_WAIT: dict = {}
SUPPORT_LAST: dict = {}
SUPPORT_TTL = 600
async def cmd_support(c: Ctx):
    if c.message.chat.type != "private":
        await c.reply("برای پشتیبانی، پی‌وی بات را باز کن و /support بفرست.")
        return
    if c.uid == config.super_owner_id:
        await c.message.answer("شما سوپرمالک هستید؛ روی پیام کاربران ریپلای کنید تا جواب برایشان برود.")
        return
    SUPPORT_WAIT[c.uid] = time.time()
    await c.message.answer("🆘 <b>پشتیبانی نو آرا</b>\nپیامت را بنویس (متن، عکس، فایل… هرچه لازم است)؛ مستقیم به مدیریت می‌رسد.\nبرای خروج: /cancel")
async def support_flow(message: Message, bot: Bot, db: Database) -> bool:
    uid = message.from_user.id
    if uid == config.super_owner_id:
        rep = message.reply_to_message
        target = await db.support_target(rep.message_id) if rep else None
        if not target:
            return False
        try:
            await bot.send_message(target, "💬 <b>پاسخ پشتیبانی:</b>")
            await bot.copy_message(target, message.chat.id, message.message_id)
            await message.reply("✅ برای کاربر ارسال شد.")
        except TelegramAPIError:
            await message.reply("⚠️ ارسال نشد؛ شاید کاربر بات را بلاک کرده.")
        return True
    t0 = SUPPORT_WAIT.get(uid)
    if not t0 or time.time() - t0 > SUPPORT_TTL:
        SUPPORT_WAIT.pop(uid, None)
        return False
    t = message.text or ""
    if t.lower() in ("/cancel", "/لغو"):
        SUPPORT_WAIT.pop(uid, None)
        await message.answer("❎ از پشتیبانی خارج شدی.")
        return True
    if t.startswith(("/", "!")):
        return False
    if time.time() - SUPPORT_LAST.get(uid, 0) < 10:
        await message.answer("⏳ چند ثانیه صبر کن و دوباره بفرست.")
        return True
    SUPPORT_LAST[uid] = SUPPORT_WAIT[uid] = time.time()
    u = message.from_user
    header = (f"🆘 <b>پیام پشتیبانی</b>\n👤 {mention(u.id, u.full_name)}\n🆔 <code>{u.id}</code>"
              + (f"\n🔗 @{esc(u.username)}" if u.username else "")
              + "\n↩️ روی همین پیام یا پیام بعدی ریپلای کن تا برای کاربر برود.")
    try:
        h = await bot.send_message(config.super_owner_id, header)
        cp = await bot.copy_message(config.super_owner_id, message.chat.id, message.message_id)
        await db.add_support(h.message_id, u.id)
        await db.add_support(cp.message_id, u.id)
        await message.answer("✅ پیامت به مدیریت رسید؛ جواب همین‌جا می‌آید.")
    except TelegramAPIError:
        await message.answer("⚠️ الان نتوانستم پیام را برسانم؛ کمی بعد دوباره امتحان کن.")
    return True
# ----------------------------------------------------------
# 7.7 منشن گروهی با دکمه
# ----------------------------------------------------------
MENTION_MIN = {"adm": 1, "u50": 2, "u300": 4}
MENTION_LABEL = {"adm": "• تگ کردن کاربران مقام دار", "u50": "• تگ کردن 50 کاربر بدون مقام", "u300": "• تگ کردن 300 کاربر گروه"}
MENTION_MAXREP = {"adm": 5, "u50": 3, "u300": 1}
MENTION_PANEL: dict = {}
MENTION_JOBS: dict = {}
MENTION_LAST: dict = {}
def is_vip(uid: int) -> bool:
    return bool(config.vip_user_id) and uid == config.vip_user_id
async def mention_lv(bot: Bot, roles: Roles, cid: int, uid: int) -> int:
    lv = (await roles.get(bot, cid, uid))[1]
    if is_vip(uid) and lv >= 1:
        lv = max(lv, 4)
    return lv
async def cmd_mention(c: Ctx):
    if c.message.chat.type not in GROUP_TYPES:
        await c.reply(Texts.PV_ONLY_GROUP)
        return
    lv = await mention_lv(c.bot, c.roles, c.cid, c.uid)
    if lv < 1:
        await c.reply(Texts.NO_ACCESS)
        return
    rows = [[btn(MENTION_LABEL[k], f"mn:{c.cid}:{k}")] for k in ("adm", "u50", "u300") if lv >= MENTION_MIN[k]]
    rows.append([btn("• بستن", "close")])
    m = await c.reply("• حالت تگ کردن را انتخاب کنید :", reply_markup=kb(rows))
    MENTION_PANEL[(c.cid, m.message_id)] = c.uid
async def collect_targets(bot: Bot, db: Database, cid: int, mode: str):
    admins = {}
    try:
        for a in await bot.get_chat_administrators(cid):
            if not a.user.is_bot:
                admins[a.user.id] = a.user.full_name
    except TelegramAPIError:
        pass
    for u, _ in await db.get_admins(cid):
        if int(u) not in admins:
            admins[int(u)] = await db.get_name(int(u))
    if mode == "adm":
        return list(admins.items())
    seen = [(int(u), n) for u, n in await db.recent_members(cid, 400) if int(u) != bot.id]
    if mode == "u50":
        return [(u, n) for u, n in seen if u not in admins][:50]
    return seen[:300]
async def run_mention(bot: Bot, cid: int, targets: list, reps: int, panel_id: int):
    stopped = False
    try:
        for r in range(reps):
            for i in range(0, len(targets), 5):
                line = " ".join(mention(u, (n or "کاربر")[:14]) for u, n in targets[i:i + 5])
                for attempt in (1, 2):
                    try:
                        await bot.send_message(cid, f"📣 {line}")
                        break
                    except TelegramRetryAfter as e:
                        await asyncio.sleep(e.retry_after + 1)
                    except TelegramAPIError:
                        break
                await asyncio.sleep(1.5)
            if r < reps - 1:
                await asyncio.sleep(4)
    except asyncio.CancelledError:
        stopped = True
    finally:
        MENTION_JOBS.pop(cid, None)
        try:
            await bot.edit_message_text("⛔ منشن متوقف شد." if stopped else f"✅ منشن {len(targets)} نفر تمام شد.", chat_id=cid, message_id=panel_id)
        except Exception:
            pass
COMMANDS = {"start": cmd_start, "help": cmd_help, "settings": cmd_settings, "groups": cmd_groups, "id": cmd_id, "rules": cmd_rules, "report": cmd_report, "stats": cmd_stats, "top": cmd_top, "admins": cmd_admins, "ban": cmd_ban, "unban": cmd_unban, "mute": cmd_mute, "unmute": cmd_unmute, "kick": cmd_kick, "warn": cmd_warn, "unwarn": cmd_unwarn, "del": cmd_del, "pin": cmd_pin, "unpin": cmd_unpin, "timed": cmd_timed, "setowner": cmd_setowner, "addadmin": cmd_addadmin, "deladmin": cmd_deladmin, "setrules": cmd_setrules, "setwelcome": cmd_setwelcome, "addkey": cmd_addkey, "delkey": cmd_delkey, "keys": cmd_keys, "addfilter": cmd_addfilter, "delfilter": cmd_delfilter, "filters": cmd_filters, "addwhite": cmd_addwhite, "delwhite": cmd_delwhite, "whites": cmd_whites, "set": cmd_set, "setnight": cmd_setnight, "backup": cmd_backup, "poll": cmd_poll, "closepoll": cmd_closepoll, "lottery": cmd_lottery, "manage": cmd_manage, "tag": cmd_tag, "untag": cmd_untag, "trust": cmd_trust, "dashboard": cmd_dashboard, "suggest": cmd_suggest, "support": cmd_support, "mention": cmd_mention}
PV_OK = {"start", "help", "groups", "backup", "id", "settings", "support"}
# ==========================================================
# 8. کالبک‌ها
# ==========================================================
class SafeRequestMiddleware(BaseRequestMiddleware):
    """فلود‌کنترل تلگرام را یک‌بار با صبر مجدد امتحان می‌کند و خطای کوئری قدیمی کالبک را بی‌صدا رد می‌کند."""
    async def __call__(self, make_request, bot, method):
        for attempt in (1, 2):
            try:
                return await make_request(bot, method)
            except TelegramRetryAfter as e:
                if attempt == 2 or e.retry_after > 15:
                    raise
                await asyncio.sleep(e.retry_after + 0.5)
            except TelegramBadRequest as e:
                if type(method).__name__ == "AnswerCallbackQuery" and (
                    "query is too old" in str(e) or "query id is invalid" in str(e).lower()
                ):
                    return True
                raise
async def safe_edit(call: CallbackQuery, text: str, markup):
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except TelegramRetryAfter as e:
        logging.warning(f"edit flood: retry after {e.retry_after}s")
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            logging.warning(f"edit error: {e}")
async def need_owner(call: CallbackQuery, bot: Bot, roles: Roles, cid: int) -> bool:
    lv = (await roles.get(bot, cid, call.from_user.id))[1]
    if lv < 4:
        await call.answer("فقط مالک گپ و سوپرمالک", show_alert=True)
        return False
    return True
@router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()
@router.callback_query(F.data == "close")
async def cb_close(call: CallbackQuery):
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()
# --- پشتیبانی ---
@router.callback_query(F.data == "sup:start")
async def cb_support(call: CallbackQuery):
    if call.message.chat.type != "private" or call.from_user.id == config.super_owner_id:
        await call.answer()
        return
    SUPPORT_WAIT[call.from_user.id] = time.time()
    await call.message.answer("🆘 پیامت را بنویس؛ مستقیم به مدیریت می‌رسد. (خروج: /cancel)")
    await call.answer()
# --- منشن گروهی ---
@router.callback_query(F.data.regexp(r"^m[nc]:"))
async def cb_mention(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    p = call.data.split(":")
    try:
        cid, mode = int(p[1]), p[2]
        reps = int(p[3]) if p[0] == "mc" else None
    except (ValueError, IndexError):
        await call.answer()
        return
    if mode not in MENTION_MIN:
        await call.answer()
        return
    uid = call.from_user.id
    lv = await mention_lv(bot, roles, cid, uid)
    asker = MENTION_PANEL.get((cid, call.message.message_id))
    if lv < MENTION_MIN[mode] or (lv < 4 and asker != uid):
        await call.answer("این گزینه برای تو فعال نیست.", show_alert=True)
        return
    if reps is None:
        if (lv >= 4 or is_vip(uid)) and MENTION_MAXREP[mode] > 0:
            opts = [n for n in (1, 2, 3, 5) if n <= MENTION_MAXREP[mode]]
            rows = [[btn(f"{n} بار", f"mc:{cid}:{mode}:{n}") for n in opts]]
            rows.append([btn("✏️ تعداد دلخواه (تایپ کن)", f"mcustom:{cid}:{mode}")])
            rows.append([btn("• بستن", "close")])
            await safe_edit(call, "🔁 چند دور منشن شود؟", kb(rows))
            await call.answer()
            return
        reps = 1
    reps = max(1, min(reps, MENTION_MAXREP[mode]))
    t = MENTION_JOBS.get(cid)
    if t and not t.done():
        await call.answer("یک منشن در حال اجراست.", show_alert=True)
        return
    cd = 60 if lv >= 4 else 180
    if time.time() - MENTION_LAST.get(cid, 0) < cd:
        await call.answer(f"چند لحظه صبر کن؛ فاصله‌ی دو منشن {cd} ثانیه است.", show_alert=True)
        return
    targets = await collect_targets(bot, db, cid, mode)
    if not targets:
        await call.answer("کسی برای منشن پیدا نشد.", show_alert=True)
        return
    MENTION_LAST[cid] = time.time()
    await db.add_log(cid, uid, 0, f"mention:{mode}", f"x{reps}")
    await safe_edit(call, f"📣 در حال منشن {len(targets)} نفر × {reps} دور…", kb([[btn("⛔ توقف", f"mx:{cid}")]]))
    MENTION_JOBS[cid] = spawn(run_mention(bot, cid, targets, reps, call.message.message_id))
    await call.answer("شروع شد ✅")
@router.callback_query(F.data.startswith("mcustom:"))
async def cb_mention_custom(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    try:
        _, cid_s, mode = call.data.split(":")
        cid = int(cid_s)
    except (ValueError, IndexError):
        await call.answer()
        return
    if mode not in MENTION_MIN:
        await call.answer()
        return
    uid = call.from_user.id
    lv = await mention_lv(bot, roles, cid, uid)
    asker = MENTION_PANEL.get((cid, call.message.message_id))
    if lv < MENTION_MIN[mode] or (lv < 4 and asker != uid):
        await call.answer("این گزینه برای تو فعال نیست.", show_alert=True)
        return
    PENDING_INPUT[(call.message.chat.id, uid)] = (
        cid,
        f"mention_reps:{mode}:{call.message.message_id}",
        time.time(),
    )
    await safe_edit(
        call,
        f"✏️ <b>تعداد دور منشن</b>\nحالت: <code>{MENTION_LABEL[mode]}</code>\n"
        f"یک عدد بین <b>1</b> تا <b>{MENTION_MAXREP[mode]}</b> بفرست.\n"
        f"(انصراف: <code>/cancel</code>)",
        kb([[btn("• بستن", "close")]]),
    )
    await call.answer("عدد رو بفرست ✍️")
@router.callback_query(F.data.startswith("mx:"))
async def cb_mention_stop(call: CallbackQuery, bot: Bot, roles: Roles):
    try:
        cid = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer()
        return
    if await mention_lv(bot, roles, cid, call.from_user.id) < 1:
        await call.answer("فقط مدیران", show_alert=True)
        return
    t = MENTION_JOBS.get(cid)
    if t and not t.done():
        t.cancel()
    await call.answer("متوقف شد")
@router.callback_query(F.data == "g:list")
async def cb_groups(call: CallbackQuery, db: Database):
    uid = call.from_user.id
    groups = await (db.get_all_groups() if uid == config.super_owner_id else db.groups_of(uid))
    groups = [(g[0], g[1]) for g in groups]
    if groups:
        text = "📂 <b>گپ‌های من</b>\nیک گپ را برای مدیریت انتخاب کن:"
    else:
        text = ("هنوز گپی ثبت نشده.\nاز صفحه‌ی اصلی دکمه‌ی «➕ افزودن بات به گپ من» را بزن؛ " "هر کس بات را به گروهی اضافه کند، مالک آن گپ در بات ثبت می‌شود.")
    await safe_edit(call, text, groups_kb(groups))
    await call.answer()
@router.callback_query(F.data == "g:home")
async def cb_home(call: CallbackQuery, bot: Bot, db: Database):
    PENDING_INPUT.pop((call.message.chat.id, call.from_user.id), None)
    text, markup = await start_view(bot, db, call.from_user.id)
    await safe_edit(call, text, markup)
    await call.answer()
@router.callback_query(F.data.startswith("h:"))
async def cb_help(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    sec = call.data.split(":", 1)[1]
    lv = await help_level(bot, db, roles, call.message.chat, call.from_user.id)
    if sec in HELP_SECTIONS:
        label, need, body = HELP_SECTIONS[sec]
        if lv < need:
            await call.answer("این بخش مخصوص مدیران است.", show_alert=True)
            return
        await safe_edit(call, f"<b>{label}</b>\n{body}", help_kb(lv, sec))
    else:
        await safe_edit(call, help_main_text(lv), help_kb(lv))
    await call.answer()
@router.callback_query(F.data.startswith("q:"))
async def cb_info(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    try:
        _, cid, topic = call.data.split(":", 2)
        cid = int(cid)
    except Exception:
        await call.answer()
        return
    if call.message.chat.type != "private":
        lv = (await roles.get(bot, cid, call.from_user.id))[1]
        if lv < 4:
            await call.answer("فقط مالک", show_alert=True)
            return
    await call.answer(EXPLAINS.get(topic, "توضیحی ثبت نشده."), show_alert=True)
@router.callback_query(F.data.startswith("preset:"))
async def cb_preset(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    try:
        _, cid, name = call.data.split(":")
        cid = int(cid)
    except Exception:
        await call.answer()
        return
    if not await need_owner(call, bot, roles, cid):
        return
    if name not in PRESETS:
        await call.answer()
        return
    for k, v in PRESETS[name].items():
        await db.set_setting(cid, k, v)
    await db.add_log(cid, call.from_user.id, 0, "preset:" + name, "")
    text, markup = await render_panel(db, cid, "antispam", call.message.chat.type == "private")
    await safe_edit(call, text, markup)
    await call.answer("پیش‌تنظیم اعمال شد ✅")
@router.callback_query(F.data.startswith("undo:"))
async def cb_undo(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    try:
        cid = int(call.data.split(":")[1])
    except Exception:
        await call.answer()
        return
    if not await need_owner(call, bot, roles, cid):
        return
    if cid not in LAST_CHANGE:
        await call.answer("چیزی برای برگرداندن نیست.", show_alert=True)
        return
    k, old = LAST_CHANGE.pop(cid)
    await db.set_setting(cid, k, old)
    text, markup = await render_panel(db, cid, SECTION_OF.get(k, "settings"), call.message.chat.type == "private")
    await safe_edit(call, text, markup)
    await call.answer("برگردانده شد ↩")
@router.callback_query(F.data.startswith("sug:"))
async def cb_sug(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    try:
        _, cid, key, val = call.data.split(":", 3)
        cid = int(cid)
    except Exception:
        await call.answer()
        return
    if not await need_owner(call, bot, roles, cid):
        return
    try:
        v: object = int(val) if val.lstrip("-").isdigit() else val
    except Exception:
        v = val
    old = (await db.get_settings(cid)).get(key)
    remember(cid, key, old)
    await db.set_setting(cid, key, v)
    await db.add_log(cid, call.from_user.id, 0, "suggest_apply:" + key, str(v))
    text, markup = await render_panel(db, cid, "suggest", call.message.chat.type == "private")
    await safe_edit(call, text, markup)
    await call.answer("اعمال شد ✅")
@router.callback_query(F.data.startswith("pg:"))
async def cb_pg(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    try:
        _, cid, sec, page = call.data.split(":")
        cid, page = int(cid), int(page)
    except Exception:
        await call.answer()
        return
    if not await need_owner(call, bot, roles, cid):
        return
    text, markup = await render_panel(db, cid, sec, call.message.chat.type == "private", page=page)
    await safe_edit(call, text, markup)
    await call.answer()
@router.callback_query(F.data.startswith("cf:"))
async def cb_confirm(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    try:
        _, cid, tid, act = call.data.split(":")
        cid, tid = int(cid), int(tid)
    except Exception:
        await call.answer()
        return
    if not await need_owner(call, bot, roles, cid):
        return
    pv = call.message.chat.type == "private"
    if act in ("ban", "kick"):
        await safe_edit(call, f"⚠️ مطمئنی <code>{tid}</code> را <b>{act}</b> کنم؟", kb([[btn("✅ بله", f"cfgo:{cid}:{tid}:{act}"), btn("◀️ نه", f"u:{cid}:{tid}:m")]]))
        await call.answer()
        return
    await call.answer()
@router.callback_query(F.data.startswith("cfgo:"))
async def cb_confirm_go(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    try:
        _, cid, tid, act = call.data.split(":")
        cid, tid = int(cid), int(tid)
    except Exception:
        await call.answer()
        return
    if not await need_owner(call, bot, roles, cid):
        return
    try:
        if not await bot_can(bot, cid):
            await call.answer(Texts.NO_BOT_RIGHTS, show_alert=True)
            return
        if act == "ban":
            await bot.ban_chat_member(cid, tid)
        elif act == "kick":
            await bot.ban_chat_member(cid, tid)
            await bot.unban_chat_member(cid, tid, only_if_banned=True)
        await db.add_log(cid, call.from_user.id, tid, act, "تأیید پنل")
        text, markup = await render_user_panel(bot, db, roles, cid, tid, call.message.chat.type == "private")
        await safe_edit(call, text, markup)
        await call.answer("انجام شد ✅")
    except TelegramAPIError as e:
        await call.answer(tg_err(e), show_alert=True)
@router.callback_query(F.data.startswith("u:"))
async def cb_user(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    parts = call.data.split(":")
    try:
        cid, tid, act = int(parts[1]), int(parts[2]), parts[3]
        arg = parts[4] if len(parts) > 4 else ""
    except (ValueError, IndexError):
        await call.answer()
        return
    uid = call.from_user.id
    lv = (await roles.get(bot, cid, uid))[1]
    if lv < 4:
        await call.answer("فقط مالک گپ و سوپرمالک", show_alert=True)
        return
    pv = call.message.chat.type == "private"
    async def show(sub: str = "main"):
        text, markup = await render_user_panel(bot, db, roles, cid, tid, pv, sub)
        await safe_edit(call, text, markup)
    if act in ("m", "pm"):
        await show("pm" if act == "pm" else "main")
        await call.answer()
        return
    if act == "tag":
        PENDING_INPUT[(call.message.chat.id, uid)] = (cid, "tag:" + str(tid), time.time())
        await call.message.answer("✍️ متن تگ را بفرست (۰ تا ۱۶ حرف، بدون ایموجی). خالی بفرست یعنی حذف. (انصراف: /cancel)")
        await call.answer("منتظر تگ هستم ✍️")
        return
    if act == "trust":
        try:
            tr = await db.get_trust(cid, tid)
            await call.answer(f"اعتماد {tr['score']} ({tr['level_fa']})", show_alert=True)
        except Exception:
            await call.answer()
        return
    if tid in (uid, bot.id):
        await call.answer("روی خودت یا بات نمی‌شود.", show_alert=True)
        return
    trole, tlv, _ = await roles.get(bot, cid, tid)
    if not can_punish(lv, tlv):
        await call.answer("روی هم‌سطح یا بالاتر از خودت نمی‌شود.", show_alert=True)
        return
    try:
        if act == "r":
            if arg == "user":
                await db.del_admin(cid, tid)
            elif arg in dict(ROLE_PICK):
                await db.set_admin(cid, tid, arg, uid)
            else:
                await call.answer()
                return
            roles.invalidate(cid, tid)
            await db.add_log(cid, uid, tid, f"role:{arg}", "پنل")
            await show()
            await call.answer("نقش به‌روز شد ✅")
        elif act == "a":
            if arg == "warn":
                cnt, mx, punished, ok = await apply_warn(bot, db, cid, tid, uid, "پنل")
                msg = f"اخطار {cnt} از {mx}" + (" — مجازات اعمال شد" if punished and ok else "")
            elif arg == "unwarn":
                n = await db.dec_warn(cid, tid)
                await db.add_log(cid, uid, tid, "unwarn", "پنل")
                msg = f"اخطار باقی‌مانده: {n}"
            elif arg == "untag":
                ok, emsg = await set_member_tag(bot, cid, tid, "")
                if ok:
                    await db.set_member_tag_db(cid, tid, "")
                    msg = "تگ حذف شد 🧹"
                else:
                    await call.answer(emsg, show_alert=True)
                    return
            else:
                if not await bot_can(bot, cid):
                    await call.answer(Texts.NO_BOT_RIGHTS, show_alert=True)
                    return
                if arg == "mute":
                    await bot.restrict_chat_member(cid, tid, permissions=ChatPermissions(can_send_messages=False), until_date=until_from_seconds(3600))
                    msg = "🔇 میوت ۱ ساعته شد"
                elif arg == "unmute":
                    await bot.restrict_chat_member(cid, tid, permissions=await open_perms(bot, cid))
                    msg = "🔊 بی‌صدایی برداشته شد"
                elif arg == "unban":
                    await bot.unban_chat_member(cid, tid, only_if_banned=True)
                    msg = "✅ رفع مسدودیت شد"
                else:
                    await call.answer()
                    return
                await db.add_log(cid, uid, tid, arg, "پنل")
            await show()
            await call.answer(msg)
        elif act in ("t", "p"):
            m = await bot.get_chat_member(cid, tid)
            if m.status == ChatMemberStatus.CREATOR:
                await call.answer("سازنده‌ی گروه را نمی‌شود تغییر داد.", show_alert=True)
                return
            br = await _bot_rights(bot, cid)
            if not br.get("can_promote_members"):
                await call.answer("بات «افزودن ادمین» ندارد؛ در تنظیمات تلگرام به بات بده.", show_alert=True)
                return
            cur = _cur_rights(m)
            if act == "t":
                key = TG_PERMS[int(arg)][0]
                want = not cur[key]
                if want and not br.get(key):
                    await call.answer("خود بات این دسترسی را ندارد؛ اول به بات بده.", show_alert=True)
                    return
                cur[key] = want
                rights = cur
            else:
                if arg == "none":
                    rights = {k: False for k, _ in TG_PERMS}
                else:
                    wanted = BASIC_PERMS if arg == "basic" else {k for k, _ in TG_PERMS}
                    rights = {k: (k in wanted and bool(br.get(k))) for k, _ in TG_PERMS}
            await _promote(bot, cid, tid, rights)
            if act == "p" and arg != "none" and trole == "user":
                await db.set_admin(cid, tid, "admin", uid)
                roles.invalidate(cid, tid)
            await db.add_log(cid, uid, tid, f"perms:{act}{arg}", "پنل")
            await show("pm")
            await call.answer("دسترسی به‌روز شد ✅")
        else:
            await call.answer()
    except (TelegramAPIError, ValueError, IndexError) as e:
        logging.warning(f"user panel error: {e}")
        await call.answer("⚠️ ناموفق. فقط عضو عادی یا ادمینی که خود بات ارتقا داده قابل تغییر است و بات باید «افزودن ادمین» داشته باشد.", show_alert=True)
@router.callback_query(F.data.startswith("p:"))
async def cb_panel(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    try:
        _, cid, section = call.data.split(":")
        cid = int(cid)
    except ValueError:
        await call.answer()
        return
    if not await need_owner(call, bot, roles, cid):
        return
    PENDING_INPUT.pop((call.message.chat.id, call.from_user.id), None)
    text, markup = await render_panel(db, cid, section, call.message.chat.type == "private")
    await safe_edit(call, text, markup)
    await call.answer()
@router.callback_query(F.data.startswith("t:"))
async def cb_toggle(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    parts = call.data.split(":")
    try:
        cid, key = int(parts[1]), parts[2]
    except (ValueError, IndexError):
        await call.answer()
        return
    if key not in TOGGLE_KEYS or not await need_owner(call, bot, roles, cid):
        await call.answer()
        return
    s = await db.get_settings(cid)
    remember(cid, key, s.get(key))
    await db.set_setting(cid, key, 0 if s.get(key) else 1)
    section = parts[3] if len(parts) > 3 else SECTION_OF.get(key, "settings")
    text, markup = await render_panel(db, cid, section, call.message.chat.type == "private")
    await safe_edit(call, text, markup)
    await call.answer("ذخیره شد ✅")
@router.callback_query(F.data.startswith("c:"))
async def cb_cycle(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    _, cid, key = call.data.split(":")
    cid = int(cid)
    if key not in CYCLES or not await need_owner(call, bot, roles, cid):
        await call.answer()
        return
    section, order = CYCLES[key]
    s = await db.get_settings(cid)
    cur = s.get(key)
    nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else order[0]
    remember(cid, key, cur)
    await db.set_setting(cid, key, nxt)
    text, markup = await render_panel(db, cid, section, call.message.chat.type == "private")
    await safe_edit(call, text, markup)
    await call.answer("به‌روزرسانی شد ✅")
@router.callback_query(F.data.startswith("n:"))
async def cb_numeric(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    _, cid, key, delta = call.data.split(":")
    cid = int(cid)
    if key not in NUMERIC or not await need_owner(call, bot, roles, cid):
        await call.answer()
        return
    lo, hi, _ = NUMERIC[key]
    s = await db.get_settings(cid)
    old = int(s.get(key, lo))
    remember(cid, key, old)
    v = max(lo, min(hi, old + int(delta)))
    await db.set_setting(cid, key, v)
    text, markup = await render_panel(db, cid, "settings", call.message.chat.type == "private")
    await safe_edit(call, text, markup)
    await call.answer(f"{v}")
@router.callback_query(F.data.startswith("bw:"))
async def cb_badwords(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    try:
        _, cid, act = call.data.split(":")
        cid = int(cid)
    except ValueError:
        await call.answer()
        return
    if not await need_owner(call, bot, roles, cid):
        return
    key = (call.message.chat.id, call.from_user.id)
    if act in ("add", "del"):
        PENDING_INPUT[key] = (cid, act, time.time())
        if act == "add":
            msg = ("✍️ <b>افزودن کلمه‌ی ممنوعه</b>\nکلمه یا عبارت را همین‌جا بفرست.\n" "چند مورد را با «،» یا خط جدید جدا کن.\n(انصراف: /cancel)")
        else:
            msg = ("✍️ <b>حذف کلمه از لیست اختصاصی</b>\nکلمه(ها) را بفرست؛ با «،» یا خط جدید جدا کن.\n(انصراف: /cancel)")
        await call.message.answer(msg)
        await call.answer("منتظر پیام تو هستم ✍️")
    elif act == "pick":
        PENDING_INPUT[key] = (cid, "pick", time.time())
        await call.message.answer("✍️ آیدی عددی یا یوزرنیم (@...) عضو را بفرست تا پنل نقش و دسترسی‌اش باز شود.\n(انصراف: /cancel)")
        await call.answer("منتظر پیام تو هستم ✍️")
    elif act == "search":
        PENDING_INPUT[key] = (cid, "search_members", time.time())
        await call.message.answer("🔎 نام یا بخشی از نام مدیر را بفرست.\n(انصراف: /cancel)")
        await call.answer()
    elif act in ("tagtop", "tagtrusted", "tagwatch"):
        mp = {"tagtop": "tag_template_top", "tagtrusted": "tag_template_trusted", "tagwatch": "tag_template_watch"}[act]
        PENDING_INPUT[key] = (cid, "tagtpl:" + mp, time.time())
        await call.message.answer(f"✍️ قالب جدید <code>{mp}</code> را بفرست (۰ تا ۱۶ حرف، بدون ایموجی، خالی=پاک).\n(انصراف: /cancel)")
        await call.answer()
    elif act == "sync":
        try:
            tg_admins = await bot.get_chat_administrators(cid)
        except TelegramAPIError:
            await call.answer("نتوانستم لیست ادمین‌ها را بگیرم؛ بات باید ادمین باشد.", show_alert=True)
            return
        n = 0
        for a in tg_admins:
            u = a.user
            if u.is_bot or a.status == ChatMemberStatus.CREATOR:
                continue
            await db.touch_user(u)
            if not await db.get_admin_role(cid, u.id):
                await db.set_admin(cid, u.id, "admin", call.from_user.id)
                n += 1
            roles.invalidate(cid, u.id)
        text, markup = await render_panel(db, cid, "members", call.message.chat.type == "private")
        await safe_edit(call, text, markup)
        await call.answer(f"{n} ادمین ثبت شد ✅")
    elif act == "list":
        custom = await db.get_filters(cid)
        body = "، ".join(esc(w) for w in custom) or "خالی"
        for i in range(0, len(body), 3500):
            await call.message.answer(("🚫 <b>لیست اختصاصی شما:</b>\n" if i == 0 else "") + body[i:i + 3500])
        await call.answer()
    elif act == "clear":
        n = len(await db.get_filters(cid))
        await safe_edit(call, f"⚠️ مطمئنی می‌خواهی کل لیست اختصاصی ({n} کلمه) پاک شود؟\n(لیست آماده‌ی ربات پاک نمی‌شود)", kb([[btn("✅ بله، پاک کن", f"bw:{cid}:clear2"), btn("◀️ نه، برگرد", f"p:{cid}:badwords")]]))
        await call.answer()
    elif act == "clear2":
        await db.clear_filters(cid)
        text, markup = await render_panel(db, cid, "badwords", call.message.chat.type == "private")
        await safe_edit(call, text, markup)
        await call.answer("لیست پاک شد 🧹")
    else:
        await call.answer()
@router.callback_query(F.data.startswith("x:"))
async def cb_show(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    _, cid, what = call.data.split(":")
    cid = int(cid)
    if not await need_owner(call, bot, roles, cid):
        return
    if what == "rules":
        s = await db.get_settings(cid)
        await call.message.answer(Texts.RULES_OK.format(rules=esc(s.get("rules_text") or Texts.RULES_DEF)))
    elif what == "stats":
        rows = await db.top(cid, 7, 8)
        data = {esc(r[1])[:10]: int(r[2]) for r in rows}
        await call.message.answer(f"📊 <b>آمار ۷ روز اخیر</b>\n<pre>{text_chart(data)}</pre>")
    elif what == "top":
        await call.message.answer(await top_text(db, cid))
    await call.answer()
@router.callback_query(F.data.startswith("warn_plus:"))
async def cb_warn_plus(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    cid = call.message.chat.id
    lv = (await roles.get(bot, cid, call.from_user.id))[1]
    if lv < 1:
        await call.answer("فقط مدیران", show_alert=True)
        return
    tid = int(call.data.split(":")[1])
    if not can_punish(lv, (await roles.get(bot, cid, tid))[1]):
        await call.answer("روی هم‌سطح/بالاتر نمی‌شود", show_alert=True)
        return
    cnt, mx, punished, ok = await apply_warn(bot, db, cid, tid, call.from_user.id, "دکمه")
    await call.answer(f"اخطار {cnt} از {mx} ثبت شد")
    if punished:
        await call.message.answer(Texts.WARN_PUNISH if ok else Texts.NO_BOT_RIGHTS)
@router.callback_query(F.data.startswith("warn_minus:"))
async def cb_warn_minus(call: CallbackQuery, bot: Bot, db: Database, roles: Roles):
    cid = call.message.chat.id
    if (await roles.get(bot, cid, call.from_user.id))[1] < 1:
        await call.answer("فقط مدیران", show_alert=True)
        return
    tid = int(call.data.split(":")[1])
    n = await db.dec_warn(cid, tid)
    await db.add_log(cid, call.from_user.id, tid, "unwarn", "دکمه")
    await call.answer(f"باقی‌مانده: {n}")
@router.callback_query(F.data.startswith("pvote:"))
async def cb_pvote(call: CallbackQuery, db: Database):
    _, pid, idx = call.data.split(":")
    p = await db.vote_poll(int(pid), call.from_user.id, int(idx))
    if not p:
        await call.answer("نظرسنجی بسته است.")
        return
    await safe_edit(call, poll_text(p), poll_kb(int(pid), p["opts"], p["votes"]))
    await call.answer("رأیت ثبت شد ✅")
@router.callback_query(F.data == "rules:accept")
async def cb_rules_accept(call: CallbackQuery, db: Database):
    await db.add_log(call.message.chat.id, call.from_user.id, call.from_user.id, "rules_accept", "")
    await call.answer("ممنون که قوانین را پذیرفتی! 🌿", show_alert=True)
@router.callback_query(F.data == "rules:show")
async def cb_rules_show(call: CallbackQuery, db: Database):
    s = await db.get_settings(call.message.chat.id)
    r = s.get("rules_text") or Texts.RULES_DEF
    await call.answer((r[:190] + "…\n(متن کامل: /rules)") if len(r) > 190 else r, show_alert=True)
@router.callback_query(F.data.startswith("verify:"))
async def cb_verify(call: CallbackQuery, bot: Bot, db: Database):
    uid = int(call.data.split(":")[1])
    cid = call.message.chat.id
    if call.from_user.id != uid:
        await call.answer("این دکمه برای تو نیست!", show_alert=True)
        return
    PENDING_VERIFY.pop((cid, uid), None)
    try:
        await bot.restrict_chat_member(cid, uid, permissions=await open_perms(bot, cid))
    except TelegramAPIError:
        pass
    await call.answer("تأیید شدی! خوش آمدی 🌸")
    try:
        await call.message.delete()
    except Exception:
        pass
    s = await db.get_settings(cid)
    if s.get("welcome_on"):
        await send_welcome(bot, db, call.message.chat, call.from_user, s)
# ==========================================================
# 9. رویدادهای گروه
# ==========================================================
async def send_welcome(bot: Bot, db: Database, chat, user, s: dict):
    tpl = esc(s.get("welcome_text") or Texts.WELCOME_DEF)
    txt = (tpl.replace("{mention}", mention(user.id, user.full_name)).replace("{name}", esc(user.full_name)).replace("{title}", esc(chat.title)))
    try:
        await bot.send_message(chat.id, txt, reply_markup=welcome_kb())
    except TelegramAPIError:
        pass
async def verify_timeout(bot: Bot, cid: int, uid: int, msg_id: int, wait: int = 60):
    await asyncio.sleep(wait)
    if PENDING_VERIFY.pop((cid, uid), None) is None:
        return
    try:
        await bot.ban_chat_member(cid, uid)
        await bot.unban_chat_member(cid, uid, only_if_banned=True)
    except TelegramAPIError:
        pass
    try:
        await bot.delete_message(cid, msg_id)
    except Exception:
        pass
@router.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated, bot: Bot, db: Database):
    if event.new_chat_member.user.id != bot.id or event.chat.type not in GROUP_TYPES:
        return
    st = event.new_chat_member.status
    if st in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
        await db.remove_group(event.chat.id)
        return
    await db.upsert_group(event.chat.id, event.chat.title or "گپ")
    if not await db.get_owner(event.chat.id):
        await db.set_owner(event.chat.id, event.from_user.id)
    if st != ChatMemberStatus.ADMINISTRATOR:
        try:
            await bot.send_message(event.chat.id, Texts.NO_BOT_RIGHTS)
        except Exception:
            pass
@router.chat_member()
async def on_chat_member(event: ChatMemberUpdated, roles: Roles):
    roles.invalidate(event.chat.id, event.new_chat_member.user.id)
@router.message(F.new_chat_members)
async def on_join(message: Message, bot: Bot, db: Database, role_level: int):
    cid = message.chat.id
    s = await db.get_settings(cid)
    if s.get("delete_service"):
        try:
            await message.delete()
        except Exception:
            pass
    for u in message.new_chat_members:
        if u.is_bot or u.id == config.super_owner_id:
            continue
        try:
            await db.ensure_member(cid, u.id)
        except Exception:
            pass
        invited_by_admin = role_level >= 1 and message.from_user and message.from_user.id != u.id
        if s.get("verify_join") and not invited_by_admin:
            try:
                await bot.restrict_chat_member(cid, u.id, permissions=ChatPermissions(can_send_messages=False), until_date=until_from_seconds(600))
                m = await bot.send_message(cid, Texts.VERIFY_TXT.format(mention=mention(u.id, u.full_name)), reply_markup=verify_kb(u.id))
                PENDING_VERIFY[(cid, u.id)] = m.message_id
                spawn(verify_timeout(bot, cid, u.id, m.message_id))
                continue
            except TelegramAPIError:
                pass
        if s.get("welcome_on"):
            await send_welcome(bot, db, message.chat, u, s)
@router.message(F.left_chat_member)
async def on_left(message: Message, bot: Bot, db: Database):
    s = await db.get_settings(message.chat.id)
    if s.get("delete_service"):
        try:
            await message.delete()
        except Exception:
            pass
        return
    if s.get("goodbye_on") and message.left_chat_member and not message.left_chat_member.is_bot:
        try:
            await bot.send_message(message.chat.id, Texts.GOODBYE_TXT.format(name=esc(message.left_chat_member.full_name)))
        except Exception:
            pass
# ==========================================================
# 10. ضداسپم و امنیت
# ==========================================================
async def kill(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
async def handle_badword(message: Message, bot: Bot, db: Database, s: dict, hit: str):
    cid, uid = message.chat.id, message.from_user.id
    await kill(message)
    try:
        await db.add_violation(cid, uid, "badword:" + str(hit)[:30])
    except Exception:
        pass
    if s.get("use_reaction"):
        await try_react(bot, cid, message.message_id, "🤬")
    act = s.get("badword_punish", "delete")
    m = mention(uid, message.from_user.full_name)
    await db.add_log(cid, bot.id, uid, "badword", act)
    if act == "warn":
        cnt, mx, punished, ok = await apply_warn(bot, db, cid, uid, bot.id, "فحش")
        if time.time() - BW_NOTE.get((cid, uid), 0) > 30:
            BW_NOTE[(cid, uid)] = time.time()
            await notice(bot, cid, f"🧼 {m} فحش ممنوعه! اخطار {cnt} از {mx} ثبت شد." + ("\n" + Texts.WARN_PUNISH if punished and ok else ""))
    elif act != "delete":
        ok = await do_punish(bot, cid, uid, act)
        if time.time() - BW_NOTE.get((cid, uid), 0) > 30:
            BW_NOTE[(cid, uid)] = time.time()
            await notice(bot, cid, f"🧼 {m} به‌خاطر فحش محدود شد." if ok else BAD_NOTES[0].format(m=m))
    else:
        if time.time() - BW_NOTE.get((cid, uid), 0) > 30:
            BW_NOTE[(cid, uid)] = time.time()
            await notice(bot, cid, random.choice(BAD_NOTES).format(m=m), 8)
async def guard(message: Message, bot: Bot, db: Database, role_level: int, tg_admin: bool) -> bool:
    if role_level >= 1 or tg_admin or not message.from_user:
        return False
    cid, uid = message.chat.id, message.from_user.id
    s = await db.get_settings(cid)
    whites = await db.get_whites(cid)
    wvals = {v for v, _ in whites}
    ids = {str(uid)} | ({str(message.sender_chat.id)} if message.sender_chat else set())
    if ids & wvals:
        return False
    txt = message.text or message.caption or ""
    trust = None
    if s.get("trust_enforce"):
        try:
            trust = await db.get_trust(cid, uid)
        except Exception:
            trust = None
    is_low = bool(trust and trust["level"] == "low")
    is_high = bool(trust and trust["level"] == "high")
    if s.get("night_lock") and in_night(now_tz().strftime("%H:%M"), s.get("night_start", "00:00"), s.get("night_end", "06:00")):
        await kill(message)
        if s.get("use_reaction"):
            await try_react(bot, cid, message.message_id, "🌙")
        if not s.get("night_silent") and time.time() - NIGHT_NOTE.get(cid, 0) > 600:
            NIGHT_NOTE[cid] = time.time()
            await notice(bot, cid, "🌙 گپ در ساعات شبانه قفل است؛ فردا می‌بینیمتان. 💤")
        return True
    forwarded = getattr(message, "forward_origin", None) or getattr(message, "forward_date", None)
    checks = [(s.get("anti_forward") and forwarded), (s.get("lock_sticker") and message.sticker), (s.get("lock_gif") and message.animation), (s.get("lock_photo") and message.photo), (s.get("lock_video") and (message.video or message.video_note)), (s.get("lock_voice") and message.voice), (s.get("lock_file") and message.document and not message.animation), (s.get("lock_music") and message.audio)]
    if is_low and (message.photo or message.video or message.document):
        await kill(message)
        try:
            await db.add_violation(cid, uid, "lowtrust-media")
        except Exception:
            pass
        if s.get("use_reaction"):
            await try_react(bot, cid, message.message_id, "⛔")
        return True
    if any(checks):
        await kill(message)
        try:
            await db.add_violation(cid, uid, "media")
        except Exception:
            pass
        if s.get("use_reaction"):
            await try_react(bot, cid, message.message_id, "⛔")
        return True
    if txt:
        if s.get("antilink") or is_low:
            domains = extract_domains(message)
            if domains:
                allowed = {v for v, t in whites if t == "domain"}
                if any(not any(d == w or d.endswith("." + w) for w in allowed) for d in domains):
                    await kill(message)
                    try:
                        await db.add_violation(cid, uid, "link")
                    except Exception:
                        pass
                    if s.get("use_reaction"):
                        await try_react(bot, cid, message.message_id, "🔗")
                    return True
        if s.get("anti_username") and USERNAME_RE.search(txt):
            await kill(message)
            if s.get("use_reaction"):
                await try_react(bot, cid, message.message_id, "⛔")
            return True
        if s.get("anti_mention") and count_mentions(message) >= 3:
            await kill(message)
            if s.get("use_reaction"):
                await try_react(bot, cid, message.message_id, "⛔")
            return True
        if s.get("lock_emoji") and not is_high:
            ents = message.entities or []
            n = len(EMOJI_RE.findall(txt)) + sum(1 for e in ents if e.type == "custom_emoji")
            if n >= 8:
                await kill(message)
                return True
        if s.get("antilong") and not is_high and len(txt) > int(s.get("antilong_max", 2000)):
            await kill(message)
            return True
        if s.get("antirepeat") and not is_high and REPEAT_RE.search(txt):
            await kill(message)
            return True
        if s.get("badword_filter"):
            custom = await db.get_filters(cid)
            hit = has_badword(txt, custom, bool(s.get("badword_builtin", 1)), bool(s.get("badword_mild", 1)))
            if hit:
                await handle_badword(message, bot, db, s, hit)
                return True
    if s.get("antiflood"):
        now = time.monotonic()
        dq = FLOOD[(cid, uid)]
        dq.append(now)
        win, mx = int(s.get("antiflood_sec", 10)), int(s.get("antiflood_max", 5))
        while dq and now - dq[0] > win:
            dq.popleft()
        if len(dq) > mx:
            dq.clear()
            await kill(message)
            try:
                await db.add_violation(cid, uid, "flood")
            except Exception:
                pass
            if s.get("use_reaction"):
                await try_react(bot, cid, message.message_id, "🚫")
            ok = await do_punish(bot, cid, uid, s.get("antiflood_punish", "mute:1h"))
            if ok:
                await db.add_log(cid, bot.id, uid, "flood", s.get("antiflood_punish", ""))
                if time.time() - BW_NOTE.get(("flood", cid, uid), 0) > 60:
                    BW_NOTE[("flood", cid, uid)] = time.time()
                    await notice(bot, cid, f"🚫 {mention(uid, message.from_user.full_name)} به‌خاطر ارسال پیام‌های پشت‌سرهم محدود شد.")
            return True
    return False
# ==========================================================
# 11. سخنگو
# ==========================================================
SPEAKER_TRIGGERS = [norm_text(x) for x in ("نو آرا", "نوآرا", "نوارا", "نو ارا", "noara", "noa ara")]
MODE_CHANCE = {"called": 0.0, "sometimes": 0.18, "always": 0.85}
MODE_GAP = {"called": 3, "sometimes": 25, "always": 5}
def W(*words):
    ws = "|".join(re.escape(norm_text(w)) for w in words)
    return re.compile(rf"(?<!\w)(?:{ws})(?:ی|ه|ها|م|ت|ش|ا)?(?!\w)")
def RAW(pattern: str):
    return ("RAW", re.compile(pattern))
def K(*keys):
    return tuple(k if isinstance(k, (re.Pattern, tuple)) else norm_text(k) for k in keys)
REPLY = {
    "insult": ["اوه اوه، مثلاً دلم شکست؟ نه بابا، من سیم‌کشی شده‌ام، دل ندارم! 😎", "تو که انقدر انرژی داری، برو یه دور دور پارک بدو بعد بیا حرف بزن. 🏃", "ناسزا مثل نمکه؛ زیادش آدمو تشنه می‌کنه. آب بخور عزیز! 🧂🥤", "من اینجا مدیرم، تو مهمون. مهمون معمولاً با ادب‌تره. 😌", "حرف بدی بود، ولی ببخشمت! 🙃", "جواب بدی رو با لبخند دادن شغل منه؛ بفرما: 😁", "اگه با توهین کسی عوض می‌شد، دنیا الان بهشت بود! 🌍", "من آنتی‌ویروس دارم، حرف‌های بد روی من اثر نمی‌کنه! 🛡"],
    "praise": ["وای خجالت کشیدم! 🙈 ولی ادامه بده، خوشم اومد!", "قند توی دلم آب شد! 🍬", "ایول به تو که قدر می‌دونی! 💚", "این حرف‌ها رو یه بار دیگه بگو؛ ضبط می‌کنم! 🎙"],
    "greet": ["سلام سلام! خوش اومدی، چایی دم کردم؛ البته مجازی! ☕", "درود! امروز چه شکلی‌ای؟ 😄", "های! دیر کردی، داشتم گپ رو جارو می‌کردم. 🧹", "سلام عزیز! جات خالی بود. 😉", "به به! کی اومده! 🌸"],
    "daytime": ["صبحت بخیر! قهوه‌ات رو بخور. ☕", "ظهر بخیر! ناهار خوردی؟ 🍚", "عصر بخیر! یه چای تازه‌دم کم داریم. 🍵"],
    "goodnight": ["شب بخیر! خواب‌های رنگی ببینی. 🌙", "برو بخواب، فردا هم گپ هست! 😴"],
    "bye": ["به سلامت! زود برگرد. 👋", "خدانگهدار! 🪑", "فعلاً! یادت نره برگردی. 🌿"],
    "thanks": ["قابل شما رو نداشت! 💚", "وظیفه‌ست عزیزم. 🌿", "نوکرتیم! 😄"],
    "howru": ["من که عالی‌ام؛ تو چطوری؟ ✨", "خدا رو شکر، باتری‌م پره! 🔋", "سرپام! تو چی؟ 😄"],
    "love": ["لطف داری! منم همه‌تون رو دوست دارم. 💕", "وای خجالتم دادی! 🙈"],
    "crush": ["اوه اوه! بگو ببینم کیه؟ 🤫😂", "عشق یعنی دو تا آدم، یه پیتزا! 🍕"],
    "sad": ["ای جانم، ناراحت نباش؛ کنارتیم. 🤗", "غصه نخور؛ خدا بزرگه! 💚", "یه نفس عمیق بکش... بگو «جوک»! 😊"],
    "lonely": ["تنها نیستی؛ منم هستم! 🌿", "بیا اینجا حرف بزنیم. 💬"],
    "angry": ["آروم باش رفیق؛ نفس عمیق... 🧘", "یه لیوان آب بخور. 💧"],
    "laugh": ["ترکوندی! 😂", "خنده‌ت رو تا اینجا شنیدم! 🤣"],
    "bored": ["حوصله‌ت سر رفته؟ بگو «جوک»! 😄", "بیا بازی کنیم: بگو «سکه»! 🎲"],
    "hungry": ["گرسنه‌ای؟ پیتزا؟ 🍕", "یه املت ساده هم شاهکاره! 🍳"],
    "drink": ["یه چایی بریزم برات؟ ☕", "قهوه؟ بدون قهوه ربات‌ها هم از کار می‌افتن! 😴☕"],
    "sleepy": ["برو بخواب بابا! 😴", "یه لیوان شیر گرم بخور! 🥛"],
    "study": ["درس؟ تو می‌تونی! 📚", "شب امتحانی‌ها نابغه‌ان! 🧠"],
    "work": ["کار؟ امیدوارم حقوقت خوب باشه! 😄💰", "یه مرخصی لازم داری! 🏖"],
    "money": ["پول؟ من فقط ولت دارم! ⚡😂", "شوخی‌هام هنوز مجانیه! 🙃"],
    "game": ["گیمر پیدا شد! 🎮", "فقط ساعت خواب رو فراموش نکن! 🕹"],
    "net": ["اینترنت؟ درد مشترک! 🌐😅", "پینگ بالا یعنی امتحان صبر! 🏅"],
    "football": ["فوتبال؟ فقط دعوا نکنید! ⚽😄", "داور همیشه مقصره! 🟨"],
    "music": ["موزیک؟ 🎵", "یه پلی‌لیست خوب = یه روز خوب! 🎶"],
    "movie": ["فیلم؟ بگو چی دیدی! 🍿", "اسپویل نکنی! 🤫"],
    "weather": ["هوا که چیزی نیست؛ حال‌وهواست که مهمه! 🌤", "بارون و چای یعنی حال خوب! ☔☕"],
    "congrats": ["تبریک! 🎉", "مبارکت باشه! 🥳"],
    "sorry": ["اشکال نداره؛ همه اشتباه می‌کنن! 🌸", "بخشیدم! ولی شیرینی بیار! 🍬"],
    "help": ["گوش می‌دم! بگو چه کمکی می‌خوای. 🌿", "دستور «راهنما» رو بفرست. 📖"],
    "who": ["من «نو آرا» هستم؛ مدیر هوشمند این گپ. 🌿", "ربات خانگی این گروه! ☕😄"],
    "whatcan": ["بن، میوت، اخطار، نظرسنجی، قرعه‌کشی و شوخی! 🎯", "هم مدیریت، هم جوک و فال! 🪙"],
    "age": ["من هنوز جوونم! 👶", "ربات‌ها سن ندارن؛ فقط ورژن! 🔢"],
    "admin": ["مدیرها رو با «مدیران» ببین! 👥"],
    "rule": ["قوانین رو با «قوانین» ببین! 📜"],
    "yes": ["آفرین! همین‌طوره. 👍", "باشه، حله! 🫡"],
    "no": ["نه؟ حتماً دلایل خودت رو داری! 🤔", "نشد؟ بعداً دوباره! 💪"],
    "wow": ["واقعاً؟! 😮", "نه بابا؟! 😲"],
    "kiss": ["وای! خجالتم دادی! 🙈", "بغل مجازی! 🤗"],
    "called": ["جانم؟ گوش می‌دهم. 🙂", "بله؟ در خدمتم! 🌿", "صدا کردی؟ من اینجام! ✨"],
    "yesno": ["آره، صد در صد! 💯", "نه بابا! 🙅", "احتمالاً... ⏳", "ستاره‌ها می‌گن «شاید»! ✨"],
    "wh": ["سؤال خوبیه! ⏳", "اگه جوابش رو می‌دونستم ثروتمند بودم! 😆"],
    "exclaim": ["اوه! چه هیجانی! 🎉", "آروم‌تر! ولی باحاله! 😄"],
    "short": ["کوتاه و مفید! 😄", "اوکی! 👍"],
    "long": ["ماشالله! چه پیام بلندی! 📜😄", "رمان نوشتی! 📖"],
    "general": ["جالبه! بیشتر بگو. 🤔", "آها، می‌فهمم. 😌", "واقعاً؟ باحاله! ✨", "من که موافقم! 👍", "حرف حساب! 👌"],
    "riff": ["«{w}»؟ دقیقاً همین رو دنبالش بودم! 😄", "«{w}» مگه می‌شه حرف نزد؟ 💬", "«{w}» یعنی یه دنیای جدید! 🌍"],
    "emoji": ["یه ایموجی گفت: بقیه‌ش رو بگو! 😄", "من هم: 🌸"],
    "m_sticker": ["استیکرش باحاله! 😂", "یه استیکر ارزش هزار کلمه! 🎭"],
    "m_photo": ["عکس قشنگیه! 📸", "ماشالله! چه کادری! 😍"],
    "m_video": ["فیلم جالبیه! 🎬", "کارگردان گرامی، آفرین! 🎥"],
    "m_voice": ["صداتو شنیدم! 🎙", "ویس؟ می‌فهمم! 😄"],
    "m_note": ["ویدیو‌نوت! 🔴"],
    "m_gif": ["گیف باحاله! 😂"],
    "m_doc": ["فایل مهمی بود؟ 📄"],
    "m_audio": ["آهنگ خوبیه! 🎵"],
    "m_poll": ["نظرسنجی؟ رأی من محرمانه‌ست! 🗳"],
    "m_other": ["جالب بود! 👀"],
    "joke": ["یارو به خسیس می‌گه: ۱۰ تومن داری؟ می‌گه نه! 😂", "چرا برنامه‌نویس‌ها تاریکی دوست دارن؟ چون نور باگ جذب می‌کنه! 🐛💻", "به ربات گفتن چرا آنلاینی؟ گفت جای دیگه‌ای ندارم! 🤖😂"],
    "fortune": ["✨ فالت می‌گه امروز خبر خوب می‌شنوی! 😄", "🔮 ستاره‌ها می‌گن مهمون چایی می‌شی!", "🍀 شانس در می‌زنه؛ بیدار شو! 😂"],
}
# --- افزوده‌ها: دسته‌ی «morning» که قبلاً جا افتاده بود + تنوع بیشتر ---
REPLY["morning"] = ["روزت بخیر! انرژی‌ت رو نگه دار. ☀️", "سلام صبحانه‌ای! 🍳", "روز خوبی داشته باشی! اول یه چای بزن. 🍵"]
REPLY["greet"] += ["{n} جان سلام! امروز چه خبر؟ 😄", "به‌به {n}! گپ گرم شد. 🔥", "سلام {n}! خوش اومدی، بشین راحت باش. 🛋"]
REPLY["thanks"] += ["خواهش می‌کنم {n} جان! 💚", "قابلی نداشت؛ هر وقت لازم شد بگو. 🌿"]
REPLY["howru"] += ["عالی‌ام {n} جان! تو چی، چه خبرا؟ ✨"]
REPLY["general"] += ["دقیقاً! حرف دل منو زدی. 💬", "خب، بعدش؟ ادامه بده، گوشم باهاته. 👂", "این یکی رو باید یادداشت کنم! 📝", "نظر جالبیه {n} جان! 🌟"]
REPLY["called"] += ["بله {n} جان؟ بفرما! 😄", "اسممو آوردی؛ حتماً کار مهمی داری! 😎"]
VIP_REPLY = {
    "greet": ["سلام {n} عزیز، قدمتون روی چشم! 🌹", "درود بر شما {n} جان! خیلی خوش اومدین، گپ بدون شما یه چیزی کم داشت. 🌸", "سلام و صد سلام! امیدوارم روزتون عالی باشه. 🌿"],
    "morning": ["روزتون بخیر {n} عزیز! امیدوارم امروز همه‌چی به کامتون باشه. ☀️", "سلام صبح‌بخیر! قهوه‌تون رو با آرامش بخورید. ☕"],
    "goodnight": ["شب‌تون آروم و خوش، {n} عزیز. 🌙", "شب بخیر! خواب‌های قشنگ ببینید. 🌟"],
    "bye": ["به سلامت {n} جان، منتظر برگشتتون هستیم. 👋", "خدانگهدار! جای شما همیشه این‌جا گرمه. 🌿"],
    "thanks": ["این چه حرفیه، وظیفه‌ست {n} عزیز. 💚", "قابل شما رو نداره؛ همیشه در خدمتم. 🌹"],
    "praise": ["لطف دارید {n} جان، شما بزرگواری می‌کنید! 🙈💚", "همین که نظرتون مثبته انرژی می‌ده بهم. 🌸"],
    "howru": ["ممنونم از احوال‌پرسی‌تون {n} عزیز، عالی‌ام! شما چطورید؟ ✨", "خدا رو شکر، سرحالم؛ شما خوب هستید؟ 🌿"],
    "love": ["نظر لطف شماست؛ ما هم ارادتمندیم! 💕", "وای، شرمنده‌مون کردید! دوستون داریم. 🙈"],
    "sad": ["{n} جان، ناراحت نباشید؛ همه‌ی ما اینجا کنارتونیم. 🤗", "این روزها هم می‌گذره؛ اگه خواستید حرف بزنید، گوش می‌دم. 💚"],
    "lonely": ["شما تنها نیستید {n} عزیز؛ این گپ خونه‌ی شماست. 🌿"],
    "angry": ["حق دارید؛ یه نفس عمیق، و بعد هر کاری بگید انجام می‌دم. 🧘"],
    "bored": ["اگه بخواید یه جوک یا فال براتون بیارم؛ فقط بفرمایید. 😄"],
    "congrats": ["صد تبریک {n} جان! خدا قوت، همیشه شاد باشید. 🎉"],
    "sorry": ["اصلاً مهم نیست {n} عزیز، شما بزرگوارید. 🌸"],
    "help": ["در خدمتم {n} جان؛ بفرمایید چه کاری از دستم برمیاد. 🌿"],
    "insult": ["{n} عزیز، حتماً شوخی می‌کنید. من که از شما دلخور نمی‌شم. 😊"],
    "joke": ["چشم! این یکی مخصوص شماست: چرا برنامه‌نویس‌ها تاریکی دوست دارن؟ چون نور باگ جذب می‌کنه! 🐛😄", "به ربات گفتن چرا آنلاینی؟ گفت جای دیگه‌ای ندارم! 🤖"],
    "fortune": ["✨ فال امروز شما: یه خبر خوب تو راهه، دلتون قرص باشه. 🌹"],
    "laugh": ["خنده‌تون به ما هم سرایت کرد! 😄"],
    "called": ["بله {n} عزیز؟ در خدمتم. 🌹", "جانم {n} جان؟ بفرمایید. 🌿", "حضور دارم، امر بفرمایید! ✨"],
    "wh": ["سؤال خوبیه {n} جان؛ بگید ببینم نظر خودتون چیه؟ 🤔", "اگه جواب دقیق می‌دونستم حتماً می‌گفتم؛ شما چه فکری می‌کنید؟ 🌸"],
    "yesno": ["به نظر من آره، ولی نظر شما برام مهم‌تره. 🌹", "احتمالاً... شما چی فکر می‌کنید؟ ✨"],
    "short": ["چشم {n} جان! 👍", "در خدمتم. 🌿"],
    "long": ["{n} عزیز، با دقت خوندم؛ ممنون که توضیح دادید. 📖"],
    "general": ["جالبه {n} جان، بفرمایید ادامه بدید. 🌿", "حرف حسابیه! موافقم. 👌", "ممنون که می‌گید؛ این‌جا همیشه گوش شنواست. 💚", "نظر شما همیشه ارزشمنده. 🌸"],
}
SASS = ["راستی، جمله‌ی بعدی رو با ایموجی بگو! 😜", "یادت نره: من مدیرم! 😂", "نگران نباش، فقط ۳۰۰ نفر می‌خونن! 🤫"]
CALLED_BANK = {"low": ["جانم؟ گوش می‌دهم. 🙂", "در خدمتم. 🌿"], "medium": REPLY["called"] + ["اوه! صدام کردی؟ 🍬", "من اومدم! 😄"], "high": ["به‌به! اسمم رو بردی! 🌸😜", "نو آرا در خدمته! 😂"]}
STOP_WORDS = {"این", "اون", "برای", "ولی", "اما", "یعنی", "چون", "هم", "که", "رو", "من", "تو", "ما", "شما", "یه", "یک", "هست", "نیست", "خیلی", "یا", "با", "از", "به", "در", "بود", "کرد"}
MEDIA_KEYS = ("sticker", "photo", "video", "voice", "video_note", "animation", "audio", "document", "poll", "location", "contact")
MEDIA_BANK = {"sticker": "m_sticker", "photo": "m_photo", "video": "m_video", "voice": "m_voice", "video_note": "m_note", "animation": "m_gif", "audio": "m_audio", "document": "m_doc", "poll": "m_poll"}
RULES = [("insult", K(W("احمق", "ابله", "خنگ", "بیشعور", "اسکل", "عوضی", "خر", "الاغ"), "خفه شو", "ببند", "گمشو"), True), ("joke", K("جوک", "جک بگو", "بخندون"), True), ("fortune", K("فال", "طالع"), True), ("time", K("ساعت چنده", "ساعت چند"), True), ("date", K("تاریخ امروز", "امروز چندمه"), True), ("coin", K("سکه", "شیر یا خط"), True), ("dice", K("تاس", "عدد شانسی"), True), ("sad", K("ناراحتم", "غمگین", "😢", "😭", "💔"), False), ("lonely", K("تنهام", "تنهایی"), False), ("angry", K("عصبانیم", "😡"), False), ("morning", K("صبح بخیر", "ظهر بخیر", "عصر بخیر"), False), ("goodnight", K("شب بخیر", "شب خوش"), False), ("greet", K("سلام", "درود", W("های", "هلو")), False), ("bye", K("خداحافظ", "خدافظ", "فعلا", W("بای")), False), ("thanks", K("ممنون", "مرسی", "تشکر"), False), ("praise", K("دمت گرم", "ایول", "آفرین"), False), ("howru", K("حالت چطوره", "چطوری", "چه خبر"), False), ("love", K("دوستت دارم", "عاشقتم"), False), ("laugh", K(RAW(r"[خه]{3,}|😂|🤣|لول")), False), ("bored", K("حوصله ندارم", "بیکارم"), False), ("hungry", K("گشنمه", "گرسنه", W("غذا", "پیتزا")), False), ("drink", K(W("چای", "قهوه")), False), ("study", K(W("درس", "امتحان", "کنکور")), False), ("work", K(W("شغل", "حقوق")), False), ("money", K(W("پول", "دلار", "تورم")), False), ("game", K(W("بازی", "گیم")), False), ("net", K(W("نت", "اینترنت", "فیلتر")), False), ("football", K(W("فوتبال", "پرسپولیس", "استقلال")), False), ("music", K(W("آهنگ", "موزیک")), False), ("movie", K(W("فیلم", "سریال")), False), ("weather", K(W("هوا", "بارون", "برف")), False), ("congrats", K("تبریک", "مبارک", "تولد"), False), ("sorry", K(W("ببخشید", "شرمنده")), False), ("help", K("کمکم کن", "کمک کن"), False), ("who", K("تو کی هستی", "اسمت چیه"), True), ("whatcan", K("چیکار می‌کنی", "چی بلدی"), True)]
QUESTION_WORDS = W("چرا", "چطور", "چگونه", "کجا", "کی", "چند", "چه", "چی", "کدوم")
YESNO_STARTS = ("آیا", "میشه", "می‌شه", "درسته")
def _match(keys, low: str, nt: str) -> bool:
    for k in keys:
        if isinstance(k, tuple):
            if k[1].search(low):
                return True
        elif isinstance(k, re.Pattern):
            if k.search(nt):
                return True
        elif k and k in nt:
            return True
    return False
def msg_kind(m: Message) -> str:
    for k in MEDIA_KEYS:
        if getattr(m, k, None):
            return k
    return "text" if (m.text or m.caption) else "other"
def longest_word(nt: str) -> str:
    ws = [w for w in re.findall(r"\w+", nt) if len(w) >= 3 and w not in STOP_WORDS and not w.isdigit()]
    return max(ws, key=len) if ws else ""
# حافظه‌ی ۸ جواب آخر هر گپ تا جواب تکراری نیاید
RECENT: dict = defaultdict(lambda: deque(maxlen=8))
def pick(key: str, chat_id: int) -> str:
    pool = REPLY[key]
    h = RECENT[chat_id]
    ans = random.choice([x for x in pool if x not in h] or pool)
    h.append(ans)
    return ans
def fill(t: str, name: str) -> str:
    return t.replace("{n}", esc(name or "عزیز"))
def day_part() -> str:
    h = now_tz().hour
    return "morning" if 5 <= h < 12 else "noon" if 12 <= h < 17 else "evening" if 17 <= h < 21 else "night"
GREET_PART = {"morning": "صبح بخیر! ☀️ ", "noon": "ظهر بخیر! 🌤 ", "evening": "عصر بخیر! 🌇 ", "night": "شب بخیر! 🌙 "}
def vipick(cat: str, name: str, chat_id: int) -> str:
    h = RECENT[("vip", chat_id)]
    pool = VIP_REPLY[cat]
    ans = random.choice([x for x in pool if x not in h] or pool)
    h.append(ans)
    return fill(ans, name)
def special_reply(cat: str, core: str, chat_id: int, vip: bool = False, name: str = ""):
    out = None
    if cat == "time":
        out = f"⏰ ساعت الان {now_tz().strftime('%H:%M')} به وقت تهرانه! 😄"
    elif cat == "date":
        n = now_tz()
        jy, jm, jd = to_jalali(n.year, n.month, n.day)
        out = f"📅 امروز {WEEKDAYS[n.weekday()]} {jd} {JMONTHS[jm - 1]} {jy} است."
    elif cat == "coin":
        out = random.choice(["🪙 سکه انداختم: <b>شیر</b> اومد!", "🪙 سکه انداختم: <b>خط</b> اومد!"])
    elif cat == "dice":
        out = f"🎲 تاس ریختم: <b>{random.randint(1, 6)}</b>"
    if out:
        return out + ("\nدر خدمتتونم 🌹" if vip else "")
    if vip and cat in VIP_REPLY:
        return vipick(cat, name, chat_id)
    if cat == "greet" and random.random() < 0.5:
        return GREET_PART[day_part()] + fill(pick("greet", chat_id), name)
    return fill(pick(cat, chat_id), name)
def choose_reply(core: str):
    c = re.sub(r"[؟?!.]+", " ", core).strip()
    if " یا " not in f" {c} ":
        return None
    parts = [p.strip() for p in re.split(r"\s+یا\s+", c) if p.strip()]
    if len(parts) < 2 or len(parts) > 4:
        return None
    parts[0] = re.split(r"[:،,]", parts[0])[-1].strip()
    parts = [p for p in parts if 0 < len(p) <= 40]
    if len(parts) < 2:
        return None
    ch = random.choice(parts)
    return f"من رأیم با «{esc(ch)}» است! 🗳"
def build_reply(message: Message, nt: str, low: str, addressed: bool, level: str, chat_id: int, vip: bool = False, name: str = "") -> str:
    kind = msg_kind(message)
    txt = message.text or message.caption or ""
    core = nt
    for t in SPEAKER_TRIGGERS:
        core = core.replace(t, " ")
    core = re.sub(r"\s+", " ", core).strip()
    only_call = not re.sub(r"[\s؟?!.،,:؛;…~\-_*]+", "", core)
    V = lambda k: vipick(k, name, chat_id)
    if not txt:
        return pick(MEDIA_BANK.get(kind, "m_other"), chat_id)
    if addressed and only_call:
        return V("called") if vip else fill(random.choice(CALLED_BANK.get(level, CALLED_BANK["medium"])), name)
    if not re.sub(r"[\s\W_]+", "", EMOJI_RE.sub("", txt)) and EMOJI_RE.search(txt):
        return pick("emoji", chat_id)
    if addressed:
        ch = choose_reply(core)
        if ch:
            return ch + (" 🌹" if vip else "")
    for cat, keys, need_addr in RULES:
        if need_addr and not addressed:
            continue
        if _match(keys, low, core):
            return special_reply(cat, core, chat_id, vip, name)
    is_q = ("؟" in txt or "?" in txt or core.startswith(YESNO_STARTS) or bool(QUESTION_WORDS.search(core)))
    if is_q:
        wh = bool(QUESTION_WORDS.search(core)) and not core.startswith(YESNO_STARTS)
        return V("wh" if wh else "yesno") if vip else pick("wh" if wh else "yesno", chat_id)
    if "!" in txt and len(txt) < 40:
        return pick("exclaim", chat_id)
    words = core.split()
    if len(words) <= 2:
        return V("short") if vip else pick("short", chat_id)
    if len(words) >= 25 or len(txt) > 200:
        return V("long") if vip else pick("long", chat_id)
    if vip:
        return V("general")
    w = longest_word(core)
    if w and random.random() < 0.4:
        return random.choice(REPLY["riff"]).format(w=esc(w))
    return fill(pick("general", chat_id), name)
async def llm_reply(text: str, name: str):
    if not LLM_ENABLED:
        return None
    try:
        url, key, model = LLM_API_URL, LLM_API_KEY, LLM_MODEL
        if not (url and key and model):
            return None
        payload = {"model": model, "max_tokens": 150, "messages": [{"role": "system", "content": "تو «نو آرا» هستی؛ مدیر صمیمی گروه تلگرام. کوتاه و فارسی و بدون توهین."}, {"role": "user", "content": f"{name}: {text}"}]}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as ses:
            async with ses.post(url, json=payload, headers={"Authorization": f"Bearer {key}"}) as r:
                data = await r.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.warning(f"llm error: {e}")
        return None
async def speak(message: Message, bot: Bot, db: Database) -> bool:
    cid = message.chat.id
    s = await db.get_settings(cid)
    if not s.get("speaker_on"):
        return False
    txt = message.text or message.caption or ""
    low = txt.lower()
    nt = norm_text(txt)
    called = any(t in nt for t in SPEAKER_TRIGGERS)
    replied = bool(message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == bot.id)
    addressed = called or replied
    mode = s.get("speaker_mode", "called")
    now = time.time()
    if addressed:
        if now - SPEAK_LAST.get(cid, 0) < 3:
            return False
    else:
        if mode not in MODE_CHANCE or mode == "called":
            return False
        if txt.startswith(("/", "!")):
            return False
        rep = message.reply_to_message
        if rep and rep.from_user and rep.from_user.id != bot.id:
            return False
        if now - SPEAK_LAST.get(cid, 0) < MODE_GAP[mode]:
            return False
        chance = MODE_CHANCE[mode] * (0.5 if not txt else 1.0)
        if random.random() > chance:
            return False
    SPEAK_LAST[cid] = now
    level = s.get("speaker_level", "medium")
    name = message.from_user.first_name or message.from_user.full_name
    vip = is_vip(message.from_user.id)
    reply = None
    if addressed and txt:
        r = await llm_reply(txt, name)
        if r:
            reply = esc(r)
    if not reply:
        reply = build_reply(message, nt, low, addressed, level, cid, vip, name)
        if not vip and level == "high" and random.random() < 0.4:
            reply += "\n" + random.choice(SASS)
        elif not vip and addressed and random.random() < 0.4:
            reply = f"{esc(name)} جان! {reply}"
    try:
        await message.reply(reply)
        return True
    except TelegramAPIError:
        return False
# ==========================================================
# 12. هندلر اصلی پیام‌ها
# ==========================================================
async def group_flow(message: Message, bot: Bot, db: Database, role_level: int, tg_admin: bool):
    if not message.from_user:
        return
    if await guard(message, bot, db, role_level, tg_admin):
        return
    if message.from_user.is_bot:
        return
    try:
        await db.record_message(message.chat.id, message.from_user.id)
    except Exception as e:
        logging.warning(f"record error: {e}")
    txt = message.text or ""
    if txt:
        for kw, rep in await db.get_keywords(message.chat.id):
            if kw and kw.lower() in txt.lower():
                try:
                    await message.reply(esc(rep))
                except TelegramAPIError:
                    pass
                return
    await speak(message, bot, db)
async def handle_pending(message: Message, bot: Bot, db: Database, roles: Roles, pend: tuple) -> bool:
    tcid, mode, _ = pend
    uid = message.from_user.id
    if (await roles.get(bot, tcid, uid))[1] < 4:
        return False
    txt = (message.text or "").strip()
    group = message.chat.type in GROUP_TYPES
    if txt.lower() in ("/cancel", "cancel", "لغو", "/لغو"):
        await message.answer("❎ لغو شد.")
        return True
    if mode == "pick":
        tok = txt.split()[0] if txt.split() else ""
        tid = None
        if re.fullmatch(r"-?\d{5,}", tok):
            tid = int(tok)
        elif tok.startswith("@"):
            tid = await db.find_username(tok)
        if not tid or tid == bot.id:
            await message.answer("کاربر پیدا نشد؛ آیدی عددی یا یوزرنیمی بفرست که بات قبلاً دیده باشد.")
            return True
        ptext, pmarkup = await render_user_panel(bot, db, roles, tcid, tid, message.chat.type == "private")
        if group:
            await kill(message)
        await message.answer(ptext, reply_markup=pmarkup)
        return True
    if mode.startswith("tag:"):
        try:
            tid = int(mode.split(":")[1])
        except Exception:
            return True
        tag = txt.strip()[:TAG_MAX_LEN]
        if tag and not valid_tag_text(tag):
            await message.answer("تگ نامعتبر است (۰ تا ۱۶ حرف، بدون ایموجی).")
            return True
        ok, emsg = await set_member_tag(bot, tcid, tid, tag)
        if group:
            await kill(message)
        if ok:
            await db.set_member_tag_db(tcid, tid, tag)
            await db.add_log(tcid, uid, tid, "tag", tag)
            await message.answer(f"🏷 تگ «{esc(tag) or '—'}» ثبت شد.") if not group else await notice(bot, message.chat.id, f"🏷 تگ «{esc(tag) or '—'}» ثبت شد.")
        else:
            await message.answer(f"⚠️ {esc(emsg)}")
        return True
    if mode.startswith("tagtpl:"):
        k = mode.split(":", 1)[1]
        t = txt.strip()[:TAG_MAX_LEN]
        if t and not valid_tag_text(t):
            await message.answer("قالب نامعتبر است.")
            return True
        await db.set_setting(tcid, k, t)
        await message.answer(f"✅ قالب {k} ثبت شد: {esc(t) or '—'}")
        return True
    if mode == "search_members":
        q = norm_text(txt)
        admins = await db.get_admins(tcid)
        found = []
        for a_uid, role in admins:
            nm = await db.get_name(a_uid)
            if q in norm_text(nm) or q in str(a_uid):
                found.append((a_uid, role))
                if len(found) >= 10:
                    break
        if not found:
            await message.answer("موردی پیدا نشد.")
            return True
        rows = [[btn(f"{ROLE_FA.get(r, r)} • {await db.get_name(u)}"[:40], f"u:{tcid}:{u}:m")] for u, r in found]
        rows.append([btn("◀️ بازگشت", f"p:{tcid}:members")])
        await message.answer("🔎 <b>نتیجه جستجو:</b>", reply_markup=kb(rows))
        return True
    if mode.startswith("mention_reps:"):
        _, m_mode, panel_id_s = mode.split(":", 2)
        panel_id = int(panel_id_s)
        if m_mode not in MENTION_MIN:
            await message.answer("⚠️ حالت منشن نامعتبره.")
            return True
        lv = await mention_lv(bot, roles, tcid, uid)
        if lv < MENTION_MIN[m_mode]:
            await message.answer("⛔️ دیگه دسترسی این گزینه رو نداری.")
            return True
        try:
            reps = int(txt)
        except ValueError:
            await message.answer("❗️ فقط عدد بفرست، مثلاً: 3")
            return True
        reps = max(1, min(reps, MENTION_MAXREP[m_mode]))
        t = MENTION_JOBS.get(tcid)
        if t and not t.done():
            await message.answer("⏳ یه منشن دیگه در حال اجراست؛ صبر کن.")
            return True
        cd = 60 if lv >= 4 else 180
        if time.time() - MENTION_LAST.get(tcid, 0) < cd:
            await message.answer(f"⏳ فاصله‌ی دو منشن {cd} ثانیه است؛ کمی بعد امتحان کن.")
            return True
        targets = await collect_targets(bot, db, tcid, m_mode)
        if not targets:
            await message.answer("کسی برای منشن پیدا نشد.")
            return True
        MENTION_LAST[tcid] = time.time()
        await db.add_log(tcid, uid, 0, f"mention:{m_mode}", f"custom x{reps}")
        try:
            if group:
                await bot.edit_message_text(
                    f"📣 در حال منشن {len(targets)} نفر × {reps} دور…",
                    chat_id=tcid,
                    message_id=panel_id,
                    reply_markup=kb([[btn("⛔ توقف", f"mx:{tcid}")]]),
                )
            else:
                await message.answer(f"📣 در حال منشن {len(targets)} نفر × {reps} دور…")
        except Exception:
            pass
        MENTION_JOBS[tcid] = spawn(run_mention(bot, tcid, targets, reps, panel_id))
        if group:
            await kill(message)
        else:
            await message.answer(f"✅ منشن با {reps} دور شروع شد.")
        return True
    words = split_words(txt)
    if not words:
        await message.answer("کلمه‌ای پیدا نشد؛ دوباره از دکمه‌ی پنل شروع کن.")
        return True
    for w in words:
        if mode == "add":
            await db.add_filter(tcid, w)
        else:
            await db.del_filter(tcid, w)
    if group:
        await kill(message)
    res = f"✅ {len(words)} کلمه " + ("به لیست ممنوعه اضافه شد." if mode == "add" else "از لیست حذف شد.")
    if group:
        await notice(bot, message.chat.id, res)
    else:
        await message.answer(res + "\nبرای دیدن لیست: پنل ← 🚫 فحش‌ها")
    return True
@router.message()
async def on_message(message: Message, bot: Bot, db: Database, roles: Roles, role: str, role_level: int, tg_admin: bool):
    if not message.from_user or message.from_user.is_bot and not message.sender_chat:
        return
    private = message.chat.type == "private"
    group = message.chat.type in GROUP_TYPES
    if not (private or group):
        return
    # پشتیبانی: پیام کاربر ← سوپرمالک، و پاسخ سوپرمالک ← کاربر
    if private and await support_flow(message, bot, db):
        return
    if message.text:
        key = (message.chat.id, message.from_user.id)
        pend = PENDING_INPUT.get(key)
        if pend:
            PENDING_INPUT.pop(key, None)
            t = message.text.strip()
            is_cmd = t.startswith(("/", "!")) and t.lower() not in ("/cancel", "/لغو")
            if time.time() - pend[2] <= 180 and not is_cmd:
                if await handle_pending(message, bot, db, roles, pend):
                    return
    # دستور تگ دستی بدون اسلش: ریپلای + «تگ ...»
    if group and message.text and message.reply_to_message and message.reply_to_message.from_user:
        low_raw = (message.text or "").strip()
        if norm_text(low_raw).startswith(norm_text("تگ")) and role_level >= 4:
            rest = low_raw.split(None, 1)
            tag = rest[1].strip()[:TAG_MAX_LEN] if len(rest) > 1 else ""
            if not tag or valid_tag_text(tag):
                tid = message.reply_to_message.from_user.id
                ok, emsg = await set_member_tag(bot, message.chat.id, tid, tag)
                if ok:
                    await db.set_member_tag_db(message.chat.id, tid, tag)
                    await db.add_log(message.chat.id, message.from_user.id, tid, "tag", tag)
                    await kill(message)
                    await notice(bot, message.chat.id, f"🏷 تگ «{esc(tag) or '—'}» ثبت شد.")
                else:
                    await message.reply(f"⚠️ {esc(emsg)}")
                return
    parsed = parse_cmd(message.text or "", (await bot.me()).username or "") if message.text else None
    if parsed:
        name, args, slash = parsed
        if slash or role_level >= 1 or (name == "mention" and is_vip(message.from_user.id)):
            if private and name not in PV_OK:
                await message.answer(Texts.PV_ONLY_GROUP)
                return
            c = Ctx(message, bot, db, roles, args, role, role_level)
            try:
                await COMMANDS[name](c)
            except TelegramAPIError as e:
                logging.warning(f"command {name} api error: {e}")
                await c.reply(tg_err(e))
            if group:
                s = await db.get_settings(message.chat.id)
                if s.get("autodelete_cmd"):
                    spawn(delayed_delete(bot, message.chat.id, message.message_id, int(s.get("autodelete_sec", 10))))
            return
    if group:
        await group_flow(message, bot, db, role_level, tg_admin)
@router.error()
async def on_error(event: ErrorEvent):
    exc = event.exception
    if isinstance(exc, TelegramRetryAfter) or (
        isinstance(exc, TelegramBadRequest) and any(k in str(exc).lower() for k in ("query is too old", "query id is invalid", "message is not modified", "message to edit not found", "message to delete not found"))
    ):
        logging.warning("خطای بی‌اهمیت تلگرام: %s", str(exc).splitlines()[0])
        return True
    logging.exception("خطای مدیریت‌نشده: %s", exc)
    return True
# ==========================================================
# 13. کارهای زمان‌دار و اجرا
# ==========================================================
async def daily_summary(bot: Bot, db: Database):
    try:
        for cid, title, _ in await db.get_all_groups():
            rows = await db.today_logs(cid)
            total = await db.day_total(cid)
            if not rows and not total:
                continue
            lines = [f"• {esc(a)}: {n}" for a, n in rows] or ["• اقدام مدیریتی ثبت نشد"]
            top = await db.top(cid, 1, 3)
            lines.append(f"\n💬 پیام‌های امروز: {total}")
            if top:
                lines.append("🏆 فعال‌ترین‌ها: " + "، ".join(esc(r[1]) for r in top))
            for owner in await db.owners_of(cid):
                try:
                    await bot.send_message(owner, Texts.DAILY_SUMMARY.format(title=esc(title or cid), lines="\n".join(lines)))
                except Exception:
                    continue
    except Exception as e:
        logging.warning(f"summary err: {e}")
async def daily_backup(db: Database):
    await db.backup()
async def repent_job(db: Database):
    try:
        n = await db.repent_decay_all()
        if n:
            logging.info(f"repent decay: {n}")
    except Exception as e:
        logging.warning(f"repent err: {e}")
async def auto_tag_job(bot: Bot, db: Database):
    try:
        for cid, title, _ in await db.get_all_groups():
            try:
                s = await db.get_settings(int(cid))
            except Exception:
                continue
            if not s.get("tag_enabled") or not s.get("tag_auto"):
                continue
            try:
                bm = await bot.get_chat_member(int(cid), bot.id)
                if bm.status != ChatMemberStatus.ADMINISTRATOR:
                    continue
                if getattr(bm, "can_manage_tags", None) is False:
                    continue
            except Exception:
                pass
            try:
                top = await db.top(int(cid), 7, 1)
                if top:
                    tid = int(top[0][0])
                    try:
                        tm = await bot.get_chat_member(int(cid), tid)
                        st = getattr(getattr(tm, "status", None), "value", str(getattr(tm, "status", "")))
                        if st == "member":
                            tpl = str(s.get("tag_template_top", "برتر هفته") or "برتر هفته")
                            if valid_tag_text(tpl):
                                ok, _ = await set_member_tag(bot, int(cid), tid, tpl)
                                if ok:
                                    await db.set_member_tag_db(int(cid), tid, tpl)
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception as e:
        logging.warning(f"autotag err: {e}")
async def main():
    global SCHED, BOT
    validate()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    db = Database(config.db_path)
    await db.connect()
    roles = Roles(db)
    bot = Bot(token=config.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot.session.middleware(SafeRequestMiddleware())
    BOT = bot
    dp = Dispatcher(db=db, roles=roles)
    mw = RoleMiddleware()
    router.message.middleware(mw)
    router.callback_query.middleware(mw)
    dp.include_router(router)
    SCHED = AsyncIOScheduler(timezone="Asia/Tehran")
    SCHED.add_job(daily_summary, "cron", hour=23, minute=59, args=[bot, db])
    SCHED.add_job(daily_backup, "cron", hour=4, minute=0, args=[db])
    SCHED.add_job(repent_job, "cron", hour=3, minute=30, args=[db])
    SCHED.add_job(auto_tag_job, "cron", hour=5, minute=0, args=[bot, db])
    SCHED.start()
    me = await bot.get_me()
    await bot.delete_webhook(drop_pending_updates=True)
    print(f"نو آرا (@{me.username}) روشن شد 🌿")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member", "my_chat_member"])
    finally:
        SCHED.shutdown(wait=False)
        await db.close()
        await bot.session.close()
if __name__ == "__main__":
    asyncio.run(main())
