import os, asyncio, subprocess
from pyrogram import Client, filters
from pyrogram.types import Message

API_ID, API_HASH, BOT_TOKEN = int(os.getenv("API_ID")), os.getenv("API_HASH"), os.getenv("BOT_TOKEN")
bot = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

media_groups = {}

async def run(cmd): await asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.run(cmd, stdout=None, stderr=None))
    
async def get_duration(f): return float((await asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", f],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT))).stdout)

@bot.on_message(filters.forwarded & filters.video)
async def fwd_video(bot, m): media_groups.setdefault(m.media_group_id, []).append(m) if m.media_group_id else await process(bot, m)
    
@bot.on_message(filters.forwarded & filters.media_group)
async def fwd_album(bot, m): media_groups.setdefault(m.media_group_id, []).append(m)
    
@bot.on_message(filters.text)
async def flush(bot, m):
    for g, msgs in list(media_groups.items()):
        for msg in sorted(msgs, key=lambda x: x.message_id):
            if msg.video: await process(bot, msg)
        del media_groups[g]

async def process(bot, m: Message):
    path = await bot.download_media(m)
    thumb = f"{path}_thumb.jpg"
    await run(["ffmpeg", "-ss", "00:00:10", "-i", path, "-vframes", "1", "-q:v", "1", "-vf", "scale=1280:-1", "-y", thumb])
    duration = int(await get_duration(path))
    await bot.send_video(m.chat.id, video=path, thumb=thumb if os.path.exists(thumb) else None,
                         caption=m.caption, caption_entities=m.caption_entities,
                         duration=duration, supports_streaming=True)
    try: await m.delete()
    except: pass
    os.remove(path)
    if os.path.exists(thumb): os.remove(thumb)

bot.run()
