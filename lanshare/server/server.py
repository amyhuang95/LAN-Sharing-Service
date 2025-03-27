#--API for Service Communications between Front-end and Back-end--

from flask import Flask, jsonify
from lanshare.core.udp_discovery import UDPPeerDiscovery
from lanshare.config.settings import Config

app = Flask(__name__)

# Global references for the discovery service
discovery_service = None

@app.route("/peers")
def get_peers():
    """
    Return a JSON list of current peers from the discovery service.
    """
    if discovery_service is None:
        return jsonify({"error": "Discovery service not initialized"}), 500

    peers_dict = discovery_service.list_peers()  # e.g. {username: PeerObj}
    peers_list = [
        {"username": p.username, "ip": p.address}
        for p in peers_dict.values()
    ]
    return jsonify(peers_list), 200

#   add more routes here, for example:
#   POST /send_file
#   POST /share_clipboard
#   etc.

def init_backend_service(username_with_id):
    """
    Initializes the UDPPeerDiscovery (or other services) and stores
    the instance in a global variable for Flask routes to use.
    """
    global discovery_service
    config = Config()
    discovery_service = UDPPeerDiscovery(username_with_id, config)
    discovery_service.start()

def run_flask_server(host="127.0.0.1", port=5000):
    """
    Run the Flask server. Typically called in a background thread
    or main thread from create.py.
    """
    app.run(host=host, port=port)
