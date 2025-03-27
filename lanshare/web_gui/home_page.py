import argparse
import sys
import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh

def parse_cli_args():
    """
    Parse command-line arguments passed after the `--` to Streamlit.
    For example:
        streamlit run streamlit_app.py -- --username=Bob123
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="UnknownUser", help="Username passed via CLI")
    return parser.parse_args()

def discover_peers():
    """
    Call the Flask server at http://127.0.0.1:5000/peers to retrieve the current peer list.
    Returns a list of dicts, each with 'username' and 'ip' keys.
    """
    try:
        response = requests.get("http://127.0.0.1:5000/peers", timeout=3)
        if response.status_code == 200:
            # Expected a JSON array of peers, e.g.:
            # [ {"username": "Alice", "ip": "192.168.1.5"}, ... ]
            return response.json()
        else:
            # No user found
            return []
    except requests.RequestException as e:
        st.error(f"Error connecting to Flask server: {e}")
        return []

cli_args = parse_cli_args()
username_with_id = cli_args.username

# ---------------- MAIN CONTENT ------------------
st.markdown("<div class='main-content'>", unsafe_allow_html=True)

st.markdown(f"### Welcome to LAN Share, `{username_with_id}`!")
st.write(
    "You can interact with others in the local network easily for the following tasks:\n\n"
    "   👈 **Share files and directories**  \n"
    "   💬 **Chat with others**  \n"
    "   📋 **Share clipboard contents**  \n\n"
    "👈 Open the side bar and start sharing!"
)

st.markdown("---")
st.subheader("Online Users")

# Auto-refresh every 5 seconds (5000 ms)
# st_autorefresh will rerun the script, so each run re-calls discover_peers()
count = st_autorefresh(interval=5000, limit=None, key="peer_autorefresh")

users_list = discover_peers()
if users_list:
    st.table(users_list)
else:
    st.write("No users discovered at the moment.")

st.markdown("</div>", unsafe_allow_html=True)
