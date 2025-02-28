import openai 
from utils import call_chatgpt_api_all_chats, stream_process_chatgpt_response
from secret import naveen_key as key 
import re 
import time 
from benefits.eligibility_check import eligibility_check

openai.api_key = key
system_prompt = open("benefits/prompts/system_prompt.txt").read()
extract_prompt = open("benefits/prompts/uncertain_prompt.txt").read()

def get_situation_llm(user_input,all_messages):
    """Extract information from a user's input
    
    Arguments:
        user_input: Current user situation
        all_messages: All the previous messages
        
    Returns: Response, which is the extracted information"""

    new_messages = [{'role': 'system', 'content': extract_prompt}] + all_messages
    new_messages.append({'role': 'user', 'content': user_input})
    extracted_info = call_chatgpt_api_all_chats(new_messages,stream=False).strip()
    return extracted_info

def get_benefit_info(situation,all_messages):
    """Given a situation and all the messages, get info on their benefits
    
    Arguments:
        situation: String, the user's current situation
        all_messages: List of previous messages
    
    Returns: String, info on their current benefit eligibilities"""
    
    extracted_info = get_situation_llm(situation,all_messages)
    print("The extracted info is {}".format(extracted_info))

    pattern = r"\[Situation\](.*?)\[/Situation\]"
    eligibility_info = re.sub(
        pattern,
        lambda m: eligibility_check(m.group()),  # Pass the matched content as a string
        extracted_info,
        flags=re.DOTALL
    )
 
    return eligibility_info


def analyze_benefits(situation, all_messages,model):
    """Given a situation and a CSV, get the information from the CSV file
    Then create a prompt
    
    Arguments:
        situation: String, what the user requests
        csv_file_path: Location with the database
        
    Returns: A string, the response from ChatGPT"""

    if model == 'chatgpt':
        print("Using ChatGPT")
        all_message_list = [{'role': 'system', 'content': 'You are a Co-Pilot tool for CSPNJ, a peer-peer mental health organization. Please provide information on benefit eligibility'}] + all_messages + [{'role': 'user', 'content': situation}]
        time.sleep(4)

        response = call_chatgpt_api_all_chats(all_message_list)
        yield from stream_process_chatgpt_response(response)
        return 

    eligibility_info = get_benefit_info(situation,all_messages)

    constructed_messages = [{'role': 'system', 'content': system_prompt}] + all_messages
    constructed_messages.append({'role': 'user', 'content': situation})
    constructed_messages.append({'role': 'user', 'content': 'Eligible Benefits: {}'.format(eligibility_info)})

    response = call_chatgpt_api_all_chats(constructed_messages,stream=True,max_tokens=750)
    yield from stream_process_chatgpt_response(response)