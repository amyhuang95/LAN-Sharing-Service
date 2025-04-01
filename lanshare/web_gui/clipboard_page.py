from typing import List
import streamlit as st
import time
from lanshare.web_gui.service import LANSharingService
from lanshare.core.clipboard import Clipboard
from lanshare.core.clipboard import Clip

# # Page configuration
# st.set_page_config(
#     page_title="LAN Share - Clipboard",
#     page_icon="📋",
#     layout="wide"
# )

# Cache the service instance to keep it from page refresh
@st.cache_resource
def setup():
    return LANSharingService.get_instance(st.session_state.username)

service = setup()
clipboard: Clipboard = service.clipboard

# initialize session state variables
if "clipboard_status" not in st.session_state:
    st.session_state["clipboard_status"] = clipboard.running


def toggler():
    if not st.session_state.clipboard_status:
        clipboard.start()
        st.session_state["clipboard_status"] = True
    else:
        clipboard.stop()
        st.session_state["clipboard_status"] = False

def main():
    st.markdown("# 📋 Clipboard Sharing")

    with st.sidebar:
        st.markdown("Copy something on your device and automatically share with active peers you selected!")
        st.header("⚙️ Settings")
        # Top section
        toggle_label = (
            "On"
            if st.session_state.clipboard_status
            else "Off"
        )
        st.toggle(toggle_label, value=st.session_state.clipboard_status, on_change=toggler)
    
    # Middle section
    st.subheader("Clipboard History")
    clips_container = st.empty()
    curr_clips = []
    while st.session_state.clipboard_status:
        clips: List[Clip] = clipboard.get_clipboard_history()

        if not clips:
            clips_container.write("No clips yet...try copy something!")
        elif clips != curr_clips:
            clips_container.empty() # clear previous content
            with clips_container.container():
                curr_clips = clips.copy()
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

        time.sleep(2) # refresh every 2 seconds

    # Bottom section
    # with st.container():
    #     pass

if __name__ == "__main__":
    main()