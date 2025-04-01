from typing import List
import streamlit as st
import threading
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
debug_log("Connecting to LAN Sharing - Clipboard Service")

# initialize session state variables
if "clipboard_status" not in st.session_state:
    st.session_state["clipboard_status"] = clipboard.running
    debug_log(f"Update clipboard_status: {st.session_state["clipboard_status"]}")
if "cb_refresh_seconds" not in st.session_state:
    st.session_state["cb_refresh_seconds"] = 1
if "clips" not in st.session_state:
    st.session_state["clips"] = []

def toggle_clipboard():
    """Toggle clipboard on and off based on its current status."""
    if not st.session_state.clipboard_status:
        clipboard.start()
        debug_log("Start clipboard service")
        st.session_state["clipboard_status"] = True
        debug_log(f"Update clipboard_status: {st.session_state["clipboard_status"]}")
    else:
        clipboard.stop()
        debug_log("Stop clipboard service")
        st.session_state["clipboard_status"] = False
        debug_log(f"Update clipboard_status: {st.session_state["clipboard_status"]}")

def clear_history():
    """Clear clipboard history"""
    try:
        clipboard.clip_list.clear()
        st.toast("Clipboard history cleared!")
        debug_log("Clear clipboard history")
    except Exception as e:
        st.error(f"Error clearing history: {str(e)}")

def display_clipboard_history(placeholder, clips):
    """Shows list of clips"""
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

def main():
    st.markdown("# 📋 Clipboard Sharing")

    # Side Bar
    with st.sidebar:
        st.markdown("Copy something on your device and automatically share with active peers you selected!")
        st.header("⚙️ Settings")
        # Top section
        toggle_label = "Status: "
        toggle_label += "On" if st.session_state.clipboard_status else "Off"
        st.toggle(toggle_label, 
                  value=st.session_state.clipboard_status, 
                  on_change=toggle_clipboard, 
                  help="Turn clipboard sharing on or off")
        st.button("Clear Clipboard History", on_click=clear_history)
    
    # Check whether the feature is activated
    if not st.session_state.clipboard_status:
        st.info("Clipboard sharing is not enabled. Toggled the setting in the sidebar to activate the feature.")
        return

    # Main Section - Top
    st.subheader("Clipboard History")
    cb_history_container = st.empty()
    curr_clips = []

    # Refresh the main section
    while st.session_state.clipboard_status:
        # Clipboard History
        clips: List[Clip] = clipboard.get_clipboard_history()
        debug_log(f"st.session_state.clips[{len(st.session_state.clips)}] - clips[{len(clips)}]")
        if not clips:
            cb_history_container.write("No clips yet...try copy something!")
            st.session_state.clips.clear()
        elif clips != curr_clips:
            cb_history_container.empty()
            curr_clips = clips.copy()
            display_clipboard_history(cb_history_container, curr_clips)
        
        time.sleep(st.session_state.cb_refresh_seconds)
    

    # clips_container = st.empty()
    # curr_clips = []
    
    # while st.session_state.clipboard_status:
    #     clips: List[Clip] = clipboard.get_clipboard_history()

    #     if not clips:
    #         clips_container.write("No clips yet...try copy something!")
    #     elif clips != curr_clips:
    #         clips_container.empty() # clear previous content
    #         with clips_container.container():
    #             curr_clips = clips.copy()
    #             size = len(clips)
    #             num_cols = 3

    #             for i in range(0, size, num_cols):
    #                 cols = st.columns(num_cols)
    #                 for j in range(num_cols):
    #                     index = i + j
    #                     if index < size:
    #                         clip = clips[index]
    #                         content = clip.content
    #                         source = clip.source
    #                         if len(content) > 150:
    #                             display_content = content[:150] + "..."
    #                         else:
    #                             display_content = content
                            
    #                         tile = cols[j].container(height=120, border=True)
    #                         tile.text(display_content)
    #                         tile.caption("-- " + source)

    #     time.sleep(2) # refresh every 2 seconds
        

    # Bottom section
    # with st.container():
    #     pass

if __name__ == "__main__":
    main()