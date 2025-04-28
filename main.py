import os
import asyncio
import html
from time import time
import requests
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from bs4 import BeautifulSoup
from youtube_search import YoutubeSearch
import yt_dlp

# Bot credentials
API_ID = "api_id"
API_HASH = "api_hash"
BOT_TOKEN = "bot_token"

# Genius API Key
GENIUS_API_KEY = "contact_me_on_tg_for_api_@TheErenYeager"

# Initialize the bot client
app = Client("NekoTunes, api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Optimized session for lyrics
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

# Path to cookies file
COOKIES_FILE = 'Cookies/cookies.txt'

# Anti-spam control
user_last_message_time = {}
user_command_count = {}
SPAM_THRESHOLD = 2
SPAM_WINDOW_SECONDS = 5

# --- Lyrics Functions ---
def scrape_lyrics(url):
    try:
        response = session.get(url, timeout=10)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        lyrics_divs = soup.find_all("div", attrs={"data-lyrics-container": "true"})

        if not lyrics_divs:
            return "❌ **Couldn't extract lyrics from Genius.**"

        lyrics = "\n".join(div.get_text(separator="\n", strip=True) for div in lyrics_divs)
        return html.escape(lyrics)

    except Exception as e:
        return f"❌ **Error fetching lyrics:** {str(e)}"

def fetch_lyrics(song_name):
    try:
        search_url = f"https://api.genius.com/search?q={song_name}&access_token={GENIUS_API_KEY}"
        response = session.get(search_url, timeout=10)

        if response.status_code != 200:
            return f"❌ **API Error {response.status_code}:** Unable to fetch lyrics."

        data = response.json()
        hits = data.get("response", {}).get("hits", [])

        if not hits:
            return "❌ **No lyrics found** for this song."

        song_info = hits[0]["result"]
        lyrics_url = song_info.get("url")

        if not lyrics_url:
            return "❌ **Error:** Lyrics URL not found."

        lyrics = scrape_lyrics(lyrics_url)
        if not lyrics:
            return f"❌ **Couldn't extract lyrics.** Try manually at [Genius]({lyrics_url})."

        title = song_info.get("title", "Unknown Title")
        artist = song_info.get("primary_artist", {}).get("name", "Unknown Artist")

        return f"🎶 **{html.escape(title)}** by **{html.escape(artist)}**\n\n<pre>{lyrics[:4096]}</pre>"

    except Exception as e:
        return f"❌ **Request Error:** {str(e)}"

async def send_long_message(msg, text):
    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
    for chunk in chunks:
        await msg.reply_text(chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

# --- Commands ---

# /start
@app.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply(
        f"Hey {message.from_user.mention},\n"
        "I'm NekoTune Advance Music Downloader Bot. 🎶\n"
        "Use /song <song_name> to download music!\n"
        "Use /lyrics <song_name> to get lyrics!\n\n"
        "Developed by: @TheErenYeager"
    )

# /song
@app.on_message(filters.command("song"))
async def download_song(_, message: Message):
    user_id = message.from_user.id
    current_time = time()

    # Anti-spam
    last_message_time = user_last_message_time.get(user_id, 0)
    if current_time - last_message_time < SPAM_WINDOW_SECONDS:
        user_last_message_time[user_id] = current_time
        user_command_count[user_id] = user_command_count.get(user_id, 0) + 1
        if user_command_count[user_id] > SPAM_THRESHOLD:
            hu = await message.reply_text(f"{message.from_user.mention} ᴘʟᴇᴀsᴇ ᴅᴏɴᴛ ᴅᴏ sᴘᴀᴍ, ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ ᴀғᴛᴇʀ 5 sᴇᴄ")
            await asyncio.sleep(3)
            await hu.delete()
            return
    else:
        user_command_count[user_id] = 1
        user_last_message_time[user_id] = current_time

    query = " ".join(message.command[1:])
    if not query:
        await message.reply("**✦ Usage: /song <song_name>**")
        return

    m = await message.reply("🔎 Searching for your song...")
    ydl_opts = {
        "format": "bestaudio[ext=m4a]",
        "noplaylist": True,
        "quiet": True,
        "logtostderr": False,
        "cookiefile": COOKIES_FILE,
    }

    try:
        results = YoutubeSearch(query, max_results=1).to_dict()
        if not results:
            await m.edit("No Result Found. Try Another Track")
            return

        link = f"https://youtube.com{results[0]['url_suffix']}"
        title = results[0]["title"]
        thumbnail = results[0]["thumbnails"][0]
        thumb_name = f"{title}.jpg"

        thumb = requests.get(thumbnail, allow_redirects=True)
        open(thumb_name, "wb").write(thumb.content)

        duration = results[0]["duration"]
        views = results[0]["views"]
        channel_name = results[0]["channel"]

        await m.edit("**✦ Processing your request**")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(link, download=False)
            audio_file = ydl.prepare_filename(info_dict)
            ydl.download([link])

        dur = sum(int(x) * 60 ** i for i, x in enumerate(reversed(duration.split(":"))))

        await m.edit("Uploading...")
        await message.reply_audio(
            audio_file,
            thumb=thumb_name,
            title=title,
            caption=f"{title}\nRequested by: {message.from_user.mention}\nViews: {views}\nChannel: {channel_name}",
            duration=dur
        )

        os.remove(audio_file)
        os.remove(thumb_name)
        await m.delete()

    except Exception as e:
        await m.edit("Error...")
        print(f"Error: {str(e)}")

# /lyrics
@app.on_message(filters.command("lyrics"))
async def send_lyrics(_, message: Message):
    if len(message.command) < 2:
        await message.reply_text("**✦ Usage: /lyrics <song_name>**")
        return

    song_name = " ".join(message.command[1:])
    m = await message.reply_text("🎶 **Fetching lyrics...**")
    lyrics = fetch_lyrics(song_name)

    if len(lyrics) > 4096:
        await send_long_message(message, lyrics)
        await m.delete()
    else:
        await m.edit_text(lyrics, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

# Start bot
if __name__ == "__main__":
    app.run()
