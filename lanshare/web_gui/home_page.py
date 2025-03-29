import streamlit as st

# Main page content
st.markdown("# Main page 🎈")
st.sidebar.markdown("# Main page 🎈")
st.write(f"Username: {st.session_state["username"]}")