#!/usr/bin/env python3
"""
Utility script to list available models on the configured OpenAI-compatible endpoint.
Usage:
    python -m ai.list_models
"""
import os
import sys
from pathlib import Path
from openai import OpenAI

# Try loading .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    ai_env = Path(__file__).resolve().parent / ".env"
    if ai_env.exists():
        load_dotenv(dotenv_path=ai_env)
    else:
        load_dotenv()
except ImportError:
    pass

def list_models():
    base_url = os.getenv("LLM_BASE_URL", "https://inference.do-ai.run/v1").rstrip("/")
    api_key = os.getenv("LLM_API_KEY", "")

    print(f"Connecting to endpoint: {base_url}")
    if not api_key:
        print("Warning: LLM_API_KEY is not set. Listing models may fail if auth is required.")

    try:
        client = OpenAI(base_url=base_url, api_key=api_key or "no-key", timeout=15.0)
        models = client.models.list()
        print("\nAvailable Models:")
        print("-" * 50)
        found = 0
        for m in models.data:
            print(f"  - {m.id}")
            found += 1
        print("-" * 50)
        print(f"Total: {found} model(s) found.")
    except Exception as e:
        print(f"\nError fetching models from {base_url}: {e}", file=sys.stderr)
        print("\nTip: For DigitalOcean, ensure LLM_API_KEY is set to your DO model access key.", file=sys.stderr)
        print("For local Ollama, ensure Ollama is running and LLM_BASE_URL=http://localhost:11434/v1.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    list_models()
