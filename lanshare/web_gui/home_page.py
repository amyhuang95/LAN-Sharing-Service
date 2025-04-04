import streamlit as st
import time
from lanshare.web_gui.service import LANSharingService

# Cache the service instance to keep it from page refresh
@st.cache_resource
def setup():
    return LANSharingService.get_instance(st.session_state.username)
service = setup()

# Maintain session variables
if "is_using_registry" not in st.session_state:
    st.session_state["is_using_registry"] = service.discovery.is_using_registry()
if "registry_address" not in st.session_state:
    st.session_state["registry_address"] = service.discovery.get_registry_server_url()
if "online_peers" not in st.session_state:
    st.session_state["online_peers"] = service.discovery.list_peers()

def sync_registry_status():
    st.session_state["is_using_registry"] = service.discovery.is_using_registry()
    st.session_state["registry_address"] = service.discovery.get_registry_server_url()

def sync_online_peers():
    st.session_state["online_peers"] = service.discovery.list_peers()

def main():
    # Side bar
    with st.sidebar:
        st.subheader("Registry Mode")
        status = "On" if st.session_state.is_using_registry else "Off"
        st.write(f"Status: {status}")
        
        # Show registry option if not in use
        if not st.session_state.is_using_registry: 
            with st.form("address", border=False):
                address = st.text_input(label="Registry address",
                                        help="Register to a server to connect with peers in different subnets of a local network",
                                        placeholder="E.g.: 12.34.56.78:5050")
                submit = st.form_submit_button("Register")
            
            if submit:
                if service.discovery.register_with_server(address):
                    sync_registry_status()
                    st.toast("Successfully registered with a registry server!", icon="🎉")
                else:
                    st.toast("Error connecting to the registry server. Please re-check the provided address.", icon="⚠️")
                st.rerun() # refresh to update status text
        else:
            placeholder = st.empty()
            with placeholder.container():
                st.write(f"Registry address: {st.session_state.registry_address[7:]}") # ignore http://
                if st.button(label="Disconnect"):
                    if service.discovery.unregister_from_server():
                        sync_registry_status()
                        st.toast("Successfully unregistered from registry server!", icon="🎉")
                    else:
                        st.toast("Error unregistering from the registry server.", icon="⚠️")
                    st.rerun() # refresh to update status text

    # Main content
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

    # Refresh active peers list
    while True:
        peers = service.discovery.list_peers()
        with st.container():
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