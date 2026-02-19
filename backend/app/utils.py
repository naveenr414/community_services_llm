"""Small utility wrappers for PDF handling and OpenAI/ChatGPT access."""

from openai import AzureOpenAI
import PyPDF2
from fpdf import FPDF
from pathlib import Path
import os 
from openai import AzureOpenAI

BASE_DIR = Path(__file__).parent.parent

client = AzureOpenAI(
            api_version="2024-12-01-preview",
            azure_endpoint=os.environ.get("OPENAI_AZURE_ENDPOINT"),
            api_key=os.environ.get("OPENAI_API_KEY_AZURE"),
        )

def write_text_pdf(text,pdf_loc):
    """Save some text into a PDF
    
    Arguments:
        text: String, what to save
        pdf_loc: File location, where to save the resulting PDF
    
    Returns: Nothing
    
    Side Effects: Saves a PDF"""

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, text)
    pdf.output(pdf_loc)


def call_chatgpt_api(system_prompt,prompt,stream=True):
    """Run ChatGPT with the 4o-mini model for a system prompt
    
    Arguments:
        system_prompt: String, what the main system prompt is
            Tells ChatGPT the general scenario
        prompt: Specific prompt for ChatGPT

    Returns: String, result from ChatGPT"""

    response = client.chat.completions.create(
        model="gpt-5-chat",  
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        stream=stream,

    )

    if stream:
        return response
    else:
        return response.choices[0].message.content


def call_chatgpt_api_all_chats(all_chats,stream=True,max_tokens=750,response_format=None):
    """Run ChatGPT with the 4o-mini model for a system prompt
    
    Arguments:
        all_chats: List of dictionaries, 
            each with a role and content field
        stream: Boolean, whether to return a stream response
        max_tokens: Integer, maximum number of tokens from OpenAI
    
    Returns: Either a Stream or String, result from ChatGPT"""

    if response_format is not None:
        response = client.chat.completions.create(
            model="gpt-5-chat",  
            messages=all_chats,
            stream=stream,
            # max_tokens=max_tokens,
            response_format=response_format
        )
    else:
        response = client.chat.completions.create(
            model="gpt-5-chat",  
            messages=all_chats,
            stream=stream,
            # max_tokens=max_tokens,
        )
    
    if stream:
        return response
    else:
        return response.choices[0].message.content


def extract_text_from_pdf(pdf_file_path):
    """Extract some text from a PDF file path
    
    Arguments:
        pdf_file_path: String, location to the PDF file
        
    Returns: String, all the text in the file"""

    with open(pdf_file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
    return text


def stream_process_chatgpt_response(response):
    """Process a stream from ChatGPT
    
    Arguments:
        response: Some stream response from ChatGPT
    
    Returns: Character-by-character stream from the response"""
    
    for event in response:
        if event.choices[0].delta.content is not None:
            current_response = event.choices[0].delta.content
            current_response = current_response.replace("\n", "<br/>")
            yield "data: " + current_response + "\n\n"
    yield "[DONE]\n\n" 


def get_all_prompts():
    """Load all the prompts
    
    Arguments: None
    
    Returns: Dictionary internal_prompts and external_prompts
        mapping prompt name to a string"""

    internal_prompt_names = ["benefit_system","benefit_extract","goal","followup_question","resource","orchestration","which_resource","refine_resources"]
    external_prompt_names = ['human_resource','peer','crisis','trans']

    internal_prompts = {}
    external_prompts = {}

    for i in internal_prompt_names:
        internal_prompts[i] = open(BASE_DIR / "prompts/internal/{}.txt".format(i), encoding="utf-8").read()

    for i in external_prompt_names:
        external_prompts[i] = open(BASE_DIR / "prompts/external/{}.txt".format(i), encoding="utf-8").read()

    return internal_prompts, external_prompts

def call_chatgpt_with_functions(messages, functions, stream=False, max_tokens=750):
    """
    Wrapper around OpenAI’s function-calling API.
    Always returns a single ChatCompletion object.
    """
    response = client.chat.completions.create(
        model="gpt-5-chat", 
        messages=messages,
        functions=functions,
        function_call="auto",
        stream=stream,
        max_tokens=max_tokens,
    )

    if isinstance(response, (tuple, list)):
        response = response[0]
    return response
