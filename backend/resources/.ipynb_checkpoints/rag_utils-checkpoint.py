import pandas as pd
import faiss
import os 
import numpy as np

def load_embeddings(file_path, documents, model):
    """Load or compute embeddings and save them
    
    Arguments:
        file_path: String, location of the file with embeddings
        documents: List of strings, the documents to recreate embeddings
        model: Some sentence transformer model
    
    Returns: Numpy array of the embeddings"""

    if os.path.exists(file_path):
        return np.load(file_path)
    else:
        embeddings = model.encode(documents, convert_to_tensor=False, show_progress_bar=True)
        embeddings = np.array(embeddings)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        np.save(file_path, embeddings)
        return embeddings

def process_resources(csv_file_path):
    """Load and process resources data into a list of strings
    
    Arguments:
        csv_file_path: String, location of all the resources 
            in a csv file
    
    Returns: List of strings, each represents a document"""

    resources_df = pd.read_csv(csv_file_path)
    names = list(resources_df['Organization'])
    descriptions = list(resources_df['Generated Description'])
    urls = list(resources_df['Website'])
    phones = list(resources_df['Phone'])

    return ["{}: {}".format(names[i], descriptions[i]) for i in range(len(names))], names, descriptions, urls, phones

def process_guidance_resources(guidance_types):
    """Load guidance-specific resources and process them
    
    Arguments:
        guidance_types: Dictionary, mapping which guidance types are
            true/false for whether to process
    
    Returns: List of documents for each type of guidance"""

    documents_by_guidance = {}
    for guidance in guidance_types:
        with open(f"mental_health/prompts/resources/{guidance}.txt") as file:
            resource_data = [line for line in file.read().split("\n") if len(line) > 10]
            documents_by_guidance[guidance] = [f"{line}: {resource_data[i]}" for i, line in enumerate(resource_data)]
    return documents_by_guidance

def create_faiss_index(embeddings):
    """Create and return FAISS index
    
    Arguments:
        embeddings: Numpy array representing embeddings
    
    Returns: FAISS index computed from the embeddings"""
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    return index
