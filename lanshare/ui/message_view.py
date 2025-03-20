from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import Window, HSplit, VSplit, ScrollOffsets
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.filters import Condition

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED, HEAVY, DOUBLE
from rich.table import Table
from rich.style import Style as RichStyle
from rich.console import ConsoleOptions, RenderResult

from datetime import datetime
from typing import List, Optional, Dict
import threading
import time
import uuid
import io

from ..core.types import Message

class RichToPromptToolkit:
    """Utility class to convert Rich renderable objects to prompt_toolkit formatted text"""
    @staticmethod
    def convert(renderable) -> List:
        """Convert a Rich renderable to prompt_toolkit formatted text"""
        console = Console(file=io.StringIO(), width=100)
        console.print(renderable)
        output = console.file.getvalue()
        
        # Simple conversion - a more sophisticated version would handle ANSI codes
        return [("", output)]

class MessageView:
    def __init__(self, discovery, recipient=None):
        self.discovery = discovery
        self.recipient = recipient
        self.running = True
        self.messages: List[Message] = []
        self.last_check = datetime.now()
        self.last_message_count = 0
        self.current_conversation_id = None
        self.message_buffer = Buffer()
        
        # Rich console for formatting
        self.console = Console(width=120, record=True)
        
        # Message styles for Rich
        self.rich_styles = {
            'user_message': RichStyle(color="green", bold=True),
            'peer_message': RichStyle(color="blue", bold=True),
            'timestamp': RichStyle(color="grey62"),
            'system': RichStyle(color="yellow", italic=True),
            'header': RichStyle(color="white", bold=True),
            'divider': RichStyle(color="grey50")
        }
        
        # Setup components
        self._setup_keybindings()
        self._setup_styles()

    def _setup_keybindings(self):
        self.kb = KeyBindings()

        @self.kb.add('c-c')
        @self.kb.add('q')
        def _(event):
            self.running = False
            event.app.exit()

        @self.kb.add('enter')
        def _(event):
            if self.message_buffer.text:
                self._send_message(self.message_buffer.text)
                self.message_buffer.text = ""

    def _setup_styles(self):
        # prompt_toolkit styles
        self.style = Style.from_dict({
            'username': '#00aa00 bold',    # Green for current user
            'peer': '#0000ff bold',        # Blue for other users
            'timestamp': '#888888',        # Gray for timestamp
            'prompt': '#ff0000',           # Red for prompt
            'info': '#888888 italic',      # Gray italic for info
            'header': 'bg:#000088 #ffffff', # White on blue for header
        })

    def _format_rich_message(self, msg: Message) -> Panel:
        """Format a single message using Rich Panel"""
        # Format timestamp
        time_str = msg.timestamp.strftime("%H:%M:%S")
        
        # Determine if message is from current user or peer
        is_self = msg.sender == self.discovery.username
        
        # Create header with sender info and timestamp
        header = Text()
        header.append(
            f"{msg.sender}", 
            style=self.rich_styles['user_message'] if is_self else self.rich_styles['peer_message']
        )
        header.append(f" • {time_str}", style=self.rich_styles['timestamp'])
        
        # Create message content
        content = Text(msg.content)
        
        # Create panel with appropriate styling
        border_style = "green" if is_self else "blue"
        panel = Panel(
            content,
            box=ROUNDED,
            border_style=border_style,
            title=header,
            title_align="left",
            width=None
        )
        
        return panel

    def _format_messages(self):
        """Format messages for prompt_toolkit display"""
        formatted_text = []
        
        # Add header
        title = f"Conversation with {self.recipient}" if self.recipient else "Message List"
        formatted_text.extend([
            ("class:header", f"╔═══ {title} ").ljust(100, "═") + "╗\n",
        ])
        
        # Format each message
        for msg in sorted(self.messages, key=lambda m: m.timestamp):
            # Use Rich to format the message
            panel = self._format_rich_message(msg)
            
            # Convert Rich panel to string
            with self.console.capture() as capture:
                self.console.print(panel)
            panel_str = capture.get()
            
            # Add to formatted text
            formatted_text.extend([("", panel_str + "\n")])
        
        # Add input prompt if in direct message mode
        if self.recipient:
            formatted_text.extend([
                ("", "\n"),
                ("class:prompt", "Type your message (Enter to send, Ctrl-C to exit)> ")
            ])
        else:
            formatted_text.extend([
                ("", "\n"),
                ("class:prompt", "Press 'q' to exit")
            ])
            
        return formatted_text

    def format_conversation_list(self):
        """Format the list of conversations using Rich Table"""
        # Group messages by conversation
        conversations: Dict[str, List[Message]] = {}
        for msg in self.discovery.list_messages():
            conv_id = msg.conversation_id
            if conv_id not in conversations:
                conversations[conv_id] = []
            conversations[conv_id].append(msg)
        
        # Create a Rich table
        table = Table(
            box=DOUBLE,
            show_header=True,
            header_style="bold white on blue"
        )
        
        table.add_column("ID", style="cyan", width=6)
        table.add_column("With", style="blue bold")
        table.add_column("Last Message", style="white")
        table.add_column("Time", style="grey62", width=10)
        
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
        
        # Convert Rich table to string
        with self.console.capture() as capture:
            self.console.print(table)
        table_str = capture.get()
        
        # Format for prompt_toolkit
        formatted_text = [
            ("class:header", "╔═══ Conversations List ").ljust(100, "═") + "╗\n",
            ("", table_str + "\n"),
            ("class:info", "Press 'q' to exit\n")
        ]
        
        return formatted_text

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
                # Force update display
                if hasattr(self, 'app'):
                    self.app.invalidate()

    def _check_new_messages(self):
        """Check for new messages and update display"""
        while self.running:
            if self.recipient and self.current_conversation_id:
                # Get all messages for this conversation
                new_messages = self.discovery.get_conversation(self.current_conversation_id)
                if len(new_messages) > self.last_message_count:
                    self.messages = new_messages
                    self.last_message_count = len(new_messages)
                    # Force refresh of the display
                    if hasattr(self, 'app'):
                        self.app.invalidate()
            time.sleep(0.5)  # Check every 500ms

    def show_conversation(self, peer: str, conversation_id: Optional[str] = None):
        """Show and interact with a conversation"""
        self.recipient = peer
        self.current_conversation_id = conversation_id or self.discovery._generate_conversation_id(
            self.discovery.username, peer)
        
        # Get existing messages for this conversation
        self.messages = self.discovery.get_conversation(self.current_conversation_id)
        self.last_message_count = len(self.messages)

        # Create auto-scrolling message window
        message_window = Window(
            content=FormattedTextControl(
                self._format_messages,
                focusable=False  # Make message window not focusable
            ),
            wrap_lines=True,
            always_hide_cursor=True,
            scroll_offsets=ScrollOffsets(top=1, bottom=1)
        )

        # Add input window if in conversation mode
        if self.recipient:
            input_window = Window(
                content=BufferControl(
                    buffer=self.message_buffer,
                    focusable=True
                ),
                height=1,
                dont_extend_height=True
            )
            layout = Layout(HSplit([
                message_window,
                input_window
            ]))
            # Ensure input window gets focus
            layout.focus(input_window)
        else:
            layout = Layout(message_window)

        # Create and configure the application
        self.app = Application(
            layout=layout,
            key_bindings=self.kb,
            full_screen=True,
            style=self.style,
            mouse_support=True
        )

        # Clear screen
        clear()
        
        # Start message checking thread
        check_thread = threading.Thread(target=self._check_new_messages)
        check_thread.daemon = True
        check_thread.start()

        try:
            self.app.run()
        finally:
            self.running = False
            clear()

    def show_message_list(self):
        """Show list of all conversations"""
        app = Application(
            layout=Layout(
                Window(
                    content=FormattedTextControl(self.format_conversation_list),
                    wrap_lines=True
                )
            ),
            key_bindings=self.kb,
            full_screen=True,
            style=self.style,
            mouse_support=True
        )

        clear()
        app.run()
        clear()

def send_new_message(discovery, recipient: str):
    """Start a direct message session with a recipient"""
    view = MessageView(discovery, recipient)
    view.show_conversation(recipient)