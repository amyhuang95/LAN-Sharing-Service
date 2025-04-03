import streamlit as st
import time
from lanshare.web_gui.service import LANSharingService

# Cache the service instance to keep it from page refresh
@st.cache_resource
def setup():
    return LANSharingService.get_instance(st.session_state.username)

def main():
    service = setup()

    with st.sidebar:
        address = st.text_input(
        "Enter some text 👇",
    )
        if address:
            service.discovery.register_with_server(address)


    st.markdown(f"### Welcome to LAN Share, `{service.username}`!")
    st.write(
    "You can interact with others in the local network easily for the following tasks:\n\n"
    "   🗂️ **Share files and directories**  \n"
    "   💬 **Chat with others**  \n"
    "   📋 **Share clipboard contents**  \n\n"
    "👈 Open the side bar and start sharing!"
    )

    st.markdown("---")
    st.subheader("Online Users")

    active_peers_container = st.empty()

    while True:
        peers = service.discovery.list_peers()

        if not peers:
            active_peers_container.info("No active peers found.")
        else:
            data = []
            for username, peer in peers.items():
                data.append({
                    "Username": username,
                    "IP Address": peer.address,
                    "Port": str(peer.port),
                    "Last Seen": peer.last_seen
                })
            active_peers_container.dataframe(data)

        time.sleep(1) # refresh every 1 second


if __name__ == "__main__":
    main()