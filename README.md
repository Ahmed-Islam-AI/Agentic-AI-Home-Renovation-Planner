# 🏠 AI Home Renovation Planner

**Your Personal Digital Architect: Visualizing Dreams, Planning Reality.**

An intelligent, multi-agent system that acts as your personal interior designer. This application uses **Google Gemini 2.5 Flash** (Multimodal) and the **Google Agent Development Kit (ADK)** to "see" your room, plan renovations, calculate budgets, and generate photorealistic "after" visualizations.

## 🚀 Features

- **👁️ Visual Analysis:** Upload photos of your current room. The **Visual Assessor Agent** analyzes dimensions, materials, and current condition.
- **🧠 Intelligent Planning:** The **Design Planner Agent** creates detailed material lists, cost estimates (based on room type & scope), and construction timelines.
- **🎨 Photorealistic Rendering:** The **Project Coordinator** generates high-fidelity "After" images of your renovated space using Gemini Imagen.
- **🔄 Iterative Editing:** Ask the **Rendering Editor** to tweak specific details (e.g., _"Change the cabinets to navy blue"_) naturally.
- **📂 Smart Image Management:** Categorize uploads as "Current Room" or "Inspiration" to guide the AI's design process via the Streamlit sidebar.

---

## 🏗️ Architecture

This project implements the **Coordinator-Dispatcher Pattern**. A central "Root Agent" analyzes user intent and routes tasks to specialized sub-agents.

### The Agent Team

1.  **Root Agent (Coordinator):** The traffic controller. It analyzes your request and routes it to the correct specialist:
    - _General Chat_ → Info Agent
    - _Design Changes_ → Rendering Editor
    - _New Projects_ → Planning Pipeline
2.  **Info Agent:** Handles general Q&A and greetings.
3.  **Rendering Editor:** Specialized in refining existing generated images based on specific user feedback.
4.  **Planning Pipeline (Sequential Agent):**
    - **Step 1: Visual Assessor:** Uses computer vision to analyze uploaded images for room type, style, and constraints.
    - **Step 2: Design Planner:** Generates the specs, budget, and timeline based on the visual data.
    - **Step 3: Project Coordinator:** Synthesizes the plan and calls the image generation tool.

---

## 🛠️ Tech Stack

- **Frontend:** [Streamlit](https://streamlit.io/)
- **Orchestration:** [Google ADK (Agent Development Kit)](https://github.com/google/adk)
- **AI Models:**
  - **Logic & Vision:** Google Gemini 2.5 Flash
  - **Image Generation:** Google Gemini 2.5 Flash Image (Imagen)
- **Language:** Python 3.10+

---

## 📦 Installation

Follow these steps to set up the project locally.

### 1. Clone the repository

```bash
git clone [https://github.com/Ahmed-Islam-AI/Agentic-AI-Home-Renovation-Planner.git](https://github.com/Ahmed-Islam-AI/Agentic-AI-Home-Renovation-Planner.git)
cd Agentic-AI-Home-Renovation-Planner
```

### 2\. Create a virtual environment

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

**Mac/Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3\. Install dependencies

```bash
pip install -r requirements.txt
```

### 4\. Set up Environment Variables

Create a `.env` file in the root directory of the project and add your Google API key:

```ini
# .env
GOOGLE_API_KEY=your_actual_api_key_here
GEMINI_API_KEY=your_actual_api_key_here
```

---

## ▶️ Usage

1.  **Start the application:**

    ```bash
    streamlit run frontend.py
    ```

2.  **Access the UI:**
    Open your browser to the URL provided in the terminal (usually `http://localhost:8501`).

3.  **How to use:**

    - **Upload:** Go to the sidebar and upload a photo of your room. Categorize it as "Current Room".
    - **Plan:** Type a command like: _"Plan a modern renovation for this kitchen. I want white cabinets."_
    - **Result:** The AI will analyze the image, provide a cost estimate, and generate a new image of the renovated room.
    - **Edit:** Don't like the floor? Just say: _"Change the flooring to dark wood."_

---

## 📂 Project Structure

```text
├── agent.py           # Core logic: Defines Agents, Routing, and Pipelines
├── frontend.py        # User Interface: Streamlit app & State Management
├── tools.py           # Tools: Image generation, file versioning, & editing
├── requirements.txt   # Dependencies: adk, streamlit, google-genai
├── .env               # Secrets: API Keys (Not committed to Git)
├── .gitignore         # Git configuration
└── README.md          # Documentation
```

---

## 🤝 Contributing

Contributions are welcome\! Please feel free to submit a Pull Request.

1.  Fork the project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.
