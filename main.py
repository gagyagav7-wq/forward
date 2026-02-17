import asyncio, os
from telethon import TelegramClient
from src.auth import account_manager, SESSION_DIR
from src.utils import console
from src.worker import start_transit

async def main():
    try:
        # 1. Login Process
        name, api_id, api_hash = await account_manager()
        
        # Setup Client dengan Path Session yang rapi
        session_path = os.path.join(SESSION_DIR, name)
        client = TelegramClient(session_path, api_id, api_hash)
        
        # 2. Start Client
        await client.start()
        
        console.print(f"[bold green]Login Berhasil: {name}[/bold green]")
        
        # 3. Masuk ke Logic Utama
        await start_transit(client)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Diberhentikan oleh user.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]CRITICAL ERROR: {e}[/bold red]")

if __name__ == "__main__":
    asyncio.run(main())
  
