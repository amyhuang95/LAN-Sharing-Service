"""This file serves as the entry point of the LAN Sharing Service app.

The program parses user specifications from the command line, generates a 
random user id, then starts peer discovery and other services.

Start the app by running `python create.py create --username <enter_username>`
from the project directory.
"""

import argparse
import uuid
import shutil
import atexit
from pathlib import Path
import sys
import signal
import logging
import os
import threading
import subprocess

from lanshare.config.settings import Config
from lanshare.core.udp_discovery import UDPPeerDiscovery
from lanshare.core.clipboard import Clipboard
from lanshare.terminal_gui.session import InteractiveSession
from lanshare.server.server import *  

# ----------------- Logging Configuration ----------------- #
logging.basicConfig(level=logging.ERROR)
for logger_name in [
    'pyftpdlib',
    'pyftpdlib.server',
    'pyftpdlib.handler',
    'pyftpdlib.authorizer',
    'pyftpdlib.filesystems'
]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

# ----------------- Global Variables ----------------- #
discovery_service = None  # reference for cleanup

# ----------------- Exception Hook ----------------- #
def silent_excepthook(exc_type, exc_value, exc_traceback):
    """
    Override the default sys.excepthook to suppress errors during exit.
    Only show exceptions during normal operation, not during exit.
    """
    if not sys._getframe(1).f_code.co_name == 'graceful_shutdown':
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = silent_excepthook

# ----------------- Utility Functions ----------------- #
def generate_user_id(username: str) -> str:
    """Generates a short random ID for the user.

    Concatenates provided username with first 4 characters of a UUID to create
    a new unique username. In case different users provide the same username, 
    they can still differentiate each other using the random UUID after its
    username.
    """
    random_id = str(uuid.uuid4())[:4]
    return f"{username}#{random_id}"

def create_lanshare_folder():
    """Create the shared folder when the application starts."""
    shared_dir = Path.cwd() / 'shared'
    if shared_dir.exists():
        # If folder exists from a previous session that didn't exit properly, clean it
        shutil.rmtree(shared_dir)
    
    shared_dir.mkdir(exist_ok=True)
    print(f"Created temporary folder: {shared_dir}")
    return shared_dir

def cleanup_lanshare_folder():
    """Remove the shared folder when the application exits."""
    shared_dir = Path.cwd() / 'shared'
    if shared_dir.exists():
        try:
            shutil.rmtree(shared_dir)
            print(f"Cleaned up temporary folder: {shared_dir}")
        except Exception as e:
            print(f"Error cleaning up folder: {e}")

# ----------------- Cleanup and Shutdown ----------------- #
def graceful_shutdown():
    """Perform a graceful shutdown of all services."""
    global discovery_service
    if discovery_service:
        try:
            discovery_service.cleanup()
        except Exception:
            pass  # Suppress any shutdown errors
    
    cleanup_lanshare_folder()

def signal_handler(sig, frame):
    """Handle keyboard interrupts and other signals."""
    print("\nReceived exit signal. Cleaning up...")
    graceful_shutdown()
    sys.exit(0)

# ----------------- Main ----------------- #
def main():
    global discovery_service
    
    # Set up signal handlers for cleaner exit
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Register the cleanup function to run when the program exits normally
    atexit.register(graceful_shutdown)
    
    # Create the shared folder
    create_lanshare_folder()
    
    # Parse user specifications
    parser = argparse.ArgumentParser(description='LAN Peer Discovery Service')
    parser.add_argument('command', choices=['create'], help='Command to execute')
    parser.add_argument('--username', help='Username for the peer', required=False)
    parser.add_argument("--gui", choices=['terminal', 'streamlit'], default='terminal',
                        help="Select GUI implementation (default: terminal)")
    args = parser.parse_args()
    
    if args.command == 'create':
        if not args.username:
            parser.error("Username is required for 'create' command")
        
        # Generate username with random ID
        username_with_id = generate_user_id(args.username)
        
        # Start the discovery service
        config = Config()
        discovery_service = UDPPeerDiscovery(username_with_id, config)
        discovery_service.start()

        # Optionally start a clipboard service
        clipboard = Clipboard(discovery_service, config)
        
        # Choose GUI
        if args.gui == 'terminal':
            # ---------------- Terminal GUI ----------------
            session = InteractiveSession(discovery_service, clipboard)
            
            # Completely suppress stderr and stdout for clean exit
            class DevNull:
                def write(self, msg):
                    pass
                def flush(self):
                    pass
            
            try:
                devnull = open(os.devnull, 'w')
                sys.stderr = devnull  # Suppress pyftpdlib messages
                session.start()
                
            except KeyboardInterrupt:
                print("\nExiting application...", flush=True)
                
                # Immediately redirect both stderr and stdout to suppress exit messages
                sys.stderr = DevNull()
                sys.stdout = DevNull()
                
                # Also suppress threading excepthook errors
                threading.excepthook = lambda *args: None
        
        elif args.gui == 'streamlit':
            # ---------------- Web GUI ----------------
            # 1) Start the Flask server from server.py in a background thread
            flask_thread = threading.Thread(target=run_flask_server, daemon=True)
            flask_thread.start()
            print("[INFO] Flask server started on http://127.0.0.1:5000")

            # 2) Launch the Streamlit app via subprocess
            #    Pass the username so Streamlit can also use it
            cmd = [
                "streamlit", "run",
                "lanshare/web_gui/streamlit_app.py",
                "--",
                f"--username={username_with_id}"
            ]
            subprocess.run(cmd)
            
            # After Streamlit exits, gracefully shut down
            graceful_shutdown()
            sys.exit(0)

if __name__ == "__main__":
    main()
