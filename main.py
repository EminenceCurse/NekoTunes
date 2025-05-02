import os
import asyncio
import html
from time import monotonic as time
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.enums import ParseMode
from bs4 import BeautifulSoup
from youtube_search import YoutubeSearch
import yt_dlp

# Bot credentials
API_ID = "API_ID"
API_HASH = "API_HASH"
BOT_TOKEN = "BOT_TOKEN"
GENIUS_API_KEY = "for_geniues_api_contact_me_on_tg_@TheErenYeager"

# Initialize bot
app = Client("NekoTuneUltraBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Anti-spam
user_last_message_time = {}
user_command_count = {}
SPAM_THRESHOLD = 2
SPAM_WINDOW_SECONDS = 5

# Ensure downloads folder exists
os.makedirs("downloads", exist_ok=True)

# Caption
caption = """**Welcome to Nekotune!** Your ultimate lightning-fast music bot.

**Commands:**
• /song [song name] – Download any song
• /lyrics [song name] – Get song lyrics

**Need Help?** Join [Support](https://t.me/Ahjin_sprt)

**Bot by:** @TheErenYeager"""

# --- Lyrics Function ---
async def fetch_lyrics(song):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.genius.com/search?q={song}&access_token={GENIUS_API_KEY}", timeout=7
            ) as resp:
                data = await resp.json()
                hits = data.get("response", {}).get("hits", [])
                if not hits:
                    return "❌ No lyrics found."

                lyrics_url = hits[0]["result"].get("url")
                async with session.get(lyrics_url, timeout=7) as page:
                    html_content = await page.text()
                    soup = BeautifulSoup(html_content, "html.parser")
                    divs = soup.find_all("div", {"data-lyrics-container": "true"})
                    lyrics = "\n".join(div.get_text(strip=True, separator="\n") for div in divs)
                    return f"<b>{html.escape(hits[0]['result']['title'])}</b> by <i>{html.escape(hits[0]['result']['primary_artist']['name'])}</i>\n\n<pre>{html.escape(lyrics[:4096])}</pre>"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# --- Start Command ---
@app.on_message(filters.command("start"))
async def start(_, message: Message):
    image_url = "https://files.catbox.moe/p5m63t.jpg"
    buttons = [
        [InlineKeyboardButton("Support", url="https://t.me/Ahjin_sprt"),
         InlineKeyboardButton("Updates", url="https://t.me/Erenbots")],
        [InlineKeyboardButton("Help", callback_data="help_menu")]
    ]
    await message.reply_photo(image_url, caption=caption, reply_markup=InlineKeyboardMarkup(buttons))

# --- Help Callback ---
@app.on_callback_query(filters.regex("help_menu"))
async def help_callback(_, query: CallbackQuery):
    await query.message.edit_text(
        "**NekoTune Help Menu**\n\n"
        "**/song [name]** - Download any song\n"
        "**/lyrics [name]** - Get lyrics instantly",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="go_back")]])
    )

@app.on_callback_query(filters.regex("go_back"))
async def back_to_start(_, query: CallbackQuery):
    buttons = [
        [InlineKeyboardButton("Support", url="https://t.me/Ahjin_sprt"),
         InlineKeyboardButton("Updates", url="https://t.me/Erenbots")],
        [InlineKeyboardButton("Help", callback_data="help_menu")]
    ]
    await query.message.edit_caption(caption, reply_markup=InlineKeyboardMarkup(buttons))

# --- Song Command ---
@app.on_message(filters.command("song"))
async def download_song(_, message: Message):
    user_id = message.from_user.id
    now = time()
    last = user_last_message_time.get(user_id, 0)

    if now - last < SPAM_WINDOW_SECONDS:
        user_command_count[user_id] = user_command_count.get(user_id, 0) + 1
        if user_command_count[user_id] > SPAM_THRESHOLD:
            warn = await message.reply_text("⚠️ Avoid spamming. Wait a few seconds.")
            await asyncio.sleep(3)
            return await warn.delete()
    else:
        user_command_count[user_id] = 1
        user_last_message_time[user_id] = now

    query = " ".join(message.command[1:])
    if not query:
        return await message.reply_text("**Usage:** /song [song name]", parse_mode=ParseMode.MARKDOWN)

    m = await message.reply_text("🔍 Searching...")
    try:
        results = YoutubeSearch(query, max_results=1).to_dict()
        if not results:
            return await m.edit("❌ No results found.")

        link = f"https://youtube.com{results[0]['url_suffix']}"
        title = results[0]['title']
        duration = results[0]['duration']

        await m.edit("📥 Downloading...")

        ydl_opts = {
            'format': 'bestaudio[ext=m4a]',
            'quiet': True,
            'noplaylist': True,
            'outtmpl': 'downloads/%(title)s.%(ext)s',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            filename = ydl.prepare_filename(info)

        dur = sum(int(x) * 60 ** i for i, x in enumerate(reversed(duration.split(":"))))

        await m.edit("📤 Uploading...")
        try:
            await message.reply_audio(
                audio=filename,
                title=title,
                duration=dur,
                caption=f"🎵 {title}\nRequested by: {message.from_user.mention}"
            )
        except Exception as e:
            await m.edit("❌ Upload failed. File too large or error.")
            print(e)
        else:
            await m.delete()
        finally:
            if os.path.exists(filename):
                os.remove(filename)

    except Exception as e:
        await m.edit("❌ Failed to download.")
        print(e)

# --- Lyrics Command ---
@app.on_message(filters.command("lyrics"))
async def lyrics_cmd(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** /lyrics [song name]", parse_mode=ParseMode.MARKDOWN)
    song = " ".join(message.command[1:])
    m = await message.reply_text("🎤 Fetching lyrics...")
    lyrics = await fetch_lyrics(song)
    await m.edit(lyrics, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

# --- Run Bot ---
if __name__ == "__main__":
    app.run()