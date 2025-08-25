import threading
import tkinter as tk

from util.keyboard import monitor_keyboards_thread

# --- Global State ---
# Stores the assigned evdev.InputDevice for each player.
player_keyboards = {}  # {player_id: evdev.InputDevice}
# Tracks which player is currently registering their keyboard (1 or 2).
current_player_registering = 1
# Flag to control the keyboard monitoring thread's lifecycle.
poc_running = True
# A lock to protect access to shared state variables (player_keyboards, current_player_registering)
# when accessed from both the main Tkinter thread and the monitoring thread.
ui_update_lock = threading.Lock()

# --- Tkinter UI Elements ---
root = None  # The main Tkinter window
message_label = None  # Label to display instructions and status to the user

# --- Helper Functions ---

def update_ui():
    """
    Updates the Tkinter window's message label.
    This function is scheduled to run on the main Tkinter thread using `root.after()`.
    """
    global current_player_registering, root, message_label, poc_running

    if root is None or message_label is None: # Ensure UI elements exist
        return

    with ui_update_lock: # Acquire lock to safely read shared state
        if current_player_registering == 1:
            message = "Player 1: Press any key on your keyboard to register it."
        elif current_player_registering == 2:
            message = "Player 2: Press any key on your keyboard to register it."
        else: # Both players have registered their keyboards
            msg_parts = ["All keyboards registered!\n"]
            for player, device in player_keyboards.items():
                msg_parts.append(f"Player {player}: {device.name} ({device.path})\n")
            message = "".join(msg_parts)
            message += "\nPoC complete. You can close this window."
            poc_running = False # Signal the monitoring thread to stop

    message_label.config(text=message)



def start_poc():
    """Initializes and runs the Tkinter PoC application."""
    global root, message_label

    root = tk.Tk()
    root.title("Keyboard Registration PoC")
    root.geometry("1280x720") # Set window size
    root.resizable(False, False) # Prevent resizing for simplicity

    # Configure the message label with Inter font and text wrapping.
    message_label = tk.Label(root, text="", font=("Inter", 16), wraplength=550, justify=tk.LEFT)
    message_label.pack(expand=True, padx=20, pady=20)

    update_ui() # Display the initial message for Player 1

    # Start the keyboard monitoring logic in a separate daemon thread.
    # A daemon thread will automatically exit when the main program exits.
    monitor_thread = threading.Thread(target=monitor_keyboards_thread, args=(current_player_registering, player_keyboards, poc_running, root, ui_update_lock, update_ui), daemon=True)
    monitor_thread.start()

    # Schedule a periodic check on the main Tkinter thread to see if the PoC is complete.
    # If complete, it will gracefully close the Tkinter window.
    def check_poc_status_and_exit():
        if not poc_running:
            if root is not None:
                root.quit() # Use quit() to exit the Tkinter mainloop
        else:
            root.after(100, check_poc_status_and_exit) # Re-schedule check after 100ms
    
    root.after(100, check_poc_status_and_exit) # Start the periodic check

    root.mainloop() # Start the Tkinter event loop
    print("Tkinter main loop finished.")


# --- Main Execution ---
if __name__ == "__main__":
    print("Starting Keyboard Differentiation PoC.")
    print("Make sure you have appropriate read permissions for /dev/input/event* devices.")
    print("If you encounter 'Permission denied' errors, try running with 'sudo python your_script_name.py'")
    start_poc()


