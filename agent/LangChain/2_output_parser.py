
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
class OutputParser:
    def parse(self, text: str):
        """Parse the output of an LLM call."""
        return text.strip().split("answer = ")
template = """
You are a helpful assistant that solves math problems and shows your work.
Output each step then return the answer in the following format: answer = <answer here>.
Make sure to output the answer in all lowercase and to have exactly one space between the equals sign and the answer.
"""
human_template = "{problem}"

chat_prompt = ChatPromptTemplate.from_messages([
    ("system",template),
    ("human", human_template),
])

messages = chat_prompt.format_messages(problem="2x^2 - 5x + 3 = 0")
result = chat_model.invoke(messages)
parsed = OutputParser().parse(result.content)
steps, answer = parsed
print(steps)

