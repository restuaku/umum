import os
import logging
import re
from datetime import datetime
from typing import Dict, Any, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.request import HTTPXRequest
import httpx

from sheerid_verifier import SheerIDVerifier, VerificationResult

# =====================================================
# KONFIGURASI
# =====================================================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
LOG_BOT_TOKEN = os.environ.get("LOG_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
BOT_NAME = os.environ.get("BOT_NAME", "University_Verify_Bot")

SHEERID_BASE_URL = "https://services.sheerid.com"
ORGSEARCH_URL = "https://orgsearch.sheerid.net/rest/organization/search"

LOG_API_URL = (
    f"https://api.telegram.org/bot{LOG_BOT_TOKEN}/sendMessage"
    if LOG_BOT_TOKEN
    else None
)

SHEERID_URL, NAME, EMAIL, SCHOOL_TYPE, SCHOOL_SEARCH, BIRTH_DATE = range(6)
STEP_TIMEOUT = 300

# in-memory state (kalau produksi: Redis/DB)
user_data: Dict[int, Dict[str, Any]] = {}

sheerid_verifier = SheerIDVerifier(base_url=SHEERID_BASE_URL)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def send_log(text: str):
    if not LOG_BOT_TOKEN or ADMIN_CHAT_ID == 0 or not LOG_API_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(LOG_API_URL, json={"chat_id": ADMIN_CHAT_ID, "text": text})
    except Exception as e:
        print(f"❌ send_log error: {e}")


async def log_user_start(update: Update):
    user = update.effective_user
    text = (
        f"📥 NEW USER ({BOT_NAME})\n\n"
        f"ID: {user.id}\nName: {user.full_name}\n"
        f"Username: @{user.username or '-'}\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await send_log(text)


async def log_verification_result(
    user_id: int,
    full_name: str,
    school_name: str,
    email: str,
    success: bool,
    error_msg: str = "",
):
    status_emoji = "✅" if success else "❌"
    text = (
        f"{status_emoji} VERIFICATION ({BOT_NAME})\n\n"
        f"ID: {user_id}\nName: {full_name}\n"
        f"School: {school_name}\nEmail: {email}"
    )
    if not success:
        text += f"\nError: {error_msg}"
    await send_log(text)


# =====================================================
# TIMEOUT
# =====================================================
async def step_timeout_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    user_id = job.user_id
    step_name = job.data.get("step", "UNKNOWN")

    user_data.pop(user_id, None)

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏰ *Timeout di step {step_name}*\n\nKirim /start untuk ulang.",
        parse_mode="Markdown",
    )


def set_step_timeout(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, step: str):
    if context.job_queue is None:
        return
    job_name = f"timeout_{step}_{user_id}"
    for job in context.job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()

    context.job_queue.run_once(
        step_timeout_job,
        when=STEP_TIMEOUT,
        chat_id=chat_id,
        user_id=user_id,
        name=job_name,
        data={"step": step},
    )


def clear_all_timeouts(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    if context.job_queue is None:
        return
    for step in ["URL", "NAME", "EMAIL", "SCHOOL_TYPE", "SCHOOL_SEARCH", "BIRTH_DATE"]:
        job_name = f"timeout_{step}_{user_id}"
        for job in context.job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()


# =====================================================
# FLOW
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    await log_user_start(update)

    user_data.pop(user_id, None)
    clear_all_timeouts(context, user_id)
    set_step_timeout(context, chat_id, user_id, "URL")

    await update.message.reply_text(
        "🎓 *University Student Verification Bot*\n\n"
        "Kirim SheerID verification URL:\n\n"
        "`https://services.sheerid.com/verify/.../?verificationId=...`\n\n"
        "*⏰ 5 menit untuk kirim link*",
        parse_mode="Markdown",
    )
    return SHEERID_URL


async def get_sheerid_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    url = update.message.text.strip()

    verification_id = SheerIDVerifier.parse_verification_id(url)
    if not verification_id:
        await update.message.reply_text(
            "❌ *URL tidak valid!*\n\n"
            "Harus ada `verificationId=` (24-32 karakter hex).\n\n"
            "*Contoh:*\n"
            "`https://services.sheerid.com/verify/.../?verificationId=694f8154135fb92c1921e6fd`\n\n"
            "*⏰ 5 menit lagi*",
            parse_mode="Markdown",
        )
        set_step_timeout(context, chat_id, user_id, "URL")
        return SHEERID_URL

    user_data[user_id] = {
        "verification_id": verification_id,
        "original_url": url,
    }

    clear_all_timeouts(context, user_id)
    set_step_timeout(context, chat_id, user_id, "NAME")

    await update.message.reply_text(
        f"✅ *Verification ID:* `{verification_id[:8]}...{verification_id[-8:]}` ({len(verification_id)} chars)\n\n"
        "Nama lengkap kamu?\n"
        "Contoh: John Smith\n\n"
        "*⏰ 5 menit*",
        parse_mode="Markdown",
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    full_name = update.message.text.strip()

    parts = full_name.split()
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ *Nama harus ada first + last name*\n"
            "Contoh: John Smith\n\n*⏰ 5 menit lagi*",
            parse_mode="Markdown",
        )
        set_step_timeout(context, chat_id, user_id, "NAME")
        return NAME

    user_data[user_id]["first_name"] = parts[0]
    user_data[user_id]["last_name"] = " ".join(parts[1:])
    user_data[user_id]["full_name"] = full_name

    clear_all_timeouts(context, user_id)
    set_step_timeout(context, chat_id, user_id, "EMAIL")

    await update.message.reply_text(
        f"✅ *Nama:* {full_name}\n\n"
        "Email universitas?\n"
        "Contoh: john@stanford.edu\n\n"
        "*⏰ 5 menit*",
        parse_mode="Markdown",
    )
    return EMAIL


async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    email = update.message.text.strip()

    if "@" not in email or "." not in email:
        await update.message.reply_text(
            "❌ *Email tidak valid!*\n"
            "Contoh: john@stanford.edu\n\n*⏰ 5 menit lagi*",
            parse_mode="Markdown",
        )
        set_step_timeout(context, chat_id, user_id, "EMAIL")
        return EMAIL

    user_data[user_id]["email"] = email

    clear_all_timeouts(context, user_id)

    keyboard = [
        [InlineKeyboardButton("🎓 4-year University", callback_data="type_FOUR_YEAR")],
        [InlineKeyboardButton("📚 2-year College", callback_data="type_TWO_YEAR")],
        [InlineKeyboardButton("🏛️ Public University", callback_data="type_UNIVERSITY")],
        [InlineKeyboardButton("🏫 Private University", callback_data="type_COLLEGE")],
    ]
    await update.message.reply_text(
        f"✅ *Email:* `{email}`\n\nPilih *tipe universitas*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    set_step_timeout(context, chat_id, user_id, "SCHOOL_TYPE")
    return SCHOOL_TYPE


async def search_universities(query: str, school_type: str) -> List[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        params = {"country": "US", "type": school_type, "name": query}
        try:
            resp = await client.get(ORGSEARCH_URL, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()
            if not isinstance(data, list):
                return []
            # dedupe by id
            seen = set()
            unique = []
            for u in data:
                sid = u.get("id")
                if sid and sid not in seen:
                    seen.add(sid)
                    unique.append(u)
            return unique[:15]
        except Exception:
            return []


async def display_universities(update: Update, universities: list, user_id: int):
    text = "🎓 *UNIVERSITY SEARCH RESULTS*\n\n"
    text += f"Query: `{user_data[user_id]['school_search']}`\n"
    text += f"Found: *{len(universities)}*\n\n"

    keyboard = []
    for idx, uni in enumerate(universities):
        user_data[user_id][f"uni_{idx}"] = uni
        name = uni.get("name", "Unknown")
        city = uni.get("city", "")
        state = uni.get("state", "")
        univ_type = uni.get("type", "UNIVERSITY")
        location = f"{city}, {state}".strip(", ")

        text += f"{idx+1}. *{name}*\n"
        text += f"   📍 {location or '-'}\n"
        text += f"   └─ `{univ_type}`\n\n"

        button_text = f"{idx+1}. {name[:35]}{'...' if len(name) > 35 else ''}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sel_{idx}")])

    text += "👆 *Pilih universitas*"

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def get_school_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    school_name = update.message.text.strip()

    user_data[user_id]["school_search"] = school_name
    set_step_timeout(context, chat_id, user_id, "SCHOOL_SEARCH")

    msg = await update.message.reply_text(
        f"🔍 *Mencari universitas:* `{school_name}`\nMenunggu hasil SheerID...",
        parse_mode="Markdown",
    )

    school_type = user_data[user_id].get("school_type", "UNIVERSITY")
    schools = await search_universities(school_name, school_type)

    if not schools:
        await msg.edit_text(
            "❌ *Universitas tidak ditemukan*\n\nCoba nama lain atau /start ulang.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    await msg.delete()
    await display_universities(update, schools, user_id)

    clear_all_timeouts(context, user_id)
    return SCHOOL_SEARCH


async def get_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    birth_date = update.message.text.strip()

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", birth_date):
        await update.message.reply_text(
            "❌ *Format salah!*\n"
            "Gunakan: `YYYY-MM-DD`\n"
            "Contoh: `2000-05-15`\n\n*⏰ 5 menit lagi*",
            parse_mode="Markdown",
        )
        set_step_timeout(context, chat_id, user_id, "BIRTH_DATE")
        return BIRTH_DATE

    user_data[user_id]["birth_date"] = birth_date

    await process_verification(update, context, user_id)
    clear_all_timeouts(context, user_id)
    return ConversationHandler.END


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id
    chat_id = query.message.chat.id  # FIX v20

    if data.startswith("type_"):
        # callback_data: type_FOUR_YEAR, type_TWO_YEAR, type_UNIVERSITY, type_COLLEGE
        school_type = data.replace("type_", "", 1)
        user_data.setdefault(user_id, {})
        user_data[user_id]["school_type"] = school_type

        await query.edit_message_text(
            f"✅ *Tipe universitas:* `{school_type}`\n\n"
            "Ketik *nama universitas* kamu:\n"
            "Contoh: Stanford University",
            parse_mode="Markdown",
        )
        set_step_timeout(context, chat_id, user_id, "SCHOOL_SEARCH")
        return SCHOOL_SEARCH

    if data.startswith("sel_"):
        try:
            idx = int(data.split("_", 1)[1])
        except Exception:
            await query.edit_message_text("❌ Data pilihan tidak valid. Silakan /start ulang.")
            return ConversationHandler.END

        uni = user_data.get(user_id, {}).get(f"uni_{idx}")
        if not uni:
            await query.edit_message_text("❌ Universitas tidak ditemukan di state. Silakan /start ulang.")
            return ConversationHandler.END

        user_data[user_id]["school_id"] = uni.get("id")
        user_data[user_id]["school_name"] = uni.get("name")

        await query.edit_message_text(
            f"✅ *Universitas terpilih:*\n"
            f"{uni.get('name')} ({uni.get('city','')}, {uni.get('state','')})\n\n"
            "Kirim *tanggal lahir* kamu (YYYY-MM-DD):\n"
            "Contoh: `2000-05-15`",
            parse_mode="Markdown",
        )
        set_step_timeout(context, chat_id, user_id, "BIRTH_DATE")
        return BIRTH_DATE

    return ConversationHandler.END


async def process_verification(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    chat_id = update.effective_chat.id
    state = user_data.get(user_id, {})

    verification_id = state.get("verification_id")
    original_url = state.get("original_url")
    first_name = state.get("first_name")
    last_name = state.get("last_name")
    full_name = state.get("full_name") or f"{first_name} {last_name}"
    email = state.get("email")
    birth_date = state.get("birth_date")
    school_id = state.get("school_id")
    school_name = state.get("school_name") or "-"
    school_type = state.get("school_type") or "UNIVERSITY"

    if not all([verification_id, first_name, last_name, email, birth_date, school_id]):
        await context.bot.send_message(chat_id=chat_id, text="❌ Data tidak lengkap. Silakan /start ulang.")
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text="⏳ Memproses data...\nMohon tunggu sebentar.",
    )

    # SAFE: no bypass, just validate + tell user to continue in browser
    result: VerificationResult = await sheerid_verifier.submit_student_verification(
        verification_id=verification_id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        birth_date=birth_date,
        organization_id=int(school_id),
        organization_type=school_type,
        original_url=original_url,
    )

    if result.success:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "✅ *Data diterima!*\n\n"
                f"• Nama: *{full_name}*\n"
                f"• Email: `{email}`\n"
                f"• Kampus: *{school_name}*\n"
                f"• Birth date: `{birth_date}`\n\n"
                "Sekarang *lanjutkan verifikasi di browser* lewat link ini:\n"
                f"{original_url}\n\n"
                "_Catatan: Bot ini tidak meng-automate verifikasi SheerID._"
            ),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        await log_verification_result(
            user_id=user_id,
            full_name=full_name,
            school_name=school_name,
            email=email,
            success=True,
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ *Gagal memproses:* `{result.error_message}`",
            parse_mode="Markdown",
        )
        await log_verification_result(
            user_id=user_id,
            full_name=full_name,
            school_name=school_name,
            email=email,
            success=False,
            error_msg=result.error_message or "",
        )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN belum di-set di environment")

    request = HTTPXRequest(connection_pool_size=8)
    application = Application.builder().token(BOT_TOKEN).request(request).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SHEERID_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sheerid_url)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            SCHOOL_TYPE: [CallbackQueryHandler(button_callback, pattern=r"^type_")],
            SCHOOL_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_school_name),
                CallbackQueryHandler(button_callback, pattern=r"^sel_"),
            ],
            BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_date)],
        },
        fallbacks=[CommandHandler("start", start)],
        per_chat=True,
        per_user=True,
        per_message=False,
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_callback))  # fallback callback handler

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
