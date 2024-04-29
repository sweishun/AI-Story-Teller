from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import json
import datetime
from openai import OpenAI
from dotenv import load_dotenv
import os
from extract_text import *
import requests


app = Flask(__name__)
# Initialize with your OpenAI API key
load_dotenv() 
# openai.api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(
    api_key=os.environ['OPENAI_API_KEY']
)

# voice generation URL
url = "https://api.elevenlabs.io/v1/text-to-speech/mt8Xy7FBJEHheef7Glqi"

headers = {
  "Accept": "audio/mpeg",
  "Content-Type": "application/json",
  "xi-api-key": os.environ['ELEVEN_LAB_API']
}

# Function to load and save books with audio 
def load_books():
    try:
        with open('generated_books.json', 'r') as file: 
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

# To synchronise list of books with those in directory 
def sync_books (books, directory='generated_books'):
    actual_files = {file for file in os.listdir(directory) if file.endswith('.html')}
    updated_books = [book for book in books if book.get('filename') in actual_files]
    return updated_books

def save_books(books):
    with open('generated_books.json', 'w') as file:
        json.dump(books, file)  

generated_books = load_books()

@app.route('/', methods=['GET', 'POST'])
def index():
    global generated_books
    if request.method == 'POST':
        theme = request.form['theme']
        age_range = request.form['age_range']
        num_pages = request.form['num_pages']
        num_char = request.form['num_char']
        user_input = request.form['user_input']
        return redirect(url_for('book_display', theme=theme, age_range=age_range, num_pages=num_pages, num_char=num_char, user_input=user_input))
    else:
        # print(generated_books)
        generated_books = sync_books(generated_books)
        # print("Synced Books:", generated_books)
        return render_template('index.html', books=generated_books)

@app.route('/book_display')
def book_display():
    theme = request.args.get('theme')
    age_range = request.args.get('age_range')
    num_pages = int(request.args.get('num_pages'))
    num_char = int(request.args.get('num_char'))
    user_input = request.args.get('user_input')

    # delimiter = "####"
    system_message = f"""Follow these steps to generate the final output in the format strictly as shown in the example format identified between the below.
    You are a world class story generator.
    Step 1: Generate a children's story title for a {theme} themed book that is {num_pages} pages long, for children ages {age_range} years old. 
    Step 2: For each page, write a page text for a children's book. The book must consist of {num_char} characters. There needs to be at least one dialogue.
    
    Example Format: 
    Step 1: The Little Explorer's Journey

    Step 2: 
    Page 1: Once upon a time, Little Explorer packed his bag. "I'm ready for a big adventure!" he exclaimed.
    Page 2: In the forest, he met Wise Owl. "What do you seek?" asked Owl, peering down.
    """

    # Call GPT-4 to generate a title and outline
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content":system_message},
            {"role": "user", "content": f"Generate a story based on {user_input}."}
        ])

    response_output = response.choices[0].message.content.strip()
    # print(response_output)

    # Call GPT to answer who are characters
    response_characters = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "The following text is a story: " + response_output + " Create imaginative but concise descriptions for the main characters' appearances based on their personalities and actions in the story, even if these details are not explicitly mentioned in the text."},
            {"role": "user", "content": "Give me brief and imaginative descriptions for the main characters"}
        ])
    characters_output = response_characters.choices[0].message.content.strip()
    # print(f'Characters are:', characters_output)

    # Generate text, images and audio for each page
    title = extract_title(response_output)
    # characters_output = extract_char(response_output)
    # print(characters_output)
    # print(title)
    pages = []
    page_contents = extract_page_contents(response_output)
    # print(page_contents)

    for page, content in page_contents.items():
        # print(content)
        response_2 = client.images.generate(
            model = "dall-e-3",
            prompt = f"This is for a kids story book. Characters are: {characters_output} Use {content} for generation. There must be no words in image.",
            size = "1024x1024",
            quality = "standard",
        )
        image_url =  response_2.data[0].url 

        data = {
            "text": content,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }

        response_3 = requests.post(url, json=data, headers=headers)
        audio_filename = f'{title.replace(" ", "_")}_page_{page}.mp3'
        audio_filepath = os.path.join('generated_books', 'audio', audio_filename)
        os.makedirs(os.path.dirname(audio_filepath), exist_ok=True)

        with open(audio_filepath, 'wb') as f:
            for chunk in response_3.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)


        pages.append({'text': content, 'image_url': image_url, 'audio_url': audio_filename})

    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{title.replace(' ', '_')}_{timestamp}.html"
    filepath = os.path.join('generated_books', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    rendered_html = render_template('book_display.html', title=title, pages=pages)

    with open(filepath, "w") as file:
        file.write(rendered_html)

    book_info = {
        "title": title,
        "filename": filename,
    }
    generated_books.append(book_info)
    save_books(generated_books)

    return rendered_html

@app.route('/generated_books/<filename>')
def book_display_file(filename):
    # Serve the saved HTML file
    return send_from_directory('generated_books', filename)

@app.route('/audio/<filename>')
def audio_file(filename):
    return send_from_directory('generated_books/audio', filename)

@app.route('/delete_book', methods=['POST'])
def delete_book():
    filename = request.form['filename']
    # filename = secure_filename(filename)  # Ensure filename is secure
    
    # Remove the book from the JSON file
    global generated_books        
    generated_books = [book for book in generated_books if book['filename'] != filename]
    save_books(generated_books)
    
    # Try to delete the HTML file
    html_file_path = os.path.join('generated_books', filename)
    try:
        if os.path.exists(html_file_path):
            os.remove(html_file_path)
    except Exception as e:
        return redirect(url_for('index'))
    
    # Try to delete associated audio files
    book_title = "_".join(filename.split('_')[:-2])  # Remove the timestamp and extension
    audio_dir_path = os.path.join('generated_books', 'audio')
    try:
        for audio_file in os.listdir(audio_dir_path):
            if audio_file.startswith(book_title):
                audio_file_path = os.path.join(audio_dir_path, audio_file)
                if os.path.exists(audio_file_path):
                    os.remove(audio_file_path)
    except Exception as e:
        return redirect(url_for('index'))
    
    # Redirect back to the homepage
    return redirect(url_for('index'))



if __name__ == '__main__':
    app.run(debug=True)
