import openai
import PyPDF2
import pyttsx3
from fpdf import FPDF


def read_text(text):
    """Read some text outloud
    
    Arguments:
        text: String, some text to read
    
    Returns: Nothing
    
    Side Effects: Reads the text outloud"""

    engine = pyttsx3.init()
    
    # Set properties, such as the speech rate
    engine.setProperty('rate', 150)  # Adjust as needed
    
    # Speak the text
    engine.say(text)
    engine.runAndWait()

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
        prompt: Specific promt for ChatGPT

    Returns: String, result from ChatGPT"""

    response = openai.chat.completions.create(
        model="gpt-4o-mini",  
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


def call_chatgpt_api_all_chats(all_chats,stream=True,max_tokens=750):
    """Run ChatGPT with the 4o-mini model for a system prompt
    
    Arguments:
        all_chats: List of dictionaries, 
            each with a role and content field
        stream: Boolean, whether to return a stream response
        max_tokens: Integer, maximum number of tokens from OpenAI
    
    Returns: Either a Stream or String, result from ChatGPT"""
    response = openai.chat.completions.create(
        model="gpt-4o-mini",  
        messages=all_chats,
        stream=stream,
        max_tokens=max_tokens,
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