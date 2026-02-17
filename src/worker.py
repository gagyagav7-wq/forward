import os, asyncio
from telethon import TelegramClient, functions, types
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, IntPrompt
from .utils import console, fix_id
from .history import is_processed, save_to_history

async def start_transit(client: TelegramClient):
    # --- 1. SETUP SOURCE ---
    console.print(f"[bold cyan]--- PENGATURAN SUMBER ---[/bold cyan]")
    src_id = fix_id(Prompt.ask("ID Grup ASAL"))
    topic_id = IntPrompt.ask("ID Topik ASAL (0 jika tidak ada)", default=0)

    # --- 2. SETUP DESTINATION ---
    console.print(f"\n[bold cyan]--- PENGATURAN TUJUAN ---[/bold cyan]")
    dst_id = fix_id(Prompt.ask("ID Grup TUJUAN"))
    
    # SETUP TOPIK (Simpel Angka)
    console.print("\n[bold yellow]METODE TOPIK:[/bold yellow]")
    console.print("1. Manual ID\n2. Cari Nama\n3. General (No Topic)")
    mode_topik = Prompt.ask("Pilih", choices=["1", "2", "3"], default="1")
    
    target_topic_id = None
    dst_ent = await client.get_input_entity(dst_id)

    if mode_topik == "1":
        console.print("[dim]Tips: Link https://t.me/c/123/456/99 -> ID Topik: 456[/dim]")
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

    # --- 3. FILTER & SETTINGS ---
    console.print("\n1. Video | 2. Foto | 3. Semua")
    mode_file = Prompt.ask("Tipe File", choices=["1", "2", "3"], default="1")
    resume_mode = Prompt.ask("Lanjut (Anti-Duplikat)?", choices=["y", "n"], default="y")
    
    console.print("1. Lama ke Baru (Eps 1->End)\n2. Baru ke Lama")
    urut = Prompt.ask("Urutan", choices=["1", "2"], default="1")
    is_reverse = True if urut == "1" else False

    # Filter Logic
    m_filter = None
    if mode_file == "1": m_filter = types.InputMessagesFilterVideo()
    elif mode_file == "2": m_filter = types.InputMessagesFilterPhotos()
    
    src_ent = await client.get_input_entity(src_id)

    console.print(f"\n[bold yellow]🚀 GASKEUN![/bold yellow]")
    
    # --- 4. EKSEKUSI ---
    async for msg in client.iter_messages(src_ent, reply_to=topic_id if topic_id > 0 else None, filter=m_filter, reverse=is_reverse):
        try:
            if resume_mode == "y" and is_processed(src_id, msg.id):
                console.print(f"[dim]⏩ Skip {msg.id}[/dim]")
                continue

            valid = False
            if mode_file == "3":
                if (hasattr(msg, 'video') and msg.video) or (hasattr(msg, 'photo') and msg.photo): valid = True
            else: valid = True

            if valid:
                with Progress(SpinnerColumn(), TextColumn("[cyan]{task.description}[/cyan]"), BarColumn(), console=console) as prg:
                    task = prg.add_task(f"Moving {msg.id}...", total=None)
                    
                    # 1. AMBIL ATRIBUT ASLI (KTP VIDEO)
                    my_attributes = []
                    if msg.media and hasattr(msg.media, 'document') and hasattr(msg.media.document, 'attributes'):
                        my_attributes = msg.media.document.attributes

                    # 2. DOWNLOAD
                    path = await client.download_media(msg)
                    
                    if path:
                        try:
                            # 3. UPLOAD DENGAN ATRIBUT & STREAMING
                            await client.send_file(
                                dst_ent, 
                                path, 
                                caption=msg.text or "", 
                                reply_to=target_topic_id,
                                attributes=my_attributes,   # <--- INI KUNCINYA
                                supports_streaming=True     # <--- BIAR BISA DIPLAY LANGSUNG
                            )
                            save_to_history(src_id, msg.id)
                            await asyncio.sleep(0.5) 
                        except Exception as e:
                            console.print(f"[red]Gagal: {e}[/red]")
                        finally:
                            if os.path.exists(path): os.remove(path)
                            
        except Exception as e:
            console.print(f"[red]Err {msg.id}: {e}[/red]")

    console.print("[green]✅ DONE![/green]")
    
