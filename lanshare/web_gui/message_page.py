import streamlit as st
from lanshare.web_gui.service import LANSharingService
from datetime import datetime
import time
from streamlit_autorefresh import st_autorefresh

# Custom CSS styling
st.markdown("""
<style>
.stApp {
    padding-top: 0.5rem;
}

.main-container {
    display: flex;
    flex-direction: row;
    gap: 1rem;
    height: calc(100vh - 80px);
}

.user-sidebar {
    width: 30%;
    padding: 0.5rem;
}

.chat-area {
    width: 70%;
    padding: 0.5rem;
}

.user-list {
    margin-top: 0.5rem;
}

.user-button {
    width: 100%;
    text-align: left;
    padding: 0.5rem;
    margin: 0.2rem 0;
    border-radius: 5px;
    border: 1px solid #e0e0e0;
    background: white;
    cursor: pointer;
}

.user-button:hover {
    background-color: #f0f0f0;
}

.user-button.selected {
    background-color: #e3f2fd;
    border-color: #bbdefb;
}

.message-container {
    height: calc(100% - 120px);
    overflow-y: auto;
    margin: 0.5rem 0;
}

.message {
    padding: 0.75rem;
    margin: 0.5rem 0;
    border-radius: 8px;
    max-width: 80%;
    color: #666;
    bold: True;

}

.incoming {
    background: #f1f1f1;
    margin-right: auto;
}

.outgoing {
    background: #e3f2fd;
    margin-left: auto;
}

.timestamp {
    font-size: 0.7rem;
    color: #716e6d;
    margin-top: 0.25rem;
}
</style>
""", unsafe_allow_html=True)

st.title("✉️ Messages")

@st.cache_resource
def setup():
    return LANSharingService.get_instance(st.session_state.username)

# Initialize session state
if "selected_user" not in st.session_state:
    st.session_state.selected_user = None
if "message_count" not in st.session_state:
    st.session_state.message_count = {}

def main():
    service = setup()
    discovery = service.discovery

    with st.sidebar:
        st.markdown("Find a friend to chat with!!!")

    # Auto-refresh only when in a chat (every 2 seconds)
    if st.session_state.selected_user:
        st_autorefresh(interval=2000, key="chat_refresh")

    # Main container: Two columns side by side
    col1, col2 = st.columns([3, 7], gap="small")

    # ---- LEFT SIDEBAR ----
    with col1:
        st.subheader("Online Users 🦖🦖🦖", divider=True)
        search_query = st.text_input("Search users...", 
                                   key="user_search",
                                   placeholder="Search users...",
                                   label_visibility="collapsed")
        
        peers_dict = discovery.list_peers()
        peers = list(peers_dict.keys())
        
        if search_query:
            peers = [p for p in peers if search_query.lower() in p.lower()]

        if peers:
            for user in peers:
                if st.button(user, key=f"user_{user}", use_container_width=True):
                    if st.session_state.selected_user == user:
                        st.session_state.selected_user = None
                    else:
                        st.session_state.selected_user = user
                        # Initialize message count for this user
                        messages = discovery.list_messages(peer=user)
                        st.session_state.message_count[user] = len(messages) if messages else 0
                    st.rerun()
        else:
            st.info("No online users found")

    # ---- RIGHT CHAT AREA ----
    with col2:
        st.subheader("Conversation 💭💭💭", divider=True)

        if st.session_state.selected_user:
            current_user = st.session_state.selected_user
            # Header with exit button
            header_col1, header_col2 = st.columns([4, 1])
            with header_col1:
                st.markdown(f"{current_user} 💬 ")
            with header_col2:
                if st.button("Exit Chat", key="exit_chat"):
                    st.session_state.selected_user = None
                    st.rerun()
            
            st.divider()
            
            # Get current messages
            messages = discovery.list_messages(peer=current_user)
            current_count = len(messages) if messages else 0
            
            # Check for new messages and update if needed
            if current_user in st.session_state.message_count:
                if current_count > st.session_state.message_count[current_user]:
                    st.session_state.message_count[current_user] = current_count
            else:
                st.session_state.message_count[current_user] = current_count

            # Message display
            if messages:
                for msg in messages:
                    formatted_time = (datetime.strptime(msg.timestamp, "%Y-%m-%d %H:%M:%S.%f")
                                      .strftime("%Y-%m-%d %H:%M")
                                      if isinstance(msg.timestamp, str) else 
                                      msg.timestamp.strftime("%Y-%m-%d %H:%M"))
                    if msg.sender == current_user:
                        st.markdown(
                            f"""<div class="message incoming">
                                {msg.content}
                                <div class="timestamp">{"🦖 " + msg.sender + " 🦖"} • {formatted_time}</div>
                            </div>""",
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f"""<div class="message outgoing">
                                {msg.content}
                                <div class="timestamp">🧑‍💻 You 🧑‍💻 • {formatted_time}</div>
                            </div>""",
                            unsafe_allow_html=True
                        )
            else:
                st.info("No messages yet")
            
            # Message input
            prompt = st.chat_input("Type a message...")
            if prompt:
                discovery.send_message(
                    recipient=current_user,
                    title="Chat",
                    content=prompt
                )
                # Update message count
                messages = discovery.list_messages(peer=current_user)
                st.session_state.message_count[current_user] = len(messages) if messages else 0
                st.rerun()
        else:
            st.info("Select a user to start chatting")

if __name__ == "__main__":
    main()