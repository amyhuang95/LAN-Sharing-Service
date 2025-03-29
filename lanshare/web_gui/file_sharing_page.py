import streamlit as st
from lanshare.web_gui.service import LANSharingService

st.markdown("# File Sharing")
st.sidebar.markdown("...")

# Cache the service instance to keep it from page refresh
@st.cache_resource
def setup():
    return LANSharingService.get_instance(st.session_state.username)


def main():
    # Get instance for LAN Sharing Service
    service = setup()
    # Access point for file share manager
    file_share_manager = service.discovery.file_share_manager
    st.write(f"Directory for shared files: {file_share_manager.share_dir}")

if __name__ == "__main__":
    main()