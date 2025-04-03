import streamlit as st
from lanshare.web_gui.service import LANSharingService
from pathlib import Path
from datetime import datetime
import time
import os 
from streamlit_autorefresh import st_autorefresh

# Initialize session state
if 'selected_resource' not in st.session_state:
    st.session_state.selected_resource = None
    
# Add debug toggle to session state
if 'show_debug' not in st.session_state:
    st.session_state.show_debug = False

@st.cache_resource
def setup():
    return LANSharingService.get_instance(st.session_state.username)


def format_timestamp(timestamp):
    """Format timestamp for display"""
    if isinstance(timestamp, str):
        return datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M")
    elif isinstance(timestamp, datetime):
        return timestamp.strftime("%Y-%m-%d %H:%M")
    return timestamp

def main():
    service = setup()
    if not service:
        st.error("Service not initialized. Please launch from main app.")
        st.stop()

    st_autorefresh(interval=5000, key="file_sharing_refresh")

    with st.sidebar:
        st.markdown("Find a file or directory, share it with your friends!!!")
        if st.button("🔄 Sync Shared Files"):
            st.rerun()
        
        # Add a debug toggle to help troubleshoot
        st.session_state.show_debug = st.checkbox("Show debug info", value=st.session_state.show_debug)

    manager = service.file_share_manager
    discovery = service.discovery

    st.markdown("# 🔄 Shared Resources")

    # Get all resources: both shared and received
    all_resources = []
    
    # Add resources you share with others
    owned_resources = list(manager.shared_resources.values())
    all_resources.extend(owned_resources)
    
    # Add resources others share with you
    received_resources = list(manager.received_resources.values())
    all_resources.extend(received_resources)
    
    # Sort by timestamp (newest first)
    all_resources = sorted(all_resources, key=lambda r: r.timestamp, reverse=True)
    
    # Display debug info if enabled
    if st.session_state.show_debug:
        st.write("---")
        st.subheader("Debug Information")
        st.write(f"**Username:** {service.username}")
        st.write(f"**Number of shared resources:** {len(owned_resources)}")
        st.write(f"**Number of received resources:** {len(received_resources)}")
        st.write(f"**Total resources:** {len(all_resources)}")
        
        # Show peers
        peers = discovery.list_peers()
        st.write(f"**Active peers:** {len(peers)}")
        for username, peer in peers.items():
            st.write(f"- {username} ({peer.address})")
        
        # Show received resources details
        if received_resources:
            st.write("**Received resources:**")
            for r in received_resources:
                st.write(f"- ID: {r.id[:8]}... | From: {r.owner} | Name: {Path(r.path).name}")
        else:
            st.write("**No received resources**")
        st.write("---")

    # Display table with live data
    cols = st.columns([1, 2, 1, 1, 1, 1, 1])
    headers = ["Type", "Name", "Owner", "Access", "Shared On", "Last Modified", "Actions"]
    for col, header in zip(cols, headers):
        col.write(f"**{header}**")

    for resource in all_resources:
        cols = st.columns([1, 2, 1, 1, 1, 1, 1])

        try:
            filename = Path(resource.path).name
        except (AttributeError, TypeError):
            filename = str(resource.path)

        access = "Everyone" if resource.shared_to_all else f"{len(resource.allowed_users)} users"
        
        # Highlight if resource is owned by you
        is_own = resource.owner == service.username
        name_style = "" if is_own else "color: blue;"

        with cols[0]: 
            st.write("📁" if resource.is_directory else "📄")
        with cols[1]:
            if st.button(filename, key=f"btn_{resource.id}"):
                st.session_state.selected_resource = resource
        with cols[2]: 
            if is_own:
                st.write("You")
            else:
                st.write(resource.owner)
        with cols[3]: st.write(access)
        with cols[4]: st.write(format_timestamp(resource.timestamp))
        with cols[5]: 
            try:
                st.write(time.strftime("%Y-%m-%d %H:%M", time.localtime(resource.modified_time)))
            except:
                st.write("Unknown")
        with cols[6]:
            if resource.owner == service.username:
                if st.button("❌", key=f"remove_{resource.id}"):
                    try:
                        # Instead of deleting, just disable share_to_all
                        if manager.set_share_to_all(resource.id, False):
                            # Also remove all individual access
                            for user in list(resource.allowed_users):
                                manager.update_resource_access(resource.id, user, add=False)
                            
                            st.success(f"Access revoked for all users to {filename}")

                            del manager.shared_resources[resource.id]
                            manager._remove_shared_resource(resource)
                            st.rerun()
                        else:
                            st.error("Failed to revoke access")
                            
                    except Exception as e:
                        st.error(f"Error removing resource: {str(e)}")
    st.markdown("---")

    st.subheader("Add Resources to Share", divider=True)
    uploaded_file = st.file_uploader("Select a file to share:", type=["txt", "pdf", "png", "jpg", "docx"])
    folder_path = st.text_input("Or enter folder path to share:", placeholder="e.g., /Documents/Project")

    if st.button("Share Resource"):
        try:
            if uploaded_file:
                temp_dir = Path("temp_uploads")
                temp_dir.mkdir(exist_ok=True)
                temp_path = temp_dir / uploaded_file.name
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                resource = manager.share_resource(str(temp_path))
                if resource:
                    st.success(f"Successfully shared: {uploaded_file.name}")
                    os.remove(temp_path)
                    st.rerun()
                else:
                    st.error("Failed to share file")

            elif folder_path:
                folder_path = Path(folder_path)
                if not folder_path.exists():
                    st.error("Folder path does not exist")
                else:
                    resource = manager.share_resource(str(folder_path), is_directory=True)
                    if resource:
                        st.success(f"Successfully shared folder: {folder_path}")
                        st.rerun()
                    else:
                        st.error("Failed to share folder")
            else:
                st.warning("Please select a file or enter a folder path")
        except Exception as e:
            st.error(f"Error sharing resource: {str(e)}")

    if (st.session_state.selected_resource and 
        st.session_state.selected_resource.owner == service.username and
        st.session_state.selected_resource.id in manager.shared_resources):
        
        resource = st.session_state.selected_resource
        st.markdown("---")
        st.subheader(f"Manage Access: {Path(resource.path).name}", divider=True)

        st.write(f"**Owner:** {resource.owner}")
        st.write(f"**Current Access:** {'Everyone' if resource.shared_to_all else 'Restricted'}")

        new_global_access = st.toggle(
            "Share with everyone",
            value=resource.shared_to_all,
            key=f"global_{resource.id}"
        )

        if new_global_access != resource.shared_to_all:
            if manager.set_share_to_all(resource.id, new_global_access):
                st.success("Access updated successfully!")
                st.rerun()
            else:
                st.error("Failed to update access")

        if not new_global_access:
            st.subheader("Manage Individual Access", divider=True)

            new_user = st.text_input("Add user access:", placeholder="Enter username...")
            if st.button("Grant Access") and new_user:
                if manager.update_resource_access(resource.id, new_user, add=True):
                    st.success(f"Access granted to {new_user}")
                    st.rerun()
                else:
                    st.error("Failed to grant access")

            if resource.allowed_users:
                user_to_remove = st.selectbox(
                    "Remove user access:",
                    options=list(resource.allowed_users)
                )
                if st.button("Revoke Access"):
                    if manager.update_resource_access(resource.id, user_to_remove, add=False):
                        st.success(f"Access revoked for {user_to_remove}")
                        st.rerun()
                    else:
                        st.error("Failed to revoke access")

if __name__ == "__main__":
    main()