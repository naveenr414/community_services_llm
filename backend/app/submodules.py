"""Core pipeline: resource extraction, refinement, and orchestration for responses.

This module exposes `construct_response` which calls RAG extraction and OpenAI
APIs to build streaming responses.
"""

import os
import openai
import json 
import re
import time
import concurrent.futures
import numpy as np

from app.rag_utils import get_model_and_indices
from app.tools import *
from app.utils import (
    call_chatgpt_api_all_chats,
    stream_process_chatgpt_response,
    get_all_prompts,
)

# Initialize
openai.api_key = os.environ.get("SECRET_KEY")
# NOTE: This eagerly loads embedding models and indices on import which can be
# expensive; consider lazy-loading in production to reduce startup time.
embedding_model, saved_resources, documents_resources, saved_articles, documents_articles = get_model_and_indices()
internal_prompts, external_prompts = get_all_prompts()


# ============================================================================
# Legacy RAG pipeline helpers (used for the "Old Version")
# ============================================================================

def extract_resources(
    embedding_model,
    saved_indices,
    documents,
    situation: str,
    which_indices: dict,
    k: int = 25,
) -> str:
    """
    Extract most similar resources using RAG.

    Args:
        embedding_model: SentenceTransformer model
        saved_indices: Dictionary of FAISS indices
        documents: Dictionary of document lists
        situation: User's situation text
        which_indices: Dictionary indicating which indices to search
        k: Number of results to retrieve

    Returns:
        Newline-separated resource strings
    """
    results = []

    for index_name, should_search in which_indices.items():
        if not should_search:
            continue

        # Encode query
        query_embedding = embedding_model.encode(
            situation,
            convert_to_tensor=False,
        )

        # Search index
        _, indices = saved_indices[index_name].search(
            np.array([query_embedding]),
            k=k,
        )

        # Collect results
        doc_list = documents[index_name]
        results.extend(
            [doc_list[j] for j in indices[0] if j < len(doc_list)]
        )

    return "\n".join(results)


def deduplicate_resources(resources: list) -> list:
    """
    Remove duplicate resources from list.

    Args:
        resources: List of resource strings

    Returns:
        Deduplicated list of resources
    """
    all_lines = "\n".join(resources).split("\n")
    seen_resources = set()
    unique_lines = []

    idx = 0
    while idx < len(all_lines):
        line = all_lines[idx]

        # Found a new resource header
        if "Resource:" in line and line not in seen_resources:
            seen_resources.add(line)
            unique_lines.append(line)
            idx += 1

            # Include continuation lines
            while idx < len(all_lines) and "Resource:" not in all_lines[idx]:
                unique_lines.append(all_lines[idx])
                idx += 1

        # Skip duplicate resource
        elif line in seen_resources:
            idx += 1
            while idx < len(all_lines) and "Resource:" not in all_lines[idx]:
                idx += 1

        # Skip non-resource line
        else:
            idx += 1

    return unique_lines


def get_questions_resources(
    situation: str,
    all_messages: list,
    organization: str,
    k: int = 5,
) -> tuple:
    """
    Process user situation and generate goals, questions, and resources.

    This reproduces the legacy "old" pipeline behavior.
    """
    print(f"[Pipeline] Starting at {time.time()}")

    # Build message lists for parallel processing
    prompts = ["goal", "followup_question", "resource"]
    message_lists = []

    for prompt_name in prompts:
        system_msg = internal_prompts[prompt_name].replace(
            "[Organization]",
            organization,
        )
        messages = (
            [{"role": "system", "content": system_msg}]
            + all_messages
            + [{"role": "user", "content": situation}]
        )
        message_lists.append(messages)

    # Parallel API calls
    with concurrent.futures.ThreadPoolExecutor() as executor:
        responses = list(
            executor.map(
                lambda msgs: call_chatgpt_api_all_chats(msgs, stream=False),
                message_lists,
            )
        )

    print(f"[Pipeline] Initial responses at {time.time()}")

    # Extract resource mentions from response
    pattern = r"\[Resource\](.*?)\[\/Resource\]"
    resource_mentions = re.findall(
        pattern,
        str(responses[2]),
        flags=re.DOTALL,
    )
    resource_mentions.append(situation)

    # Retrieve resources in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        resource_lists = list(
            executor.map(
                lambda text: extract_resources(
                    embedding_model,
                    saved_resources,
                    documents_resources,
                    text,
                    {f"resource_{organization}": True},
                    k=k,
                ),
                resource_mentions,
            )
        )

    print(f"[Pipeline] Resources retrieved at {time.time()}")

    # Deduplicate and refine resources
    unique_resources = deduplicate_resources(resource_lists)

    refined_resources = call_chatgpt_api_all_chats(
        [
            {
                "role": "system",
                "content": internal_prompts["refine_resources"].format(
                    organization,
                    situation,
                ),
            },
            {"role": "user", "content": "\n".join(unique_resources)},
        ],
        stream=False,
    )

    print(f"[Pipeline] Resources refined at {time.time()}")

    # Build response
    response = "\n".join(
        [
            f"SMART Goals: {responses[0]}",
            f"Questions: {responses[1]}",
            f"Resources (use only these resources):\n{refined_resources}",
        ]
    )

    # External resources (legacy behavior: currently empty)
    external_resources = ""
    raw_resource_prompt = responses[2]

    return response, external_resources, raw_resource_prompt


def parse_goals(full_response: str) -> list:
    """Parse SMART goals from response."""
    goals = []
    match = re.search(
        r"SMART Goals:\s*(.*?)\n(Questions|Goals|Steps)",
        full_response,
        flags=re.DOTALL,
    )

    if match:
        section = match.group(1).strip()
        for line in section.splitlines():
            text = line.strip().lstrip("•").strip()
            if text:
                goals.append(text)

    return goals


def parse_resources(full_response: str, raw_prompt: str, k: int = 25) -> list:
    """
    Parse resources from response.

    Args:
        full_response: The full pipeline response
        raw_prompt: Raw resource extraction output
        k: Maximum number of additional resources

    Returns:
        List of formatted resource strings
    """
    resources = []

    # Parse main resources section
    match = re.search(
        r"Resources[\s\S]*?:\s*\n([\s\S]*)",
        full_response,
    )

    if match:
        section = match.group(1).strip()
        for line in section.splitlines():
            text = line.strip().lstrip("•").strip()
            if text:
                resources.append(text)

    # Parse additional resources from raw prompt
    block_re = (
        r"\[Resource\]\s*"
        r"Name:\s*(?P<name>.+?)\s*"
        r"URL:\s*(?P<url>\S+?)\s*"
        r"Action:\s*(?P<action>.+?)\s*"
        r"\[/Resource\]"
    )

    for match in re.finditer(block_re, raw_prompt, flags=re.DOTALL | re.IGNORECASE):
        if len(resources) >= k:
            break

        name = match.group("name").strip()
        url = match.group("url").strip()
        action = match.group("action").strip()

        entry = f"**{name}**  \n"
        if url:
            entry += f"[Link]({url})  \n"
        if action:
            entry += f"**Action:** {action}"

        resources.append(entry)

    return resources


def fetch_goals_and_resources(
    situation: str,
    all_messages: list,
    organization: str,
    k: int = 25,
) -> tuple:
    """
    Main entry point for legacy goals and resources pipeline.

    Returns:
        Tuple of (goals, resources, full_response, external_resources, raw_prompt)
    """
    # Run pipeline
    full_response, external_resources, raw_prompt = get_questions_resources(
        situation,
        all_messages,
        organization,
        k=k,
    )

    print(f"[Pipeline] Questions/resources done at {time.time()}")

    # Parse outputs
    goals = parse_goals(full_response)
    resources = parse_resources(full_response, raw_prompt, k=k)

    # Add external resources to beginning (kept for compatibility)
    if external_resources:
        resources.insert(0, external_resources)

    print(f"[Pipeline] Parsing done at {time.time()}")

    return goals, resources, full_response, external_resources, raw_prompt


def _legacy_construct_response(
    situation: str,
    all_messages: list,
    model: str,
    organization: str,
    full_response: str,
    external_resources: str,
    raw_prompt: str,
):
    """
    Legacy response generation with streaming.

    This is essentially the original `construct_response` implementation.
    """
    print(f"[Response] Starting at {time.time()}")

    # For the "old version" path we always use the full copilot orchestration.
    needs_goals = True
    verbosity = "medium"

    # Small talk branch (kept for completeness, but not used in practice)
    if not needs_goals:
        chat_msgs = (
            [
                {
                    "role": "system",
                    "content": (
                        f"You are a helpful assistant for {organization}. "
                        "Reply warmly and concisely."
                    ),
                }
            ]
            + all_messages
            + [{"role": "user", "content": situation}]
        )
        response = call_chatgpt_api_all_chats(
            chat_msgs,
            stream=True,
            max_tokens=500,
        )
        yield from stream_process_chatgpt_response(response)
        return

    # Brief goals only branch (kept for completeness)
    if verbosity == "brief":
        prompt = (
            f"You are a concise assistant for {organization}. "
            "Given the user's request, produce **up to three** SMART goals "
            "as bullet points, each in one short sentence, tailored exactly "
            "to their situation."
        )
        msgs = (
            [{"role": "system", "content": prompt}]
            + all_messages
            + [{"role": "user", "content": situation}]
        )
        response = call_chatgpt_api_all_chats(
            msgs,
            stream=True,
            max_tokens=200,
        )
        yield from stream_process_chatgpt_response(response)
        return

    # ChatGPT mode branch (not used in current integration, but retained)
    if model == "chatgpt":
        msgs = (
            [
                {
                    "role": "system",
                    "content": (
                        f"You are a Co-Pilot tool for {organization}, "
                        "a peer-peer support org."
                    ),
                }
            ]
            + all_messages
            + [{"role": "user", "content": situation}]
        )
        response = call_chatgpt_api_all_chats(
            msgs,
            stream=True,
            max_tokens=750,
        )
        yield from stream_process_chatgpt_response(response)
        return

    # Full copilot orchestration (main path)
    print(f"[Response] Full orchestration at {time.time()}")

    orchestration_messages = [
        {"role": "system", "content": internal_prompts["orchestration"]},
        {"role": "system", "content": external_resources},
    ]
    orchestration_messages += all_messages
    orchestration_messages += [
        {"role": "user", "content": situation},
        {"role": "user", "content": full_response},
    ]

    print(f"[Response] Streaming orchestration at {time.time()}")
    response = call_chatgpt_api_all_chats(
        orchestration_messages,
        stream=True,
        max_tokens=1000,
    )
    yield from stream_process_chatgpt_response(response)


def construct_response(
    situation: str,
    all_messages: list,
    model: str,
    organization: str,
    version: str = "new",
):
    # Route to appropriate version implementation
    print(f"[construct_response] Version received: {version}")  # Add this
    if version == "new":
        # NEW VERSION: Current implementation with all tools
        print("[construct_response] Routing to NEW VERSION")  # Add this
        return _construct_response_new(situation, all_messages, model, organization)
    elif version == "old":
        # OLD VERSION: RAG retrieval → inject into prompt → GPT call (no tools)
        print("[construct_response] Routing to OLD VERSION")  # Add this
        return _construct_response_old(situation, all_messages, model, organization)
    elif version == "vanilla":
        # VANILLA GPT: Simple prompt → GPT call (no RAG, no tools)
        print("[construct_response] Routing to VANILLA VERSION")  # Add this
        return _construct_response_vanilla(situation, all_messages, model, organization)
    else:
        # Default to new version if unknown version
        print("[construct_response] Routing to NEW VERSION (default)")  # Add this
        return _construct_response_new(situation, all_messages, model, organization)

def _construct_response_new(
    situation: str,
    all_messages: list,
    model: str,
    organization: str,
):
    print("Organization", organization)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "resources_tool",
                "description": (
                    "Find nearby local resources such as food banks, shelters, or clinics. "
                    "Always use the user's location when searching."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "k": {"type": "integer", "default": 5}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "library_tool",
                "description": "Search deep-dive documents for peer support, crisis, or trans-related topics.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "category": {
                            "type": "string",
                            "enum": ["trans", "crisis", "peer"]
                        }
                    },
                    "required": ["query", "category"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "directions_tool",
                "description": "Get distance and travel time between two locations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "origin": {"type": "string"},
                        "destination": {"type": "string"},
                        "mode": {
                            "type": "string",
                            "enum": ["driving", "transit", "walking", "bicycling"]
                        }
                    },
                    "required": ["origin", "destination", "mode"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "calculator_tool",
                "description": "Perform basic math calculations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string"}
                    },
                    "required": ["expression"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "web_search_tool",
                "description": (
                    "Search the internet for nearby local services, addresses, hours, "
                    "or other information when internal resources are insufficient or unclear."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_eligibility",
                "description": "Check eligibility for benefits such as SNAP.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "program": {"type": "string", "enum": ["snap"]},
                        "household_size": {"type": "integer"},
                        "monthly_income": {"type": "number"}
                    },
                    "required": ["program", "household_size", "monthly_income"]
                }
            }
        },
    ]

    system_prompt = f"""
    You are PeerCoPilot, a supportive AI assistant for peer providers at {organization}.

    Use peer-friendly, non-clinical language grounded in CSPNJ values.
    Prioritize accuracy and safety. Never invent facts or resources.

    IMPORTANT TOOL RULES:
    - You may call multiple tools in sequence.
    - Do not answer from general knowledge alone when local resources are requested.
    """

    messages = [{"role": "system", "content": system_prompt}]
    messages += all_messages
    messages.append({"role": "user", "content": situation})

    # ---- TOOL LOOP ----
    while True:
        response = openai.chat.completions.create(
            model="gpt-5.2",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        choice = response.choices[0]

        # FINAL ANSWER (no more tools)
        if choice.finish_reason != "tool_calls":
            final_text = choice.message.content or ""
            for chunk in final_text.split("\n"):
                yield f"data: {chunk}<br/>\n\n"
            break

        # ASSISTANT REQUESTED TOOLS
        messages.append(choice.message)

        for tool_call in choice.message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            print(f"[DEBUG] Executing {name} with {args}")

            if name == "resources_tool":
                output = resources_tool(
                    query=args.get("query", ""),
                    organization=organization,
                    saved_indices=saved_resources,
                    documents=documents_resources,
                    embedding_model=embedding_model
                )

            elif name == "library_tool":
                output = library_tool(
                    query=args.get("query", ""),
                    category=args.get("category", "peer"),
                    saved_indices_peer=saved_articles,
                    documents_peer=documents_articles,
                    embedding_model=embedding_model
                )

            elif name == "directions_tool":
                output = directions_tool(
                    origin=args.get("origin", ""),
                    destination=args.get("destination", ""),
                    mode=args.get("mode", "driving")
                )

            elif name == "calculator_tool":
                output = calculator_tool(
                    expression=args.get("expression", "0")
                )

            elif name == "web_search_tool":
                output = web_search_tool(
                    query=args.get("query", "")
                )

            elif name == "check_eligibility":
                output = check_eligibility(
                    program=args.get("program", ""),
                    household_size=args.get("household_size", 1),
                    monthly_income=args.get("monthly_income", 0)
                )

            else:
                output = "Error: Unknown tool."

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": output
            })

    yield "[DONE]\n\n"

def _construct_response_old(
    situation: str,
    all_messages: list,
    model: str,
    organization: str,
):
    """
    Old version: recreate the legacy goals/questions/resources pipeline
    and orchestration behavior (no tools).
    """
    # 1) Run the legacy questions/resources pipeline
    #    This uses internal prompts, RAG over resources, and refinement.
    goals, resources, full_response, external_resources, raw_prompt = fetch_goals_and_resources(
        situation=situation,
        all_messages=all_messages,
        organization=organization,
        k=25,
    )

    # 2) Stream the final response using the legacy orchestration logic.
    #    We explicitly pass model="copilot" to take the full orchestration path.
    return _legacy_construct_response(
        situation=situation,
        all_messages=all_messages,
        model="copilot",
        organization=organization,
        full_response=full_response,
        external_resources=external_resources,
        raw_prompt=raw_prompt,
    )

def _construct_response_vanilla(
    situation: str,
    all_messages: list,
    model: str,
    organization: str,
):
    """Vanilla GPT: Simple prompt → GPT call (no RAG, no tools)."""
    # Build messages with simple system prompt
    system_prompt = "You are a helpful assistant for CSPNJ peer providers. Answer questions based on your general knowledge."
    
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    messages += all_messages
    messages.append({"role": "user", "content": situation})
    
    # Call GPT without tools, without RAG
    response = openai.chat.completions.create(
        model="gpt-5.2",
        messages=messages,
        stream=True
    )
    
    for event in response:
        if event.choices[0].delta.content:
            formatted_content = event.choices[0].delta.content.replace("\n", "<br/>")
            yield f"data: {formatted_content}\n\n"
    
    yield "[DONE]\n\n"