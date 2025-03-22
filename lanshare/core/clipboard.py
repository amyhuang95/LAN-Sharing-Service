"""This module implements the clipboard sharing feature."""

import socket
import time
from typing import List
from .types import Clip
from .udp_discovery import UDPPeerDiscovery
import json
import uuid
from ..config.settings import Config
import pyperclip
import threading

class Clipboard:

    def __init__(self, discovery: UDPPeerDiscovery, config: Config, activate: bool):
        """Initialize the Clipboard synchronization service.
        This constructor sets up the clipboard service that allows sharing clipboard content
        between peers on a local network.

        Args:
            discovery (UDPPeerDiscovery): Discovery service to identify active peers on the network.
            config (Config): Configuration settings for the clipboard service.
            activate (bool): Whether to immediately activate the clipboard service upon initialization.
                If True, the service starts running; if False, it needs to be manually started later.

        Attributes:
            curr_clip_content (str): The current clipboard content, initialized with the last copied content.
            clipboard_lock (threading.Lock): Lock to prevent concurrent updates to the clipboard content.
            send_to_peers (set): Set of peers to which local clipboard content will be sent.
            receive_from_peers (set): Set of peers from which remote clipboard content will be accepted.
            username (str): Username obtained from the discovery service.
            in_live_view (bool): Flag indicating if the clipboard is currently being viewed live.
            udp_socket (socket.socket): UDP socket used for sending/receiving clipboard content.
            clip_list (List[Clip]): List to track recent clipboard items.
            max_clips (int): Maximum number of clipboard items to retain in history.
            running (bool): Flag indicating if the clipboard service is currently running.
        """
        self.curr_clip_content = pyperclip.paste()
        self.clipboard_lock = threading.Lock()
        self.send_to_peers = set()
        self.receive_from_peers = set()

        # Config Set up
        self.discovery = discovery # to get a list of active peers's address
        self.username = self.discovery.username
        self.config = config # debug print & service port
        self.in_live_view = False

        # Set up UDP socket
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind(('', self.config.clipboard_port))
        
        # Track recent clips
        self.clip_list: List[Clip] = []
        self.max_clips = 20
        
        # Run the service if user activates it
        self.activate = activate
        self.running = True if activate else False

    def start(self) -> None:
        """Start all services."""
        self._start_threads()

    def stop(self) -> None:
        """Stop all services."""
        self.running = False
        self.udp_socket.close()
    
    def _start_threads(self) -> None:
        """Start the broadcast and listener threads."""
        self.local_clip_thread = threading.Thread(target=self._listen_for_local_clip)
        self.local_clip_thread.daemon = True
        self.local_clip_thread.start()

        self.remote_clip_thread = threading.Thread(target=self._listen_for_remote_clip)
        self.remote_clip_thread.daemon = True
        self.remote_clip_thread.start()

    def debug_print(self, message: str) -> None:
        """Print debug message if enabled.
        
        Args: 
            message: information to be printed in the terminal.
        """
        self.config.load_config()
        if self.config.debug and not self.in_live_view:
            self.config.add_debug_message(f"📋 Clipboard - {message}")

    def _listen_for_local_clip(self) -> None:
        """Listen for new locally-copied content."""
        while self.running:
            try:
                content = pyperclip.paste()
                if content and content != self.curr_clip_content:
                    self._process_local_clip(content)
                    self.debug_print(f"New local copy detected...")

            except Exception as e:
                self.debug_print(f"Error checking new local copy {e}")

            time.sleep(0.5)

    def _process_local_clip(self, content: str) -> None:
        """
        Process a newly detected local clipboard change.
        
        This method updates the current clipboard content and shares it with all connected peers.
        It generates a unique ID for the clip, broadcasts it to allowed peers, and adds it to the
        local clip history.
        
        Args:
            content (str): The new clipboard content detected locally
        """
        with self.clipboard_lock:
            self.curr_clip_content = content
            clip = Clip(
                id=str(uuid.uuid4())[:4],  # for debugging purpose
                content=content,
                source=self.username
            )
            self.debug_print(f"New local copy id: {clip.id}")

            self.send_clip(clip)
            self.add_to_clip_history(clip)

    def _listen_for_remote_clip(self) -> None:
        """Listen for copied content from other peers"""
        while self.running:
            try:
                raw_packet, _ = self.udp_socket.recvfrom(4096)
                packet = json.loads(raw_packet.decode())
                if packet["type"] == "clip":
                    clip = Clip.from_dict(packet["data"])
                    self.debug_print(f"New remote copy id: {clip.id}")
                    self._process_remote_clip(clip)

            except Exception as e:
                self.debug_print(f"Packet receiving error: {e}")

    def _process_remote_clip(self, clip: Clip) -> None:
        """
        Process clipboard content received from remote peers with proper synchronization.

        This method updates the local clipboard with content received from remote peers,
        but only if the sender is in the accepted peers list.

        Args:
            clip (Clip): The clipboard object containing the content and metadata from remote peer
        """
        if clip.source not in self.receive_from_peers:
            self.debug_print(f"Sender not in accepted peers list")
            return
        with self.clipboard_lock:
            self.curr_clip_content = clip.content # Update current clipboard content
            pyperclip.copy(clip.content)
            self.debug_print("Copied received content to local clipboard")
            self.add_to_clip_history(clip)

    def send_clip(self, clip: Clip) -> None:
        """
        Send the clip content to selected connected peers.
        
        This method sends clipboard content to all allowed peers. 
        It first checks if there are active peers available,
        then creates a clip packet and sends it via UDP to each selected peer.
        
        Args:
            clip (Clip): The clipboard content object to be sent.
        """
        try:
            # Get peers from discovery service
            peers = self.discovery.list_peers()
            if not peers or not self.send_to_peers:
                self.debug_print("No active peers found to send clipboard content")
                return
            
            packet = {
                'type': 'clip',
                'data': clip.to_dict()
            }
            
            for username in self.send_to_peers:
                if username in peers:
                    peer = peers[username]
                    
                    # Determine target port based on discovery method
                    # For registry peers, use their registered port + 1
                    # For broadcast peers, use the config clipboard port
                    if hasattr(peer, 'registry_peer') and peer.registry_peer:
                        # For registry peers, base_port is explicitly stored
                        base_port = getattr(peer, 'port', self.discovery.config.port)
                        clipboard_port = base_port + 1
                        self.debug_print(f"Using registry port for clipboard: {base_port} + 1 = {clipboard_port}")
                    else:
                        # For broadcast peers, use the clipboard port directly
                        clipboard_port = self.config.clipboard_port
                    
                    self.debug_print(f"Sending clip id {clip.id} to peer - {username} at {peer.address}:{clipboard_port}")
                    self.udp_socket.sendto(
                        json.dumps(packet).encode(), 
                        (peer.address, clipboard_port)
                    )
        except Exception as e:
            self.debug_print(f"Error sending clip id {clip.id}: {e}")
            
    def update_send_to_peers(self, peers: list[str]) -> None:
        """
        Update the list of peers that will receive local clipboard changes.
        
        This method replaces the current set of peers with a new set created from the provided list. 
        Only these peers will receive clipboard updates from the local machine.

        Args:
            peers (list[str]): A list of peer identifiers to send clipboard updates to.
                              Each identifier should uniquely identify a peer in the network.
        """
        self.send_to_peers = set(peers)

    def update_receive_from_peers(self, peers: list[str]) -> None:
        """
        Update the list of peers from which this node will accept remote clipboard data.

        Args:
            peers (list[str]): List of peer IDs that are allowed to send clipboard 
                              content to this node. Duplicates will be automatically removed.
        """
        self.receive_from_peers = set(peers)

    def add_to_clip_history(self, clip: Clip) -> None:
        """
        Add a clip to the history of received clips.

        This method maintains a bounded history of clips by removing the oldest clip
        when the maximum capacity is reached.

        Args:
            clip (Clip): The clip object to be added to the history.
        """

        self.clip_list.append(clip)
        if len(self.clip_list) > self.max_clips:
            self.clip_list.pop(0)
            
    def get_clipboard_history(self) -> List[Clip]:
        """Retrieves a list of clip contents from the current clipboard history."""
        return self.clip_list
