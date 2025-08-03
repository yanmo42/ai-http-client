import json
import os
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import google.generativeai as genai
import anthropic
import logging

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)

# Load configurations (make sure config.yaml exists and is in the correct directory)
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

# File path for storing conversation history
HISTORY_FILE = "conversation_history.json"

# Load conversation history from file (if it exists)
def load_conversation_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}

# Save conversation history to file
def save_conversation_history():
    with open(HISTORY_FILE, "w") as f:
        json.dump(conversation_history, f)

# Initialize conversation history from file
conversation_history = load_conversation_history()

class ChatRequest(BaseModel):
    prompt: str
    provider: str | None = None
    user_id: str
    chat_id: str  # Added chat_id to handle multiple conversations

app = FastAPI()

# Allow requests from your frontend development server (localhost:3000)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # CORS configuration
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        provider = request.provider or config["default_provider"]
        prompt = request.prompt
        user_id = request.user_id  # Use a unique user ID for each session
        chat_id = request.chat_id   # Get the chat ID from the request

        # Initialize conversation history for the user and chat_id if not already present
        if user_id not in conversation_history:
            conversation_history[user_id] = {}

        if chat_id not in conversation_history[user_id]:
            conversation_history[user_id][chat_id] = []

        # Add the new user message to the conversation history for the specific chat
        conversation_history[user_id][chat_id].append({"role": "user", "content": prompt})

        # Save conversation history to file after update
        save_conversation_history()

        # Handle each provider case (OpenAI, Gemini, Anthropic)
        if provider == "openai":
            return openai_chat(user_id, chat_id)
        elif provider == "gemini":
            return gemini_chat(user_id, chat_id)
        elif provider == "anthropic":
            return anthropic_chat(user_id, chat_id)
        else:
            raise HTTPException(status_code=400, detail="Unsupported provider")

    except Exception as e:
        logging.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

def openai_chat(user_id, chat_id):
    client = OpenAI(api_key=config["providers"]["openai"]["api_key"])
    model = config["providers"]["openai"]["model"]

    # Fetch the conversation history for the user and specific chat
    messages = conversation_history[user_id][chat_id]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )

    # Add assistant's reply to conversation history
    conversation_history[user_id][chat_id].append({
        "role": "assistant",
        "content": response.choices[0].message.content.strip()
    })

    # Save conversation history to file after update
    save_conversation_history()

    return {
        "provider": "openai",
        "response": response.choices[0].message.content.strip()
    }

def gemini_chat(user_id, chat_id):
    api_key = config["providers"]["gemini"]["api_key"]
    model = config["providers"]["gemini"]["model"]

    genai.configure(api_key=api_key)
    gemini_model = genai.GenerativeModel(model)

    # Fetch the conversation history for the user and specific chat
    prompt = " ".join([msg['content'] for msg in conversation_history[user_id][chat_id]])
    response = gemini_model.generate_content(prompt)

    # Add assistant's reply to conversation history
    conversation_history[user_id][chat_id].append({
        "role": "assistant",
        "content": response.text.strip()
    })

    # Save conversation history to file after update
    save_conversation_history()

    return {
        "provider": "gemini",
        "response": response.text.strip()
    }

def anthropic_chat(user_id, chat_id):
    api_key = config["providers"]["anthropic"]["api_key"]
    model = config["providers"]["anthropic"]["model"]

    client = anthropic.Anthropic(api_key=api_key)

    # Fetch the conversation history for the user and specific chat
    messages = conversation_history[user_id][chat_id]
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=messages,
    )

    # Add assistant's reply to conversation history
    conversation_history[user_id][chat_id].append({
        "role": "assistant",
        "content": response.content[0].text.strip()
    })

    # Save conversation history to file after update
    save_conversation_history()

    return {
        "provider": "anthropic",
        "response": response.content[0].text.strip()
    }

# Setup logging
logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def handle_exception(request, exc):
    logger.error(f"Unexpected error: {exc}")
    return {"detail": "Internal Server Error"}

