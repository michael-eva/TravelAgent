import os
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from pydantic import SecretStr
from dotenv import load_dotenv
import sys

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
together_api_key = os.getenv("TOGETHER_API_KEY")

# if not api_key:
#     print("Error: ANTHROPIC_API_KEY is not set in .env")
#     exit(1)

open_source_chat_model = ChatOpenAI(
    api_key=SecretStr(together_api_key) if together_api_key else None,
    base_url="https://api.together.xyz/v1",
    model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
    temperature=0.7,
)

chat_model = ChatAnthropic(
    model_name="claude-3-sonnet-20240229",
    temperature=0,
    # max_tokens=1024,
    timeout=None,
    max_retries=2,
    stop="Human:",
)


def ask_agent(question: str):
    # response = chat_model.invoke(question).content
    response = open_source_chat_model.invoke(question).content
    return response


