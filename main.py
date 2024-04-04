from fastapi import FastAPI, APIRouter, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel
import openai
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Set up OpenAI API
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
mongo_uri = os.getenv("MONGODB_URI")
if not mongo_uri:
    raise EnvironmentError("MongoDB URI not found in environment variables.")

client = MongoClient(mongo_uri)

# Define data models
class TaskCreate(BaseModel):
    task_text: str

class TaskResponse(BaseModel):
    task_id: str
    task_text: str
    created_at: datetime
    priority: str

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
async def list_tasks_api(user_name: str, collection_name: str = None):
    # Validate user authentication
    if not validate_user(user_name):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not collection_name:
        collection_name = get_collection_name()
    
    try:
        # Call list_tasks function
        tasks = list_tasks(user_name, collection_name)
        return {"tasks": tasks}
    except Exception as e:
        return {"message": "Failed to list tasks", "error": str(e)}

@router.delete("/delete_task/{task_id}/")
async def delete_task_api(user_name: str, task_id: str, collection_name: str = None):
    # Validate user authentication
    if not validate_user(user_name):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not collection_name:
        collection_name = get_collection_name()
    
    try:
        # Call delete_task function
        deleted_count = delete_task(user_name, collection_name, task_id)
        if deleted_count > 0:
            return {"message": f"Successfully deleted data with ObjectId: {task_id}"}
        else:
            return {"message": f"No data found with ObjectId: {task_id}"}
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
        # Call update_task function
        updated_count = update_task(user_name, collection_name, task_id, task_data.task_text)
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

@router.get("/collections/")
async def get_collections(username: str):
    # Validate user authentication
    if not validate_user(username):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        # Get the list of collections for the user
        collections = get_collections_list(username)
        return {"collections": collections}
    except Exception as e:
        return {"message": "Failed to fetch collections", "error": str(e)}

def get_collections_list(username):
    # Get all database names for the user
    database_names = client.list_database_names()
    # Filter out system databases and return remaining as collections
    collections = [db_name for db_name in database_names if db_name not in ['admin', 'local', 'config', 'system']]
    return collections


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
    collection = get_collection(username, collection_name)
    task = {
        "task_text": task_text,
        "priority": priority,
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
    tasks = list(collection.find({}, {"_id": 1, "task_text": 1, "created_at": 1, "priority": 1}))
    formatted_tasks = [{"task_id": str(task["_id"]), "task_text": task["task_text"], "created_at": task["created_at"], "priority": task["priority"]} for task in tasks]
    return formatted_tasks

def delete_task(username, collection_name, task_id):
    collection = get_collection(username, collection_name)
    result = collection.delete_one({"_id": ObjectId(task_id)})
    return result.deleted_count

def update_task(username, collection_name, task_id, updated_text):
    collection = get_collection(username, collection_name)
    result = collection.update_one({"_id": ObjectId(task_id)}, {"$set": {"task_text": updated_text}})
    return result.modified_count

# Include the router in the main app
app.include_router(router, prefix="/tasks")
