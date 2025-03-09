"""This module implements the peer discovery service."""

import socket
import json
import threading
import time
from datetime import datetime
from typing import Dict, Optional, List
import uuid

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

    def start(self) -> None:
        """Start all services."""
        self._start_threads()
        self.file_share_manager.start()

    def stop(self) -> None:
        """Stop all services."""
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
                # Add more detailed error info
                self.debug_print(f"Error details: {str(e)}")
            time.sleep(self.config.broadcast_interval)

    def _listen_for_packets(self) -> None:
        """Listen for both broadcasts and direct messages."""
        self.debug_print(f"Started listening for packets on port {self.config.port}")
        while self.running:
            try:
                raw_packet, addr = self.udp_socket.recvfrom(4096)
                self.debug_print(f"Received raw data from {addr}")
                packet = json.loads(raw_packet.decode())
                self.debug_print(f"Decoded packet type: {packet['type']}")

                # Check whether the packet is a broadcast announcement, a message, or a file share packet
                if packet['type'] == 'announcement':
                    self._handle_announcement(packet, addr)
                elif packet['type'] == 'message':
                    self._handle_message(packet)
                elif packet['type'] == 'file_share':
                    self.file_share_manager.handle_file_share_packet(packet, addr)
                
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
            
            # Check if this is a new peer or an existing one
            is_new_peer = packet['username'] not in self.peers
            
            self.peers[packet['username']] = Peer(
                username=packet['username'],
                address=addr[0],
                last_seen=now,
                first_seen=now if is_new_peer else 
                        self.peers[packet['username']].first_seen # use current time for newly connected peer, keep the old value for already connected peer
            )
            self.debug_print(f"Updated peer: {packet['username']} at {addr[0]}")
            
            # If this is a new peer, announce all our shared resources to them
            if is_new_peer:
                self.debug_print(f"New peer detected: {packet['username']} - announcing shared resources")
                # Get all resources shared by this user
                own_resources = [r for r in self.file_share_manager.shared_resources.values() 
                            if r.owner == self.username and 
                                (r.shared_to_all or packet['username'] in r.allowed_users)]
                
                # Announce each resource that this peer can access
                for resource in own_resources:
                    # Use direct UDP message to the new peer instead of broadcast
                    try:
                        announce_packet = {
                            'type': 'file_share',
                            'action': 'announce',
                            'data': resource.to_dict()
                        }
                        
                        # Send directly to the new peer
                        self.udp_socket.sendto(
                            json.dumps(announce_packet).encode(),
                            (addr[0], self.config.port)
                        )
                        self.debug_print(f"Announced resource {resource.id} to new peer {packet['username']}")
                    except Exception as e:
                        self.debug_print(f"Error announcing resource to new peer: {e}")

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

            self.udp_socket.sendto(
                json.dumps(packet).encode(),
                (peer.address, self.config.port)
            )
            
            self.messages.append(message)
            self.debug_print(f"Sent message to {recipient} at {peer.address}: {title}")
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

        # Gets peers whose last seene time were within the timeout limit
        for username, peer in self.peers.items():
            time_diff = (current_time - peer.last_seen).total_seconds()
            if time_diff <= self.config.peer_timeout:
                active_peers[username] = peer
            else:
                self.debug_print(f"Removing {username} - not seen for {time_diff:.1f} seconds")
        
        self.peers = active_peers
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

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop()