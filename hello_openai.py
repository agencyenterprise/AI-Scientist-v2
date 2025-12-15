#!/usr/bin/env python3
"""
Quick hello-world script to confirm the OpenAI API key works.
Loads environment variables from `.env`, calls a small chat completion,
and prints the model's reply.
"""

import sys
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def main() -> int:
    # Load .env from repository root
    load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

    print(f"OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY')}")

    client = OpenAI()
    prompt = "Say a friendly hello world in one short sentence."
    
    # Test model - change this to test different models
    model = "gpt-5.2"
    print(f"Testing model: {model}")

    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=20,
    )

    message = completion.choices[0].message.content
    print(message.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
