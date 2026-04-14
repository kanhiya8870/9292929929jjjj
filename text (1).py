import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
import yt_dlp

# ================= CONFIGURATION =================
API_ID = 30842203  # Apna API ID daalo
API_HASH = "6b64dd14b635b99d5bb820448542f45b"
BOT_TOKEN = "8597654224:AAGifQaQBFOaputrPnwsx7-WRt_a1BgG9vE"

OWNER_ID = 7204275439  # APNI TELEGRAM USER ID YAHA DAALO
# =================================================

# Global Variables
AUTHORIZED_USERS = [OWNER_ID]
TARGET_GROUP = None  # Jiss group me play karna hai
queue = []
is_playing = False

# Clients setup
bot = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
userbot = Client("user_session", api_id=API_ID, api_hash=API_HASH)
call = PyTgCalls(userbot)

# State management for login
login_state = {}

# Filter: Sirf private chat aur authorized users ke liye
def auth_private(func):
    async def wrapper(client, message):
        if message.chat.type != getattr(message.chat.type, "PRIVATE", "private"):
            return # GC me kuch reply nahi karega
        if message.from_user.id not in AUTHORIZED_USERS:
            await message.reply("Aapko is bot ko use karne ka access nahi hai.")
            return
        return await func(client, message)
    return wrapper

@bot.on_message(filters.command("start"))
@auth_private
async def start(client, message):
    await message.reply("Bot chalu hai! 🎵\n\nCommands:\n/login - Number se login karne ke liye\n/setgroup <group_id> - Target group set karne ke liye\n/play <song name> - Gaana bajane ke liye\n/next - Agla gaana\n/stop - Band karne ke liye\n/auth <user_id> - Kisi aur ko access dene ke liye (Only Owner)")

@bot.on_message(filters.command("auth"))
@auth_private
async def auth_user(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("Sirf owner access de sakta hai.")
    try:
        new_user = int(message.text.split()[1])
        if new_user not in AUTHORIZED_USERS:
            AUTHORIZED_USERS.append(new_user)
            await message.reply(f"User {new_user} ko access mil gaya hai!")
    except:
        await message.reply("Sahi format: `/auth user_id`")

@bot.on_message(filters.command("setgroup"))
@auth_private
async def set_group(client, message):
    global TARGET_GROUP
    try:
        TARGET_GROUP = int(message.text.split()[1])
        await message.reply(f"Target group set ho gaya: {TARGET_GROUP}\nAb aap /play use kar sakte hain.")
    except:
        await message.reply("Sahi format: `/setgroup -100123456789`")

# ================= LOGIN SYSTEM =================
@bot.on_message(filters.command("login"))
@auth_private
async def login_start(client, message):
    user_id = message.from_user.id
    login_state[user_id] = {"step": "phone"}
    await message.reply("Apna mobile number country code ke sath bhejo. (Example: +919876543210)")

@bot.on_message(filters.text & ~filters.command(["play", "stop", "next", "start", "setgroup", "auth"]))
@auth_private
async def login_process(client, message):
    user_id = message.from_user.id
    if user_id not in login_state:
        return

    state = login_state[user_id]["step"]

    if state == "phone":
        phone = message.text
        login_state[user_id]["phone"] = phone
        await message.reply("OTP bheja ja raha hai, wait karo...")
        try:
            await userbot.connect()
            sent_code = await userbot.send_code(phone)
            login_state[user_id]["phone_code_hash"] = sent_code.phone_code_hash
            login_state[user_id]["step"] = "otp"
            await message.reply("Aapke Telegram par OTP aaya hoga.\nOTP ko is format me bhejo: `1 2 3 4 5` (Spaces ke sath, taaki telegram error na de)")
        except Exception as e:
            await message.reply(f"Error: {e}")
            del login_state[user_id]

    elif state == "otp":
        otp = message.text.replace(" ", "")
        phone = login_state[user_id]["phone"]
        phone_code_hash = login_state[user_id]["phone_code_hash"]
        try:
            await userbot.sign_in(phone, phone_code_hash, otp)
            await message.reply("✅ Login successful! Bot ab gaane play kar sakta hai.")
            await call.start()
            del login_state[user_id]
        except Exception as e:
            await message.reply(f"Login failed: {e}")
            del login_state[user_id]

# ================= MUSIC PLAYER SYSTEM =================
def get_audio_url(query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        if 'entries' in info:
            info = info['entries'][0]
        return info['url'], info['title']

@bot.on_message(filters.command("play"))
@auth_private
async def play_song(client, message):
    global is_playing, TARGET_GROUP
    if not TARGET_GROUP:
        return await message.reply("Pehle target group set karo: `/setgroup group_id`")
    
    query = message.text.split(" ", 1)
    if len(query) < 2:
        return await message.reply("Gaane ka naam bhi likho: `/play tum hi ho`")
    
    query = query[1]
    m = await message.reply("🔍 Gaana dhundh raha hu...")
    
    try:
        url, title = get_audio_url(query)
        queue.append({"url": url, "title": title})
        
        if not is_playing:
            song = queue.pop(0)
            await call.play(TARGET_GROUP, MediaStream(song["url"]))
            is_playing = True
            await m.edit_text(f"▶️ Play ho raha hai: **{song['title']}**")
        else:
            await m.edit_text(f"✅ Queue me add ho gaya: **{title}**")
    except Exception as e:
        await m.edit_text(f"❌ Error: {e}")

@bot.on_message(filters.command("next"))
@auth_private
async def next_song(client, message):
    global is_playing
    if len(queue) > 0:
        song = queue.pop(0)
        await call.play(TARGET_GROUP, MediaStream(song["url"]))
        await message.reply(f"⏭️ Next song play ho raha hai: **{song['title']}**")
    else:
        await call.leave_call(TARGET_GROUP)
        is_playing = False
        await message.reply("Queue khatam ho gayi hai. Call leave kar di.")

@bot.on_message(filters.command("stop"))
@auth_private
async def stop_song(client, message):
    global is_playing, queue
    queue.clear()
    try:
        await call.leave_call(TARGET_GROUP)
    except:
        pass
    is_playing = False
    await message.reply("🛑 Song stop kar diya aur queue clear kar di.")

# Auto play next when song ends
@call.on_stream_end()
async def stream_end_handler(client, update):
    global is_playing
    if len(queue) > 0:
        song = queue.pop(0)
        await call.play(TARGET_GROUP, MediaStream(song["url"]))
    else:
        await call.leave_call(TARGET_GROUP)
        is_playing = False

# ================= STARTUP =================
async def main():
    await bot.start()
    print("Bot is running...")
    # Check if userbot is already logged in
    try:
        await userbot.start()
        await call.start()
        print("Userbot is logged in and PyTgCalls started.")
    except:
        print("Userbot login nahi hai. Pehle bot me /login command use karo.")
    
    await pyrogram.idle()

if __name__ == "__main__":
    asyncio.run(main())