# core_brain.py
import os
import asyncio
import json
from collections import Counter
from dotenv import load_dotenv
from openrouter import OpenRouter

# -----------------------
# Config
# -----------------------
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in .env")

# Ranked models for ensemble voting
MODELS = [
    "openai/gpt-5.2",
    "openai/gpt-5.1",
    "openai/gpt-4o-mini",
    "meta-llama/llama-3.1-70b-instruct",
    "qwen/qwen3-max-thinking",
]

client = OpenRouter(api_key=OPENROUTER_API_KEY)

# -----------------------
# Sync call wrapper
# -----------------------
def call_model_sync(model_name, user_packet):
    """
    Call a single model to detect intent
    """
    prompt = f"""
You are an assistant that detects user intent.
Possible intents: list, create, update, delete, chat
You are given the user packet:
{json.dumps(user_packet, indent=2)}
Respond in JSON format:
{{ "intent": "<intent>", "confidence": 0-1, "message": "<short summary>" }}
"""
    try:
        completion = client.chat.send(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        text = completion.choices[0].message.content.strip()
        data = json.loads(text)
        data["model"] = model_name
        return data
    except Exception as e:
        return {"intent": "chat", "confidence": 0, "message": f"Error: {str(e)}", "model": model_name}


# -----------------------
# Async wrapper
# -----------------------
async def call_model_async(model_name, user_packet):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, call_model_sync, model_name, user_packet)


# -----------------------
# Ensemble voting
# -----------------------
async def detect_intent(user_packet):
    """
    user_packet example:
    {
        "user_id": str,
        "user_message": str,
        "chat_context": [...],
        "tasks": [...],
        "user_timezone": str,
        "current_time": ISO string
    }
    """
    tasks = [call_model_async(m, user_packet) for m in MODELS]
    results = await asyncio.gather(*tasks)

    # Count votes
    intents = [r["intent"] for r in results]
    intent_counts = Counter(intents)
    winning_intent = intent_counts.most_common(1)[0][0]

    # Pick response from highest-ranked model predicting winning intent
    winning_response = None
    for model_name in MODELS:
        for r in results:
            if r["model"] == model_name and r["intent"] == winning_intent:
                winning_response = r.get("message", "")
                break
        if winning_response:
            break

    return {
        "intent": winning_intent,
        "response": winning_response,
        "stats": {
            "votes": dict(intent_counts),
            "model_results": results
        }
    }


# -----------------------
# Sync callable
# -----------------------
def get_ensemble_intent(user_packet):
    import nest_asyncio
    nest_asyncio.apply()
    return asyncio.run(detect_intent(user_packet))
