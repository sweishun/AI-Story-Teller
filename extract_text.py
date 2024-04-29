import re

def extract_title(text):
  title = text.split("Step 1:")[1].split("Step 2:")[0].strip()
  return title

# def extract_char(text):
#     char_contents = text.split("Step 4:")[0].split()

#     return char_names

def extract_page_contents(text):
    """
    Extracts the contents from each page section after "Page Text" in the provided story text.
    
    Parameters:
        text (str): The full text of the document, including the "Page Text" section.
        
    Returns:
        dict: A dictionary with keys as page titles ("Page 1", "Page 2", etc.) and values as the corresponding text content.
    """
    # Split the text at "Page Text" to get the relevant section
    pages_text = text.split("Step 2:")[1].strip()

    # Searching for page numbers
    page_contents = re.findall(r'Page \d+:\s*(.*?)\s*(?=(Page \d+:|$))', pages_text, re.DOTALL)

    # Extracting just the contents and strip any extra whitespace
    page_texts = {f"Page {i+1}": content.strip() for i, (content, _) in enumerate(page_contents)}

    # Extracting the characters
    
    return page_texts
