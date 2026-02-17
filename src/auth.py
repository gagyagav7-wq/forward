import os, json, glob
from rich.prompt import Prompt, IntPrompt
from rich.table import Table
from .utils import console, get_base_paths, show_banner

SESSION_DIR, CONFIG_FILE = get_base_paths()

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f: return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f: json.dump(data, f)

async def account_manager():
    show_banner()
    config = load_config()
    # Baca session dari folder data/sessions/
    sessions = [os.path.basename(f).replace(".session", "") for f in glob.glob(os.path.join(SESSION_DIR, "*.session"))]
    
    table = Table(title="Account Manager", border_style="cyan")
    table.add_column("No", style="dim"); table.add_column("Label", style="bold green")
    for i, s in enumerate(sessions, 1): table.add_row(str(i), s)
    console.print(table)
    
    choice = Prompt.ask("[bold cyan]Pilih / [+] Tambah / [x] Hapus[/bold cyan]", choices=[str(i) for i in range(1, len(sessions)+1)] + ["+", "x"])

    if choice == "+":
        name = Prompt.ask("Nama Label Akun (cth: AkunUtama)")
        api_id = IntPrompt.ask("API ID")
        api_hash = Prompt.ask("API HASH")
        config[name] = {"api_id": api_id, "api_hash": api_hash}
        save_config(config)
        return name, api_id, api_hash
        
    elif choice == "x":
        t = IntPrompt.ask("No Akun yg mau dihapus")
        n = sessions[t-1]
        sess_path = os.path.join(SESSION_DIR, f"{n}.session")
        if os.path.exists(sess_path): os.remove(sess_path)
        if n in config: del config[n]; save_config(config)
        return await account_manager() # Refresh menu
        
    else:
        name = sessions[int(choice)-1]
        # Handle kalau config manual hilang
        if name not in config:
             console.print("[red]Config hilang, input ulang API ID/Hash[/red]")
             api_id = IntPrompt.ask("API ID")
             api_hash = Prompt.ask("API HASH")
             config[name] = {"api_id": api_id, "api_hash": api_hash}
             save_config(config)
        
        return name, config[name]["api_id"], config[name]["api_hash"]
      
