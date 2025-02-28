import openai 
import numpy as np
from sentence_transformers import SentenceTransformer
import time 
import re

from utils import *
import json 
from resources.rag_utils import * 
from secret import naveen_key as key 
import torch
import concurrent.futures
from benefits.eligibility_check import eligibility_check

openai.api_key = key
csv_file_path = "resources/data/EPINET_resource_with_descriptions.csv"

print('Finished loading!')

if torch.cuda.is_available():
    print("CUDA is available!")
    model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2',device='cuda')
else:
    model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

documents, names, descriptions, urls, phones = process_resources(csv_file_path)
documents_by_guidance = process_guidance_resources(['human_resource', 'peer', 'crisis', 'trans'])

print('Finished processing!')

saved_models = {}
for guidance, doc_list in documents_by_guidance.items():
    embeddings_file_path = f"results/saved_embedding_{guidance}.npy"
    embeddings = load_embeddings(embeddings_file_path, doc_list, model)
    saved_models[guidance] = create_faiss_index(embeddings)

print('Finished guiding!')

# Process main documents
file_path = "results/saved_embedding.npy"
embeddings = load_embeddings(file_path, documents, model)
main_index = create_faiss_index(embeddings)

print('Finished creating main index!')

mental_health_system_prompt = open("mental_health/prompts/mental_health_prompt.txt").read()
question_prompt = open("mental_health/prompts/question_prompts.txt").read()
summary_prompt = open("mental_health/prompts/EPINET_summary.txt").read()
resource_prompt = open("mental_health/prompts/resource_prompt.txt").read()
which_resource_prompt = open("mental_health/prompts/which_resource.txt").read()

def get_questions_resources(situation,all_messages):
    """Process user situation + generate questions and resources

    Arguments:
        situation: String, last message user sent
        all_messages: List of dictionaries, with all the messages

    Returns: String response, with resources and questions, 
        and a string, containing a dictionary on which 
        external resources to load """
    
    start = time.time() 
    all_message_list = [[{'role': 'system', 'content': mental_health_system_prompt}]+all_messages+[{"role": "user", "content": situation}]]
    all_message_list.append([{'role': 'system', 'content': question_prompt}]+all_messages+[{"role": "user", "content": situation}])
    all_message_list.append([{'role': 'system', 'content': resource_prompt}]+all_messages+[{"role": "user", "content": situation}])
    all_message_list.append([{'role': 'system', 'content': which_resource_prompt}]+[{'role': 'user', 'content': i['content'][:1000]} for i in all_messages if i['role'] == 'user']+[{"role": "user", "content": situation}])

    with concurrent.futures.ThreadPoolExecutor() as executor:
        initial_responses = list(executor.map(lambda s: call_chatgpt_api_all_chats(s, stream=False), all_message_list))
    start = time.time()

    initial_responses = list(initial_responses)

    pattern = r"\[Resource\](.*?)\[\/Resource\]"
    matches = re.findall(pattern,str(initial_responses[2]),flags=re.DOTALL)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        resources = list(executor.map(lambda s: analyze_situation_rag(s), matches))
    pattern = r"\[Situation\](.*?)\[/Situation\]"
    resources = "\n\n\n".join(resources)

    response = "\n".join(["SMART Goals: {}\n\n\n".format(initial_responses[0]),
                          "Questions: {}\n\n\n".format(initial_responses[1]),
                          "Resources (use only these resources): {}".format(resources)])
    which_external_resources = initial_responses[3]

    return response, which_external_resources

def analyze_resource_situation(situation, all_messages,model):
    """Process user situation + generate SMART goals, etc.

    Arguments:
        situation: String, last message user sent
        all_messages: List of dictionaries, with all the messages
        model: String, either chatgpt or copilot 
        
    Returns: Streaming response in text"""
    
    if model == 'chatgpt':
        all_message_list = [{'role': 'system', 'content': 'You are a Co-Pilot tool for CSPNJ, a peer-peer mental health organization. Please provider helpful responses to the client'}] + all_messages + [{'role': 'user', 'content': situation}]
        time.sleep(4)
        response = call_chatgpt_api_all_chats(all_message_list,max_tokens=750)
        yield from stream_process_chatgpt_response(response)
        return 

    start = time.time()
    response, which_external_resources = get_questions_resources(situation,all_messages)
    print("Took {} time for first".format(time.time()-start))
    start = time.time()
    try:
        which_external_resources = json.loads(which_external_resources.strip()) 
    except:
        which_external_resources = {}

    full_situation = "\n".join([i['content'] for i in all_messages if i['role'] == 'user' and len(i['content']) < 500] + [situation])
    rag_info = analyze_situation_rag_guidance(full_situation, which_external_resources)
    print("RAG took {}".format(time.time()-start))

    new_message = [{'role': 'system', 'content': summary_prompt}]
    new_message += [{'role': 'system', 'content': rag_info}]
    new_message += all_messages+[{"role": "user", "content": situation}, {'role': 'user' , 'content': response}]
    response = call_chatgpt_api_all_chats(new_message,stream=True,max_tokens=1000)
    yield from stream_process_chatgpt_response(response)

# def analyze_resource_situation(situation, all_messages,text_model):
#     """Process user situation + find the relevant resources.

#     Arguments:
#         situation: String, last message user sent
#         all_messages: List of dictionaries, with all the messages
#         text_model: String, either chatgpt or copilot 
        
#     Returns: Streaming response in text"""

#     if text_model == 'chatgpt':
#         all_message_list = [{'role': 'system', 'content': 'You are a Co-Pilot tool for CSPNJ, a peer-peer mental health organization. Please provide resourecs to the client'}] + all_messages + [{'role': 'user', 'content': situation}]
#         time.sleep(4)
#         response = call_chatgpt_api_all_chats(all_message_list,max_tokens=500)
#         yield from stream_process_chatgpt_response(response)

#     full_situation = "\n".join([i['content'] for i in all_messages if i['role'] == 'user']+[situation])

#     response = analyze_situation_rag(full_situation,k=10)
    
#     stream_response = call_chatgpt_api_all_chats([{'role': 'system', 'content': 'You are a helpful assistant who formats the list of resources provided in a nice Markdown format. Give the list of the most relevant resources along with explanations of why they are relevant to the situation.'},{'role': 'user','content': response}],max_tokens=500)
    
#     yield from stream_process_chatgpt_response(stream_response)
    

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