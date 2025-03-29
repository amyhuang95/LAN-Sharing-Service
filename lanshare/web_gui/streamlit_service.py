"""
This module provides a service layer for Streamlit integration with LAN Sharing App
It uses a static variable to ensure all pages in the Streamlit share the same service instance.
"""

from typing import Dict, List

from lanshare.config.settings import Config
from lanshare.core.udp_discovery import UDPPeerDiscovery
from lanshare.core.clipboard import Clipboard
from lanshare.core.types import Peer, Clip

class StreamlitService:
    """Service layer for Streamlit integration with LAN Sharing app."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls, username: str, port: int = None):
        """Singleton pattern to ensure only one service instance at a time."""
        if cls._instance is None and username is not None:
            cls._instance = cls(username, port)
        return cls._instance
    
    def __init__(self, username: str, port: int):
        """Initialize the Streamlit service.
        
        Args:
            username: The username for this peer
            port: port number for the UDP discovery service
        """
        self.config = Config()
        self.username = username
        self.config.port = port  # Set the custom port if specified
        self.config.clipboard_port = port + 1 # Update clipboard port to be one higher than the main port
            
        self.discovery = UDPPeerDiscovery(self.username, self.config)
        self.clipboard = Clipboard(self.discovery, self.config)
        
        # Start background services
        self.discovery.start()
        
        # Status tracking
        self.clipboard_active = False
    
    def stop(self):
        """Stop all services."""
        self.running = False
        if self.clipboard_active:
            self.clipboard.stop()
            self.clipboard_active = False
        self.discovery.stop()
    
    # Peer discovery methods
    def get_active_peers(self) -> Dict[str, Peer]:
        """Get the list of active peers."""
        return self.discovery.list_peers()
    
    # Clipboard methods
    def start_clipboard(self):
        """Start the clipboard sharing service."""
        if not self.clipboard_active:
            self.clipboard.start()
            self.clipboard_active = True
    
    def stop_clipboard(self):
        """Stop the clipboard sharing service."""
        if self.clipboard_active:
            self.clipboard.stop()
            self.clipboard_active = False
    
    def toggle_clipboard(self) -> bool:
        """Toggle the clipboard sharing service."""
        if self.clipboard_active:
            self.stop_clipboard()
        else:
            self.start_clipboard()
        return self.clipboard_active
    
    def get_clipboard_history(self) -> List[Clip]:
        """Get the clipboard history."""
        if self.clipboard_active:
            return self.clipboard.get_clipboard_history()
        return []
    
    def add_clipboard_sharing_peer(self, peer: str):
        """Add a peer to share clipboard with."""
        if self.clipboard_active:
            self.clipboard.add_sending_peer(peer)
    
    def remove_clipboard_sharing_peer(self, peer: str):
        """Remove a peer from clipboard sharing."""
        if self.clipboard_active:
            self.clipboard.remove_sending_peer(peer)
    
    def add_clipboard_receiving_peer(self, peer: str):
        """Add a peer to receive clipboard from."""
        if self.clipboard_active:
            self.clipboard.add_receiving_peer(peer)
    
    def remove_clipboard_receiving_peer(self, peer: str):
        """Remove a peer from clipboard receiving."""
        if self.clipboard_active:
            self.clipboard.remove_receiving_peer(peer)
    
    def get_clipboard_sending_peers(self) -> List[str]:
        """Get the list of peers we're sending clipboard to."""
        if self.clipboard_active:
            return list(self.clipboard.send_to_peers)
        return []
    
    def get_clipboard_receiving_peers(self) -> List[str]:
        """Get the list of peers we're receiving clipboard from."""
        if self.clipboard_active:
            return list(self.clipboard.receive_from_peers)
        return []
    