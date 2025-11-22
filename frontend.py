import streamlit as st
import asyncio
import os
import re
import time
import mimetypes
import glob

# --- Google ADK & GenAI Imports ---
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.genai.errors import ServerError

# --- Import your agent ---
from agent import root_agent

# ==========================================
# 1. App Configuration
# ==========================================
st.set_page_config(
    page_title="AI Home Renovation Planner", 
    layout="wide",
    page_icon="🏠"
)

# Main header with better styling
st.title("🏠 AI Home Renovation Planner")
st.markdown("**Chat with your AI architect. Upload multiple photos of your room and inspiration images to get started!**")

# Quick tips
with st.expander("💡 Quick Tips", expanded=False):
    st.markdown("""
    - **Upload multiple images**: Select multiple files at once or upload them one by one
    - **Categorize images**: Mark images as 'Current Room', 'Inspiration', or 'Reference'
    - **Compare spaces**: Upload both current room photos and inspiration images for better analysis
    - **Image gallery**: View and manage all uploaded images in the gallery tab
    """)

# Constants
APP_NAME = "renovation_planner"
USER_ID = "user_frontend"
SESSION_ID = "session_frontend_01"

# Initialize Session Service
if "session_service" not in st.session_state:
    st.session_state.session_service = InMemorySessionService()

# Shared state helpers
if "attach_uploaded_images" not in st.session_state:
    st.session_state.attach_uploaded_images = True
if "attach_last_rendering" not in st.session_state:
    st.session_state.attach_last_rendering = False
if "last_generated_image" not in st.session_state:
    st.session_state.last_generated_image = None
if "last_generated_filename" not in st.session_state:
    st.session_state.last_generated_filename = None

# ==========================================
# 2. Sidebar: Image Upload & Management
# ==========================================
with st.sidebar:
    st.header("📁 Project Files")
    
    # Initialize image storage
    if 'uploaded_images' not in st.session_state:
        st.session_state.uploaded_images = []
    if 'image_categories' not in st.session_state:
        st.session_state.image_categories = {}  # filename -> category
    
    # Tab-based organization
    tab1, tab2 = st.tabs(["📤 Upload Images", "🖼️ Image Gallery"])
    
    with tab1:
        st.subheader("Upload Multiple Images")
        st.caption("Upload your current room photos and inspiration images")
        
        # Multiple file uploader
        uploaded_files = st.file_uploader(
            "Choose images to upload",
            type=['png', 'jpg', 'jpeg'],
            accept_multiple_files=True,
            help="You can upload multiple images at once. Categorize them after upload."
        )
        
        if uploaded_files:
            for uploaded_file in uploaded_files:
                # Check if already uploaded
                if uploaded_file.name not in [img['name'] for img in st.session_state.uploaded_images]:
                    # Save locally
                    save_path = os.path.join(os.getcwd(), uploaded_file.name)
                    with open(save_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Add to state
                    st.session_state.uploaded_images.append({
                        'name': uploaded_file.name,
                        'path': save_path,
                        'size': uploaded_file.size
                    })
                    
                    # Default category
                    st.session_state.image_categories[uploaded_file.name] = "current_room"
                    
                    # Save as artifact for editing capability
                    if 'image_artifacts' not in st.session_state:
                        st.session_state.image_artifacts = {}
                    st.session_state.image_artifacts[uploaded_file.name] = save_path
            
            st.success(f"✅ {len(uploaded_files)} image(s) uploaded successfully!")
        
        # Quick categorization section
        if st.session_state.uploaded_images:
            st.divider()
            st.subheader("📋 Categorize Images")
            st.caption("Mark images as current room or inspiration")
            
            for img_info in st.session_state.uploaded_images:
                img_name = img_info['name']
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.text(img_name[:30] + "..." if len(img_name) > 30 else img_name)
                
                with col2:
                    category = st.selectbox(
                        f"Type for {img_name[:15]}...",
                        ["current_room", "inspiration", "reference"],
                        index=["current_room", "inspiration", "reference"].index(
                            st.session_state.image_categories.get(img_name, "current_room")
                        ),
                        key=f"cat_{img_name}",
                        label_visibility="collapsed"
                    )
                    st.session_state.image_categories[img_name] = category
    
    with tab2:
        st.subheader("🖼️ Uploaded Images Gallery")
        
        if not st.session_state.uploaded_images:
            st.info("👆 Upload images in the 'Upload Images' tab")
        else:
            # Group by category
            current_room_imgs = [img for img in st.session_state.uploaded_images 
                               if st.session_state.image_categories.get(img['name']) == "current_room"]
            inspiration_imgs = [img for img in st.session_state.uploaded_images 
                              if st.session_state.image_categories.get(img['name']) == "inspiration"]
            reference_imgs = [img for img in st.session_state.uploaded_images 
                            if st.session_state.image_categories.get(img['name']) == "reference"]
            
            # Display by category
            if current_room_imgs:
                st.markdown("**🏠 Current Room Photos**")
                cols = st.columns(min(2, len(current_room_imgs)))
                for idx, img_info in enumerate(current_room_imgs):
                    with cols[idx % 2]:
                        if os.path.exists(img_info['path']):
                            st.image(img_info['path'], caption=img_info['name'], use_container_width=True)
                            if st.button("🗑️ Remove", key=f"remove_{img_info['name']}", use_container_width=True):
                                # Remove from state
                                st.session_state.uploaded_images = [img for img in st.session_state.uploaded_images 
                                                                  if img['name'] != img_info['name']]
                                if img_info['name'] in st.session_state.image_categories:
                                    del st.session_state.image_categories[img_info['name']]
                                # Optionally delete file
                                try:
                                    if os.path.exists(img_info['path']):
                                        os.remove(img_info['path'])
                                except:
                                    pass
                                st.rerun()
            
            if inspiration_imgs:
                st.markdown("**✨ Inspiration Images**")
                cols = st.columns(min(2, len(inspiration_imgs)))
                for idx, img_info in enumerate(inspiration_imgs):
                    with cols[idx % 2]:
                        if os.path.exists(img_info['path']):
                            st.image(img_info['path'], caption=img_info['name'], use_container_width=True)
                            if st.button("🗑️ Remove", key=f"remove_insp_{img_info['name']}", use_container_width=True):
                                st.session_state.uploaded_images = [img for img in st.session_state.uploaded_images 
                                                                  if img['name'] != img_info['name']]
                                if img_info['name'] in st.session_state.image_categories:
                                    del st.session_state.image_categories[img_info['name']]
                                try:
                                    if os.path.exists(img_info['path']):
                                        os.remove(img_info['path'])
                                except:
                                    pass
                                st.rerun()
            
            if reference_imgs:
                st.markdown("**📎 Reference Images**")
                cols = st.columns(min(2, len(reference_imgs)))
                for idx, img_info in enumerate(reference_imgs):
                    with cols[idx % 2]:
                        if os.path.exists(img_info['path']):
                            st.image(img_info['path'], caption=img_info['name'], use_container_width=True)
                            if st.button("🗑️ Remove", key=f"remove_ref_{img_info['name']}", use_container_width=True):
                                st.session_state.uploaded_images = [img for img in st.session_state.uploaded_images 
                                                                  if img['name'] != img_info['name']]
                                if img_info['name'] in st.session_state.image_categories:
                                    del st.session_state.image_categories[img_info['name']]
                                try:
                                    if os.path.exists(img_info['path']):
                                        os.remove(img_info['path'])
                                except:
                                    pass
                                st.rerun()
            
            # Clear all button
            if st.session_state.uploaded_images:
                st.divider()
                if st.button("🗑️ Clear All Images", use_container_width=True, type="secondary"):
                    # Delete all files
                    for img_info in st.session_state.uploaded_images:
                        try:
                            if os.path.exists(img_info['path']):
                                os.remove(img_info['path'])
                        except:
                            pass
                    st.session_state.uploaded_images = []
                    st.session_state.image_categories = {}
                    st.rerun()
    
    # Quick Actions Section
    st.divider()
    st.subheader("⚡ Quick Actions")
    
    if st.session_state.uploaded_images:
        st.session_state.attach_uploaded_images = st.checkbox(
            "Include uploaded reference photos in the next response",
            value=st.session_state.attach_uploaded_images,
            help="Keep this on when you want the AI to see your current room / inspiration images.",
        )
        
        # Show image summary
        current_count = len([img for img in st.session_state.uploaded_images 
                             if st.session_state.image_categories.get(img['name']) == "current_room"])
        insp_count = len([img for img in st.session_state.uploaded_images 
                         if st.session_state.image_categories.get(img['name']) == "inspiration"])
        
        summary_msg = []
        if current_count > 0:
            summary_msg.append(f"{current_count} current room")
        if insp_count > 0:
            summary_msg.append(f"{insp_count} inspiration")
        if summary_msg:
            st.info("📸 " + " | ".join(summary_msg))
    else:
        st.info("👆 Upload images to get started!")
    
    if st.session_state.last_generated_image:
        st.session_state.attach_last_rendering = st.checkbox(
            "Iterate on the last AI rendering",
            value=st.session_state.attach_last_rendering,
            help="Turn this on to edit the most recent AI-generated rendering.",
        )
        if st.session_state.last_generated_filename:
            st.caption(f"Last rendering: {st.session_state.last_generated_filename}")

# ==========================================
# 3. Chat Interface
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = []

# Enhanced header with stats
col1, col2, col3 = st.columns(3)
with col1:
    if st.session_state.uploaded_images:
        st.metric("📸 Images", len(st.session_state.uploaded_images))
with col2:
    current_room_count = len([img for img in st.session_state.uploaded_images 
                              if st.session_state.image_categories.get(img['name']) == "current_room"])
    if current_room_count > 0:
        st.metric("🏠 Current Room", current_room_count)
with col3:
    inspiration_count = len([img for img in st.session_state.uploaded_images 
                            if st.session_state.image_categories.get(img['name']) == "inspiration"])
    if inspiration_count > 0:
        st.metric("✨ Inspiration", inspiration_count)

st.divider()

# Render History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Display single image
        if "image_path" in msg:
            st.image(msg["image_path"], use_container_width=True)
        
        # Display multiple images if available
        if "image_paths" in msg:
            cols = st.columns(min(3, len(msg["image_paths"])))
            for idx, img_path in enumerate(msg["image_paths"]):
                with cols[idx % 3]:
                    if os.path.exists(img_path):
                        st.image(img_path, use_container_width=True)

# Handle Input
if prompt := st.chat_input("Describe your renovation ideas..."):
    
    # Display User Message with images
    user_msg_data = {"role": "user", "content": prompt}
    
    # Include uploaded images info in user message
    if st.session_state.uploaded_images:
        user_msg_data["uploaded_images"] = [img['name'] for img in st.session_state.uploaded_images]
        user_msg_data["image_categories"] = {img['name']: st.session_state.image_categories.get(img['name']) 
                                            for img in st.session_state.uploaded_images}
    
    st.session_state.messages.append(user_msg_data)
    
    with st.chat_message("user"):
        st.markdown(prompt)
        
        # Show preview of uploaded images in user message
        if st.session_state.uploaded_images:
            with st.expander(f"📎 {len(st.session_state.uploaded_images)} image(s) attached", expanded=False):
                cols = st.columns(min(3, len(st.session_state.uploaded_images)))
                for idx, img_info in enumerate(st.session_state.uploaded_images):
                    with cols[idx % 3]:
                        if os.path.exists(img_info['path']):
                            category = st.session_state.image_categories.get(img_info['name'], 'unknown')
                            st.image(img_info['path'], caption=f"{img_info['name']} ({category})", use_container_width=True)

    # 4. Run Agent
    with st.chat_message("assistant"):
        
        # Configuration
        MAX_RETRIES = 3
        RETRY_DELAY = 5
        final_response = ""
        error_occurred = False

        # Initialize Runner
        runner = Runner(
            agent=root_agent,
            session_service=st.session_state.session_service,
            app_name=APP_NAME
        )

        async def run_agent_conversation():
            # A. Ensure Session Exists
            current_session = await st.session_state.session_service.get_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
            )
            if not current_session:
                print("DEBUG: Creating new session...")
                await st.session_state.session_service.create_session(
                    app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
                )
            
            # B. Prepare Multimodal Content (Text + Multiple Images)
            content_parts = [types.Part(text=prompt)]
            
            # Attach uploaded references if enabled
            image_context = []
            if st.session_state.attach_uploaded_images and st.session_state.uploaded_images:
                attached_names = []
                for img_info in st.session_state.uploaded_images:
                    if not os.path.exists(img_info['path']):
                        continue
                    
                    mime_type, _ = mimetypes.guess_type(img_info['path'])
                    if not mime_type:
                        mime_type = "image/png"
                    
                    with open(img_info['path'], "rb") as img_f:
                        image_bytes = img_f.read()
                    
                    image_part = types.Part(
                        inline_data=types.Blob(
                            mime_type=mime_type,
                            data=image_bytes
                        )
                    )
                    content_parts.append(image_part)
                    attached_names.append(img_info['name'])
                    print(f"DEBUG: Attached uploaded image {img_info['name']} ({st.session_state.image_categories.get(img_info['name'], 'unknown')}) to prompt.")
                
                if attached_names:
                    image_context.append(f"Uploaded images ({len(attached_names)}): {', '.join(attached_names)}")
            
            # Attach last generated rendering if enabled
            if (
                st.session_state.attach_last_rendering
                and st.session_state.last_generated_image
                and os.path.exists(st.session_state.last_generated_image)
            ):
                mime_type, _ = mimetypes.guess_type(st.session_state.last_generated_image)
                if not mime_type:
                    mime_type = "image/png"
                
                with open(st.session_state.last_generated_image, "rb") as img_f:
                    rendering_bytes = img_f.read()
                
                rendering_part = types.Part(
                    inline_data=types.Blob(
                        mime_type=mime_type,
                        data=rendering_bytes
                    )
                )
                content_parts.append(rendering_part)
                filename = st.session_state.last_generated_filename or os.path.basename(st.session_state.last_generated_image)
                image_context.append(f"Last generated rendering: {filename}")
                print(f"DEBUG: Attached last rendering {filename} to prompt.")
            
            if image_context:
                content_parts[0].text += f"\n\n[System Note: {'; '.join(image_context)}]"

            # Create Message Object
            message_content = types.Content(role="user", parts=content_parts)

            # C. Stream Response
            text_accumulator = ""
            response_container = st.empty()
            
            # Status indicator for tools
            tool_status = st.status("🧠 AI Architect is thinking...", expanded=False)

            print("DEBUG: Starting Runner Loop...")
            
            async for event in runner.run_async(
                user_id=USER_ID,
                session_id=SESSION_ID,
                new_message=message_content
            ):
                # DEBUG: Uncomment the next line to see raw events in your console
                # print(f"EVENT -> author={event.author}, partial={event.partial}")

                # Surfacing any model errors immediately helps with debugging.
                if getattr(event, "error_message", None):
                    raise ServerError(event.error_message)

                content = getattr(event, "content", None)
                if not content or not content.parts:
                    continue

                for part in content.parts:
                    # Case 1: Stream plain text from the agent
                    if getattr(part, "text", None):
                        text_accumulator += part.text
                        response_container.markdown(text_accumulator + "▌")
                    
                    # Case 2: Tool call in progress
                    elif part.function_call:
                        func_name = part.function_call.name
                        tool_status.write(f"🛠️ Using tool: {func_name}...")
                        print(f"DEBUG: Tool Called -> {func_name}")
                    
                    # Case 3: Tool finished and returned a result
                    elif part.function_response:
                        func_name = part.function_response.name
                        tool_status.write(f"✅ Tool finished: {func_name}")

            tool_status.update(label="✅ Response Complete", state="complete", expanded=False)
            response_container.markdown(text_accumulator)
            return text_accumulator

        # --- EXECUTION WITH RETRY ---
        for attempt in range(MAX_RETRIES):
            try:
                final_response = asyncio.run(run_agent_conversation())
                error_occurred = False
                break 
            except Exception as e:
                error_str = str(e)
                print(f"ERROR ENCOUNTERED: {error_str}") # Print to console
                
                # Catch 503 Overloaded or 429 Rate Limit
                if "503" in error_str or "overloaded" in error_str.lower():
                    if attempt < MAX_RETRIES - 1:
                        wait_time = RETRY_DELAY * (attempt + 1)
                        st.warning(f"⚠️ Server busy. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        st.error("❌ Google AI servers are currently overloaded. Please try again later.")
                        error_occurred = True
                else:
                    # Show actual error in UI
                    st.error(f"An error occurred: {e}")
                    error_occurred = True
                    break

        # 5. Detect & Display Generated Image
        if not error_occurred and final_response:
            found_image = None
            
            # Method 1: Look for the filename pattern **image.png** used in tools.py
            match = re.search(r"\*\*([^\*]+\.(png|jpg|jpeg))\*\*", final_response)
            if match:
                image_filename = match.group(1).strip()
                if os.path.exists(image_filename):
                    found_image = image_filename
            
            # Method 2: Look for "Saved as:" pattern
            if not found_image:
                match = re.search(r"Saved as:\s*\*\*([^\*]+\.(png|jpg|jpeg))\*\*", final_response, re.IGNORECASE)
                if match:
                    image_filename = match.group(1).strip()
                    if os.path.exists(image_filename):
                        found_image = image_filename
            
            # Method 3: Look for any .png/.jpg/.jpeg filename in the response
            if not found_image:
                match = re.search(r"([a-zA-Z0-9_\-]+\.(png|jpg|jpeg))", final_response)
                if match:
                    image_filename = match.group(1)
                    if os.path.exists(image_filename):
                        found_image = image_filename
            
            # Method 4: Check for recently created image files in current directory
            if not found_image:
                try:
                    current_dir = os.getcwd()
                    image_files = []
                    for ext in ['*.png', '*.jpg', '*.jpeg']:
                        image_files.extend(glob.glob(os.path.join(current_dir, ext)))
                    
                    # Sort by modification time, get most recent
                    if image_files:
                        image_files.sort(key=os.path.getmtime, reverse=True)
                        # Check if file was created in the last 5 minutes (likely from this generation)
                        most_recent = image_files[0]
                        if os.path.getmtime(most_recent) > time.time() - 300:  # 5 minutes
                            found_image = most_recent
                except Exception as e:
                    print(f"Error checking for recent images: {e}")
            
            # Display the image if found
            if found_image:
                st.success("✨ Renovation Plan Generated!")
                st.image(found_image, caption="AI Generated Design", use_container_width=True)
                st.session_state.last_generated_image = found_image
                st.session_state.last_generated_filename = os.path.basename(found_image)
                st.session_state.attach_last_rendering = True
                st.session_state.attach_uploaded_images = False
            elif "rendering generated" in final_response.lower() or "saved as" in final_response.lower():
                st.warning("⚠️ Image was generated but file not found. Check the console for the filename.")
            
            # Save to chat history
            msg_data = {"role": "assistant", "content": final_response}
            if found_image:
                msg_data["image_path"] = found_image
            st.session_state.messages.append(msg_data)