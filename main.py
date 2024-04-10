from fastapi import FastAPI, APIRouter, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel
import openai
from dotenv import load_dotenv
import os
import datefinder


load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

# Set up CORS middleware
origins = ["*"]  # Update with your frontend URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter()

# MongoDB connection
mongo_uri = "mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/"
client = MongoClient(mongo_uri)

# Define data models
class TaskCreate(BaseModel):
    task_text: str
    priority: str
    date: str
    time: str

class TaskResponse(BaseModel):
    task_id: str
    task_text: str
    created_at: datetime
    priority: str
    date: str
    time: str

# Define user model for authentication
class User(BaseModel):
    username: str

# Define API routes
@router.post("/login/")
async def login(user: User):
    username = user.username
    # Check if the username exists as a database in MongoDB
    if not validate_user(username):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"message": "Login successful"}

@router.post("/register/")
async def register(user: User):
    username = user.username
    # Check if the username already exists as a database in MongoDB
    if validate_user(username):
        raise HTTPException(status_code=400, detail="Username already exists")
    # Create a new database with the provided username
    create_new_user(username)
    return {"message": "User registered successfully"}

@router.post("/add_task/")
async def add_task_api(user_name: str, task_data: TaskCreate, collection_name: str = None):
    # Validate user authentication
    if not validate_user(user_name):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not collection_name:
        collection_name = get_collection_name()
    
    try:
        # Call add_task function
        task_id = add_task(user_name, collection_name, task_data.task_text)
        return {"message": "Task added successfully", "task_id": str(task_id)}
    except Exception as e:
        return {"message": "Failed to add task", "error": str(e)}

@router.get("/list_tasks/")
async def list_tasks_api(username: str, collection_name: str = None):
    # Validate user authentication
    if not validate_user(username):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not collection_name:
        collection_name = get_collection_name()
    
    try:
        # Call list_tasks function
        tasks = list_tasks(username, collection_name)
        return {"tasks": tasks}
    except Exception as e:
        return {"message": "Failed to list tasks", "error": str(e)}

@router.delete("/delete_task/")
async def delete_task_api(username: str, task_id: str, collection_name: str = None):
    try:
        # Validate user authentication
        if not validate_user(username):
            raise HTTPException(status_code=401, detail="Unauthorized")

        if not collection_name:
            collection_name = get_collection_name()

        # Call delete_task function
        deleted_count = delete_task(username, collection_name, task_id)
        if deleted_count > 0:
            return {"message": f"Successfully deleted task with ObjectId: {task_id}"}
        else:
            return {"message": f"No task found with ObjectId: {task_id}"}
    except Exception as e:
        return {"message": "Failed to delete task", "error": str(e)}
    
@router.put("/update_task/{task_id}/")
async def update_task_api(user_name: str, task_id: str, task_data: TaskCreate, collection_name: str = None):
    # Validate user authentication
    if not validate_user(user_name):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not collection_name:
        collection_name = get_collection_name()

    try:
        # Convert task_data to dictionary
        task_data_dict = task_data.dict()

        # Remove created_at field from task_data_dict to avoid updating it
        task_data_dict.pop("created_at", None)

        # Call update_task function
        updated_count = update_task(user_name, collection_name, task_id, task_data_dict)
        if updated_count > 0:
            return {"message": f"Successfully updated task with ObjectId: {task_id}"}
        else:
            return {"message": f"No data found with ObjectId: {task_id}"}
    except Exception as e:
        return {"message": "Failed to update task", "error": str(e)}

@router.post("/chat_with_gpt3_turbo")
async def chat_with_gpt3_turbo(username: str, collection_name: str, user_input: str = Form(...)):
    try:
        if user_input.startswith("Add new task:"):
            task_text = user_input.replace("Add new task:", "").strip()
            priority = suggest_priority(task_text)
            task_id = add_task(username, collection_name, task_text, priority)
            return {"message": "Task added successfully", "task_id": str(task_id)}

        # Use OpenAI GPT-3.5-turbo to get assistant's response
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"User: {username}"},
                {"role": "user", "content": f"Collection: {collection_name}"},
                {"role": "user", "content": user_input}
            ]
        )

        # Extract the response from the API result
        gpt3_turbo_response = response['choices'][0]['message']['content'].strip()

        # Save user input and GPT-3 response to the conversation
        save_user_input_response(username, collection_name, user_input, gpt3_turbo_response)

        # Log the response
        print("GPT-3.5-turbo Response:", gpt3_turbo_response)

        return {"message": gpt3_turbo_response}

    except Exception as e:
        # Log the error
        print("Error:", e)

        # Return error message if there's an exception
        return {"message": "Error:", "error": str(e)}

def save_user_input_response(username, collection_name, user_input, response):
    try:
        # Get the conversation collection
        collection = get_collection(username, collection_name)
        
        # Create a document representing the user input, response, and timestamp
        document = {
            "user_input": user_input,
            "response": response,
            "created_at": datetime.now()
        }
        
        # Insert the document into the conversation collection
        collection.insert_one(document)
        
    except Exception as e:
        # Log the error
        print("Error saving user input and response:", e)

@router.get("/collections/{username}")
async def get_collections(username: str):
    # Validate user authentication
    if not validate_user(username):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        # Get the list of collections for the user
        database = client[username]
        collections = database.list_collection_names()
        return {"collections": collections}
    except Exception as e:
        return {"message": "Failed to fetch collections", "error": str(e)}

def get_collections_list(username):
    # Get all database names for the user
    database_names = client.list_database_names()
    # Filter out system databases and return remaining as collections
    collections = [db_name for db_name in database_names if db_name not in ['admin', 'local', 'config', 'system']]
    return collections

def get_databases_list(username):
    # Get all collections for the user
    collections = get_collections_list(username)
    databases = {}
    # Iterate through each collection and get its databases
    for collection_name in collections:
        db = client[username]
        collection = db[collection_name]
        databases[collection_name] = collection.list_collection_names()
    return databases

# Function to validate user
def validate_user(username):
    # Check if the username exists as a database in MongoDB
    mongo_uri = "mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/"
    client = MongoClient(mongo_uri)
    database_names = client.list_database_names()
    return username in database_names

def get_collection_name():
    return datetime.now().strftime("%B").lower()

def get_collection(username, collection_name):
    db = client[username]
    return db[collection_name]

def add_task(username, collection_name, task_text, priority="Low"):
    # Parse date and time from task text
    date_matches = datefinder.find_dates(task_text)
    date_str = None
    time_str = None
    if date_matches:
        for match in date_matches:
            date_str = match.strftime("%Y-%m-%d")
            time_str = match.strftime("%H:%M:%S")
            break

    collection = get_collection(username, collection_name)
    task = {
        "task_text": task_text,
        "priority": priority,
        "date": date_str,
        "time": time_str,
        "created_at": datetime.now()
    }
    result = collection.insert_one(task)
    return result.inserted_id

def suggest_priority(task_text):
    task_text_lower = task_text.lower()
    high_priority_keywords = ["urgent", "important", "asap", "critical"]
    medium_priority_keywords = ["tomorrow", "soon", "schedule"]
    for keyword in high_priority_keywords:
        if keyword in task_text_lower:
            return "High"
    for keyword in medium_priority_keywords:
        if keyword in task_text_lower:
            return "Medium"
    return "Low"

def validate_user(username):
    database_names = client.list_database_names()
    return username in database_names

def create_new_user(username):
    db = client[username]
    current_month = get_collection_name()
    db[current_month].insert_one({})
    return db

def list_tasks(username, collection_name):
    collection = get_collection(username, collection_name)
    # Use projection to include only fields that are present in the document
    tasks = list(collection.find({}, {"_id": 1, "task_text": 1, "created_at": 1, "priority": 1, "date": 1, "time": 1}))
    formatted_tasks = []
    for task in tasks:
        formatted_task = {
            "task_id": str(task["_id"]),
            "task_text": task.get("task_text", ""),
            "priority": task.get("priority", ""),
            "date": task.get("date", ""),
            "time": task.get("time", ""),
            "created_at": task.get("created_at", "")  # Use .get() method to handle missing field
        }
        formatted_tasks.append(formatted_task)
    return formatted_tasks

def delete_task(username, collection_name, task_id):
    collection = get_collection(username, collection_name)
    result = collection.delete_one({"_id": ObjectId(task_id)})
    return result.deleted_count

def update_task(username, collection_name, task_id, updated_task_data):
    collection = get_collection(username, collection_name)

    # Ensure the updated_task_data is formatted properly for update
    updated_task_data = {key: value for key, value in updated_task_data.items() if value is not None}

    # Set the updated_at field to the current datetime
    updated_task_data["updated_at"] = datetime.now()

    result = collection.update_one({"_id": ObjectId(task_id)}, {"$set": updated_task_data})
    return result.modified_count

# Include the router in the main app
app.include_router(router, prefix="/tasks")
