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
            'broadcast-title': 'bold #00ff00',
            'registry-title': 'bold #00ffff',
            'dual-title': 'bold #ff00ff',
            'broadcast-peer': '#00ff00',  # Green for broadcast peers
            'registry-peer': '#00ffff',   # Cyan for registry peers
            'dual-peer': '#ff00ff',       # Magenta for dual-discovered peers
            'peer-address': '#bbbbbb',    # Light gray for IP addresses
            'peer-port': '#aaaaff',       # Light blue for port numbers
        })

    def _get_user_list_text(self):
        """Generate the formatted user list text with separate sections for different discovery methods"""
        peers = self.discovery.list_peers()
        
        # Separate peers by discovery method
        broadcast_only_peers = {}
        registry_only_peers = {}
        dual_peers = {}
        
        for username, peer in peers.items():
            broadcast = hasattr(peer, 'broadcast_peer') and peer.broadcast_peer
            registry = hasattr(peer, 'registry_peer') and peer.registry_peer
            
            if broadcast and registry:
                dual_peers[username] = peer
            elif broadcast:
                broadcast_only_peers[username] = peer
            elif registry:
                registry_only_peers[username] = peer
        
        # Column widths - consistent across all tables
        username_width = 25
        ip_width = 20
        port_width = 10
        total_width = username_width + ip_width + port_width + 3  # +3 for spacing
        
        # Generate text for the view
        text = []
        
        # Header and introduction
        text.extend([
            ("", "\n"),
            ("class:title", "  Online Peers "),
            ("", "\n\n")
        ])
        
        # 1. Dual-discovered peers section (shown first as they're most reliable)
        if dual_peers:
            text.extend([
                ("class:dual-title", "  Peers Discovered by Both Methods "),
                ("", "\n"),
                ("", "  "),
                ("class:border", "╭" + "─" * total_width + "╮"),
                ("", "\n"),
                ("", "  "),
                ("class:border", " "),
                ("", " "),
                ("", f"{'Username':<{username_width}}"),
                ("", f"{'IP Address':<{ip_width}}"),
                ("", f"{'Port':<{port_width}}"),
                ("class:border", " "),
                ("", "\n"),
                ("", "  "),
                ("class:border", "├" + "─" * total_width + "┤"),
                ("", "\n")
            ])
            
            # User entries
            for username, peer in dual_peers.items():
                port = getattr(peer, 'port', self.discovery.config.port)
                text.extend([
                    ("", "  "),
                    ("class:border", " "),
                    ("", " "),
                    ("class:dual-peer", f"{username:<{username_width}}"),
                    ("class:peer-address", f"{peer.address:<{ip_width}}"),
                    ("class:peer-port", f"{port:<{port_width}}"),
                    ("class:border", " "),
                    ("", "\n")
                ])
            
            # Footer for dual section
            text.extend([
                ("", "  "),
                ("class:border", "╰" + "─" * total_width + "╯"),
                ("", "\n\n")
            ])
        
        # 2. Broadcast peers section
        text.extend([
            ("class:broadcast-title", "  Broadcast Discovered Peers "),
            ("", "\n"),
            ("", "  "),
            ("class:border", "╭" + "─" * total_width + "╮"),
            ("", "\n")
        ])
        
        if not broadcast_only_peers:
            text.extend([
                ("", "  "),
                ("class:border", " "),
                ("fg:gray", f" No broadcast-only peers online{' ' * (total_width - 29)}"),
                ("class:border", " "),
                ("", "\n")
            ])
        else:
            # Header
            text.extend([
                ("", "  "),
                ("class:border", " "),
                ("", " "),
                ("", f"{'Username':<{username_width}}"),
                ("", f"{'IP Address':<{ip_width}}"),
                ("", f"{'Port':<{port_width}}"),
                ("class:border", "  "),
                ("", "\n"),
                ("", "  "),
                ("class:border", "├" + "─" * total_width + "┤"),
                ("", "\n")
            ])
            
            # User entries
            for username, peer in broadcast_only_peers.items():
                port = getattr(peer, 'port', self.discovery.config.port)
                text.extend([
                    ("", "  "),
                    ("class:border", " "),
                    ("", " "),
                    ("class:broadcast-peer", f"{username:<{username_width}}"),
                    ("class:peer-address", f"{peer.address:<{ip_width}}"),
                    ("class:peer-port", f"{port:<{port_width}}"),
                    ("class:border", " "),
                    ("", "\n")
                ])
        
        # Footer for broadcast section
        text.extend([
            ("", "  "),
            ("class:border", "╰" + "─" * total_width + "╯"),
            ("", "\n\n")
        ])
        
        # 3. Registry peers section
        text.extend([
            ("class:registry-title", "  Registry Discovered Peers "),
            ("", "\n"),
            ("", "  "),
            ("class:border", "╭" + "─" * total_width + "╮"),
            ("", "\n")
        ])
        
        if not registry_only_peers:
            text.extend([
                ("", "  "),
                ("class:border", " "),
                ("fg:gray", f" No registry-only peers online{' ' * (total_width - 28)}"),
                ("class:border", " "),
                ("", "\n")
            ])
        else:
            # Header
            text.extend([
                ("", "  "),
                ("class:border", " "),
                ("", " "),
                ("", f"{'Username':<{username_width}}"),
                ("", f"{'IP Address':<{ip_width}}"),
                ("", f"{'Port':<{port_width}}"),
                ("class:border", " "),
                ("", "\n"),
                ("", "  "),
                ("class:border", "├" + "─" * total_width + "┤"),
                ("", "\n")
            ])
            
            # User entries
            for username, peer in registry_only_peers.items():
                port = getattr(peer, 'port', self.discovery.config.port)
                text.extend([
                    ("", "  "),
                    ("class:border", " "),
                    ("", " "),
                    ("class:registry-peer", f"{username:<{username_width}}"),
                    ("class:peer-address", f"{peer.address:<{ip_width}}"),
                    ("class:peer-port", f"{port:<{port_width}}"),
                    ("class:border", " "),
                    ("", "\n")
                ])
        
        # Footer for registry section
        text.extend([
            ("", "  "),
            ("class:border", "╰" + "─" * total_width + "╯"),
            ("", "\n\n")
        ])
        
        # Show registry connection status
        if self.discovery.is_using_registry():
            server_url = self.discovery.get_registry_server_url()
            text.extend([
                ("fg:cyan", f"  Connected to registry server: {server_url}\n")
            ])
        else:
            text.extend([
                ("fg:yellow", f"  Not connected to a registry server (using broadcast only)\n")
            ])
        
        # Add clipboard service status
        if hasattr(self.discovery, 'clipboard') and self.discovery.clipboard:
            clipboard_status = "ACTIVE" if self.discovery.clipboard.running else "INACTIVE"
            clipboard_color = "fg:green" if self.discovery.clipboard.running else "fg:red"
            text.extend([
                (clipboard_color, f"  Clipboard sharing service: {clipboard_status}\n")
            ])
        
        # Summary count
        total_peers = len(peers)
        dual_count = len(dual_peers)
        broadcast_count = len(broadcast_only_peers)
        registry_count = len(registry_only_peers)
        
        text.extend([
            ("fg:white", f"  Total peers online: {total_peers}"),
            ("", " ("),
            ("class:dual-peer", f"{dual_count} dual"),
            ("", ", "),
            ("class:broadcast-peer", f"{broadcast_count} broadcast-only"),
            ("", ", "),
            ("class:registry-peer", f"{registry_count} registry-only"),
            ("", ")\n\n"),
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