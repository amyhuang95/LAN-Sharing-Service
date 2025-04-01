import streamlit as st
from lanshare.web_gui.service import LANSharingService
from pathlib import Path
from datetime import datetime
import time
from streamlit_autorefresh import st_autorefresh


# Initialize session state
if 'selected_resource' not in st.session_state:
    st.session_state.selected_resource = None

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
        st.markdown("Find a file/directory, share it with your friends!!!")
        
    manager = service.file_share_manager
    
    st.markdown("# Shared Resources")

    # Get live data from FileShareManager
    shared_resources = manager.list_shared_resources()
    
    # Display table with live data
    cols = st.columns([1, 2, 1, 1, 1, 1])
    headers = ["Type", "Name", "Owner", "Access", "Shared On", "Last Modified"]
    for col, header in zip(cols, headers):
        col.write(f"**{header}**")

    for resource in shared_resources:
        cols = st.columns([1, 2, 1, 1, 1, 1])
        
        # Get filename safely
        try:
            filename = Path(resource.path).name
        except (AttributeError, TypeError):
            filename = str(resource.path)
        
        # Determine access level
        access = "Everyone" if resource.shared_to_all else f"{len(resource.allowed_users)} users"
        
        with cols[0]: 
            st.write("📁" if resource.is_directory else "📄")
        with cols[1]:
            if st.button(filename, key=f"btn_{resource.id}"):
                st.session_state.selected_resource = resource
        with cols[2]: st.write(resource.owner)
        with cols[3]: st.write(access)
        with cols[4]: st.write(format_timestamp(resource.timestamp))
        with cols[5]: 
            st.write(time.strftime("%Y-%m-%d %H:%M", time.localtime(resource.modified_time)))

    st.markdown("---")

    # Add Resources Section
    st.subheader("Add Resources to Share")
    uploaded_file = st.file_uploader("Select a file to share:", type=["txt", "pdf", "png", "jpg", "docx"])
    folder_path = st.text_input("Or enter folder path to share:", placeholder="e.g., /Documents/Project")

    if st.button("Share Resource"):
        try:
            if uploaded_file:
                # Create temp directory if it doesn't exist
                temp_dir = Path("temp_uploads")
                temp_dir.mkdir(exist_ok=True)
                temp_path = temp_dir / uploaded_file.name
                
                # Save uploaded file
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Share the file
                resource = manager.share_resource(str(temp_path))
                if resource:
                    st.success(f"Successfully shared: {uploaded_file.name}")
                    # Force refresh of resources
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

    # Manage Access Section
    if st.session_state.selected_resource:
        resource = st.session_state.selected_resource
        st.markdown("---")
        st.subheader(f"Manage Access: {Path(resource.path).name}")
        
        st.write(f"**Owner:** {resource.owner}")
        st.write(f"**Current Access:** {'Everyone' if resource.shared_to_all else 'Restricted'}")
        
        # Toggle global access
        new_global_access = st.toggle(
            "Share with everyone",
            value=resource.shared_to_all,
            key=f"global_{resource.id}"
        )
        
        if new_global_access != resource.shared_to_all:
            if manager.set_share_to_all(resource.id, new_global_access):
                st.success("Access updated successfully!")
                resource.shared_to_all = new_global_access
                st.rerun()
            else:
                st.error("Failed to update access")
        
        # User-specific access
        if not new_global_access:
            st.markdown("### Manage Individual Access")
            
            # Add user access
            new_user = st.text_input("Add user access:", placeholder="Enter username...")
            if st.button("Grant Access") and new_user:
                if manager.update_resource_access(resource.id, new_user, add=True):
                    st.success(f"Access granted to {new_user}")
                    resource.add_user(new_user)
                    st.rerun()
                else:
                    st.error("Failed to grant access")
            
            # Remove user access
            if resource.allowed_users:
                user_to_remove = st.selectbox(
                    "Remove user access:",
                    options=list(resource.allowed_users)
                )
                if st.button("Revoke Access"):
                    if manager.update_resource_access(resource.id, user_to_remove, add=False):
                        st.success(f"Access revoked for {user_to_remove}")
                        resource.remove_user(user_to_remove)
                        st.rerun()
                    else:
                        st.error("Failed to revoke access")

if __name__ == "__main__":
    main()