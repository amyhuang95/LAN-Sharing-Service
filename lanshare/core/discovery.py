"""This module defines the interface for peer discovery implementations."""

from abc import ABC, abstractmethod
from typing import Dict
from .types import Peer

class PeerDiscovery(ABC):
    """Base interface for peer discovery implementations"""
    
    @abstractmethod
    def _start_threads(self) -> None:
        """Start the necessary threads for peer discovery"""
        pass

    @abstractmethod
    def debug_print(self, message: str) -> None:
        """Print debug messages
        
        Args:
            message: information to be printed in the terminal.
        """
        pass

    @abstractmethod
    def list_peers(self) -> Dict[str, Peer]:
        """List all currently active peers
        
        Returns:
            A dict mapping username to the corresponding Peer object.
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up resources"""
        pass
    
    @abstractmethod
    def start(self) -> None:
        """Start the discovery service"""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the discovery service"""
        pass