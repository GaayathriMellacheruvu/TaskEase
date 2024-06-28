from fastapi import FastAPI, APIRouter, Form, HTTPException
from fastapi.security import HTTPBasic
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime,timedelta
from bson import ObjectId
from pydantic import BaseModel
from dotenv import load_dotenv
import datefinder
import os
import datefinder
import openai
from demo import chatbot_response
import re
from random import choice
import string
from hashlib import sha256
from typing import Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import ssl

load_dotenv()

# Connect to MongoDB
mongo_uri = "mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/"
client = MongoClient(mongo_uri)
db = client["API_KEY"]
collection = db["openai_api_key"]

# Fetch OpenAI API key from MongoDB
api_key_document = collection.find_one({"name": "openai"})
if api_key_document:
    openai.api_key = api_key_document["key"]
else:
    raise Exception("OpenAI API key not found in the database")

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

# Define data models
class TaskCreate(BaseModel):
    task_text: str
    priority: str
    date: Optional[str] = None
    time: Optional[str] = None
    reminder_date: Optional[str] = None
    reminder_time: Optional[str] = None  # Add reminder settings
    created_at: datetime

class User(BaseModel):
    username: str
    password: str
    email: str  # Added email field to the User model


class ResetToken(BaseModel):
    username: str
    token: str

class Email(BaseModel):
    receiver_email: str
    subject: str
    message: str
    bg_image_path: str

# Store hashed passwords
def hash_password(password: str) -> str:
    return sha256(password.encode()).hexdigest()

from fastapi.responses import JSONResponse

def send_registration_email(receiver_email: str, username: str, subject: str, message: str, bg_image_path: str):
    # Sender's email address and password (you should store these securely)
    sender_email = "ease.tasks@gmail.com"  # Update with your email address
    sender_password = "ozgq lpfs atmi fitu"  # Update with your email password
    sender_name = "TaskEase"

    # Create message container
    msg = MIMEMultipart()
    msg['From'] = f"{sender_name} <{sender_email}>"
    msg['To'] = receiver_email
    msg['Subject'] = subject

    # Load HTML template with email text and background image
    with open("register_email.html", "r") as template_file:
        email_template = template_file.read()

    # Replace username placeholder in the HTML template
    email_template = email_template.replace("{username}", username)

    # Attach HTML content to the email
    msg.attach(MIMEText(email_template, 'html'))

    # Attach background image
    with open(bg_image_path, 'rb') as bg_image_file:
        bg_image = MIMEImage(bg_image_file.read())
        bg_image.add_header('Content-ID', '<bg_image>')
        msg.attach(bg_image)

    # SMTP server setup
    smtp_server = "smtp.gmail.com"
    smtp_port = 587  # Change the port if needed for TLS

    # Create a secure SSL context
    context = ssl.create_default_context()

    try:
        # Connect to the SMTP server
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(sender_email, sender_password)
            # Send email
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("Registration email sent successfully!")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send registration email: {e}")

@router.post("/register/")
async def register(user: User):
    username = user.username
    password = user.password
    email = user.email
    
    # Check if the username or email already exists
    if validate_user_or_email(username) or validate_user_or_email(email):
        raise HTTPException(status_code=400, detail="Username or email already exists")
    
    # Store hashed password in the 'passwords' collection
    store_password(username, hash_password(password))
    
    # Store username and email in the 'emails' collection
    store_user_email(username, email)
    
    # Create a new database with the provided username
    create_new_user(username)

    # Send welcome email to the newly registered user
    subject = "Registration Successful"
    message = "Thank you for registering with TaskEase. Your account has been successfully created."
    bg_image_path = "bg_image.png"
    send_registration_email(email, username, subject, message, bg_image_path)

    return {"message": "User registered successfully", "email_sent": True}

def validate_user_or_email(identifier: str) -> bool:
    database_names = client.list_database_names()
    emails_collection = db["emails"]
    user_exists = identifier in database_names
    email_exists = emails_collection.find_one({"email": identifier}) is not None
    return user_exists or email_exists

def store_user_email(username: str, email: str):
    # Connect to the 'emails' collection in the 'API_KEY' database
    emails_collection = db["emails"]

    # Insert the username and email into the collection
    emails_collection.insert_one({"username": username, "email": email})

# Login endpoint
security = HTTPBasic()

@router.post("/login/")
async def login(username: str = Form(...), password: str = Form(...)):
    # Check if the provided credentials are valid
    if not validate_credentials(username, hash_password(password)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"message": "Login successful"}

# Add task endpoint
@app.post("/tasks/add_task")
async def add_task(task: TaskCreate, username: str, collection_name: str = None):
    # Connect to MongoDB
    db = client[username]
    tasks_collection = db[collection_name]

    # Extract date, time, and reminder settings from task text using datefinder
    extracted_datetime = extract_datetime(task.task_text)
    if extracted_datetime:
        task.date = extracted_datetime.strftime("%Y-%m-%d")
        task.time = extracted_datetime.strftime("%H:%M:%S")
        # For simplicity, assuming the reminder is set a day before the task date
        # task.reminder_date = (extracted_datetime - timedelta(days=1)).strftime("%Y-%m-%d")
        # task.reminder_time = "09:00:00"  # Set a default reminder time
        
    # Check if a task with the same date and time already exists
    existing_task = tasks_collection.find_one({"date": task.date, "time": task.time})
    if existing_task:
        raise HTTPException(status_code=400, detail="Task with the same date and time already exists")

    # Convert created_at datetime object to ISO format string
    task.created_at = datetime.now()

    # Insert task data into the database
    result = tasks_collection.insert_one(task.dict())

    # Check if task insertion was successful
    if result.inserted_id:
        return {"message": "Task added successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to add task")
    
def extract_datetime(task_text: str) -> Optional[datetime]:
    # Use datefinder to extract date and time from task text
    matches = list(datefinder.find_dates(task_text))
    if matches:
        return matches[0]
    return None

# Delete task endpoint
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

# Update task endpoint
@router.put("/update_task/{task_id}/")
async def update_task_api(username: str, task_id: str, task_data: TaskCreate, collection_name: str = None):
    # Validate user authentication
    if not validate_user(username):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not collection_name:
        collection_name = get_collection_name()

    try:
        # Connect to MongoDB
        db = client[username]
        tasks_collection = db[collection_name]

        # Convert task_data to dictionary
        task_data_dict = task_data.dict()

        # Remove created_at field from task_data_dict to avoid updating it
        task_data_dict.pop("created_at", None)

        # Extract date and time from task text if present
        extracted_datetime = extract_datetime(task_data.task_text)
        if extracted_datetime:
            task_data_dict["date"] = extracted_datetime.strftime("%Y-%m-%d")
            task_data_dict["time"] = extracted_datetime.strftime("%H:%M:%S")

        # Set the updated_at field to the current datetime
        task_data_dict["updated_at"] = datetime.now()

        # Perform the update operation
        result = tasks_collection.update_one({"_id": ObjectId(task_id)}, {"$set": task_data_dict})

        # Check if any document was modified
        if result.modified_count > 0:
            return {"message": f"Successfully updated task with ObjectId: {task_id}"}
        else:
            return {"message": f"No data found with ObjectId: {task_id}"}
    except Exception as e:
        return {"message": "Failed to update task", "error": str(e)}

# List tasks endpoint
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

# Reset password endpoint
@router.post("/reset_password/")
async def reset_password(reset_token: ResetToken, new_password: str):
    username = reset_token.username
    token = reset_token.token
    
    # Check if the reset token is valid
    reset_tokens_collection = db["reset_tokens"]
    reset_token_record = reset_tokens_collection.find_one({"username": username, "token": token})
    if reset_token_record is None:
        raise HTTPException(status_code=404, detail="Invalid token")
    # Update the password in the passwords collection
    passwords_collection = db["passwords"]
    passwords_collection.update_one({"username": username}, {"$set": {"password": hash_password(new_password)}})
    # Delete the reset token from MongoDB
    reset_tokens_collection.delete_one({"username": username, "token": token})
    return {"message": "Password reset successfully"}

# Forgot password endpoint
@router.post("/forgot_password/")
async def forgot_password(username: str):
    # Check if the username exists
    if not validate_user(username):
        raise HTTPException(status_code=404, detail="User not found")
    # Fetch user's email address from the 'emails' collection
    user_email = get_user_email(username)
    if user_email:
        # Generate a random token
        token = generate_token()
        # Store the token in MongoDB with a TTL index for auto-expiration after 15 minutes
        reset_tokens_collection = db["reset_tokens"]
        reset_tokens_collection.create_index("createdAt", expireAfterSeconds=900)
        reset_tokens_collection.insert_one({"username": username, "token": token, "createdAt": datetime.utcnow()})

        # Send email with reset token
        subject = "Password Reset"
        message = f"Dear User,\n\nWe are pleased to assist you with resetting your password. Below, you will find your personalized password reset token, carefully crafted for your security:\n\nToken: {token}\n\nShould you require any further assistance or have any questions, please do not hesitate to reach out to our support team.\n\nBest regards,\nThe TaskEase Team"
        bg_image_path = "bg_image.png"  
        send_password_email(user_email, subject, token, bg_image_path)

        return {"message": "Token generated successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send email: User email not found")

def get_user_email(username: str) -> Optional[str]:
    # Query the MongoDB collection to fetch the user's email address
    user_collection = db["emails"]  # Assuming emails are stored in a collection named "emails"
    user_data = user_collection.find_one({"username": username})
    if user_data:
        return user_data.get("email")
    else:
        return None

from apscheduler.schedulers.background import BackgroundScheduler
# Initialize the scheduler
db = client["API_KEY"]

# Initialize the scheduler
scheduler = BackgroundScheduler()

# Start the scheduler
scheduler.start()

# Define a function to send reminder emails
def send_reminder_emails():
    # Get current time
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Iterate through users and their collections
    for username in client.list_database_names():
        # Check if the current month collection exists
        current_month_collection_name = datetime.now().strftime("%B")
        if current_month_collection_name in client[username].list_collection_names():
            collection = client[username][current_month_collection_name]
            tasks = collection.find({"reminder_date": current_time.split()[0], "reminder_time": current_time.split()[1]})
            for task in tasks:
                # Get the email address of the user
                user_email = get_user_email(username)
                if user_email:
                    # Send reminder email
                    send_email(user_email, "Task Reminder", task["task_text"], "bg_image.png")
                else:
                    print(f"Failed to send reminder email for task: {task['_id']}. User email not found.")

# Schedule the function to run every minute
scheduler.add_job(send_reminder_emails, 'interval', minutes=1)

def get_user_email(username: str) -> str:
    # Query the MongoDB collection to fetch the user's email address
    user_collection = db["emails"]  
    user_data = user_collection.find_one({"username": username})
    if user_data:
        return user_data.get("email", "")
    else:
        return ""

def send_password_email(receiver_email: str, subject: str, token: str, bg_image_path: str):
    # Sender's email address and password (you should store these securely)
    sender_email = "ease.tasks@gmail.com"
    sender_password = "ozgq lpfs atmi fitu"
    sender_name = "TaskEase"

    # Create message container - the correct MIME type is multipart/related
    msg = MIMEMultipart('related')
    msg['From'] = f"{sender_name} <{sender_email}>"
    msg['To'] = receiver_email
    msg['Subject'] = subject

    # Load HTML template with email text and background image
    with open("email_template.html", "r") as template_file:
        email_template = template_file.read()

    # Replace token placeholder in the HTML template
    email_template = email_template.replace("{token}", token)

    # Attach HTML content to the email
    msg.attach(MIMEText(email_template, 'html'))

    # Attach background image
    with open(bg_image_path, 'rb') as bg_image_file:
        bg_image = MIMEImage(bg_image_file.read())
        bg_image.add_header('Content-ID', '<bg_image>')
        msg.attach(bg_image)

    # SMTP server setup
    smtp_server = "smtp.gmail.com"
    smtp_port = 465  # Change the port if needed for SSL/TLS

    # Create a secure SSL context
    context = ssl.create_default_context()

    try:
        # Connect to the SMTP server
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(sender_email, sender_password)
            # Send email
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("Email sent successfully!")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")
        
def send_email(receiver_email: str, subject: str, message: str, bg_image_path: str):
    # Sender's email address and password (you should store these securely)
    sender_email = "ease.tasks@gmail.com"
    sender_password = "ozgq lpfs atmi fitu"
    sender_name = "TaskEase"

    # Create message container - the correct MIME type is multipart/related
    msg = MIMEMultipart('related')
    msg['From'] = f"{sender_name} <{sender_email}>"
    msg['To'] = receiver_email
    msg['Subject'] = subject

    # Load HTML template with email text
    with open("notif_email.html", "r") as template_file:
        email_template = template_file.read()

    # Replace message placeholder in the HTML template
    email_template = email_template.replace("{message}", message)

    # Attach HTML content to the email
    msg.attach(MIMEText(email_template, 'html'))

    # Attach background image
    with open(bg_image_path, 'rb') as bg_image_file:
        bg_image = MIMEImage(bg_image_file.read())
        bg_image.add_header('Content-ID', '<bg_image>')
        msg.attach(bg_image)

    # SMTP server setup
    smtp_server = "smtp.gmail.com"
    smtp_port = 587  # Change the port if needed for TLS

    # Create a secure SSL context
    context = ssl.create_default_context()

    try:
        # Connect to the SMTP server
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(sender_email, sender_password)
            # Send email
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("Reminder email sent successfully!")
    except Exception as e:
        print(f"Failed to send reminder email: {e}")

# Chat with chatbot endpoint
@router.post("/chat_with_chatbot")
async def chat_with_chatbot(user_input: str, username: str, collection_name: str):
    # Call chatbot_response function from chat_module
    response = chatbot_response(user_input, username, collection_name)
    return {"response": response}

# Get collections endpoint
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
    
@router.get("/tasks/filter/")
async def filter_tasks(username: str, priority: Optional[str] = None, status: Optional[str] = None):
    # Validate user authentication
    if not validate_user(username):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not priority and not status:
        raise HTTPException(status_code=400, detail="Please provide at least one filter criteria")

    try:
        # Call filter_tasks function
        filtered_tasks = filter_tasks(username, priority, status)
        return {"tasks": filtered_tasks}
    except Exception as e:
        return {"message": "Failed to filter tasks", "error": str(e)}

def filter_tasks(username, priority=None, status=None):
    collection_name = get_collection_name()
    collection = get_collection(username, collection_name)
    filter_criteria = {}
    if priority:
        filter_criteria["priority"] = priority
    if status:
        filter_criteria["status"] = status
    tasks = list(collection.find(filter_criteria))
    formatted_tasks = []
    for task in tasks:
        formatted_task = {
            "task_id": str(task["_id"]),
            "task_text": task.get("task_text", ""),
            "priority": task.get("priority", ""),
            "date": task.get("date", ""),
            "time": task.get("time", ""),
            "created_at": task.get("created_at", "") 
        }
        formatted_tasks.append(formatted_task)
    return formatted_tasks

from fastapi import Query

@router.get("/tasks/reminder/")
async def get_tasks_by_reminder(
    username: str,
    collection_name: str,
    reminder_date: str = Query(..., description="Reminder date in YYYY-MM-DD format"),
    reminder_time: str = Query(..., description="Reminder time in HH:MM:SS format")
):
    tasks = find_tasks_by_reminder(username, collection_name, reminder_date, reminder_time)
    return {"tasks": tasks}

def find_tasks_by_reminder(username: str, collection_name: str, reminder_date: str, reminder_time: str):
    collection = get_collection(username, collection_name)
    tasks = list(collection.find({"reminder_date": reminder_date, "reminder_time": reminder_time}, {"_id": 0, "task_text": 1}))
    return [task["task_text"] for task in tasks]


@router.post("/tasks/delete_bulk/")
async def delete_bulk_tasks(username: str, collection_name: str):
    # Validate user authentication
    if not validate_user(username):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        # Call delete_bulk_tasks function
        deleted_count = delete_bulk_tasks(username, collection_name)
        return {"message": f"{deleted_count} tasks deleted successfully"}
    except Exception as e:
        return {"message": "Failed to delete tasks", "error": str(e)}

def delete_bulk_tasks(username, collection_name):
    collection = get_collection(username, collection_name)
    result = collection.delete_many({})
    return result.deleted_count


# Helper functions

def get_collection_name():
    month_name = datetime.now().strftime("%B")
    capitalized_month_name = month_name.capitalize()
    return capitalized_month_name

def get_collection(username, collection_name):
    db = client[username]
    return db[collection_name]

def list_tasks(username, collection_name):
    collection = get_collection(username, collection_name)
    # Use projection to include all required fields
    tasks = list(collection.find({}, {"_id": 1, "task_text": 1, "created_at": 1, "priority": 1, "date": 1, "time": 1, "reminder_date": 1, "reminder_time": 1}))
    formatted_tasks = []
    for task in tasks:
        formatted_task = {
            "task_id": str(task["_id"]),
            "task_text": task.get("task_text", ""),
            "priority": task.get("priority", ""),
            "date": task.get("date", ""),
            "time": task.get("time", ""),
            "reminder_date": task.get("reminder_date", ""),  # Include reminder_date
            "reminder_time": task.get("reminder_time", ""),  # Include reminder_time
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

def validate_user(username):
    database_names = client.list_database_names()
    return username in database_names

def create_new_user(username):
    db = client[username]
    current_month = get_collection_name()
    # Create an empty collection
    db.create_collection(current_month)
    return db

# Generate a random token
def generate_token(length=10):
    characters = string.ascii_letters + string.digits
    return ''.join(choice(characters) for i in range(length))

# Store password in MongoDB
def store_password(username: str, password_hash: str):
    passwords_collection = db["passwords"]
    passwords_collection.insert_one({"username": username, "password": password_hash})

# Validate credentials
def validate_credentials(username: str, password_hash: str) -> bool:
    passwords_collection = db["passwords"]
    user = passwords_collection.find_one({"username": username, "password": password_hash})
    return user is not None

# Include the router in the main app
app.include_router(router, prefix="/tasks")