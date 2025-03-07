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

    def __init__(self, discovery: UDPPeerDiscovery, config: Config, share_local_clip, accept_remote_clip):
        """Default not share local clips to peers or accepts clips from peers for better security."""
        self.curr_clip_content = pyperclip.paste() # initialize to previously copied content # TODO: ensure thread safety
        self.share_local_clip = share_local_clip
        self.accept_remote_clip = accept_remote_clip

        # Config Set up
        self.discovery = discovery # to get a list of active peers
        self.config = config # debug print & service port
        self.in_live_view = False

        # Set up UDP socket
        self.service_port = self.config.port + 1
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind(('', self.service_port))
        
        # Track recent clips
        self.remote_clips: List[Clip] = []
        self.local_clips: List[Clip] = []
        self.max_clips = 20        

    def start(self) -> None:
        """Start all services."""
        self._start_threads()

    def stop(self) -> None:
        """Stop all services."""
        self.share_local_clip = False
        self.accept_remote_clip = False
        self.udp_socket.close()
    
    def _start_threads(self) -> None:
        """Start the broadcast and listener threads."""
        if self.share_local_clip:
            self.local_clip_thread = threading.Thread(target=self._listen_for_local_clip)
            self.local_clip_thread.daemon = True
            self.local_clip_thread.start()

        if self.accept_remote_clip:
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
        while self.share_local_clip:
            try:
                content = pyperclip.paste()
                if content and content != self.curr_clip_content:
                    self._process_local_clip(content)
                    self.debug_print(f"New local copy detected...")

            except Exception as e:
                self.debug_print(f"Error checking new local copy {e}")

            time.sleep(0.5)

    def _process_local_clip(self, content: str) -> None:
        """Process newly detected local clip by updating the current clipt content and send it to peers."""
        self.curr_clip_content = content
        
        clip = Clip(
            id=str(uuid.uuid4())[:4],  # for debugging purpose
            content=content,
            source='local'
        )
        self.debug_print(f"New local copy id: {clip.id}")

        self.send_clip(clip)
        self.add_to_clip_history(clip, self.local_clips)

    def _listen_for_remote_clip(self) -> None:
        """Listen for copied content from other peers"""
        while self.accept_remote_clip:
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
        self.curr_clip_content = clip.content
        clip.source = 'remote'
        self.add_to_clip_history(clip, self.remote_clips)
        self.update_local_clipboard(clip.content)

    def send_clip(self, clip: Clip) -> None:
        """Send the clip content to all connected peers."""
        try:
            # Get active peers
            peers = self.discovery.list_peers()
            if not peers:
                self.debug_print("No active peers found to send clipboard content")
                return
            
            packet = {
                'type': 'clip',
                'data': clip.to_dict()
                }
            
            # Send packet to each active peer
            for username, peer in peers.items():
                self.debug_print(f"Sending clip id {clip.id} to peer - {username} at {peer.address}")
                self.udp_socket.sendto(json.dumps(packet).encode(), (peer.address, self.service_port))

        except Exception as e:
            self.debug_print(f"Error sending clip id {clip.id}: {e}")

    def update_local_clipboard(self, content: str) -> None:
        """Copy a new content received from a remote peer to local clipboard if that's different from current copied content"""
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
    