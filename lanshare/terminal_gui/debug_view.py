from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import Window, HSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.dimension import LayoutDimension as D
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import clear

class DebugView:
    def __init__(self, discovery):
        self.discovery = discovery
        self.running = True
        self.scroll_position = 0
        self.initial_messages = len(self.discovery.config.debug_messages)
        
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

        @self.kb.add('c')
        def _(event):
            """Clear messages on 'c'"""
            self.discovery.config.debug_messages.clear()
            self.initial_messages = 0
            self.scroll_position = 0

        @self.kb.add('up')
        def _(event):
            """Scroll up one line"""
            self.scroll_position = max(0, self.scroll_position - 1)

        @self.kb.add('down')
        def _(event):
            """Scroll down one line"""
            self.scroll_position = min(
                len(self.discovery.config.debug_messages) - 1,
                self.scroll_position + 1
            )

    def _setup_styles(self):
        """Setup UI styles"""
        self.style = Style.from_dict({
            'title': 'bold #ffffff',
        })

    def _get_debug_text(self):
        """Generate the formatted debug text"""
        messages = self.discovery.config.debug_messages[:self.initial_messages + self.scroll_position]
        
        # Show 20 messages per page
        start_idx = max(0, len(messages) - 20)
        visible_messages = messages[start_idx:len(messages)]
        
        text = [
            ("class:title", "Debug Log "),
            ("class:title", f"({len(messages)} messages)"),
            ("", "\n\n")
        ]
        
        if not visible_messages:
            text.append(("fg:gray", "No debug messages\n"))
        else:
            for timestamp, message in visible_messages:
                text.extend([
                    ("fg:blue", f"[{timestamp}] "),
                    ("fg:green", f"{message}"),
                    ("", "\n")
                ])
        
        # Add new message indicator if there are more messages
        if len(self.discovery.config.debug_messages) > self.initial_messages + self.scroll_position:
            text.extend([
                ("", "\n"),
                ("fg:yellow", "↓ New messages below (press down arrow to view)")
            ])
        
        text.extend([
            ("", "\n"),
            ("fg:yellow", "↑/↓ to scroll  |  'q' to exit  |  'c' to clear\n"),
        ])
        return text

    def show(self):
        """Display the debug view"""
        # Enable debug mode
        self.discovery.config.debug = True
        self.discovery.config.save_config()
        self.discovery.in_live_view = False

        # Create the layout
        layout = Layout(
            HSplit([
                Window(
                    content=FormattedTextControl(self._get_debug_text),
                    always_hide_cursor=True,
                    height=D(preferred=22)
                )
            ])
        )

        # Create application
        app = Application(
            layout=layout,
            key_bindings=self.kb,
            full_screen=True,
            mouse_support=True,
            style=self.style
        )

        # Setup refresh thread
        from threading import Thread
        import time

        def refresh_screen():
            while self.running:
                app.invalidate()
                time.sleep(0.1)

        refresh_thread = Thread(target=refresh_screen)
        refresh_thread.daemon = True
        refresh_thread.start()

        # Clear screen and run
        clear()
        try:
            app.run()
        finally:
            # Cleanup
            self.discovery.config.debug = False
            self.discovery.config.save_config()
            self.discovery.in_live_view = True
            clear()
            print("Debug mode disabled")