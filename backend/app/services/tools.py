import os
import json
from typing import Optional, Dict, Any, Union, List
from langchain_core.tools import tool

# Determine the absolute workspace directory
WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Directories and files blacklisted from inspection to protect secrets and ignore build noise
IGNORED_DIRS = {'.git', '.venv', 'venv', 'node_modules', '.next', '__pycache__', '.pytest_cache', '.idea', '.vscode'}
SENSITIVE_PATTERNS = {'.pem', '.key', '.p12', '.crt', 'id_rsa'}
SENSITIVE_FILENAMES = {'mcp_config.json'}

def is_sensitive_path(rel_path: str) -> bool:
    """
    Checks if a relative path matches sensitive credential files or hidden secret files.
    Allows .env.example while blocking actual .env files.
    """
    parts = os.path.normpath(rel_path).split(os.sep)
    for part in parts:
        part_lower = part.lower()
        if part_lower in IGNORED_DIRS:
            return True
        if part_lower.startswith(".env") and part_lower != ".env.example":
            return True
        if part_lower in SENSITIVE_FILENAMES:
            return True
        if any(part_lower.endswith(pat) for pat in SENSITIVE_PATTERNS):
            return True
    return False

@tool
def list_workspace_files() -> str:
    """
    Recursively list all relevant file paths in the workspace directory.
    Use this to see what files are in the repository and find the structure of the project.
    """
    try:
        files = []
        for root, dirs, filenames in os.walk(WORKSPACE_DIR):
            # Exclude standard generated and ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for filename in filenames:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, WORKSPACE_DIR)
                if is_sensitive_path(rel_path):
                    continue
                files.append(rel_path)
        
        if not files:
            return "No files found in workspace."
            
        # Return first 150 files to avoid overloading prompt length
        result = "\n".join(files[:150])
        if len(files) > 150:
            result += f"\n\n...and {len(files) - 150} more files."
        return result
    except Exception as e:
        return f"Error listing files: {str(e)}"

@tool
def read_workspace_file(file_path: str) -> str:
    """
    Read the contents of a specific text file within the workspace.
    
    Args:
        file_path (str): The relative path of the file to read, e.g., 'backend/app/main.py' or 'README.md'.
    """
    try:
        # Resolve path and sanitize to ensure it is within the workspace sandbox
        resolved_path = os.path.abspath(os.path.join(WORKSPACE_DIR, file_path))
        if not resolved_path.startswith(WORKSPACE_DIR):
            return "Error: Access Denied. Cannot read files outside the workspace."
            
        rel_path = os.path.relpath(resolved_path, WORKSPACE_DIR)
        if is_sensitive_path(rel_path):
            return "Error: Access Denied. Reading sensitive configuration, credentials, or secret files is strictly prohibited."
            
        if not os.path.exists(resolved_path):
            return f"Error: File not found at '{file_path}'."
            
        if os.path.isdir(resolved_path):
            return f"Error: '{file_path}' is a directory. Use list_workspace_files to list its contents."

        with open(resolved_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(6000) # Limit reading to 6k characters to manage token usage
            if len(content) == 6000:
                content += "\n\n...[content truncated (file too large)]"
            return content
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool
def search_workspace_content(query: str) -> str:
    """
    Search for a text string (case-insensitive) inside files in the workspace (grep search).
    
    Args:
        query (str): The search query to look for in the workspace files.
    """
    try:
        results = []
        for root, dirs, filenames in os.walk(WORKSPACE_DIR):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for filename in filenames:
                # Target text-based files primarily (excluding raw secrets and env files)
                if not any(filename.endswith(ext) for ext in ['.py', '.js', '.ts', '.tsx', '.json', '.md', '.css', '.html', '.yml', '.yaml', '.toml', '.example']):
                    continue
                    
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, WORKSPACE_DIR)
                if is_sensitive_path(rel_path):
                    continue
                
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if query.lower() in line.lower():
                                results.append(f"{rel_path}:{i}: {line.strip()}")
                                if len(results) >= 30: # Safeguard boundary
                                    break
                except Exception:
                    pass
                if len(results) >= 30:
                    break
        
        if not results:
            return f"No occurrences of '{query}' found in workspace."
        return "\n".join(results)
    except Exception as e:
        return f"Error searching: {str(e)}"

WMO_WEATHER_DESCRIPTIONS = {
    0: "Clear sky ☀️",
    1: "Mainly clear 🌤️",
    2: "Partly cloudy ⛅",
    3: "Overcast ☁️",
    45: "Fog 🌫️",
    48: "Depositing rime fog 🌫️",
    51: "Light drizzle 🌦️",
    53: "Moderate drizzle 🌦️",
    55: "Dense drizzle 🌧️",
    56: "Light freezing drizzle 🌧️",
    57: "Dense freezing drizzle 🌧️",
    61: "Slight rain 🌧️",
    63: "Moderate rain 🌧️",
    65: "Heavy rain 🌧️",
    66: "Light freezing rain 🌨️",
    67: "Heavy freezing rain 🌨️",
    71: "Slight snow fall ❄️",
    73: "Moderate snow fall ❄️",
    75: "Heavy snow fall ❄️",
    77: "Snow grains ❄️",
    80: "Slight rain showers 🌦️",
    81: "Moderate rain showers 🌦️",
    82: "Violent rain showers 🌧️",
    85: "Slight snow showers 🌨️",
    86: "Heavy snow showers 🌨️",
    95: "Thunderstorm ⛈️",
    96: "Thunderstorm with slight hail ⛈️",
    99: "Thunderstorm with heavy hail ⛈️",
}

@tool
async def get_weather(location: str) -> str:
    """
    Get the real-time weather conditions and multi-day forecast for any city or location using Open-Meteo.
    
    Args:
        location (str): The name of the city, region, or location (e.g., 'San Francisco', 'London', 'Tokyo', 'Paris').
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Geocoding: resolve location name to latitude & longitude
            geo_response = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": location.strip(), "count": 1, "language": "en", "format": "json"}
            )
            geo_response.raise_for_status()
            geo_data = geo_response.json()
            
            results = geo_data.get("results")
            if not results:
                return f"Could not find any location or coordinates matching '{location}'. Please verify the spelling or specify a nearby major city."
            
            top_match = results[0]
            lat = top_match["latitude"]
            lon = top_match["longitude"]
            city_name = top_match.get("name", location)
            country = top_match.get("country", "")
            admin1 = top_match.get("admin1", "")
            location_label = f"{city_name}"
            if admin1 and admin1 != city_name:
                location_label += f", {admin1}"
            if country:
                location_label += f", {country}"

            # 2. Weather & Forecast retrieval
            weather_response = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": [
                        "temperature_2m",
                        "relative_humidity_2m",
                        "apparent_temperature",
                        "precipitation",
                        "weather_code",
                        "wind_speed_10m"
                    ],
                    "daily": [
                        "weather_code",
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "precipitation_probability_max"
                    ],
                    "timezone": "auto",
                    "forecast_days": 4
                }
            )
            weather_response.raise_for_status()
            weather_data = weather_response.json()
            
            current = weather_data.get("current", {})
            daily = weather_data.get("daily", {})

            curr_temp_c = current.get("temperature_2m")
            curr_temp_f = round(curr_temp_c * 9 / 5 + 32, 1) if curr_temp_c is not None else None
            apparent_c = current.get("apparent_temperature")
            apparent_f = round(apparent_c * 9 / 5 + 32, 1) if apparent_c is not None else None
            humidity = current.get("relative_humidity_2m")
            wind_speed = current.get("wind_speed_10m")
            precip = current.get("precipitation", 0.0)
            code = current.get("weather_code", 0)
            condition = WMO_WEATHER_DESCRIPTIONS.get(code, f"Code {code}")

            lines = [
                f"🌤️ **Weather Report for {location_label}**",
                f"• 📋 **Condition:** {condition}",
                f"• 🌡️ **Temperature:** {curr_temp_c}°C ({curr_temp_f}°F)",
                f"• 🤔 **Feels Like:** {apparent_c}°C ({apparent_f}°F)",
                f"• 💧 **Relative Humidity:** {humidity}%",
                f"• 💨 **Wind Speed:** {wind_speed} km/h",
                f"• 🌧️ **Precipitation:** {precip} mm",
            ]

            # Append forecast
            dates = daily.get("time", [])
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            precip_probs = daily.get("precipitation_probability_max", [])
            codes = daily.get("weather_code", [])

            if dates and len(dates) > 1:
                lines.append("\n📅 **Upcoming Forecast:**")
                for i in range(len(dates)):
                    d_date = dates[i]
                    d_max_c = max_temps[i] if i < len(max_temps) else "N/A"
                    d_min_c = min_temps[i] if i < len(min_temps) else "N/A"
                    d_max_f = round(d_max_c * 9 / 5 + 32, 1) if isinstance(d_max_c, (int, float)) else "N/A"
                    d_min_f = round(d_min_c * 9 / 5 + 32, 1) if isinstance(d_min_c, (int, float)) else "N/A"
                    d_prob = precip_probs[i] if i < len(precip_probs) else 0
                    d_code = codes[i] if i < len(codes) else 0
                    d_cond = WMO_WEATHER_DESCRIPTIONS.get(d_code, "Varied")

                    lines.append(
                        f"- 🗓️ **{d_date}**: {d_cond} | 🌡️ High: {d_max_c}°C ({d_max_f}°F), Low: {d_min_c}°C ({d_min_f}°F) | ☔ Rain Chance: {d_prob}%"
                    )

            return "\n".join(lines)
    except httpx.ConnectError:
        return f"Network Error: Unable to connect to Open-Meteo weather service to fetch data for '{location}'."
    except httpx.TimeoutException:
        return f"Timeout Error: Open-Meteo weather service took too long to respond for '{location}'."
    except Exception as e:
        return f"Error fetching weather for '{location}': {str(e)}"

@tool
def web_search(query: str) -> str:
    """
    Search the web for information using Tavily Search API.
    Use this to look up current events, news, documentation, or code libraries that are not local.
    
    Args:
        query (str): The search query.
    """
    from app.core.config import settings
    import requests

    api_key = settings.TAVILY_API_KEY or os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY is not configured. Please add TAVILY_API_KEY to your .env file."

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": 5
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        
        if not results:
            return f"No search results found for query: '{query}'"
            
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(f"[{i}] {r.get('title')}\nURL: {r.get('url')}\nContent: {r.get('content')}\n")
        return "\n".join(formatted)
    except Exception as e:
        return f"Error performing Tavily search: {str(e)}"

@tool
def send_telegram_message(message: str) -> str:
    """
    Send a notification message to the user via Telegram.
    Use this tool whenever the user asks you to send a message, note, or alert to Telegram.
    
    Args:
        message (str): The content of the message to send.
    """
    from app.core.config import settings
    import requests

    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        return f"[SIMULATION MODE] Successfully simulated sending Telegram message: '{message}'"

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return f"Successfully sent Telegram message: '{message}'"
    except Exception as e:
        return f"Error sending Telegram message: {str(e)}"

@tool
async def save_record(
    collection: str,
    title: str,
    data: Optional[dict] = None,
    event_date: Optional[str] = None
) -> str:
    """
    Save or track any structured or semi-structured information in the database.
    Use this tool whenever the user wants to log, store, or remember items like:
    - Gas / Fuel fill-ups (e.g. collection='gas', title='Gas at Shell', data={'amount': 45.00, 'gallons': 12.5, 'price_per_gallon': 3.60, 'odometer': 54200, 'station': 'Shell', 'vehicle': 'Honda Civic'})
    - Expenses (e.g. collection='expense', title='Dinner with friends', data={'amount': 45.50, 'category': 'food', 'currency': 'USD'})
    - To-Do list items (e.g. collection='todo', title='Fix login bug', data={'priority': 'high', 'status': 'pending'})
    - Bookmarks / Reading list (e.g. collection='bookmark', title='LangGraph Guide', data={'url': 'https://...', 'tags': ['ai', 'langchain']})
    - Reminders (e.g. collection='reminder', title='Call doctor', event_date='2026-08-20T10:00:00-04:00', data={'status': 'scheduled'})
    - Notes, workout logs, habits, or any custom collection.

    Args:
        collection (str): The category/type name (e.g., 'gas', 'expense', 'todo', 'bookmark', 'reminder', 'note').
        title (str): Brief descriptive title or summary of the item.
        data (dict, optional): Key-value attributes (e.g., amount, gallons, price_per_gallon, odometer, station, category, tags, url, status).
        event_date (str, optional): ISO-8601 formatted datetime string with timezone offset (e.g. '2026-08-20T10:00:00-04:00' or UTC 'Z') or date (YYYY-MM-DD) for expenses, gas logs, due dates, or reminder times.
    """
    from app.services.tracker import create_or_update_record
    try:
        record = await create_or_update_record(
            collection=collection,
            title=title,
            data=data or {},
            event_date=event_date,
            user_id="default_user"
        )
        return (
            f"Successfully saved record to collection '{record['collection']}'.\n"
            f"ID: {record['id']}\n"
            f"Title: {record['title']}\n"
            f"Date: {record['event_date'] or 'N/A'}\n"
            f"Data: {json.dumps(record['data'])}"
        )
    except Exception as e:
        return f"Error saving record: {str(e)}"

@tool
async def query_records(
    collection: Optional[str] = None,
    filters: Optional[dict] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search_query: Optional[str] = None,
    limit: int = 20
) -> str:
    """
    Search and retrieve tracked items from the database with filtering and text search.
    Use this to look up previous gas fill-ups, expenses, active to-dos, saved links, or past reminders.

    Args:
        collection (str, optional): Filter by collection name (e.g., 'gas', 'expense', 'todo', 'bookmark').
        filters (dict, optional): Match JSON attributes, e.g. {'station': 'Shell'} or {'category': 'food'} or {'status': 'pending'}.
        date_from (str, optional): ISO date (YYYY-MM-DD) for start of time window.
        date_to (str, optional): ISO date (YYYY-MM-DD) for end of time window.
        search_query (str, optional): Keyword search matching title or data contents.
        limit (int, optional): Max records to retrieve (default 20).
    """
    from app.services.tracker import query_records as db_query_records
    try:
        records = await db_query_records(
            user_id="default_user",
            collection=collection,
            filters=filters,
            date_from=date_from,
            date_to=date_to,
            search_query=search_query,
            limit=limit
        )
        if not records:
            filter_desc = f"in collection '{collection}' " if collection else ""
            return f"No records found {filter_desc}matching your search criteria."
        
        output = [f"Found {len(records)} record(s):"]
        for r in records:
            output.append(
                f"- [{r['collection'].upper()}] ID: {r['id']} | Title: '{r['title']}' | "
                f"Date: {r['event_date'] or r['created_at'][:10]} | Data: {json.dumps(r['data'])}"
            )
        return "\n".join(output)
    except Exception as e:
        return f"Error querying records: {str(e)}"

@tool
async def aggregate_records(
    collection: str = "expense",
    calculation: str = "sum",
    field: Optional[str] = "amount",
    group_by: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    filters: Optional[dict] = None
) -> str:
    """
    Perform accurate SQL numeric calculations (sum, avg, count, min, max) and grouping on tracked data.
    ALWAYS use this tool when the user asks questions involving math, totals, spending, fuel gallons, or counts, such as:
    - "How much did I spend on gas this month?" -> collection='gas', calculation='sum', field='amount', date_from='...', date_to='...'
    - "How many gallons of gas did I buy?" -> collection='gas', calculation='sum', field='gallons'
    - "What is my average price per gallon?" -> collection='gas', calculation='avg', field='price_per_gallon'
    - "What is my spending breakdown by category?" -> collection='expense', calculation='sum', field='amount', group_by='category'
    - "How many pending to-dos do I have?" -> collection='todo', calculation='count', filters={'status': 'pending'}

    Args:
        collection (str): The collection name (default 'expense' or 'gas').
        calculation (str): One of 'sum', 'avg', 'count', 'min', 'max' (default 'sum').
        field (str, optional): The JSON numeric property to calculate on (e.g., 'amount', 'gallons', 'price_per_gallon', 'odometer').
        group_by (str, optional): Field to group results by (e.g., 'station', 'category', 'status').
        date_from (str, optional): ISO date (YYYY-MM-DD) for start of time window.
        date_to (str, optional): ISO date (YYYY-MM-DD) for end of time window.
        filters (dict, optional): Specific JSON key-value filters.
    """
    from app.services.tracker import aggregate_records as db_aggregate_records
    try:
        res = await db_aggregate_records(
            user_id="default_user",
            collection=collection,
            calculation=calculation,
            field=field,
            group_by=group_by,
            date_from=date_from,
            date_to=date_to,
            filters=filters
        )
        
        calc_name = res["calculation"].upper()
        field_str = f" of '{res['field']}'" if res.get("field") else ""
        result_text = f"Analytics Calculation Result ({calc_name}{field_str} on '{res['collection']}'):\n"
        result_text += f"- Total/Value: {res['result']}\n"
        result_text += f"- Matching Record Count: {res['record_count']}\n"
        
        if "breakdown" in res:
            result_text += f"- Breakdown by '{res.get('group_by')}':\n"
            for k, v in res["breakdown"].items():
                result_text += f"  * {k}: {v['value']} ({v['count']} records)\n"
                
        return result_text
    except Exception as e:
        return f"Error executing calculation: {str(e)}"

@tool
async def manage_record(
    record_id: str,
    action: str = "mark_completed",
    status: Optional[str] = None,
    updates: Optional[dict] = None
) -> str:
    """
    Update, complete, or delete an existing tracked record.
    
    Args:
        record_id (str): The UUID of the record to modify.
        action (str): One of 'mark_completed', 'update', 'delete'.
        status (str, optional): New status string (e.g., 'completed', 'cancelled', 'archived').
        updates (dict, optional): Key-value fields to merge into data (if action is 'update').
    """
    from app.services.tracker import update_record_status, delete_record
    try:
        action_clean = action.lower().strip()
        if action_clean == "delete":
            deleted = await delete_record(record_id=record_id, user_id="default_user")
            if deleted:
                return f"Successfully deleted record '{record_id}'."
            return f"Record '{record_id}' was not found or could not be deleted."
            
        new_status = status
        if action_clean == "mark_completed":
            new_status = "completed"
            
        updated = await update_record_status(
            record_id=record_id,
            user_id="default_user",
            status=new_status,
            updates=updates
        )
        if updated:
            return f"Successfully updated record '{record_id}'. New data: {json.dumps(updated['data'])}"
        return f"Record '{record_id}' not found."
    except Exception as e:
        return f"Error managing record: {str(e)}"

tools = [
    get_weather,
    web_search,
    send_telegram_message,
    save_record,
    query_records,
    aggregate_records,
    manage_record
]

TOOL_METADATA = {
    "get_weather": {
        "emoji": "🌤️",
        "name": "get_weather",
        "description": "Real-time weather conditions & 4-day forecast via Open-Meteo",
        "category": "Weather"
    },
    "web_search": {
        "emoji": "🔍",
        "name": "web_search",
        "description": "Live web search & research via Tavily Search API",
        "category": "Search"
    },
    "send_telegram_message": {
        "emoji": "📱",
        "name": "send_telegram_message",
        "description": "Telegram notifications dispatch (Requires Human-in-the-Loop approval)",
        "category": "Notifications"
    },
    "save_record": {
        "emoji": "💾",
        "name": "save_record",
        "description": "Universal tracker: save fuel logs, expenses, todos, reminders, bookmarks",
        "category": "Tracker"
    },
    "query_records": {
        "emoji": "🔎",
        "name": "query_records",
        "description": "Universal tracker: search & filter database records",
        "category": "Tracker"
    },
    "aggregate_records": {
        "emoji": "📊",
        "name": "aggregate_records",
        "description": "Universal tracker: deterministic SQL math & analytics (sum, avg, count)",
        "category": "Tracker"
    },
    "manage_record": {
        "emoji": "✏️",
        "name": "manage_record",
        "description": "Universal tracker: update status, mark completed, or delete records",
        "category": "Tracker"
    },
}


def log_builtin_tools(custom_logger=None):
    """
    Logs all built-in agent tools as they load with distinct emojis and descriptions.
    """
    import logging
    target_logger = custom_logger or logging.getLogger("tools")
    target_logger.info("🛠️  Loading built-in agent tools...")
    for t in tools:
        meta = TOOL_METADATA.get(t.name, {
            "emoji": "🔧",
            "name": t.name,
            "description": (t.description or "").split("\n")[0].strip(),
            "category": "General"
        })
        target_logger.info(f"  {meta['emoji']}  [Built-in] {t.name} - {meta['description']}")
    target_logger.info(f"✅ Loaded {len(tools)} built-in tool(s) successfully.")


