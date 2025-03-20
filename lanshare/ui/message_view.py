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
        # prompt_toolkit styles
        self.style = Style.from_dict({
            'username': '#00aa00 bold',     # Green for current user
            'peer': '#0000ff bold',         # Blue for other users
            'timestamp': '#888888',         # Gray for timestamp
            'prompt': '#ff0000',            # Red for prompt
            'info': '#888888 italic',       # Gray italic for info
            'header': 'bg:#000088 #ffffff', # White on blue for header
            'box': '#444444',               # Dark gray for box drawing
            'message-box-self': '#00aa00',  # Green for user message boxes
            'message-box-peer': '#0000ff',  # Blue for peer message boxes
        })

    def _format_message_box(self, msg: Message) -> str:
        """Format a single message with HTML for prompt_toolkit, handling wrapping properly"""
        # Format timestamp
        time_str = msg.timestamp.strftime("%H:%M:%S")
        
        # Get terminal width
        import shutil
        terminal_width = shutil.get_terminal_size().columns - 4  # Subtract a bit for margins
        box_width = min(terminal_width, 80)  # Cap at 80 or terminal width, whichever is smaller
        
        # Determine if message is from current user or peer
        is_self = msg.sender == self.discovery.username
        box_style = "message-box-self" if is_self else "message-box-peer"
        user_style = "username" if is_self else "peer"
        
        # Calculate header width
        header_text = f"{msg.sender} • {time_str}"
        
        # Create nicely formatted HTML for the message header
        html = f"""
        <{box_style}>╭{'─' * (min(box_width - 2, len(header_text) + 4))}╮</{box_style}>
        <{box_style}>│ </{box_style}><{user_style}>{msg.sender}</{user_style}> <timestamp>• {time_str}</timestamp><{box_style}>{' ' * max(0, box_width - len(header_text) - 4)} │</{box_style}>
        <{box_style}>├{'─' * (box_width - 2)}┤</{box_style}>
        """
        
        # Process message content with proper wrapping
        content_width = box_width - 4  # Subtract margin for the box borders
        lines = []
        
        # Split the message by newlines first
        for paragraph in msg.content.split('\n'):
            # Then wrap each paragraph to fit the content width
            current_line = ""
            for word in paragraph.split():
                if len(current_line) + len(word) + 1 <= content_width:
                    current_line += (" " + word if current_line else word)
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
        
        # If no content, add a single empty line
        if not lines:
            lines = [""]
            
        # Add message content with proper wrapping
        for line in lines:
            padding = ' ' * (box_width - len(line) - 4)  # Calculate padding based on box width
            html += f"<{box_style}>│ </{box_style}>{line}{padding}<{box_style}> │</{box_style}>\n"
            
        # Close the box
        html += f"<{box_style}>╰{'─' * (box_width - 2)}╯</{box_style}>\n"
        
        return html

    def _format_messages(self):
        """Format messages for prompt_toolkit display using HTML with terminal width adaptation"""
        # Get terminal width
        import shutil
        terminal_width = shutil.get_terminal_size().columns - 2  # Subtract a bit for margins
        
        # Create header
        title = f"Conversation with {self.recipient}" if self.recipient else "Message List"
        header = f"<header>{'═' * 10} {title} {'═' * (terminal_width - len(title) - 12)}</header>\n\n"
        
        # Format each message
        message_html = ""
        for msg in sorted(self.messages, key=lambda m: m.timestamp):
            message_html += self._format_message_box(msg) + "\n"
        
        # Add empty message if no messages yet
        if not self.messages:
            message_html += "<info>No messages yet. Type below to start the conversation.</info>\n\n"
        
        # Add input prompt if in direct message mode
        footer = ""
        if self.recipient:
            footer = "\n<prompt>Type your message (Enter to send, Ctrl-C to exit)> </prompt>"
        else:
            footer = "\n<info>Press 'q' to exit</info>"
            
        # Combine all parts
        return HTML(header + message_html + footer)

    def format_conversation_list(self):
        """Format the list of conversations for prompt_toolkit with proper terminal width"""
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
        
        # Calculate column widths based on terminal width
        id_width = 7
        time_width = 12
        with_width = min(20, max(10, int(terminal_width * 0.2)))  # 20% of width, min 10, max 20
        msg_width = terminal_width - id_width - with_width - time_width - 5  # 5 for borders
        
        # Create header
        header = f"<header>{'═' * (terminal_width - 1)}</header>\n"
        header += f"<header>{'═' * 10} Conversations List {'═' * (terminal_width - 30)}</header>\n\n"
        
        # Create table header with box drawing characters
        table = f"<box>┌{'─' * id_width}┬{'─' * with_width}┬{'─' * msg_width}┬{'─' * time_width}┐</box>\n"
        table += f"<box>│</box> {'ID'.ljust(id_width - 1)}<box>│</box> {'With'.ljust(with_width - 1)}<box>│</box> {'Last Message'.ljust(msg_width - 1)}<box>│</box> {'Time'.ljust(time_width - 1)}<box>│</box>\n"
        table += f"<box>├{'─' * id_width}┼{'─' * with_width}┼{'─' * msg_width}┼{'─' * time_width}┤</box>\n"
        
        # Add rows for each conversation
        if not conversations:
            table += f"<box>│</box> {'No conversations found'.ljust(terminal_width - 4)}<box>│</box>\n"
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
                
                # Add row with proper padding
                table += f"<box>│</box> <cyan>{conv_id[:5].ljust(id_width - 2)}</cyan><box>│</box> <peer>{other_party[:with_width-2].ljust(with_width - 2)}</peer><box>│</box> {preview.ljust(msg_width - 1)}<box>│</box> <timestamp>{last_msg.timestamp.strftime('%H:%M:%S')}</timestamp><box>│</box>\n"
        
        # Close the table
        table += f"<box>└{'─' * id_width}┴{'─' * with_width}┴{'─' * msg_width}┴{'─' * time_width}┘</box>\n\n"
        
        # Add footer
        footer = "<info>Press 'q' to exit</info>"
        
        # Combine all parts
        return HTML(header + table + footer)

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