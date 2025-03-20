from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import Window, HSplit, VSplit, ScrollOffsets
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.formatted_text import HTML

from datetime import datetime
from typing import List, Optional, Dict
import threading
import time
import uuid
import os
import io
from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text
from rich.panel import Panel

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
        self.message_buffer = Buffer()
        
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
        # prompt_toolkit styles with enhanced colors
        self.style = Style.from_dict({
            'username': '#00ff00 bold',     # Bright green for current user (enhanced)
            'peer': '#5555ff bold',         # Brighter blue for other users (enhanced)
            'timestamp': '#aaaaaa',         # Lighter gray for timestamp (enhanced)
            'prompt': '#ff5555',            # Brighter red for prompt (enhanced)
            'info': '#aaaaaa italic',       # Lighter gray italic for info (enhanced)
            'header': 'bg:#000088 #ffffff', # White on blue for header (unchanged)
            'header-text': '#ffffff bold',  # Bold white for header text
            'header-accent': '#ff55ff',     # Pink accent for header decorations
            'box': '#444444',               # Dark gray for box drawing (unchanged)
            'message-box-self': '#00aa00',  # Green for user message boxes (unchanged)
            'message-box-peer': '#0000ff',  # Blue for peer message boxes (unchanged)
            'message-content': '#ffffff',   # White for message content
        })

    def _create_stylish_header(self, title):
        """Create a stylish header for message and conversation views"""
        # Get terminal width
        import shutil
        terminal_width = shutil.get_terminal_size().columns - 2
        
        # Calculate padding based on title length to center the title
        title_len = len(title)
        decoration_length = (terminal_width - title_len - 8) // 2
        
        # Create cool header with symmetric decorations
        left_decor = "<header-accent>╔" + "═" * decoration_length + "╦</header-accent>"
        right_decor = "<header-accent>╦" + "═" * decoration_length + "╗</header-accent>"
        
        # Combine all parts to create a stylish header
        header = f"<header>{left_decor} <header-text>{title}</header-text> {right_decor}</header>\n\n"
        
        return header

    def _format_message_box(self, msg: Message) -> str:
        """Format a single message with Rich panels and align based on sender"""
        # Format timestamp
        time_str = msg.timestamp.strftime("%H:%M:%S")
        
        # Get terminal width
        import shutil
        from rich.panel import Panel
        from rich.console import Console
        from rich.text import Text
        from rich.box import ROUNDED
        from rich.align import Align
        
        terminal_width = shutil.get_terminal_size().columns - 4  # Subtract a bit for margins
        box_width = min(terminal_width * 0.7, 80)  # 70% of terminal width, max 80 chars
        
        # Determine if message is from current user or peer
        is_self = msg.sender == self.discovery.username
        sender_color = "bright_green" if is_self else "bright_blue"  # Enhanced colors
        box_style = "message-box-self" if is_self else "message-box-peer"
        user_style = "username" if is_self else "peer"
        
        # Create StringIO to capture Rich output
        string_io = io.StringIO()
        console = Console(file=string_io, width=terminal_width, highlight=False)
        
        # Format sender and timestamp with enhanced colors
        header_text = Text()
        header_text.append(f"{msg.sender}", style=f"bold {sender_color}")
        header_text.append(f" • {time_str}", style="bright_white dim")
        
        # Create the message content with proper wrapping and enhanced text color
        content_text = Text(msg.content, style="bright_white")
        
        # Create a panel with the message (keeping same panel style)
        panel = Panel(
            content_text,
            title=header_text,
            box=ROUNDED,
            border_style=sender_color,
            width=int(box_width),
            expand=False
        )
        
        # Align panel to the right if from self, left if from peer
        alignment = "right" if is_self else "left"
        aligned_panel = Align.left(panel) if not is_self else Align.right(panel)
        
        # Render the aligned panel
        console.print(aligned_panel)
        panel_str = string_io.getvalue()
        
        # Convert Rich output to prompt_toolkit HTML
        # Replace color and style tags
        if is_self:
            html_out = panel_str.replace("[bold bright_green]", f"<{user_style}>")
            html_out = html_out.replace("[/bold bright_green]", f"</{user_style}>")
            html_out = html_out.replace("[bright_green]", f"<{box_style}>")
            html_out = html_out.replace("[/bright_green]", f"</{box_style}>")
        else:
            html_out = panel_str.replace("[bold bright_blue]", f"<{user_style}>")
            html_out = html_out.replace("[/bold bright_blue]", f"</{user_style}>")
            html_out = html_out.replace("[bright_blue]", f"<{box_style}>")
            html_out = html_out.replace("[/bright_blue]", f"</{box_style}>")
        
        html_out = html_out.replace("[bright_white dim]", "<timestamp>")
        html_out = html_out.replace("[/bright_white dim]", "</timestamp>")
        html_out = html_out.replace("[bright_white]", "<message-content>")
        html_out = html_out.replace("[/bright_white]", "</message-content>")
        
        # Clean up any remaining ANSI codes
        import re
        html_out = re.sub(r'\x1b\[[0-9;]*m', '', html_out)
        
        return html_out

    def _format_messages(self):
        """Format messages for prompt_toolkit display using Rich with terminal width adaptation"""
        # Get terminal width
        import shutil
        from rich.console import Console
        from rich.text import Text
        from rich.panel import Panel
        
        terminal_width = shutil.get_terminal_size().columns - 2  # Subtract a bit for margins
        
        # Create stylish header
        title = f"Conversation with {self.recipient}" if self.recipient else "Message List"
        header = self._create_stylish_header(title)
        
        # Format each message
        message_html = ""
        for msg in sorted(self.messages, key=lambda m: m.timestamp):
            message_html += self._format_message_box(msg) + "\n"
        
        # Add empty message if no messages yet
        if not self.messages:
            empty_io = io.StringIO()
            empty_console = Console(file=empty_io, width=terminal_width, highlight=False)
            empty_console.print("[italic bright_white dim]No messages yet. Type below to start the conversation.[/]")
            empty_msg = empty_io.getvalue()
            empty_msg = empty_msg.replace("[italic bright_white dim]", "<info>")
            empty_msg = empty_msg.replace("[/]", "</info>")
            message_html += empty_msg + "\n\n"
        
        # Add input prompt if in direct message mode
        footer = ""
        if self.recipient:
            footer_io = io.StringIO()
            footer_console = Console(file=footer_io, width=terminal_width, highlight=False)
            footer_console.print("[bold bright_red]Type your message (Enter to send, Ctrl-C to exit)> [/]", end="")
            footer = footer_io.getvalue()
            footer = footer.replace("[bold bright_red]", "<prompt>")
            footer = footer.replace("[/]", "</prompt>")
        else:
            footer_io = io.StringIO()
            footer_console = Console(file=footer_io, width=terminal_width, highlight=False)
            footer_console.print("[italic bright_white dim]Press 'q' to exit[/]")
            footer = footer_io.getvalue()
            footer = footer.replace("[italic bright_white dim]", "<info>")
            footer = footer.replace("[/]", "</info>")
        
        # Clean up any remaining ANSI codes
        import re
        message_html = re.sub(r'\x1b\[[0-9;]*m', '', message_html)
        footer = re.sub(r'\x1b\[[0-9;]*m', '', footer)
            
        # Combine all parts
        return HTML(header + message_html + footer)

    def format_conversation_list(self):
        """Format the list of conversations for prompt_toolkit using Rich table with enhanced text colors"""
        # Get terminal width
        import shutil
        terminal_width = shutil.get_terminal_size().columns - 2  # Subtract a bit for margins
        
        # Group messages by conversation
        conversations: Dict[str, List[Message]] = {}
        for msg in self.discovery.list_messages():
            conv_id = msg.conversation_id
            if conv_id not in conversations:
                conversations[conv_id] = []
            conversations[conv_id].append(msg)
        
        # Create a Rich table and render it to a string
        string_io = io.StringIO()
        console = Console(file=string_io, width=terminal_width, highlight=False)
        
        # Create stylish header directly using prompt_toolkit HTML
        header = self._create_stylish_header("Conversation List")
        
        # Create the Rich table - same structure, enhanced colors
        table = Table(box=box.DOUBLE_EDGE, width=terminal_width)
        table.add_column("ID", style="bright_cyan bold", width=7)
        
        # Calculate dynamic column widths - same as original
        with_width = min(20, max(10, int(terminal_width * 0.2)))  # 20% of width, min 10, max 20
        msg_width = terminal_width - 7 - with_width - 12 - 5  # 7=ID, 12=Time, 5=borders
        
        table.add_column("With", style="bright_blue bold", width=with_width)
        table.add_column("Last Message", style="bright_white", width=msg_width)
        table.add_column("Time", style="bright_white dim", width=12)
        
        # Add rows for each conversation
        if not conversations:
            table.add_row("", "No conversations found", "", "")
        else:
            for conv_id, msgs in conversations.items():
                # Sort messages by timestamp
                msgs.sort(key=lambda m: m.timestamp)
                last_msg = msgs[-1]
                
                # Get the other participant
                other_party = last_msg.recipient if last_msg.sender == self.discovery.username else last_msg.sender
                
                # Format message preview with proper truncation
                preview = last_msg.content.replace('\n', ' ')
                if len(preview) > msg_width - 5:
                    preview = preview[:msg_width - 5] + "..."
                
                # Add row with enhanced colors
                table.add_row(
                    conv_id[:5],
                    other_party[:with_width-2],
                    preview,
                    last_msg.timestamp.strftime('%H:%M:%S')
                )
        
        # Render the table to string
        console.print(table)
        console.print()  # Empty line
        console.print("[italic bright_white dim]Press 'q' to exit[/]")
        
        # Convert the Rich output to HTML that prompt_toolkit can use
        rich_output = string_io.getvalue()
        
        # Replace tags with prompt_toolkit HTML
        rich_output = rich_output.replace("[italic bright_white dim]", "<info>")
        rich_output = rich_output.replace("[/italic bright_white dim]", "</info>")
        rich_output = rich_output.replace("[bright_cyan bold]", "<cyan>")
        rich_output = rich_output.replace("[/bright_cyan bold]", "</cyan>")
        rich_output = rich_output.replace("[bright_blue bold]", "<peer>")
        rich_output = rich_output.replace("[/bright_blue bold]", "</peer>")
        rich_output = rich_output.replace("[bright_white dim]", "<timestamp>")
        rich_output = rich_output.replace("[/bright_white dim]", "</timestamp>")
        rich_output = rich_output.replace("[bright_white]", "<message-content>")
        rich_output = rich_output.replace("[/bright_white]", "</message-content>")
        
        # Return as HTML for prompt_toolkit
        return HTML(header + rich_output)

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
            scroll_offsets=ScrollOffsets(top=1, bottom=1),
            allow_scroll_beyond_bottom=True
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