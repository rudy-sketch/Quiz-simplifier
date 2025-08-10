import tkinter as tk
from tkinter import scrolledtext
import threading
import sys
import os
import subprocess

# On importe l'application Flask et l'objet SocketIO depuis votre fichier server.py
from server import app, socketio, load_data

class TextRedirector:
    """Une classe pour rediriger le texte de la console vers un widget Tkinter."""
    def __init__(self, widget):
        self.widget = widget

    def write(self, str):
        self.widget.config(state=tk.NORMAL)
        self.widget.insert(tk.END, str)
        self.widget.see(tk.END) # Fait défiler vers le bas automatiquement
        self.widget.config(state=tk.DISABLED)

    def flush(self):
        pass # Requis par sys.stdout

def run_flask_app():
    """Fonction qui lance le serveur Socket.IO."""
    print("Démarrage du serveur Flask/Socket.IO...")
    try:
        # On utilise le port 5000 et l'hôte 0.0.0.0 comme dans votre script original
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
        print("Serveur arrêté.")
    except Exception as e:
        print(f"ERREUR SERVEUR: {e}")

def create_gui():
    """Crée et configure l'interface graphique."""
    root = tk.Tk()
    root.title("Contrôleur de Serveur - Quiz Night Arena")
    root.geometry("700x500")

    # Frame pour les boutons
    button_frame = tk.Frame(root, pady=10)
    button_frame.pack(fill=tk.X)

    # --- Fonctions des boutons ---
    def restart_server():
        print("\n>>> REDÉMARRAGE DU SERVEUR...\n")
        # Relance le script actuel dans un nouveau processus
        python_executable = sys.executable
        script_path = os.path.abspath(__file__)
        subprocess.Popen([python_executable, script_path])
        # Ferme la fenêtre actuelle
        root.destroy()

    def stop_server():
        print("\n>>> ARRÊT DU SERVEUR...\n")
        # Ferme simplement la fenêtre. Le thread du serveur étant un "daemon", il s'arrêtera avec le programme principal.
        root.destroy()

    # --- Création des boutons ---
    restart_button = tk.Button(button_frame, text="Redémarrer", command=restart_server, width=15, height=2, bg="#f59e0b", fg="white", font=("Arial", 10, "bold"))
    restart_button.pack(side=tk.LEFT, padx=20)

    stop_button = tk.Button(button_frame, text="Arrêter", command=stop_server, width=15, height=2, bg="#ef4444", fg="white", font=("Arial", 10, "bold"))
    stop_button.pack(side=tk.RIGHT, padx=20)

    # --- Widget pour afficher la console ---
    console_output = scrolledtext.ScrolledText(root, state=tk.DISABLED, wrap=tk.WORD, bg="black", fg="white", font=("Courier New", 10))
    console_output.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)

    # Rediriger stdout (les prints) et stderr (les erreurs) vers notre widget
    sys.stdout = TextRedirector(console_output)
    sys.stderr = TextRedirector(console_output)

    # --- Lancement du serveur dans un thread séparé ---
    # Le 'daemon=True' assure que le thread s'arrête quand la fenêtre principale est fermée
    server_thread = threading.Thread(target=run_flask_app, daemon=True)
    server_thread.start()

    # Lancer la boucle principale de l'interface
    root.mainloop()

if __name__ == '__main__':
    print("Chargement des données initiales...")
    load_data() # Charge les données une fois avant de lancer l'interface
    create_gui()