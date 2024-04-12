import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import speech_recognition as sr
from bson import ObjectId
import openai
import datefinder
from dateutil import parser

# Set up OpenAI API
openai.api_key = os.getenv("OPENAI_API_KEY")

# Add custom styles
st.markdown("""
    <style>
        body {
            font-family: 'Roboto', sans-serif;
            background-color: #f8f9fa;
        }
        .streamlit-container {
            width: 80%;
            max-width: 600px;
            background-color: #fff;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
            margin: auto;
            margin-top: 20px;
            padding: 20px;
            box-sizing: border-box;
            text-align: center;
        }
        h1 {
            color: #007bff;
            margin-bottom: 30px;
            font-size: 28px;
            font-weight: 700;
            letter-spacing: 1px;
        }
        .streamlit-widget {
            margin-bottom: 20px;
        }
        .streamlit-button {
            padding: 10px 20px;
            font-size: 16px;
            cursor: pointer;
            background-color: #007bff;
            color: #fff;
            border: none;
            border-radius: 5px;
            transition: background-color 0.3s;
        }
        .streamlit-button:hover {
            background-color: #0056b3;
        }
    </style>
""", unsafe_allow_html=True)

def get_user_info():
    user_name = st.text_input("Enter your username:")
    return user_name

def get_collection_name(month):
    return month.lower()

def recognize_speech(recognizer, mic):
    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
        st.write("Listening... Say your task.")
        audio = recognizer.listen(source)

    try:
        task_text = recognizer.recognize_google(audio)
        return task_text
    except sr.UnknownValueError:
        return "Sorry, could not understand the audio."
    except sr.RequestError:
        return "Could not request results; check your internet connection."

def store_in_mongo(text, user_name, collection_name):
    # MongoDB connection
    client = MongoClient(f'mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/{user_name}')
    db = client[user_name]
    collection = db[collection_name]

    # Parsing date and time from the task text
    date_matches = datefinder.find_dates(text)
    date_str = None
    time_str = None
    if date_matches:
        for match in date_matches:
            date_str = match.strftime("%d-%m-%Y")
            time_str = match.strftime("%I:%M %p")
            break

    # Creating a document to insert into the collection
    task_document = {
        'task_text': text,
        'date': date_str,
        'time': time_str
    }

    # Inserting the document into the collection
    result = collection.insert_one(task_document)
    return result

def delete_from_mongo(task_id, user_name, collection_name):
    # MongoDB connection
    client = MongoClient(f'mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/{user_name}')
    db = client[user_name]
    collection = db[collection_name]

    try:
        # Convert the input string to ObjectId
        obj_id = ObjectId(task_id)
        result = collection.delete_one({"_id": obj_id})

        if result.deleted_count > 0:
            return {"message": f"Successfully deleted data with ObjectId: {task_id}"}
        else:
            return {"message": f"No data found with ObjectId: {task_id}"}
    except Exception as e:
        return {"message": "Invalid ObjectId format. Please enter a valid ObjectId."}

def list_tasks(user_name, collection_name):
    # MongoDB connection
    client = MongoClient(f'mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/{user_name}')
    db = client[user_name]
    collection = db[collection_name]

    # Filter tasks for the selected month
    tasks = list(collection.find())

    return tasks

def chat_with_gpt3_turbo(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
    )
    return response['choices'][0]['message']['content'].strip()

def chat_with_user():
    st.subheader("Chat with the Task Manager Assistant")
    st.write("Use this chat window to interact with the assistant.")

    user_input = st.text_input("You:", "")
    if user_input:
        # Use OpenAI GPT-3.5 Turbo to get assistant's response
        gpt3_turbo_response = chat_with_gpt3_turbo(user_input)

        # Display assistant's response
        st.text_area("Assistant:", value=gpt3_turbo_response, height=100)

        # Check if the user wants to proceed with the task
        if st.button("Save Task"):
            month = datetime.now().strftime("%B")  # Get current month
            collection_name = get_collection_name(month)
            store_in_mongo(gpt3_turbo_response, user_name, collection_name)
            st.success("Task saved successfully!")

def main():
    global user_name
    user_name = get_user_info()

    if user_name:
        recognizer = sr.Recognizer()
        mic = sr.Microphone()

        st.title("Speech-to-Text Task Manager")

        st.sidebar.subheader("Menu")
        menu_choice = st.sidebar.radio("Select an option:", ("Speech", "View Tasks", "Chat"))

        if menu_choice == "Speech":
            st.sidebar.markdown("### Speech Recognition")
            st.write("Enter your task using the microphone:")
            start_recording_button = st.button("Start Recording 🎙", key="start_recording_button")

            if start_recording_button:
                recognized_text = recognize_speech(recognizer, mic)
                st.write("Spoken Task:", recognized_text)

                # Store in MongoDB
                if recognized_text:
                    month = datetime.now().strftime("%B")  # Get current month
                    collection_name = get_collection_name(month)
                    result_speech = store_in_mongo(recognized_text, user_name, collection_name)
                    st.success(f"Speech Task stored in MongoDB with ID: {result_speech.inserted_id}")

        elif menu_choice == "View Tasks":
            st.sidebar.markdown("### View Tasks")
            month = st.selectbox("Select Month", ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"))
            collection_name = get_collection_name(month)
            tasks = list_tasks(user_name, collection_name)

            for task in tasks:
                with st.expander(f"Task: {task['task_text']}", expanded=False):
                    st.write(f"*Task ID:* {task['_id']}")
                    if 'date' in task:
                        st.write(f"*Date:* {task['date']}")
                    else:
                        st.write("*Date:* Not available")
                    st.write(f"*Time:* {task.get('time', 'Not available')}")
                    
                    # Generate a unique key for the delete button based on task ID
                    delete_button_key = f"delete_button_{task['_id']}"
                    if st.button("Delete Task", key=delete_button_key):
                        result_delete = delete_from_mongo(str(task['_id']), user_name, collection_name)
                        st.write(result_delete["message"])

        elif menu_choice == "Chat":
            chat_with_user()

if __name__ == "__main__":
    main()
