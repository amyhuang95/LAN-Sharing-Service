import streamlit as st
from lanshare.web_gui.service import LANSharingService


st.markdown("# Message")
st.sidebar.markdown("...")

# Cache the service instance to keep it from page refresh
@st.cache_resource
def setup():
    return LANSharingService.get_instance(st.session_state.username)


def main():
    # Get instance for LAN Sharing Service
    service = setup()
    # Access point for core methods for discovery service
    discovery = service.discovery
    st.write(f"Message list: {discovery.list_messages(st.session_state.username)}")

if __name__ == "__main__":
    main()