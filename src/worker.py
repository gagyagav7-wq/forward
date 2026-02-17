import os, asyncio
from telethon import TelegramClient, functions, types
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, IntPrompt
from .utils import console, fix_id

async def start_transit(client: TelegramClient):
    # Input Data
    src_id = fix_id(Prompt.ask("[bold cyan]Source Group ID[/bold cyan]"))
    topic_id = IntPrompt.ask("[bold cyan]Source Topic ID (0 jika tidak ada)[/bold cyan]", default=0)
    dst_id = fix_id(Prompt.ask("[bold cyan]Destination Group ID[/bold cyan]"))
    mode = Prompt.ask("Mode: 1.Video | 2.Photo | 3.All", choices=["1", "2", "3"], default="3")
    
    # Auto Topic Logic
    target_topic_id = None
    dst_ent = await client.get_input_entity(dst_id)
    
    # Cek apakah tujuan adalah forum
    try:
        full_channel = await client(functions.channels.GetFullChannelRequest(dst_ent))
        if full_channel.full_chat.forum:
            target_name = Prompt.ask("Target Topic Name")
            # Cari Topik
            res = await client(functions.channels.GetForumTopicsRequest(channel=dst_ent, offset_date=None, offset_id=0, offset_topic=0, limit=100))
            for t in res.topics:
                if t.title.lower() == target_name.lower():
                    target_topic_id = t.id; break
            
            # Kalau ga ada, bikin baru
            if not target_topic_id:
                try:
                    new_t = await client(functions.channels.CreateForumTopicRequest(channel=dst_ent, title=target_name))
                    target_topic_id = new_t.updates[0].id
                    console.print(f"[green]Topik baru dibuat: {target_name}[/green]")
                except:
                    target_topic_id = IntPrompt.ask("[red]Gagal auto-create. Input Topic ID Manual[/red]")
    except:
        pass # Bukan grup forum, lanjut

    # Setup Filter
    m_filter = None
    if mode == "1": m_filter = types.InputMessagesFilterVideo()
    elif mode == "2": m_filter = types.InputMessagesFilterPhotos()

    src_ent = await client.get_input_entity(src_id)
    
    # THE LOOP
    console.print(f"[bold yellow]Mulai memindahkan...[/bold yellow]")
    
    async for msg in client.iter_messages(src_ent, reply_to=topic_id if topic_id > 0 else None, filter=m_filter):
        try:
            # Logic validasi tipe file
            valid = False
            if mode == "3":
                if (hasattr(msg, 'video') and msg.video) or (hasattr(msg, 'photo') and msg.photo): valid = True
            else:
                valid = True # Karena sudah difilter di iter_messages

            if valid:
                with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}[/bold cyan]"), BarColumn(), console=console) as prg:
                    t_desc = f"Moving ID {msg.id}"
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
                            await asyncio.sleep(0.5) # Jeda dikit
                        except Exception as e:
                            console.print(f"[red]Gagal Upload: {e}[/red]")
                        finally:
                            # HAPUS SAMPAH
                            if os.path.exists(path): os.remove(path)
                            
        except Exception as e:
            console.print(f"[red]Error Message {msg.id}: {e}[/red]")

    console.print("[bold green]✅ SEMUA SELESAI BOSKU![/bold green]")
  
