import json, os
from .utils import get_base_paths

# Setup Path
_, CONFIG_FILE = get_base_paths()
# Kita taruh history di folder data juga
HISTORY_FILE = os.path.join(os.path.dirname(CONFIG_FILE), "history.json")

def load_history():
    """Baca database riwayat"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            return {} # Kalau error/corrupt, bikin baru
    return {}

def save_to_history(source_id, message_id):
    """Nyatet ID yang sukses dipindah"""
    data = load_history()
    source_id = str(source_id) # Key harus string biar JSON ga bingung
    
    if source_id not in data:
        data[source_id] = []
    
    # Cuma nambahin kalau belum ada (biar ga double)
    if message_id not in data[source_id]:
        data[source_id].append(message_id)
        
        # Simpan balik ke file
        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2)

def is_processed(source_id, message_id):
    """Cek apakah video ini udah pernah dipindah?"""
    data = load_history()
    source_id = str(source_id)
    
    if source_id in data:
        if message_id in data[source_id]:
            return True
    return False

def get_last_id(source_id):
    """Ambil ID terakhir buat referensi (opsional)"""
    data = load_history()
    source_id = str(source_id)
    if source_id in data and data[source_id]:
        return max(data[source_id])
    return 0
  
