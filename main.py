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
    target_chat_id = m.chat.id
    for g, msgs in list(media_groups.items()):
        for msg in sorted(msgs, key=lambda x: x.message_id):
            if msg.video:
                await process_video(bot, msg, target_chat_id)
        del media_groups[g]

async def process_video(bot, msg, target):
    path = await bot.download_media(msg)
    thumb = f"{path}_thumb.jpg"
    await run(["ffmpeg","-ss","00:00:10","-i",path,"-vframes","1","-q:v","1","-vf","scale=1280:-1","-y",thumb])
    duration = int(await get_duration(path))
    await bot.send_video(
        chat_id=target, video=path, duration=duration,
        caption=msg.caption, caption_entities=msg.caption_entities,
        thumb=thumb if os.path.exists(thumb) else None,
        supports_streaming=True
    )
    os.remove(path)
    if os.path.exists(thumb): os.remove(thumb)
#======================================================================================
user_state = {}
msg_refs = {}

async def copy_all_messages(bot, user_id):
    state = user_state.get(user_id)
    if not state: return
    source, target = int(state["source"]), int(state["target"])
    change_thumb = state["thumb_choice"]
    async for msg in bot.iter_chat_history(source, reverse=True):
        try:
            if msg.video and change_thumb:
                await process_video(bot, msg, target)
            else:
                await msg.copy(chat_id=target)
        except: pass

@bot.on_message(filters.command("copy") | (filters.private & filters.text))
async def handle_copy_flow(bot, message):
    uid = message.from_user.id
    txt = message.text.strip().lower()
    state = user_state.get(uid,{})
    ref = msg_refs.get(uid)

    if message.text.startswith("/copyall"):
        user_state[uid] = {}
        sent = await message.reply("🤖 Is the bot admin in both channels? (/yes//no)")
        msg_refs[uid] = sent
        return

    await message.delete()
    if not ref:
        sent = await message.reply("🤖 Please start with /copyall")
        msg_refs[uid] = sent
        return

    if "admin_ok" not in state:
        if txt in ["yes","/yes"]:
            state["admin_ok"]=True
            await ref.edit("📥 Enter destination channel ID (with -100):")
        else:
            await ref.edit("❌ Please make the bot admin in both channels before proceeding.")
        user_state[uid]=state
        return

    if "target" not in state:
        state["target"]=txt
        await ref.edit("📤 Now enter the source channel ID:")
        user_state[uid]=state
        return

    if "source" not in state:
        state["source"]=txt
        await ref.edit("🎬 Do you want to change video thumbnails? (/yes//no)")
        user_state[uid]=state
        return

    if "thumb_choice" not in state:
        state["thumb_choice"] = txt in ["yes","/yes"]
        await ref.edit("⏳ Starting to copy messages...")
        user_state[uid] = state
        await copy_all_messages(bot, uid)
#======================================================================================
bot.run()
