import logging
import os
import requests
import json
import time
import datetime
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from colorama import init, Fore, Style
from pymongo import MongoClient

init(autoreset=True)

# Bot Configuration
BOT_TOKEN = "8572563199:AAECn-YoQaozn83-tSvA7Mhdr5evzR9vcpI"
ADMIN_IDS = [8260945171]  # Your Telegram ID yahan dalo
DAILY_CREDITS = 10
SEARCH_COST = 1
MONGO_URI = "mongodb+srv://Kumarshivayy:shisak67@mesco.tslgi.mongodb.net/"

# Database setup
client = MongoClient(MONGO_URI)
db = client.get_database("mesco")
users_collection = db.get_collection("users")
admin_logs_collection = db.get_collection("admin_logs")

def init_db():
    """Initializes the database collections."""
    # MongoDB collections are created on first use, so we just need to ensure indexes
    users_collection.create_index("user_id", unique=True)
    admin_logs_collection.create_index("admin_id")


# API URLs
MOBILE_API_URL = "https://demon.taitanx.workers.dev/?mobile="
AADHAAR_API_URL = "https://addartofamily.vercel.app/fetch?aadhaar={id}&key=fxtF"

# User sessions
user_sessions = {}
admin_sessions = {}

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Credit Management Functions
def get_user_credits(user_id):
    user = users_collection.find_one({"user_id": user_id})
    
    if not user:
        # New user - add to database
        today = datetime.now().date().isoformat()
        new_user = {
            "user_id": user_id,
            "credits": DAILY_CREDITS,
            "last_reset": today,
            "join_date": today
        }
        users_collection.insert_one(new_user)
        return DAILY_CREDITS
    
    today = datetime.now().date()
    last_reset_date = datetime.fromisoformat(user["last_reset"]).date()
    
    # Reset credits if it's a new day
    if today > last_reset_date:
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"credits": DAILY_CREDITS, "last_reset": today.isoformat()}}
        )
        return DAILY_CREDITS
    
    return user["credits"]

def update_user_credits(user_id, new_credits):
    users_collection.update_one({"user_id": user_id}, {"$set": {"credits": new_credits}})

def is_admin(user_id):
    return user_id in ADMIN_IDS

def log_admin_action(admin_id, action, target_user=None):
    admin_logs_collection.insert_one({
        "admin_id": admin_id,
        "action": action,
        "target_user": target_user,
        "timestamp": datetime.now()
    })

def get_user_info_from_db(user_id):
    return users_collection.find_one({"user_id": user_id})

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send khatarnak welcome message"""
    user = update.effective_user
    user_id = user.id
    
    # Get user credits
    credits = get_user_credits(user_id)
    
    welcome_text = f"""
+----------------------------------------------+
¦ ?? WELCOME TO — ICONIC INFORMATION BOT ?? ¦
¦----------------------------------------------¦
¦ ?? THIS BOT MADE BY @SHOPILOVER                ¦
¦ ?? Developer ? @shopilover                    ¦
¦ ?? Hello {user.first_name}!                      ¦
+----------------------------------------------+

?? HOW TO USE:
+- 1. Choose search type (Mobile/Aadhaar)
+- 2. Enter number
+- 3. Get complete information
+- 4. Only {SEARCH_COST} credit per search!

?? CREDIT SYSTEM:
+- ?? Daily Free: {DAILY_CREDITS} credits
+- ?? Cost per lookup: {SEARCH_COST} credit 
+- ?? Auto reset: Every 24 hours
+- ? Your Credits: *{credits}*

?? YOUR ACCOUNT:
+- ?? User: {user.first_name}
+- ?? Credits: {credits}
+- ?? Status: ACTIVE
+- ?? Resets: Daily at 00:00

? CHOOSE SEARCH TYPE BELOW!
    """
    
    keyboard = [
        [InlineKeyboardButton("?? MOBILE SEARCH", callback_data="mobile_search"),
         InlineKeyboardButton("?? AADHAAR SEARCH", callback_data="aadhaar_search")],
        [InlineKeyboardButton("?? CHECK CREDITS", callback_data="check_credits"),
         InlineKeyboardButton("?? HELP", callback_data="help")],
        [InlineKeyboardButton("?? ADMIN PANEL", callback_data="admin_panel")] if is_admin(user_id) else []
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel for credit management"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.answer("? Access Denied! Admin only.", show_alert=True)
        return
    
    await query.answer()
    
    admin_text = """
+------------------------------+
¦         ?? ADMIN PANEL       ¦
¦------------------------------¦
¦ ICONIC CONTROL CENTER    ¦
+------------------------------+

Available Commands:
• /stats - Bot statistics
• /broadcast - Send message to all users
• /addcredits <user_id> <amount>
• /removecredits <user_id> <amount>
• /resetcredits <user_id>

Quick Actions:
    """
    
    keyboard = [
        [InlineKeyboardButton("?? BOT STATS", callback_data="admin_stats")],
        [InlineKeyboardButton("?? ADD CREDITS", callback_data="admin_add"),
         InlineKeyboardButton("? REMOVE CREDITS", callback_data="admin_remove")],
        [InlineKeyboardButton("?? RESET CREDITS", callback_data="admin_reset"),
         InlineKeyboardButton("?? GET USER INFO", callback_data="admin_getuserinfo")],
        [InlineKeyboardButton("?? BROADCAST", callback_data="admin_broadcast")],
        [InlineKeyboardButton("?? BACK TO MAIN", callback_data="start_search")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(admin_text, reply_markup=reply_markup)

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin statistics"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.answer("? Access Denied! Admin only.", show_alert=True)
        return
    
    await query.answer()
    
    # Total users
    total_users = users_collection.count_documents({})
    
    # Total credits
    pipeline = [
        {"$group": {"_id": None, "total_credits": {"$sum": "$credits"}}}
    ]
    result = list(users_collection.aggregate(pipeline))
    total_credits = result[0]["total_credits"] if result else 0
    
    # Today's new users
    today_iso = datetime.now().date().isoformat()
    today_users = users_collection.count_documents({"join_date": today_iso})
    
    # Active users (used bot in last 7 days)
    week_ago_iso = (datetime.now().date() - timedelta(days=7)).isoformat()
    active_users = users_collection.count_documents({"last_reset": {"$gte": week_ago_iso}})
    
    stats_text = f"""
+--------------------------+
¦       ?? BOT STATS       ¦
¦--------------------------¦
¦ ICONICBOT STATS     ¦
¦                          ¦
¦ ?? Total Users: {total_users}
¦ ?? Today's New: {today_users}
¦ ?? Active Users: {active_users}
¦ ?? Total Credits: {total_credits}
¦ ?? Daily Credits: {DAILY_CREDITS}
¦ ?? Search Cost: {SEARCH_COST}
¦ ?? Admin Users: {len(ADMIN_IDS)}
¦ ? Server Time: {datetime.now().strftime('%H:%M')}
+--------------------------+
    """
    
    keyboard = [
        [InlineKeyboardButton("?? REFRESH", callback_data="admin_stats")],
        [InlineKeyboardButton("?? BACK TO ADMIN", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(stats_text, reply_markup=reply_markup)

async def admin_add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add credits to user"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.answer("? Access Denied! Admin only.", show_alert=True)
        return
    
    await query.answer()
    
    admin_sessions[user_id] = {"action": "add_credits", "step": "waiting_user_id"}
    
    add_text = """
+--------------------------+
¦       ?? ADD CREDITS     ¦
¦--------------------------¦
¦ Add credits to user      ¦
¦                          ¦
¦ Please enter:            ¦
¦ UserID Amount            ¦
¦                          ¦
¦ Example:                 ¦
¦ 123456789 50             ¦
¦                          ¦
¦ ?? /cancel to go back    ¦
+--------------------------+
    """
    
    keyboard = [[InlineKeyboardButton("?? BACK", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(add_text, reply_markup=reply_markup)

async def admin_remove_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove credits from user"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.answer("? Access Denied! Admin only.", show_alert=True)
        return
    
    await query.answer()
    
    admin_sessions[user_id] = {"action": "remove_credits", "step": "waiting_user_id"}
    
    remove_text = """
+--------------------------+
¦      ? REMOVE CREDITS   ¦
¦--------------------------¦
¦ Remove credits from user ¦
¦                          ¦
¦ Please enter:            ¦
¦ UserID Amount            ¦
¦                          ¦
¦ Example:                 ¦
¦ 123456789 25             ¦
¦                          ¦
¦ ?? /cancel to go back    ¦
+--------------------------+
    """
    
    keyboard = [[InlineKeyboardButton("?? BACK", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(remove_text, reply_markup=reply_markup)

async def admin_reset_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset user credits"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.answer("? Access Denied! Admin only.", show_alert=True)
        return
    
    await query.answer()
    
    admin_sessions[user_id] = {"action": "reset_credits", "step": "waiting_user_id"}
    
    reset_text = f"""
+--------------------------+
¦      ?? RESET CREDITS    ¦
¦--------------------------¦
¦ Reset user credits       ¦
¦                          ¦
¦ Please enter UserID:     ¦
¦                          ¦
¦ Example:                 ¦
¦ 123456789                ¦
¦                          ¦
¦ This will set credits to ¦
¦ daily default: {DAILY_CREDITS}       ¦
¦                          ¦
¦ ?? /cancel to go back    ¦
+--------------------------+
    """
    
    keyboard = [[InlineKeyboardButton("?? BACK", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(reset_text, reply_markup=reply_markup)

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all users"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.answer("? Access Denied! Admin only.", show_alert=True)
        return
    
    await query.answer()
    
    admin_sessions[user_id] = {"action": "broadcast", "step": "waiting_message"}
    
    broadcast_text = """
+--------------------------+
¦       ?? BROADCAST       ¦
¦--------------------------¦
¦ Send message to all users¦
¦                          ¦
¦ Please enter your        ¦
¦ broadcast message:       ¦
¦                          ¦
¦ ?? /cancel to go back    ¦
+--------------------------+
    """
    
    keyboard = [[InlineKeyboardButton("?? BACK", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(broadcast_text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer()
    
    if query.data == "start_search":
        credits = get_user_credits(user_id)
        keyboard = [
            [InlineKeyboardButton("?? MOBILE SEARCH", callback_data="mobile_search"),
             InlineKeyboardButton("?? AADHAAR SEARCH", callback_data="aadhaar_search")],
            [InlineKeyboardButton("?? CHECK CREDITS", callback_data="check_credits"),
             InlineKeyboardButton("?? HELP", callback_data="help")],
            [InlineKeyboardButton("?? ADMIN PANEL", callback_data="admin_panel")] if is_admin(user_id) else []
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        main_text = f"""
+--------------------------+
¦     ?? MAIN MENU         ¦
¦--------------------------¦
¦ Ready for action!        ¦
¦                          ¦
¦ ?? Credits: {credits}       ¦
¦ ? Status: ACTIVE         ¦
+--------------------------+

Choose search type:
        """
        await query.edit_message_text(main_text, reply_markup=reply_markup)
    
    elif query.data == "mobile_search":
        credits = get_user_credits(user_id)
        if credits < SEARCH_COST:
            await query.answer(f"? Insufficient credits! You need {SEARCH_COST} credit.", show_alert=True)
            return
        
        user_sessions[user_id] = {"type": "mobile", "step": "waiting_number"}
        await query.edit_message_text(
            "?? MOBILE NUMBER SEARCH\n\n"
            "? Please enter the 10-digit mobile number:\n\n"
            f"?? This will cost {SEARCH_COST} credit\n"
            f"?? Your balance: {credits} credits\n\n"
            "?? Example: 9876543210"
        )
    
    elif query.data == "aadhaar_search":
        credits = get_user_credits(user_id)
        if credits < SEARCH_COST:
            await query.answer(f"? Insufficient credits! You need {SEARCH_COST} credit.", show_alert=True)
            return
        
        user_sessions[user_id] = {"type": "aadhaar", "step": "waiting_number"}
        await query.edit_message_text(
            "?? AADHAAR NUMBER SEARCH\n\n"
            "? Please enter the 12-digit Aadhaar number:\n\n"
            f"?? This will cost {SEARCH_COST} credit\n"
            f"?? Your balance: {credits} credits\n\n"
            "?? Example: 123456789012"
        )
    
    elif query.data == "check_credits":
        credits = get_user_credits(user_id)
        credit_text = f"""
+--------------------------+
¦       ?? CREDITS         ¦
¦--------------------------¦
¦ Your Credit Status       ¦
¦                          ¦
¦ ?? User: {query.from_user.first_name}
¦ ?? Available: {credits}      
¦ ?? Cost/Search: {SEARCH_COST}
¦ ?? Daily Free: {DAILY_CREDITS}
¦ ?? Resets: Daily
+--------------------------+
        """
        keyboard = [[InlineKeyboardButton("?? BACK", callback_data="start_search")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(credit_text, reply_markup=reply_markup)
    
    elif query.data == "help":
        help_text = f"""
+--------------------------+
¦        ?? HELP           ¦
¦--------------------------¦
¦ HOW TO USE THE BOT       ¦
¦                          ¦
¦ ?? MOBILE SEARCH:        ¦
¦ • 10-digit number        ¦
¦ • Get name, address etc. ¦
¦                          ¦
¦ ?? AADHAAR SEARCH:       ¦
¦ • 12-digit number        ¦
¦ • Get family details     ¦
¦                          ¦
¦ CREDIT SYSTEM:           ¦
¦ • {DAILY_CREDITS} free credits daily
¦ • {SEARCH_COST} credit per search
¦ • Auto-reset at midnight
¦                          ¦
¦ SUPPORT: @shopilover      ¦
+--------------------------+
        """
        keyboard = [[InlineKeyboardButton("?? BACK", callback_data="start_search")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(help_text, reply_markup=reply_markup)
    
    elif query.data == "admin_panel":
        await admin_panel(update, context)
    
    elif query.data == "admin_stats":
        await admin_stats(update, context)
    
    elif query.data == "admin_add":
        await admin_add_credits(update, context)
    
    elif query.data == "admin_remove":
        await admin_remove_credits(update, context)
    
    elif query.data == "admin_reset":
        await admin_reset_credits(update, context)
    
    elif query.data == "admin_broadcast":
        await admin_broadcast(update, context)

# API Functions (same as before)
def _call_mobile_api(number):
    try:
        resp = requests.get(MOBILE_API_URL + str(number), timeout=12)
        if resp.status_code != 200:
            return {"done": False, "error": f"Mobile API Status Code {resp.status_code}"}
        
        raw = resp.text.strip()
        start = raw.find('{')
        end = raw.rfind('}')
        
        if start == -1 or end == -1:
            return {"done": False, "error": "Mobile API Invalid response format"}
        
        clean = raw[start:end+1]
        try:
            j = json.loads(clean)
        except json.JSONDecodeError as e:
            return {"done": False, "error": f"Mobile API JSON decode error: {str(e)}"}
        
        results = []
        if isinstance(j, dict):
            if j.get("data"):
                if isinstance(j["data"], list):
                    for item in j["data"]:
                        if isinstance(item, dict):
                            results.append(item)
                elif isinstance(j["data"], dict):
                    results.append(j["data"])
            else:
                for key, value in j.items():
                    if isinstance(value, dict):
                        results.append(value)
        
        return {"done": True, "results": results, "used_api": "mobile"}
    
    except requests.exceptions.RequestException as e:
        return {"done": False, "error": f"Mobile API request error: {str(e)}"}
    except Exception as e:
        return {"done": False, "error": f"Mobile API error: {str(e)}"}

def _call_aadhaar_api(aadhaar):
    try:
        resp = requests.get(AADHAAR_API_URL.format(id=aadhaar), timeout=15)
        if resp.status_code != 200:
            return {"done": False, "error": f"Aadhaar API Status Code {resp.status_code}"}
        
        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            return {"done": False, "error": f"Aadhaar API JSON decode error: {str(e)}"}
        
        members = []
        if data.get("memberDetailsList"):
            for m in data["memberDetailsList"]:
                members.append({
                    "name": m.get("memberName", ""),
                    "relationship": m.get("releationship_name", ""),
                    "uid": m.get("uid", ""),
                    "memberId": m.get("memberId", ""),
                    "address": m.get("address", ""),
                    "schemeName": m.get("schemeName", "")
                })
        
        return {"done": True, "results": members, "used_api": "aadhaar"}
    
    except requests.exceptions.RequestException as e:
        return {"done": False, "error": f"Aadhaar API request error: {str(e)}"}
    except Exception as e:
        return {"done": False, "error": f"Aadhaar API error: {str(e)}"}

async def handle_admin_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin session messages"""
    user_id = update.effective_user.id
    message = update.message.text.strip()
    
    if not is_admin(user_id):
        await update.message.reply_text("? Admin access required!")
        return
    
    if user_id not in admin_sessions:
        await handle_admin_commands(update, context)
        return
    
    session = admin_sessions[user_id]
    
    if message == '/cancel':
        del admin_sessions[user_id]
        await update.message.reply_text("? Operation cancelled.")
        return
    
    if session["action"] == "add_credits":
        try:
            parts = message.split()
            if len(parts) != 2:
                await update.message.reply_text("? Please enter: UserID Amount\nExample: 123456789 50")
                return
            
            target_user = int(parts[0])
            amount = int(parts[1])
            
            current_credits = get_user_credits(target_user)
            new_credits = current_credits + amount
            update_user_credits(target_user, new_credits)
            
            log_admin_action(user_id, f"add_{amount}_credits", target_user)
            
            await update.message.reply_text(
                f"? Credits Added Successfully!\n\n"
                f"?? Target User: {target_user}\n"
                f"?? Credits Added: {amount}\n"
                f"?? Previous Balance: {current_credits}\n"
                f"?? New Balance: {new_credits}"
            )
            
            del admin_sessions[user_id]
            
        except ValueError:
            await update.message.reply_text("? Invalid format! Use: UserID Amount\nExample: 123456789 50")
        except Exception as e:
            await update.message.reply_text(f"? Error: {str(e)}")
    
    elif session["action"] == "remove_credits":
        try:
            parts = message.split()
            if len(parts) != 2:
                await update.message.reply_text("? Please enter: UserID Amount\nExample: 123456789 25")
                return
            
            target_user = int(parts[0])
            amount = int(parts[1])
            
            current_credits = get_user_credits(target_user)
            new_credits = max(0, current_credits - amount)
            update_user_credits(target_user, new_credits)
            
            log_admin_action(user_id, f"remove_{amount}_credits", target_user)
            
            await update.message.reply_text(
                f"? Credits Removed Successfully!\n\n"
                f"?? Target User: {target_user}\n"
                f"?? Credits Removed: {amount}\n"
                f"?? Previous Balance: {current_credits}\n"
                f"?? New Balance: {new_credits}"
            )
            
            del admin_sessions[user_id]
            
        except ValueError:
            await update.message.reply_text("? Invalid format! Use: UserID Amount\nExample: 123456789 25")
        except Exception as e:
            await update.message.reply_text(f"? Error: {str(e)}")
    
    elif session["action"] == "reset_credits":
        try:
            target_user = int(message)
            
            current_credits = get_user_credits(target_user)
            update_user_credits(target_user, DAILY_CREDITS)
            
            log_admin_action(user_id, "reset_credits", target_user)
            
            await update.message.reply_text(
                f"? Credits Reset Successfully!\n\n"
                f"?? Target User: {target_user}\n"
                f"?? Previous Balance: {current_credits}\n"
                f"?? Reset to: {DAILY_CREDITS} credits"
            )
            
            del admin_sessions[user_id]
            
        except ValueError:
            await update.message.reply_text("? Please enter a valid User ID")
        except Exception as e:
            await update.message.reply_text(f"? Error: {str(e)}")
    
    elif session["action"] == "broadcast":
        broadcast_message = message
        
        # Confirm broadcast
        confirm_text = f"""
?? BROADCAST CONFIRMATION

Message:
{broadcast_message}

This will be sent to all users.
Are you sure?

? /confirm_broadcast
? /cancel
        """
        
        admin_sessions[user_id] = {"action": "confirm_broadcast", "message": broadcast_message}
        await update.message.reply_text(confirm_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages"""
    user_id = update.effective_user.id
    user_message = update.message.text.strip()
    
    # Check if user has an active admin session
    if is_admin(user_id) and user_id in admin_sessions:
        await handle_admin_messages(update, context)
        return
    
    # Check if user has an active search session
    if user_id not in user_sessions:
        # Check for admin commands
        if user_message.startswith('/'):
            await handle_admin_commands(update, context)
            return
        
        await update.message.reply_text(
            "? Please use buttons to interact with the bot!\nUse /start to begin."
        )
        return
    
    session = user_sessions[user_id]
    
    if session["step"] == "waiting_number":
        # Check credits first
        credits = get_user_credits(user_id)
        if credits < SEARCH_COST:
            await update.message.reply_text(
                f"? INSUFFICIENT CREDITS!\n\n"
                f"You need {SEARCH_COST} credit but have only {credits}.\n"
                f"Wait for daily reset or contact admin."
            )
            del user_sessions[user_id]
            return
        
        # Validate input based on search type
        if session["type"] == "mobile":
            if not user_message.isdigit() or len(user_message) != 10:
                await update.message.reply_text("? Please enter a valid 10-digit mobile number.")
                return
            search_type = "Mobile"
            api_function = _call_mobile_api
            
        elif session["type"] == "aadhaar":
            if not user_message.isdigit() or len(user_message) != 12:
                await update.message.reply_text("? Please enter a valid 12-digit Aadhaar number.")
                return
            search_type = "Aadhaar"
            api_function = _call_aadhaar_api
        
        # Show processing message
        processing_text = f"""
?? PROCESSING YOUR REQUEST...

+--------------------------+
¦     ?? SEARCHING...      ¦
¦--------------------------¦
¦ Type: {search_type} Search
¦ Scanning databases...    ¦
¦ Checking records...      ¦
¦ Gathering information... ¦
¦ Decrypting data...       ¦
+--------------------------+

Please wait... This may take a few seconds.
        """
        processing_msg = await update.message.reply_text(processing_text)
        
        # Perform search
        result = api_function(user_message)
        
        # Deduct credit
        new_credits = credits - SEARCH_COST
        update_user_credits(user_id, new_credits)
        
        # Clear session
        del user_sessions[user_id]
        
        # Send results
        await send_results(update, context, result, processing_msg, new_credits, session["type"])

async def send_results(update: Update, context: ContextTypes.DEFAULT_TYPE, result, processing_msg, new_credits, search_type):
    """Send search results to user"""
    if not result.get("done"):
        error_text = f"""
? SEARCH FAILED!

Error: {result.get('error', 'Unknown error')}

?? Credits left: {new_credits}
?? Try again with different number
        """
        await processing_msg.edit_text(error_text)
        return
    
    data = result.get("results", [])
    used_api = result.get("used_api", "")
    
    if not data:
        no_data_text = f"""
? NO DATA FOUND!

The {'mobile' if search_type == 'mobile' else 'Aadhaar'} number you searched is not in our database.

?? Credits left: {new_credits}
?? Try with different number
        """
        await processing_msg.edit_text(no_data_text)
        return
    
    # Send success message
    success_text = f"""
? SEARCH COMPLETE!

?? Results Found: {len(data)} matches
?? Source: {used_api}
?? Credits Used: {SEARCH_COST}
?? Balance: {new_credits} credits

Fetching details...
    """
    await processing_msg.edit_text(success_text)
    
    # Send each result as separate message
    for idx, entry in enumerate(data, 1):
        if search_type == "mobile":
            result_text = f"""
+--------------------------+
¦     ?? RESULT {idx}         ¦
¦--------------------------¦
"""
            
            # Mobile result fields
            fields_displayed = 0
            if entry.get('name'): 
                result_text += f"?? Name: {entry.get('name')}\n"
                fields_displayed += 1
            if entry.get('fname'): 
                result_text += f"????? Father: {entry.get('fname')}\n"
                fields_displayed += 1
            if entry.get('mobile'): 
                result_text += f"?? Mobile: {entry.get('mobile')}\n"
                fields_displayed += 1
            if entry.get('alt'): 
                result_text += f"?? Alt Mobile: {entry.get('alt')}\n"
                fields_displayed += 1
            if entry.get('id'): 
                result_text += f"?? ID: {entry.get('id')}\n"
                fields_displayed += 1
            if entry.get('circle'): 
                result_text += f"?? Circle: {entry.get('circle')}\n"
                fields_displayed += 1
            if entry.get('address'): 
                address = entry.get('address')
                if len(address) > 200:
                    address = address[:200] + "..."
                result_text += f"?? Address: {address}\n"
                fields_displayed += 1
            if entry.get('operator'): 
                result_text += f"?? Operator: {entry.get('operator')}\n"
                fields_displayed += 1
            
            if fields_displayed == 0:
                result_text += "?? No detailed information available\n"
            
            result_text += "+--------------------------+"
            
        else:  # Aadhaar search
            result_text = f"""
+--------------------------+
¦     ??????????? FAMILY MEMBER {idx}  ¦
¦--------------------------¦
"""
            
            # Aadhaar result fields
            fields_displayed = 0
            if entry.get('name'): 
                result_text += f"?? Name: {entry.get('name')}\n"
                fields_displayed += 1
            if entry.get('relationship'): 
                result_text += f"?? Relationship: {entry.get('relationship')}\n"
                fields_displayed += 1
            if entry.get('uid'): 
                result_text += f"?? UID: {entry.get('uid')}\n"
                fields_displayed += 1
            if entry.get('memberId'): 
                result_text += f"?? Member ID: {entry.get('memberId')}\n"
                fields_displayed += 1
            if entry.get('schemeName'): 
                result_text += f"?? Scheme: {entry.get('schemeName')}\n"
                fields_displayed += 1
            if entry.get('address'): 
                address = entry.get('address')
                if len(address) > 150:
                    address = address[:150] + "..."
                result_text += f"?? Address: {address}\n"
                fields_displayed += 1
            
            if fields_displayed == 0:
                result_text += "?? No detailed information available\n"
            
            result_text += "+--------------------------+"
        
        await update.message.reply_text(result_text)
        time.sleep(0.5)  # Prevent rate limiting
    
    # Send final message with navigation
    keyboard = [
        [InlineKeyboardButton("?? NEW SEARCH", callback_data="start_search")],
        [InlineKeyboardButton("?? CHECK CREDITS", callback_data="check_credits")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"?? SEARCH COMPLETED!\n\n"
        f"?? Total results: {len(data)}\n"
        f"?? Credits used: {SEARCH_COST}\n"
        f"?? Balance: {new_credits} credits\n\n"
        f"? Ready for next search!",
        reply_markup=reply_markup
    )

async def handle_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin commands"""
    user_id = update.effective_user.id
    message = update.message.text
    
    if not is_admin(user_id):
        return
    
    if message.startswith('/stats'):
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT SUM(credits) FROM users")
        total_credits = c.fetchone()[0] or 0
        
        today = datetime.now().date()
        c.execute("SELECT COUNT(*) FROM users WHERE join_date = ?", (today,))
        today_users = c.fetchone()[0]
        
        conn.close()
        
        stats_text = f"""
?? BOT STATISTICS

?? Total Users: {total_users}
?? Today's New: {today_users}
?? Total Credits: {total_credits}
?? Daily Credits: {DAILY_CREDITS}
?? Search Cost: {SEARCH_COST}
        """
        await update.message.reply_text(stats_text)
    
    elif message.startswith('/addcredits'):
        try:
            parts = message.split()
            if len(parts) != 3:
                await update.message.reply_text("? Usage: /addcredits <user_id> <amount>")
                return
            
            target_user = int(parts[1])
            amount = int(parts[2])
            
            current_credits = get_user_credits(target_user)
            new_credits = current_credits + amount
            update_user_credits(target_user, new_credits)
            
            log_admin_action(user_id, f"add_{amount}_credits", target_user)
            
            await update.message.reply_text(
                f"? Credits Added!\n"
                f"?? User: {target_user}\n"
                f"?? Added: {amount}\n"
                f"?? New Balance: {new_credits}"
            )
            
        except ValueError:
            await update.message.reply_text("? Invalid user ID or amount!")
        except Exception as e:
            await update.message.reply_text(f"? Error: {str(e)}")
    
    elif message.startswith('/removecredits'):
        try:
            parts = message.split()
            if len(parts) != 3:
                await update.message.reply_text("? Usage: /removecredits <user_id> <amount>")
                return
            
            target_user = int(parts[1])
            amount = int(parts[2])
            
            current_credits = get_user_credits(target_user)
            new_credits = max(0, current_credits - amount)
            update_user_credits(target_user, new_credits)
            
            log_admin_action(user_id, f"remove_{amount}_credits", target_user)
            
            await update.message.reply_text(
                f"? Credits Removed!\n"
                f"?? User: {target_user}\n"
                f"?? Removed: {amount}\n"
                f"?? New Balance: {new_credits}"
            )
            
        except ValueError:
            await update.message.reply_text("? Invalid user ID or amount!")
        except Exception as e:
            await update.message.reply_text(f"? Error: {str(e)}")
    
    elif message.startswith('/resetcredits'):
        try:
            parts = message.split()
            if len(parts) != 2:
                await update.message.reply_text("? Usage: /resetcredits <user_id>")
                return
            
            target_user = int(parts[1])
            
            current_credits = get_user_credits(target_user)
            update_user_credits(target_user, DAILY_CREDITS)
            
            log_admin_action(user_id, "reset_credits", target_user)
            
            await update.message.reply_text(
                f"? Credits Reset!\n"
                f"?? User: {target_user}\n"
                f"?? Previous: {current_credits}\n"
                f"?? Reset to: {DAILY_CREDITS}"
            )
            
        except ValueError:
            await update.message.reply_text("? Invalid user ID!")
        except Exception as e:
            await update.message.reply_text(f"? Error: {str(e)}")
    
    elif message.startswith('/broadcast'):
        broadcast_message = message.replace('/broadcast', '').strip()
        
        if not broadcast_message:
            await update.message.reply_text("? Usage: /broadcast <message>")
            return
        
        # Get all users
        users = users_collection.find({}, {"user_id": 1})
        
        sent = 0
        failed = 0
        
        await update.message.reply_text(f"?? Broadcasting to {users_collection.count_documents({})} users...")
        
        for user_doc in users:
            user_id = user_doc["user_id"]
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"?? BROADCAST MESSAGE\n\n{broadcast_message}\n\nFrom Admin"
                )
                sent += 1
                time.sleep(0.1)  # Rate limiting
            except Exception:
                failed += 1
        
        log_admin_action(user_id, f"broadcast_{sent}_users")
        
        await update.message.reply_text(
            f"?? BROADCAST COMPLETE\n\n"
            f"? Sent: {sent}\n"
            f"? Failed: {failed}\n"
            f"?? Total: {users_collection.count_documents({})}"
        )
    
    elif message.startswith('/confirm_broadcast'):
        if user_id in admin_sessions and admin_sessions[user_id]["action"] == "confirm_broadcast":
            broadcast_message = admin_sessions[user_id]["message"]
            
            # Get all users
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("SELECT user_id FROM users")
            users = c.fetchall()
            conn.close()
            
            sent = 0
            failed = 0
            
            await update.message.reply_text(f"?? Broadcasting to {len(users)} users...")
            
            for (user_id,) in users:
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"?? BROADCAST MESSAGE\n\n{broadcast_message}\n\nFrom Admin"
                    )
                    sent += 1
                    time.sleep(0.1)  # Rate limiting
                except Exception:
                    failed += 1
            
            log_admin_action(user_id, f"broadcast_{sent}_users")
            del admin_sessions[user_id]
            
            await update.message.reply_text(
                f"?? BROADCAST COMPLETE\n\n"
                f"? Sent: {sent}\n"
                f"? Failed: {failed}\n"
                f"?? Total: {len(users)}"
            )
    
    elif message.startswith('/getuserinfo'):
        try:
            parts = message.split()
            if len(parts) != 2:
                await update.message.reply_text("? Usage: /getuserinfo <user_id>")
                return
            
            target_user_id = int(parts[1])
            user_info = get_user_info_from_db(target_user_id)
            
            if user_info:
                user_id, credits, last_reset, join_date = user_info
                info_text = f"""
+--------------------------+
¦       ?? USER INFO       ¦
¦--------------------------¦
¦ User ID: {user_id}
¦ Credits: {credits}
¦ Last Reset: {last_reset}
¦ Join Date: {join_date}
+--------------------------+
                """
                await update.message.reply_text(info_text)
            else:
                await update.message.reply_text(f"? User with ID {target_user_id} not found.")
            
            log_admin_action(user_id, f"get_user_info_{target_user_id}", target_user_id)
            
        except ValueError:
            await update.message.reply_text("? Invalid user ID!")
        except Exception as e:
            await update.message.reply_text(f"? Error: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logging.error(f"Update {update} caused error {context.error}")

def main():
    """Start the bot"""
    init_db() # Initialize MongoDB collections
    print(f"{Fore.GREEN}?? Starting ICONIC Information Bot...{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}? Bot Token: {BOT_TOKEN[:15]}...{Style.RESET_ALL}")
    print(f"{Fore.CYAN}?? Admin IDs: {ADMIN_IDS}{Style.RESET_ALL}")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", handle_admin_commands))
    application.add_handler(CommandHandler("addcredits", handle_admin_commands))
    application.add_handler(CommandHandler("removecredits", handle_admin_commands))
    application.add_handler(CommandHandler("resetcredits", handle_admin_commands))
    application.add_handler(CommandHandler("broadcast", handle_admin_commands))
    application.add_handler(CommandHandler("confirm_broadcast", handle_admin_commands))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    print(f"{Fore.GREEN}? Bot is running...{Style.RESET_ALL}")
    print(f"{Fore.RED}?? Press Ctrl+C to stop{Style.RESET_ALL}")
    
    application.run_polling()

if __name__ == '__main__':
    main()
