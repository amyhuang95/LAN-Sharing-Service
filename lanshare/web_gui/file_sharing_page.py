import streamlit as st
import pandas as pd

st.markdown("## Shared Resources")

# Sample table data
data = [
    {
        "Type": "File",
        "Name": "text.txt",
        "Owner": "username",
        "Access": "peername",
        "Shared On": "2024/03/02",
        "Last Modified": "2024/03/10",
    },
    {
        "Type": "File",
        "Name": "text2.txt",
        "Owner": "username",
        "Access": "peername",
        "Shared On": "2024/03/03",
        "Last Modified": "2024/03/10",
    },
]
df = pd.DataFrame(data)

# Display the table
# st.table(df)  # or st.dataframe(df)
st.table(df)

st.markdown("---")

# 3. Form-like inputs
st.subheader("Manage Shared Resources")

new_resource = st.text_input("Add resources to share:")
add_access = st.text_input("Add user access:")
remove_access = st.text_input("Remove user access:")
share_everyone = st.checkbox("Share with everyone")

if st.button("Apply Changes"):
    st.success("Changes have been applied (this is just a demo).")
