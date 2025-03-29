"""
This module provides a service layer for Streamlit integration with LAN Sharing App
It uses a static variable to ensure all pages in the Streamlit share the same service instance.
"""

from lanshare.config.settings import Config
from lanshare.core.udp_discovery import UDPPeerDiscovery
from lanshare.core.clipboard import Clipboard

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
    
    