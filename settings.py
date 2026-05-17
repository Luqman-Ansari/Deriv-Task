"""
Central configuration for the evaluation pipeline.
All pydantic-ai agents are created via make_agent() so model/provider changes
propagate everywhere from a single place.
"""
import os
from dotenv import load_dotenv
from pydantic_ai import Agent

load_dotenv()

# pydantic-ai Groq provider looks for GROQ_API_KEY; alias GROK_API_KEY if set
_groq_key = os.getenv("GROK_API_KEY")
if _groq_key and not os.getenv("GROQ_API_KEY"):
    os.environ["GROQ_API_KEY"] = _groq_key

MODEL_NAME: str = os.getenv("MODEL_NAME", "groq:meta-llama/llama-4-scout-17b-16e-instruct")
PROVIDER: str = "groq"


def make_agent(output_type: type) -> Agent:
    """Factory that creates a pydantic-ai Agent with the configured model."""
    return Agent(MODEL_NAME, output_type=output_type, retries=3)
