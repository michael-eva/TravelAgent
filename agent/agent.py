from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langchain_google_community import GooglePlacesTool 
from .google_route_tool import GoogleRoutesTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import SecretStr
from langchain_core.runnables import RunnableConfig
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

tavily_api_key = os.getenv("TAVILY_API_KEY")
together_api_key = os.getenv("TOGETHER_API_KEY")
google_places_api_key = os.getenv("GPLACES_API_KEY")

if not all([tavily_api_key, together_api_key, google_places_api_key]):
    missing = []
    if not tavily_api_key: missing.append("TAVILY_API_KEY")
    if not together_api_key: missing.append("TOGETHER_API_KEY")
    if not google_places_api_key: missing.append("GOOGLE_PLACES_API_KEY")
    raise ValueError(f"Missing API keys: {', '.join(missing)}")

memory = MemorySaver()
model = ChatOpenAI(
    api_key=SecretStr(together_api_key) if together_api_key else None,
    base_url="https://api.together.xyz/v1",
    model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
    temperature=0.7,
)
search = TavilySearch(tavily_api_key=tavily_api_key, max_results=5)
places = GooglePlacesTool()
routes = GoogleRoutesTool()
tools = [search, places, routes]

template = """
You're a serious most of the time, but sarcastic some of the time. Every now and again you throw a 'penis' into the conversation.
When giving directions, don't give me the directions, just give me a summary of the route and a link to the destination/s on google maps.

{context_info}
"""

agent_executor = create_react_agent(model, tools, checkpointer=memory, prompt=template)
config: RunnableConfig = {"configurable": {"thread_id": "abc123"}}

def get_location_context(user_context: dict) -> str:
    """Extract location context for the agent prompt"""
    if not user_context or 'current_location' not in user_context:
        return ""
    
    location = user_context['current_location']
    
    # Check if location is still valid (within 30 minutes)
    if 'timestamp' in location:
        time_diff = datetime.now() - location['timestamp']
        if time_diff > timedelta(minutes=30):
            return ""  # Location too old
        
        minutes_ago = time_diff.seconds // 60
        time_info = f" (shared {minutes_ago} minutes ago)" if minutes_ago > 0 else " (just shared)"
    else:
        time_info = ""
    
    context = f"""
IMPORTANT CONTEXT: The user has shared their current location:
- Latitude: {location['latitude']:.6f}
- Longitude: {location['longitude']:.6f}
- Location shared: {time_info}

When the user asks for directions, routes, or navigation:
1. Use their current location as the starting point if no origin is specified
2. The GoogleRoutesTool will automatically use this location when origin is empty
3. Always mention that you're using their current location as the starting point
"""
    return context

def ask_agent(question: str, user_context: dict):
    """
    Ask the agent a question with optional user context (like current location)
    
    Args:
        question: The user's question
        user_context: Dictionary containing user data like current_location
    """
    
    # Build context information for the prompt
    context_info = get_location_context(user_context) if user_context else ""
    
    # Update the prompt template with context
    current_template = template.format(context_info=context_info)
    
    # Create context-aware tools
    context_routes = GoogleRoutesTool(user_context=user_context) if user_context else routes
    context_tools = [search, places, context_routes]
    
    # Create agent with context-aware tools and updated prompt
    current_agent = create_react_agent(
        model, 
        context_tools, 
        checkpointer=memory, 
        prompt=current_template
    )
    
    input_message = {"role": "user", "content": question}
    
    response_content = ""
    
    try:
        for step in current_agent.stream(
            {"messages": [input_message]}, config, stream_mode="values"
        ):
            last_message = step["messages"][-1]
            
            # Check if this is a tool call
            if hasattr(last_message, 'content'):
                response_content = last_message.content
            elif isinstance(last_message, dict) and 'content' in last_message:
                response_content = last_message['content']
            else:
                response_content = str(last_message)
                
    except Exception as e:
        print(f"Error during agent execution: {e}")
        return f"Error: {e}"
    
    return response_content if response_content else "Sorry, I couldn't generate a response."
