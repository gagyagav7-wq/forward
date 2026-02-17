import os, asyncio
from telethon import TelegramClient, functions, types
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, IntPrompt
from .utils import console, fix_id
from .history import is_processed, save_to_history

async def start_transit(client: TelegramClient):
    # --- 1. SETUP SOURCE (ASAL) ---
    console.print(f"[bold cyan]--- PENGATURAN SUMBER (ASAL) ---[/bold cyan]")
    src_id = fix_id(Prompt.ask("ID Grup ASAL"))
    topic_id = IntPrompt.ask("ID Topik ASAL (Ketik 0 jika tidak ada)", default=0)

    # --- 2. SETUP DESTINATION (TUJUAN) ---
    console.print(f"\n[bold cyan]--- PENGATURAN TUJUAN ---[/bold cyan]")
    dst_id = fix_id(Prompt.ask("ID Grup TUJUAN"))
    
    # --- MENU PILIHAN TOPIK (YANG TADI ERROR) ---
    console.print("\n[bold yellow]PILIH METODE TOPIK:[/bold yellow]")
    console.print("1. Input Manual ID (Paling Akurat)")
    console.print("2. Cari via Nama Topik")
    console.print("3. Kirim ke General (Tanpa Topik)")
    
    # Nah ini fix-nya, choices-nya angka doang
    mode_topik = Prompt.ask("Pilih Angka", choices=["1", "2", "3"], default="1")
    
    target_topic_id = None
    dst_ent = await client.get_input_entity(dst_id)

    if mode_topik == "1":
        # Tips cara nyari ID
        console.print("[dim]Tips: Di Telegram, klik titik 3 di pojok kanan atas topik -> Copy Link.[/dim]")
        console.print("[dim]Contoh Link: https://t.me/c/12345/123/999 -> ID Topiknya adalah 123[/dim]")
        target_topic_id = IntPrompt.ask("Masukkan ID Topik (Angka)")
        
    elif mode_topik == "2":
        try:
            full_channel = await client(functions.channels.GetFullChannelRequest(dst_ent))
            if full_channel.full_chat.forum:
                target_name = Prompt.ask("Masukkan NAMA Topik (Harus Persis)")
                console.print(f"[dim]Mencari topik '{target_name}'...[/dim]")
                
                res = await client(functions.channels.GetForumTopicsRequest(channel=dst_ent, offset_date=None, offset_id=0, offset_topic=0, limit=100))
                found = False
                for t in res.topics:
                    if t.title.lower() == target_name.lower():
                        target_topic_id = t.id
                        found = True
                        console.print(f"[green]Topik ketemu! ID: {target_topic_id}[/green]")
                        break
                
                if not found:
                    console.print(f"[red]Topik '{target_name}' gak ketemu! Bikin baru...[/red]")
                    try:
                        new_t = await client(functions.channels.CreateForumTopicRequest(channel=dst_ent, title=target_name))
                        target_topic_id = new_t.updates[0].id
                    except:
                        target_topic_id = IntPrompt.ask("[red]Gagal bikin. Masukkan ID Manual aja[/red]")
            else:
                console.print("[yellow]Grup tujuan bukan Forum! Skip topik.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error cari topik: {e}[/red]")
            target_topic_id = IntPrompt.ask("Masukkan ID Topik Manual aja")
            
    else:
        target_topic_id = None # Kirim ke General

    # --- 3. FILTER & SETTINGS ---
    console.print(f"\n[bold cyan]--- FILTER & SETTINGS ---[/bold cyan]")
    # Menu simpel angka
    console.print("1. Video\n2. Foto\n3. Semua")
    mode_file = Prompt.ask("Tipe File", choices=["1", "2", "3"], default="1")
    
    resume_mode = Prompt.ask("Lanjut dari yg terakhir (Anti-Duplikat)?", choices=["y", "n"], default="y")
    
    console.print("1. Lama ke Baru (Urut Episode)\n2. Baru ke Lama")
    urut_pilihan = Prompt.ask("Urutan Ambil", choices=["1", "2"], default="1")
    is_reverse = True if urut_pilihan == "1" else False

    # Setup Filter
    m_filter = None
    if mode_file == "1": m_filter = types.InputMessagesFilterVideo()
    elif mode_file == "2": m_filter = types.InputMessagesFilterPhotos()

    src_ent = await client.get_input_entity(src_id)

    console.print(f"\n[bold yellow]🚀 GASKEUN! (Target Topik ID: {target_topic_id})[/bold yellow]")
    
    # --- 4. EKSEKUSI ---
    async for msg in client.iter_messages(src_ent, reply_to=topic_id if topic_id > 0 else None, filter=m_filter, reverse=is_reverse):
        try:
            # SKIP CHECK
            if resume_mode == "y" and is_processed(src_id, msg.id):
                console.print(f"[dim]⏩ Skip ID {msg.id}[/dim]")
                continue

            # VALIDASI TIPE
            valid = False
            if mode_file == "3":
                if (hasattr(msg, 'video') and msg.video) or (hasattr(msg, 'photo') and msg.photo): valid = True
            else: valid = True

            if valid:
                with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}[/bold cyan]"), BarColumn(), console=console) as prg:
                    t_desc = f"Moving ID {msg.id}..."
                    task = prg.add_task(t_desc, total=None)
                    
                    path = await client.download_media(msg)
                    
                    if path:
                        try:
                            await client.send_file(
                                dst_ent, 
                                path, 
                                caption=msg.text or "", 
                                reply_to=target_topic_id 
                            )
                            save_to_history(src_id, msg.id)
                            await asyncio.sleep(0.5) 
                        except Exception as e:
                            console.print(f"[red]Gagal Upload: {e}[/red]")
                        finally:
                            if os.path.exists(path): os.remove(path)
                            
        except Exception as e:
            console.print(f"[red]Error Message {msg.id}: {e}[/red]")

    console.print("[bold green]✅ SEMUA SELESAI BOSKU![/bold green]")
    
