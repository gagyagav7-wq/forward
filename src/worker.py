import os, asyncio
from telethon import TelegramClient, functions, types
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, IntPrompt
from .utils import console, fix_id
from .history import is_processed, save_to_history

# --- FUNGSI KIRIM ALBUM ---
async def send_batch(client, dst_ent, batch_msgs, batch_files, batch_thumbs, batch_attrs, target_topic_id, src_id):
    if not batch_files: return

    try:
        # Ambil caption dari pesan pertama aja (biar ga kepanjangan)
        caption = batch_msgs[0].text or ""
        
        # PROSES UPLOAD ALBUM
        # force_document=False biar jadi galeri (bukan file dokumen)
        await client.send_file(
            dst_ent,
            file=batch_files,
            caption=caption,
            thumb=batch_thumbs,
            attributes=batch_attrs,
            reply_to=target_topic_id,
            supports_streaming=True,
            force_document=False 
        )

        # CATAT HISTORY (Semua item di batch dianggap sukses)
        for msg in batch_msgs:
            save_to_history(src_id, msg.id)

    except Exception as e:
        console.print(f"[red]Gagal Kirim Album: {e}[/red]")
    finally:
        # BERSIH-BERSIH SAMPAH
        for f in batch_files:
            if f and os.path.exists(f): os.remove(f)
        for t in batch_thumbs:
            if t and os.path.exists(t): os.remove(t)

async def start_transit(client: TelegramClient):
    # --- 1. SETUP ---
    console.print(f"[bold cyan]--- PENGATURAN SUMBER ---[/bold cyan]")
    src_id = fix_id(Prompt.ask("ID Grup ASAL"))
    topic_id = IntPrompt.ask("ID Topik ASAL (0 jika tidak ada)", default=0)

    console.print(f"\n[bold cyan]--- PENGATURAN TUJUAN ---[/bold cyan]")
    dst_id = fix_id(Prompt.ask("ID Grup TUJUAN"))
    
    console.print("\n[bold yellow]METODE TOPIK:[/bold yellow]")
    console.print("1. Manual ID\n2. Cari Nama\n3. General (No Topic)")
    mode_topik = Prompt.ask("Pilih", choices=["1", "2", "3"], default="1")
    
    target_topic_id = None
    dst_ent = await client.get_input_entity(dst_id)

    if mode_topik == "1":
        target_topic_id = IntPrompt.ask("Masukkan ID Topik")
    elif mode_topik == "2":
        try:
            full = await client(functions.channels.GetFullChannelRequest(dst_ent))
            if full.full_chat.forum:
                name = Prompt.ask("Nama Topik")
                res = await client(functions.channels.GetForumTopicsRequest(channel=dst_ent, offset_date=None, offset_id=0, offset_topic=0, limit=100))
                for t in res.topics:
                    if t.title.lower() == name.lower():
                        target_topic_id = t.id; break
                if not target_topic_id:
                    console.print("[red]Gak ketemu! Pake ID Manual aja.[/red]")
                    target_topic_id = IntPrompt.ask("ID Topik")
        except: pass

    # --- SETTINGS ---
    console.print("\n[bold]MODE ALBUM (GROUPING)[/bold]")
    console.print("Maksimal 10 item per album (Aturan Telegram).")
    
    console.print("\n1. Video | 2. Foto | 3. Semua")
    mode_file = Prompt.ask("Tipe File", choices=["1", "2", "3"], default="1")
    resume_mode = Prompt.ask("Lanjut (Anti-Duplikat)?", choices=["y", "n"], default="y")
    
    console.print("1. Lama ke Baru (Urut Episode)\n2. Baru ke Lama")
    urut = Prompt.ask("Urutan", choices=["1", "2"], default="1")
    is_reverse = True if urut == "1" else False

    m_filter = None
    if mode_file == "1": m_filter = types.InputMessagesFilterVideo()
    elif mode_file == "2": m_filter = types.InputMessagesFilterPhotos()
    
    src_ent = await client.get_input_entity(src_id)

    # --- KERANJANG BELANJA (BATCH) ---
    batch_msgs = []
    batch_files = []
    batch_thumbs = []
    batch_attrs = []
    current_type = None # 'video' atau 'photo'

    console.print(f"\n[bold yellow]🚀 GASKEUN MODE ALBUM![/bold yellow]")
    
    with Progress(SpinnerColumn(), TextColumn("[cyan]{task.description}[/cyan]"), BarColumn(), console=console) as prg:
        task = prg.add_task("Mencari file...", total=None)
        
        async for msg in client.iter_messages(src_ent, reply_to=topic_id if topic_id > 0 else None, filter=m_filter, reverse=is_reverse):
            
            # 1. SKIP CHECK
            if resume_mode == "y" and is_processed(src_id, msg.id):
                continue

            # 2. TENTUKAN TIPE FILE SAAT INI
            msg_type = None
            if hasattr(msg, 'video') and msg.video: msg_type = 'video'
            elif hasattr(msg, 'photo') and msg.photo: msg_type = 'photo'
            
            if not msg_type: continue # Skip text doang
            
            # Filter User Request (Misal cuma mau video)
            if mode_file == "1" and msg_type != 'video': continue
            if mode_file == "2" and msg_type != 'photo': continue

            # 3. LOGIC GANTI BATCH (Kirim kalau Penuh atau Beda Tipe)
            # Kalau keranjang penuh (10) ATAU tipe file berubah (misal dari Foto ke Video)
            if len(batch_msgs) >= 10 or (current_type and current_type != msg_type):
                prg.update(task, description=f"Mengirim Album ({len(batch_msgs)} items)...")
                await send_batch(client, dst_ent, batch_msgs, batch_files, batch_thumbs, batch_attrs, target_topic_id, src_id)
                
                # Kosongkan Keranjang
                batch_msgs = []
                batch_files = []
                batch_thumbs = []
                batch_attrs = []
                current_type = None

            # 4. MASUKIN KERANJANG (Download dulu)
            current_type = msg_type
            prg.update(task, description=f"Download ID {msg.id} ({len(batch_msgs)+1}/10)...")
            
            # Download Media Utama
            path = await client.download_media(msg)
            
            # Download Thumb & Ambil Atribut (Biar Video ga Gelap)
            thumb_path = None
            attrs = None
            
            if msg_type == 'video':
                thumb_path = await client.download_media(msg, thumb=-1)
                if msg.media and hasattr(msg.media, 'document'):
                    attrs = msg.media.document.attributes
            
            # Simpan data ke list batch
            if path:
                batch_msgs.append(msg)
                batch_files.append(path)
                batch_thumbs.append(thumb_path) # Bisa None kalo foto
                batch_attrs.append(attrs)       # Bisa None kalo foto

        # 5. KIRIM SISA KERANJANG (Di akhir loop)
        if batch_msgs:
            prg.update(task, description=f"Mengirim sisa album ({len(batch_msgs)} items)...")
            await send_batch(client, dst_ent, batch_msgs, batch_files, batch_thumbs, batch_attrs, target_topic_id, src_id)

    console.print("[green]✅ SEMUA SELESAI BOSKU![/green]")
    
