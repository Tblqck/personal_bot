# test_openrouter.py
import os
from dotenv import load_dotenv
from openrouter import OpenRouter

# Load .env variables
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    raise ValueError("❌ OPENROUTER_API_KEY not found in .env")

# Initialize OpenRouter client
client = OpenRouter(api_key=OPENROUTER_API_KEY)

# Send a test chat completion
completion = client.chat.send(
    model="openai/gpt-5.2",
    messages=[{"role": "user", "content": "Say 'test success' in a short comment."}],
    stream=False
)

print("✅ Output:", completion.choices[0].message.content)
