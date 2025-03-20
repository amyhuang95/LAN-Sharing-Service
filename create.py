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

from lanshare.config.settings import Config
from lanshare.core.udp_discovery import UDPPeerDiscovery
from lanshare.core.clipboard import Clipboard
from lanshare.ui.session import InteractiveSession

# Configure logging to suppress pyftpdlib messages
logging.basicConfig(level=logging.ERROR)
for logger_name in ['pyftpdlib', 'pyftpdlib.server', 'pyftpdlib.handler', 
                    'pyftpdlib.authorizer', 'pyftpdlib.filesystems']:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

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
    
    # Create a fresh directory
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

# Global reference to discovery service for cleanup
discovery_service = None

def graceful_shutdown():
    """Perform a graceful shutdown of all services."""
    global discovery_service
    if discovery_service:
        try:
            # Properly shut down the discovery service (which includes FTP server)
            discovery_service.cleanup()
        except Exception:
            pass  # Suppress any shutdown errors
    
    # Now clean up the folder
    cleanup_lanshare_folder()

def signal_handler(sig, frame):
    """Handle keyboard interrupts and other signals."""
    print("\nReceived exit signal. Cleaning up...")
    graceful_shutdown()
    sys.exit(0)

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
    parser.add_argument("-sc", "--share_clip", help="Enable clipboard sharing with peers", action="store_true")
    
    args = parser.parse_args()
    
    if args.command == 'create':
        if not args.username:
            parser.error("Username is required for 'create' command")
        
        # Generate username with random ID
        username_with_id = generate_user_id(args.username)
        
        # Start the service
        config = Config()
        discovery_service = UDPPeerDiscovery(username_with_id, config)
        discovery_service.start()

        # Start clipboard sharing service (default off unless user enables it with command line args)
        clipboard = Clipboard(discovery_service, config, args.share_clip)
        clipboard.start()
        
        # Start terminal UI
        session = InteractiveSession(discovery_service, clipboard)
        try:
            # Redirect stderr to suppress pyftpdlib error messages
            original_stderr = sys.stderr
            devnull = open(os.devnull, 'w')
            sys.stderr = devnull
            
            session.start()
            
            # Restore stderr
            sys.stderr = original_stderr
            devnull.close()
        except KeyboardInterrupt:
            print("\nExiting application...")

if __name__ == "__main__":
    import os  # Add this import at the top if not already there
    main()