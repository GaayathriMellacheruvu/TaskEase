from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel

app = FastAPI()

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

class TaskCreate(BaseModel):
    task_text: str

@router.post("/add_task/")
async def add_task(task_data: TaskCreate, user_name: str):
    collection_name = get_collection_name()
    client = MongoClient(f"mongodb+srv://mellacheruvugaayathri:Ue99aD5KQLQCL7wZ@cluster0.kavkfm1.mongodb.net/{user_name}")
    db = client[user_name]
    collection = db[collection_name]

    task_document = {"task_text": task_data.task_text}
    result = collection.insert_one(task_document)

    return {"message": "Task added successfully", "task_id": str(result.inserted_id)}

@router.get("/list_tasks/")
async def list_tasks(user_name: str):
    collection_name = get_collection_name()
    client = MongoClient(f"mongodb+srv://mellacheruvugaayathri:Ue99aD5KQLQCL7wZ@cluster0.kavkfm1.mongodb.net/{user_name}")
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
    client = MongoClient(f"mongodb+srv://mellacheruvugaayathri:Ue99aD5KQLQCL7wZ@cluster0.kavkfm1.mongodb.net/{user_name}")
    db = client[user_name]
    collection = db[collection_name]

    try:
        # Convert the input string to ObjectId
        obj_id = ObjectId(task_id)
        result = collection.delete_one({"_id": obj_id})

        if result.deleted_count > 0:
            return {"message": f"Successfully deleted data with ObjectId: {task_id}"}
        else:
            raise HTTPException(status_code=404, detail=f"No data found with ObjectId: {task_id}")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format. Please enter a valid ObjectId.")

app.include_router(router)
