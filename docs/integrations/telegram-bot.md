# Telegram Gateway & Background Reminders

J.A.R.V.I.S. features a full-featured **Telegram Gateway** that allows you to converse with your AI assistant, manage tasks, log expenses, and receive proactive reminders anywhere from your phone.

---

## 🚀 Setting Up the Telegram Bot

### 1. Create a Bot with BotFather
1. Open Telegram and search for `@BotFather`.
2. Send `/newbot` and follow the prompts to name your bot.
3. Copy the HTTP API token provided by BotFather.

### 2. Configure Environment Variables
In your `backend/.env` file:
```ini
TELEGRAM_BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
TELEGRAM_CHAT_ID="987654321" # Your Telegram user ID for whitelist security
```

### 3. How to Find Your Telegram User ID
Send `/start` or any message to `@userinfobot` on Telegram to view your unique numeric user ID.

---

## ⚡ Capabilities on Telegram

### Natural Language Commands
- *"Add a task: Prepare slides for tomorrow's standup"*
- *"Log $14.50 for lunch at Chipotle"*
- *"Remind me at 4:30 PM to submit project invoice"*
- *"What's my total dining expense this week?"*

### Proactive Background Reminders
The backend runs an asynchronous reminder worker that continuously checks the `tracker_items` reminders collection:
- When a reminder's target timestamp arrives, the worker dispatches a Telegram push notification directly to your verified chat.
- Marks the reminder as dispatched in PostgreSQL to prevent duplicate alerts.

---

## 🔒 Security & Chat Whitelisting

To prevent unauthorized users from interacting with your bot:
- All incoming updates verify `message.from_user.id == settings.TELEGRAM_CHAT_ID`.
- Unauthorized requests are silently ignored or replied with an access denied alert.
