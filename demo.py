import re
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
from typing import Optional
import json
import datefinder

# MongoDB connection URI
mongo_uri = "mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/"

# Load intents from JSON file
with open('intents.json', 'r') as file:
    intents = json.load(file)

# Define chat patterns and responses for CRUD operations
crud_pairs = [
    # Adding a task
    ['add task (.+)|create task (.+)|add new task (.+)|can you add a task for me (.+)|please add task (.+)|I want to add task (.+)', ['Task added.', lambda x, username, collection_name: add_task(x[0], username, collection_name)]],

    # Deleting a task (adjusted pattern)
    ['(delete|remove) task (.+)', ['Task deleted.', lambda x, username, collection_name: delete_task(x[1], username, collection_name)]],

    # Viewing tasks (adjusted pattern)
    ['(view|display|show all|list|what are my|can you show my) tasks', ['Tasks:', lambda x, username, collection_name: view_tasks(username, collection_name)]],

    # Updating a task (adjusted pattern)
    ['(update|modify|change|edit) task (\S+) to (.+)', ['Task updated.', lambda x, username, collection_name: update_task(x[1], x[2], username, collection_name)]],
]

# Convert all patterns to case-insensitive
for i in range(len(crud_pairs)):
    crud_pairs[i][0] = re.compile(crud_pairs[i][0], re.IGNORECASE)

def add_task(task_text, username, collection_name, reminder_date=None, reminder_time=None):
    # Connect to MongoDB
    client = MongoClient(mongo_uri)
    db = client[username]
    tasks_collection = db[collection_name]

    # Extract date and time from task text using datefinder
    extracted_datetime = extract_datetime(task_text)
    if extracted_datetime:
        task_data = {
            "task_text": task_text,
            "priority": suggest_priority(task_text),
            "date": extracted_datetime.strftime("%Y-%m-%d"),
            "time": extracted_datetime.strftime("%H:%M:%S"),
            "reminder_date": reminder_date,
            "reminder_time": reminder_time,
            "created_at": datetime.now().isoformat()
        }

        # Check if a task with the same date and time already exists
        existing_task = tasks_collection.find_one({"date": task_data["date"], "time": task_data["time"]})
        if existing_task:
            client.close()
            return "Task with the same date and time already exists"
        
        # If no task with the same date and time exists, but reminder date and time are not provided, ask for them
        if not (reminder_date and reminder_time):
            client.close()
            return "Please provide reminder date and time."

        # Insert task data into the database
        result = tasks_collection.insert_one(task_data)
        client.close()

        # Check if task insertion was successful
        if result.inserted_id:
            return "Task added successfully"
        else:
            return "Failed to add task"
    else:
        client.close()
        return "Failed to extract date and time from task"

# Function to extract date and time using datefinder
def extract_datetime(task_text: str) -> Optional[datetime]:
    matches = list(datefinder.find_dates(task_text))
    if matches:
        return matches[0]  # Return the first match
    return None

# Function to delete a task
def delete_task(task_id, username, collection_name):
    client = MongoClient(mongo_uri)
    db = client[username]
    tasks_collection = db[collection_name]

    result = tasks_collection.delete_one({"_id": ObjectId(task_id)})
    client.close()

    if result.deleted_count:
        return f"Task with ID {task_id} deleted."
    else:
        return f"Task with ID {task_id} not found."

def view_tasks(username, collection_name):
    client = MongoClient(mongo_uri)
    db = client[username]
    tasks_collection = db[collection_name]

    tasks = tasks_collection.find()
    tasks_list = [f"{task['task_text']}\n" for task in tasks]  # Include newline character after each task
    client.close()

    if tasks_list:
        return "".join(tasks_list)  # Join the tasks without any separator
    else:
        return "No tasks found."

# Function to update a task
def update_task(task_id, new_description, username, collection_name):
    client = MongoClient(mongo_uri)
    db = client[username]
    tasks_collection = db[collection_name]

    result = tasks_collection.update_one({"_id": ObjectId(task_id)}, {"$set": {"task_text": new_description}})
    client.close()

    if result.modified_count:
        return f"Task with ID {task_id} updated."
    else:
        return f"Task with ID {task_id} not found."

# Function to suggest priority based on task description
def suggest_priority(task_text):
    # Your priority suggestion logic here
    return "Medium"  # Placeholder logic

import random

def get_response_from_intents(user_input):
    user_input = user_input.lower()
    matched_responses = []
    for intent in intents['intents']:
        for pattern in intent['patterns']:
            if re.search(r'\b' + re.escape(pattern.lower()) + r'\b', user_input):
                matched_responses.extend(intent['responses'])
                break  # Stop searching for patterns once a match is found
    if matched_responses:
        return random.choice(matched_responses)
    return None

def chatbot_response(user_input, username, collection_name):
    for pattern, responses in crud_pairs:
        match = re.match(pattern, user_input)
        if match:
            if callable(responses[1]):
                return responses[1](match.groups(), username, collection_name)
            else:
                return responses[1]
    
    # If no CRUD pattern matched, try to get response from intents.json
    intent_response = get_response_from_intents(user_input)
    if intent_response:
        return intent_response
    else:
        return "I'm sorry, I didn't quite get that. Could you please rephrase?"
