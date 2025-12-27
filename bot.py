"""
SheerID University Student Verification Bot (SHEERID ORGSEARCH API)
Flow: URL → Name → Email → University Type → Search & Select → Birth Date
"""
import os
import logging
import re
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.request import HTTPXRequest
import httpx
from sheerid_verifier import SheerIDVerifier

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

# States untuk ConversationHandler
SHEERID_URL, NAME, EMAIL, SCHOOL_TYPE, SCHOOL_SEARCH, BIRTH_DATE = range(6)

STEP_TIMEOUT = 300  # 5 menit

user_data = {}

# =====================================================
# LOGGING
# =====================================================

async def send_log(text: str):
    """Kirim log ke admin"""
    if not LOG_BOT_TOKEN or ADMIN_CHAT_ID == 0 or not LOG_API_URL:
        print("⚠️ LOG_BOT_TOKEN atau ADMIN_CHAT_ID belum diset")
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(LOG_API_URL, json={
                "chat_id": ADMIN_CHAT_ID,
                "text": text,
            })
    except:
        pass

async def log_user_start(update: Update):
    """Log user start"""
    user = update.effective_user
    text = (
        f"📥 NEW USER ({BOT_NAME})\n\n"
        f"ID: {user.id}\nName: {user.full_name}\n"
        f"Username: @{user.username or '-'}\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await send_log(text)

async def log_verification_result(user_id: int, full_name: str, school_name: str, 
                                email: str, success: bool, error_msg: str = ""):
    """Log hasil verifikasi"""
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
# TIMEOUT HANDLERS
# =====================================================

async def step_timeout_job(context: ContextTypes.DEFAULT_TYPE):
    """Timeout handler"""
    job = context.job
    chat_id = job.chat_id
    user_id = job.user_id
    step_name = job.data.get("step", "UNKNOWN")
    
    if user_id in user_data:
        del user_data[user_id]
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏰ *Timeout di step {step_name}*\n\nKirim /start untuk ulang.",
        parse_mode="Markdown",
    )

def set_step_timeout(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, step: str):
    """Set timeout 5 menit"""
    if context.job_queue is None:
        return
    job_name = f"timeout_{step}_{user_id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()
    
    context.job_queue.run_once(
        step_timeout_job, when=STEP_TIMEOUT, chat_id=chat_id, user_id=user_id,
        name=job_name, data={"step": step}
    )

def clear_all_timeouts(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Clear semua timeout"""
    if context.job_queue is None:
        return
    for step in ["URL", "NAME", "EMAIL", "SCHOOL_TYPE", "SCHOOL_SEARCH", "BIRTH_DATE"]:
        job_name = f"timeout_{step}_{user_id}"
        for job in context.job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()

# =====================================================
# CONVERSATION FLOW
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /start"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    await log_user_start(update)
    
    if user_id in user_data:
        del user_data[user_id]
    clear_all_timeouts(context, user_id)
    
    set_step_timeout(context, chat_id, user_id, "URL")
    
    await update.message.reply_text(
        "🎓 *University Student Verification Bot*\n\n"
        "Kirim SheerID verification URL:\n\n"
        "`https://services.sheerid.com/verify/.../verificationId=...`\n\n"
        "*⏰ 5 menit untuk kirim link*",
        parse_mode="Markdown",
    )
    return SHEERID_URL

async def get_sheerid_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ambil SheerID URL (32 chars)"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    url = update.message.text.strip()
    
    # Extract verification ID (32 hex chars seperti skrip asli)
    match = re.search(r"verificationId=([a-f0-9]{32})", url, re.IGNORECASE)
    if not match:
        await update.message.reply_text(
            "❌ *URL tidak valid!*\n\n"
            "Format: `verificationId=abc123...` (32 karakter hex)\n\n"
            "*⏰ 5 menit lagi*",
            parse_mode="Markdown",
        )
        set_step_timeout(context, chat_id, user_id, "URL")
        return SHEERID_URL
    
    verification_id = match.group(1)
    user_data[user_id] = {"verification_id": verification_id}
    
    clear_all_timeouts(context, user_id)
    set_step_timeout(context, chat_id, user_id, "NAME")
    
    await update.message.reply_text(
        f"✅ *Verification ID:* `{verification_id[:8]}...{verification_id[-8:]}`\n\n"
        "Nama lengkap kamu?\n"
        "Contoh: John Smith\n\n"
        "*⏰ 5 menit*",
        parse_mode="Markdown",
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ambil nama"""
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
    """Ambil email"""
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
    
    # Keyboard pilih university type
    keyboard = [
        [InlineKeyboardButton("🎓 4-year University", callback_data="type_4year")],
        [InlineKeyboardButton("📚 2-year College", callback_data="type_2year")],
        [InlineKeyboardButton("🏛️ Public University", callback_data="type_public")],
        [InlineKeyboardButton("🏫 Private University", callback_data="type_private")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ *Email:* `{email}`\n\n"
        "Pilih *tipe universitas*:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    set_step_timeout(context, chat_id, user_id, "SCHOOL_TYPE")
    return SCHOOL_TYPE

async def get_school_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User input nama universitas untuk search"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    school_name = update.message.text.strip()
    
    user_data[user_id]["school_search"] = school_name
    
    set_step_timeout(context, chat_id, user_id, "SCHOOL_SEARCH")
    
    msg = await update.message.reply_text(
        f"🔍 *Mencari universitas:* `{school_name}`\n"
        "Menunggu hasil SheerID...",
        parse_mode="Markdown",
    )
    
    # Search via SheerID API
    schools = await search_universities(school_name)
    
    if not schools:
        await msg.edit_text(
            "❌ *Universitas tidak ditemukan*\n\n"
            "Coba nama lain atau /start ulang.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END
    
    await msg.delete()
    await display_universities(update, schools, user_id)
    
    clear_all_timeouts(context, user_id)
    return SCHOOL_SEARCH

async def get_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ambil tanggal lahir"""
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
    
    # PROSES VERIFICATION!
    await process_verification(update, context, user_id)
    return ConversationHandler.END

# =====================================================
# SHEERID UNIVERSITY SEARCH
# =====================================================

async def search_universities(query: str) -> list:
    """Search universities via SheerID OrgSearch API"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        all_universities = []
        
        # Search UNIVERSITY types
        for univ_type in ["UNIVERSITY", "COLLEGE", "FOUR_YEAR", "TWO_YEAR"]:
            try:
                params = {
                    "country": "US",
                    "type": univ_type,
                    "name": query
                }
                print(f"📡 SheerID search: {univ_type} '{query}'")
                resp = await client.get(ORGSEARCH_URL, params=params)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        all_universities.extend(data)
            except Exception as e:
                print(f"❌ Search {univ_type} error: {e}")
                continue
        
        # Remove duplicates
        seen = set()
        unique = []
        for u in all_universities:
            sid = u.get("id")
            if sid and sid not in seen:
                seen.add(sid)
                unique.append(u)
        
        print(f"📊 Found {len(unique)} unique universities")
        return unique[:15]  # Max 15 pilihan

async def display_universities(update: Update, universities: list, user_id: int):
    """Tampilkan hasil search dengan tombol"""
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
        location = f"{city}, {state}" if city and state else state
        
        text += f"{idx+1}. *{name}*\n"
        text += f"   📍 {location}\n"
        text += f"   └─ `{univ_type}`\n\n"
        
        button_text = f"{idx+1}. {name[:35]}{'...' if len(name) > 35 else ''}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sel_{user_id}_{idx}")])
    
    text += "\n👆 *Pilih universitas*"
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

# =====================================================
# BUTTON CALLBACKS
# =====================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle tombol type & selection"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data.startswith("type_"):
        # Pilih type → minta nama universitas
        type_map = {
            "type_4year": "FOUR_YEAR",
            "type_2year": "TWO_YEAR", 
            "type_public": "UNIVERSITY",
            "type_private": "COLLEGE"
        }
        user_data[user_id]["school_type"] = type_map.get(data, "UNIVERSITY")
        
        await query.edit_message_text(
            f"✅ *{data.replace('type_', '').replace('_', ' ').title()}*\n\n"
            "Nama universitas apa yang dicari?\n"
            "Contoh: `Stanford`, `Harvard`, `UCLA`\n\n"
            "*⏰ 5 menit*",
            parse_mode="Markdown",
        )
        
        chat_id = query.message.chat_id
        set_step_timeout(context, chat_id, user_id, "SCHOOL_SEARCH")
        return SCHOOL_SEARCH
        
    elif data.startswith("sel_"):
        # Pilih university spesifik
        parts = data.split("_")
        school_idx = int(parts[2])
        
        school = user_data[user_id].get(f"uni_{school_idx}")
        if not school:
            await query.edit_message_text("❌ *Data universitas hilang*\n/start ulang")
            return
        
        user_data[user_id]["school"] = school
        school_name = school["name"]
        location = f"{school.get('city', '')}, {school.get('state', '')}".strip(", ")
        
        await query.edit_message_text(
            f"✅ *Universitas terpilih:*\n\n"
            f"🏛️ *{school_name}*\n"
            f"📍 {location}\n"
            f"🆔 `{school['id']}`\n"
            f"Type: `{school.get('type', 'UNIVERSITY')}`\n\n"
            f"📅 *Tanggal lahir?*\n"
            f"Format: `YYYY-MM-DD`\n"
            f"Contoh: `2000-05-15`\n\n*⏰ 5 menit*",
            parse_mode="Markdown",
        )
        
        set_step_timeout(context, query.message.chat_id, user_id, "BIRTH_DATE")
        return BIRTH_DATE

# =====================================================
# VERIFICATION PROCESS
# =====================================================

async def process_verification(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Jalankan SheerIDVerifier dengan data user"""
    chat_id = update.effective_chat.id
    
    try:
        data = user_data[user_id]
        verification_id = data["verification_id"]
        first_name = data["first_name"]
        last_name = data["last_name"]
        full_name = data["full_name"]
        email = data["email"]
        birth_date = data["birth_date"]
        school = data["school"]
        
        msg = await update.message.reply_text(
            f"⚙️ *Memproses verifikasi...*\n\n"
            f"👤 {full_name}\n"
            f"🏛️ {school['name'][:30]}...\n"
            f"📧 {email}\n"
            f"⏳ Menyiapkan student ID card...",
            parse_mode="Markdown",
        )
        
        # JALANKAN SHEERIDVERIFIER ASLI (dengan modifikasi parameter)
        verifier = SheerIDVerifier(verification_id)
        result = verifier.verify(
            first_name=first_name,
            last_name=last_name,
            email=email,
            birth_date=birth_date,
            school=school  # ← Parameter baru
        )
        
        # Log hasil
        await log_verification_result(
            user_id, full_name, school["name"], email,
            result.success, result.message if not result.success else ""
        )
        
        if result.success:
            await msg.edit_text(
                f"✅ *VERIFICATION SUCCESS!*\n\n"
                f"👤 *{full_name}*\n"
                f"🏛️ *{school['name']}*\n"
                f"📧 `{email}`\n"
                f"📅 `{birth_date}`\n\n"
                f"⏳ *Hasil dalam 24-48 jam*\n"
                f"✅ Cek email (termasuk spam folder)",
                parse_mode="Markdown",
            )
        else:
            await msg.edit_text(
                f"❌ *VERIFICATION FAILED*\n\n"
                f"Error: `{result.message}`\n\n"
                f"/start untuk coba lagi",
                parse_mode="Markdown",
            )
            
    except Exception as e:
        await update.message.reply_text(
            f"❌ *Error:*\n`{str(e)[:100]}`\n\n/start ulang",
            parse_mode="Markdown",
        )
        await log_verification_result(user_id, "UNKNOWN", "ERROR", "N/A", False, str(e))
    
    finally:
        if user_id in user_data:
            del user_data[user_id]
        clear_all_timeouts(context, user_id)

# =====================================================
# CANCEL
# =====================================================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel handler"""
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]
    clear_all_timeouts(context, user_id)
    
    await update.message.reply_text(
        "❌ *Dibatalkan*\n\nKirim /start untuk mulai lagi",
        parse_mode="Markdown",
    )
    return ConversationHandler.END

# =====================================================
# MAIN
# =====================================================

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN belum diset!")
        return
    
    print("\n" + "="*60)
    print(f"🎓 {BOT_NAME} (SHEERID ORGSEARCH)")
    print("="*60)
    print(f"🤖 Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-5:]}")
    print(f"👮 Admin: {ADMIN_CHAT_ID}")
    print(f"📡 ORGSEARCH: {ORGSEARCH_URL}")
    print("="*60)
    
    request = HTTPXRequest(
        connect_timeout=10, read_timeout=30, write_timeout=30, pool_timeout=10
    )
    
    app = Application.builder().token(BOT_TOKEN).request(request).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SHEERID_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sheerid_url)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            SCHOOL_TYPE: [CallbackQueryHandler(button_callback)],
            SCHOOL_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_school_name)],
            BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=None,
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
