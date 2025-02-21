"""This file serves as the entry point of the LAN Sharing Service app.

The program parses user specifications from the command line, generates a 
random user id, then starts peer discovery and other services.

Start the app by running `python create.py create --username <enter_username>`
from the project directory.
"""


import argparse
import uuid
from lanshare.config.settings import Config
from lanshare.core.udp_discovery import UDPPeerDiscovery
from lanshare.ui.session import InteractiveSession

def generate_user_id(username: str) -> str:
    """Generates a short random ID for the user.

    Concatenates provided username with first 4 characters of a UUID to create
    a new unique username. In case different users provide the same username, 
    they can still differentiate each other using the random UUID after its
    username.    
    """
    
    random_id = str(uuid.uuid4())[:4]
    return f"{username}#{random_id}"

def main():
    # Parse user specifications
    parser = argparse.ArgumentParser(description='LAN Peer Discovery Service')
    parser.add_argument('command', choices=['create'], help='Command to execute')
    parser.add_argument('--username', help='Username for the peer', required=False)
    
    args = parser.parse_args()
    
    if args.command == 'create':
        if not args.username:
            parser.error("Username is required for 'create' command")
        
        # Generate username with random ID
        username_with_id = generate_user_id(args.username)
        
        # Start the service
        config = Config()
        discovery = UDPPeerDiscovery(username_with_id, config)
        discovery.start()
        
        # Start terminal UI
        session = InteractiveSession(discovery)
        session.start()

if __name__ == "__main__":
    main()