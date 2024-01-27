from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
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

async def get_db(user_name: str):
    client = AsyncIOMotorClient("your_mongodb_connection_string")  # Replace with your actual MongoDB connection string
    return client[user_name]

@router.post("/add_task/")
async def add_task(task_data: TaskCreate, user_name: str, db = Depends(get_db)):
    collection_name = get_collection_name()
    collection = db[collection_name]

    task_document = {"task_text": task_data.task_text}
    result = await collection.insert_one(task_document)

    return {"message": "Task added successfully", "task_id": str(result.inserted_id)}

@router.get("/list_tasks/")
async def list_tasks(user_name: str, db = Depends(get_db)):
    collection_name = get_collection_name()
    collection = db[collection_name]

    tasks = await collection.find({}, {"_id": 1, "task_text": 1}).to_list(length=None)

    # Convert ObjectId to string
    tasks = [{"_id": str(task["_id"]), "task_text": task["task_text"]} for task in tasks]

    return {"tasks": tasks}

@router.delete("/delete_task/{task_id}/")
async def delete_task(task_id: str, user_name: str, db = Depends(get_db)):
    collection_name = get_collection_name()
    collection = db[collection_name]

    # Validate ObjectId
    try:
        obj_id = ObjectId(task_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format. Please enter a valid ObjectId.")

    result = await collection.delete_one({"_id": obj_id})

    if result.deleted_count > 0:
        return {"message": f"Successfully deleted data with ObjectId: {task_id}"}
    else:
        raise HTTPException(status_code=404, detail=f"No data found with ObjectId: {task_id}")

app.include_router(router)
