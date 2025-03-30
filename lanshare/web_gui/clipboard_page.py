from typing import List
import streamlit as st
import time
from lanshare.web_gui.service import LANSharingService
from lanshare.core.clipboard import Clipboard
from lanshare.core.clipboard import Clip

st.markdown("# Clipboard")
st.sidebar.markdown("...")

# Cache the service instance to keep it from page refresh
@st.cache_resource
def setup():
    return LANSharingService.get_instance(st.session_state.username)



service = setup()
clipboard: Clipboard = service.clipboard

def toggler():
    if not st.session_state.clipboard_status:
        clipboard.start()
        st.session_state["clipboard_status"] = True
    else:
        clipboard.stop()
        st.session_state["clipboard_status"] = False

def main():
    
    # initialize status to False
    if "clipboard_status" not in st.session_state:
        st.session_state["clipboard_status"] = clipboard.running

    # Top section
    toggle_label = (
        "On"
        if st.session_state.clipboard_status
        else "Off"
    )
    st.toggle(toggle_label, value=st.session_state.clipboard_status, on_change=toggler)
    
    # Middle section
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
                num_rows = size // num_cols
                num_last_row = size % num_cols
                num_rows += 1 if num_last_row > 0 else 0

                i = 0
                for row in range(num_rows):
                    for col in st.columns(num_cols):
                        if i > size - 1:
                            tile = col.empty()
                        else:
                            tile = col.container(height=120, border=True)
                            tile.text(clips[i].content + "\n")
                            tile.caption("-- " + clips[i].source)
                        i += 1

        time.sleep(2) # refresh every 2 seconds

    # Bottom section
    # with st.container():
    #     pass

if __name__ == "__main__":
    main()