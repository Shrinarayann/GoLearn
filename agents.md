
### **System Architecture Prompt: "The Three-Pass Study Companion"**

**Project Overview**
We are building an AI-powered educational platform that transforms raw study materials into a scientifically rigorous learning experience. The system combines the **Three-Pass Method** for comprehension with the **Leitner System (Spaced Repetition)** for long-term retention.

**1. Input Layer**

* **User Action:** Users create "Study Sessions" by uploading raw material.
* **Supported Formats:** PDF, PPT, Website Links, and Plain Text.

**2. The Agentic Study Core (Phase I: Comprehension)**
An **Orchestrator Agent** manages three specialized agents using a collaborative/consensus workflow. These agents analyze the input and run in parallel loops until their outputs are consistent and meet quality standards before presenting them to the user.

* **Agent A: Exploration (Pass 1):** Scans the material to generate a structural overview, high-level summary, and key topic identification.
* **Agent B: Engagement (Pass 2):** Performs a deep-dive analysis. It explains core details and specifically handles **multi-modal extraction** (interpreting and explaining diagrams/charts found in the input).
* **Agent C: Application (Pass 3):** Synthesizes the information to demonstrate practical application, critical analysis, and connection to broader concepts.

**3. The Testing & Retention Engine (Phase II: Retention)**
Once the user completes the study phase, the system transitions to active recall.

* **Testing Agent:** Generates questions based on the validated content from Phase I.
* **Leitner System Logic:**
* **Correct Answer:** The specific concept is promoted to a higher "Box" (reviewed less frequently/later).
* **Incorrect Answer:**
1. The concept is demoted to "Box 1" (reviewed sooner).
2. **Feedback Loop:** The system triggers the **Engagement Agent** to immediately re-explain the concept to the user to close the knowledge gap.



**4. Technical Stack (not comprehensive)**

* **LLM Backend:** Google Gemini Models via Google Cloud Vertex AI.
* **Framework:** Google Gen AI Agent SDK (ADK) for agent orchestration and tool use.

---
