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

    def __init__(self, discovery: UDPPeerDiscovery, config: Config):
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

        # Track recent clips
        self.clip_list: List[Clip] = []
        self.max_clips = 10
        
        # Default not start this service
        self.running = False

    def start(self) -> None:
        """Start all services."""
        # Set up UDP socket
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind(('', self.config.clipboard_port))
        
        self.running = True
        self._start_threads()

    def stop(self) -> None:
        """Stop all services."""
        self.running = False
        self.send_to_peers.clear()
        self.receive_from_peers.clear()
        self.udp_socket.close()
    
    def _start_threads(self) -> None:
        """Start the broadcast and listener threads."""
        self.local_clip_thread = threading.Thread(target=self._listen_for_local_clip)
        self.local_clip_thread.daemon = True
        self.local_clip_thread.start()

        self.remote_clip_thread = threading.Thread(target=self._listen_for_remote_clip)
        self.remote_clip_thread.daemon = True
        self.remote_clip_thread.start()

        self.refresh_peers_thread = threading.Thread(target=self._refresh_sharing_peers)
        self.refresh_peers_thread.daemon = True
        self.refresh_peers_thread.start()

    def debug_print(self, message: str) -> None:
        """Print debug message if enabled.
        
        Args: 
            message: information to be printed in the terminal.
        """
        self.discovery.debug_print(f"📋 Clipboard - {message}")

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
        # Check if sender is in receiving list
        if clip.source not in self.receive_from_peers:
            self.debug_print(f"Sender not in accepted peers list")
            return
        
        with self.clipboard_lock:
            self.curr_clip_content = clip.content # Update current clipboard content
            pyperclip.copy(clip.content)
            self.debug_print("Copied received content to local clipboard")
            self.add_to_clip_history(clip)

    def _refresh_sharing_peers(self):
        """
        Refresh the list of peers to share clips with. Removes inactive peers from the list.
        """
        while self.running:
            active_peers = set(self.discovery.list_peers())
            self.send_to_peers = self.send_to_peers & active_peers
            self.receive_from_peers = self.receive_from_peers & active_peers
            time.sleep(1) # refresh every 1 second

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
            # Get active peers
            peers = self.discovery.list_peers()
            if not peers or not self.send_to_peers:
                self.debug_print("No active peers found to send clipboard content")
                return
            
            packet = {
                'type': 'clip',
                'data': clip.to_dict()
                }
            
            for username in self.send_to_peers:
                self.debug_print(f"Sending clip id {clip.id} to peer - {username} at {peers[username].address}")
                self.udp_socket.sendto(json.dumps(packet).encode(), (peers[username].address, self.config.clipboard_port))

        except Exception as e:
            self.debug_print(f"Error sending clip id {clip.id}: {e}")

    def add_sending_peer(self, peer: str) -> None:
        """
        Add a peer to the list of peers to share clips with.

        Args:
            peer (str): username of the peer
        """
        active_peers = self.discovery.list_peers()
        if peer in active_peers:
            self.send_to_peers.add(peer)
    
    def remove_sending_peer(self, peer:str) -> None:
        """
        Remove a peer from the list of peers to share clips with.

        Args:
            peer (str): username of the peer
        """
        self.send_to_peers.remove(peer)

    def add_receiving_peer(self, peer: str) -> None:
        """
        Add a peer to the list of peers to accept clips from.

        Args:
            peer (str): username of the peer
        """
        active_peers = self.discovery.list_peers()
        if peer in active_peers:
            self.receive_from_peers.add(peer)
    
    def remove_receiving_peer(self, peer: str) -> None:
        """
        Remove a peer from the list of peers to accept clips from.

        Args:
            peer (str): username of the peer
        """
        self.receive_from_peers.remove(peer)

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
