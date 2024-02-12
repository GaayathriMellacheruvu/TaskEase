from fastapi import FastAPI, APIRouter, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel
from demo import (
    chat_with_gpt3_turbo,
    add_task,
    list_tasks,
    update_task,
    delete_task,
)

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

# MongoDB connection details
def get_collection_name():
    return datetime.now().strftime("%B").lower()

def get_collection(username, collection_name):
    mongo_uri = f"mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/{username}"
    client = MongoClient(mongo_uri)
    db = client[username]
    collection = db[collection_name]
    return collection

# Define data models
class TaskCreate(BaseModel):
    task_text: str

class TaskUpdate(BaseModel):
    task_text: str

class TaskResponse(BaseModel):
    task_id: str
    task_text: str

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
async def add_task_api(user_name: str, task_data: TaskCreate = Form(...), collection_name: str = None):
    # Validate user authentication
    if not validate_user(user_name):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not collection_name:
        collection_name = get_collection_name()
    
    try:
        # Call add_task function from demo.py
        task_id = add_task(user_name, collection_name, task_data.task_text)
        return {"message": "Task added successfully", "task_id": str(task_id)}
    except Exception as e:
        return {"message": str(e)}

@router.get("/list_tasks/")
async def list_tasks_api(user_name: str, collection_name: str = None):
    # Validate user authentication
    if not validate_user(user_name):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not collection_name:
        collection_name = get_collection_name()
    
    try:
        # Call list_tasks function from demo.py
        tasks = list_tasks(user_name, collection_name)
        return {"tasks": tasks}
    except Exception as e:
        return {"message": str(e)}

@router.delete("/delete_task/{task_id}/")
async def delete_task_api(user_name: str, task_id: str, collection_name: str = None):
    # Validate user authentication
    if not validate_user(user_name):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not collection_name:
        collection_name = get_collection_name()
    
    try:
        # Call delete_task function from demo.py
        deleted_count = delete_task(user_name, collection_name, task_id)
        if deleted_count > 0:
            return {"message": f"Successfully deleted data with ObjectId: {task_id}"}
        else:
            return {"message": f"No data found with ObjectId: {task_id}"}
    except Exception as e:
        return {"message": str(e)}

@router.put("/update_task/{task_id}/")
async def update_task_api(user_name: str, task_id: str, task_data: TaskUpdate = Form(...), collection_name: str = None):
    # Validate user authentication
    if not validate_user(user_name):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not collection_name:
        collection_name = get_collection_name()
    
    try:
        # Call update_task function from demo.py
        updated_count = update_task(user_name, collection_name, task_id, task_data.task_text)
        if updated_count > 0:
            return {"message": f"Successfully updated task with ObjectId: {task_id}"}
        else:
            return {"message": f"No data found with ObjectId: {task_id}"}
    except Exception as e:
        return {"message": str(e)}

@router.post("/chat_with_gpt3_turbo")
async def chat_with_gpt3_turbo_api(user_name: str, user_input: str = Form(...), collection_name: str = None):
    # Validate user authentication
    if not validate_user(user_name):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not collection_name:
        collection_name = get_collection_name()
    
    try:
        # Call chat_with_gpt3_turbo function from demo.py
        response = chat_with_gpt3_turbo(user_name, collection_name, user_input)
        return response
    except Exception as e:
        return {"message": str(e)}

@router.delete("/delete_all_tasks/")
async def delete_all_tasks_api(user_name: str, collection_name: str = None):
    # Validate user authentication
    if not validate_user(user_name):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not collection_name:
        collection_name = get_collection_name()
    
    try:
        # Connect to the database and drop the entire collection
        collection = get_collection(user_name, collection_name)
        collection.drop()
        return {"message": "All tasks deleted successfully"}
    except Exception as e:
        return {"message": str(e)}

# Include the router in the main app
app.include_router(router, prefix="/tasks")

# Function to validate user
def validate_user(username):
    # Check if the username exists as a database in MongoDB
    mongo_uri = "mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/"
    client = MongoClient(mongo_uri)
    database_names = client.list_database_names()
    return username in database_names

# Function to create a new user (create a new database with the provided username)
def create_new_user(username):
    # Implement your logic here to create a new database with the provided username
    mongo_uri = "mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/"
    client = MongoClient(mongo_uri)
    db = client[username]  # Create a new database with the provided username
    
    # Create an empty collection for the current month
    current_month = get_collection_name()
    db[current_month].insert_one({})  # Insert an empty document to create the collection

    return db
