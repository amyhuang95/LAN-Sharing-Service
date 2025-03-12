import socket
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import clear

from .debug_view import DebugView
from .user_list_view import UserListView
from .message_view import MessageView, send_new_message

from ..core.udp_discovery import UDPPeerDiscovery
from ..core.clipboard import Clipboard


class InteractiveSession:
    def __init__(self, discovery: UDPPeerDiscovery, clipboard: Clipboard):
        self.discovery = discovery
        self.clipboard = clipboard
        self.commands = {
            'ul': self._show_user_list,
            'debug': self._show_debug_view,
            'msg': self._send_message,
            'lm': self._list_messages,
            'om': self._open_message,
            'sc': self._share_clipboard,
            'rc': self._receive_clipboard,
            'help': self.show_help,
            'clear': self.clear_screen,
            'exit': self.exit_session,
            'quit': self.exit_session
        }
        self.running = True
        self._setup_prompt()

    def _setup_prompt(self):
        """Setup the prompt session"""
        self.style = Style.from_dict({
            'username': '#00aa00 bold',
            'at': '#888888',
            'colon': '#888888',
            'pound': '#888888',
        })
        
        self.completer = WordCompleter(list(self.commands.keys()))
        
        self.session = PromptSession(
            completer=self.completer,
            style=self.style,
            complete_while_typing=True
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
            print("Usage: msg <username>")
            return

        recipient = args[0]
        peers = self.discovery.list_peers()
        if recipient not in peers:
            print(f"Error: User '{recipient}' not found or offline")
            return

        send_new_message(self.discovery, recipient)

    def _list_messages(self, *args):
        """Handle the lm command"""
        view = MessageView(self.discovery)
        view.show_message_list()

    def _open_message(self, *args):
        """Handle the om command"""
        if not args:
            print("Usage: om <conversation_id>")
            return

        conversation_id = args[0]
        messages = self.discovery.get_conversation(conversation_id)
        if not messages:
            print(f"No conversation found with ID: {conversation_id}")
            return

        # Get the other participant from the conversation
        last_message = max(messages, key=lambda m: m.timestamp)
        other_party = (last_message.recipient 
                      if last_message.sender == self.discovery.username 
                      else last_message.sender)

        # Open the conversation view
        view = MessageView(self.discovery, other_party)
        view.show_conversation(other_party, conversation_id)

    def _share_clipboard(self, *args):
        """Handle the sc command"""
        if not args:
            print("Usage: sc <username_1> <username_2> ...")
            return

        if not self.clipboard.activate:
            print("Clipboard sharing is not activated. Restart the application with --sc flag for activation.")
            return

        recipients = args
        active_peers = self.discovery.list_peers()

        # Check at least one requested recipient is online
        at_least_one_online = False
        for recipient in recipients:
            if recipient in active_peers:
                at_least_one_online = True
            else:
                print(f"User '{recipient}' not found or offline")
        if not at_least_one_online:
            print("None of the provided peers is online")
            return

        self.clipboard.update_send_to_peers(recipients)
    
    def _receive_clipboard(self, *args):
        """Handle the rc command"""
        if not args:
            print("Usage: rc <username_1> <username_2> ...")
            return

        if not self.clipboard.activate:
            print("Clipboard sharing is not activated. Restart the application with --sc flag for activation.")
            return
        
        senders = args
        active_peers = self.discovery.list_peers()

        # Check at least one requested sender is online
        at_least_one_online = False
        for sender in senders:
            if sender in active_peers:
                at_least_one_online = True
            else:
                print(f"User '{sender}' not found or offline")
        if not at_least_one_online:
            print("None of the provided peers is online")
            return

        self.clipboard.update_receive_from_peers(senders)

    def show_help(self, *args):
        """Show help message"""
        print("\nAvailable commands:")
        print("  ul     - List online users")
        print("  msg    - Send a message (msg <username>)")
        print("  lm     - List all messages")
        print("  om     - Open a message conversation (om <conversation_id>)")
        print("  sc     - Share clipboard (sc <username_1> <username_2> ...)")
        print("  rc     - Receive clipboard from peers (rc <username_1> <username_2> ...)")
        print("  debug  - Toggle debug mode")
        print("  clear  - Clear screen")
        print("  help   - Show this help message")
        print("  exit   - Exit the session")

    def clear_screen(self, *args):
        """Clear the terminal screen"""
        clear()

    def exit_session(self, *args):
        """Exit the session"""
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
            print(f"Unknown command: {command}")
            print("Type 'help' for available commands")
            return False

    def start(self):
        """Start the interactive session"""
        clear()
        print(f"\nWelcome to LAN Share, {self.discovery.username}!")
        print("Type 'help' for available commands")
        
        while self.running:
            try:
                command = self.session.prompt(self.get_prompt_text())
                self.handle_command(command)
            except KeyboardInterrupt:
                print("\nUse 'exit' to quit")
            except EOFError:
                break
            except Exception as e:
                print(f"Error: {e}")

        # Cleanup
        self.discovery.cleanup()