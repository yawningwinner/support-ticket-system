# Support Ticket System

Tech Intern Assessment: A full-stack support ticket system with LLM-powered category and priority suggestions.

## Quick start

```bash
docker-compose up --build
```

- **Frontend:** http://localhost:3000  
- **Backend API:** http://localhost:8000/api/

Optional: set a Google (Gemini) API key for the classify feature (suggest category/priority from description). Create a `.env` file in the project root:

```
GOOGLE_API_KEY=your-google-api-key
```

Docker Compose loads `.env` automatically. Get a key at [Google AI Studio](https://aistudio.google.com/apikey).

## Stack

- **Backend:** Django 4.x + Django REST Framework + PostgreSQL  
- **Frontend:** React 18 + Vite  
- **LLM:** Google Gemini (gemini-2.0-flash) — configurable via `GOOGLE_API_KEY`  
- **Infrastructure:** Docker + Docker Compose  

## Design decisions

- **LLM:** Google Gemini was chosen for a simple API and free tier; the prompt is in `backend/tickets/llm_service.py` for review. If the API key is missing or the call fails, the app still works: the classify endpoint returns nulls and the user picks category/priority manually.
- **Stats:** Aggregations use the Django ORM (`Count`, `TruncDate`, `values().annotate()`) so all stats are computed in the database, not with Python loops.
- **Frontend:** Single-page app with a form (title, description, category, priority), ticket list with filters and search, and a stats panel. Description blur triggers the classify request; suggestions pre-fill dropdowns but can be overridden before submit.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/tickets/` | Create ticket (201 on success) |
| GET    | `/api/tickets/` | List tickets (newest first). Query params: `category`, `priority`, `status`, `search` |
| PATCH  | `/api/tickets/<id>/` | Update ticket (e.g. status, category, priority) |
| GET    | `/api/tickets/stats/` | Aggregated stats (total, open, avg/day, breakdowns) |
| POST   | `/api/tickets/classify/` | Body: `{"description": "..."}` → `{"suggested_category": "...", "suggested_priority": "..."}` |

## Requirements

- Docker and Docker Compose  
- (Optional) Google API key for auto-suggestions (in `.env` as `GOOGLE_API_KEY`)  

No other setup steps; migrations run on backend startup.
