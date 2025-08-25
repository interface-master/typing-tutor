import evdev
from evdev import InputDevice, categorize, ecodes
import time
import select
import os
import fcntl

def is_keyboard(device):
    """
    Checks if an evdev device is likely a keyboard.
    This is a heuristic based on device capabilities.
    """
    # A keyboard must support EV_KEY events (key presses/releases).
    if ecodes.EV_KEY not in device.capabilities():
        return False

    # Additionally, check for common keyboard keys to be more specific.
    # This helps filter out devices like mice that might also send some EV_KEY events.
    # We check for a selection of typical QWERTY keys.
    if any(k in device.capabilities()[ecodes.EV_KEY] for k in [ecodes.KEY_A, ecodes.KEY_Z, ecodes.KEY_SPACE, ecodes.KEY_ENTER, ecodes.KEY_1]):
        return True
    return False


def discover_available_keyboards(player_keyboards):
    """
    Scans for all potential keyboard devices using evdev and returns
    a dictionary of {file_descriptor: InputDevice} for devices that are:
    1. Identified as keyboards by `is_keyboard`.
    2. Not yet assigned to a player.
    It also ensures devices are opened in non-blocking mode.
    """
    available_devices = {}
    
    # Use /dev/input/by-id for more stable and unique device identification.
    # This directory contains symbolic links that usually point to /dev/input/eventX
    # but use persistent IDs, making it easier to distinguish between identical devices.
    by_id_devices = {}
    by_id_path = '/dev/input/by-id'
    if os.path.exists(by_id_path):
        for entry in os.listdir(by_id_path):
            full_path = os.path.join(by_id_path, entry)
            event_path = os.path.realpath(full_path) # Resolve symlink to actual /dev/input/eventX path
            if event_path.startswith('/dev/input/event'):
                try:
                    dev = InputDevice(event_path)
                    if is_keyboard(dev):
                        by_id_devices[dev.path] = dev # Store by path to avoid duplicates
                    else:
                        dev.close() # Close non-keyboard devices to release file descriptors
                except Exception:
                    # Ignore devices that cannot be opened (e.g., permissions) or are invalid
                    pass

    # Fallback: Also scan /dev/input/event* directly to catch any devices missed by /dev/input/by-id,
    # or if /dev/input/by-id is not populated on the system.
    for path in evdev.list_devices():
        if path not in by_id_devices: # Avoid re-processing devices already found via by-id
            try:
                dev = InputDevice(path)
                if is_keyboard(dev):
                    by_id_devices[dev.path] = dev
                else:
                    dev.close()
            except Exception:
                pass

    # Get paths of keyboards already assigned to players to filter them out.
    assigned_paths = [dev.path for dev in player_keyboards.values()]

    # Process discovered devices: set non-blocking, add to available_devices if not assigned.
    for path, dev in by_id_devices.items():
        if path not in assigned_paths:
            # Set the device's file descriptor to non-blocking mode.
            # This is crucial for `select.select` to work without blocking the thread
            # if no events are available from a specific device.
            fd = dev.fd
            flag = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flag | os.O_NONBLOCK)
            available_devices[fd] = dev
            # Uncomment for detailed debugging:
            # print(f"Discovered unassigned keyboard: {dev.name} ({dev.path}) [FD: {fd}]")
        else:
            dev.close() # Close devices that are already assigned to release resources

    return available_devices


def monitor_keyboards_thread(current_player_registering, player_keyboards, is_running, root, ui_update_lock, update_ui):
    """
    This function runs in a separate thread. It continuously monitors
    key presses from all available keyboards and assigns them to players
    as keys are pressed.
    """
    print("Starting keyboard monitoring thread...")

    # Keeps track of devices currently being monitored by THIS thread.
    open_devices = {} # {fd: InputDevice}

    while is_running:
        with ui_update_lock: # Safely check if Game should continue running
            if current_player_registering > 2:
                break # Both players registered, stop monitoring

        # Discover currently available (unassigned) keyboards.
        # This also ensures previously assigned or non-keyboard devices are closed.
        newly_available_devices = discover_available_keyboards(player_keyboards)

        # Close any devices that were previously open in this thread but are
        # no longer available, assigned, or relevant.
        fds_to_close = [fd for fd in open_devices if fd not in newly_available_devices]
        for fd in fds_to_close:
            try:
                open_devices[fd].close()
                del open_devices[fd]
                # print(f"Closed old device FD: {fd}")
            except Exception as e:
                print(f"Error closing old device {fd}: {e}")

        # Add newly available devices to our current monitoring set.
        for fd, dev in newly_available_devices.items():
            if fd not in open_devices:
                open_devices[fd] = dev
                # print(f"Now monitoring: {dev.name} ({dev.path}) [FD: {fd}]")

        if not open_devices:
            # No unassigned keyboards to listen to, wait a bit before re-scanning.
            time.sleep(0.5)
            continue

        read_fds = list(open_devices.keys())
        
        try:
            # Use select.select to wait for data on any of the file descriptors.
            # The timeout (0.05s) prevents blocking indefinitely, allowing the
            # `is_running` flag to be checked and the thread to terminate gracefully.
            rlist, _, _ = select.select(read_fds, [], [], 0.05)
        except ValueError as e:
            # This can happen if a file descriptor becomes invalid.
            print(f"Select error (ValueError): {e}. Re-scanning devices.")
            # Force a re-discovery of devices on the next iteration.
            for dev in open_devices.values():
                try:
                    dev.close()
                except Exception:
                    pass
            open_devices.clear()
            time.sleep(0.1)
            continue
        except Exception as e:
            # Catch any other unexpected errors during select.
            print(f"An unexpected error occurred in select.select: {e}")
            time.sleep(0.1)
            continue

        for fd in rlist: # Iterate through file descriptors that have events ready
            dev = open_devices.get(fd)
            if not dev:
                continue # Device might have been removed or closed

            try:
                # Read all pending events from the device.
                for event in dev.read():
                    if event.type == ecodes.EV_KEY: # We are interested in key events
                        data = categorize(event)
                        if data.keystate == data.key_down: # Only process key presses (not releases)
                            print(f"Key press detected on: {dev.name} ({dev.path})")
                            
                            with ui_update_lock: # Acquire lock before modifying shared state
                                # Assign keyboard to the current player if it's not already assigned
                                if current_player_registering <= 2 and dev.path not in [d.path for d in player_keyboards.values()]:
                                    player_keyboards[current_player_registering] = dev
                                    print(f"Assigned Player {current_player_registering} to keyboard: {dev.name} ({dev.path})")
                                    current_player_registering += 1
                                    # Schedule UI update on the main Tkinter thread.
                                    root.after(0, update_ui, current_player_registering)
                                    
                                    if current_player_registering > 2:
                                        print("Both players registered. Monitoring thread will stop.")
                                        is_running = False # Signal thread to terminate
                                        break # Exit event loop
                if not is_running:
                    break # Exit fd loop if Game is done
            except BlockingIOError:
                pass # No more events to read from this device right now, continue to next fd.
            except OSError as e:
                # Handle cases where a device might be disconnected or have permission issues.
                print(f"OSError reading from {dev.name} ({dev.path}): {e}. Device might be disconnected.")
                if fd in open_devices:
                    try:
                        open_devices[fd].close()
                    except Exception:
                        pass
                    del open_devices[fd]
                break # Break from this fd loop to force a re-evaluation of `open_devices`
            except Exception as e:
                # Catch any other unexpected errors during event processing.
                print(f"Error processing event from {dev.name} ({dev.path}): {e}")
        
        # Small sleep to prevent a tight loop if no events are detected but is_running is still true.
        if is_running:
            time.sleep(0.01) 

    print("Keyboard monitoring thread finished.")
    # Ensure all open device file descriptors are explicitly closed when the thread exits.
    for dev in open_devices.values():
        try:
            dev.close()
        except Exception:
            pass
    for dev in player_keyboards.values():
        try:
            dev.close()
        except Exception:
            pass
