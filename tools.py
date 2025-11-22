import os
import logging
import mimetypes
from google import genai
from google.genai import types
from google.adk.tools import ToolContext
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# Helper Functions for Asset Version Management
# ============================================================================

def get_next_version_number(tool_context: ToolContext, asset_name: str) -> int:
    """Get the next version number for a given asset name."""
    asset_versions = tool_context.state.get("asset_versions", {})
    current_version = asset_versions.get(asset_name, 0)
    next_version = current_version + 1
    return next_version


def update_asset_version(tool_context: ToolContext, asset_name: str, version: int, filename: str) -> None:
    """Update the version tracking for an asset."""
    if "asset_versions" not in tool_context.state:
        tool_context.state["asset_versions"] = {}
    if "asset_filenames" not in tool_context.state:
        tool_context.state["asset_filenames"] = {}
    
    tool_context.state["asset_versions"][asset_name] = version
    tool_context.state["asset_filenames"][asset_name] = filename
    
    # Maintain a list of all versions for this asset
    asset_history_key = f"{asset_name}_history"
    if asset_history_key not in tool_context.state:
        tool_context.state[asset_history_key] = []
    tool_context.state[asset_history_key].append({"version": version, "filename": filename})


def create_versioned_filename(asset_name: str, version: int, file_extension: str = "png") -> str:
    """Create a versioned filename for an asset."""
    return f"{asset_name}_v{version}.{file_extension}"


def get_asset_versions_info(tool_context: ToolContext) -> str:
    """Get information about all asset versions in the session."""
    asset_versions = tool_context.state.get("asset_versions", {})
    if not asset_versions:
        return "No renovation renderings have been created yet."
    
    info_lines = ["Current renovation renderings:"]
    for asset_name, current_version in asset_versions.items():
        history_key = f"{asset_name}_history"
        history = tool_context.state.get(history_key, [])
        total_versions = len(history)
        latest_filename = tool_context.state.get("asset_filenames", {}).get(asset_name, "Unknown")
        info_lines.append(f"  • {asset_name}: {total_versions} version(s), latest is v{current_version} ({latest_filename})")
    
    return "\n".join(info_lines)


def get_reference_images_info(tool_context: ToolContext) -> str:
    """Get information about all reference images (current room/inspiration) uploaded in the session."""
    reference_images = tool_context.state.get("reference_images", {})
    if not reference_images:
        return "No reference images have been uploaded yet."
    
    info_lines = ["Available reference images (current room photos & inspiration):"]
    for filename, info in reference_images.items():
        version = info.get("version", "Unknown")
        image_type = info.get("type", "reference")
        info_lines.append(f"  • {filename} ({image_type} v{version})")
    
    return "\n".join(info_lines)


async def load_reference_image(tool_context: ToolContext, filename: str):
    """Load a reference image artifact by filename."""
    try:
        loaded_part = await tool_context.load_artifact(filename)
        if loaded_part:
            logger.info(f"Successfully loaded reference image: {filename}")
            return loaded_part
        else:
            logger.warning(f"Reference image not found: {filename}")
            return None
    except Exception as e:
        logger.error(f"Error loading reference image {filename}: {e}")
        return None


async def load_image_from_file(tool_context: ToolContext, filename: str):
    """Load an image from a file path (for uploaded images that aren't artifacts yet)."""
    import os
    from google.genai import types
    
    try:
        # Check if file exists
        if not os.path.exists(filename):
            logger.warning(f"Image file not found: {filename}")
            return None
        
        # Read the image file
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            mime_type = "image/png"
        
        with open(filename, "rb") as f:
            image_bytes = f.read()
        
        # Create a Part from the image data
        image_part = types.Part(
            inline_data=types.Blob(
                mime_type=mime_type,
                data=image_bytes
            )
        )
        
        logger.info(f"Successfully loaded image from file: {filename}")
        return image_part
    except Exception as e:
        logger.error(f"Error loading image from file {filename}: {e}")
        return None


def get_latest_reference_image_filename(tool_context: ToolContext) -> str:
    """Get the filename of the most recently uploaded reference image."""
    return tool_context.state.get("latest_reference_image")


def is_artifact_service_available(tool_context: ToolContext) -> bool:
    """Check if artifact service is available in the tool context."""
    try:
        # Check if save_artifact method exists and is callable
        if hasattr(tool_context, 'save_artifact') and callable(getattr(tool_context, 'save_artifact', None)):
            # Try to access the artifact service through the session
            # If it raises an AttributeError, the service might not be initialized
            return True
        return False
    except Exception:
        return False


async def save_artifact_safely(tool_context: ToolContext, filename: str, artifact) -> tuple[bool, int | None]:
    """
    Safely save an artifact, returning (success, version).
    Returns (False, None) if artifact service is not available.
    """
    try:
        if hasattr(tool_context, 'save_artifact'):
            artifact_version = await tool_context.save_artifact(
                filename=filename,
                artifact=artifact
            )
            return (True, artifact_version)
        else:
            logger.debug(f"Artifact service not available - saving to disk only: {filename}")
            return (False, None)
    except AttributeError:
        logger.debug(f"Artifact service not initialized - saving to disk only: {filename}")
        return (False, None)
    except Exception as e:
        # Check if it's specifically about artifact service not being initialized
        error_msg = str(e).lower()
        if "artifact service" in error_msg and "not initialized" in error_msg:
            logger.debug(f"Artifact service not initialized - saving to disk only: {filename}")
            return (False, None)
        else:
            # Some other error - log as warning
            logger.warning(f"Error saving artifact (image saved to disk): {e}")
            return (False, None)


# ============================================================================
# Pydantic Input Models
# ============================================================================

class GenerateRenovationRenderingInput(BaseModel):
    prompt: str = Field(..., description="A detailed description of the renovated space to generate. Include room type, style, colors, materials, fixtures, lighting, and layout.")
    aspect_ratio: str = Field(default="16:9", description="The desired aspect ratio, e.g., '1:1', '16:9', '9:16'. Default is 16:9 for room photos.")
    asset_name: str = Field(default="renovation_rendering", description="Base name for the rendering (will be versioned automatically). Use descriptive names like 'kitchen_modern_farmhouse' or 'bathroom_spa'.")
    current_room_photo: str = Field(default=None, description="Optional: filename of the current room photo to use as reference for layout/structure.")
    inspiration_image: str = Field(default=None, description="Optional: filename of an inspiration image to guide the style. Use 'latest' for most recent upload.")


class EditRenovationRenderingInput(BaseModel):
    artifact_filename: str = Field(..., description="The filename of the rendering artifact to edit.")
    prompt: str = Field(..., description="The prompt describing the desired changes (e.g., 'make cabinets darker', 'add pendant lights', 'change floor to hardwood').")
    asset_name: str = Field(default=None, description="Optional: specify asset name for the new version (defaults to incrementing current asset).")
    reference_image_filename: str = Field(default=None, description="Optional: filename of a reference image to guide the edit. Use 'latest' for most recent upload.")


# ============================================================================
# Image Generation Tool
# ============================================================================

async def generate_renovation_rendering(tool_context: ToolContext, inputs: GenerateRenovationRenderingInput) -> str:
    """
    Generates a photorealistic rendering of a renovated space based on the design plan.
    """
    if "GEMINI_API_KEY" not in os.environ and "GOOGLE_API_KEY" not in os.environ:
        raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set.")

    logger.info("Starting renovation rendering generation")
    try:
        client = genai.Client()
        
        # --- FIX 1: Handle Input Type Safety ---
        if isinstance(inputs, dict):
            inputs = GenerateRenovationRenderingInput(**inputs)
        
        # Handle reference images
        reference_images = []
        current_room_part = None
        
        if inputs.current_room_photo:
            # Try loading as artifact first, then as file
            current_photo_part = await load_reference_image(tool_context, inputs.current_room_photo)
            if not current_photo_part:
                current_photo_part = await load_image_from_file(tool_context, inputs.current_room_photo)
            
            if current_photo_part:
                current_room_part = current_photo_part
                reference_images.append(current_photo_part)
                logger.info(f"Using current room photo: {inputs.current_room_photo}")
        
        if inputs.inspiration_image:
            if inputs.inspiration_image == "latest":
                insp_filename = get_latest_reference_image_filename(tool_context)
            else:
                insp_filename = inputs.inspiration_image
            
            if insp_filename:
                inspiration_part = await load_reference_image(tool_context, insp_filename)
                if not inspiration_part:
                    inspiration_part = await load_image_from_file(tool_context, insp_filename)
                if inspiration_part:
                    reference_images.append(inspiration_part)
        
        # Build the enhanced prompt
        # If current_room_photo is provided, we should modify it, not generate from scratch
        has_base_image = inputs.current_room_photo is not None
        
        if has_base_image:
            # User provided a base image - we should modify it, not generate new
            # This should ideally go through edit_renovation_rendering, but if we're here,
            # we'll use the base image as the primary input
            base_rewrite_prompt = f"""
            Modify the provided base image according to this description: {inputs.prompt}
            Keep the same room structure, layout, and perspective as the base image.
            Apply the requested changes while preserving the original composition.
            Aspect ratio: {inputs.aspect_ratio}
            """
            if inputs.inspiration_image:
                base_rewrite_prompt += "\nUse the inspiration image to guide the style."
        else:
            # No base image - generate new
            base_rewrite_prompt = f"""
            Create a highly detailed, photorealistic prompt for generating an interior design image.
            Original description: {inputs.prompt}
            Enhance this to be a professional interior photography prompt.
            Aspect ratio: {inputs.aspect_ratio}
            """
            if reference_images:
                base_rewrite_prompt += "\nUse the provided reference image(s) as inspiration."
        
        # Rewrite Prompt
        rewritten_prompt_response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=base_rewrite_prompt
        )
        rewritten_prompt = rewritten_prompt_response.text
        logger.info(f"Enhanced prompt: {rewritten_prompt}")

        # Prepare Image Generation
        model = "gemini-2.5-flash-image"
        
        if has_base_image and current_room_part:
            # Put base image first, then prompt, then inspiration if any
            content_parts = [current_room_part, types.Part.from_text(text=rewritten_prompt)]
            # Add any inspiration images (skip the first one which is the base)
            for ref_img in reference_images:
                if ref_img != current_room_part:
                    content_parts.append(ref_img)
        else:
            # Standard generation: prompt first, then reference images
            content_parts = [types.Part.from_text(text=rewritten_prompt)]
            content_parts.extend(reference_images)

        contents = [types.Content(role="user", parts=content_parts)]
        generate_content_config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        )

        # Generate Filename
        version = get_next_version_number(tool_context, inputs.asset_name)
        artifact_filename = create_versioned_filename(inputs.asset_name, version)
        logger.info(f"Generating rendering: {artifact_filename}")

        # Generate Stream
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                part = chunk.candidates[0].content.parts[0]
                
                # CHECK FOR IMAGE DATA
                if part.inline_data and part.inline_data.data:
                    inline_data = part.inline_data
                    
                    # --- FIX 2: MANUALLY SAVE TO DISK ---
                    # This ensures Streamlit can actually find the file
                    try:
                        with open(artifact_filename, "wb") as f:
                            f.write(inline_data.data)
                        logger.info(f"💾 Saved image to disk: {artifact_filename}")
                    except Exception as e:
                        logger.error(f"Failed to write to disk: {e}")
                    # ------------------------------------

                    image_part = types.Part(inline_data=inline_data)
                    
                    # Update State (always update state even if artifact service fails)
                    version = get_next_version_number(tool_context, inputs.asset_name)
                    tool_context.state["last_generated_rendering"] = artifact_filename
                    tool_context.state["current_asset_name"] = inputs.asset_name
                    
                    # Try to save to ADK Session (Memory) - but don't fail if artifact service is not available
                    artifact_saved, artifact_version = await save_artifact_safely(
                        tool_context, artifact_filename, image_part
                    )
                    
                    if artifact_saved and artifact_version:
                        update_asset_version(tool_context, inputs.asset_name, artifact_version, artifact_filename)
                        logger.info(f"✅ Saved artifact to session: {artifact_filename} (version {artifact_version})")
                    else:
                        # Artifact service not available - that's okay, file is already on disk
                        # Still update version tracking manually
                        update_asset_version(tool_context, inputs.asset_name, version, artifact_filename)
                        logger.info(f"💾 Image saved to disk: {artifact_filename} (version {version})")
                    
                    return f"✅ Renovation rendering generated successfully!\n\nSaved as: **{artifact_filename}** (version {version} of {inputs.asset_name})"
                
                # CHECK FOR TEXT DATA
                elif part.text:
                     logger.info(f"Model text response: {part.text}")

        return "No rendering was generated. Please try again."
        
    except Exception as e:
        logger.error(f"Error in generate_renovation_rendering: {e}")
        return f"An error occurred: {e}"

# ============================================================================
# Image Editing Tool
# ============================================================================

async def edit_renovation_rendering(tool_context: ToolContext, inputs: EditRenovationRenderingInput) -> str:
    """
    Edits an existing renovation rendering based on feedback or refinements.
    Can edit both generated renderings and uploaded images.
    """
    if "GEMINI_API_KEY" not in os.environ and "GOOGLE_API_KEY" not in os.environ:
        raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set.")

    logger.info("Starting renovation rendering edit")

    try:
        client = genai.Client()
        
        # --- FIX: Check if inputs is already an object or needs conversion ---
        if isinstance(inputs, dict):
            inputs = EditRenovationRenderingInput(**inputs)
        # If it is not a dict, we assume it is already the correct object
        
        # Load the existing rendering - try artifact first, then file
        logger.info(f"Loading image: {inputs.artifact_filename}")
        loaded_image_part = None
        
        # First, try to load as artifact
        try:
            loaded_image_part = await tool_context.load_artifact(inputs.artifact_filename)
            if loaded_image_part:
                logger.info(f"Loaded image from artifact: {inputs.artifact_filename}")
        except Exception as e:
            logger.info(f"Could not load as artifact, trying file: {e}")
        
        # If not found as artifact, try loading from file (for uploaded images)
        if not loaded_image_part:
            loaded_image_part = await load_image_from_file(tool_context, inputs.artifact_filename)
            if loaded_image_part:
                logger.info(f"Loaded image from file: {inputs.artifact_filename}")
        
        if not loaded_image_part:
            return f"❌ Could not find image: {inputs.artifact_filename}. Please ensure the image was uploaded or generated."

        # Handle reference image if specified
        reference_image_part = None
        if inputs.reference_image_filename:
            if inputs.reference_image_filename == "latest":
                ref_filename = get_latest_reference_image_filename(tool_context)
            else:
                ref_filename = inputs.reference_image_filename
            
            if ref_filename:
                reference_image_part = await load_reference_image(tool_context, ref_filename)
                if reference_image_part:
                    logger.info(f"Using reference image for editing: {ref_filename}")

        model = "gemini-2.5-flash-image"

        # Build content parts
        content_parts = [loaded_image_part, types.Part.from_text(text=inputs.prompt)]
        if reference_image_part:
            content_parts.append(reference_image_part)

        contents = [
            types.Content(
                role="user",
                parts=content_parts,
            ),
        ]
        
        generate_content_config = types.GenerateContentConfig(
            response_modalities=[
                "IMAGE",
                "TEXT",
            ],
        )

        # Determine asset name and generate versioned filename
        if inputs.asset_name:
            asset_name = inputs.asset_name
        else:
            current_asset_name = tool_context.state.get("current_asset_name")
            if current_asset_name:
                asset_name = current_asset_name
            else:
                # Extract from filename
                base_name = inputs.artifact_filename.split('_v')[0] if '_v' in inputs.artifact_filename else "renovation_rendering"
                asset_name = base_name
        
        version = get_next_version_number(tool_context, asset_name)
        edited_artifact_filename = create_versioned_filename(asset_name, version)
        logger.info(f"Editing rendering with artifact filename: {edited_artifact_filename} (version {version})")

        # Edit the image
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if (
                chunk.candidates is None
                or chunk.candidates[0].content is None
                or chunk.candidates[0].content.parts is None
            ):
                continue
            
            if chunk.candidates[0].content.parts[0].inline_data and chunk.candidates[0].content.parts[0].inline_data.data:
                inline_data = chunk.candidates[0].content.parts[0].inline_data
                
                # Create a Part object from the inline data
                edited_image_part = types.Part(inline_data=inline_data)
                
                # Save to disk first
                try:
                    with open(edited_artifact_filename, "wb") as f:
                        f.write(inline_data.data)
                    logger.info(f"💾 Saved edited image to disk: {edited_artifact_filename}")
                except Exception as e:
                    logger.error(f"Failed to write edited image to disk: {e}")
                
                # Update version tracking
                version = get_next_version_number(tool_context, asset_name)
                update_asset_version(tool_context, asset_name, version, edited_artifact_filename)
                
                # Store in session state
                tool_context.state["last_generated_rendering"] = edited_artifact_filename
                tool_context.state["current_asset_name"] = asset_name
                
                # Try to save to ADK Session (Memory) - but don't fail if artifact service is not available
                artifact_saved, artifact_version = await save_artifact_safely(
                    tool_context, edited_artifact_filename, edited_image_part
                )
                
                if artifact_saved and artifact_version:
                    logger.info(f"✅ Saved edited artifact to session: {edited_artifact_filename} (version {artifact_version})")
                else:
                    # Artifact service not available - that's okay, file is already on disk
                    logger.info(f"💾 Edited image saved to disk: {edited_artifact_filename} (version {version})")
                
                return f"✅ Rendering edited successfully!\n\nSaved as: **{edited_artifact_filename}** (version {version} of {asset_name})\n\nThe rendering has been updated based on your feedback."
            else:
                # Log any text responses
                if hasattr(chunk, 'text') and chunk.text:
                    logger.info(f"Model response: {chunk.text}")
                
        return "No edited rendering was generated. Please try again."
        
    except Exception as e:
        logger.error(f"Error in edit_renovation_rendering: {e}")
        return f"An error occurred while editing the rendering: {e}"


# ============================================================================
# Utility Tools
# ============================================================================

async def list_renovation_renderings(tool_context: ToolContext) -> str:
    """Lists all renovation renderings created in this session."""
    return get_asset_versions_info(tool_context)


async def list_reference_images(tool_context: ToolContext) -> str:
    """Lists all reference images (current room photos & inspiration) uploaded in this session."""
    return get_reference_images_info(tool_context)


async def save_uploaded_image_as_artifact(
    tool_context: ToolContext,
    image_data: str,
    artifact_name: str,
    image_type: str = "current_room"
) -> str:
    """
    Saves an uploaded image as a named artifact for later use in editing.
    """
    try:
        # Try to save as artifact
        artifact_saved, artifact_version = await save_artifact_safely(
            tool_context, artifact_name, image_data
        )
        
        # Track in state
        if "uploaded_images" not in tool_context.state:
            tool_context.state["uploaded_images"] = {}
        
        tool_context.state["uploaded_images"][artifact_name] = {
            "type": image_type,
            "filename": artifact_name
        }
        
        if image_type == "current_room":
            tool_context.state["current_room_artifact"] = artifact_name
        elif image_type == "inspiration":
            tool_context.state["inspiration_artifact"] = artifact_name
        
        if artifact_saved:
            logger.info(f"Saved uploaded image as artifact: {artifact_name}")
            return f"✅ Image saved as artifact: {artifact_name} (type: {image_type}). This can now be used for editing."
        else:
            logger.info(f"Saved uploaded image reference: {artifact_name} (artifact service not available, using file-based storage)")
            return f"✅ Image reference saved: {artifact_name} (type: {image_type}). This can now be used for editing."
        
    except Exception as e:
        logger.error(f"Error saving uploaded image: {e}")
        return f"❌ Error saving uploaded image: {e}"