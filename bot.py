"""
SheerID Telegram Verification Bot
Automates student verification with document generation
"""
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    filters, 
    ContextTypes
)
from dotenv import load_dotenv

from sheerid_verifier import SheerIDVerifier

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')

# User states
user_states = {}

# ============================================================================
# Command Handlers
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user

    welcome_text = f"""
🎓 **SheerID Student Verification Bot**

Hi {user.first_name}! 👋

I can help you complete SheerID student verification automatically with:
✅ Random verified US university selection
✅ Realistic student data generation
✅ Automated document creation & upload

**How to use:**
1. Get your SheerID verification URL
2. Send the URL to me
3. I'll handle the rest!

**Commands:**
/verify - Start new verification
/help - Show help
/about - About this bot

Ready to verify? Send me your SheerID URL! 🚀
"""

    keyboard = [
        [InlineKeyboardButton("🎓 Start Verification", callback_data='start_verify')],
        [InlineKeyboardButton("❓ Help", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /verify command"""
    user_id = update.effective_user.id
    user_states[user_id] = 'waiting_url'

    text = """
📝 **Start Verification**

Please send me your SheerID verification URL.

**Example URL format:**
`https://services.sheerid.com/verify/xxxxx/?verificationId=abc123...`

You can get this URL from:
• GitHub Student Pack signup
• Student discount pages
• Educational program enrollments

Send the URL now 👇
"""

    await update.message.reply_text(text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
❓ **Help & Instructions**

**How it works:**
1. Bot selects a random verified US university
2. Generates realistic student data (name, DOB, email)
3. Creates authentic student ID card with photo
4. Submits everything to SheerID
5. You get verification result via email in 24-48 hours

**Commands:**
/start - Welcome message
/verify - Start new verification
/help - Show this help
/about - Bot information
/cancel - Cancel current operation

**Tips:**
• Use official SheerID URLs only
• Check email (including spam) after 24-48 hours
• One verification per URL
• Success rate: ~70-85% (depends on SheerID checks)

**Need support?**
Contact: @YourSupportUsername
"""

    await update.message.reply_text(help_text, parse_mode='Markdown')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /about command"""
    about_text = """
ℹ️ **About This Bot**

**Version:** 1.0.0
**Created:** December 2024

**Features:**
• 2,826 verified US universities database
• Realistic name generation (20,600+ combinations)
• Automated student ID card creation
• Real student photos integration
• Full SheerID API workflow automation

**Technology Stack:**
• Python 3.11+
• python-telegram-bot
• PIL/Pillow (image generation)
• httpx (async HTTP)

**Database:**
• IPEDS 2023 official data
• SheerID organization verification
• 100% legitimate universities

**Disclaimer:**
This bot is for educational purposes. Use responsibly and comply with SheerID's terms of service.

🔒 Your privacy: We don't store any personal data.
"""

    await update.message.reply_text(about_text, parse_mode='Markdown')

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command"""
    user_id = update.effective_user.id

    if user_id in user_states:
        del user_states[user_id]
        text = "❌ Operation cancelled. Use /verify to start new verification."
    else:
        text = "Nothing to cancel. Use /verify to start."

    await update.message.reply_text(text)

# ============================================================================
# Message Handlers
# ============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages (mainly URLs)"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Check if user is waiting for URL
    if user_states.get(user_id) == 'waiting_url':
        await process_verification_url(update, context, text)
    else:
        # Try to detect SheerID URL anyway
        if 'sheerid.com' in text.lower() and 'verificationid=' in text.lower():
            await process_verification_url(update, context, text)
        else:
            await update.message.reply_text(
                "Send me a SheerID verification URL to start, or use /help for instructions."
            )

async def process_verification_url(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    """Process SheerID verification URL"""
    user_id = update.effective_user.id

    # Parse verification ID
    verification_id = SheerIDVerifier.parse_verification_id(url)

    if not verification_id:
        await update.message.reply_text(
            "❌ Invalid SheerID URL format.\n\n"
            "Please send a valid URL like:\n"
            "`https://services.sheerid.com/verify/xxxxx/?verificationId=abc123...`",
            parse_mode='Markdown'
        )
        return

    # Clear user state
    if user_id in user_states:
        del user_states[user_id]

    # Send processing message
    processing_msg = await update.message.reply_text(
        f"⏳ **Processing Verification**\n\n"
        f"🆔 Verification ID: `{verification_id}`\n"
        f"⚙️ Status: Initializing...\n\n"
        f"This may take 30-60 seconds. Please wait...",
        parse_mode='Markdown'
    )

    try:
        # Update: Selecting university
        await processing_msg.edit_text(
            f"⏳ **Processing Verification**\n\n"
            f"🆔 Verification ID: `{verification_id}`\n"
            f"🎓 Status: Selecting university...\n",
            parse_mode='Markdown'
        )

        # Create verifier and execute
        verifier = SheerIDVerifier(verification_id)

        # Update: Generating data
        await processing_msg.edit_text(
            f"⏳ **Processing Verification**\n\n"
            f"🆔 Verification ID: `{verification_id}`\n"
            f"📝 Status: Generating student data...\n",
            parse_mode='Markdown'
        )

        # Run verification
        result = verifier.verify()

        # Format result message
        if result['success']:
            info = result['student_info']

            success_text = f"""
✅ **Verification Submitted Successfully!**

**Student Information:**
👤 Name: {info['name']}
📧 Email: {info['email']}
🎂 Birth: {info['birth_date']}

**University:**
🏫 {info['school']}
📍 {info['location']}
🆔 SheerID Org ID: {info['school_id']}

**Next Steps:**
1. Check email: `{info['email']}` in 24-48 hours
2. Look for email from SheerID or the service provider
3. Check spam/junk folder if not in inbox

**Verification ID:** `{result['verification_id']}`

⏰ Processing time: Usually 24-48 hours
📊 Success rate: ~70-85%

Good luck! 🍀
"""

            keyboard = []
            if result.get('redirect_url'):
                keyboard.append([InlineKeyboardButton("🔗 Open Verification Page", url=result['redirect_url'])])
            keyboard.append([InlineKeyboardButton("🔄 New Verification", callback_data='start_verify')])

            reply_markup = InlineKeyboardMarkup(keyboard)

            await processing_msg.edit_text(
                success_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

            # Notify admin (if configured)
            if ADMIN_USER_ID:
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_USER_ID,
                        text=f"✅ Successful verification\nUser: {user_id}\nSchool: {info['school']}"
                    )
                except:
                    pass

        else:
            # Failure message
            error_text = f"""
❌ **Verification Failed**

{result['message']}

**Verification ID:** `{result['verification_id']}`

**Possible reasons:**
• Invalid verification URL
• Verification already completed
• SheerID API temporary issue
• Network connectivity problem

**What to do:**
1. Try again with a fresh verification URL
2. Wait a few minutes and retry
3. Contact support if problem persists

Use /verify to try again.
"""

            keyboard = [[InlineKeyboardButton("🔄 Try Again", callback_data='start_verify')]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await processing_msg.edit_text(
                error_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

    except Exception as e:
        logger.error(f"Error processing verification: {e}")

        await processing_msg.edit_text(
            f"❌ **Unexpected Error**\n\n"
            f"An error occurred during verification:\n"
            f"`{str(e)}`\n\n"
            f"Please try again or contact support.\n\n"
            f"Use /verify to retry.",
            parse_mode='Markdown'
        )

# ============================================================================
# Callback Query Handlers
# ============================================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks"""
    query = update.callback_query
    await query.answer()

    if query.data == 'start_verify':
        user_id = query.from_user.id
        user_states[user_id] = 'waiting_url'

        await query.message.reply_text(
            "📝 Please send me your SheerID verification URL.\n\n"
            "Example: `https://services.sheerid.com/verify/xxxxx/?verificationId=abc123...`",
            parse_mode='Markdown'
        )

    elif query.data == 'help':
        await help_command(update, context)

# ============================================================================
# Error Handler
# ============================================================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")

    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred. Please try again or contact support."
        )

# ============================================================================
# Main Function
# ============================================================================

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found in .env file!")
        return

    logger.info("🚀 Starting SheerID Telegram Bot...")

    # Create application
    app = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("verify", verify_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("cancel", cancel_command))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))

    app.add_error_handler(error_handler)

    # Start bot
    logger.info("✅ Bot is running... Press Ctrl+C to stop")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
