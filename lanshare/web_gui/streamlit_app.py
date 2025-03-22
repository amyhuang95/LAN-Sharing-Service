import streamlit as st

# Define the pages
main_page = st.Page("home_page.py", title="Home Page", icon="🌐")
message_page = st.Page("message_page.py", title="Message", icon="🗣️")
file_sharing_page = st.Page("file_sharing_page.py", title="Share Files", icon="🤝")
clipboard_page = st.Page("clipboard_page.py", title="Clipboard", icon="📋")

# Set up navigation
pg = st.navigation([main_page, message_page, file_sharing_page, clipboard_page])

# Run the selected page
pg.run()
