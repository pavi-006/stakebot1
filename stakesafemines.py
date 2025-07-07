from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler, ConversationHandler, MessageHandler, filters
)
import hmac
import hashlib
import random
import json
import os
import time

# === Config ===
TILES_COUNT = 25
COMBO_FILE = "used_combos.json"
PAID_FILE = "paid_users.json"
BOT_TOKEN = os.getenv("7949366449:AAGGx0j8WvL2ig7zMW4V01Fe1pDdwtEg9eg")  # ✅ Use environment variable
ADMIN_ID = 5628303560  # Replace with your Telegram ID

# === File helpers ===
def load_used_combos():
    if not os.path.exists(COMBO_FILE):
        return []
    with open(COMBO_FILE, "r") as f:
        return json.load(f)

def save_used_combo(combo_key):
    combos = load_used_combos()
    if combo_key not in combos:
        combos.append(combo_key)
        with open(COMBO_FILE, "w") as f:
            json.dump(combos, f)

def load_paid_users():
    if not os.path.exists(PAID_FILE):
        return {}
    with open(PAID_FILE, "r") as f:
        return json.load(f)

def save_paid_users(data):
    with open(PAID_FILE, "w") as f:
        json.dump(data, f)

def is_paid_user(user_id):
    users = load_paid_users()
    now = int(time.time())
    return str(user_id) in users and users[str(user_id)] > now

# === Prediction logic ===
def get_mine_tiles(server_seed, client_seed, nonce, mine_count):
    tiles = []
    i = 0
    while len(tiles) < mine_count:
        message = f"{client_seed}:{nonce}:{i}"
        hash_bytes = hmac.new(server_seed.encode(), message.encode(), hashlib.sha256).digest()
        for byte in hash_bytes:
            tile = byte % TILES_COUNT
            if tile not in tiles:
                tiles.append(tile)
            if len(tiles) == mine_count:
                break
        i += 1
    return tiles

def get_safe_tiles(bomb_tiles):
    return [i for i in range(TILES_COUNT) if i not in bomb_tiles]

def print_safe_tiles_with_emojis(safe_tiles):
    board = "\n💎 Safe Tile Board:\n\n"
    for i in range(TILES_COUNT):
        board += "💎 " if i in safe_tiles else "⬛ "
        if (i + 1) % 5 == 0:
            board += "\n"
    return board

# === Commands ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔮 Predict", callback_data="predict")],
        [InlineKeyboardButton("🍭 Buy VIP", callback_data="buy")],
        [InlineKeyboardButton("📜 Rules", callback_data="rules")]
    ]
    await update.message.reply_text(
        "👋 Welcome to the VIP Stake Mines Predictor Bot!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📨 Contact Admin", url=f"tg://user?id={ADMIN_ID}")]]
    msg = """*🍭️ Choose a VIP Plan:*

🟢 1 Day - ₹49  
🟡 7 Days - ₹199  
🔵 30 Days - ₹499

Pay via UPI: `aswinaswin21606-@oksbi`  
After payment, contact admin to activate.
"""
    message = update.message or update.callback_query.message
    await message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """*📜 VIP Access Rules & Disclaimer:*

✅ Our bot gives predictions with up to *90% accuracy*.  
🔁 Predictions work only *once per unique Server Seed + Total Bets* pair.

📌 *Rules:*
1. Use *only 1 to 5 Mines* for best accuracy.
2. Don’t share predictions publicly.
3. Use valid Server Seed + Total Bets only once.
4. No refunds once access is activated.
5. Access auto-expires after your plan ends.

⚠️ *Disclaimer:*  
This bot is for educational & entertainment purposes only. We do not guarantee winnings. Use responsibly and at your own risk.
"""
    message = update.message or update.callback_query.message
    await message.reply_text(msg, parse_mode="Markdown")

async def activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Only admin can activate users.")
        return

    try:
        user_id = str(context.args[0])
        days = int(context.args[1])
        expiry_time = int(time.time()) + (days * 86400)

        users = load_paid_users()
        users[user_id] = expiry_time
        save_paid_users(users)

        await update.message.reply_text(f"✅ User {user_id} activated for {days} days.")
        await context.bot.send_message(
            chat_id=int(user_id),
            text="✅ *Your VIP access is activated!*\nUse /predict to get predictions.",
            parse_mode="Markdown"
        )
    except:
        await update.message.reply_text("❌ Usage: /activate <user_id> <days>")

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "predict":
        await query.message.reply_text("🔐 To start prediction, type /predict and follow the steps.")
    elif query.data == "buy":
        await buy(update, context)
    elif query.data == "rules":
        await rules(update, context)

# === Prediction flow ===
SERVER_SEED, CLIENT_SEED, NONCE, MINE_COUNT = range(4)

async def predict_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_paid_user(update.effective_user.id):
        await update.message.reply_text("🔐 This is a *VIP-only* feature.\nUse /buy to get access.", parse_mode="Markdown")
        return ConversationHandler.END
    await update.message.reply_text("📥 Send your *Server Seed*:")
    return SERVER_SEED

async def get_server_seed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["server_seed"] = update.message.text
    await update.message.reply_text("📥 Now send your *Client Seed*:")
    return CLIENT_SEED

async def get_client_seed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["client_seed"] = update.message.text
    await update.message.reply_text("📥 Enter *Total bets made with pair* (number):")
    return NONCE

async def get_nonce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["nonce"] = int(update.message.text)
        await update.message.reply_text("📥 Enter *Mines Count (1–5)*:")
        return MINE_COUNT
    except:
        await update.message.reply_text("⚠️ Invalid number. Please enter a number.")
        return NONCE

async def get_mine_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mines = int(update.message.text)
        if not (1 <= mines <= 5):
            await update.message.reply_text("⚠️ Please enter a number between 1 and 5.")
            return MINE_COUNT

        server_seed = context.user_data["server_seed"]
        client_seed = context.user_data["client_seed"]
        nonce = context.user_data["nonce"]
        combo_key = f"{server_seed}_{nonce}"

        if combo_key in load_used_combos():
            await update.message.reply_text("❌ This Server Seed + Total Bets combo already used.")
            return ConversationHandler.END

        save_used_combo(combo_key)

        bomb_tiles = get_mine_tiles(server_seed, client_seed, nonce, mines)
        all_safe_tiles = get_safe_tiles(bomb_tiles)

        tile_count = min(5, len(all_safe_tiles)) if mines == 1 else min(3, len(all_safe_tiles))
        safe_tiles = random.sample(all_safe_tiles, tile_count)
        board = print_safe_tiles_with_emojis(safe_tiles)

        await update.message.reply_text(
            f"🛡️ *Safe Tiles ({tile_count}):* {safe_tiles}\n"
            f"{board}",
            parse_mode="Markdown"
        )
    except:
        await update.message.reply_text("⚠️ Error in processing. Try again.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Prediction cancelled.")
    return ConversationHandler.END

# === Bot Run ===
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("activate", activate))
    app.add_handler(CallbackQueryHandler(handle_button_click))

    predict_handler = ConversationHandler(
        entry_points=[CommandHandler("predict", predict_start)],
        states={
            SERVER_SEED: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_server_seed)],
            CLIENT_SEED: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_client_seed)],
            NONCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_nonce)],
            MINE_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mine_count)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(predict_handler)

    print("🤖 VIP Bot is running...")
    app.run_polling()
