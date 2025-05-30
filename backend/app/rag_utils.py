import pandas as pd
import faiss
import os 
import numpy as np
from sentence_transformers import SentenceTransformer

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

def process_resources(resource_dict):
    """Load and process resources data into a list of strings
    
    Arguments:
        csv_file_path: String, location of all the resources 
            in a csv file
    
    Returns: List of strings, each represents a document"""

    d = {}
    for key in resource_dict:
        csv_file_path = resource_dict[key]
        resources_df = pd.read_csv(csv_file_path)
        names = list(resources_df['service'])
        descriptions = list(resources_df['description'])
        urls = list(resources_df['url'])
        phones = list(resources_df['phone'])

        formatted_documents = [f"Resource: {names[i]}, URL: {urls[i]}, Phone: {phones[i]}, Description: {descriptions[i]}" for i in range(len(descriptions))]
        d[key] = formatted_documents

    return d

def process_guidance_resources(guidance_types):
    """Load guidance-specific resources and process them
    
    Arguments:
        guidance_types: Dictionary, mapping which guidance types are
            true/false for whether to process
    
    Returns: List of documents for each type of guidance"""

    documents_by_guidance = {}
    for guidance in guidance_types:
        with open(f"prompts/external/{guidance}.txt", encoding="utf-8") as file:
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


def get_all_embeddings(resource_dict):
    """Get all the saved embeddings to run RAG
    
    Arguments:
        resource_list: String, path to a CSV file with all the resources
    
    Returns: A SentenceTransforemr Model and a dictionary
        mapping a string to an Index for different embeddins"""

    model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

    org_resources = process_resources(resource_dict)

    documents = process_guidance_resources(['human_resource', 'peer', 'crisis', 'trans'])

    saved_indices = {}
    for guidance, doc_list in documents.items():
        embeddings_file_path = f"saved_embeddings/saved_embedding_{guidance}.npy"
        embeddings = load_embeddings(embeddings_file_path, doc_list, model)
        saved_indices[guidance] = create_faiss_index(embeddings)

    for key in org_resources:
        documents['resource_{}'.format(key)] = org_resources[key]
        file_path = "saved_embeddings/saved_embedding_{}.npy".format(key)
        embeddings = load_embeddings(file_path, documents['resource_{}'.format(key)], model)
        saved_indices['resource_{}'.format(key)] = create_faiss_index(embeddings)

    return model, saved_indices, documents
