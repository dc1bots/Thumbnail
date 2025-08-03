import os, asyncio, subprocess
from pyrogram import Client, filters
from pyrogram.types import Message

API_ID, API_HASH, BOT_TOKEN = int(os.getenv("API_ID")), os.getenv("API_HASH"), os.getenv("BOT_TOKEN")
bot = Client("forward_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

media_groups, user_state, msg_refs = {}, {}, {}

async def run(cmd): await asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.run(cmd, stdout=None, stderr=None))
async def get_duration(f): return float((await asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", f],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT))).stdout)

@bot.on_message(filters.forwarded & filters.video)
async def fwd_video(bot, m):
    if m.media_group_id: media_groups.setdefault(m.media_group_id, []).append(m)
    else: await process_video(bot, m, m.chat.id)

@bot.on_message(filters.forwarded & filters.media_group)
async def fwd_album(bot, m): media_groups.setdefault(m.media_group_id, []).append(m)

@bot.on_message(filters.text & filters.regex(r"^done$"))
async def flush(bot, m):
    for g, msgs in list(media_groups.items()):
        for msg in sorted(msgs, key=lambda x: x.message_id):
            if msg.video: await process_video(bot, msg, m.chat.id)
        del media_groups[g]

async def process_video(bot, msg, target):
    path = await bot.download_media(msg)
    thumb = f"{path}_thumb.jpg"
    await run(["ffmpeg","-ss","00:00:10","-i",path,"-vframes","1","-q:v","1","-vf","scale=1280:-1","-y",thumb])
    duration = int(await get_duration(path))
    await bot.send_video(chat_id=target, video=path, duration=duration, caption=msg.caption,
        caption_entities=msg.caption_entities, thumb=thumb if os.path.exists(thumb) else None, supports_streaming=True)
    os.remove(path); os.remove(thumb) if os.path.exists(thumb) else None

async def copy_all_messages(bot, uid):
    state = user_state.get(uid); ref = msg_refs.get(uid)
    if not state: return
    source, target = int(state["source"]), int(state["target"])
    start_id, thumb_change = int(state["start_id"]), state["thumb_choice"]
    for msg_id in range(start_id, start_id + 5000):  # adjust range as needed
        try:
            msg = await bot.get_messages(source, msg_id)
            if not msg: break
            if msg.video and thumb_change: await process_video(bot, msg, target)
            else: await msg.copy(chat_id=target)
        except: continue
    await ref.edit("✅ Done copying messages.")

@bot.on_message(filters.command("copyall") | (filters.private & filters.text))
async def handle_copy_flow(bot, m):
    uid, txt = m.from_user.id, m.text.strip().lower()
    state, ref = user_state.get(uid, {}), msg_refs.get(uid)

    if m.text.startswith("/copyall"):
        user_state[uid] = {}; msg_refs[uid] = await m.reply("🤖 Is bot admin in both channels? /yes or /no"); return

    await m.delete()
    if not ref: msg_refs[uid] = await m.reply("❗ Start with /copyall"); return

    if "admin_ok" not in state:
        if txt in ["yes","/yes"]: state["admin_ok"]=1; await ref.edit("📥 Enter target channel ID:")
        else: await ref.edit("❌ Make bot admin in both channels."); user_state[uid]=state
        return

    if "target" not in state:
        state["target"] = txt; await ref.edit("📤 Now FORWARD the FIRST message from source channel.")
        user_state[uid] = state; return

    if "source" not in state:
        if not m.forward_from_chat: await ref.edit("❗Please forward a message from the source channel."); return
        state["source"] = m.forward_from_chat.id
        state["start_id"] = m.forward_from_message_id
        await ref.edit("🎬 Change video thumbnail? /yes or /no")
        user_state[uid] = state
        return

    if "thumb_choice" not in state:
        state["thumb_choice"] = txt in ["yes","/yes"]
        await ref.edit("⏳ Copying messages...")
        user_state[uid] = state
        await copy_all_messages(bot, uid)

bot.run()
