import telebot
from telebot import types
import pytz
from . import config
import sys
import os
import googlemaps
from datetime import datetime, timedelta

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.agent import ask_agent

P_TIMEZONE = pytz.timezone(config.TIMEZONE)
TIMEZONE_COMMON_NAME = config.TIMEZONE_COMMON_NAME

if not config.TOKEN:
    print("Error: TOKEN is not set in config.py")
    sys.exit(1)

bot = telebot.TeleBot(config.TOKEN)

# Initialize Google Maps client for reverse geocoding
try:
    gmaps = googlemaps.Client(key=os.getenv("GPLACES_API_KEY"))
except:
    gmaps = None
    print("Warning: Google Maps client not initialized - location features may not work")

# Store user data (in production, use a proper database)
user_data = {}

# Keywords that indicate user wants directions
DIRECTION_KEYWORDS = [
    'directions', 'route', 'how to get', 'navigate', 'drive to', 'walk to',
    'go to', 'travel to', 'trip to', 'way to', 'path to', 'find route',
    'take me to', 'get me to', 'show me the way', 'best route', 'closest'
]
PLAN_MODIFICATION_KEYWORDS = [
    'update', 'update my', 'update my plan', 'update my travel plan', 'update travel plan',
    'add to plan', 'remove from plan', 'delete from plan', 'change plan',
    'modify plan', 'edit plan', 'add restaurant', 'add hotel', 'add activity',
    'remove restaurant', 'remove hotel', 'cancel booking', 'replace with',
    'insert', 'include', 'exclude', 'swap', 'substitute'
]
def needs_plan_modification(message_text):
    """Check if message is asking to modify the travel plan"""
    message_lower = message_text.lower()
    return any(keyword in message_lower for keyword in PLAN_MODIFICATION_KEYWORDS)
def extract_travel_plan_from_response(agent_response):
    """Extract and format travel plan from agent response with existing Google Maps links"""
    
    # The agent response already contains the formatted travel plan with links
    # We just need to wrap it in a nice format for the pinned message
    
    formatted_plan = f"📋 **Your Travel Plan**\n\n{agent_response}\n\n"
    formatted_plan += f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_"
    
    return formatted_plan

def needs_directions(message_text):
    """Check if message is asking for directions"""
    message_lower = message_text.lower()
    return any(keyword in message_lower for keyword in DIRECTION_KEYWORDS)

def has_valid_location(user_id):
    """Check if user has shared location recently (within 30 minutes)"""
    if user_id not in user_data or 'current_location' not in user_data[user_id]:
        return False
    
    location_data = user_data[user_id]['current_location']
    if 'timestamp' in location_data:
        time_diff = datetime.now() - location_data['timestamp']
        return time_diff < timedelta(minutes=30)
    
    return False

def get_address_from_coords(lat, lng):
    """Convert coordinates to readable address"""
    if not gmaps:
        return f"({lat:.4f}, {lng:.4f})"
    
    try:
        result = gmaps.reverse_geocode((lat, lng)) # type: ignore
        if result:
            return result[0]['formatted_address']
        return f"({lat:.4f}, {lng:.4f})"
    except Exception as e:
        print(f"Reverse geocoding error: {e}")
        return f"({lat:.4f}, {lng:.4f})"

def request_location(message):
    """Request user's location with custom keyboard"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    
    # Create location button
    location_button = types.KeyboardButton("📍 Share My Location", request_location=True)
    skip_button = types.KeyboardButton("❌ Skip Location")
    
    markup.add(location_button, skip_button)
    
    bot.send_message(
        message.chat.id,
        "🗺️ To give you accurate directions from your current location, "
        "please share your location by tapping the button below:\n\n"
        "📱 This helps me calculate the best route for you!",
        reply_markup=markup
    )
    
    # Store the original message to process after location is received
    if message.from_user.id not in user_data:
        user_data[message.from_user.id] = {}
    user_data[message.from_user.id]['pending_direction_query'] = message.text

@bot.message_handler(commands=['start', 'hello'])
def send_welcome(message):
    bot.reply_to(message, "Howdy, how are you doing?")
@bot.message_handler(commands=['location'])
def manual_location_request(message):
    """Manual location request command"""
    user_id = message.from_user.id
    
    # Initialize user_data if needed
    if user_id not in user_data:
        user_data[user_id] = {}
    
    # Store a placeholder query so the location handler knows this was a manual request
    user_data[user_id]['pending_direction_query'] = "manual_location_request"
    
    request_location(message)
@bot.message_handler(content_types=['location'])
def handle_location(message):
   """Handle when user shares their location"""
   user_id = message.from_user.id
   
   # Store the location data
   if user_id not in user_data:
       user_data[user_id] = {}
   
   location_data = {
       'latitude': message.location.latitude,
       'longitude': message.location.longitude,
       'timestamp': datetime.now()
   }
   
   user_data[user_id]['current_location'] = location_data
   
   # Get readable address
   address = get_address_from_coords(message.location.latitude, message.location.longitude)
   
   # Remove keyboard
   markup = types.ReplyKeyboardRemove()
   
   # Check if this was a manual location request
   if (user_id in user_data and 
       'pending_direction_query' in user_data[user_id] and 
       user_data[user_id]['pending_direction_query'] == "manual_location_request"):
       
       # Just confirm location was saved
       bot.send_message(
           message.chat.id,
           f"📍 Location saved: {address}\n\n✅ You can now ask for directions and I'll use this location!",
           reply_markup=markup
       )
       del user_data[user_id]['pending_direction_query']
       return
   
   bot.send_message(
       message.chat.id,
       f"📍 Got your location: {address}\n\nNow processing your request...",
       reply_markup=markup
   )
   
   # Process the pending query with location
   if user_id in user_data and 'pending_direction_query' in user_data[user_id]:
       original_query = user_data[user_id]['pending_direction_query']
       del user_data[user_id]['pending_direction_query']
       
       try:
           # Add location context to user data
           context = user_data.get(user_id, {})
           response = ask_agent(original_query, user_context=context)
           
           bot.send_message(message.chat.id, response)
       except Exception as e:
           bot.send_message(message.chat.id, f"Sorry, I encountered an error: {str(e)}")
@bot.message_handler(func=lambda message: message.text == "❌ Skip Location")
def handle_skip_location(message):
    """Handle when user skips sharing location"""
    user_id = message.from_user.id
    
    # Remove keyboard
    markup = types.ReplyKeyboardRemove()
    
    bot.send_message(
        message.chat.id,
        "⚠️ No problem! You can still ask for directions, but you'll need to "
        "specify your starting location in your message.\n\n"
        "For example: 'Directions from Times Square to Central Park'",
        reply_markup=markup
    )
    
    # Process pending query without location
    if user_id in user_data and 'pending_direction_query' in user_data[user_id]:
        original_query = user_data[user_id]['pending_direction_query']
        del user_data[user_id]['pending_direction_query']
        
        try:
            response = ask_agent(original_query, user_context=user_data.get(user_id, {}))
            bot.send_message(message.chat.id, response)
        except Exception as e:
            bot.send_message(message.chat.id, f"Sorry, I encountered an error: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """Main message handler with location logic"""
    user_id = message.from_user.id
    user_message = message.text
    # Check if user is asking for directions
    if needs_directions(user_message):
        if not has_valid_location(user_id):
            request_location(message)
            return
        else:
            print(f"Using saved location for user {user_id}")
    
    try:
        # Get user context (including location if available)
        context = user_data.get(user_id, {})
        response = ask_agent(user_message, user_context=context)
    
        bot.reply_to(message, response)
        print("[user data]", user_data)
        
    except Exception as e:
        bot.reply_to(message, f"Sorry, I encountered an error: {str(e)}")

def bot_startup():
    print("✅ Bot is successfully running and ready to receive messages!")
    print(f"Bot username: @{bot.get_me().username}")
    print("📍 Location features enabled!")
    print("Press Ctrl+C to stop the bot")

if __name__ == "__main__":
    print("🚀 Starting Telegram bot...")
    try:
        bot_info = bot.get_me()
        print(f"Connected as: @{bot_info.username}")
        bot_startup()
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ Error starting bot: {e}")



def pin_message(chat_id: int, message_id: int) -> str:
    """Pin a message in a chat"""
    try:
        bot.pin_chat_message(chat_id, message_id)
        if chat_id not in user_data:
            user_data[chat_id] = {}
        user_data[chat_id]['pinned_message_id'] = message_id
        return "✅ Your travel plan has been pinned!"
    except Exception as e:
        return f"Error pinning message: {str(e)}"

def unpin_message(message):
    """Unpin a message from the chat"""
    try:
        bot.unpin_chat_message(message.chat.id, message.message_id)
        if message.chat.id not in user_data:
            user_data[message.chat.id] = {}
        user_data[message.chat.id]['pinned_message_id'] = None
        return "✅ Your travel plan has been unpinned!"
    except Exception as e:
        return f"Error unpinning message: {str(e)}"

def update_pinned_message(message):
    """Update the pinned message with the travel plan from agent response"""