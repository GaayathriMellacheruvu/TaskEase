from fastapi import FastAPI, APIRouter, Form
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel
import openai
from typing import List, Dict, Union

app = FastAPI()

openai.api_key = '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'

@app.on_event("startup")
async def startup_event():
    # Add your startup initialization code here
    pass

def get_collection_name():
    current_month = datetime.now().strftime("%B").lower()
    return current_month

router = APIRouter()

# Add CORS middleware
origins = ["*"]  # Change this to your frontend's actual domain in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskUpdate(BaseModel):
    task_text: str

class TaskResponse(BaseModel):
    task_id: str
    task_text: str

class TaskCreate(BaseModel):
    task_text: str

@router.post("/add_task/")
async def add_task(task_data: TaskCreate, user_name: str):
    collection_name = get_collection_name()
    client = MongoClient(f"mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/{user_name}")
    db = client[user_name]
    collection = db[collection_name]

    task_document = {"task_text": task_data.task_text}
    result = collection.insert_one(task_document)

    return {"message": "Task added successfully", "task_id": str(result.inserted_id)}

@router.get("/list_tasks/")
async def list_tasks(user_name: str):
    collection_name = get_collection_name()
    client = MongoClient(f"mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/{user_name}")
    db = client[user_name]
    collection = db[collection_name]

    tasks = list(collection.find({}, {"_id": 1, "task_text": 1}))

    # Convert ObjectId to string
    for task in tasks:
        task["_id"] = str(task["_id"])

    return {"tasks": tasks}

@router.delete("/delete_task/{task_id}/")
async def delete_task(task_id: str, user_name: str):
    collection_name = get_collection_name()
    client = MongoClient(f"mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/{user_name}")
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

@router.put("/update_task/{task_id}/")
async def update_task(task_id: str, task_data: TaskUpdate, user_name: str):
    collection_name = get_collection_name()
    client = MongoClient(f"mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/{user_name}")
    db = client[user_name]
    collection = db[collection_name]

    try:
        # Convert the input string to ObjectId
        obj_id = ObjectId(task_id)
        result = collection.update_one({"_id": obj_id}, {"$set": {"task_text": task_data.task_text}})

        if result.modified_count > 0:
            return {"message": f"Successfully updated task with ObjectId: {task_id}"}
        else:
            return {"message": f"No data found with ObjectId: {task_id}"}
    except Exception as e:
        return {"message": "Invalid ObjectId format. Please enter a valid ObjectId."}

@router.get("/get_task/{task_id}/")
async def get_task(task_id: str, user_name: str):
    collection_name = get_collection_name()
    client = MongoClient(f"mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/{user_name}")
    db = client[user_name]
    collection = db[collection_name]

    try:
        # Convert the input string to ObjectId
        obj_id = ObjectId(task_id)
        task = collection.find_one({"_id": obj_id}, {"_id": 1, "task_text": 1})

        if task:
            task["_id"] = str(task["_id"])
            return {"task": task}
        else:
            return {"message": f"No data found with ObjectId: {task_id}"}
    except Exception as e:
        return {"message": "Invalid ObjectId format. Please enter a valid ObjectId."}

@router.delete("/delete_all_tasks/")
async def delete_all_tasks(user_name: str):
    collection_name = get_collection_name()
    client = MongoClient(f"mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/{user_name}")
    db = client[user_name]
    collection = db[collection_name]

    result = collection.delete_many({})

    if result.deleted_count > 0:
        return {"message": "All tasks deleted successfully"}
    else:
        return {"message": "No tasks found to delete"}

@router.post("/chat_with_gpt3_turbo")
async def chat_with_gpt3_turbo(user_name: str, user_input: str = Form(...)):
    try:
        # Use OpenAI GPT-3.5-turbo to get assistant's response
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_input},
            ]
        )

        gpt3_turbo_response = response['choices'][0]['message']['content'].strip()

        return {'success': True, 'response': gpt3_turbo_response}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# Include the router in the main app
app.include_router(router, prefix="/tasks")
