"""This module implements file sharing functionality for the LAN sharing service."""

import os
import shutil
import threading
from pathlib import Path
import json
import socket
import ftplib
from typing import Dict, List, Optional, Set
import time
from datetime import datetime

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from .types import Peer


class SharedResource:
    """Represents a shared file or directory in the LAN sharing service.
    
    Attributes:
        id: Unique identifier for the shared resource.
        owner: Username of the owner.
        path: Original path of the resource on the owner's system.
        is_directory: Whether the resource is a directory.
        allowed_users: Set of usernames allowed to access the resource.
        shared_to_all: Whether the resource is shared to everyone.
        timestamp: When the resource was shared.
        ftp_password: Password for FTP access.
    """
    
    def __init__(self, 
                 owner: str, 
                 path: str, 
                 is_directory: bool = False, 
                 shared_to_all: bool = False,
                 ftp_password: str = None):
        """Initialize a SharedResource instance.
        
        Args:
            owner: Username of the resource owner.
            path: Path to the resource on the owner's system.
            is_directory: Whether the resource is a directory.
            shared_to_all: Whether the resource is shared to everyone.
            ftp_password: Password for FTP access.
        """
        self.id = f"{owner}_{int(time.time())}_{os.path.basename(path)}"
        self.owner = owner
        self.path = path
        self.is_directory = is_directory
        self.allowed_users = set()
        self.shared_to_all = shared_to_all
        self.timestamp = datetime.now()
        self.ftp_password = ftp_password
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary representation of the shared resource.
        """
        return {
            'id': self.id,
            'owner': self.owner,
            'path': self.path,
            'is_directory': self.is_directory,
            'allowed_users': list(self.allowed_users),
            'shared_to_all': self.shared_to_all,
            'timestamp': self.timestamp.isoformat(),
            'ftp_password': self.ftp_password
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SharedResource':
        """Create a SharedResource from a dictionary.
        
        Args:
            data: Dictionary containing shared resource data.
            
        Returns:
            SharedResource instance.
        """
        resource = cls(
            owner=data['owner'],
            path=data['path'],
            is_directory=data['is_directory'],
            shared_to_all=data['shared_to_all'],
            ftp_password=data.get('ftp_password')
        )
        resource.id = data['id']
        resource.allowed_users = set(data['allowed_users'])
        resource.timestamp = datetime.fromisoformat(data['timestamp'])
        return resource
    
    def add_user(self, username: str) -> None:
        """Add a user to the allowed users list.
        
        Args:
            username: Username to add.
        """
        self.allowed_users.add(username)
    
    def remove_user(self, username: str) -> None:
        """Remove a user from the allowed users list.
        
        Args:
            username: Username to remove.
        """
        if username in self.allowed_users:
            self.allowed_users.remove(username)
    
    def can_access(self, username: str) -> bool:
        """Check if a user can access this resource.
        
        Args:
            username: Username to check.
            
        Returns:
            True if the user can access, False otherwise.
        """
        return (self.owner == username or 
                username in self.allowed_users or 
                self.shared_to_all)


class FileShareManager:
    """Manages file sharing in the LAN sharing service.
    
    This class handles:
    1. Sharing files and directories with selected peers
    2. Managing access permissions
    3. Running an FTP server for file transfers
    4. Announcing shared resources to peers
    5. Downloading shared resources automatically
    """
    
    def __init__(self, username: str, discovery_service):
        """Initialize the FileShareManager.
        
        Args:
            username: Username of the user.
            discovery_service: The discovery service instance.
        """
        self.username = username
        self.discovery = discovery_service
        self.config = discovery_service.config
        
        # Directory where shared files are stored
        self.share_dir = Path.home() / 'shared'
        self.share_dir.mkdir(exist_ok=True)
        
        # Create directory for this user's shared files
        self.user_share_dir = self.share_dir / username
        self.user_share_dir.mkdir(exist_ok=True)
        
        # Tracking shared resources
        self.shared_resources: Dict[str, SharedResource] = {}
        self.received_resources: Dict[str, SharedResource] = {}
        
        # Download history to avoid downloading the same file multiple times
        self.downloaded_resources: Set[str] = set()
        
        # FTP server settings
        self.authorizer = DummyAuthorizer()
        self.ftp_handler = FTPHandler
        self.ftp_handler.authorizer = self.authorizer
        
        # Add the user to the authorizer with full permissions to their share directory
        self.default_password = "anonymous"  # Simplified password for easier testing
        self.authorizer.add_user(
            username, 
            password=self.default_password, 
            homedir=str(self.user_share_dir),
            perm='elradfmwMT'  # Full permissions
        )
        
        # Also add anonymous user for easier access
        try:
            self.authorizer.add_anonymous(str(self.user_share_dir), perm='elr')
        except Exception as e:
            self.discovery.debug_print(f"Warning: Could not add anonymous user: {e}")
        
        # Set up FTP server
        self.ftp_server = None
        self.ftp_address = ('0.0.0.0', self.config.port + 1)  # Use next port after discovery port
        
        # Server thread
        self.server_thread = None
        self.running = False
        
        # Load previously shared resources
        self._load_resources()
    
    def _generate_password(self) -> str:
        """Generate a random password for FTP access.
        
        Returns:
            Random password string.
        """
        import uuid
        return str(uuid.uuid4())[:12]
    
    def _load_resources(self) -> None:
        """Load previously shared resources from disk."""
        resource_file = self.user_share_dir / '.shared_resources.json'
        if resource_file.exists():
            try:
                with open(resource_file, 'r') as f:
                    data = json.load(f)
                    for resource_data in data.get('shared', []):
                        resource = SharedResource.from_dict(resource_data)
                        self.shared_resources[resource.id] = resource
                    
                    for resource_data in data.get('received', []):
                        resource = SharedResource.from_dict(resource_data)
                        self.received_resources[resource.id] = resource
                    
                    self.downloaded_resources = set(data.get('downloaded', []))
            except Exception as e:
                self.discovery.debug_print(f"Error loading shared resources: {e}")
    
    def _save_resources(self) -> None:
        """Save shared resources to disk."""
        resource_file = self.user_share_dir / '.shared_resources.json'
        try:
            data = {
                'shared': [r.to_dict() for r in self.shared_resources.values()],
                'received': [r.to_dict() for r in self.received_resources.values()],
                'downloaded': list(self.downloaded_resources)
            }
            with open(resource_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.discovery.debug_print(f"Error saving shared resources: {e}")
    
    def start(self) -> None:
        """Start the file sharing service."""
        if not self.running:
            try:
                # Create and start FTP server
                self.ftp_server = FTPServer(self.ftp_address, self.ftp_handler)
                self.server_thread = threading.Thread(target=self.ftp_server.serve_forever)
                self.server_thread.daemon = True
                self.server_thread.start()
                
                self.running = True
                self.discovery.debug_print(f"File sharing server started on port {self.ftp_address[1]}")
                
                # Announce previously shared resources
                for resource in self.shared_resources.values():
                    self._announce_resource(resource)
                    
            except Exception as e:
                self.discovery.debug_print(f"Error starting file sharing server: {e}")
    
    def stop(self) -> None:
        """Stop the file sharing service."""
        if self.running:
            try:
                self.running = False
                if self.ftp_server:
                    self.ftp_server.close_all()
                self._save_resources()
            except Exception as e:
                self.discovery.debug_print(f"Error stopping file sharing server: {e}")
    
    def share_resource(self, path: str, share_to_all: bool = False) -> Optional[SharedResource]:
        """Share a file or directory with peers.
        
        Args:
            path: Path to the file or directory to share.
            share_to_all: Whether to share with all peers.
            
        Returns:
            SharedResource if successful, None otherwise.
        """
        try:
            path = os.path.abspath(path)
            if not os.path.exists(path):
                self.discovery.debug_print(f"Path does not exist: {path}")
                return None
            
            is_directory = os.path.isdir(path)
            
            # Create shared resource with password
            resource = SharedResource(
                owner=self.username,
                path=path,
                is_directory=is_directory,
                shared_to_all=share_to_all,
                ftp_password=self.default_password
            )
            
            # Create symlink in user's share directory
            resource_name = os.path.basename(path)
            symlink_path = self.user_share_dir / resource_name
            
            # Handle name conflicts by appending a number
            counter = 1
            original_name = resource_name
            while symlink_path.exists():
                name_parts = os.path.splitext(original_name)
                resource_name = f"{name_parts[0]}_{counter}{name_parts[1]}"
                symlink_path = self.user_share_dir / resource_name
                counter += 1
            
            # On Windows, we can't easily use symlinks, so we'll copy the file/dir
            if os.name == 'nt':
                if is_directory:
                    shutil.copytree(path, symlink_path)
                else:
                    shutil.copy2(path, symlink_path)
            else:
                os.symlink(path, symlink_path)
            
            # Add to shared resources
            self.shared_resources[resource.id] = resource
            self._save_resources()
            
            # Announce to peers
            self._announce_resource(resource)
            
            self.discovery.debug_print(f"Shared {'directory' if is_directory else 'file'}: {path}")
            return resource
            
        except Exception as e:
            self.discovery.debug_print(f"Error sharing resource: {e}")
            return None
    
    def _announce_resource(self, resource: SharedResource) -> None:
        """Announce a shared resource to peers.
        
        Args:
            resource: The resource to announce.
        """
        try:
            packet = {
                'type': 'file_share',
                'action': 'announce',
                'data': resource.to_dict()
            }
            
            # Broadcast to all peers
            self.discovery.udp_socket.sendto(
                json.dumps(packet).encode(),
                ('<broadcast>', self.config.port)
            )
            
        except Exception as e:
            self.discovery.debug_print(f"Error announcing resource: {e}")
    
    def update_resource_access(self, resource_id: str, username: str, add: bool = True) -> bool:
        """Update access permissions for a shared resource.
        
        Args:
            resource_id: ID of the resource to update.
            username: Username to add or remove.
            add: True to add access, False to remove.
            
        Returns:
            True if successful, False otherwise.
        """
        if resource_id not in self.shared_resources:
            return False
        
        resource = self.shared_resources[resource_id]
        
        # Only the owner can modify access
        if resource.owner != self.username:
            return False
        
        if add:
            resource.add_user(username)
            action = 'add_access'
        else:
            resource.remove_user(username)
            action = 'remove_access'
        
        self._save_resources()
        
        # Announce access change
        try:
            packet = {
                'type': 'file_share',
                'action': action,
                'data': {
                    'resource_id': resource_id,
                    'username': username
                }
            }
            
            # Send update to specific peer
            peer = self.discovery.peers.get(username)
            if peer:
                self.discovery.udp_socket.sendto(
                    json.dumps(packet).encode(),
                    (peer.address, self.config.port)
                )
            
        except Exception as e:
            self.discovery.debug_print(f"Error updating resource access: {e}")
        
        return True
    
    def set_share_to_all(self, resource_id: str, share_to_all: bool) -> bool:
        """Set whether a resource is shared with all peers.
        
        Args:
            resource_id: ID of the resource to update.
            share_to_all: Whether to share with all peers.
            
        Returns:
            True if successful, False otherwise.
        """
        if resource_id not in self.shared_resources:
            return False
        
        resource = self.shared_resources[resource_id]
        
        # Only the owner can modify access
        if resource.owner != self.username:
            return False
        
        resource.shared_to_all = share_to_all
        self._save_resources()
        
        # Announce update
        self._announce_resource(resource)
        
        return True
    
    def handle_file_share_packet(self, packet: Dict, addr: tuple) -> None:
        """Handle a file share packet.
        
        Args:
            packet: The packet to handle.
            addr: The address the packet came from.
        """
        action = packet.get('action')
        data = packet.get('data', {})
        
        if action == 'announce':
            self._handle_resource_announcement(data, addr)
        elif action == 'add_access':
            self._handle_access_update(data, addr, add=True)
        elif action == 'remove_access':
            self._handle_access_update(data, addr, add=False)
    
    def _handle_resource_announcement(self, data: Dict, addr: tuple) -> None:
        """Handle a resource announcement.
        
        Args:
            data: The resource data.
            addr: The address the announcement came from.
        """
        try:
            resource = SharedResource.from_dict(data)
            
            # Skip if we're the owner
            if resource.owner == self.username:
                return
            
            # Check if we can access this resource
            if resource.can_access(self.username):
                # Store the resource
                self.received_resources[resource.id] = resource
                self._save_resources()
                
                # Create the owner's directory if it doesn't exist
                owner_dir = self.share_dir / resource.owner
                owner_dir.mkdir(exist_ok=True)
                
                # Check if this resource needs to be downloaded
                if resource.id not in self.downloaded_resources:
                    # Download the resource in a separate thread
                    download_thread = threading.Thread(
                        target=self._download_resource,
                        args=(resource, addr[0])
                    )
                    download_thread.daemon = True
                    download_thread.start()
                
                self.discovery.debug_print(
                    f"Received shared {'directory' if resource.is_directory else 'file'} from {resource.owner}: {os.path.basename(resource.path)}"
                )
            
        except Exception as e:
            self.discovery.debug_print(f"Error handling resource announcement: {e}")
    
    def _download_resource(self, resource: SharedResource, host_ip: str) -> None:
        """Download a resource from a peer.
        
        Args:
            resource: The resource to download.
            host_ip: The IP address of the host.
        """
        try:
            self.discovery.debug_print(f"Downloading {os.path.basename(resource.path)} from {host_ip}...")
            
            # Create destination path
            dest_dir = self.share_dir / resource.owner
            dest_path = dest_dir / os.path.basename(resource.path)
            
            # Create FTP connection
            ftp = ftplib.FTP()
            ftp.connect(host_ip, self.ftp_address[1])
            
            # Try different login methods
            login_successful = False
            
            # First, try using the provided password
            if resource.ftp_password:
                try:
                    ftp.login(resource.owner, resource.ftp_password)
                    login_successful = True
                    self.discovery.debug_print(f"Logged in with username and password")
                except Exception as e:
                    self.discovery.debug_print(f"FTP login with owner credentials failed: {e}")
            
            # If that fails, try anonymous login
            if not login_successful:
                try:
                    ftp.login('anonymous', 'anonymous@')
                    login_successful = True
                    self.discovery.debug_print(f"Logged in anonymously")
                except Exception as e:
                    self.discovery.debug_print(f"Anonymous FTP login failed: {e}")
            
            # If all login attempts failed, we can't proceed
            if not login_successful:
                self.discovery.debug_print(f"All FTP login attempts failed - cannot download resource")
                return
            
            # List files in current directory
            file_list = []
            ftp.dir(file_list.append)
            self.discovery.debug_print(f"FTP directory listing: {file_list}")
            
            # Check if the resource exists on the server
            filename = os.path.basename(resource.path)
            
            # Try to find the file in the directory listing
            found = False
            for item in file_list:
                if filename in item:
                    found = True
                    break
            
            if not found:
                self.discovery.debug_print(f"File {filename} not found on server")
                ftp.quit()
                return
            
            # Download the resource
            if resource.is_directory:
                # For directories, we need to recursively download
                try:
                    self._download_directory(ftp, os.path.basename(resource.path), dest_path)
                except Exception as e:
                    self.discovery.debug_print(f"Error downloading directory: {e}")
            else:
                # For files, just download the file
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                    with open(dest_path, 'wb') as f:
                        self.discovery.debug_print(f"Starting download of {filename}")
                        ftp.retrbinary(f'RETR {filename}', f.write)
                    self.discovery.debug_print(f"Successfully downloaded file to {dest_path}")
                except Exception as e:
                    self.discovery.debug_print(f"Error downloading file: {e}")
            
            # Close connection
            ftp.quit()
            
            # Mark as downloaded
            self.downloaded_resources.add(resource.id)
            self._save_resources()
            
            self.discovery.debug_print(f"Downloaded {resource.path} to {dest_path}")
            
        except Exception as e:
            self.discovery.debug_print(f"Error in download_resource: {e}")
    
    def _download_directory(self, ftp, remote_dir, local_dir):
        """Download a directory recursively.
        
        Args:
            ftp: FTP connection.
            remote_dir: Remote directory name.
            local_dir: Local directory path.
        """
        try:
            # Create local directory
            os.makedirs(local_dir, exist_ok=True)
            
            # Change to remote directory
            ftp.cwd(remote_dir)
            
            # Get directory listing
            items = []
            ftp.dir(items.append)
            
            # Process each item
            for item in items:
                parts = item.split()
                if len(parts) < 9:
                    continue
                    
                name = parts[-1]
                
                if name in ('.', '..'):
                    continue
                
                # Check if it's a directory
                is_dir = item.startswith('d')
                
                if is_dir:
                    # Recursively download subdirectory
                    self._download_directory(ftp, name, os.path.join(local_dir, name))
                else:
                    # Download file
                    local_path = os.path.join(local_dir, name)
                    with open(local_path, 'wb') as f:
                        ftp.retrbinary(f'RETR {name}', f.write)
            
            # Return to parent directory
            ftp.cwd('..')
            
        except Exception as e:
            self.discovery.debug_print(f"Error downloading directory: {e}")
    
    def _handle_access_update(self, data: Dict, addr: tuple, add: bool) -> None:
        """Handle an access update.
        
        Args:
            data: The update data.
            addr: The address the update came from.
            add: True if adding access, False if removing.
        """
        try:
            resource_id = data.get('resource_id')
            username = data.get('username')
            
            if username != self.username:
                return
            
            # Check if we have this resource
            for resources in [self.shared_resources, self.received_resources]:
                if resource_id in resources:
                    resource = resources[resource_id]
                    
                    if add:
                        resource.add_user(username)
                        # Download the resource if we're being granted access
                        if resource.owner != self.username and resource_id not in self.downloaded_resources:
                            peer = self.discovery.peers.get(resource.owner)
                            if peer:
                                download_thread = threading.Thread(
                                    target=self._download_resource,
                                    args=(resource, peer.address)
                                )
                                download_thread.daemon = True
                                download_thread.start()
                    else:
                        resource.remove_user(username)
                    
                    self._save_resources()
                    
                    action_str = "added to" if add else "removed from"
                    self.discovery.debug_print(
                        f"You were {action_str} the access list for {os.path.basename(resource.path)} from {resource.owner}"
                    )
            
        except Exception as e:
            self.discovery.debug_print(f"Error handling access update: {e}")
    
    def list_shared_resources(self, include_own: bool = True) -> List[SharedResource]:
        """List shared resources.
        
        Args:
            include_own: Whether to include resources shared by this user.
            
        Returns:
            List of SharedResource instances.
        """
        resources = []
        
        if include_own:
            resources.extend(self.shared_resources.values())
        
        resources.extend(self.received_resources.values())
        
        return sorted(resources, key=lambda r: r.timestamp, reverse=True)
    
    def get_resource_by_id(self, resource_id: str) -> Optional[SharedResource]:
        """Get a resource by ID.
        
        Args:
            resource_id: ID of the resource.
            
        Returns:
            SharedResource if found, None otherwise.
        """
        if resource_id in self.shared_resources:
            return self.shared_resources[resource_id]
        
        if resource_id in self.received_resources:
            return self.received_resources[resource_id]
        
        return None