"""Registry client for connecting to rendezvous server.

This module extends the UDPPeerDiscovery with registry server capabilities.
"""

import requests
import threading
import time
import socket
from typing import Optional, Dict, Set
from datetime import datetime

class RegistryClient:
    """Client for connecting to a registry server to discover peers."""
    
    def __init__(self, discovery_service):
        """Initialize registry client.
        
        Args:
            discovery_service: The UDPPeerDiscovery service instance
        """
        self.discovery = discovery_service
        self.server_url = None
        self.registered = False
        self.heartbeat_thread = None
        self.refresh_thread = None
        self.running = False
        self.refresh_interval = 0.5  # Refresh peers every 0.5 seconds
        self.heartbeat_interval = 10.0  # Send heartbeat every 10 seconds
        # Keep track of registry peers we've seen
        self.known_registry_peers: Set[str] = set()
        self.seen_registry_peers: Set[str] = set()
    
    def get_local_ip(self) -> str:
        """Get the local IP address of this device."""
        try:
            # Create a temporary socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "127.0.0.1"  # Fallback to localhost
    
    def register(self, server_url: str) -> bool:
        """Register this peer with the registry server.
        
        Args:
            server_url: URL of the registry server (e.g., 'http://192.168.1.5:5000')
            
        Returns:
            bool: True if registration was successful, False otherwise
        """
        try:
            # Make sure URL has http:// prefix
            if not server_url.startswith('http://') and not server_url.startswith('https://'):
                server_url = 'http://' + server_url
                
            # If only hostname:port is provided, extract and reformat
            if '://' in server_url and not server_url.split('://', 1)[1].startswith('http'):
                server_url = 'http://' + server_url.split('://', 1)[1]
            
            self.server_url = server_url
            
            # Register with the server
            response = requests.post(
                f"{server_url}/register",
                json={
                    "username": self.discovery.username,
                    "address": self.get_local_ip(),
                    "port": self.discovery.config.port
                },
                timeout=5  # 5-second timeout
            )
            
            if response.status_code == 200 and response.json().get("status") == "registered":
                self.registered = True
                self.running = True
                self.discovery.debug_print(f"Successfully registered with registry server at {server_url}")
                
                # Clear known peers list
                self.known_registry_peers.clear()
                self.seen_registry_peers.clear()
                
                # Start heartbeat thread
                self._start_heartbeat_thread()
                
                # Start peer refresh thread
                self._start_peer_refresh_thread()
                
                return True
            else:
                error_msg = response.json().get("message", "Unknown error")
                self.discovery.debug_print(f"Failed to register with registry: {error_msg}")
                return False
                
        except requests.RequestException as e:
            self.discovery.debug_print(f"Error connecting to registry server: {e}")
            return False
        except Exception as e:
            self.discovery.debug_print(f"Unexpected error in registration: {e}")
            return False
    
    def unregister(self) -> bool:
        """Unregister from the registry server.
        
        Returns:
            bool: True if unregistration was successful, False otherwise
        """
        if not self.registered or not self.server_url:
            return True  # Nothing to unregister
            
        try:
            # Stop threads
            self.running = False
            
            # Wait for threads to finish if they exist
            if self.heartbeat_thread and self.heartbeat_thread.is_alive():
                self.heartbeat_thread.join(1.0)  # Wait up to 1 second
                
            if self.refresh_thread and self.refresh_thread.is_alive():
                self.refresh_thread.join(1.0)  # Wait up to 1 second
            
            # Unregister from the server
            response = requests.post(
                f"{self.server_url}/unregister",
                json={"username": self.discovery.username},
                timeout=5
            )
            
            # Update registry peers
            self._cleanup_registry_peers()
            
            if response.status_code == 200:
                self.discovery.debug_print(f"Successfully unregistered from registry server")
                return True
            else:
                error_msg = response.json().get("message", "Unknown error")
                self.discovery.debug_print(f"Failed to unregister: {error_msg}")
                return False
                
        except requests.RequestException as e:
            self.discovery.debug_print(f"Error connecting to registry server during unregister: {e}")
            # Still clean up registry peers
            self._cleanup_registry_peers()
            return False
        except Exception as e:
            self.discovery.debug_print(f"Unexpected error in unregistration: {e}")
            # Still clean up registry peers
            self._cleanup_registry_peers()
            return False
        finally:
            self.registered = False
            self.known_registry_peers.clear()
            self.seen_registry_peers.clear()
    
    def _cleanup_registry_peers(self):
        """Update peers when disconnecting from registry."""
        # Find all peers that need modification
        peers_to_remove = []
        
        # For all peers that were registry-discovered
        for username, peer in self.discovery.peers.items():
            if hasattr(peer, 'registry_peer') and peer.registry_peer:
                if hasattr(peer, 'broadcast_peer') and peer.broadcast_peer:
                    # If also broadcast-discovered, just mark as not registry-discovered
                    peer.registry_peer = False
                    self.discovery.debug_print(f"Marking peer {username} as broadcast-only (was dual)")
                else:
                    # If only registry-discovered, mark for removal
                    peers_to_remove.append(username)
        
        # Remove peers that were only registry-discovered
        for username in peers_to_remove:
            if username in self.discovery.peers:
                del self.discovery.peers[username]
                self.discovery.debug_print(f"Removed registry-only peer: {username}")
    
    def _start_heartbeat_thread(self) -> None:
        """Start thread to send periodic heartbeats to the registry server."""
        def send_heartbeats():
            while self.running and self.registered:
                try:
                    response = requests.post(
                        f"{self.server_url}/heartbeat",
                        json={"username": self.discovery.username},
                        timeout=5
                    )
                    
                    if response.status_code != 200:
                        self.discovery.debug_print(f"Heartbeat failed with status code: {response.status_code}")
                        # If we get several failures, we might want to consider reconnecting
                        
                except requests.RequestException as e:
                    self.discovery.debug_print(f"Error sending heartbeat: {e}")
                except Exception as e:
                    self.discovery.debug_print(f"Unexpected error in heartbeat: {e}")
                
                # Sleep for the heartbeat interval
                for _ in range(int(self.heartbeat_interval / 0.1)):
                    if not self.running:
                        break
                    time.sleep(0.1)
        
        self.heartbeat_thread = threading.Thread(target=send_heartbeats)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
    
    def _start_peer_refresh_thread(self) -> None:
        """Start thread to periodically refresh the peer list from the registry."""
        def refresh_peers():
            from datetime import datetime
            
            consecutive_failures = 0
            
            while self.running and self.registered:
                try:
                    # Clear the seen peers set for this refresh cycle
                    self.seen_registry_peers.clear()
                    
                    # Get peers from registry server
                    response = requests.get(f"{self.server_url}/peers", timeout=5)
                    
                    if response.status_code == 200:
                        consecutive_failures = 0  # Reset failure counter
                        peer_data = response.json()
                        now = datetime.now()
                        
                        # Process each peer
                        for peer in peer_data:
                            username = peer.get("username")
                            
                            # Skip ourselves
                            if username == self.discovery.username:
                                continue
                                
                            # Get address and port
                            address = peer.get("address")
                            port = peer.get("port", self.discovery.config.port)  # Get port, default to config
                            
                            # Add to seen peers set
                            self.seen_registry_peers.add(username)
                            self.known_registry_peers.add(username)
                            
                            # Process this registry peer
                            self._process_registry_peer(username, address, port, now)
                            
                        # Check for registry peers that have disappeared
                        self._check_disappeared_peers()
                    else:
                        consecutive_failures += 1
                        self.discovery.debug_print(f"Failed to refresh peers, status code: {response.status_code}")
                        
                        # If we've had too many failures, consider the registry connection lost
                        if consecutive_failures > 5:
                            self.discovery.debug_print("Too many consecutive failures, registry connection may be lost")
                            # You could add auto-reconnect logic here
                
                except requests.RequestException as e:
                    consecutive_failures += 1
                    self.discovery.debug_print(f"Error refreshing peers from registry: {e}")
                    
                    # If we've had too many failures, consider the registry connection lost
                    if consecutive_failures > 5:
                        self.discovery.debug_print("Too many consecutive failures, registry connection may be lost")
                        # You could add auto-reconnect logic here
                        
                except Exception as e:
                    self.discovery.debug_print(f"Unexpected error refreshing registry peers: {e}")
                
                # Sleep before next refresh, using short intervals to check if we're still running
                for _ in range(int(self.refresh_interval / 0.1)):
                    if not self.running:
                        break
                    time.sleep(0.1)
        
        self.refresh_thread = threading.Thread(target=refresh_peers)
        self.refresh_thread.daemon = True
        self.refresh_thread.start()
        
    def _process_registry_peer(self, username: str, address: str, port: int, now: datetime) -> None:
        """Process a peer discovered through the registry.
        
        Args:
            username: Peer's username
            address: Peer's IP address
            port: Peer's port number
            now: Current timestamp
        """
        # Check if this is a completely new peer
        is_new_peer = username not in self.discovery.peers
        
        if is_new_peer:
            # Create the peer
            from .types import Peer
            self.discovery.peers[username] = Peer(
                username=username,
                address=address,
                port=port,  # Store the port explicitly
                last_seen=now,
                first_seen=now,
                registry_peer=True,  # Mark as registry-discovered
                broadcast_peer=False  # Initially not broadcast-discovered
            )
            self.discovery.debug_print(f"New peer found via registry: {username} at {address}:{port}")
            # Announce resources to new peer
            self.discovery._announce_resources_to_new_peer(username, address, port)
        else:
            # Update existing peer
            peer = self.discovery.peers[username]
            peer.last_seen = now
            peer.address = address
            peer.port = port  # Update port
            peer.registry_peer = True  # Mark as registry-discovered
            # Don't change the broadcast_peer flag - keep it if set
            
            # If this peer is dual-discovered, log it
            if peer.broadcast_peer:
                self.discovery.debug_print(f"Peer {username} is dual-discovered (registry + broadcast)")
    
    def _check_disappeared_peers(self) -> None:
        """Check for peers that have disappeared from the registry."""
        for username in list(self.known_registry_peers):
            if username not in self.seen_registry_peers:
                # Peer has disappeared from the registry
                if username in self.discovery.peers:
                    peer = self.discovery.peers[username]
                    
                    # Always clean up resources when a peer disappears from registry
                    # This happens regardless of whether they're also broadcast-discovered
                    self.discovery.debug_print(f"Registry peer {username} disappeared - cleaning up their resources")
                    self.discovery._cleanup_disconnected_peer_resources(username)
                    
                    if peer.broadcast_peer:
                        # If also discovered via broadcast, just mark as not registry-discovered
                        peer.registry_peer = False
                        self.discovery.debug_print(f"Peer {username} no longer available via registry, but still tracked via broadcast")
                    else:
                        # If only discovered via registry, remove completely
                        del self.discovery.peers[username]
                        self.discovery.debug_print(f"Removed peer {username} - no longer available via registry")
                    
                # Remove from known registry peers
                self.known_registry_peers.remove(username)