import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import google.generativeai as genai
import anthropic

# Load configurations
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

app = FastAPI()

# Allow requests from your frontend dev server
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # or ["*"] while prototyping
    allow_credentials=True,
    allow_methods=["*"],          # GET, POST, OPTIONS, etc.
    allow_headers=["*"],          # Content-Type, Authorization, …
)

# Request schema
class ChatRequest(BaseModel):
    prompt: str
    provider: str | None = None  # If None, uses default from config

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    provider = request.provider or config["default_provider"]
    prompt = request.prompt

    if provider == "openai":
        return openai_chat(prompt)
    elif provider == "gemini":
        return gemini_chat(prompt)
    elif provider == "anthropic":
        return anthropic_chat(prompt)
    else:
        return {"error": f"Unsupported provider: {provider}"}

def openai_chat(prompt):
    client = OpenAI(api_key=config["providers"]["openai"]["api_key"])
    model = config["providers"]["openai"]["model"]

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )

    return {
        "provider": "openai",
        "response": response.choices[0].message.content.strip()
    }

# Google Gemini chat handler
def gemini_chat(prompt):
    api_key = config["providers"]["gemini"]["api_key"]
    model = config["providers"]["gemini"]["model"]

    genai.configure(api_key=api_key)
    gemini_model = genai.GenerativeModel(model)

    response = gemini_model.generate_content(prompt)

    return {
        "provider": "gemini",
        "response": response.text.strip()
    }

# Anthropic Claude chat handler
def anthropic_chat(prompt):
    api_key = config["providers"]["anthropic"]["api_key"]
    model = config["providers"]["anthropic"]["model"]

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return {
        "provider": "anthropic",
        "response": response.content[0].text.strip()
    }

