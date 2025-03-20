from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import Window, HSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.dimension import LayoutDimension as D
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import clear

class UserListView:
    def __init__(self, discovery):
        self.discovery = discovery
        self.running = True
        
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

    def _setup_styles(self):
        """Setup UI styles"""
        self.style = Style.from_dict({
            'border': '#666666',
            'title': 'bold #ffffff',
        })

    def _get_user_list_text(self):
        """Generate the formatted user list text"""
        peers = self.discovery.list_peers()
        text = [
            ("", "\n"),
            ("class:title", "  Online Users "),
            ("", "\n"),
            ("", "  "),
            ("class:border", "╭" + "─" * 50 + "╮"),
            ("", "\n")
        ]
        
        if not peers:
            text.extend([
                ("", "  "),
                ("class:border", "│"),
                ("fg:gray", " No users online"),
                ("", " " * (49 - len("No users online"))),
                ("class:border", "│"),
                ("", "\n")
            ])
        else:
            # Header
            text.extend([
                ("", "  "),
                ("class:border", "│"),
                ("", f" {'Username':<20} {'IP Address':<28}"),
                ("class:border", "│"),
                ("", "\n"),
                ("", "  "),
                ("class:border", "├" + "─" * 50 + "┤"),
                ("", "\n")
            ])
            
            # User entries
            for username, peer in peers.items():
                text.extend([
                    ("", "  "),
                    ("class:border", "│"),
                    ("fg:green", f" {username:<20} "),
                    ("fg:blue", f"{peer.address:<28}"),
                    ("class:border", "│"),
                    ("", "\n")
                ])
        
        # Footer
        text.extend([
            ("", "  "),
            ("class:border", "╰" + "─" * 50 + "╯"),
            ("", "\n\n"),
            ("fg:yellow", "  Press 'q' to exit live view\n")
        ])
        return text

    def show(self):
        """Display the user list view"""
        self.discovery.in_live_view = True

        # Create the layout
        layout = Layout(
            HSplit([
                Window(
                    content=FormattedTextControl(self._get_user_list_text),
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
            self.discovery.in_live_view = False
            clear()