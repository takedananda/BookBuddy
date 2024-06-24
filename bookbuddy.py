# -*- coding: utf-8 -*-
import streamlit as st
import io
from google.cloud import vision
from PIL import Image
import os
import fitz  # PyMuPDF
from openai import OpenAI
from streamlit_free_text_select import st_free_text_select
import sys
import psycopg2

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\taked\OneDrive\Documents\GCP_API.json"

# Connect to Postgres
conn = psycopg2.connect(
    dbname="DEV_BookBuddy_DB",
    user="postgres",
    password="Zedd414!",
    host="localhost",
    port="5432"
)

#Creating cursor object

cursor = conn.cursor()




# Initialize the Google Cloud Vision client
def initialize_vision_client():
    client = vision.ImageAnnotatorClient()
    return client

# Function to perform OCR using Google Cloud Vision
def ocr_image(client, image):
    # Convert the image to bytes
    with io.BytesIO() as output:
        image.save(output, format="PNG")
        content = output.getvalue()

    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations

    if response.error.message:
        raise Exception(f'{response.error.message}')

    # Extract and return the detected text
    if texts:
        return texts[0].description
    return ""


# Function to extract contents from a PDF
def extract_from_pdf(pdf_bytes):
    try:
        # Open the PDF document from the byte stream
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        if pdf_document.page_count == 0:
            raise Exception("The PDF document is empty.")
        
        texts = []
        
        # Parse cases for readable PDF
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            text_from_pdf = page.get_text()
            texts.append(text_from_pdf)

        # Parse cases for unreadable PDF
        if len(texts) == 0:
            images = []
            readable_flg = 0
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                image_list = page.get_images(full=True)
                # print(f"Page {page_num + 1} has {len(image_list)} images.")
                
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = pdf_document.extract_image(xref)
                    image_bytes = base_image["image"]
                    image = Image.open(io.BytesIO(image_bytes))
                    images.append(image)

            return images, readable_flg
                

        else: 
            readable_flg = 1
            return texts[0], readable_flg
    
    except Exception as e:
        raise Exception(f"Error parsing PDF: {e}")
        
        

# Streamlit app
st.title('Book Analysis App')

# Initialize session state for uploaded file and button
if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = False
    
if 'button_pressed' not in st.session_state:
    st.session_state.button_pressed = False


with st.sidebar:
    # Free text selecter to store book name, chapter, and page
    options = ["apple"]
    
    book_title = st_free_text_select(
        label="Book Title",
        options=options,
        format_func=lambda x: x.lower(),
        placeholder="Select or enter the book title",
        disabled=False,
        delay=300,
    )
    # st.write("Book title:", book_title)
    
    
    # Gain chapter and page data
    ch_options = ["apple"]
    
    chapter = st_free_text_select(
        label="Chapter",
        options=ch_options,
        format_func=lambda x: x.lower(),
        disabled=False,
        delay=300,
    )
    st.write("Book title:",chapter)
    
    page = st.number_input("Insert page number", step = 1)


# Enforcing book info to be filled to proceed with the rest of the app usage
if book_title is None or chapter is None or page == 0:
    sys.exit()
    
# File uploader for images
uploaded_file = st.file_uploader('Upload an image or PDF of a book page', type=['jpg', 'jpeg', 'png', 'pdf'])


if uploaded_file is not None:
    # Initialize the Google Cloud Vision client
    client = initialize_vision_client()

    if uploaded_file.type == "application/pdf":
        with st.spinner('Extracting pdf...'):

            # Extract images from the PDF
            pdf_bytes = uploaded_file.read()
            output, readable_flg = extract_from_pdf(pdf_bytes)
            if readable_flg == 0:
                images = output
            else:
                #cleaned_output = []
                #for extraction in output:
                    #cleaned_output.append(extraction.replace("\n"," "))
                extracted_text = output
                st.text_area('Extracted Text', extracted_text, height=200) # Return text of first page
    else:
        # Load the image
        readable_flg = 0
        image = Image.open(uploaded_file)
        images = [image]

    # Process each image if image
    
    if readable_flg == 0:
        for image in images:
            # Display the uploaded image
            #st.image(image, caption='Uploaded Image', use_column_width=True)
    
            # Perform OCR and display the extracted text
            with st.spinner('Extracting text...'):
                extracted_text = ocr_image(client, image)
            st.text_area('Extracted Text', extracted_text, height=200)
            
    # Check if uploaded file is a new file
    if st.session_state.uploaded_file is None or uploaded_file != st.session_state.uploaded_file:
        st.session_state.uploaded_file = uploaded_file
        st.session_state.button_pressed = False
            
# Will be working on cases where book pages are loaded into the app one page at a time

# Store book title and 
# cursor.execute("Insert into dbo.book (title)")

# book_title = xyz
# chapter = xyz

# Store book data in Postgres
# Insert into dbo.book (title)

# Store book ID to send future data 
# book_id = SELECT id FROM dbo.book where title = book_title


# Enforcing file to be uploaded in order to proceed to summarization
if uploaded_file is None:
    sys.exit() 

# Send extracted text to OpenAI API

# Initialize OpenAI Client
client = OpenAI()

# Create session state for  model
if "openai_model" not in st.session_state: 
    st.session_state["openai_model"] = "gpt-3.5-turbo"

# Create session state for messages
if "messages" not in st.session_state: 
    st.session_state.messages = []
    
for message in st.session_state.messages: # Write each message in messages along with their roles
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# Get chatGPT to generate summary
if not st.session_state.button_pressed or st.session_state.button_pressed == False:
    if st.button("Summarize") and uploaded_file is not None:
    
        with st.chat_message("assistant"):
    
        # Create a chat completion
            stream = client.chat.completions.create(
                model=st.session_state["openai_model"],  # or another model name like "gpt-3.5-turbo"
                messages=[
                    {"role": "system", "content": "You are a knowledgeable reading partner. You will be given excerpts from books your partner is reading, and you will give summaries, and be ready to provide difficult vocabularies lists, comprehension quizzes, or provide historical context behind the book when asked."},
                    {"role": "user", "content": "Please summarize the following excerpt from a book I am reading:" + extracted_text}
                ],
                stream=True,
            )
            response = st.write_stream(stream)
        st.session_state.messages.append({"role": "assistant", "content": response}) # Append the chat info to dictionary
        
        # Flip the button switch to true to hide button
        st.session_state.button_pressed = True
    
        # Store extracted text and summary into database
        # INsert into Summary (id = book_id, chapter = chapter, page = page, summary = stream.choices[0].message.content,
        #   orig_text = extracted_text, summary_level = 'Page' )
        
        # Print the response
    #    st.text_area('Summary', response.choices[0].message.content, height=200)

if prompt := st.chat_input("What is up?"): # If chat input is obtained
    st.session_state.messages.append({"role": "user", "content": prompt}) # Add content and user role as a dictionary in message
    with st.chat_message("user"): # Write the user prompt in the chat box
        st.markdown(prompt)
    # Initialize chat box and show ChatGPT response
    
    # Context layer of ChatGPT
    intent_parse_prompt = """(Determine the intent of the following user input. If the user is for reading comprehension quizzes to be generated based on the content they are reading, return 'Quiz'. If, however, the user is asking about what happened in the text that the user was reading, return "Pass" because the user is asking for a discussion. Only when the user seems to ask for new quiz questions to be generated, return "Quiz".

Example 1:
Prompt: "Please quiz me on this chapter"
Output: "Quiz"

Example 2:
Prompt: "What was the author's intent with the character's monologue?'
Output: "Pass"

Example 3:
Prompt: "Quiz me'
Output: "Quiz"

Example 4:
Prompt: "What are some vocabs I should know from this?'
Output: "Pass"

Example 5:
Prompt: "in the chapter, what were the five things Mark was quizzed on by the teacher?'
Output: "Pass"

Now that I gave you some examples, I will start giving you prompts for you to classify whether they are quiz or pass. Are you ready? And remember, you are only allowed to say "Quiz" or "Pass". Don't be chatty. Your response can only be one word long"""
    
    
    
    
    response = client.chat.completions.create(
        model=st.session_state["openai_model"],
        messages=[
                {"role": "system", "content": intent_parse_prompt},
                {"role": "user", "content": prompt}
        ]
    )
    
    with st.chat_message("assistant"):
    
    
        if response.choices[0].message.content == "Quiz":
            # chat completion for quiz. 
            st.text_area('Extracted Text', "This is a quiz response", height=200)
            
            # Come up with prompt that returns specific format
            quiz_generation_prompt = """I am reading a book and would like you to generate quiz questions based on a page of text I provide. Please follow these instructions:
    
            1. Read the text data that I will feed you.
            2. Generate four quiz questions based on the content of the text.
            3. Each question should be open-ended (not multiple-choice).
            4. Provide a clear separator between the questions and the answers. Use 'ANSWERS' as the separator.
            5. Format your response as follows:
            Q1: [Your first quiz question]
            Q2: [Your second quiz question]
            Q3: [Your third quiz question]
            Q4: [Your fourth quiz question]
            
            ANSWERS
            
            A1: [Answer to the first question]
            A2: [Answer to the second question]
            A3: [Answer to the third question]
            A4: [Answer to the fourth question]
            
            6. Be ready to be able to grade the answers that the user provides back.
            
            
            Remember, your response should strictly only be in the format provided on instruction #5.
            """
            stream = client.chat.completions.create(
                model=st.session_state["openai_model"],
                messages=[
                        {"role": "system", "content": quiz_generation_prompt},
                        {"role": "user", "content": "With the output in the specified format from the instructions, please generate quizzes based on this text:" + extracted_text}
                ], stream = True
            )
            
            response = st.write_stream(stream)
            st.session_state.messages.append({"role": "assistant", "content": response}) # Append the chat info to dictionary

            
        
        else:
            # What I have now
            st.text_area('Extracted Text', "This is a pass response", height=200)
    
            stream = client.chat.completions.create(
                model=st.session_state["openai_model"],
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ],
                stream=True,
            )
            response = st.write_stream(stream)
            st.session_state.messages.append({"role": "assistant", "content": response}) # Append the chat info to dictionary
    
    
    
