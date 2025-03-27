#!/usr/bin/env python3
"""Registry server for LAN Sharing Service.

This script runs a registry server that helps peers discover each other
in restricted networks where UDP broadcast doesn't work (like eduroam).

Run this on any machine that's accessible to all peers.
"""

from flask import Flask, request, jsonify
import time
import logging
import argparse
import socket
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.layout import Layout
from rich.live import Live
from rich.align import Align

# Configure Flask to be less verbose
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Initialize Rich console
console = Console()

app = Flask(__name__)
peers = {}  # Store peer information
start_time = datetime.now()
stats = {
    "registrations": 0,
    "unregistrations": 0,
    "heartbeats": 0,
    "peer_requests": 0
}

@app.route('/register', methods=['POST'])
def register():
    """Register a peer with the registry."""
    try:
        peer_data = request.json
        if not all(k in peer_data for k in ['username', 'address', 'port']):
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
            
        peer_data['last_seen'] = time.time()
        is_new = peer_data['username'] not in peers
        peers[peer_data['username']] = peer_data
        
        # Log with port included
        console.print(f"[bold green] Peer registered:[/] [cyan]{peer_data['username']}[/] at [yellow]{peer_data['address']}:{peer_data['port']}[/]")
        
        return jsonify({"status": "registered"})
    except Exception as e:
        console.print(f"[bold red]Error in register:[/] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/unregister', methods=['POST'])
def unregister():
    """Unregister a peer from the registry."""
    try:
        peer_data = request.json
        if 'username' not in peer_data:
            return jsonify({"status": "error", "message": "Username required"}), 400
            
        username = peer_data['username']
        if username in peers:
            del peers[username]
            # Update stats
            stats["unregistrations"] += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            console.print(f"[bold yellow][{timestamp}] Peer unregistered:[/] [cyan]{username}[/]")
            
        return jsonify({"status": "unregistered"})
    except Exception as e:
        console.print(f"[bold red]Error in unregister:[/] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    """Update peer's last seen timestamp."""
    try:
        peer_data = request.json
        if 'username' not in peer_data:
            return jsonify({"status": "error", "message": "Username required"}), 400
            
        username = peer_data['username']
        if username in peers:
            peers[username]['last_seen'] = time.time()
            stats["heartbeats"] += 1
            
        return jsonify({"status": "success"})
    except Exception as e:
        console.print(f"[bold red]Error in heartbeat:[/] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/peers', methods=['GET'])
def get_peers():
    """Get list of registered peers (excluding expired ones)."""
    try:
        # Remove stale peers (not seen in 30 seconds)
        current_time = time.time()
        for username in list(peers.keys()):
            if current_time - peers[username]['last_seen'] > 30:
                timestamp = datetime.now().strftime("%H:%M:%S")
                console.print(f"[bold red][{timestamp}] Peer expired:[/] [cyan]{username}[/]")
                del peers[username]
        
        # Update stats
        stats["peer_requests"] += 1
        
        return jsonify(list(peers.values()))
    except Exception as e:
        console.print(f"[bold red]Error in get_peers:[/] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/', methods=['GET'])
def info():
    """Display information about the registry server."""
    html = f"""
    <html>
    <head>
        <title>LAN Sharing Service Registry</title>
    </head>
    <body>
        <h1>LAN Sharing Service Registry</h1>
        <p>See console for registry information.</p>
    </body>
    </html>
    """
    return html

def get_local_ip():
    """Get the local IP address of this machine."""
    try:
        # Create a temporary socket to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"  # Fallback to localhost

def create_dashboard(host, port, active_peers):
    """Create a rich dashboard layout."""
    # Create the layout
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=4)
    )
    
    # Split the main section into left and right
    layout["main"].split_row(
        Layout(name="peers", ratio=2),
        Layout(name="stats", ratio=1),
    )
    
    # Header section
    header_text = Text()
    header_text = Text("LAN Sharing Service - Registry Server", style="bold white")
    header_text.append(f"Server Address: ", style="bright_white")
    header_text.append(f"{host}:{port}", style="bold yellow")
    header_text.append(f"  •  Running since: ", style="bright_white")
    header_text.append(f"{start_time.strftime('%Y-%m-%d %H:%M:%S')}", style="green")
    

    # Header panel - update panel style to be cleaner
    header_panel = Panel(
        Align.center(header_text),
        box=box.SIMPLE,
        style="white",
        border_style="bright_white"
    )
    layout["header"].update(header_panel)
    
    # Create the peer table
    peer_table = Table(
        title="Online Peers", 
        box=box.ROUNDED, 
        border_style="bright_blue", 
        title_style="bold cyan",
        highlight=True,
        header_style="bold bright_white"
    )
    
    peer_table.add_column("Username", style="cyan")
    peer_table.add_column("IP Address", style="yellow")
    peer_table.add_column("Port")
    peer_table.add_column("Last Seen", style="green")
    
    current_time = time.time()
    peer_count = 0
    
    # Add rows for each active peer
    for username, peer_data in active_peers.items():
        last_seen_secs = int(current_time - peer_data["last_seen"])
        if last_seen_secs <= 30:  # Only show active peers
            peer_count += 1
            peer_table.add_row(
                username,
                peer_data["address"],
                str(peer_data["port"]),
                f"{last_seen_secs}s ago"
            )
    
    # Add the peer table to the layout
    layout["peers"].update(Panel(
        peer_table, 
        title=f"[bold cyan]Active Peers: {peer_count}[/]",
        border_style="blue"
    ))
    
    # Create statistics panel
    stats_table = Table(box=box.ROUNDED, show_header=False, border_style="cyan")
    stats_table.add_column("Stat", style="bright_white")
    stats_table.add_column("Value", style="green")
    
    stats_table.add_row("Registrations", str(stats["registrations"]))
    stats_table.add_row("Unregistrations", str(stats["unregistrations"]))
    stats_table.add_row("Heartbeats", str(stats["heartbeats"]))
    stats_table.add_row("Peer Requests", str(stats["peer_requests"]))
    stats_table.add_row("Uptime", get_uptime())
    
    stats_panel = Panel(
        stats_table,
        title="[bold cyan]Server Statistics[/]",
        border_style="blue"
    )
    layout["stats"].update(stats_panel)
    
    # Create footer with connection instructions
    connection_cmd = f"registry connect {host}:{port}"
    footer_text = Text()
    footer_text.append("Connection Instructions\n", style="bold bright_white")
    footer_text.append("Command for peers to connect: ", style="bright_white")
    footer_text.append(f"{connection_cmd}", style="bold green")
    
    footer_panel = Panel(
        footer_text,
        box=box.ROUNDED,
        border_style="blue"
    )
    layout["footer"].update(footer_panel)
    
    return layout

def get_uptime():
    """Get server uptime as a formatted string."""
    uptime = datetime.now() - start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def update_dashboard(host, port, live):
    """Update the live dashboard."""
    # Filter active peers
    current_time = time.time()
    active_peers = {username: peer_data for username, peer_data in peers.items() 
                   if current_time - peer_data["last_seen"] <= 30}
    
    # Create dashboard with current data
    layout = create_dashboard(host, port, active_peers)
    
    # Update the live display
    live.update(layout)

def main():
    """Run the registry server with a Rich console interface."""
    parser = argparse.ArgumentParser(description='LAN Sharing Service Registry Server')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on (default: 5000)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    args = parser.parse_args()
    
    local_ip = get_local_ip()
    
    # Initial welcome message
    console.print(Panel.fit(
        f"[bold green]LAN Sharing Service Registry Server[/]",
        border_style="green"
    ))
    console.print(f"[cyan]Server address for peers to connect:[/] [bold yellow]{local_ip}:{args.port}[/]")
    console.print(f"[cyan]Command for peers:[/] [bold green]registry connect {local_ip}:{args.port}[/]")
    console.print()
    console.print("[cyan]Starting server and dashboard...[/]")
    
    # Start the Flask server in a background thread
    from threading import Thread
    server_thread = Thread(target=lambda: app.run(host=args.host, port=args.port, debug=False, use_reloader=False))
    server_thread.daemon = True
    server_thread.start()
    
    try:
        # Start the live dashboard
        with Live(screen=True, auto_refresh=False) as live:
            while True:
                update_dashboard(local_ip, args.port, live)
                live.refresh()
                time.sleep(1)  # Update once per second
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Shutting down registry server...[/]")

if __name__ == '__main__':
    main()