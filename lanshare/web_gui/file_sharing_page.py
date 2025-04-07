import streamlit as st
from lanshare.web_gui.service import LANSharingService
from pathlib import Path
from datetime import datetime
import time
import os 
import json
from streamlit_autorefresh import st_autorefresh

# Initialize session state
if 'selected_resource' not in st.session_state:
    st.session_state.selected_resource = None
    
# Add debug toggle to session state
if 'show_debug' not in st.session_state:
    st.session_state.show_debug = False
    
# Add force refresh counter to trigger full refreshes
if 'refresh_counter' not in st.session_state:
    st.session_state.refresh_counter = 0
    
# Add folder path input value storage
if 'folder_path' not in st.session_state:
    st.session_state.folder_path = ""

# This will be used to force a new file uploader
if 'upload_key' not in st.session_state:
    st.session_state.upload_key = 0


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


def verify_received_files(manager):
    """Verify that received files still exist on disk and in received_resources."""
    resources_to_remove = []
    
    # Check if files actually exist in the shared directory
    for resource_id, resource in manager.received_resources.items():
        if resource.owner != manager.username:  # Only check resources owned by others
            target_path = manager.share_dir / resource.owner / Path(resource.path).name
            if not target_path.exists():
                # File doesn't exist on disk
                resources_to_remove.append(resource_id)
    
    # Remove invalid resources
    for resource_id in resources_to_remove:
        if resource_id in manager.received_resources:
            resource = manager.received_resources[resource_id]
            del manager.received_resources[resource_id]
            # Also remove from downloaded resources
            if resource_id in manager.downloaded_resources:
                manager.downloaded_resources.remove(resource_id)
    
    # Save updated resources
    if resources_to_remove:
        manager._save_resources()
        return len(resources_to_remove)
    
    return 0


def share_path(manager, path):
    """Share a file or directory.
    
    Args:
        manager: The file share manager instance
        path: Path to the file or directory.
    Returns:
        bool: True if shared successfully, False otherwise
    """
    try:
        # Expand user paths like ~ and ~user
        path = os.path.expanduser(path)
        
        if not os.path.exists(path):
            st.error(f"Path not found: {path}")
            return False

        resource = manager.share_resource(str(path))
        
        if resource:
            resource_type = "folder" if os.path.isdir(path) else "file"
            st.success(f"Successfully shared {resource_type}: {path}")
            return True
        else:
            st.error(f"Failed to share path: {path}")
            return False
    except Exception as e:
        st.error(f"Error sharing path: {str(e)}")
        return False

def main():
    service = setup()
    if not service:
        st.error("Service not initialized. Please launch from main app.")
        st.stop()

    # Shorter refresh interval for more responsiveness
    st_autorefresh(interval=5000, key=f"file_sharing_refresh_{st.session_state.refresh_counter}")

    with st.sidebar:
        st.markdown("Find a file or directory and share it with your friends!!!")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Sync Files"):
                # Force a full reload of resources by incrementing the counter
                st.session_state.refresh_counter += 1
                # Also reload resource files from disk
                service.file_share_manager._load_resources()
                # Verify received files are valid
                removed = verify_received_files(service.file_share_manager)
                if removed > 0:
                    st.success(f"Removed {removed} invalid resources")
                st.rerun()
        
        with col2:
            if st.button("🔍 Re-scan"):
                # Rebroadcast presence to ensure peers know you exist
                try:
                    packet = {
                        'type': 'announcement',
                        'username': service.username,
                        'timestamp': datetime.now().isoformat()
                    }
                    service.discovery.udp_socket.sendto(
                        json.dumps(packet).encode(),
                        ('<broadcast>', service.discovery.config.port)
                    )
                    # Re-announce all resources
                    for resource in service.file_share_manager.shared_resources.values():
                        service.file_share_manager._announce_resource(resource)
                    st.success("Re-announced presence and resources")
                except Exception as e:
                    st.error(f"Error re-announcing: {e}")
                
                st.session_state.refresh_counter += 1
                st.rerun()
        
        # Add a debug toggle to help troubleshoot
        st.session_state.show_debug = st.toggle("Show debug info", value=st.session_state.show_debug)

    manager = service.file_share_manager
    discovery = service.discovery

    st.markdown("# 🔄 Shared Resources")

    # Force a reload of resources from disk before displaying
    try:
        manager._load_resources()
        # Verify received files
        verify_received_files(manager)
    except Exception as e:
        if st.session_state.show_debug:
            st.error(f"Error loading resources: {str(e)}")

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
        
        # Show file sharing directory structure
        st.write(f"**Share directory:** {manager.share_dir}")
        if manager.share_dir.exists():
            for p in manager.share_dir.glob("*"):
                if p.is_dir():
                    st.write(f"- Directory: {p.name} (contains {len(list(p.glob('*')))} items)")
                else:
                    st.write(f"- File: {p.name}")
        
        # Show resource file
        resource_file = manager.user_share_dir / '.shared_resources.json'
        if resource_file.exists():
            st.write(f"**Resource file exists:** {resource_file}")
            try:
                with open(resource_file, 'r') as f:
                    data = json.load(f)
                    st.write(f"Shared count in file: {len(data.get('shared', []))}")
                    st.write(f"Received count in file: {len(data.get('received', []))}")
            except Exception as e:
                st.write(f"Error reading resource file: {e}")
        else:
            st.write(f"**Resource file not found:** {resource_file}")
            
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

    # Check if no resources to display
    if not all_resources:
        st.info("No shared resources available. Share a file or folder to get started!")

    for resource in all_resources:
        cols = st.columns([1, 2, 1, 1, 1, 1, 1])

        try:
            filename = Path(resource.path).name
        except (AttributeError, TypeError):
            filename = str(resource.path)

        access = "Everyone" if resource.shared_to_all else f"{len(resource.allowed_users)} users"
        
        # Highlight if resource is owned by you
        is_own = resource.owner == service.username
        owner_display = "You" if is_own else resource.owner

        with cols[0]: 
            st.write("📁" if resource.is_directory else "📄")
        with cols[1]:
            # Show blue text for files shared with you
            if is_own:
                if st.button(filename, key=f"btn_{resource.id}"):
                    st.session_state.selected_resource = resource
            else:
                st.markdown(f"<span style='color: blue;'>{filename}</span>", unsafe_allow_html=True)
                if st.button("Select", key=f"btn_{resource.id}"):
                    st.session_state.selected_resource = resource
        with cols[2]: st.write(owner_display)
        with cols[3]: st.write(access)
        with cols[4]: st.write(format_timestamp(resource.timestamp))
        with cols[5]: 
            try:
                st.write(time.strftime("%Y-%m-%d %H:%M", time.localtime(resource.modified_time)))
            except:
                st.write("Unknown")
        with cols[6]:
            if is_own:
                # For your own resources, show remove button
                if st.button("❌", key=f"remove_{resource.id}"):
                    try:
                        # First disable sharing with everyone
                        manager.set_share_to_all(resource.id, False)
                        
                        # Remove all individual access permissions
                        for user in list(resource.allowed_users):
                            manager.update_resource_access(resource.id, user, add=False)
                        
                        # Delete from shared_resources dictionary
                        if resource.id in manager.shared_resources:
                            del manager.shared_resources[resource.id]
                        
                        # Clean up the actual file
                        manager._remove_shared_resource(resource)
                        
                        # Save changes
                        manager._save_resources()
                        
                        st.success(f"Successfully removed: {filename}")
                        st.session_state.refresh_counter += 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error removing resource: {str(e)}")
            else:
                # For resources shared with you, show status indicator
                st.write("✓")
    
    st.markdown("---")

    st.subheader("Add Resources to Share 🤝🤝🤝", divider=True)
    # Dynamic key to force file uploader to reset
    uploader_key = f"file_uploader_{st.session_state.upload_key}"
    text_input_key = f"text_input_{st.session_state.upload_key}"
    uploaded_file = st.file_uploader("Select a file to share:", 
                                type=["txt", "pdf", "png", "jpg", "docx"],
                                key=uploader_key)
    folder_path = st.text_input(
        "Or enter folder path to share:", 
        value=st.session_state.folder_path,
        placeholder="e.g., /Documents/Project", key=text_input_key)

    if st.button("Share Resource"):
        shared_successfully = False
        
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
                    shared_successfully = True
                    
                else:
                    st.error("Failed to share file")

            elif folder_path:
                if share_path(manager, folder_path):
                    shared_successfully = True
            else:
                st.warning("Please select a file or enter a folder path")
                
            # Clear inputs if sharing was successful
            if shared_successfully:
                # Clear the folder path input
                st.session_state.folder_path = ""
                # Force a refresh to clear the file uploader
                st.session_state.upload_key += 1
                st.rerun()
                
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