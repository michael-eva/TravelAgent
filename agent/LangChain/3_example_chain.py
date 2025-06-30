
import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseOutputParser

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")

chat_model=ChatAnthropic(
    model="claude-3-sonnet-20240229",
    temperature=0,
    max_tokens=1024,
    timeout=None,
    max_retries=2,
)
class OutputParser(BaseOutputParser):
    def parse(self, text: str):
        """Parse the output of an LLM call."""
        return text.strip().split(", ")
    
template = """
You are a helpful assistant that generates comma seperated lists.
A user will pass in a category, and you should generate 5 objects in the category in a comma seperated list.
ONLY return the list, and nothing more.
"""
human_template = "{text}"

chat_prompt = ChatPromptTemplate.from_messages([
    ("system",template),
    ("human", human_template),
])

chain = chat_prompt | chat_model | OutputParser()
result = chain.invoke({'text': 'cars'})
print(result)

