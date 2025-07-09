import streamlit as st
import geemap.foliumap as gf
import ee
from _work_flow_gen import generate_workflow
from python_sandbox import execute_workflow 
import streamlit.components.v1 as components


# Initialize GEE
try:
    ee.Authenticate()
    ee.Initialize(project="558258839591")
except Exception as e:
    st.error(f"Error initializing Google Earth Engine: {e}")
    st.stop()

st.set_page_config(layout="wide")
st.title("🛰️ Map Man ")

# Create layout with 2 columns
col1, col2 = st.columns([1, 2])

with col1:
    st.header("Input")
    user_input = st.text_area("Enter your query", height=100, key="user_input")

    st.header("Chain of Thought")
    thoughts = []
    workflow = None

    if user_input:
        try:
            workflow = generate_workflow(user_input)
            # print(workflow)  # Debugging: print the workflow structure
            thoughts = workflow.get("thoughts", [])
        except Exception as e:
            st.error(f"Error generating workflow: {e}")

    # Display each thought as a box
    if thoughts:
        st.subheader("Reasoning Steps")
        for t in thoughts:
            st.markdown(
                f"""
                <div style="
                padding: 16px 20px;
                margin-bottom: 16px;
                background-color: #ffffff;
                border-left: 6px solid #4a90e2;
                border-radius: 8px;
                box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                font-size: 15px;
                color: #333;
                ">
                {t}
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.info('Ask query like "Chennai map with flood hazard?" or anything :)')

with col2:
    st.header("GEE Map Display")

    if user_input and workflow:
        with st.spinner("Generating map..."):
            try:
                wf = execute_workflow(workflow)
                st.success("Map updated with all visual layers!")

                # 🔍 Try to find the step ID for 'Final_land_cover'
                base_map_step = None
                for step in workflow["steps"]:
                    if step["function"] == "Final_land_cover":
                        base_map_step = step["id"]
                        break

                # 🗺️ Use that map as the base if found, else use a blank map
                if base_map_step and base_map_step in wf:
                    base_map = wf[base_map_step]
                else:
                    base_map = gf.Map(center=[20.5937, 78.9629], zoom=4)  # Default base map centered on India

                # Add all other visual layers except the base map step
                for step_id, content in wf.items():
                    if step_id == base_map_step:
                        continue
                    if isinstance(content, gf.Map):
                    
                        bounds = content.get_bounds()
                        for key, layer in content._children.items():
                            if "OpenStreetMap" in str(layer) or "LayerControl" in str(type(layer)):
                                continue
                            base_map.add_child(layer)



                # ✅ Show the final map
                base_map.to_streamlit(height=600, use_container_width=True)

            except Exception as e:
                st.error(f"Execution error: {e}")

    else:
        # 👇 This shows an initial empty map if no user input yet
        default_map = gf.Map(center=[20.5937, 78.9629], zoom=4)
        default_map.to_streamlit(height=600, use_container_width=True)
