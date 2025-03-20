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
        self.command_mode = "main"  # Start in main mode
        
        # Setup key bindings and styles
        self._setup_keybindings()
        self._setup_styles()
    
    def _setup_keybindings(self):
        """Setup keyboard shortcuts"""
        self.kb = KeyBindings()
        
        @self.kb.add('up')
        def _(event):
            """Move selection up"""
            if self.resources and self.command_mode == "main":
                self.selected_index = max(0, self.selected_index - 1)
                event.app.invalidate()
        
        @self.kb.add('down')
        def _(event):
            """Move selection down"""
            if self.resources and self.command_mode == "main":
                self.selected_index = min(len(self.resources) - 1, self.selected_index + 1)
                event.app.invalidate()
        
        @self.kb.add('enter')
        def _(event):
            """Process command input"""
            command = self.command_buffer.text.strip().lower()
            
            if self.command_mode == "main":
                # Process commands in main mode
                if command == "q" or command == "quit" or command == "exit":
                    self.running = False
                    event.app.exit()
                elif command == "s" or command == "share":
                    self.status_text = "Share mode: Enter the path to share (press Enter when done)"
                    self.command_mode = "share"
                    self.command_buffer.text = ""  # Clear input
                    event.app.invalidate()
                elif command == "a" or command == "add":
                    if not self.resources:
                        self.status_text = "No resources available to modify access"
                        self._add_to_status_history("No resources available to modify access")
                    else:
                        resource = self.resources[self.selected_index]
                        if resource.owner != self.discovery.username:
                            self.status_text = "You can only modify access for resources you own"
                            self._add_to_status_history("You can only modify access for resources you own")
                        else:
                            self.status_text = f"Add access: Enter username to grant access to resource {resource.id[:8]}"
                            self.command_mode = "add_access"
                            self.command_buffer.text = ""  # Clear input
                    event.app.invalidate()
                elif command == "r" or command == "remove":
                    if not self.resources:
                        self.status_text = "No resources available to modify access"
                        self._add_to_status_history("No resources available to modify access")
                    else:
                        resource = self.resources[self.selected_index]
                        if resource.owner != self.discovery.username:
                            self.status_text = "You can only modify access for resources you own"
                            self._add_to_status_history("You can only modify access for resources you own")
                        else:
                            self.status_text = f"Remove access: Enter username to remove access from resource {resource.id[:8]}"
                            self.command_mode = "remove_access"
                            self.command_buffer.text = ""  # Clear input
                    event.app.invalidate()
                elif command == "e" or command == "everyone":
                    if not self.resources:
                        self.status_text = "No resources available to modify access"
                        self._add_to_status_history("No resources available to modify access")
                    else:
                        resource = self.resources[self.selected_index]
                        if resource.owner != self.discovery.username:
                            self.status_text = "You can only modify access for resources you own"
                            self._add_to_status_history("You can only modify access for resources you own")
                        else:
                            self._share_with_all(resource.id, not resource.shared_to_all)
                    self.command_buffer.text = ""  # Clear input
                    event.app.invalidate()
                elif command == "help":
                    self.status_text = "Available commands: [s]hare, [a]dd, [r]emove, [e]veryone, [q]uit, help"
                    self._add_to_status_history("Command help displayed")
                    self.command_buffer.text = ""  # Clear input
                    event.app.invalidate()
                else:
                    # If the command is not recognized in main mode, show a message
                    if command:
                        self.status_text = f"Unknown command: {command}. Type 'help' for available commands."
                        self.command_buffer.text = ""  # Clear input
                        event.app.invalidate()
            else:
                # Process commands in other modes
                input_text = self.command_buffer.text  # Save the input text
                self.command_buffer.text = ""  # Clear input immediately
                self._process_command(input_text)  # Use the saved text
                self.command_mode = "main"
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
        """Generate the formatted resources list text with proper alignment and dynamic line breaks."""
        # Use file_share_manager directly
        self.resources = self.file_share_manager.list_shared_resources()
        
        # Define column widths
        col_widths = {
            'id': 20,
            'type': 10,
            'name': 15,
            'owner': 12,
            'access': 12,
            'shared': 16,
            'modified': 20
        }
        
        # Calculate total width (adding 2 for padding each column + border chars)
        content_width = sum(col_widths.values()) + len(col_widths.values())*2
        border_width = content_width + 2  # +2 for left and right border chars
        
        text = [
            ("", "\n"),
            ("class:title", "  Shared Resources "),
            ("", "\n"),
            ("", "  "),
            ("class:border", "╭" + "─" * border_width + "╮"),
            ("", "\n")
        ]
        
        if not self.resources:
            text.extend([
                ("", "  "),
                ("class:border", " "),
                ("fg:gray", " No resources shared yet"),
                ("", " " * (border_width - len("No resources shared yet") - 1)),
                ("class:border", " "),
                ("", "\n")
            ])
        else:
            # Header
            header_text = (
                f" {'ID':<{col_widths['id']}} {'Type':<{col_widths['type']}} {'Name':<{col_widths['name']}} "
                f"{'Owner':<{col_widths['owner']}} {'Access':<{col_widths['access']}} {'Shared On':<{col_widths['shared']}} "
                f"{'Last Modified':<{col_widths['modified']}} "
            )
            text.extend([
                ("", "  "),
                ("class:border", " "),
                ("class:label", header_text),
                ("class:border", " "),
                ("", "\n"),
                ("", "  "),
                ("class:border", "├" + "─" * border_width + "┤"),
                ("", "\n")
            ])
            
            # Resource entries
            for idx, resource in enumerate(self.resources):
                resource_type = "Directory" if resource.is_directory else "File"
                owner = "You" if resource.owner == self.discovery.username else resource.owner
                
                # Handle access field
                access = "Everyone" if resource.shared_to_all else ", ".join(resource.allowed_users) or "Only owner"
                
                shared_date = resource.timestamp.strftime("%Y-%m-%d %H:%M")
                
                # Format modification time
                try:
                    mod_time = datetime.fromtimestamp(resource.modified_time).strftime("%Y-%m-%d %H:%M")
                except:
                    mod_time = "Unknown"
                
                name = os.path.basename(resource.path)
                
                # Apply selection highlight if this is the selected item
                style_prefix = "class:selected " if idx == self.selected_index else ""
                
                # Break text into multiple lines for all fields that might need it
                id_lines = self._break_text(resource.id, max_length=col_widths['id'])
                name_lines = self._break_text(name, max_length=col_widths['name'])
                owner_lines = self._break_text(owner, max_length=col_widths['owner'])
                access_lines = self._break_text(access, max_length=col_widths['access'])
                
                # Get the maximum number of lines needed for this entry
                max_lines = max(
                    len(id_lines),
                    len(name_lines),
                    len(owner_lines),
                    len(access_lines),
                    1  # Always at least one line
                )
                
                # Format the resource entry with proper line breaks for all fields
                for i in range(max_lines):
                    id_part = id_lines[i] if i < len(id_lines) else " " * col_widths['id']
                    name_part = name_lines[i] if i < len(name_lines) else " " * col_widths['name'] 
                    owner_part = owner_lines[i] if i < len(owner_lines) else " " * col_widths['owner']
                    access_part = access_lines[i] if i < len(access_lines) else " " * col_widths['access']
                    
                    # Only show type and dates on the first line
                    type_part = resource_type if i == 0 else " " * col_widths['type']
                    shared_part = shared_date if i == 0 else " " * col_widths['shared']
                    mod_part = mod_time if i == 0 else " " * col_widths['modified']
                    
                    row_content = (
                        f" {id_part:<{col_widths['id']}} {type_part:<{col_widths['type']}} {name_part:<{col_widths['name']}} "
                        f"{owner_part:<{col_widths['owner']}} {access_part:<{col_widths['access']}} {shared_part:<{col_widths['shared']}} "
                        f"{mod_part:<{col_widths['modified']}} "
                    )
                    
                    resource_entry = [
                        ("", "  "),
                        ("class:border", " "),
                        (f"{style_prefix}class:resource_id", f" {id_part:<{col_widths['id']}} "),
                        (f"{style_prefix}class:resource_type", f"{type_part:<{col_widths['type']}} "),
                        (f"{style_prefix}", f"{name_part:<{col_widths['name']}} "),
                        (f"{style_prefix}class:{'owner' if 'You' in owner else 'peer'}", f"{owner_part:<{col_widths['owner']}} "),
                        (f"{style_prefix}class:access", f"{access_part:<{col_widths['access']}} "),
                        (f"{style_prefix}class:date", f"{shared_part:<{col_widths['shared']}} "),
                        (f"{style_prefix}class:date", f"{mod_part:<{col_widths['modified']}} "),  # Added space at the end for consistent padding
                        ("class:border", " "),
                        ("", "\n")
                    ]
                    
                    # Add the resource entry to the text
                    text.extend(resource_entry)
        
        # Footer
        text.extend([
            ("", "  "),
            ("class:border", "╰" + "─" * border_width + "╯"),
            ("", "\n\n"),
            ("class:help", "  Commands (type and press Enter):\n"),
            ("class:help", "    [s] or [share] Share file/directory   [a] or [add] Add user access    [r] or [remove] Remove user access\n"),
            ("class:help", "    [e] or [everyone] Toggle share with everyone    [↑/↓] Navigate    [q] or [quit] Exit    [help] Show commands\n\n"),
            ("class:status", f"  {self.status_text if self.status_text else ''}\n"),
            ("class:help", f"  Current mode: {self.command_mode.upper() if self.command_mode != 'main' else 'COMMAND'}\n")
        ])
        
        # Display command prompt based on mode
        if self.command_mode == "main":
            text.append(("class:help", "  Enter command: "))
        elif self.command_mode == "share":
            text.append(("class:help", "  Enter path to share: "))
        elif self.command_mode == "add_access":
            text.append(("class:help", "  Enter username to add: "))
        elif self.command_mode == "remove_access":
            text.append(("class:help", "  Enter username to remove: "))
        
        # Add status history section
        if self.status_history:
            text.append(("class:title", "\n  Recent Actions:\n"))
            for msg in self.status_history:
                text.append(("class:history", f"  • {msg}\n"))
        
        return text

    def _break_text(self, text, max_length):
        """Break text into multiple lines if it exceeds the max_length."""
        lines = []
        while len(text) > max_length:
            lines.append(text[:max_length])
            text = text[max_length:]
        lines.append(text)
        return lines

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
        self.command_mode = "main"
        self.status_text = "Type a command and press Enter. Type 'help' for available commands."
        self._add_to_status_history("File sharing view started")
        
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
        
        # Start with command window focused
        layout.focus(self.command_window)
        
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