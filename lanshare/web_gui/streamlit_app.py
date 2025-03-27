import streamlit as st
import sys
import os
# Ensure the project root is in the Python path.
# Adjust the number of ".." based on your file’s location.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# First add your sidebar content
with st.sidebar:
    st.markdown("### LAN Share")
    st.write("LAN Share is an app that makes sharing data over your local network quick and easy!")
    st.markdown("---")

# Define your pages and navigation outside of the sidebar
main_page = st.Page("home_page.py", title="Home Page", icon="🌐")
message_page = st.Page("message_page.py", title="Message", icon="🗣️")
file_sharing_page = st.Page("file_sharing_page.py", title="Share Files", icon="🤝")
clipboard_page = st.Page("clipboard_page.py", title="Clipboard", icon="📋")

nav = st.navigation([main_page, message_page, file_sharing_page, clipboard_page])

nav.run()