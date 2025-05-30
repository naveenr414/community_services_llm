import openai 
import concurrent.futures
import re
import json 
import os 
import numpy as np

from app.eligibility_check import eligibility_check
from app.rag_utils import get_all_embeddings
from app.utils import (
    call_chatgpt_api_all_chats,
    stream_process_chatgpt_response,
    get_all_prompts,
    call_chatgpt_with_functions,
)

openai.api_key = os.environ.get("SECRET_KEY")

internal_prompts, external_prompts = get_all_prompts()
model, saved_indices, documents = get_all_embeddings({'cspnj': 'data/cspnj.csv','clhs': 'data/clhs.csv'})

def get_questions_resources(situation,all_messages,organization,k: int = 25):
    """Process user situation + generate questions and resources

    Arguments:
        situation: String, last message user sent
        all_messages: List of dictionaries, with all the messages

    Returns: String response, with resources and questions, 
        and a string, containing a dictionary on which 
        external resources to load """
    
    all_message_list = []
    
    for prompt in ['goal','followup_question','resource','which_resource','benefit_extract']:
        all_message_list.append([{'role': 'system', 'content': internal_prompts[prompt].replace("[Organization]",organization)}]+all_messages+[{"role": "user", "content": situation}])
    with concurrent.futures.ThreadPoolExecutor() as executor:
        initial_responses = list(executor.map(lambda s: call_chatgpt_api_all_chats(s, stream=False), all_message_list))
    initial_responses = list(initial_responses)

    # Combine prompts with external information on resources
    pattern = r"\[Resource\](.*?)\[\/Resource\]"
    matches = re.findall(pattern,str(initial_responses[2]),flags=re.DOTALL)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        resources = list(executor.map(lambda s: extract_resources(s,{'resource_{}'.format(organization): True},k=k), matches))
    
    # Combine prompts with external information on benefits
    pattern = r"\[Situation\](.*?)\[/Situation\]"
    benefit_info = re.sub(
        pattern,
        lambda m: eligibility_check(m.group()),  # Pass the matched content as a string
        initial_responses[4],
        flags=re.DOTALL
    )
    if "Irrelevant" in benefit_info:
        benefit_info = ""
    else:
        constructed_messages = [{'role': 'system', 'content': internal_prompts['benefit_system']}] + [{'role': 'user', 'content': i['content'][:1000]} for i in all_messages if i['role'] == 'user']
        constructed_messages.append({'role': 'user', 'content': situation})
        constructed_messages.append({'role': 'user', 'content': 'Eligible Benefits: {}'.format(benefit_info)})
        benefit_info = call_chatgpt_api_all_chats(constructed_messages,stream=False)

    # Call modules with additional extra information
    which_external_resources = initial_responses[3]
    try:
        which_external_resources = json.loads(which_external_resources.strip()) 
    except:
        which_external_resources = {}
    full_situation = "\n".join([i['content'] for i in all_messages if i['role'] == 'user' and len(i['content']) < 500] + [situation])
    external_resources = extract_resources(full_situation,which_external_resources,k=k)


    # capture the raw "[Resource]...[/Resource]" output
    raw_resource_prompt = initial_responses[2]

    # build the normal response text
    sep = "\n\n\n"
    response = "\n".join([
        f"SMART Goals: {initial_responses[0]}",
        f"Questions: {initial_responses[1]}",
        "Resources (use only these resources):\n" + sep.join(resources),
        f"Benefit Info: {benefit_info}"
    ])

    # now return three things: 
    # 1) the string we already had, 
    # 2) the RAG hits, 
    # 3) the raw resource prompt
    return response, external_resources, raw_resource_prompt


def format_resources_for_user(situation, all_messages, organization, max_items: int = 3):
    """
    Turn raw RAG lines into [{"name","url","how_to_use"}, …].
    """
    _, raw_resources, __ = get_questions_resources(situation, all_messages, organization)
    formatted = []
    for entry in raw_resources[:max_items]:
        m = re.match(
            r"Resource:\s*(?P<name>[^,]+),\s*URL:\s*(?P<url>[^,]+),.*Description:\s*(?P<desc>.+)",
            entry,
            flags=re.IGNORECASE
        )
        if m:
            formatted.append({
                "name":       m.group("name").strip(),
                "url":        m.group("url").strip(),
                "how_to_use": m.group("desc").strip()
            })
        else:
            formatted.append({
                "name":       entry.strip(),
                "url":        "",
                "how_to_use": ""
            })
    return formatted


def format_additional_resources(raw_resource_prompt: str, max_items: int = 3):
    """
    Parse the raw [Resource]…[/Resource] output into a list of dicts:
      [{"name","url","action"}, …]
    """
    formatted = []
    block_re = (
        r"\[Resource\]\s*"
        r"Name:\s*(?P<name>.+?)\s*"
        r"URL:\s*(?P<url>\S+?)\s*"
        r"Action:\s*(?P<action>.+?)\s*"
        r"\[/Resource\]"
    )
    for m in re.finditer(block_re, raw_resource_prompt, flags=re.DOTALL|re.IGNORECASE):
        formatted.append({
            "name":   m.group("name").strip(),
            "url":    m.group("url").strip(),
            "action": m.group("action").strip()
        })
        if len(formatted) >= max_items:
            break
    return formatted



#NEW PLANNER APPROACH
def construct_response(situation, all_messages, model, organization):
    """
    1) Ask the model: is this a substantive request that needs SMART goals?
       -> JSON: {"needs_goals": true/false}
    2a) If false: one-shot vanilla chat (no goals).
    2b) If true: your existing SMART-goals + orchestration pipeline.
    """



    # -- 1) INTENT & verbosity CHECK tiny LLM call --
    intent_and_verbosity_msgs = [
    {
        "role": "system",
        "content": (
            "You’re a request analyzer.  "
            "Given one user message, answer **strictly** in JSON with two keys:\n"
            '  • "needs_goals": true if they want advice or help or concrete next steps;\n'
            '  • "verbosity": one of "brief","medium","deep", chosen based on how much detail they implicitly want.\n'
            "\n"
            "Examples:\n"
            '- User: "How are you?" → { "needs_goals": false, "verbosity": "brief" }\n'
            '- User: "I’m struggling to pay rent, please help me." → { "needs_goals": true, "verbosity": "medium" }\n'
            '- User: "I need a detailed plan to switch careers and build new skills." → { "needs_goals": true, "verbosity": "deep" }\n'
            "Return only valid JSON, no extra commentary."
        )
    },
    {"role": "user", "content": situation}
    ]
    meta_resp = call_chatgpt_api_all_chats(
        intent_and_verbosity_msgs,
        stream=False,
        max_tokens=40
    ).strip()

    

    try:
        meta = json.loads(meta_resp)
        needs_goals = meta.get("needs_goals", False)
        verbosity   = meta.get("verbosity", "medium")
    except:
        needs_goals = False
        verbosity   = "medium"

    # ← NEW DEBUG LOG
    print(f"[DEBUG] needs_goals={needs_goals}, verbosity={verbosity}")

    # -- 2a) if it's just small talk, do a pure chat reply --
    if not needs_goals:
        print("[DEBUG] taking small‐talk branch")
        chat_msgs = (
            [{"role": "system", "content":
              f"You are a helpful assistant for {organization}. Reply warmly and concisely."}]
            + all_messages
            + [{"role": "user", "content": situation}]
        )
        # STREAM the response back
        chat_resp = call_chatgpt_api_all_chats(chat_msgs, stream=True, max_tokens=500)
        yield from stream_process_chatgpt_response(chat_resp)
        return


    # If they implicitly want just the headlines…
    if verbosity == "brief":
        print("[DEBUG] taking brief GOALS branch")
        prompt = (
            f"You are a concise assistant for {organization}.  "
            "Given the user’s request, produce **up to three** SMART goals as bullet points, "
            "each in one short sentence, tailored exactly to their situation."
        )
        msgs = [{"role":"system","content":prompt}] + all_messages + [{"role":"user","content":situation}]
        yield from stream_process_chatgpt_response(
            call_chatgpt_api_all_chats(msgs, stream=True, max_tokens=20)
        )
        return

    # If they want the full orchestration…
    if verbosity == "deep":
        print("[DEBUG] verbosity=deep → using full orchestration with k=50")
        # bump max_tokens
        full_k = 50
    else:  # medium
        print("[DEBUG] verbosity=medium → using standard orchestration with k=25")
        full_k = 25


    # -- 2b) otherwise: we run our full SMART-goals + orchestration pipeline --

    # retaining the 'chatgpt' vs 'copilot' modes branch:
    if model == 'chatgpt':
        print("[DEBUG] model=chatgpt branch")
        msgs = (
            [{'role': 'system', 'content':
              f"You are a Co-Pilot tool for {organization}, a peer-peer support org."}]
            + all_messages
            + [{'role': 'user', 'content': situation}]
        )
        resp = call_chatgpt_api_all_chats(msgs, max_tokens=750)
        yield from stream_process_chatgpt_response(resp)
        return

    # the existing copilot pipeline:
    print("[DEBUG] copilot pipeline branch (SMART goals + orchestration)")
    initial_response, external_resources, raw_resource_prompt = get_questions_resources(
        situation, all_messages, organization, k=full_k
    )


    new_message = [{'role': 'system', 'content': internal_prompts['orchestration']}]
    new_message += [{'role': 'system', 'content': external_resources}]
    new_message += all_messages + [
        {"role": "user",    "content": situation},
        {"role": "user",    "content": initial_response}
    ]

    # 1) stream the main orchestration output as before
    response = call_chatgpt_api_all_chats(new_message, stream=True, max_tokens=1000)
    yield from stream_process_chatgpt_response(response)

    # 2b) now append only the actionable “Additional Resources” section
    addl_list = format_additional_resources(raw_resource_prompt, max_items=7)
    # build one big markdown chunk
    md = "### Additional Resources  <br/>\n*(Disclaimer: information may be inaccurate)*<br/><br/>\n"
    for idx, res in enumerate(addl_list, 1):
        md += f"{idx}. **{res['name']}**<br/>\n"
        if res['url']:
            md += f"   • [Link]({res['url']})<br/>\n"
        md += f"   • Action: {res['action']}<br/><br/>\n"

    # emit as a single SSE payload
    yield f"data: {md}\n\n"






def extract_resources(situation,which_indices,k=25):
    """Given a string, and a list of external resources to use
        find the most similar lines in the external resources
    
    Arguments:
        situation: String, what the user requests
        indices: Dictionary, mapping which 
            documents to use (guidances, e.g. crisis)
        
    Returns: A string, list of relevant lines"""
    ret = []

    for i in which_indices:
        if which_indices[i]:
            query_embedding = model.encode(situation, convert_to_tensor=False)
            _, I = saved_indices[i].search(np.array([query_embedding]), k=k)  # Retrieve top k resources
            ret += [":".join(documents[i][j].split(":")[1:]).strip() for j in I[0]]            
    return "\n".join(ret)

def get_benefit_demographics(user_input,all_messages):
    """Extract information from a user's input
    
    Arguments:
        user_input: Current user situation
        all_messages: All the previous messages
        
    Returns: Response, which is the extracted information"""

    new_messages = [{'role': 'system', 'content': internal_prompts['benefit_extract']}] + all_messages
    new_messages.append({'role': 'user', 'content': user_input})
    extracted_info = call_chatgpt_api_all_chats(new_messages,stream=False).strip()
    return extracted_info

def get_benefit_eligibility(situation,all_messages):
    """Given a situation and all the messages, get info on their benefits
    
    Arguments:
        situation: String, the user's current situation
        all_messages: List of previous messages
    
    Returns: String, info on their current benefit eligibilities"""
    
    extracted_info = get_benefit_demographics(situation,all_messages)

    pattern = r"\[Situation\](.*?)\[/Situation\]"
    eligibility_info = re.sub(
        pattern,
        lambda m: eligibility_check(m.group()),  # Pass the matched content as a string
        extracted_info,
        flags=re.DOTALL
    )
 
    return eligibility_info