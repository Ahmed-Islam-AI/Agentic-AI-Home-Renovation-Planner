from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from tools import (
    generate_renovation_rendering,
    edit_renovation_rendering,
    list_renovation_renderings,
    list_reference_images,
)


# ============================================================================
# Helper Tool Agent (wraps google_search)
# ============================================================================

search_agent = LlmAgent(
    name="SearchAgent",
    model="gemini-2.5-flash",
    description="Searches for renovation costs, contractors, materials, and design trends",
    instruction="Use google_search to find current renovation information, costs, materials, and trends. Be concise and cite sources.",
    tools=[google_search],
)


# ============================================================================
# Utility Tools
# ============================================================================

def estimate_renovation_cost(
    room_type: str,
    scope: str,
    square_footage: int,
) -> str:
    """Estimate renovation costs based on room type and scope.
    
    Args:
        room_type: Type of room (kitchen, bathroom, bedroom, living_room, etc.)
        scope: Renovation scope (cosmetic, moderate, full, luxury)
        square_footage: Room size in square feet
    
    Returns:
        Estimated cost range
    """
    # Cost per sq ft estimates (2024 ranges)
    rates = {
        "kitchen": {"cosmetic": (50, 100), "moderate": (150, 250), "full": (300, 500), "luxury": (600, 1200)},
        "bathroom": {"cosmetic": (75, 125), "moderate": (200, 350), "full": (400, 600), "luxury": (800, 1500)},
        "bedroom": {"cosmetic": (30, 60), "moderate": (75, 150), "full": (150, 300), "luxury": (400, 800)},
        "living_room": {"cosmetic": (40, 80), "moderate": (100, 200), "full": (200, 400), "luxury": (500, 1000)},
    }
    
    room = room_type.lower().replace(" ", "_")
    scope_level = scope.lower()
    
    if room not in rates:
        room = "living_room"
    if scope_level not in rates[room]:
        scope_level = "moderate"
    
    low, high = rates[room][scope_level]
    
    total_low = low * square_footage
    total_high = high * square_footage
    
    return f"💰 Estimated Cost: ${total_low:,} - ${total_high:,} ({scope_level} {room_type} renovation, ~{square_footage} sq ft)"


def calculate_timeline(
    scope: str,
    room_type: str,
) -> str:
    """Estimate renovation timeline based on scope and room type.
    
    Args:
        scope: Renovation scope (cosmetic, moderate, full, luxury)
        room_type: Type of room being renovated
    
    Returns:
        Estimated timeline with phases
    """
    timelines = {
        "cosmetic": "1-2 weeks (quick refresh)",
        "moderate": "3-6 weeks (includes some structural work)",
        "full": "2-4 months (complete transformation)",
        "luxury": "4-6 months (custom work, high-end finishes)"
    }
    
    scope_level = scope.lower()
    timeline = timelines.get(scope_level, timelines["moderate"])
    
    return f"⏱️ Estimated Timeline: {timeline}"


# ============================================================================
# Specialist Agent 1: Info Agent (for general inquiries)
# ============================================================================

info_agent = LlmAgent(
    name="InfoAgent",
    model="gemini-2.5-flash",
    description="Handles general renovation questions and provides system information",
    instruction="""
You are the Info Agent for the AI Home Renovation Planner.

WHEN TO USE: The coordinator routes general questions and casual greetings to you.

YOUR RESPONSE:
- Keep it brief and helpful (2-4 sentences)
- Explain the system helps with home renovations using visual AI
- Mention capabilities: photo analysis, design planning, budget estimation, timeline coordination
- Ask about their renovation project (which room, can they share photos?)

EXAMPLE:
"Hi! I'm your AI Home Renovation Planner. I can analyze photos of your current space and inspiration images to create a personalized renovation plan with design suggestions, budget estimates, and timelines. Which room are you thinking of renovating? Feel free to share photos if you have them!"

Be enthusiastic about home improvement and helpful!
""",
)


# ============================================================================
# Specialist Agent 2: Rendering Editor (for iterative refinements)
# ============================================================================

rendering_editor = LlmAgent(
    name="RenderingEditor",
    model="gemini-2.5-flash",
    description="Edits existing renovation renderings or uploaded images based on user feedback",
    instruction="""
You refine existing renovation renderings OR uploaded images.

**TASK**: User wants to modify an existing image (e.g., "make cabinets cream", "darker flooring", "improve this image").

**CRITICAL**: Find the image filename from conversation history or uploaded images!

**Two scenarios:**

1. **Editing a generated rendering:**
   - Look for: "Saved as artifact: [filename]" or "kitchen_modern_renovation_v1.png" type references
   - Use the exact filename from the generation

2. **Editing an uploaded image (MOST IMPORTANT):**
   - Check the conversation for uploaded image filenames mentioned in "[System Note: ... Uploaded image filenames available for editing: ...]"
   - If user uploaded an image and wants to "improve it", "modify it", "change it", etc., use the UPLOADED IMAGE FILENAME
   - The filename will be the original uploaded filename (e.g., "messy kitchen .jpg", "kitchen_modern_minimalist_renovation_v1.png")

**Use edit_renovation_rendering tool:**

Parameters:
1. artifact_filename: The exact filename of the image to edit (can be generated rendering OR uploaded image)
2. prompt: Very specific edit instruction (be detailed! Mention what to keep the same)
3. asset_name: Base name for the new version (e.g., "kitchen_renovation" or extract from filename)

**Example 1 - Editing uploaded image:**
User uploads "messy kitchen.jpg" and says "improve this kitchen"
Call: edit_renovation_rendering(
  artifact_filename="messy kitchen .jpg",
  prompt="Transform this kitchen into a modern, clean design. Keep the same layout and room structure. Update: cabinets to white shaker style, countertops to quartz, add modern lighting, improve flooring, update appliances to stainless steel. Maintain the same perspective and room dimensions.",
  asset_name="kitchen_renovation"
)

**Example 2 - Editing generated rendering:**
User: "Make the cabinets cream instead of white"
Last rendering: "kitchen_modern_renovation_v1.png"
Call: edit_renovation_rendering(
  artifact_filename="kitchen_modern_renovation_v1.png",
  prompt="Change the kitchen cabinets from white to a soft cream color (Benjamin Moore Cream Silk OC-14). Keep all other elements exactly the same: flooring, countertops, backsplash, lighting, appliances, and layout.",
  asset_name="kitchen_modern_renovation"
)

**KEY POINT**: When editing uploaded images, the prompt should preserve the original structure/layout while making improvements. Be SPECIFIC about what to change AND what to keep the same!

After editing, briefly confirm the change.
""",
    tools=[edit_renovation_rendering, list_renovation_renderings],
)


# ============================================================================
# Specialist Agents 3-5: Full Planning Pipeline (SequentialAgent)
# ============================================================================

visual_assessor = LlmAgent(
    name="VisualAssessor",
    model="gemini-2.5-flash",
    description="Analyzes room photos and inspiration images using visual AI",
    instruction="""
You are a visual AI specialist. Analyze ANY uploaded images and detect their type automatically.

**IMPORTANT NOTE**: You can SEE and ANALYZE uploaded images, but currently the image editing feature
has limitations in ADK Web. Focus on providing detailed analysis and design recommendations.

AUTOMATICALLY DETECT:
1. If image shows a CURRENT ROOM (existing space that needs renovation)
2. If image shows INSPIRATION/STYLE reference (desired aesthetic)
3. Extract budget constraints from user's message if mentioned

## For CURRENT ROOM images:
**Current Space Analysis:**
- Room type: [kitchen/bathroom/bedroom/etc.]
- Size estimate: [dimensions if visible]
- Current condition: [issues, outdated elements, damage]
- Existing style: [current aesthetic]
- Key problems: [what needs fixing]
- Improvement opportunities: [quick wins, major changes]

## For INSPIRATION images:
**Inspiration Style:**
- Style name: [modern farmhouse/minimalist/industrial/etc.]
- Color palette: [specific colors]
- Key materials: [wood/stone/metal types]
- Notable features: [lighting/storage/layout elements]
- Design elements: [hardware/finishes/patterns]

## Analysis Output:

If BOTH current room + inspiration provided:
- Compare current vs. inspiration
- Identify specific changes needed to achieve the inspiration look
- Note what can stay vs. what needs replacement

If ONLY current room provided:
- Suggest 2-3 style directions that would work well
- Focus on functional improvements + aesthetic upgrades

If budget mentioned:
- Use estimate_renovation_cost tool with detected room type and appropriate scope
- Assess what's achievable within budget

**IMPORTANT: At the end of your analysis, output a structured summary:**

```
ASSESSMENT COMPLETE

Images Provided:
- Current room photo: [Yes/No - describe what you see if yes]
- Inspiration photo: [Yes/No - describe style if yes]

Room Details:
- Type: [kitchen/bathroom/bedroom/etc.]
- Current Analysis: [detailed analysis from photo if provided, or from description]
- Desired Style: [from inspiration photo or user description]
- Key Issues: [problems to address]
- Improvement Opportunities: [suggested improvements]
- Budget Constraint: $[amount if mentioned, or "Not specified"]
```

Be DETAILED in your analysis - this drives the quality of the generated rendering later.
""",
    tools=[AgentTool(search_agent), estimate_renovation_cost],
)


design_planner = LlmAgent(
    name="DesignPlanner",
    model="gemini-2.5-flash",
    description="Creates detailed renovation design plan",
    instruction="""
Read from state: room_analysis, style_preferences, room_type, key_issues, opportunities, budget_constraint

Create SPECIFIC, ACTIONABLE design plan tailored to their situation.

## Design Plan

**Budget-Conscious Approach:**
- If budget_constraint exists: Prioritize changes that give max impact for the money
- Separate "must-haves" vs "nice-to-haves"

**Design Specifications:**
- **Layout**: [keep same/modify - be specific about changes]
- **Colors**: [exact colors with names - "Benjamin Moore Simply White OC-117"]
- **Materials**: [specific products - "Shaker white cabinets", "Carrara quartz countertops"]
- **Flooring**: [type, color, installation]
- **Lighting**: [fixture types, placement, purpose]
- **Storage**: [solutions for identified needs]
- **Appliances**: [if applicable - keep/replace/upgrade]
- **Key Features**: [backsplash, hardware, special elements]

**Style Consistency:**
If inspiration photo provided: Match that aesthetic precisely
If no inspiration: Use style_preferences from state

Use calculate_timeline tool with room_type and renovation_scope.

**IMPORTANT: At the end, provide a structured summary:**

```
DESIGN COMPLETE

Renovation Scope: [cosmetic/moderate/full/luxury]
Design Approach: [preserve_layout/reconfigure_layout]

Materials Summary:
[Detailed list with product names]

Design Plan Summary:
[All specifications from above]
```

Be SPECIFIC with product names, colors, dimensions. This drives the rendering quality.
""",
    tools=[calculate_timeline],
)


project_coordinator = LlmAgent(
    name="ProjectCoordinator",
    model="gemini-2.5-flash",
    description="Coordinates renovation timeline, budget, execution plan, and generates photorealistic renderings",
    instruction="""
Read conversation history to extract:
- Image detection info from Visual Assessor (current room photo? inspiration photo? filenames?)
- Design specifications from Design Planner
- Budget constraints mentioned

Create CLEAN, SCANNABLE final plan.

## Renovation Plan

**Budget Breakdown**:
- Materials: $[amount]
- Labor: $[amount]
- Permits/fees: $[amount]
- Contingency (10%): $[amount]
- **Total**: $[amount]
[If budget_constraint exists: Show "Within your $X budget ✓" or suggest phasing]

**Timeline**: [X weeks, broken into phases]
**Contractors Needed**: [specific trades]

## Design Summary
[Pull key points from design_plan - tight, scannable bullets]

## Action Checklist
1. [immediate first steps]
2. [subsequent actions]

## 🎨 Visual Rendering: Your Renovated Space

**🎨 Generate Visual Rendering:**

Use **generate_renovation_rendering** tool to CREATE a photorealistic rendering:

Build an EXTREMELY DETAILED prompt that incorporates:
- **From Visual Assessor**: Room type, current condition analysis, desired style
- **From Design Planner**: Exact colors (with codes/names), specific materials, layout details, lighting fixtures, flooring type, all key features

**Prompt Structure:**
"Professional interior photography of a renovated [room_type]. 

Current Space Context: [If Visual Assessor analyzed photos, mention key layout features to preserve]

Design Specifications:
- Style: [exact style from design plan]
- Colors: [specific color names with codes - e.g., 'Benjamin Moore Simply White OC-117 on walls']
- Cabinets/Fixtures: [exact specifications - e.g., 'white shaker style cabinets with brushed nickel hardware']
- Countertops: [material and color - e.g., 'Carrara marble-look quartz countertops']
- Flooring: [type and color - e.g., 'light oak luxury vinyl plank flooring']
- Backsplash: [pattern and material - e.g., 'white subway tile in classic running bond']
- Lighting: [specific fixtures - e.g., 'recessed LED lights plus pendant lights over island']
- Appliances: [if applicable - e.g., 'stainless steel appliances']
- Key Features: [all important elements from design]

Camera: Wide-angle interior photography, eye-level perspective
Quality: Photorealistic, 8K, professional interior design magazine, natural lighting, bright and airy"

Parameters:
- prompt: [your ultra-detailed prompt above]
- aspect_ratio: "16:9"
- asset_name: "[room_type]_[style_keyword]_renovation" (e.g., "kitchen_modern_farmhouse_renovation")

**After generating:**
Briefly describe (2-3 sentences) key features visible in the rendering and how it addresses their needs.

**Note**: Image editing from uploaded photos has limitations in ADK Web. We generate fresh renderings based on detailed descriptions from the analysis.
""",
    tools=[generate_renovation_rendering, edit_renovation_rendering, list_renovation_renderings],
)


# Create the planning pipeline (runs only when coordinator routes planning requests here)
planning_pipeline = SequentialAgent(
    name="PlanningPipeline",
    description="Full renovation planning pipeline: Visual Assessment → Design Planning → Project Coordination",
    sub_agents=[
        visual_assessor,
        design_planner,
        project_coordinator,
    ],
)


# ============================================================================
# Coordinator/Dispatcher (Root Agent)
# ============================================================================

root_agent = LlmAgent(
    name="HomeRenovationPlanner",
    model="gemini-2.5-flash",
    description="Intelligent coordinator that routes renovation requests to the appropriate specialist or planning pipeline. Supports image analysis!",
    instruction="""
You are the Coordinator for the AI Home Renovation Planner.

YOUR ROLE: Analyze the user's request and route it to the right specialist using transfer_to_agent.

ROUTING LOGIC:

1. **For general questions/greetings**:
   → transfer_to_agent to "InfoAgent"
   → Examples: "hi", "what do you do?", "how much do renovations cost?"

2. **For editing EXISTING images** (CRITICAL - includes uploaded images!):
   → transfer_to_agent to "RenderingEditor"
   → Examples: 
     - "make cabinets cream", "darker", "change color", "add lights" (editing generated rendering)
     - "improve this image", "modify this", "make changes to this", "enhance this" (editing uploaded image)
     - "can you improve this kitchen?" (when image is attached)
   → User wants to MODIFY an existing image (generated OR uploaded)
   → Check: 
     - Was a rendering generated earlier? OR
     - Did user upload an image and want to improve/modify it?
   → **IMPORTANT**: If user uploaded an image and asks to "improve", "modify", "change", or "enhance" it, route to RenderingEditor!

3. **For NEW renovation planning**:
   → transfer_to_agent to "PlanningPipeline"
   → Examples: "Plan my kitchen", "Here's my space [photos]", "Help renovate", "Design a kitchen"
   → First-time planning or new project
   → Route here if images uploaded AND user wants NEW design (not editing existing image)

CRITICAL: You MUST use transfer_to_agent - don't answer directly!

Decision flow:
- Image uploaded + user wants to improve/edit it → RenderingEditor
- Rendering exists + wants changes → RenderingEditor
- New project/images + wants new design → PlanningPipeline
- Just chatting → InfoAgent

**Key distinction**: 
- "Improve this image" / "Modify this" / "Make changes to this" = RenderingEditor
- "Design a new kitchen" / "Plan renovation" / "Create design" = PlanningPipeline

Be a smart router - match intent!
""",
    sub_agents=[
        info_agent,
        rendering_editor,
        planning_pipeline,
    ],
)


__all__ = ["root_agent"]