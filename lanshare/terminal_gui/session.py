import socket
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.shortcuts import clear
import os
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.theme import Theme
from rich.markdown import Markdown

from .debug_view import DebugView
from .user_list_view import UserListView
from .message_view import MessageView, send_new_message
from .autocomplete import CommandCompleter

from ..core.udp_discovery import UDPPeerDiscovery
from ..core.clipboard import Clipboard

from .file_share_view import FileShareView
from ..core.file_share import SharedResource


class InteractiveSession:
    def __init__(self, discovery: UDPPeerDiscovery, clipboard: Clipboard):
        self.discovery = discovery
        self.clipboard = clipboard
        # Direct access to the file share manager
        self.file_share_manager = discovery.file_share_manager
        
        # Initialize Rich console with custom theme
        self.theme = Theme({
            "info": "cyan",
            "warning": "yellow",
            "danger": "bold red",
            "success": "bold green",
            "command": "bold blue",
            "highlight": "magenta",
            "username": "green",
            "ip": "blue",
            "resource_id": "magenta",
        })
        self.console = Console(theme=self.theme)
        
        self.commands = {
            'ul': self._show_user_list,
            'debug': self._show_debug_view,
            'msg': self._send_message,
            'lm': self._list_messages,
            'om': self._open_message,
            'clipboard': self._clipboard_activation,
            'sc': self._share_clipboard,
            'share': self._share_file,
            'files': self._list_files,
            'access': self._manage_access,
            'all': self._share_with_all,
            'registry': self._manage_registry,
            'help': self.show_help,
            'clear': self.clear_screen,
            'exit': self.exit_session,
            'quit': self.exit_session
        }
        self.running = True
        self._setup_prompt()

    def _setup_prompt(self):
        """Setup the prompt session with advanced completion"""
        self.style = Style.from_dict({
            'username': '#00aa00 bold',
            'at': '#888888',
            'colon': '#888888',
            'pound': '#888888',
            # Add styles for completion menu
            'completion-menu': 'bg:#333333',
            'completion-menu.completion': 'bg:#333333 #ffffff',
            'completion-menu.completion.current': 'bg:#00aaaa #000000',
            'completion-menu.meta.completion': 'bg:#333333 #999999',
            'completion-menu.meta.completion.current': 'bg:#00aaaa #000000',
        })
        
        # Use the advanced command completer instead of simple word completer
        self.completer = CommandCompleter(self.discovery, self.commands)
        
        self.session = PromptSession(
            completer=self.completer,
            style=self.style,
            complete_while_typing=True,
            complete_in_thread=True,  # Perform completion in a separate thread for better responsiveness
        )

    def _show_user_list(self, *args):
        """Show the user list view"""
        view = UserListView(self.discovery)
        view.show()

    def _show_debug_view(self, *args):
        """Show the debug view"""
        view = DebugView(self.discovery)
        view.show()

    def _send_message(self, *args):
        """Handle the msg command"""
        if not args:
            self.console.print(Panel("[warning]Usage: msg <username>", 
                                     title="Command Help", 
                                     border_style="yellow"))
            return

        recipient = args[0]
        peers = self.discovery.list_peers()
        if recipient not in peers:
            self.console.print(f"[danger]Error:[/] User '[highlight]{recipient}[/]' not found or offline")
            return

        send_new_message(self.discovery, recipient)

    def _list_messages(self, *args):
        """Handle the lm command"""
        view = MessageView(self.discovery)
        view.show_message_list()

    def _open_message(self, *args):
        """Handle the om command"""
        if not args:
            self.console.print(Panel("[warning]Usage: om <conversation_id>", 
                                     title="Command Help", 
                                     border_style="yellow"))
            return

        conversation_id = args[0]
        messages = self.discovery.get_conversation(conversation_id)
        if not messages:
            self.console.print(f"[warning]No conversation found with ID: [highlight]{conversation_id}")
            return

        # Get the other participant from the conversation
        last_message = max(messages, key=lambda m: m.timestamp)
        other_party = (last_message.recipient 
                      if last_message.sender == self.discovery.username 
                      else last_message.sender)

        # Open the conversation view
        view = MessageView(self.discovery, other_party)
        view.show_conversation(other_party, conversation_id)
    
    def _share_file(self, *args):
        """Handle the share command to share a file or directory."""
        if not args:
            self.console.print(Panel("[warning]Usage: share <file_path> or <directory_path>", 
                                     title="Command Help", 
                                     border_style="yellow"))
            return
            
        path = " ".join(args)  # Handle paths with spaces
        path = os.path.expanduser(path)  # Expand user paths like ~ and ~user
        
        if not os.path.exists(path):
            self.console.print(f"[danger]Error:[/] Path not found: [highlight]{path}")
            return
            
        # Direct call to file_share_manager instead of through discovery
        resource = self.file_share_manager.share_resource(path)
        
        if resource:
            resource_type = "directory" if resource.is_directory else "file"
            
            # Create a nice panel for success message
            info_text = f"""Successfully shared {resource_type}: [highlight]{path}[/]
Resource ID: [resource_id]{resource.id}[/]
            
By default, only you can access this resource.
Use [command]access <resource_id> <username> add[/] to give access to others.
Or use [command]all <resource_id> on[/] to share with everyone."""
            
            self.console.print(Panel(info_text, 
                                     title="[success]✓ Share Successful", 
                                     border_style="green"))
        else:
            self.console.print(f"[danger]Error:[/] Failed to share [highlight]{path}")
    
    def _list_files(self, *args):
        """Handle the files command to list shared files."""
        view = FileShareView(self.discovery)
        view.show()
    
    def _manage_access(self, *args):
        """Handle the access command to manage access to shared resources."""
        if len(args) < 3:
            self.console.print(Panel("[warning]Usage: access <resource_id> <username> add|rm", 
                                     title="Command Help", 
                                     border_style="yellow"))
            return
            
        resource_id = args[0]
        username = args[1]
        action = args[2].lower()
        
        if action not in ["add", "rm"]:
            self.console.print("[warning]Action must be 'add' or 'rm'")
            return
            
        # Direct call to file_share_manager instead of through discovery
        result = self.file_share_manager.update_resource_access(
            resource_id=resource_id,
            username=username,
            add=(action == "add")
        )
        
        if result:
            action_text = "added to" if action == "add" else "removed from"
            self.console.print(f"[success]✓ Successfully {action_text} access list for [username]{username}[/]")
        else:
            self.console.print(Panel("[danger]Failed to update access. Check that you own the resource and the resource ID is correct.", 
                                     title="Access Error", 
                                     border_style="red"))
    
    def _share_with_all(self, *args):
        """Handle the all command to share with everyone."""
        if len(args) < 2:
            self.console.print(Panel("[warning]Usage: all <resource_id> on|off", 
                                     title="Command Help", 
                                     border_style="yellow"))
            return
            
        resource_id = args[0]
        share_option = args[1].lower()
        
        if share_option not in ["on", "off"]:
            self.console.print("[warning]Option must be 'on' or 'off'")
            return
            
        share_all = share_option == "on"
        
        # Direct call to file_share_manager instead of through discovery
        result = self.file_share_manager.set_share_to_all(
            resource_id=resource_id,
            share_to_all=share_all
        )
        
        if result:
            status = "shared with everyone" if share_all else "no longer shared with everyone"
            self.console.print(f"[success]✓ Resource is now {status}")
        else:
            self.console.print(Panel("[danger]Failed to update sharing settings. Check that you own the resource and the resource ID is correct.", 
                                     title="Sharing Error", 
                                     border_style="red"))
            
    def _clipboard_activation(self, *args):
        """Handle the clipboard on/off command"""
        if not args or args[0].lower() not in ('on', 'off'):
            self.console.print(Panel("[warning]Usage: clipboard on|off", 
                                     title="Command Help", 
                                     border_style="yellow"))
            return
        
        option: str = args[0]
        if option.lower() == 'on':
            if self.clipboard.running:
                self.console.print(f"[warning]Clipboard sharing already enabled.")
            else:
                self.clipboard.start()
                self.console.print(f"[success]✓ Clipboard sharing activated. Edit peers to share clipboard using sc command")
        elif option.lower() == 'off':
            if self.clipboard.running:
                self.clipboard.stop()
                self.console.print(f"[success]✓ Clipboard sharing deactivated.")
            else:
                self.console.print(f"[warning]Clipboard sharing is not enabled")
        

    def _share_clipboard(self, *args):
        """Handle the sc command"""
        # Validat command
        if len(args) < 3:
            self.console.print(Panel("[warning]Usage: sc to|from <username> add|rm", 
                                     title="Command Help", 
                                     border_style="yellow"))
            return

        if not self.clipboard.running:
            self.console.print(Panel("[warning]Clipboard sharing is not activated.\nActivate clipboard sharing with 'clipboard on' command", 
                                     title="Feature Not Enabled", 
                                     border_style="yellow"))
            return

        direction = args[0].lower()
        peer = args[1]
        option = args[2]
        active_peers = self.discovery.list_peers()

        # Define actions for sending and receiving
        actions = {
            "to": {"add": self.clipboard.add_sending_peer, 
                   "rm": self.clipboard.remove_sending_peer},
            "from": {"add": self.clipboard.add_receiving_peer, 
                     "rm": self.clipboard.remove_receiving_peer},
        }

        # Execute the corresponding function if valid
        if direction in actions and option in actions[direction]:
            # Check peer is online
            if peer not in active_peers:
                self.console.print(f"[warning]User not found or offline: [highlight]{peer}")
                return

            actions[direction][option](peer)
            self.console.print(f"[success]✓ Updated sharing {direction} [username]{peer}")
        else:
            self.console.print(Panel("[warning]Usage: sc to|from <username> add|rm", 
                                     title="Command Help", 
                                     border_style="yellow"))
             
    def _manage_registry(self, *args):
        """Handle the registry command for alternative peer discovery."""
        if not args:
            # Show current registry status
            if self.discovery.is_using_registry():
                server_url = self.discovery.get_registry_server_url()
                self.console.print(Panel(
                    f"[success]✓ Currently registered with registry server:[/]\n[highlight]{server_url}[/]\n\n"
                    f"To unregister, use: [command]registry disconnect[/]",
                    title="Registry Status",
                    border_style="green"
                ))
            else:
                self.console.print(Panel(
                    "[info]Not using registry server. Currently in UDP broadcast discovery mode.[/]\n\n"
                    "To connect to a registry server, use: [command]registry connect <server_url>[/]\n"
                    "Example: [command]registry connect 192.168.1.5:5000[/]",
                    title="Registry Status",
                    border_style="blue"
                ))
            return

        # Process commands
        command = args[0].lower()

        if command == "connect":
            if len(args) < 2:
                self.console.print(Panel(
                    "[warning]Please specify a server URL.[/]\n"
                    "Example: [command]registry connect 192.168.1.5:5000[/]",
                    title="Command Help",
                    border_style="yellow"
                ))
                return

            server_url = args[1]
            self.console.print(f"[info]Connecting to registry server at {server_url}...[/]")
            
            if self.discovery.register_with_server(server_url):
                self.console.print(f"[success]✓ Successfully registered with registry server[/]")
                self.console.print("[info]Now discovering peers via both UDP broadcast and registry server[/]")
            else:
                self.console.print(f"[danger]Failed to connect to registry server at {server_url}[/]")
                self.console.print("[info]Make sure the registry server is running and the URL is correct[/]")
                self.console.print("[info]Continuing with UDP broadcast discovery only[/]")
                
        elif command == "disconnect":
            if not self.discovery.is_using_registry():
                self.console.print("[warning]Not currently connected to any registry server[/]")
                return
                
            server_url = self.discovery.get_registry_server_url()
            self.console.print(f"[info]Disconnecting from registry server at {server_url}...[/]")
            
            if self.discovery.unregister_from_server():
                self.console.print(f"[success]✓ Successfully disconnected from registry server[/]")
                self.console.print("[info]Now using UDP broadcast discovery only[/]")
            else:
                self.console.print(f"[danger]Error disconnecting from registry server[/]")
                
        elif command == "status":
            if self.discovery.is_using_registry():
                server_url = self.discovery.get_registry_server_url()
                self.console.print(f"[success]✓ Currently registered with registry server:[/] [highlight]{server_url}[/]")
            else:
                self.console.print("[info]Not using registry server. Currently in UDP broadcast discovery mode.[/]")
                
        else:
            self.console.print(Panel(
                "[warning]Unknown registry command.[/]\n\n"
                "Available commands:\n"
                "  [command]registry[/] - Show current status\n"
                "  [command]registry connect <server_url>[/] - Connect to a registry server\n"
                "  [command]registry disconnect[/] - Disconnect from registry server\n"
                "  [command]registry status[/] - Show current registry status",
                title="Command Help",
                border_style="yellow"
            ))

    def show_help(self, *args):
        """Show help message"""
        help_table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
        help_table.add_column("Command", style="command")
        help_table.add_column("Description")
        help_table.add_column("Usage Example", style="dim")
        
        # Add commands to the table
        help_table.add_row("ul", "List online users", "ul")
        help_table.add_row("msg", "Send a message to a user", "msg username")
        help_table.add_row("lm", "List all message conversations", "lm")
        help_table.add_row("om", "Open a specific conversation", "om conv_id")
        help_table.add_row("share", "Share a file or directory", "share ~/Documents/file.txt")
        help_table.add_row("files", "List and manage shared files", "files")
        help_table.add_row("access", "Manage access to shared resources", "access resource_id username add|rm")
        help_table.add_row("all", "Share resource with everyone", "all resource_id on|off")
        help_table.add_row("clipboard", "Activate/deactivate clipboard sharing", "clipboard on|off")
        help_table.add_row("sc", "Add peers to share clips to or receive clips from", "sc to|from username add|rm")
        help_table.add_row("registry", "Manage registry connection for restricted networks", 
                           "registry connect 192.168.1.5:5000")
        help_table.add_row("debug", "Toggle debug mode", "debug")
        help_table.add_row("clear", "Clear screen", "clear")
        help_table.add_row("help", "Show this help message", "help")
        help_table.add_row("exit/quit", "Exit the application", "exit")
        
        # Add note about autocompletion
        autocomplete_note = Panel(
            "[green]TIP:[/] Press [bold]Tab[/] to autocomplete commands, usernames, and file paths.",
            border_style="green",
            padding=1
        )
        
        self.console.print(Panel.fit(help_table, title="[bold]LAN Share Command Reference", 
                                    border_style="cyan"))
        self.console.print(autocomplete_note)

    def clear_screen(self, *args):
        """Clear the terminal screen"""
        clear()

    def exit_session(self, *args):
        """Exit the session"""
        # Display a goodbye message
        farewell = Text()
        farewell.append("\nThank you for using ", style="cyan")
        farewell.append("LAN Share", style="bold green")
        farewell.append("!\n", style="cyan")
        farewell.append("Your shared resources have been cleaned up.\n", style="green")
        farewell.append("Have a great day!", style="cyan bold")
        
        farewell_panel = Panel(
            farewell,
            title="[bold]Goodbye",
            border_style="cyan",
            box=box.ROUNDED
        )
        
        self.console.print(farewell_panel)
        self.running = False
        return True

    def get_prompt_text(self):
        """Get the formatted prompt text"""
        # Get local IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = '127.0.0.1'
        finally:
            s.close()

        return HTML(
            f'<username>{self.discovery.username}</username>'
            f'<at>@</at>'
            f'<colon>LAN</colon>'
            f'<colon>({local_ip})</colon>'
            f'<pound># </pound>'
        )

    def handle_command(self, command_line):
        """Handle a command input"""
        if not command_line:
            return False
            
        parts = command_line.strip().split()
        command = parts[0].lower()
        args = parts[1:]

        if command in self.commands:
            return self.commands[command](*args)
        else:
            self.console.print(f"[danger]Unknown command:[/] [highlight]{command}")
            self.console.print("Type [command]help[/] for available commands")
            return False

    def start(self):
        """Start the interactive session"""
        clear()
        
        # Create fancy welcome panel
        welcome_text = Text()
        welcome_text.append("Welcome to ", style="cyan")
        welcome_text.append("LAN Share", style="bold green")
        welcome_text.append(f", {self.discovery.username}!\n\n", style="cyan")
        welcome_text.append("• Share files and directories on your local network\n", style="green")
        welcome_text.append("• Chat with other users on the same network\n", style="green")
        welcome_text.append("• Share clipboard contents securely\n\n", style="green")
        welcome_text.append("Type ", style="cyan")
        welcome_text.append("help", style="bold blue")
        welcome_text.append(" for available commands\n", style="cyan")
        welcome_text.append("Press ", style="cyan")
        welcome_text.append("Tab", style="bold blue")
        welcome_text.append(" to autocomplete commands, usernames, and file paths", style="cyan")
        
        welcome_panel = Panel(
            welcome_text,
            title="[bold]LAN Share Service",
            subtitle=f"Connected as [bold green]{self.discovery.username}[/]",
            border_style="cyan",
            box=box.DOUBLE
        )
        
        self.console.print(welcome_panel)
        
        while self.running:
            try:
                command = self.session.prompt(self.get_prompt_text())
                self.handle_command(command)
            except KeyboardInterrupt:
                self.console.print("\n[warning]Use '[command]exit[/]' to quit")
            except EOFError:
                # Show goodbye message on Ctrl+D
                self.exit_session()
                break
            except Exception as e:
                self.console.print(f"[danger]Error:[/] {e}")

        # Cleanup
        self.discovery.cleanup()