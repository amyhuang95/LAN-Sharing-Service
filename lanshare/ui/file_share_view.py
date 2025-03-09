"""This module provides a file sharing view for the LAN sharing service."""

import os
import logging
from datetime import datetime
from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import Window, HSplit, VSplit, FloatContainer, Float
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.layout.dimension import LayoutDimension as D
import threading
import time


class FileShareView:
    """View for managing file sharing."""
    
    def __init__(self, discovery):
        """Initialize the file share view.
        
        Args:
            discovery: The discovery service instance.
        """
        self.discovery = discovery
        # Direct access to the file share manager
        self.file_share_manager = discovery.file_share_manager
        self.running = True
        self.command_buffer = Buffer()
        self.status_text = ""
        self.status_history = []  # Store important messages
        self.selected_index = 0
        self.resources = []
        
        # Setup key bindings and styles
        self._setup_keybindings()
        self._setup_styles()
    
    def _setup_keybindings(self):
        """Setup keyboard shortcuts"""
        self.kb = KeyBindings()

        @self.kb.add('q')
        def _(event):
            """Exit on 'q'"""
            self.running = False
            event.app.exit()
        
        @self.kb.add('s')
        def _(event):
            """Share a new file or directory"""
            event.app.layout.focus(self.command_window)
            self.status_text = "Share mode: Enter the path to share (press Enter when done)"
            self.command_mode = "share"
            event.app.invalidate()
        
        @self.kb.add('a')
        def _(event):
            """Add access for a user"""
            if not self.resources:
                self.status_text = "No resources available to modify access"
                self._add_to_status_history("No resources available to modify access")
                event.app.invalidate()
                return
                
            resource = self.resources[self.selected_index]
            if resource.owner != self.discovery.username:
                self.status_text = "You can only modify access for resources you own"
                self._add_to_status_history("You can only modify access for resources you own")
                event.app.invalidate()
                return
                
            event.app.layout.focus(self.command_window)
            self.status_text = f"Add access: Enter username to grant access to resource {resource.id}"
            self.command_mode = "add_access"
            event.app.invalidate()
        
        @self.kb.add('r')
        def _(event):
            """Remove access for a user"""
            if not self.resources:
                self.status_text = "No resources available to modify access"
                self._add_to_status_history("No resources available to modify access")
                event.app.invalidate()
                return
                
            resource = self.resources[self.selected_index]
            if resource.owner != self.discovery.username:
                self.status_text = "You can only modify access for resources you own"
                self._add_to_status_history("You can only modify access for resources you own")
                event.app.invalidate()
                return
                
            event.app.layout.focus(self.command_window)
            self.status_text = f"Remove access: Enter username to remove access from resource {resource.id[:8]}"
            self.command_mode = "remove_access"
            event.app.invalidate()
        
        @self.kb.add('e')
        def _(event):
            """Share with everyone"""
            if not self.resources:
                self.status_text = "No resources available to modify access"
                self._add_to_status_history("No resources available to modify access")
                event.app.invalidate()
                return
                
            resource = self.resources[self.selected_index]
            if resource.owner != self.discovery.username:
                self.status_text = "You can only modify access for resources you own"
                self._add_to_status_history("You can only modify access for resources you own")
                event.app.invalidate()
                return
            
            self._share_with_all(resource.id, not resource.shared_to_all)
            event.app.invalidate()
        
        @self.kb.add('up')
        def _(event):
            """Move selection up"""
            if self.resources:
                self.selected_index = max(0, self.selected_index - 1)
                event.app.invalidate()
        
        @self.kb.add('down')
        def _(event):
            """Move selection down"""
            if self.resources:
                self.selected_index = min(len(self.resources) - 1, self.selected_index + 1)
                event.app.invalidate()
        
        @self.kb.add('enter')
        def _(event):
            """Process command input"""
            if event.app.layout.has_focus(self.command_window):
                self._process_command(self.command_buffer.text)
                self.command_buffer.text = ""
                event.app.layout.focus(self.main_window)
                event.app.invalidate()
    
    def _setup_styles(self):
        """Setup UI styles"""
        self.style = Style.from_dict({
            'border': '#666666',
            'title': 'bold #ffffff',
            'label': '#888888',
            'selected': 'reverse',
            'resource_id': '#ff00ff',
            'resource_type': '#00ffff',
            'owner': '#00aa00 bold',
            'peer': '#0000ff bold',
            'access': '#ffaa00',
            'date': '#888888',
            'command': '#ffffff bg:#000088',
            'status': 'bold #ff0000',
            'help': 'italic #888888',
            'history': '#ffcc00',  # Color for status history items
        })
    
    def _add_to_status_history(self, message):
        """Add an important message to the status history.
        
        Args:
            message: The message to add.
        """
        # Add timestamp to the message
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_history.append(f"[{timestamp}] {message}")
        
        # Keep only the last 5 messages
        if len(self.status_history) > 5:
            self.status_history = self.status_history[-5:]
    
    def _get_resources_text(self):
        """Generate the formatted resources list text"""
        # Use file_share_manager directly
        self.resources = self.file_share_manager.list_shared_resources()
        
        text = [
            ("", "\n"),
            ("class:title", "  Shared Resources "),
            ("", "\n"),
            ("", "  "),
            ("class:border", "╭" + "─" * 110 + "╮"),  # Increased width to 110
            ("", "\n")
        ]
        
        if not self.resources:
            text.extend([
                ("", "  "),
                ("class:border", "│"),
                ("fg:gray", " No resources shared yet"),
                ("", " " * (109 - len("No resources shared yet"))),  # Adjusted spacing
                ("class:border", "│"),
                ("", "\n")
            ])
        else:
            # Header
            text.extend([
                ("", "  "),
                ("class:border", "│"),
                ("class:label", f" {'ID':<8} {'Type':<10} {'Name':<20} {'Owner':<12} {'Access':<12} {'Shared On':<16} {'Last Modified':<25}"),
                ("class:border", "│"),
                ("", "\n"),
                ("", "  "),
                ("class:border", "├" + "─" * 110 + "┤"),  # Increased width to 110
                ("", "\n")
            ])
            
            # Resource entries
            for idx, resource in enumerate(self.resources):
                resource_type = "Directory" if resource.is_directory else "File"
                owner = "You" if resource.owner == self.discovery.username else resource.owner
                access = "Everyone" if resource.shared_to_all else ", ".join(resource.allowed_users) or "Only owner"
                if len(access) > 12:
                    access = access[:9] + "..."
                shared_date = resource.timestamp.strftime("%Y-%m-%d %H:%M")
                
                # Format modification time
                try:
                    mod_time = datetime.fromtimestamp(resource.modified_time).strftime("%Y-%m-%d %H:%M")
                except:
                    mod_time = "Unknown"
                
                name = os.path.basename(resource.path)
                if len(name) > 20:
                    name = name[:17] + "..."
                
                # Apply selection highlight if this is the selected item
                style_prefix = "class:selected " if idx == self.selected_index else ""
                
                text.extend([
                    ("", "  "),
                    ("class:border", "│"),
                    (f"{style_prefix}class:resource_id", f" {resource.id[:7]:<8} "),
                    (f"{style_prefix}class:resource_type", f"{resource_type:<10} "),
                    (f"{style_prefix}", f"{name:<20} "),
                    (f"{style_prefix}class:{'owner' if owner == 'You' else 'peer'}", f"{owner:<12} "),
                    (f"{style_prefix}class:access", f"{access:<12} "),
                    (f"{style_prefix}class:date", f"{shared_date:<16} "),
                    (f"{style_prefix}class:date", f"{mod_time:<25}"),
                    ("class:border", "│"),
                    ("", "\n")
                ])
        
        # Footer
        text.extend([
            ("", "  "),
            ("class:border", "╰" + "─" * 110 + "╯"),  # Increased width to 110
            ("", "\n\n"),
            ("class:help", "  Commands:\n"),
            ("class:help", "    [s] Share file/directory   [a] Add user access    [r] Remove user access\n"),
            ("class:help", "    [e] Toggle share with everyone    [↑/↓] Navigate    [q] Exit\n\n"),
            ("class:status", f"  {self.status_text if self.status_text else ''}\n")
        ])
        
        # Add status history section
        if self.status_history:
            text.append(("class:title", "\n  Recent Actions:\n"))
            for msg in self.status_history:
                text.append(("class:history", f"  • {msg}\n"))
        
        return text
    
    def _process_command(self, command):
        """Process command input.
        
        Args:
            command: Command string from the input buffer.
        """
        if not command.strip():
            self.status_text = ""
            return
            
        if self.command_mode == "share":
            self._share_resource(command)
        elif self.command_mode == "add_access":
            if not self.resources:
                self.status_text = "No resources available"
                self._add_to_status_history("No resources available")
                return
                
            resource = self.resources[self.selected_index]
            self._manage_access(resource.id, command, True)
        elif self.command_mode == "remove_access":
            if not self.resources:
                self.status_text = "No resources available"
                self._add_to_status_history("No resources available")
                return
                
            resource = self.resources[self.selected_index]
            self._manage_access(resource.id, command, False)
    
    def _share_resource(self, path):
        """Share a file or directory.
        
        Args:
            path: Path to the file or directory.
        """
        # Expand user paths like ~ and ~user
        path = os.path.expanduser(path)
        
        if not os.path.exists(path):
            self.status_text = f"Path not found: {path}"
            self._add_to_status_history(f"Path not found: {path}")
            return
            
        # Use file_share_manager directly
        resource = self.file_share_manager.share_resource(path)
        
        if resource:
            resource_type = "directory" if resource.is_directory else "file"
            self.status_text = f"Shared {resource_type}: {path}"
            self._add_to_status_history(f"Shared {resource_type}: {path}")
        else:
            self.status_text = f"Failed to share: {path}"
            self._add_to_status_history(f"Failed to share: {path}")
    
    def _manage_access(self, resource_id, username, add):
        """Manage access to a shared resource.
        
        Args:
            resource_id: ID of the resource.
            username: Username to add or remove.
            add: True to add access, False to remove.
        """
        # Use file_share_manager directly
        result = self.file_share_manager.update_resource_access(
            resource_id=resource_id,
            username=username,
            add=add
        )
        
        if result:
            action = "added to" if add else "removed from"
            self.status_text = f"Successfully {action} access list for {username}"
            self._add_to_status_history(f"Successfully {action} access list for {username}")
        else:
            self.status_text = f"Failed to update access. Check that you own the resource and the username is correct."
            self._add_to_status_history(f"Failed to update access. Check that you own the resource and the username is correct.")
    
    def _share_with_all(self, resource_id, share_all):
        """Share a resource with everyone.
        
        Args:
            resource_id: ID of the resource.
            share_all: Whether to share with everyone.
        """
        # Use file_share_manager directly
        result = self.file_share_manager.set_share_to_all(
            resource_id=resource_id,
            share_to_all=share_all
        )
        
        if result:
            status = "shared with everyone" if share_all else "no longer shared with everyone"
            self.status_text = f"Resource is now {status}"
            self._add_to_status_history(f"Resource is now {status}")
        else:
            self.status_text = "Failed to update sharing settings. Check that you own the resource."
            self._add_to_status_history("Failed to update sharing settings. Check that you own the resource.")
    
    def _configure_ftp_logging(self):
        """Configure the FTP server to be less verbose."""
        try:
            # Try to suppress FTP server logs
            
            # Set FTP server settings
            if hasattr(self.file_share_manager, 'ftp_handler'):
                # Set empty prefix and banner
                self.file_share_manager.ftp_handler.log_prefix = ""
                self.file_share_manager.ftp_handler.banner = ""
                
                # Increase the logging level
                logging.getLogger('pyftpdlib').setLevel(logging.CRITICAL)
                logging.getLogger('pyftpdlib.server').setLevel(logging.CRITICAL)
                logging.getLogger('pyftpdlib.handler').setLevel(logging.CRITICAL)
                logging.getLogger('pyftpdlib.authorizer').setLevel(logging.CRITICAL)
                logging.getLogger('pyftpdlib.filesystems').setLevel(logging.CRITICAL)
        except Exception:
            # If something goes wrong, just continue - this is not critical
            pass
    
    def show(self):
        """Show the file sharing view"""
        self.discovery.in_live_view = True
        self.command_mode = None
        self.status_text = ""
        
        # Configure the FTP server to be less verbose if possible
        self._configure_ftp_logging()
        
        # Create the main window for resource display
        self.main_window = Window(
            content=FormattedTextControl(self._get_resources_text),
            always_hide_cursor=True,
            height=D(preferred=22)
        )
        
        # Create command input window
        self.command_window = Window(
            content=BufferControl(
                buffer=self.command_buffer,
                focusable=True
            ),
            height=1,
            dont_extend_height=True,
            style="class:command"
        )
        
        # Create layout
        layout = Layout(
            HSplit([
                self.main_window,
                self.command_window
            ])
        )
        
        # Start with main window focused
        layout.focus(self.main_window)
        
        # Create application
        app = Application(
            layout=layout,
            key_bindings=self.kb,
            full_screen=True,
            mouse_support=True,
            style=self.style
        )
        
        # Setup refresh thread
        def refresh_screen():
            while self.running:
                app.invalidate()
                time.sleep(0.5)  # Refresh every 500ms

        refresh_thread = threading.Thread(target=refresh_screen)
        refresh_thread.daemon = True
        refresh_thread.start()
        
        # Clear screen and run
        clear()
        try:
            app.run()
        finally:
            self.discovery.in_live_view = False
            clear()