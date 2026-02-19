# PeerCopilot: A Language Model-Powered Assistant for Behavioral Health Organizations
<p align="center">
    <img src="./img/small_pull.png" width="512">
</p>

This repository contains the implementation for the paper **"PeerCopilot: A Language Model-Powered Assistant for Behavioral Health Organizations"** (IAAI 2025).

**Paper:** [arXiv:2511.21721](https://arxiv.org/abs/2511.21721) | [PDF](https://arxiv.org/pdf/2511.21721)

This work was done by Gao Mo*, Naveen Raman*, Megan Chai, Cindy Peng, Shannon Pagdon, Nev Jones, Hong Shen, Peggy Swarbrick, Fei Fang.

**TL;DR**

Peer-run behavioral health organizations offer holistic wellness support by combining mental health services with assistance for needs such as housing, employment, and income. However, staffing and expertise limitations hinder behavioral health organizations, making meeting all service user needs difficult. We address this issue through PeerCoPilot, a large language model (LLM)-powered assistant that helps peer providers create wellness plans, construct step-by-step goals, and find resources for these goals. Because information reliability is critical for peer providers, we designed PeerCoPilot to rely on information verified by peer providers via retrieval augmented generation. We conducted human evaluations with 15 peer providers and 6 service users and found that both groups overwhelmingly supported using PeerCoPilot. We show that PeerCoPilot provides more reliable and specific information than a baseline LLM. PeerCoPilot is now used by a group of peer providers at cspnj, a large behavioral health organization serving over 10,000 service users, and we are actively expanding PeerCoPilot's use.  


## Setup

### Installation

To set up the backend environment, first clone this repository:

```bash
git clone https://github.com/chengolivia/community_services_llm.git
cd community_services_llm
```

Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install Python dependencies:

```bash
cd backend
pip install -r requirements.txt
```

Install frontend dependencies:

```bash
cd ../frontend
npm install
```

Set up environment variables. Create a .env file in the backend directory with:

```bash
OPENAI_API_KEY=your_key_here
DATABASE_URL=your_database_url
RESOURCE_DB_URL=your_resource_database_url
GOOGLE_API_KEY=your_google_api_key
BRAVE_API_KEY=your_brave_api_key
SECRET_KEY=your_secret_key
HF_TOKEN=your_huggingface_token
```

### Running the Application

Start the backend server:

```bash
cd backend
npm run start
```

In a separate terminal, start the frontend:

```bash
cd frontend
npm start
```

PeerCoPilot will be available at:

http://localhost:3000/ (frontend)
http://127.0.0.1:8000/ (backend API)

### Extending to New Organizations
To extend this to new organizations, prepare a file called `<name>_resources.txt` in the backend/data folder
Next, scrape the resources by running
```bash
python scrape_resources.py --org_name {name} --location "<location/state>"
```
Finally, add this new organization to `Home.js` and `submodules.py`.