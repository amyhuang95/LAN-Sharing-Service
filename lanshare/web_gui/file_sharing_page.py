import streamlit as st
from lanshare.web_gui.service import LANSharingService

# Initialize session state for selected file
if 'selected_file' not in st.session_state:
    st.session_state.selected_file = None

@st.cache_resource
def setup():
    return LANSharingService.get_instance(st.session_state.username)


def main():
    service = setup()
    file_share_manager = service.file_share_manager
    st.markdown("# Shared Resources")

    # # Table data with clickable files
    shared_resources = [
        {"Type": "File", "Name": "text.txt", "Owner": "username", 
        "Access": "peername", "Shared On": "2024/03/02", "Last Modified": "2024/01/02"},
        {"Type": "File", "Name": "document.pdf", "Owner": "user2", 
        "Access": "team", "Shared On": "2024/03/01", "Last Modified": "2024/02/15"},
        {"Type": "Folder", "Name": "Project Files", "Owner": "user3",
        "Access": "private", "Shared On": "2024/02/28", "Last Modified": "2024/03/10"}
    ]

    # Display table with clickable elements
    cols = st.columns([1, 2, 1, 1, 1, 1])  # Adjust column widths as needed
    with cols[0]: st.write("**Type**")
    with cols[1]: st.write("**Name**")
    with cols[2]: st.write("**Owner**")
    with cols[3]: st.write("**Access**")
    with cols[4]: st.write("**Shared On**")
    with cols[5]: st.write("**Last Modified**")

    for item in shared_resources:
        cols = st.columns([1, 2, 1, 1, 1, 1])
        with cols[0]: st.write(item["Type"])
        with cols[1]: 
            if st.button(item["Name"], key=f"btn_{item['Name']}"):
                st.session_state.selected_file = item
        with cols[2]: st.write(item["Owner"])
        with cols[3]: st.write(item["Access"])
        with cols[4]: st.write(item["Shared On"])
        with cols[5]: st.write(item["Last Modified"])

    st.markdown("---")

    # --- Add Resources Section ---
    st.subheader("Add Resources to Share")
    uploaded_file = st.file_uploader("Select a file to share:", type=["txt", "pdf", "png", "jpg"])
    folder_path = st.text_input("Or enter folder path to share:", placeholder="e.g., /Documents/Project")

    if st.button("Share Resource"):
        if uploaded_file:
            st.success(f"Shared file: {uploaded_file.name}")
        elif folder_path:
            st.success(f"Shared folder: {folder_path}")
        else:
            st.warning("Please select a file or enter a folder path")

    # --- Manage Access Section (only shown when file is selected) ---
    if st.session_state.selected_file:
        st.markdown("---")
        st.subheader(f"Manage Access: {st.session_state.selected_file['Name']}")
        
        # Display current access info
        st.write(f"**Current Access:** {st.session_state.selected_file['Access']}")
        st.write(f"**Owner:** {st.session_state.selected_file['Owner']}")
        
        # Access management controls
        new_user = st.text_input("Add user access:", placeholder="Enter username...")
        if st.button("Grant Access") and new_user:
            st.success(f"Access granted to {new_user} for {st.session_state.selected_file['Name']}")
        
        remove_user = st.text_input("Remove user access:", placeholder="Enter username...")
        if st.button("Revoke Access") and remove_user:
            st.success(f"Access revoked for {remove_user} from {st.session_state.selected_file['Name']}")
        
        # Toggle for global access
        share_with_everyone = st.toggle("Share with everyone", value=False)
        if share_with_everyone:
            st.info("All users can now access this resource.")
        else:
            st.info("Access is restricted to selected users.")

if __name__ == "__main__":
    main()
