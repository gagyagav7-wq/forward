import os, asyncio, subprocess, json, math
from telethon import TelegramClient, functions, types
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, IntPrompt
from .utils import console, fix_id
from .history import is_processed, save_to_history

# --- 1. CEK DURASI VIDEO (Buat nentuin posisi tengah) ---
def get_video_duration(video_path):
    try:
        # Pake ffprobe buat baca metadata durasi
        cmd = [
            'ffprobe', 
            '-v', 'error', 
            '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            video_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout.strip())
    except:
        return 5.0 # Default tembak detik ke-5 kalo gagal baca

# --- 2. GENERATE THUMBNAIL (DI TENGAH VIDEO) ---
def generate_smart_thumbnail(video_path):
    thumb_path = f"{video_path}.jpg"
    try:
        # Cari titik tengah
        duration = get_video_duration(video_path)
        mid_point = duration / 2
        
        # Kalau video pendek (< 2 detik), ambil di awal aja
        if duration < 2: mid_point = 0.5
        
        # Format timestamp HH:MM:SS
        ss_time = str(mid_point)

        # Command FFmpeg: Ambil gambar di titik tengah, Resize lebar 320px (Standar Telegram)
        cmd = [
            'ffmpeg', '-y', '-v', 'error',
            '-ss', ss_time,         # Loncat ke tengah
            '-i', video_path, 
            '-vframes', '1', 
            '-vf', 'scale=320:-1',  # Resize biar enteng & valid
            '-q:v', '2',            # Kualitas JPG
            thumb_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(thumb_path):
            file_size = os.path.getsize(thumb_path)
            if file_size > 0: return thumb_path
    except Exception as e:
        console.print(f"[red]Gagal Thumb: {e}[/red]")
    return None

# --- 3. JURUS CUCI VIDEO (REMUX) ---
def clean_video(input_path):
    output_path = f"{input_path}_clean.mp4"
    try:
        cmd = [
            'ffmpeg', '-y', '-v', 'error',
            '-i', input_path, 
            '-c', 'copy', 
            '-movflags', '+faststart',
            output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(output_path): return output_path
    except: pass
    return input_path

# --- 4. KIRIM ALBUM ---
async def send_batch(client, dst_ent, batch_msgs, batch_files, batch_thumbs, target_topic_id, src_id):
    if not batch_files: return
    try:
        caption = batch_msgs[0].text or ""
        
        await client.send_file(
            dst_ent,
            file=batch_files,
            caption=caption,
            thumb=batch_thumbs,      # Thumbnail dari tengah video
            reply_to=target_topic_id,
            supports_streaming=True,
            force_document=False 
        )

        for msg in batch_msgs: save_to_history(src_id, msg.id)

    except Exception as e:
        console.print(f"[red]Gagal Kirim Album: {e}[/red]")
    finally:
        # Hapus Sampah
        for f in batch_files:
            if f and os.path.exists(f): os.remove(f)
            original = f.replace("_clean.mp4", "")
            if os.path.exists(original): os.remove(original)
        for t in batch_thumbs:
            if t and os.path.exists(t): os.remove(t)

async def start_transit(client: TelegramClient):
    # --- SETUP ---
    console.print(f"[bold cyan]--- SETUP SUMBER ---[/bold cyan]")
    src_id = fix_id(Prompt.ask("ID Grup ASAL"))
    topic_id = IntPrompt.ask("ID Topik ASAL (0=None)", default=0)
    
    console.print(f"\n[bold cyan]--- SETUP TUJUAN ---[/bold cyan]")
    dst_id = fix_id(Prompt.ask("ID Grup TUJUAN"))
    
    mode_topik = Prompt.ask("Topik Tujuan: 1.ID Manual | 2.Cari Nama | 3.General", choices=["1", "2", "3"], default="1")
    target_topic_id = None
    dst_ent = await client.get_input_entity(dst_id)

    if mode_topik == "1": target_topic_id = IntPrompt.ask("ID Topik")
    elif mode_topik == "2":
        try:
            name = Prompt.ask("Nama Topik")
            res = await client(functions.channels.GetForumTopicsRequest(channel=dst_ent, offset_date=None, offset_id=0, offset_topic=0, limit=100))
            for t in res.topics:
                if t.title.lower() == name.lower(): target_topic_id = t.id; break
            if not target_topic_id: target_topic_id = IntPrompt.ask("ID Manual")
        except: pass

    # --- SETTINGS ---
    mode_file = Prompt.ask("File: 1.Video | 2.Foto | 3.Semua", choices=["1", "2", "3"], default="1")
    resume_mode = Prompt.ask("Anti-Duplikat?", choices=["y", "n"], default="y")
    urut = Prompt.ask("Urutan: 1.Lama ke Baru | 2.Baru ke Lama", choices=["1", "2"], default="1")
    is_reverse = True if urut == "1" else False

    m_filter = None
    if mode_file == "1": m_filter = types.InputMessagesFilterVideo()
    elif mode_file == "2": m_filter = types.InputMessagesFilterPhotos()
    
    src_ent = await client.get_input_entity(src_id)

    # --- BATCH VARS ---
    batch_msgs = []; batch_files = []; batch_thumbs = []; current_type = None

    console.print(f"\n[bold yellow]🚀 GASKEUN SMART THUMBNAIL![/bold yellow]")
    
    with Progress(SpinnerColumn(), TextColumn("[cyan]{task.description}[/cyan]"), BarColumn(), console=console) as prg:
        task = prg.add_task("Standby...", total=None)
        
        async for msg in client.iter_messages(src_ent, reply_to=topic_id if topic_id > 0 else None, filter=m_filter, reverse=is_reverse):
            
            if resume_mode == "y" and is_processed(src_id, msg.id): continue

            # Detect
            msg_type = None
            if hasattr(msg, 'video') and msg.video: msg_type = 'video'
            elif hasattr(msg, 'photo') and msg.photo: msg_type = 'photo'
            if not msg_type: continue
            
            if mode_file == "1" and msg_type != 'video': continue
            if mode_file == "2" and msg_type != 'photo': continue

            # SEND BATCH
            if len(batch_msgs) >= 10 or (current_type and current_type != msg_type):
                prg.update(task, description=f"Mengirim Album ({len(batch_msgs)})...")
                await send_batch(client, dst_ent, batch_msgs, batch_files, batch_thumbs, target_topic_id, src_id)
                batch_msgs = []; batch_files = []; batch_thumbs = []; current_type = None

            current_type = msg_type
            prg.update(task, description=f"Processing ID {msg.id}...")
            
            # 1. DOWNLOAD
            path = await client.download_media(msg)
            
            # 2. PROSES
            final_path = path
            thumb_path = None
            
            if path and msg_type == 'video':
                # Bersihin Metadata
                final_path = clean_video(path)
                # Bikin Thumbnail di TENGAH Video
                thumb_path = generate_smart_thumbnail(final_path)
            
            if final_path:
                batch_msgs.append(msg)
                batch_files.append(final_path)
                batch_thumbs.append(thumb_path)

        # SISA
        if batch_msgs:
            prg.update(task, description=f"Mengirim sisa ({len(batch_msgs)})...")
            await send_batch(client, dst_ent, batch_msgs, batch_files, batch_thumbs, target_topic_id, src_id)

    console.print("[green]✅ DONE![/green]")
            
