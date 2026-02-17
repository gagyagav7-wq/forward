import os, asyncio
from telethon import TelegramClient, functions, types
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, IntPrompt
from .utils import console, fix_id
from .history import is_processed, save_to_history # <--- Import fitur baru

async def start_transit(client: TelegramClient):
    # --- INPUT ---
    src_id = fix_id(Prompt.ask("[bold cyan]Source Group ID[/bold cyan]"))
    topic_id = IntPrompt.ask("[bold cyan]Source Topic ID (0 jika tidak ada)[/bold cyan]", default=0)
    dst_id = fix_id(Prompt.ask("[bold cyan]Destination Group ID[/bold cyan]"))
    
    # Tanya user mau lanjutin atau ulang dari awal?
    resume_mode = Prompt.ask("Mode Lanjut?", choices=["y", "n"], default="y")
    
    mode = Prompt.ask("Tipe File: 1.Video | 2.Photo | 3.All", choices=["1", "2", "3"], default="3")
    
    # --- AUTO TOPIC (Sama kayak sebelumnya) ---
    target_topic_id = None
    dst_ent = await client.get_input_entity(dst_id)
    try:
        full_channel = await client(functions.channels.GetFullChannelRequest(dst_ent))
        if full_channel.full_chat.forum:
            target_name = Prompt.ask("Target Topic Name")
            res = await client(functions.channels.GetForumTopicsRequest(channel=dst_ent, offset_date=None, offset_id=0, offset_topic=0, limit=100))
            for t in res.topics:
                if t.title.lower() == target_name.lower():
                    target_topic_id = t.id; break
            if not target_topic_id:
                try:
                    new_t = await client(functions.channels.CreateForumTopicRequest(channel=dst_ent, title=target_name))
                    target_topic_id = new_t.updates[0].id
                except:
                    target_topic_id = IntPrompt.ask("[red]Input manual Topic ID Tujuan[/red]")
    except: pass

    # --- FILTER ---
    m_filter = None
    if mode == "1": m_filter = types.InputMessagesFilterVideo()
    elif mode == "2": m_filter = types.InputMessagesFilterPhotos()

    src_ent = await client.get_input_entity(src_id)
    
    # --- PILIH URUTAN (PENTING BUAT SERIAL/DRAMA) ---
    # reverse=True artinya dari LAMA ke BARU (Episode 1 -> 2 -> 3)
    # reverse=False artinya dari BARU ke LAMA (Posting terbaru dulu)
    urut = Prompt.ask("Urutan Ambil?", choices=["Lama ke Baru", "Baru ke Lama"], default="Lama ke Baru")
    is_reverse = True if urut == "Lama ke Baru" else False

    console.print(f"[bold yellow]Mulai memindahkan... (Anti-Duplikat: ON)[/bold yellow]")
    
    # Mulai Loop
    async for msg in client.iter_messages(src_ent, reply_to=topic_id if topic_id > 0 else None, filter=m_filter, reverse=is_reverse):
        try:
            # 1. CEK HISTORY (Fitur Anti Duplikat)
            if resume_mode == "y":
                if is_processed(src_id, msg.id):
                    console.print(f"[dim]⏩ Skip ID {msg.id} (Sudah diproses)[/dim]")
                    continue # Langsung loncat ke pesan berikutnya

            # 2. VALIDASI TIPE FILE
            valid = False
            if mode == "3":
                if (hasattr(msg, 'video') and msg.video) or (hasattr(msg, 'photo') and msg.photo): valid = True
            else:
                valid = True 

            if valid:
                with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}[/bold cyan]"), BarColumn(), console=console) as prg:
                    t_desc = f"Moving ID {msg.id}..."
                    task = prg.add_task(t_desc, total=None)
                    
                    # DOWNLOAD
                    path = await client.download_media(msg)
                    
                    if path:
                        try:
                            # UPLOAD
                            await client.send_file(
                                dst_ent, 
                                path, 
                                caption=msg.text or "", 
                                reply_to=target_topic_id
                            )
                            
                            # 3. SUKSES? CATAT KE HISTORY!
                            save_to_history(src_id, msg.id)
                            
                            # Jeda biar aman
                            await asyncio.sleep(1) 
                            
                        except Exception as e:
                            console.print(f"[red]Gagal Upload ID {msg.id}: {e}[/red]")
                        finally:
                            if os.path.exists(path): os.remove(path)
                            
        except Exception as e:
            console.print(f"[red]Error Message {msg.id}: {e}[/red]")

    console.print("[bold green]✅ SEMUA SELESAI BOSKU![/bold green]")
    
