
import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")

chat_model=ChatAnthropic(
    model="claude-3-sonnet-20240229",
    temperature=0,
    max_tokens=1024,
    timeout=None,
    max_retries=2,
)

template = "You are a helpful assistant that translates {input_language} to {output_language}."
human_template = "{text}"

chat_prompt = ChatPromptTemplate.from_messages([
    ("system",template),
    ("human", human_template),
])

messages = chat_prompt.format_messages(input_language="English", output_language="French", text="I love programming!")
result = chat_model.invoke(messages)
print(result.content)
