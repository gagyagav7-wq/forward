import os
from rich.console import Console
from rich.panel import Panel

console = Console()

def fix_id(group_id):
    """Benerin ID Telegram biar valid (-100xxxx)"""
    group_id = str(group_id).strip()
    if group_id.isdigit(): return int(f"-100{group_id}")
    elif group_id.startswith("-") and not group_id.startswith("-100"):
        if group_id[1:].isdigit(): return int(f"-100{group_id[1:]}")
    try: return int(group_id)
    except: return group_id

def show_banner():
    """Tampilin Logo Keren"""
    console.clear()
    banner = """
    [bold cyan]NEON TRANSIT V12 (MODULAR)[/bold cyan]
    [dim]Github: Multi-Folder Structure[/dim]
    """
    console.print(Panel(banner, border_style="cyan", expand=False))

def get_base_paths():
    """Setup Path Otomatis"""
    BASE_DIR = os.getcwd() # Root project
    DATA_DIR = os.path.join(BASE_DIR, "data")
    SESSION_DIR = os.path.join(DATA_DIR, "sessions")
    CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
    
    # Bikin folder kalau belum ada
    if not os.path.exists(SESSION_DIR):
        os.makedirs(SESSION_DIR)
        
    return SESSION_DIR, CONFIG_FILE
  
