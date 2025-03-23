import openai 
import numpy as np
from sentence_transformers import SentenceTransformer
import time 

from utils import *
from resources.rag_utils import *
# from rag_utils import *
from secret import naveen_key as key 
import torch

openai.api_key = key
# csv_file_path = "resources/data/all_resources.csv"
# csv_file_path = "data/all_resources_2025.csv"
csv_file_path = "resources/data/all_resources_2025_updated.csv"

if torch.cuda.is_available():
    print("CUDA is available!")
    model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2',device='cuda')
else:
    model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

documents, names, descriptions, urls, phones = process_resources(csv_file_path)
documents_by_guidance = process_guidance_resources(['human_resource', 'peer', 'crisis', 'trans'])

saved_models = {}
for guidance, doc_list in documents_by_guidance.items():
    embeddings_file_path = f"results/saved_embedding_{guidance}.npy"
    embeddings = load_embeddings(embeddings_file_path, doc_list, model)
    saved_models[guidance] = create_faiss_index(embeddings)

# Process main documents
file_path = "results/saved_embedding.npy"
embeddings = load_embeddings(file_path, documents, model)
main_index = create_faiss_index(embeddings)

print("Loaded!")

def analyze_resource_situation(situation, all_messages,text_model):
    """Process user situation + find the relevant resources.

    Arguments:
        situation: String, last message user sent
        all_messages: List of dictionaries, with all the messages
        text_model: String, either chatgpt or copilot 
        
    Returns: Streaming response in text"""

    if text_model == 'chatgpt':
        all_message_list = [{'role': 'system', 'content': 'You are a Co-Pilot tool for CSPNJ, a peer-peer mental health organization. Please provide resourecs to the client'}] + all_messages + [{'role': 'user', 'content': situation}]
        time.sleep(4)
        response = call_chatgpt_api_all_chats(all_message_list,max_tokens=500)
        yield from stream_process_chatgpt_response(response)

    full_situation = "\n".join([i['content'] for i in all_messages if i['role'] == 'user']+[situation])

    response = analyze_situation_rag(full_situation,k=10)
    stream_response = call_chatgpt_api_all_chats([{'role': 'system', 'content': 'You are a helpful assistant who formats the list of resources provided in a nice Markdown format. Give the list of the most relevant resources along with explanations of why they are relevant. Try to make sure resources are relevant to the location'},
                                                  {'role': 'user','content': response}],max_tokens=500)
    yield from stream_process_chatgpt_response(stream_response)

def analyze_situation_rag(situation,k=5):
    """Given a string, find the most similar resources using RAG
    
    Arguments:
        situation: String, what the user requests
        
    Returns: A string, list of relevant resources"""

    query_embedding = model.encode(situation, convert_to_tensor=False)
    _, I = main_index.search(np.array([query_embedding]), k=k)  # Retrieve top k resources
    retrieved_resources = [f"{names[i]}, URL: {urls[i]}, Phone: {phones[i]}, Description: {descriptions[i]}" for i in I[0]]
    return "\n".join(retrieved_resources)

def analyze_situation_rag_guidance(situation,relevant_guidance,k=25):
    """Given a string, and a list of external resources to use
        find the most similar lines in the external resources
    
    Arguments:
        situation: String, what the user requests
        relevant_guidance: Dictionary, mapping which 
            documents to use (guidances, e.g. crisis)
        
    Returns: A string, list of relevant lines"""

    ret = []

    for i in relevant_guidance:
        if relevant_guidance[i]:
            query_embedding = model.encode(situation, convert_to_tensor=False)
            _, I = saved_models[i].search(np.array([query_embedding]), k=k)  # Retrieve top k resources
            ret += [documents_by_guidance[i][j].split(":")[1].strip() for j in I[0]]            
    return "\n".join(ret)