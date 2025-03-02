from typing import List, Dict, Optional, Set
from .types import Peer, Clip
from .udp_discovery import UDPPeerDiscovery
import socket
import json
import uuid
from ..config.settings import Config
import pyperclip
import threading

class Clipboard:

    def __init__(self, discovery: UDPPeerDiscovery, config: Config):
        self.discovery = discovery # to get a list of active peers
        self.config = config # debug print & service port
        self.curr_clip_content = None # TODO: need to ensure this variable thread safe
        self.remote_clips: List[Clip] = []
        self.local_clips: List[Clip] = []
        self.max_clips = 20
        self.activate = True

        # TODO: look into other kind of implementation like TCP
        # Set up UDP connection for sending and accepting copied contents from other peers
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Use broadcasting from any interface # TODO: Check which interface to use
        self.udp_socket.bind(('', self.config.port))  # Use empty string instead of '0.0.0.0'

    def start(self) -> None:
        """Start all services."""
        self._start_threads()

    def stop(self) -> None:
        """Stop all services."""
        self.activate = False
        self.udp_socket.close()
    
    def _start_threads(self) -> None:
        """Start the broadcast and listener threads."""
        self.broadcast_thread = threading.Thread(target=self._listen_for_local_clip)
        self.broadcast_thread.daemon = True
        self.broadcast_thread.start()

        self.listen_thread = threading.Thread(target=self._listen_for_remote_clip)
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

    def _listen_for_local_clip(self) -> None:
        """Listen for new locally-copied content."""
        # TODO: check if possible to detect keys pressed in the background instead of comparing content
        while self.activate:
            try:
                content = pyperclip.paste()
                if content != self.curr_clip_content:
                    self.curr_clip_content = content
                    self.debug_print("New local copy detected")
                    clip = Clip(
                        id=str(uuid.uuid4()),  # for debugging purpose
                        content=content,
                        source='local'
                    )
                    self.add_to_clip_history(clip, self.local_clips)
                    self.send_clip(clip)
            except Exception as e:
                self.debug_print(f"Error checking new local copy")

    def _listen_for_remote_clip(self) -> None:
        """Listen for copied content from other peers"""
        while self.activate:
            try:
                raw_packet, addr = self.udp_socket.recvfrom(4096)
                self.debug_print(f"Received raw data from {addr}")
                packet = json.loads(raw_packet.decode())
                self.debug_print(f"Decoded packet type: {packet['type']}")

                if packet['type'] == 'clip':
                    clip = Clip.from_dict(packet['data'])
                    clip.source = 'remote'
                    self.add_to_clip_history(clip, self.remote_clips)
                    self.update_local_clipboard(clip.content)
            except Exception as e:
                if self.activate:
                    self.debug_print(f"Packet receiving error: {e}")
                    self.debug_print(f"Error details: {str(e)}")
    
    def send_clip(self, clip: Clip) -> None:
        """Send the clip content to all connected peers."""
        try:
            # Get active peers
            peers: Dict[str, Peer] = self.discovery.list_peers()
            packet = {
                'type': 'clip',
                'data': clip.to_dict()
                }
            # Send packet to each active peer
            for username, peer in peers.items():
                self.udp_socket.sendto(json.dumps(packet).encode(), peer.address, self.config.port)
                self.debug_print(f"Sent clip id {clip.id} to {username} at {peer.address}")
        except Exception as e:
            self.debug_print(f"Error sending clip id {clip.id}: {e}")

    def update_local_clipboard(self, content: str) -> None:
        """Copy a new content received from a remote peer to local clipboard if that's different from current copied content"""
        self.curr_clip_content = content
        pyperclip.copy(content)
        self.debug_print("Copied received content to local clipboard")

    def add_to_clip_history(self, clip: Clip, clip_list: List[Clip]) -> None:
        """Add the clip to a list of received clips."""
        clip_list.append(clip)
        if len(clip_list) > self.max_clips:
            clip_list.pop(0)
            
    def get_clipboard_history(self, source: str) -> List[Clip]:
        """Get a list of clips. Specify 'local' to get local clips, 'remote' for clips from peers."""
        if source == 'local':
            return self.local_clips
        elif source == 'remote':
            return self.remote_clips
    