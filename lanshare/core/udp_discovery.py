"""This module implements the peer discovery service."""

import socket
import json
import threading
import time
from datetime import datetime
from typing import Dict, Optional, List, Union
import uuid
import requests

from .discovery import PeerDiscovery
from .types import Peer, Message
from .file_share import FileShareManager
from ..config.settings import Config

class UDPPeerDiscovery(PeerDiscovery):
    """Manages peer discovery and communication using UDP.

    Multithreaded implementations for discovering peers and handling
    communication between them using UDP protocol with a fixed port. Peer 
    discovery is done by broadcasting its presence and listens for other peers' 
    broadcasts and direct messages. Broadcast packets are labeled with type 
    'announcement'. Message communication packets are labeled with type 'message'.
    File sharing packets are labeled with type 'file_share'.
    """
       
    def __init__(self, username: str, config: Config):
        """Initialize the UDPDiscovery instance.

        Args:
            username: The username of the user.
            config: The configuration containing settings.

        Attributes:
            username: The username of the user.
            config: The configuration object containing settings.
            peers: A dictionary to store peer information. Example: {username: 'Peer'}
            messages: A list to store messages.
            in_live_view: A flag indicating if the user is in live view mode.
            running: A flag indicating if the service is running.
            udp_socket: The UDP socket used for both broadcast and direct messages.
            file_share_manager: The file sharing manager.
        """

        self.username = username
        self.config = config
        self.peers: Dict[str, Peer] = {}
        self.messages: List[Message] = []
        self.in_live_view = False
        self.running = True

        # Single UDP socket for both broadcast and direct messages
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Allow broadcasting from any interface
        self.udp_socket.bind(('', self.config.port))  # Use empty string instead of '0.0.0.0'
        
        # Initialize file sharing manager
        self.file_share_manager = FileShareManager(username, self)
        
        # Initialize registry client for alternative peer discovery
        from .registry import RegistryClient
        self.registry_client = RegistryClient(self)
        self.using_registry = False

    def start(self) -> None:
        """Start all services."""
        self._start_threads()
        self.file_share_manager.start()

    def stop(self) -> None:
        """Stop all services and announce disconnection."""
        if self.running:
            try:
                # Announce disconnection before stopping
                self.announce_disconnection()
                # Give a moment for the message to be sent
                time.sleep(0.5)  
            except Exception as e:
                self.debug_print(f"Error during disconnection: {e}")
            
            self.running = False
            self.file_share_manager.stop()
            self.udp_socket.close()

    def _start_threads(self) -> None:
        """Start the broadcast and listener threads."""
        self.broadcast_thread = threading.Thread(target=self._broadcast_presence)
        self.broadcast_thread.daemon = True
        self.broadcast_thread.start()

        self.listen_thread = threading.Thread(target=self._listen_for_packets)
        self.listen_thread.daemon = True
        self.listen_thread.start()

    def debug_print(self, message: str) -> None:
        """Print debug message if enabled.
        
        Args: 
            message: information to be printed in the terminal.
        """
        self.config.load_config()
        if self.config.debug and not self.in_live_view:
            self.config.add_debug_message(message)

    def _broadcast_presence(self) -> None:
        """Sends broadcast announcement to peers in the network periodically."""
        while self.running:
            try:
                packet = {
                    'type': 'announcement',
                    'username': self.username,
                    'timestamp': datetime.now().isoformat()
                }
                # Use '<broadcast>' instead of '255.255.255.255'
                self.udp_socket.sendto(
                    json.dumps(packet).encode(),
                    ('<broadcast>', self.config.port)
                )
                self.debug_print(f"Broadcasting presence: {self.username}")
            except Exception as e:
                self.debug_print(f"Broadcast error: {e}")
                self.debug_print(f"Error details: {str(e)}")
            time.sleep(self.config.broadcast_interval)

    def announce_disconnection(self) -> None:
        """
        Broadcasts a disconnection announcement to all peers.
        This should be called before the application exits.
        """
        try:
            packet = {
                'type': 'disconnection',
                'username': self.username,
                'timestamp': datetime.now().isoformat()
            }
            # Broadcast disconnection announcement
            self.udp_socket.sendto(
                json.dumps(packet).encode(),
                ('<broadcast>', self.config.port)
            )
            self.debug_print(f"Broadcast disconnection announcement for {self.username}")
        except Exception as e:
            self.debug_print(f"Error announcing disconnection: {e}")

    def _listen_for_packets(self) -> None:
        """Listen for broadcasts, direct messages, and disconnection announcements."""
        self.debug_print(f"Started listening for packets on port {self.config.port}")
        while self.running:
            try:
                raw_packet, addr = self.udp_socket.recvfrom(4096)
                self.debug_print(f"Received raw data from {addr}")
                packet = json.loads(raw_packet.decode())
                self.debug_print(f"Decoded packet type: {packet['type']}")

                # Check packet type
                if packet['type'] == 'announcement':
                    self._handle_announcement(packet, addr)
                elif packet['type'] == 'message':
                    self._handle_message(packet)
                elif packet['type'] == 'file_share':
                    self.file_share_manager.handle_file_share_packet(packet, addr)
                elif packet['type'] == 'disconnection':
                    self._handle_disconnection(packet)
                
            except Exception as e:
                if self.running:
                    self.debug_print(f"Packet receiving error: {e}")
                    self.debug_print(f"Error details: {str(e)}")

    def _handle_announcement(self, packet: Dict, addr: tuple) -> None:
        """Processes broadcast announcements received from other peers in the network.
        
        Args:
            packet: Dict containing the broadcast announcement
            addr: Source network address of the packet
        """
        if packet['username'] != self.username:
            now = datetime.now()
            ip_address, port = addr
            # Check if this is a new peer or an existing one
            is_new_peer = packet['username'] not in self.peers
            
            if is_new_peer:
                # Create a new peer
                self.peers[packet['username']] = Peer(
                    username=packet['username'],
                    address=ip_address,
                    port=self.config.port,  # Use config port for broadcast peers
                    last_seen=now,
                    first_seen=now,
                    broadcast_peer=True,
                    registry_peer=False
                )
            else:
                # Update existing peer
                peer = self.peers[packet['username']]
                peer.last_seen = now
                peer.address = ip_address
                peer.port = self.config.port  # Update port
                peer.broadcast_peer = True
                # Don't change registry_peer status - keep it if set
            
            self.debug_print(f"Updated peer via broadcast: {packet['username']} at {addr[0]}")
            
            # If this is a new peer, announce shared resources to them
            if is_new_peer:
                self.debug_print(f"New peer detected via broadcast: {packet['username']} - announcing shared resources")
                self._announce_resources_to_new_peer(packet['username'], addr[0])

    def _announce_resources_to_new_peer(self, username: str, address: str, port: int = None) -> None:
        """Announce shared resources to a newly discovered peer.
        
        Args:
            username: The username of the new peer
            address: The IP address of the new peer
            port: Optional specific port to use
        """
        peer = self.peers.get(username)
        if not peer:
            self.debug_print(f"Cannot announce resources to unknown peer {username}")
            return
            
        # Determine the correct base port for the target peer
        # Check if explicitly provided port should be used
        if port is not None:
            target_port = port
            self.debug_print(f"Using explicitly provided port for announcements: {target_port}")
        # Check if this is a registry-discovered peer (which stores its port)
        elif hasattr(peer, 'registry_peer') and peer.registry_peer:
            target_port = peer.port
            self.debug_print(f"Using registry-provided port for announcements: {target_port}")
        # Fall back to config port for broadcast peers
        else:
            target_port = self.config.port
            self.debug_print(f"Using default config port for announcements: {target_port}")
        
        # Get resources the peer can access
        own_resources = [r for r in self.file_share_manager.shared_resources.values() 
                    if r.owner == self.username and 
                        (r.shared_to_all or username in r.allowed_users)]
        
        # Announce each resource
        for resource in own_resources:
            announce_packet = {
                'type': 'file_share',
                'action': 'announce',
                'data': resource.to_dict()
            }
            
            try:
                # Send with correct port
                self.udp_socket.sendto(
                    json.dumps(announce_packet).encode(),
                    (peer.address, target_port)
                )
                self.debug_print(f"Announced resource {resource.id} to peer {username} at {peer.address}:{target_port}")
            except Exception as e:
                self.debug_print(f"Error announcing resource to peer: {e}")

    def _handle_disconnection(self, packet: Dict) -> None:
        """
        Handles disconnection announcement from a peer.
        
        Args:
            packet: Dict containing the disconnection announcement
        """
        username = packet.get('username')
        if username and username != self.username and username in self.peers:
            self.debug_print(f"Peer disconnected: {username}")
            
            # If the peer was discovered only via broadcast, remove it completely
            # If it was also discovered via registry, just mark it as not broadcast-discovered
            if username in self.peers:
                peer = self.peers[username]
                if peer.registry_peer:
                    # If also registry-discovered, just mark as not broadcast-discovered
                    peer.broadcast_peer = False
                    self.debug_print(f"Peer {username} no longer available via broadcast, but still tracked via registry")
                else:
                    # If only broadcast-discovered, remove completely
                    del self.peers[username]
                    self.debug_print(f"Peer {username} completely removed (broadcast-only)")
                    
                    # Clean up their shared resources
                    self._cleanup_disconnected_peer_resources(username)

    def _cleanup_disconnected_peer_resources(self, username: str) -> None:
        """
        Removes all shared resources from a disconnected peer.
        
        Args:
            username: The username of the disconnected peer
        """
        try:
            # Find all resources shared by the disconnected user
            resources_to_remove = []
            for resource_id, resource in self.file_share_manager.received_resources.items():
                if resource.owner == username:
                    resources_to_remove.append(resource)
            
            # Remove each resource
            for resource in resources_to_remove:
                self.debug_print(f"Removing resource {resource.id} from disconnected peer {username}")
                
                # Remove the file/directory
                self.file_share_manager._remove_shared_resource(resource)
                
                # Remove from downloaded resources
                if resource.id in self.file_share_manager.downloaded_resources:
                    self.file_share_manager.downloaded_resources.remove(resource.id)
                
                # Remove from received resources
                if resource.id in self.file_share_manager.received_resources:
                    del self.file_share_manager.received_resources[resource.id]
            
            # Save the updated resources state
            if resources_to_remove:
                self.file_share_manager._save_resources()
                self.debug_print(f"Removed {len(resources_to_remove)} resources from disconnected peer {username}")
        
        except Exception as e:
            self.debug_print(f"Error cleaning up resources for disconnected peer {username}: {e}")

    def _handle_message(self, packet: Dict):
        """Processes incoming messages received from other peers.
        
        Args:
            packet: Dict containing the message information
        """
        try:
            msg = Message.from_dict(packet['data'])
            if msg.recipient == self.username:
                msg.timestamp = datetime.now() # update to received time
                self.messages.append(msg)
                self.debug_print(f"Received message from {msg.sender}: {msg.title}")
        except Exception as e:
            self.debug_print(f"Message handling error: {e}")

    def _generate_conversation_id(self, user1: str, user2: str) -> str:
        """Generate a consistent conversation ID for two users in a conversation.
        
        Args:
            user1: The username of one user
            user2: The username of the other user
        
        Returns:
            A conversation ID for user1 and user2 to look up the conversation later. 
        """
        # Sort usernames to ensure same ID regardless of sender/recipient
        sorted_users = sorted([user1, user2])
        # Create a consistent hash using the sorted usernames
        combined = f"{sorted_users[0]}:{sorted_users[1]}"
        import hashlib
        # Generate a short hash (first 5 characters)
        return hashlib.md5(combined.encode()).hexdigest()[:5]

    def send_message(self, recipient: str, title: str, content: str, 
                    conversation_id: Optional[str] = None,
                    reply_to: Optional[str] = None) -> Optional[Message]:
        """Send a message directly to a peer via UDP.
        
        Args:
            recipient: The username of the recipient.
            title: The title of the message.
            content: The content of the message.
            conversation_id: Optional conversation ID for the message.
            reply_to: Optional message ID to indicate this message is a reply.
        
        Returns:
            A Message instance.
        """
        peer = self.peers.get(recipient)
        if not peer:
            return None

        try:
            # Generate or use conversation ID
            conv_id = conversation_id if conversation_id else self._generate_conversation_id(self.username, recipient)

            message = Message(
                id=str(uuid.uuid4()),
                sender=self.username,
                recipient=recipient,
                title=title,
                content=content,
                timestamp=datetime.now(),
                conversation_id=conv_id,
                reply_to=reply_to
            )
            
            

            packet = {
                'type': 'message',
                'data': message.to_dict()
            }
            
            # Use the peer's stored port
            target_port = getattr(peer, 'port', self.config.port)   
                
            self.udp_socket.sendto(
                json.dumps(packet).encode(),
                (peer.address, target_port)
            )
            
            self.messages.append(message)
            self.debug_print(f"Sent message to {recipient} at {peer.address}:{target_port}: {title}")
            return message

        except Exception as e:
            self.debug_print(f"Error sending message: {e}")
            return None

    def list_peers(self) -> Dict[str, Peer]:
        """Get a list of active peers.
        
        Returns:
            A Dict containing peer username and the associated Peer instance. 
        """
        current_time = datetime.now()
        active_peers = {}

        # Process all peers
        for username, peer in list(self.peers.items()):
            keep_peer = False
            
            # If discovered via broadcast, check timeout
            if peer.broadcast_peer:
                time_diff = (current_time - peer.last_seen).total_seconds()
                if time_diff <= self.config.peer_timeout:
                    # Broadcast signal is still active
                    keep_peer = True
                else:
                    # Broadcast signal timed out
                    peer.broadcast_peer = False
                    self.debug_print(f"Peer {username} broadcast signal timed out after {time_diff:.1f} seconds")
                    
                    # If also registry-discovered, keep it
                    if peer.registry_peer:
                        keep_peer = True
                        self.debug_print(f"Keeping peer {username} as it's still tracked via registry")
            
            # If discovered via registry, keep it (registry client manages removal)
            if peer.registry_peer:
                keep_peer = True
                
            if keep_peer:
                active_peers[username] = peer
            else:
                self.debug_print(f"Removing peer {username} - not available via any discovery method")
                # Remove completely if no longer discovered via any method
                if username in self.peers:
                    del self.peers[username]
        
        return active_peers

    def list_messages(self, peer: Optional[str] = None) -> List[Message]:
        """List all messages or messages with specific peer.

        Args:
            peer: Optional list of peer usernames.
        
        Returns:
            A list of Message instances. 
        """
        if peer:
            return [msg for msg in self.messages 
                   if msg.sender == peer or msg.recipient == peer]
        return self.messages

    def get_conversation(self, conversation_id: str) -> List[Message]:
        """Get all messages in a conversation.
        
        Args:
            conversation_id: Unique identifier of the conversation.
        
        Returns:
            A list of message instances in the conversation. 
        """
        return [msg for msg in self.messages 
                if msg.conversation_id == conversation_id]

    # Registry server methods for enhanced peer discovery

    def register_with_server(self, server_url: str) -> bool:
        """Register with a registry server for peer discovery in restricted networks.
        
        Args:
            server_url: URL of the registry server (e.g., 'http://192.168.1.5:5000')
            
        Returns:
            bool: True if registration was successful, False otherwise
        """
        success = self.registry_client.register(server_url)
        self.using_registry = success
        return success

    def unregister_from_server(self) -> bool:
        """Unregister from the registry server.
        
        Returns:
            bool: True if unregistration was successful, False otherwise
        """
        success = self.registry_client.unregister()
        self.using_registry = False
        return success

    def is_using_registry(self) -> bool:
        """Check if the service is currently using a registry server.
        
        Returns:
            bool: True if using registry, False if using only UDP broadcast
        """
        return self.using_registry

    def get_registry_server_url(self) -> Optional[str]:
        """Get the URL of the currently connected registry server.
        
        Returns:
            Optional[str]: The URL or None if not connected to a registry
        """
        if self.registry_client.server_url and self.using_registry:
            return self.registry_client.server_url
        return None

    def cleanup(self) -> None:
        """Clean up resources and unregister from registry if needed."""
        if self.using_registry:
            self.unregister_from_server()
        
        if self.running:
            try:
                # Announce disconnection before stopping
                self.announce_disconnection()
                # Give a moment for the message to be sent
                time.sleep(0.5)  
            except Exception as e:
                self.debug_print(f"Error during disconnection: {e}")
            
            self.running = False
            self.file_share_manager.stop()
            self.udp_socket.close()