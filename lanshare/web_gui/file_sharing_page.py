import streamlit as st
import pandas as pd

# Title
st.markdown("<h2 style='color: #E4E4E4;'>Shared Resources</h2>", unsafe_allow_html=True)

# Table data
data = {
    "Type": ["File", "File"],
    "Name": ["text.txt", "text2.txt"],
    "Owner": ["username", "username"],
    "Access": ["peername", "peername"],
    "Shared On": ["2024/03/02", "2024/03/03"],
    "Last Modified": ["2024/03/10", "2024/03/10"]
}
df = pd.DataFrame(data)

# Display the table
st.dataframe(df)

st.markdown("---")

# Form-like inputs
st.subheader("Manage Shared Resources")


new_resource = st.text_input("Add resource:")
add_access = st.text_input("Add user access:")
remove_access = st.text_input("Remove user access:")
share_everyone = st.toggle("Share with everyone")

# Button to confirm changes
if st.button("Apply Changes"):
    st.success("Changes have been applied (this is just a demo).")
