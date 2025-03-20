from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.box import ROUNDED, HEAVY, DOUBLE
from rich.align import Align
from rich.prompt import Prompt
from rich.console import Group
from rich.table import Table
from rich.live import Live
from rich.style import Style
from rich.markdown import Markdown
from datetime import datetime
from typing import List, Optional, Dict
import threading
import time
import os

from ..core.types import Message

class MessageView:
    def __init__(self, discovery, recipient=None):
        self.discovery = discovery
        self.recipient = recipient
        self.running = True
        self.messages: List[Message] = []
        self.last_check = datetime.now()
        self.last_message_count = 0
        self.current_conversation_id = None
        
        # Rich console for output
        self.console = Console()
        
        # Message styles
        self.style_config = {
            'user_message': Style(color="green", bold=True),
            'peer_message': Style(color="blue", bold=True),
            'timestamp': Style(color="grey62"),
            'system': Style(color="yellow", italic=True),
            'header': Style(color="white", bold=True),
            'divider': Style(color="grey50")
        }

    def _format_message(self, msg: Message) -> Panel:
        """Format a single message as a Rich Panel"""
        # Format timestamp
        time_str = msg.timestamp.strftime("%H:%M:%S")
        
        # Determine if message is from current user or peer
        is_self = msg.sender == self.discovery.username
        
        # Create header with sender info and timestamp
        header = Text()
        header.append(
            f"{msg.sender}", 
            style=self.style_config['user_message'] if is_self else self.style_config['peer_message']
        )
        header.append(f" • {time_str}", style=self.style_config['timestamp'])
        
        # Create message content - could support markdown here
        content = Text(msg.content)
        
        # Combine into a group
        message_group = Group(header, Text(), content)
        
        # Create panel with appropriate styling
        border_style = "green" if is_self else "blue"
        return Panel(
            message_group,
            box=ROUNDED,
            border_style=border_style,
            title="You" if is_self else msg.sender,
            title_align="left",
            width=None
        )

    def _format_conversation_display(self) -> Layout:
        """Create a full conversation display layout"""
        # Create main layout
        layout = Layout()
        
        # Split into header, messages, and input areas
        layout.split(
            Layout(name="header", size=3),
            Layout(name="messages"),
            Layout(name="input", size=3)
        )
        
        # Create header
        title = f"Conversation with {self.recipient}" if self.recipient else "Conversation List"
        header_text = Text(title, style="bold white")
        layout["header"].update(
            Panel(
                Align.center(header_text),
                box=HEAVY,
                style="blue",
                title="P2P Messenger",
                title_align="center"
            )
        )
        
        # Create messages area
        message_panels = []
        for msg in sorted(self.messages, key=lambda m: m.timestamp):
            message_panels.append(self._format_message(msg))
        
        # Add a system message if no messages yet
        if not message_panels:
            message_panels.append(
                Panel(
                    "No messages yet. Type below to start the conversation.",
                    box=ROUNDED,
                    style="yellow",
                    border_style="yellow"
                )
            )
            
        # Update messages area
        layout["messages"].update(Group(*message_panels))
        
        # Create input area
        input_label = "Type your message (Ctrl+C to exit): "
        layout["input"].update(
            Panel(
                Text(input_label, style="bold green"),
                box=HEAVY,
                style="green",
                title="Message Input",
                title_align="left"
            )
        )
        
        return layout

    def format_conversation_list(self) -> Panel:
        """Format the list of conversations for display"""
        # Group messages by conversation
        conversations: Dict[str, List[Message]] = {}
        for msg in self.discovery.list_messages():
            conv_id = msg.conversation_id
            if conv_id not in conversations:
                conversations[conv_id] = []
            conversations[conv_id].append(msg)

        # Create a table for conversations
        table = Table(
            box=ROUNDED,
            expand=True,
            show_header=True,
            header_style="bold white on blue"
        )
        
        table.add_column("ID", style="cyan", width=6)
        table.add_column("With", style="blue bold")
        table.add_column("Last Message", style="white")
        table.add_column("Time", style=self.style_config['timestamp'], width=10)

        # Add rows for each conversation
        for conv_id, msgs in conversations.items():
            # Sort messages by timestamp
            msgs.sort(key=lambda m: m.timestamp)
            last_msg = msgs[-1]
            
            # Get the other participant
            other_party = last_msg.recipient if last_msg.sender == self.discovery.username else last_msg.sender
            
            # Add row
            table.add_row(
                conv_id[:5],
                other_party,
                last_msg.content[:50] + ('...' if len(last_msg.content) > 50 else ''),
                last_msg.timestamp.strftime('%H:%M:%S')
            )
            
        # Return the table in a panel
        return Panel(
            table,
            box=DOUBLE,
            title="Conversations",
            border_style="blue",
            padding=(1, 1)
        )

    def _send_message(self, content):
        """Send a message to the current recipient"""
        if not content.strip():
            return

        if self.recipient:
            msg = self.discovery.send_message(
                recipient=self.recipient,
                title="Direct Message",
                content=content,
                conversation_id=self.current_conversation_id
            )
            if msg:
                self.messages.append(msg)

    def _check_new_messages(self, live):
        """Check for new messages and update display"""
        while self.running:
            if self.recipient and self.current_conversation_id:
                # Get all messages for this conversation
                new_messages = self.discovery.get_conversation(self.current_conversation_id)
                if len(new_messages) > self.last_message_count:
                    self.messages = new_messages
                    self.last_message_count = len(new_messages)
                    # Update the live display
                    live.update(self._format_conversation_display())
            time.sleep(0.1)  # Check every 100ms

    def show_conversation(self, peer: str, conversation_id: Optional[str] = None):
        """Show and interact with a conversation"""
        self.recipient = peer
        self.current_conversation_id = conversation_id or self.discovery._generate_conversation_id(
            self.discovery.username, peer)
        
        # Get existing messages for this conversation
        self.messages = self.discovery.get_conversation(self.current_conversation_id)
        self.last_message_count = len(self.messages)

        # Clear screen
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Create Live display
        with Live(self._format_conversation_display(), refresh_per_second=10) as live:
            # Start message checking thread
            check_thread = threading.Thread(target=self._check_new_messages, args=(live,))
            check_thread.daemon = True
            check_thread.start()
            
            try:
                # Input loop
                while self.running:
                    try:
                        # Temporarily stop the live display to get input
                        live.stop()
                        message = Prompt.ask("\n[bold green]Enter your message[/bold green]")
                        live.start()
                        
                        # Send the message
                        self._send_message(message)
                        
                        # Update the display
                        live.update(self._format_conversation_display())
                    except KeyboardInterrupt:
                        self.running = False
                        break
            finally:
                self.running = False
                # Clear screen when done
                os.system('cls' if os.name == 'nt' else 'clear')

    def show_message_list(self):
        """Show list of all conversations"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        conversation_panel = self.format_conversation_list()
        
        # Create header
        header = Panel(
            Align.center(Text("P2P Messenger", style="bold white")),
            box=HEAVY,
            style="blue",
            title="Conversations List",
            title_align="center"
        )
        
        # Create instructions
        instructions = Panel(
            Text("Press Ctrl+C to exit", style="italic"),
            box=ROUNDED,
            style="grey50",
            border_style="grey50"
        )
        
        # Display everything
        with Live(Group(header, conversation_panel, instructions), refresh_per_second=4) as live:
            try:
                while self.running:
                    # Periodically update the conversation list
                    conversation_panel = self.format_conversation_list()
                    live.update(Group(header, conversation_panel, instructions))
                    time.sleep(1)
            except KeyboardInterrupt:
                self.running = False
        
        # Clear screen when done
        os.system('cls' if os.name == 'nt' else 'clear')

def send_new_message(discovery, recipient: str):
    """Start a direct message session with a recipient"""
    view = MessageView(discovery, recipient)
    view.show_conversation(recipient)