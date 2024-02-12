import openai
from datetime import datetime


# Set your OpenAI API key
openai.api_key = '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'

def get_collection_name():
    # Get the current month name
    return datetime.now().strftime("%B").lower()

def add_task(username, collection_name, task_text):
    # Implement your add_task function here
    pass

def list_tasks(username, collection_name):
    # Implement your list_tasks function here
    pass

def update_task(username, collection_name, task_id, updated_text):
    # Implement your update_task function here
    pass

def delete_task(username, collection_name, task_id):
    # Implement your delete_task function here
    pass

def chat_with_gpt3_turbo(username, collection_name, user_input):
    try:
        # Initialize a list to store conversation history
        conversation_history = []

        # Append username and collection name to conversation history
        conversation_history.append({"role": "user", "content": f"User: {username}"})
        conversation_history.append({"role": "user", "content": f"Collection: {collection_name}"})

        # Append user input to conversation history
        conversation_history.append({"role": "user", "content": user_input})

        # Split user input into words
        input_words = user_input.lower().split()

        # Check for keywords in the user's input
        if "add" in input_words:
            task_text = user_input.split("add", 1)[1].strip()
            task_id = add_task(username, collection_name, task_text)
            return {"message": "Task added with ID:", "task_id": task_id}
        elif "list" in input_words:
            tasks = list_tasks(username, collection_name)
            # Process tasks and return response
            return {"tasks": tasks}
        elif "update" in input_words:
            # Extract task ID and updated text from user input
            task_id = "task_id"  # Dummy value, replace with actual task ID
            updated_text = "updated_text"  # Dummy value, replace with actual updated text
            updated_count = update_task(username, collection_name, task_id, updated_text)
            return {"message": "Task updated:", "updated_count": updated_count}
        elif "delete" in input_words:
            # Extract task ID from user input
            task_id = "task_id"  # Dummy value, replace with actual task ID
            deleted_count = delete_task(username, collection_name, task_id)
            return {"message": "Task deleted:", "deleted_count": deleted_count}
        else:
            # Use OpenAI GPT-3.5-turbo to get assistant's response
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    *conversation_history  # Include conversation history
                ]
            )

            # Extract the response from the API result
            gpt3_turbo_response = response['choices'][0]['message']['content'].strip()

            # Return the AI response
            return {"message": "GPT-3.5-turbo:", "response": gpt3_turbo_response}

    except Exception as e:
        # Return error message if there's an exception
        return {"message": "Error:", "error": str(e)}
