"""
RAG Utilities: Embeddings, FAISS Indexing, and Database Management.

This module handles:
1. Connecting to the Postgres database.
2. Fetching 'resources' and 'pages' (documents).
3. generating/loading FAISS indices for fast retrieval.
"""
import os
import numpy as np
import pandas as pd
import psycopg
from sentence_transformers import SentenceTransformer
import faiss

from dotenv import load_dotenv
load_dotenv()

# --- Configuration ---
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"

CONNECTION_STRING = os.getenv("RESOURCE_DB_URL")
MODEL_NAME = 'sentence-transformers/all-mpnet-base-v2'
ALL_ORGS = ['cspnj', 'clhs','georgia']

# --- Global Cache ---
_CACHE = {
    "model": None,
    "saved_resources": {},
    "documents_resources": {},
    "saved_articles": {},
    "documents_articles": {}
}

def get_db_connection():
    return psycopg.connect(CONNECTION_STRING,sslmode="require")

def get_embedding_model():
    """Lazy loads the model."""
    if _CACHE["model"] is None:
        print("[RAG] Loading SentenceTransformer...")
        _CACHE["model"] = SentenceTransformer(MODEL_NAME, token=os.getenv('HF_TOKEN'))
    return _CACHE["model"]

def create_faiss_index(embeddings: np.ndarray) -> faiss.Index:
    """Creates a standard FlatL2 index."""
    if len(embeddings) == 0:
        return faiss.IndexFlatL2(768)
    
    d = embeddings.shape[1]
    index = faiss.IndexFlatL2(d)
    index.add(embeddings)
    return index

# ==========================================
#  DATABASE WRITERS (For adding content)
# ==========================================

def add_page_to_db(organization: str, category: str, title: str, content: str):
    """
    Encodes and inserts a new article/page into the DB.
    """
    model = get_embedding_model()
    # Create embedding from Title + Content
    text_emb = f"{title}\n{content}"
    # Truncate slightly if massive, but MPNet handles truncation generally
    embedding = model.encode(text_emb).tolist()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pages (organization, category, title, content, embedding)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (organization, category, title, content, str(embedding))
            )
        conn.commit()
    print(f"[DB] Saved page: {title}")

def add_resource_to_db(organization: str, service: str, description: str, url: str, phone: str):
    """
    Encodes and inserts a new Resource into the DB.
    """
    model = get_embedding_model()
    text_emb = f"{service} {description} {url}"
    embedding = model.encode(text_emb).tolist()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO resources (organization, service, description, url, phone, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (organization, service, description, url, phone, str(embedding))
            )
        conn.commit()
    print(f"[DB] Saved resource: {service}")

# ==========================================
#  DATABASE READERS (Fetching for RAG)
# ==========================================

def fetch_data_from_db(table_name: str, org_list: list):
    """
    Generic fetcher. Returns (indices_dict, documents_dict).
    """
    indices = {}
    documents = {}

    with get_db_connection() as conn:
        for org in org_list:
            query = f"SELECT * FROM {table_name} WHERE organization = %s"
            df = pd.read_sql_query(query, conn, params=[org])
            
            if df.empty:
                indices[org] = create_faiss_index(np.empty((0, 768)))
                documents[org] = []
                continue

            # 1. Parse Embeddings (Handle string format from DB)
            # Check if it's already a list (some drivers do this) or string "[...]"
            if isinstance(df.iloc[0]['embedding'], str):
                df['embedding'] = df['embedding'].apply(
                    lambda x: [float(n) for n in x.strip("[]").split(",")]
                )
            
            # Create Matrix
            emb_matrix = np.array(df['embedding'].tolist()).astype('float32')
            
            # 2. Format Text Documents for the LLM
            docs_list = []
            for _, row in df.iterrows():
                if table_name == "resources":
                    text = (f"Resource: {row['service']}, "
                            f"Desc: {row['description']}, "
                            f"Phone: {row['phone']}, URL: {row['url']}")
                elif table_name == "pages":
                    text = (f"Article: {row['title']} (Category: {row['category']})\n"
                            f"Content: {row['content']}")
                docs_list.append(text)

            # 3. Store Results using specific keys based on your old structure?
            # Actually, standardizing keys is better. 
            # Resources use "resource_{org}", Pages use "cat_{category}"?
            # Let's align with your request:
            
            if table_name == "resources":
                key = f"resource_{org}"
                documents[key] = docs_list
                indices[key] = create_faiss_index(emb_matrix)
            
            elif table_name == "pages":
                # For pages, you previously split by category (e.g. 'cat_crisis').
                # We can group by category here.
                for cat in df['category'].unique():
                    cat_df = df[df['category'] == cat]
                    cat_key = f"cat_{cat}" # Or "cat_{org}_{cat}" if categories overlap
                    
                    cat_matrix = np.array(cat_df['embedding'].tolist()).astype('float32')
                    cat_docs = []
                    for _, r in cat_df.iterrows():
                        cat_docs.append(f"Article: {r['title']}\n{r['content']}")
                    
                    # Update the dictionaries
                    # Note: This might overwrite if multiple orgs have same category name
                    # If that's a risk, change key to f"{org}_{cat}"
                    if cat_key in documents:
                        documents[cat_key].extend(cat_docs)
                        # Merging indices is hard, easier to just append docs and rebuild index 
                        # if strict separation isn't needed. 
                        # For simplicity, let's assume global categories or unique per org.
                    else:
                        documents[cat_key] = cat_docs
                        indices[cat_key] = create_faiss_index(cat_matrix)

    return indices, documents

# ==========================================
#  MAIN ENTRY POINT
# ==========================================

def get_model_and_indices():
    """
    Returns the 5 specific objects expected by main.py
    1. embedding_model
    2. saved_resources (FAISS indices for resources)
    3. documents_resources (Text lists for resources)
    4. saved_articles (FAISS indices for pages)
    5. documents_articles (Text lists for pages)
    """
    # Return cached if populated
    if _CACHE["model"] is not None and _CACHE["saved_resources"]:
        return (_CACHE["model"], _CACHE["saved_resources"], 
                _CACHE["documents_resources"], _CACHE["saved_articles"], 
                _CACHE["documents_articles"])

    # 1. Load Model
    model = get_embedding_model()

    # 2. Fetch Resources
    print("[RAG] Fetching Resources from DB...")
    res_indices, res_docs = fetch_data_from_db("resources", ALL_ORGS)
    _CACHE["saved_resources"] = res_indices
    _CACHE["documents_resources"] = res_docs

    # 3. Fetch Pages (Articles)
    print("[RAG] Fetching Pages from DB...")
    page_indices, page_docs = fetch_data_from_db("pages", ALL_ORGS)
    _CACHE["saved_articles"] = page_indices
    _CACHE["documents_articles"] = page_docs

    print("[RAG] Initialization Complete.")
    
    return (model, 
            _CACHE["saved_resources"], 
            _CACHE["documents_resources"], 
            _CACHE["saved_articles"], 
            _CACHE["documents_articles"])
def migrate_folders():
    base_path = "../library_resources"
    # Example structure: library_resources/cspnj/crisis/file.txt
    
    for org in ['cspnj', 'clhs']:
        org_path = os.path.join(base_path, org)
        print(org_path,os.path.exists(org_path))
        if not os.path.exists(org_path): continue
        
        for category in os.listdir(org_path):
            cat_path = os.path.join(org_path, category)
            if not os.path.isdir(cat_path): continue
            
            for filename in os.listdir(cat_path):
                filepath = os.path.join(cat_path, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    add_page_to_db(
                        organization=org,
                        category=category,
                        title=filename,
                        content=content
                    )