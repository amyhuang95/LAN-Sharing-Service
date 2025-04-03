import streamlit as st
import time
import re
from lanshare.web_gui.service import LANSharingService

# Cache the service instance to keep it from page refresh
@st.cache_resource
def setup():
    return LANSharingService.get_instance(st.session_state.username)

def validate_address(address):
    """Validate if the address is in the correct format (IP:port or just IP)."""
    # Check if port is included
    if ':' in address:
        ip, port = address.split(':', 1)
        
        # Validate port
        try:
            port = int(port)
            if port < 1 or port > 65535:
                return False, "Port must be between 1 and 65535"
        except ValueError:
            return False, "Port must be a number"
    else:
        ip = address
    
    # Validate IP address format
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(ip_pattern, ip):
        return False, "Invalid IP address format. Use format: xxx.xxx.xxx.xxx[:port]"
    
    # Validate IP address values
    octets = ip.split('.')
    for octet in octets:
        if int(octet) > 255:
            return False, "IP address octets must be between 0 and 255"
    
    return True, "Valid address"

def main():
    service = setup()

    #Registry Server for secured networks
    with st.sidebar:
        is_registry = st.toggle("Registry Server", False)
        
        # Only show the text input when toggle is on
        if is_registry:
            address = st.text_input("Enter an IP address 👇", 
                                   placeholder="Example: 192.168.1.5:5000")
            
            if address:
                # Validate the address format
                is_valid, message = validate_address(address)
                
                if not is_valid:
                    st.error(message)
                else:
                    # Try to connect to the registry server
                    try:
                        result = service.discovery.register_with_server(address)
                        if result:
                            st.success(f"Connected to registry server at {address}")
                        else:
                            st.error("Failed to connect to registry server. Server may be offline or unreachable.")
                    except Exception as e:
                        st.error(f"Connection error: {str(e)}")
        else:
            # If registry is turned off and was previously connected, disconnect
            if service.discovery.is_using_registry():
                try:
                    result = service.discovery.unregister_from_server()
                    if result:
                        st.success("Disconnected from registry server")
                    else:
                        st.warning("Failed to properly disconnect from registry server")
                except Exception as e:
                    st.error(f"Error during disconnection: {str(e)}")
                

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