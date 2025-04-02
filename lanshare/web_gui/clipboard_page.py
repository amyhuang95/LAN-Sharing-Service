from typing import List
import streamlit as st
import time
from lanshare.web_gui.service import LANSharingService
from lanshare.core.clipboard import Clipboard
from lanshare.core.clipboard import Clip

# Cache the service instance to keep it from page refresh
@st.cache_resource
def setup():
    return LANSharingService.get_instance(st.session_state.username)

# Custom debug log
def debug_log(message: str):
    from datetime import datetime
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(timestamp + " " + message)

# Setup clipboard service connection
service = setup()
clipboard: Clipboard = service.clipboard
if clipboard is None:
    st.error("Error connecting to Clipboard Sharing Service... Please restart the application.")
clipboard.max_clips = 9 # only track 9 recent clips
debug_log("Connecting to LAN Sharing - Clipboard Service")

# initialize session state variables
if "clipboard_status" not in st.session_state:
    st.session_state["clipboard_status"] = clipboard.running
    debug_log("Initialize session_state.clipboard_status")
if "clips" not in st.session_state:
    st.session_state["clips"] = []
    debug_log("Initialize session_state.clips")
if "cb_online_peers" not in st.session_state:
    st.session_state["cb_online_peers"] = set()
    debug_log("Initialize session_state.cb_online_peers")
if "cb_send_peers" not in st.session_state:
    st.session_state["cb_send_peers"] = set()
    debug_log("Initialize session_state.cb_send_peers")
if "cb_receive_peers" not in st.session_state:
    st.session_state["cb_receive_peers"] = set()
    debug_log("Initialize session_state.cb.receive_peers")

def sync_state_with_service():
    """Synchronize the session state with the clipboard service state"""
    # Update service running status
    # st.session_state.clipboard_status = clipboard.running
    
    # Update clips
    st.session_state.clips = clipboard.get_clipboard_history().copy()
    
    # Update peers
    st.session_state.cb_online_peers = set(clipboard.discovery.list_peers().keys())
    st.session_state.cb_send_peers = clipboard.send_to_peers.copy()
    st.session_state.cb_receive_peers = clipboard.receive_from_peers.copy()

def toggle_clipboard():
    """Toggle clipboard on and off based on its current status."""
    if not st.session_state.clipboard_status:
        clipboard.start()
        debug_log("Start clipboard service")
        # st.session_state["clipboard_status"] = True
        # debug_log(f"Update clipboard_status: {st.session_state.clipboard_status}")
    else:
        clipboard.stop()
        debug_log("Stop clipboard service")
        # st.session_state["clipboard_status"] = False
        # debug_log(f"Update clipboard_status: {st.session_state.clipboard_status}")
    sync_state_with_service()
    debug_log(f"clipboard_status: {st.session_state.clipboard_status}")

def clear_history():
    """Clear clipboard history"""
    try:
        clipboard.clip_list.clear()
        st.toast("Clipboard history cleared!", icon="🧹")
        debug_log("Clear clipboard history")
    except Exception as e:
        st.toast(f"Error clearing history. Please refresh the page them retry.", icon="❌")
        debug_log(f"Error clearing history: {str(e)}")
    sync_state_with_service()

def display_clipboard_history(placeholder):
    """Shows list of clips"""
    clips: List[Clip] = st.session_state.clips
    debug_log(f"Displaying clipboard history... Number of clips: {len(clips)}")
    with placeholder.container():
        size = len(clips)
        num_cols = 3
        for i in range(0, size, num_cols):
            cols = st.columns(num_cols)
            for j in range(num_cols):
                index = i + j
                if index < size:
                    clip = clips[index]
                    content = clip.content
                    source = clip.source
                    if len(content) > 150:
                        display_content = content[:150] + "..."
                    else:
                        display_content = content
                    
                    tile = cols[j].container(height=120, border=True)
                    tile.text(display_content)
                    tile.caption("-- " + source)

def display_send_peers(placeholder):
    """Show the send to peers section"""
    with placeholder.container():
        st.subheader("Send To Peers", divider=True, help="Share clipboard with these peers.")
        # check if any online peers
        if not st.session_state.cb_online_peers:
            placeholder.info("No active peers found.")
            return
        placeholder.empty()
        # Select box to add new peers
        available_send_peers = st.session_state.cb_online_peers - st.session_state.cb_send_peers
        debug_log(f"available_send_peers=[{len(available_send_peers)}] online_peers=[{len(st.session_state.cb_online_peers)}] send_peers=[{len(st.session_state.cb_send_peers)}]")
        placeholder_text = "Add a peer" if available_send_peers else "No available peers"
        option = st.selectbox(label="Add a peer to share clipboard",
                    label_visibility="collapsed",
                    index=None,
                    options=available_send_peers,
                    placeholder=placeholder_text,
                    disabled=len(available_send_peers)==0)
        if option:
            clipboard.add_sending_peer(option)
            sync_state_with_service()
        # List all added peers
        send_peers_container = st.empty()
        if not st.session_state.cb_send_peers:
            send_peers_container.info("No peer added in the sending list yet!")
            return
        send_peers_container.empty()
        with send_peers_container.container():
            # Each peer holds a container with a remove btn
            for send_peer in st.session_state.cb_send_peers:
                with st.container(height=50, border=False):
                    peer_left_col, peer_right_col = st.columns(2)
                    peer_left_col.write(send_peer)
                    with peer_right_col:
                        click = st.button(label="", 
                                  icon="❌", 
                                  type="tertiary",
                                  on_click=clipboard.remove_sending_peer, 
                                  args=(send_peer,), 
                                  key="s_" + send_peer)
                        if click:
                            sync_state_with_service()

def display_receive_peers(placeholder):
    """Show the receive from peers section"""
    with placeholder.container():
        st.subheader("Receive From Peers", divider=True, help="Receive clips shared by these peers.")
        # check if any online peers
        if not st.session_state.cb_online_peers:
            placeholder.info("No active peers found.")
            return
        placeholder.empty()
        # Select box to add new peers
        available_receive_peers = st.session_state.cb_online_peers - st.session_state.cb_receive_peers
        debug_log(f"available_receive_peers=[{len(available_receive_peers)}] online_peers=[{len(st.session_state.cb_online_peers)}] receive_peers=[{len(st.session_state.cb_receive_peers)}]")
        placeholder_text = "Add a peer" if available_receive_peers else "No available peers"
        option = st.selectbox(label="Add a peer to receive clipboard",
                     label_visibility="collapsed",
                     index=None,
                    options=available_receive_peers,
                    placeholder=placeholder_text,
                    disabled=len(available_receive_peers)==0)
        if option:
            clipboard.add_receiving_peer(option)
            sync_state_with_service()
        # List all added peers
        receive_peers_container = st.empty()
        if not st.session_state.cb_receive_peers:
            receive_peers_container.info("No peer added to accept clipboards yet!")
            return
        receive_peers_container.empty()
        with receive_peers_container.container():
            # Each peer holds a container with a remove btn
            for receive_peer in st.session_state.cb_receive_peers:
                with st.container(height=50, border=False):
                    rec_left_col, rec_right_col = st.columns(2)
                    rec_left_col.write(receive_peer)
                    with rec_right_col:
                        click = st.button(label="", 
                                  icon="❌", 
                                  type="tertiary",
                                  on_click=clipboard.remove_receiving_peer, 
                                  args=(receive_peer,), 
                                  key="r_" + receive_peer)
                        if click:
                            sync_state_with_service()

def main():
    st.title("📋 Clipboard Sharing")
    sync_state_with_service()

    # Side Bar
    with st.sidebar:
        st.markdown("Copy something on your device and automatically share with active peers you selected!")
        st.header("⚙️ Settings")
        toggle_label = "Status: "
        toggle_label += "On" if st.session_state.clipboard_status else "Off"
        status = st.toggle(toggle_label, 
                  value=st.session_state.clipboard_status, 
                  on_change=toggle_clipboard, 
                  key="clipboard_toggler",
                  help="Turn clipboard sharing on or off")
        st.session_state.clipboard_status = status
        st.button("Clear Clipboard History", on_click=clear_history)
    
    # Check whether the feature is activated, don't render other component if service is not activated
    if not st.session_state.clipboard_status:
        st.info("Clipboard sharing is not enabled. Toggled the setting in the sidebar to activate the feature.")
        return

    # Top Section - Clipboard History
    st.subheader("Clipboard History", divider=True, help="Recently copied contents by connected peers")
    cb_history_container = st.empty()
    with st.container(height=100, border=False):
        if not st.session_state.clips:
            cb_history_container.info("No clips yet...try copy something!")
        else:
            display_clipboard_history(cb_history_container)

    # Bottom Section - Authorized peers list
    bottom_left, bottom_right = st.columns(2)
    display_send_peers(bottom_left)
    display_receive_peers(bottom_right)

    # Refresh data in the main section
    if st.session_state.clipboard_status:
        changed = False

        # Clipboard History data
        clips = clipboard.get_clipboard_history()    
        if clips != st.session_state.clips:
            debug_log(f"New copy detected. clips[{len(clips)}] - st.session_state.clips[{len(st.session_state.clips)}]")
            st.session_state.clips = clips.copy()
            changed = True
        
        # Sharing peer data
        online_peers = set(clipboard.discovery.list_peers().keys())
        send_peers = clipboard.send_to_peers
        receive_peers = clipboard.receive_from_peers
        if st.session_state.cb_online_peers != online_peers:
            st.session_state.cb_online_peers = online_peers.copy()
            changed = True
        if st.session_state.cb_send_peers != send_peers:
            st.session_state.cb_send_peers = send_peers.copy()
            changed = True
        if st.session_state.cb_receive_peers != receive_peers:
            st.session_state.cb_receive_peers = receive_peers.copy()
            changed = True
        
        # Set up auto-refresh
        st.empty()  # This is a placeholder that will trigger the refresh
        time.sleep(1)  # Wait briefly
        st.rerun()  # Rerun after updating data once

        # # refresh page if there is new data
        # if changed:
        #     st.rerun()

        # time.sleep(1) # refresh every 1 second

if __name__ == "__main__":
    main()