# Google Calendar Integration

J.A.R.V.I.S. supports bidirectional integration with **Google Calendar**, enabling schedule awareness, meeting scheduling, conflict detection, and agenda summarization.

---

## 📅 Supported Features

- **Query Schedule**: *"What does my calendar look like for this Thursday afternoon?"*
- **Create Events**: *"Schedule a 45-minute sync with Sarah tomorrow at 2 PM and title it 'Q3 Roadmap Review'."*
- **Find Free Time Slots**: *"Find a 1-hour free block between 10 AM and 4 PM on Friday."*
- **Conflict Prevention**: Warns if a new task or meeting overlaps with existing commitments.

---

## ⚙️ Setup & Authentication

### 1. Google Cloud Console Configuration
1. Create a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the **Google Calendar API**.
3. Create OAuth 2.0 Client Credentials (Application type: *Web application* or *Desktop*).
4. Download `credentials.json` into `backend/credentials/`.

### 2. Required Scopes
- `https://www.googleapis.com/auth/calendar.readonly`
- `https://www.googleapis.com/auth/calendar.events`

---

## 🤖 Agent Tool Bindings

The agent uses dedicated LangChain tools:
- `get_calendar_events(start_time, end_time)`
- `create_calendar_event(summary, start_time, end_time, attendees)`
- `find_free_slots(date, duration_minutes)`
