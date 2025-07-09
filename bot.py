from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from supabase import create_client
import logging

# ======= CONFIG =======
BOT_TOKEN = "6870953348:AAEFkEPhdkV1fcFrzKvc203LjmYgsjB9mog"
SUPABASE_URL = "https://cbdrjkxlyxijcvlypcvw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNiZHJqa3hseXhpamN2bHlwY3Z3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTk0Mjg2NiwiZXhwIjoyMDY3NTE4ODY2fQ.twQPq5ULhhrCoOWfnSZjVdU-atLeA3chuR22RKC6ahI"
ADMIN_CHAT_ID = 76514915 

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
logging.basicConfig(level=logging.INFO)

# ======= COMMAND: /start =======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎁 View My Vouchers", callback_data="view_vouchers")],
        [InlineKeyboardButton("✅ My Claimed Vouchers", callback_data="my_claimed_vouchers")]
    ]
    await update.message.reply_text("👋 Welcome! Choose an option:", reply_markup=InlineKeyboardMarkup(keyboard))

# ======= CALLBACK HANDLER =======
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    user_id = str(user.id)
    username = user.username or user.first_name
    await query.answer()

    if query.data == "back_main":
        # Show main menu again
        keyboard = [
            [InlineKeyboardButton("🎁 View My Vouchers", callback_data="view_vouchers")],
            [InlineKeyboardButton("✅ My Claimed Vouchers", callback_data="my_claimed_vouchers")]
        ]
        await query.edit_message_text("👋 Welcome! Choose an option:", reply_markup=InlineKeyboardMarkup(keyboard))

    # VIEW ALL VOUCHERS
    elif query.data == "view_vouchers":
        vouchers = supabase.table("vouchers").select("*").eq("claimed", False).execute().data
        if not vouchers:
            await query.edit_message_text(
            "🚫 No vouchers available.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]])
            )
            return

        keyboard = []
        for v in vouchers:
            keyboard.append([
                InlineKeyboardButton(v["name"], callback_data=f"voucher_{v['id']}")
            ])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
        await query.edit_message_text("🎁 Available Vouchers:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # VIEW CLAIMED VOUCHERS
    
    elif query.data == "my_claimed_vouchers":
        # Query vouchers claimed by user
        claims = supabase.table("voucher_claims").select("voucher_id").eq("user_id", user_id).execute().data
        if not claims:
            await query.edit_message_text("🚫 You have not claimed any vouchers yet.",
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]))
            return

        voucher_ids = [c["voucher_id"] for c in claims]
        vouchers = supabase.table("vouchers").select("*").in_("id", voucher_ids).execute().data

        keyboard = []
        for v in vouchers:
            keyboard.append([InlineKeyboardButton(v["name"], callback_data=f"claimed_voucher_{v['id']}")])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
        await query.edit_message_text("✅ Your Claimed Vouchers:", reply_markup=InlineKeyboardMarkup(keyboard))

    # VIEW CLAIMED VOUCHERS DETAILS

    elif query.data.startswith("claimed_voucher_"):
        voucher_id = query.data.split("_", 2)[2]
        voucher = supabase.table("vouchers").select("*").eq("id", voucher_id).single().execute().data
        if not voucher:
            await query.edit_message_text("⚠️ Voucher not found.",
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]))
            return

        msg = (f"🎟️ *{voucher['name']}*\n\n"
               f"*Description:* {voucher['description']}\n"
               f"*Quantity Left:* {voucher['quantity']}")

        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="my_claimed_vouchers")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # SHOW VOUCHER DETAILS
    elif query.data.startswith("voucher_"):
        voucher_id = query.data.split("_", 1)[1]
        voucher = supabase.table("vouchers").select("*").eq("id", voucher_id).single().execute().data

        if not voucher:
            await query.edit_message_text("⚠️ Voucher not found.")
            return

        # Check if user already claimed
        already = supabase.table("voucher_claims")\
            .select("id")\
            .eq("voucher_id", voucher_id)\
            .eq("user_id", user_id).execute().data

        claimed = bool(already)
        msg = f"🎟️ *{voucher['name']}*\n\n" \
              f"*Description:* {voucher['description']}\n" \
              f"*Quantity Left:* {voucher['quantity']}\n" \
              f"*Claimed by you:* {'✅ Yes' if claimed else '❌ No'}"

        keyboard = []
        if claimed:
            keyboard = [[InlineKeyboardButton("✅ Already Claimed", callback_data="noop")]]
        elif voucher["quantity"] > 0:
            keyboard = [[InlineKeyboardButton("🎉 Claim Now", callback_data=f"claim_{voucher_id}")]]
        else:
            keyboard = [[InlineKeyboardButton("🚫 Out of Stock", callback_data="noop")]]
            
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="view_vouchers")])
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # CLAIM VOUCHER
    elif query.data.startswith("claim_"):
        voucher_id = query.data.split("_", 1)[1]

        # Check again
        voucher = supabase.table("vouchers").select("*").eq("id", voucher_id).single().execute().data
        if not voucher or voucher["quantity"] <= 0:
            await query.answer("⚠️ This voucher is no longer available.", show_alert=True)
            return

        already = supabase.table("voucher_claims")\
            .select("id")\
            .eq("voucher_id", voucher_id)\
            .eq("user_id", user_id).execute().data

        if already:
            await query.answer("You already claimed this voucher.", show_alert=True)
            return

        # Record claim
        supabase.table("voucher_claims").insert({
            "voucher_id": voucher_id,
            "user_id": user_id,
            "username": username
        }).execute()

        # Decrease quantity
        new_qty = voucher["quantity"] - 1
        claimed_flag = new_qty == 0

        supabase.table("vouchers").update({
            "quantity": new_qty,
            "claimed": claimed_flag
        }).eq("id", voucher_id).execute()

        # Notify admin
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"🔔 @{username} claimed *{voucher['name']}*", parse_mode="Markdown"
        )

        await query.answer("🎉 You’ve successfully claimed this voucher!")
        await button_handler(update, context)  # Refresh view

    elif query.data == "noop":
        await query.answer("Nothing to do here.", show_alert=True)

# ======= MAIN =======
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

if __name__ == "__main__":
    main()
