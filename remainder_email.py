# reminder_emails.py

from pymongo import MongoClient
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import ssl
from apscheduler.schedulers.background import BackgroundScheduler

# Connect to MongoDB
mongo_uri = "mongodb+srv://taskease:102938@cluster0.kavkfm1.mongodb.net/"
client = MongoClient(mongo_uri)
db = client["API_KEY"]

# Set up SSL context
context = ssl.create_default_context()

def send_reminder_emails():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Iterate through users and their collections
    for username in client.list_database_names():
        current_month_collection_name = datetime.now().strftime("%B")
        if current_month_collection_name in client[username].list_collection_names():
            collection = client[username][current_month_collection_name]
            tasks = collection.find({"reminder_date": current_time.split()[0], "reminder_time": current_time.split()[1]})
            for task in tasks:
                user_email = get_user_email(username)
                if user_email:
                    send_email(user_email, "Task Reminder", task["task_text"], "bg_image.png")
                else:
                    print(f"Failed to send reminder email for task: {task['_id']}. User email not found.")

def get_user_email(username: str) -> str:
    user_collection = db["emails"]  
    user_data = user_collection.find_one({"username": username})
    if user_data:
        return user_data.get("email", "")
    else:
        return ""

def send_email(receiver_email: str, subject: str, message: str, bg_image_path: str):
    sender_email = "ease.tasks@gmail.com"
    sender_password = "ozgq lpfs atmi fitu"
    sender_name = "TaskEase"

    msg = MIMEMultipart('related')
    msg['From'] = f"{sender_name} <{sender_email}>"
    msg['To'] = receiver_email
    msg['Subject'] = subject

    # Load HTML template with email text
    with open("notif_email.html", "r") as template_file:
        email_template = template_file.read()

    email_template = email_template.replace("{message}", message)

    msg.attach(MIMEText(email_template, 'html'))

    with open(bg_image_path, 'rb') as bg_image_file:
        bg_image = MIMEImage(bg_image_file.read())
        bg_image.add_header('Content-ID', '<bg_image>')
        msg.attach(bg_image)

    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("Reminder email sent successfully!")
    except Exception as e:
        print(f"Failed to send reminder email: {e}")

# Initialize the scheduler
scheduler = BackgroundScheduler()

# Start the scheduler
scheduler.start()

# Schedule the function to run every minute
scheduler.add_job(send_reminder_emails, 'interval', minutes=1)

# Keep the script running
# input("Press enter to exit.")
