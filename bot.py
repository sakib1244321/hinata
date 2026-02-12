# -*- coding: utf-8 -*-
import asyncio
import logging
import json
import os
import time
from datetime import timedelta
from aiohttp import ClientSession
from telegram import Update, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ChatMemberHandler
)

# ================= Configuration =================
OWNER_ID = 7333244376
BOT_TOKEN_FILE = "token.txt"
BOT_NAME = "Hinata"
BOT_USERNAME = "@Hinata_00_bot"

INBOX_FORWARD_GROUP_ID = -1003113491147

TRACKED_USER1_ID = 7039869055
FORWARD_USER1_GROUP_ID = -1002768142169
TRACKED_USER2_ID = 7209584974
FORWARD_USER2_GROUP_ID = -1002536019847

SOURCE_GROUP_ID = -4767799138
DESTINATION_GROUP_ID = -1002510490386

KEYWORDS = [
    "shawon", "shawn", "sn", "@shawonxnone", "shwon", "shaun", "sahun", "sawon",
    "sawn", "nusu", "nusrat", "saun", "ilma", "izumi", "Shaown", "izu",
    "🎀꧁𖨆❦︎ 𝑰𝒁𝑼𝑴𝑰 𝑼𝒄𝒉𝒊𝒉𝒂 ❦︎𖨆꧂🎀"
]

LOG_FILE = "hinata.log"
MAX_LOG_SIZE = 200 * 1024  # 200 KB

CHATGPT_API_URL = "https://addy-chatgpt-api.vercel.app/?text={prompt}"
GEMINI_API_KEY = "AIzaSyCIt7ga9JtU36JpJy54aKX2l1UWpxFBtPE"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# ================= Logging =================
def setup_logger():
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
        with open(LOG_FILE, "w") as f:
            f.write("")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
    )
    return logging.getLogger("hinata")

logger = setup_logger()

# ================= Load token =================
def read_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

BOT_TOKEN = read_file(BOT_TOKEN_FILE)

# ================= Helpers =================
def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

start_time = time.time()
def get_uptime() -> str:
    elapsed = time.time() - start_time
    return str(timedelta(seconds=int(elapsed)))

def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default if default is not None else []

def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ================= Forward Helper =================
async def forward_or_copy(update: Update, context: ContextTypes.DEFAULT_TYPE, command_text: str = None):
    user = update.effective_user
    msg_type = "Command" if command_text else "Message"
    try:
        caption = f"📨 From: {user.full_name} (@{user.username})\nID: <code>{user.id}</code>\nType: {msg_type}"
        if command_text:
            caption += f"\nCommand: {command_text}"
        elif update.message and update.message.text:
            caption += f"\nMessage: {update.message.text}"

        await context.bot.send_message(chat_id=INBOX_FORWARD_GROUP_ID, text=caption, parse_mode="HTML")
        if update.message:
            await update.message.forward(chat_id=INBOX_FORWARD_GROUP_ID)
    except Exception as e:
        if update.message:
            try:
                text = update.message.text or "<Media/Sticker/Other>"
                safe_text = f"📨 From: {user.full_name} (@{user.username})\nID: <code>{user.id}</code>\nType: {msg_type}\nContent: {text}"
                await context.bot.send_message(chat_id=INBOX_FORWARD_GROUP_ID, text=safe_text, parse_mode="HTML")
            except Exception as e2:
                logger.warning(f"Failed to copy message: {e2}")
        logger.warning(f"Failed to forward: {e}")

# ================= Commands =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_or_copy(update, context, "/start")
    user = update.effective_user
    users = read_json("users.json", [])
    if user.id not in users:
        users.append(user.id)
        write_json("users.json", users)

    msg = (f"👤 <b>New User Started Bot</b>\n"
           f"Name: {user.full_name}\nUsername: @{user.username}\nID: <code>{user.id}</code>")
    await context.bot.send_message(chat_id=OWNER_ID, text=msg, parse_mode="HTML")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await forward_or_copy(update, context, "/ping")
    start_ping = time.time()
    msg = await update.message.reply_text("🏓 Pinging...")
    ping_ms = int((time.time() - start_ping) * 1000)
    await msg.edit_text(
        f"💫 <i>Hi! I’m {BOT_NAME}</i>\n\n"
        f"🤖 <i>Bot Username:</i> <code>{BOT_USERNAME}</code>\n"
        f"⚡ <i>Ping:</i> <code>{ping_ms} ms</code>\n"
        f"🕒 <i>Uptime:</i> <code>{get_uptime()}</code>\n"
        f"📡 <i>Status:</i> Active ✅",
        parse_mode="HTML"
    )

# ================= AI Commands =================
async def fetch_chatgpt(session, prompt):
    url = CHATGPT_API_URL.format(prompt=prompt.replace(" ", "+"))
    async with session.get(url) as resp:
        data = await resp.json()
        return data.get("reply", "No reply from ChatGPT.")

async def fetch_gemini(session, prompt):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    headers = {"Content-Type": "application/json", "X-goog-api-key": GEMINI_API_KEY}
    async with session.post(GEMINI_API_URL, headers=headers, json=payload) as resp:
        data = await resp.json()
        try:
            return data["candidates"][0]["content"][0]["text"]
        except:
            return "No reply from Gemini."

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /ai <prompt>")
        return
    prompt = " ".join(context.args)
    await forward_or_copy(update, context, "/ai " + prompt)
    msg = await update.message.reply_text("🤖 Asking AI...")

    async with ClientSession() as session:
        chatgpt_task = fetch_chatgpt(session, prompt)
        gemini_task = fetch_gemini(session, prompt)
        chatgpt_reply, gemini_reply = await asyncio.gather(chatgpt_task, gemini_task)

    text = f"💡 <b>AI Responses</b>\n\nChatGPT:\n{chatgpt_reply}\n\nGemini:\n{gemini_reply}"
    await msg.edit_text(text, parse_mode="HTML")

# ================= Broadcasts =================
def update_stats(sent_users=0, failed_users=0, sent_groups=0, failed_groups=0):
    stats = read_json("stats.json", {"sent_users":0,"failed_users":0,"sent_groups":0,"failed_groups":0})
    stats["sent_users"] += sent_users
    stats["failed_users"] += failed_users
    stats["sent_groups"] += sent_groups
    stats["failed_groups"] += failed_groups
    write_json("stats.json", stats)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /broadcast <group_id> <message>")
        return
    group_id = int(context.args[0])
    text = " ".join(context.args[1:])
    sent = failed = 0
    try:
        await context.bot.send_message(chat_id=group_id, text=text)
        sent += 1
    except:
        failed += 1
    await update.message.reply_text(f"✅ Sent: {sent}, ❌ Failed: {failed}")
    update_stats(sent_users=0, sent_groups=sent, failed_groups=failed)

async def broadcastall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcastall <message>")
        return
    text = " ".join(context.args)
    groups = read_json("groups.json", [])
    sent = failed = 0
    for gid in groups:
        try:
            await context.bot.send_message(chat_id=gid, text=text)
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(f"✅ Sent: {sent}, ❌ Failed: {failed}")
    update_stats(sent_groups=sent, failed_groups=failed)

async def broadcast_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /broadcast_media <media_url> <caption>")
        return
    media_url = context.args[0]
    caption = " ".join(context.args[1:])
    groups = read_json("groups.json", [])
    sent = failed = 0
    for gid in groups:
        try:
            await context.bot.send_photo(chat_id=gid, photo=media_url, caption=caption)
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(f"✅ Sent: {sent}, ❌ Failed: {failed}")
    update_stats(sent_groups=sent, failed_groups=failed)

# ================= Message Handler =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return

    # Forward private messages
    if msg.chat.type == "private":
        await forward_or_copy(update, context)

    # Keyword alerts
    if msg.text:
        lowered = msg.text.lower()
        for keyword in KEYWORDS:
            if keyword.lower() in lowered:
                alert = (
                    f"🚨 <b>Keyword Mention Detected!</b>\n"
                    f"<b>Keyword:</b> <code>{keyword}</code>\n"
                    f"<b>From:</b> {msg.from_user.full_name} (@{msg.from_user.username})\n"
                    f"<b>Group:</b> {msg.chat.title if msg.chat.title else 'Private'}\n"
                    f"<b>Message:</b> {msg.text}"
                )
                await context.bot.send_message(chat_id=OWNER_ID, text=alert, parse_mode="HTML")
                break

    # Tracked users forwarding
    try:
        if msg.from_user.id == TRACKED_USER1_ID:
            await context.bot.send_message(chat_id=FORWARD_USER1_GROUP_ID,
                                           text=f"📨 Message from tracked user in <b>{msg.chat.title}</b>",
                                           parse_mode="HTML")
            await msg.forward(chat_id=FORWARD_USER1_GROUP_ID)
        if msg.from_user.id == TRACKED_USER2_ID:
            await context.bot.send_message(chat_id=FORWARD_USER2_GROUP_ID,
                                           text=f"📨 Message from tracked user in <b>{msg.chat.title}</b>",
                                           parse_mode="HTML")
            await msg.forward(chat_id=FORWARD_USER2_GROUP_ID)
    except:
        pass

    # Source -> Destination
    if msg.chat.id == SOURCE_GROUP_ID:
        try:
            await msg.forward(chat_id=DESTINATION_GROUP_ID)
        except:
            if msg.text:
                copy_text = f"📨 From: {msg.from_user.full_name} (@{msg.from_user.username})\nContent: {msg.text}"
                await context.bot.send_message(chat_id=DESTINATION_GROUP_ID, text=copy_text)

# ================= Group Tracking =================
async def track_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.my_chat_member.chat
    if chat.type in ["group", "supergroup"]:
        groups = read_json("groups.json", [])
        if chat.id not in groups:
            groups.append(chat.id)
            write_json("groups.json", groups)

# ================= Run Bot =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("ai", ai_command))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("broadcastall", broadcastall))
    app.add_handler(CommandHandler("broadcast_media", broadcast_media))

    # Message handler
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    # Track bot added to group
    app.add_handler(ChatMemberHandler(track_group, ChatMemberHandler.MY_CHAT_MEMBER))

    logger.info("Hinata Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()