# test_providers.py
import os
from dotenv import load_dotenv
import aisuite as ai

load_dotenv()

client = ai.Client()

models_to_test = [
    "groq:openai/gpt-oss-120b",
    "openrouter:nvidia/nemotron-3-super-120b-a12b:free",
    "groq:qwen/qwen3.8-27b",
]

for model in models_to_test:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=200,
        )
        print(f"✅ {model}: {response.choices[0].message.content.strip()}")
    except Exception as e:
        print(f"❌ {model}: {type(e).__name__} - {str(e)[:100]}")