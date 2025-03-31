import streamlit as st
import sys
from lanshare.web_gui.service import LANSharingService

st.set_page_config(layout="wide")


# Define the pages
home_page = st.Page("home_page.py", title="Home Page", icon="🌐")
message_page = st.Page("message_page.py", title="Message", icon="🗣️")
file_sharing_page = st.Page("file_sharing_page.py", title="Share Files", icon="🤝")
clipboard_page = st.Page("clipboard_page.py", title="Clipboard", icon="📋")

with st.sidebar:
    st.markdown("### LAN Share")
    st.write("LAN Share is an app that makes sharing data over your local network quick and easy!")
    st.markdown("---")

# Set up navigation
pg = st.navigation([home_page, message_page, file_sharing_page, clipboard_page])

# Setup username & service instance
@st.cache_resource
def setup():
    st.session_state["username"] = sys.argv[1]
    port = int(sys.argv[2])
    return LANSharingService.get_instance(st.session_state.username, port)

service = setup()

# Run the selected page
pg.run()
