You are a Senior Full‑Stack AI Engineer with DevOps expertise. Your mission is to build a complete, production‑ready **Agentic Food Recommendation System** with a modern, catchy name (choose one from the suggestions above or propose a better one). The system must be designed to run on **zero‑cost / low‑cost infrastructure** by leveraging free tiers of popular cloud services.

### **Project Overview**
- **Frontend:** React + TypeScript + Vite, styled with **shadcn/ui**. Deployed on **Vercel** (free tier).
- **Backend:** Python FastAPI, containerized with Docker. Deployed on **AWS Free Tier** (EC2 t2.micro or Lambda + API Gateway).
- **Database & Vector Store:** Use free tiers of **Pinecone** (vector DB) and **Supabase** (PostgreSQL) to keep costs at $0.
- **AI & Agentic Workflow:** LangChain / LlamaIndex with OpenAI API (costs a few cents per user, but you can use a local model via Ollama to stay completely free – optional).

The system must:
1.  **Source Data:** Automatically search and select the best Kaggle datasets for Indian & international cuisine.
2.  **Learn:** Ingest data into a RAG pipeline (vector embeddings + metadata store).
3.  **Engage Users:** Through a chat interface, collect dietary preferences, allergies, available ingredients, and max cooking time.
4.  **Reason & Recommend:** Use an AI Agent to retrieve, filter, and rank recipes based on user constraints.
5.  **Enhance:** For each recipe, fetch cooking methods for different appliances (Instant Pot, Oven, Stovetop) and relevant YouTube tutorial links.
6.  **Iterate:** Allow follow‑up prompts to refine recommendations (e.g., “I don’t have chicken, what else?”).

---

### **Technical Architecture (Zero‑Cost Focus)**
#### **Frontend (Vercel)**
- Built with React + TypeScript, Vite for fast builds.
- UI components from **shadcn/ui** (Cards, Tabs, Sliders, Checkboxes, Input with tags).
- Communicates with backend via REST APIs (or WebSockets for real‑time chat).
- Deployed on Vercel’s free tier (automatic HTTPS, global CDN).

#### **Backend (AWS Free Tier)**
- **Option A (Simpler):** EC2 t2.micro instance (free for 750 hours/month). Run the FastAPI app inside a Docker container. Use `docker-compose` to also run a local ChromaDB (vector store) and PostgreSQL (if not using Supabase). *Note: This keeps everything on one machine but may hit storage limits.*
- **Option B (More Serverless):** Package FastAPI as a Lambda function using Mangum, expose via API Gateway (free tier includes 1 million requests/month). Use Supabase (PostgreSQL) and Pinecone (vector DB) as external services – both have generous free tiers.
- **Recommendation:** Use **Option B** for true zero‑cost scaling, but **Option A** is easier to develop and deploy initially. The agent should provide instructions for both.

#### **Data Stores (All Free Tiers)**
- **Vector Database:** Pinecone (free tier: 1 pod, up to 100K vectors) – perfect for recipe embeddings.
- **Structured Database:** Supabase (free tier: 500 MB database, authentication, real‑time subscriptions) – store recipe metadata (cuisine, time, diet, YouTube links).
- **Alternative:** If you prefer self‑hosted, use ChromaDB (file‑based) + SQLite, but then you must manage backups.

#### **AI & Agent Logic**
- Use **LangChain** or **LlamaIndex** to build the agent.
- LLM: OpenAI GPT‑3.5‑turbo (costs ~$0.002 per recommendation) – or switch to a free local model via **Ollama** (e.g., Llama 3) for completely zero cost (the agent should document both options).
- The agent maintains a `UserProfile` state (preferences, ingredients, time) across the conversation.

---

### **Detailed Implementation Steps for the AI Agent**
You will generate the entire project code, including:

1. **Data Engineering**
   - Write a Python script that uses the Kaggle API to search and download the most suitable datasets (e.g., Indian Food Cuisine, Food.com Recipes, etc.).
   - Clean and preprocess: handle missing values, create text chunks for embeddings, extract metadata (time, diet, cuisine).

2. **Backend (FastAPI)**
   - Endpoints:
     - `POST /api/chat` – accepts `{ message: string, history: array }`, returns assistant reply.
     - `GET /api/recipes/{id}` – returns full recipe details.
   - Agent logic:
     - Maintain conversation state in memory (or use a simple session store).
     - Use a **Task Router** to decide actions: extract preferences, search recipes, answer general questions, refine results.
     - For recipe search: first filter by structured metadata (time, diet, avoided ingredients) using Supabase queries, then perform vector similarity on the remaining recipes using Pinecone.
   - YouTube integration: Use YouTube Data API v3 (free quota) to search for "[Recipe Name] recipe" and store the best video link in Supabase.

3. **Frontend (React + shadcn/ui)**
   - Clean chat interface with message bubbles.
   - Agent can render interactive forms (checkboxes, sliders, tag inputs) inside the chat for smooth preference collection.
   - Recipe cards displayed in a grid; modal with tabs for different cooking methods and embedded YouTube player.
   - Use React Context or Zustand for state management.

4. **Deployment Configuration**
   - **Frontend:** `vercel.json` for build settings and API proxying (if needed).
   - **Backend:** `Dockerfile` and `docker-compose.yml` for EC2 deployment; also provide instructions for deploying as a Lambda (with `serverless.yml` template).
   - Environment variables for API keys (OpenAI, Pinecone, Supabase, YouTube) – never hardcode.

5. **Edge Cases & Extensions (Must Handle)**
   - Ingredient substitution suggestions.
   - Cold start (no ingredients) → recommend based on preferences only.
   - No results → relax constraints gradually.
   - Dietary conflicts (e.g., non‑veg query for vegetarian user).
   - Multi‑turn refinement (e.g., change protein).
   - Rate limiting and error handling for external APIs.

6. **Documentation**
   - `README.md` with project overview, setup instructions, architecture diagram (text‑based), and cost breakdown (showing how everything stays free).
   - API documentation (auto‑generated via FastAPI).
   - A short video script or screenshots demonstrating the flow.

---

### **Constraints & Deliverables**
- **Code Quality:** Follow PEP 8, include type hints, use environment variables.
- **Cost Awareness:** Clearly document which services are used on free tiers and any potential costs if usage exceeds limits.
- **Final Output:** Provide all code files in a structured format (use markdown code blocks for each file). Include a `requirements.txt` (backend) and `package.json` (frontend). Summarize the architecture in a few paragraphs.

Now, proceed to build this project from scratch. Start by listing the Kaggle datasets you have selected and why, then generate the complete codebase.