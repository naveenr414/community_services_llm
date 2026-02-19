from ddgs import DDGS
import googlemaps
import os 
import requests

google_maps_api = os.getenv("GOOGLE_API_KEY")
gmaps = googlemaps.Client(key=google_maps_api)

def query_resources(
    query: str,
    org_key: str,
    k: int = 5,
    saved_indices={},
    documents={},
    embedding_model=None
):
    """
    Search preloaded organization resources using FAISS embeddings.
    
    Args:
        query: User query string
        org_key: Organization ID (e.g., 'cspnj')
        k: Number of top results to return

    Returns:
        List of dictionaries with 'resource_text' and FAISS similarity 'score'
    """
    doc_key = f'resource_{org_key}'
    
    if doc_key not in saved_indices:
        print(f"[Warning] No resources loaded for {org_key}")
        return []
    
    # Encode the query
    query_emb = embedding_model.encode(query, convert_to_numpy=True).reshape(1, -1)
    
    # Search FAISS index
    D, I = saved_indices[doc_key].search(query_emb, k=k)
    
    results = []
    for score, idx in zip(D[0], I[0]):
        if idx < len(documents[doc_key]):
            results.append({
                "resource_text": documents[doc_key][idx],
                "score": float(score)
            })
    
    return results

def resources_tool(query: str, organization: str, k: int = 5,
                       saved_indices={},
    documents={},
    embedding_model=None):
    """
    GPT-accessible tool for fetching top organization resources.
    Returns formatted string for GPT consumption.
    """
    top_resources = query_resources(query, organization.lower(), k=k,
                                        saved_indices=saved_indices,
    documents=documents,
    embedding_model=embedding_model
    )
    if not top_resources:
        return "No relevant resources found."
    
    lines = []
    for r in top_resources:
        # r['resource_text'] is already a formatted string if you used documents
        lines.append(f"- {r['resource_text']} (score: {r['score']:.2f})")
    
    return "\n".join(lines)

def library_tool(query: str, category: str, k: int = 3,saved_indices_peer={},documents_peer={},embedding_model=None):
    """
    Searches specialized document libraries (e.g., 'trans', 'crisis', 'legal').
    """
    doc_key = f"cat_{category.lower()}"
    
    if doc_key not in saved_indices_peer:
        return f"Error: The category '{category}' does not exist. Available: trans, crisis, housing."
    
    # Standard FAISS search (same logic as your query_resources)
    query_emb = embedding_model.encode(query, convert_to_numpy=True).reshape(1, -1)
    D, I = saved_indices_peer[doc_key].search(query_emb, k=k)
    
    results = [documents_peer[doc_key][idx] for idx in I[0] if idx < len(documents_peer[doc_key])]
    
    if not results:
        return "No specific documents found for that query."
        
    return "\n---\n".join(results)

def directions_tool(origin: str, destination: str, mode: str = "driving"):
    """
    Get detailed, step-by-step navigation instructions.
    """
    try:
        result = gmaps.directions(origin, destination, mode=mode, departure_time="now")
        if not result:
            return "No routes found."
        leg = result[0]['legs'][0]
        full_instructions = [f"Total Trip: {leg['duration']['text']} ({leg['distance']['text']})\n"]
        for i, step in enumerate(leg['steps'], 1):
            # Clean up HTML tags (like <b>) that Google returns
            import re
            instruction = re.sub('<[^<]+?>', '', step['html_instructions'])
            duration = step['duration']['text']
            # Add specific transit details if they exist
            if step.get('travel_mode') == 'TRANSIT':
                details = step.get('transit_details', {})
                line = details.get('line', {}).get('short_name', 'Transit')
                stop = details.get('arrival_stop', {}).get('name', 'destination')
                instruction += f" (Take {line} to {stop})"
            full_instructions.append(f"{i}. {instruction} [{duration}]")
        return "\n".join(full_instructions)
    except Exception as e:
        return f"Error: {str(e)}"

def check_eligibility(program: str, household_size: int, monthly_income: float):
    """
    Checks eligibility based on official 2026 NJ income limits.
    """
    program = program.lower()
    
    # 2026 NJ SNAP Gross Income Limits (185% Federal Poverty Level)
    # Source: NJ Dept of Human Services / USDA
    snap_limits = {
        1: 2413,
        2: 3261,
        3: 4109,
        4: 4957,
        5: 5805,
        6: 6653,
        7: 7501,
        8: 8349
    }
    
    if "snap" in program or "food stamp" in program:
        # Get limit (add $848 for each person beyond 8)
        if household_size <= 8:
            limit = snap_limits.get(household_size)
        else:
            limit = 8349 + (848 * (household_size - 8))
            
        if monthly_income <= limit:
            return f"✅ LIKELY ELIGIBLE. Household income (${monthly_income}) is BELOW the NJ SNAP gross limit (${limit}) for {household_size} people."
        else:
            return f"❌ LIKELY INELIGIBLE. Household income (${monthly_income}) is ABOVE the NJ SNAP gross limit (${limit})."

    return "Error: Unknown benefit program. Currently supporting: SNAP."


def web_search_tool(query: str, max_results: int = 4):
    """
    Performs a live web search using Brave Search API.
    """

    try:
        # Get API key from environment variable
        api_key = os.getenv("BRAVE_API_KEY")
        if not api_key:
            return "Error: BRAVE_API_KEY environment variable not set"
        
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key
        }
        
        params = {
            "q": query,
            "count": max_results,
            "safesearch": "moderate"  # Options: off, moderate, strict
        }
        
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Check if we got results
        results = data.get("web", {}).get("results", [])
        if not results:
            return "No results found."
        
        # Format results nicely for the LLM
        formatted = f"Search results for: {query}\n\n"
        for i, r in enumerate(results[:max_results], 1):
            formatted += f"{i}. {r['title']}\n"
            formatted += f"   URL: {r['url']}\n"
            formatted += f"   {r.get('description', '')}\n"
        
        return formatted
        
    except requests.exceptions.RequestException as e:
        return f"Search failed: {str(e)}"
    except Exception as e:
        return f"Search failed: {str(e)}"

def calculator_tool(expression: str):
    """
    A safe calculator for basic arithmetic. 
    Supports +, -, *, /, and round().
    """
    allowed_chars = "0123456789+-*/(). "
    if any(char not in allowed_chars for char in expression):
        return "Error: Invalid characters. Only numbers and basic math (+-*/) allowed."
    
    try:
        # Evaluate using a restricted scope to prevent code injection
        # (For production, consider libraries like 'simpleeval')
        result = eval(expression, {"__builtins__": None}, {})
        return str(result)
    except Exception as e:
        return f"Error calculating '{expression}': {str(e)}"
