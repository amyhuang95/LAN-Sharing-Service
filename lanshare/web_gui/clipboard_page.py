import streamlit as st
from lanshare.web_gui.service import LANSharingService

st.markdown("# Clipboard")
st.sidebar.markdown("...")

# Cache the service instance to keep it from page refresh
@st.cache_resource
def setup():
    return LANSharingService.get_instance(st.session_state.username)


def main():
    service = setup()

if __name__ == "__main__":
    main()