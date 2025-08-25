import threading
import tkinter as tk

from util.keyboard import monitor_keyboards_thread

# --- Global State ---
# Stores the assigned evdev.InputDevice for each player.
player_keyboards = {}  # {player_id: evdev.InputDevice}
# Tracks which player is currently registering their keyboard (1 or 2).
current_player_registering = 1
# Flag to control the keyboard monitoring thread's lifecycle.
is_running = True
# A lock to protect access to shared state variables (player_keyboards, current_player_registering)
# when accessed from both the main Tkinter thread and the monitoring thread.
ui_update_lock = threading.Lock()

# --- Tkinter UI Elements ---
roots = [None, None]  # root windows for player 1 and 2
message_labels = [None, None]  # message labels for player 1 and 2

# --- Helper Functions ---

def update_ui(player_id):
    """
    Updates both Tkinter windows to prompt for the current player.
    """
    global roots, message_labels, player_keyboards

    for i in range(2):
        root = roots[i]
        message_label = message_labels[i]
        if root is None or message_label is None:
            continue

        if player_id == 1 and 1 not in player_keyboards:
            message = "Player 1: Press any key on your keyboard to register it."
        elif player_id == 2 and 2 not in player_keyboards:
            message = "Player 2: Press any key on your keyboard to register it."
        else:
            # Registration complete
            msg_parts = ["All keyboards registered!\n"]
            for pid, dev in player_keyboards.items():
                msg_parts.append(f"Player {pid}: {dev.name} ({dev.path})\n")
            message = "".join(msg_parts)
            message += "\nComplete. You can close this window."

        message_label.config(text=message)

def start():
    """Initializes and runs the dual-window Tkinter application using Toplevel windows."""
    global roots, message_labels

    root = tk.Tk()
    root.withdraw()  # Hide the root window

    # Create two Toplevel windows, one for each player
    for i in range(2):
        win = tk.Toplevel(root)
        win.title(f"Keyboard Registration - Player {i+1}")
        win.geometry(f"1270x710+{i*1280}+0")  # Position windows side by side; adjust as needed
        win.resizable(False, False)
        label = tk.Label(win, text="", font=("Inter", 16), wraplength=550, justify=tk.LEFT)
        label.pack(expand=True, padx=20, pady=20)
        roots[i] = win
        message_labels[i] = label

    # Initial UI update for both windows
    update_ui(1)

    # Start keyboard monitoring thread
    monitor_thread = threading.Thread(
        target=monitor_keyboards_thread,
        args=(current_player_registering, player_keyboards, is_running, root, ui_update_lock, update_ui),
        daemon=True
    )
    monitor_thread.start()

    # Periodically check if game is complete and close both windows
    def check_game_status_and_exit():
        if not is_running:
            for win in roots:
                if win is not None:
                    win.destroy()
            root.quit()
        else:
            root.after(100, check_game_status_and_exit)

    root.after(100, check_game_status_and_exit)

    root.mainloop()
    print("Tkinter main loop finished.")

# --- Main Execution ---
if __name__ == "__main__":
    print("Starting Keyboard Differentiation PoC (Dual Screen).")
    print("Make sure you have appropriate read permissions for /dev/input/event* devices.")
    print("If you encounter 'Permission denied' errors, try running with 'sudo python your_script_name.py'")
    start()


