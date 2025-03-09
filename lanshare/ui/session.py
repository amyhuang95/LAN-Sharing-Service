import socket
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import clear

from .debug_view import DebugView
from .user_list_view import UserListView
from .message_view import MessageView, send_new_message

from lanshare.core.ft_client import FileTransferClient

class InteractiveSession:
    def __init__(self, discovery, ft_server):
        self.discovery = discovery
        self.ft_server = ft_server
        
        # Dictionary to track pending file requests from the server
        self.pending_file_requests = {}  # request_id -> (file_name, addr)
        
        # Set the file server's callback to our on_file_request method
        self.ft_server.notify_ui_callback = self.on_file_request
        
        self.commands = {
            'ul': self._show_user_list,
            'debug': self._show_debug_view,
            'msg': self._send_message,
            'lm': self._list_messages,
            'om': self._open_message,
            'ft': self._send_file,
            'acc': self._accept_file_request,
            'rej': self._reject_file_request,
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


    def on_file_request(self, request_id, file_name, addr):
        """
        Callback invoked by the file transfer server when a new file request arrives.
        """
        self.pending_file_requests[request_id] = (file_name, addr)
        print(f"\n[New File Request] ID={request_id}, File='{file_name}', From={addr}")
        print("Type 'acc <request_id>' to accept or 'rej <request_id>' to reject.")

    def _accept_file_request(self, *args):
        """Accept the file transfer"""

        if not args:
            print("Usage: acc <request_id>")
            return
        request_id = args[0]
        if request_id not in self.pending_file_requests:
            print(f"Unknown request_id: {request_id}")
            return

        self.ft_server.process_file_request(request_id, accept=True)
        self.pending_file_requests.pop(request_id, None)
        print(f"Accepted file request {request_id}.")

    def _reject_file_request(self, *args):
        """Reject the file transfer"""

        if not args:
            print("Usage: rej <request_id>")
            return
        request_id = args[0]
        if request_id not in self.pending_file_requests:
            print(f"Unknown request_id: {request_id}")
            return

        self.ft_server.process_file_request(request_id, accept=False)
        self.pending_file_requests.pop(request_id, None)
        print(f"Rejected file request {request_id}.")

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

    def _send_file(self, *args):
        if len(args) < 2:
            print("Usage: ft <username> <file_path>")
            return
        
        recipient = args[0]
        file_path = args[1]
        peers = self.discovery.list_peers()
        
        if recipient not in peers:
            print(f"Error: User '{recipient}' not found or offline.")
            return
        
        peer = peers[recipient]
        print(f"Attempting to send file '{file_path}' to {recipient} at {peer.address}...")
        
        client = FileTransferClient(server_ip=peer.address, port=60000)
        client.send_file(file_path)

    def show_help(self, *args):
        print("\nAvailable commands:")
        print("  ul             - List online users")
        print("  msg <username> - Send a message")
        print("  lm             - List all messages")
        print("  om <conv_id>   - Open a conversation")
        print("  ft <username> <file_path> - Send a file")
        print("  acc <request_id>  - Accept an incoming file request")
        print("  rej <request_id>  - Reject an incoming file request")
        print("  debug          - Toggle debug mode")
        print("  clear          - Clear screen")
        print("  help           - Show this help message")
        print("  exit           - Exit the session")

    def clear_screen(self, *args):
        """Clear the terminal screen"""
        clear()

    def exit_session(self, *args):
        """Exit the session"""
        self.running = False
        self.discovery.cleanup()
        self.ft_server.stop()
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
        self.ft_server.stop()
