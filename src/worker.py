import os, asyncio, subprocess
from telethon import TelegramClient, functions, types
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, IntPrompt
from .utils import console, fix_id
from .history import is_processed, save_to_history

# --- FUNGSI GENERATE THUMBNAIL MANUAL ---
def generate_thumbnail(video_path):
    thumb_path = f"{video_path}.jpg"
    try:
        # Perintah FFmpeg: Ambil gambar di detik ke-1 (-ss 00:00:01)
        # Biar gak dapet layar hitam di awal video
        cmd = [
            'ffmpeg', '-y', 
            '-i', video_path, 
            '-ss', '00:00:01', 
            '-vframes', '1', 
            thumb_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(thumb_path):
            return thumb_path
    except:
        pass
    return None

# --- FUNGSI KIRIM ALBUM ---
async def send_batch(client, dst_ent, batch_msgs, batch_files, batch_thumbs, target_topic_id, src_id):
    if not batch_files: return

    try:
        caption = batch_msgs[0].text or ""
        
        # KITA GAK PAKE 'attributes' MANUAL LAGI
        # Biarkan Telethon + Hachoir ngitung durasi otomatis
        await client.send_file(
            dst_ent,
            file=batch_files,
            caption=caption,
            thumb=batch_thumbs,      # Pake thumbnail hasil generate FFmpeg
            reply_to=target_topic_id,
            supports_streaming=True,
            force_document=False 
        )

        for msg in batch_msgs:
            save_to_history(src_id, msg.id)

    except Exception as e:
        console.print(f"[red]Gagal Kirim Album: {e}[/red]")
    finally:
        # Hapus video & thumbnail
        for f in batch_files:
            if f and os.path.exists(f): os.remove(f)
        for t in batch_thumbs:
            if t and os.path.exists(t): os.remove(t)

async def start_transit(client: TelegramClient):
    # --- SETUP ---
    console.print(f"[bold cyan]--- SETUP SUMBER & TUJUAN ---[/bold cyan]")
    src_id = fix_id(Prompt.ask("ID Grup ASAL"))
    topic_id = IntPrompt.ask("ID Topik ASAL (0 jika tidak ada)", default=0)
    dst_id = fix_id(Prompt.ask("ID Grup TUJUAN"))
    
    # Logic Topik
    console.print("1. Manual ID | 2. Cari Nama | 3. General")
    mode_topik = Prompt.ask("Pilih", choices=["1", "2", "3"], default="1")
    target_topic_id = None
    dst_ent = await client.get_input_entity(dst_id)

    if mode_topik == "1":
        target_topic_id = IntPrompt.ask("ID Topik")
    elif mode_topik == "2":
        # (Logic cari nama disingkat biar rapi, sama kek sebelumnya)
        try:
            name = Prompt.ask("Nama Topik")
            res = await client(functions.channels.GetForumTopicsRequest(channel=dst_ent, offset_date=None, offset_id=0, offset_topic=0, limit=100))
            for t in res.topics:
                if t.title.lower() == name.lower(): target_topic_id = t.id; break
            if not target_topic_id: target_topic_id = IntPrompt.ask("Gak ketemu. ID Manual aja")
        except: pass

    # --- SETTINGS ---
    mode_file = Prompt.ask("1. Video | 2. Foto | 3. Semua", choices=["1", "2", "3"], default="1")
    resume_mode = Prompt.ask("Lanjut (Anti-Duplikat)?", choices=["y", "n"], default="y")
    urut = Prompt.ask("1. Lama ke Baru | 2. Baru ke Lama", choices=["1", "2"], default="1")
    is_reverse = True if urut == "1" else False

    m_filter = None
    if mode_file == "1": m_filter = types.InputMessagesFilterVideo()
    elif mode_file == "2": m_filter = types.InputMessagesFilterPhotos()
    
    src_ent = await client.get_input_entity(src_id)

    # --- BATCH VARS ---
    batch_msgs = []
    batch_files = []
    batch_thumbs = []
    current_type = None

    console.print(f"\n[bold yellow]🚀 GASKEUN RE-ENCODE![/bold yellow]")
    
    with Progress(SpinnerColumn(), TextColumn("[cyan]{task.description}[/cyan]"), BarColumn(), console=console) as prg:
        task = prg.add_task("Mencari...", total=None)
        
        async for msg in client.iter_messages(src_ent, reply_to=topic_id if topic_id > 0 else None, filter=m_filter, reverse=is_reverse):
            
            if resume_mode == "y" and is_processed(src_id, msg.id): continue

            msg_type = None
            if hasattr(msg, 'video') and msg.video: msg_type = 'video'
            elif hasattr(msg, 'photo') and msg.photo: msg_type = 'photo'
            if not msg_type: continue
            
            if mode_file == "1" and msg_type != 'video': continue
            if mode_file == "2" and msg_type != 'photo': continue

            # KIRIM JIKA PENUH (10) ATAU TIPE BERUBAH
            if len(batch_msgs) >= 10 or (current_type and current_type != msg_type):
                prg.update(task, description=f"Mengirim Album ({len(batch_msgs)} items)...")
                await send_batch(client, dst_ent, batch_msgs, batch_files, batch_thumbs, target_topic_id, src_id)
                batch_msgs = []; batch_files = []; batch_thumbs = []; current_type = None

            current_type = msg_type
            prg.update(task, description=f"Download ID {msg.id}...")
            
            # DOWNLOAD
            path = await client.download_media(msg)
            
            # GENERATE METADATA BARU (INTI PERUBAHAN)
            thumb_path = None
            if msg_type == 'video' and path:
                # Kita bikin thumbnail manual pake FFmpeg (Detik ke-1)
                thumb_path = generate_thumbnail(path)
            
            if path:
                batch_msgs.append(msg)
                batch_files.append(path)
                batch_thumbs.append(thumb_path) # Masukin thumb hasil generate

        # KIRIM SISA
        if batch_msgs:
            prg.update(task, description=f"Mengirim sisa ({len(batch_msgs)})...")
            await send_batch(client, dst_ent, batch_msgs, batch_files, batch_thumbs, target_topic_id, src_id)

    console.print("[green]✅ DONE![/green]")
            
