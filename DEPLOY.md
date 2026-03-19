# TASKFLOW — Full Stack Deployment Guide
## Stack: Python FastAPI + SQLite + Claude AI → Render (Backend) + Netlify (Frontend)

---

## PROJECT STRUCTURE

```
taskflow/
├── backend/
│   ├── main.py            ← FastAPI app + SQLite + Claude AI
│   ├── requirements.txt   ← Python dependencies
│   └── render.yaml        ← Render deployment config
└── frontend/
    └── index.html         ← Full UI connected to the API
```

---

## STEP 1 — Run Locally

### Backend
```bash
cd taskflow/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set your Anthropic API key (get one at console.anthropic.com)
export ANTHROPIC_API_KEY=sk-ant-xxxxxxxx   # Windows: set ANTHROPIC_API_KEY=sk-ant-xxxxxxxx

# Start the server
uvicorn main:app --reload --port 8000
```

Your API is now live at: http://localhost:8000
API docs at: http://localhost:8000/docs  ← interactive Swagger UI

### Frontend
Just open `frontend/index.html` in your browser.
The `API` variable in the script already points to `http://localhost:8000`.

---

## STEP 2 — Push to GitHub

```bash
cd taskflow
git init
git add .
git commit -m "Initial commit"

# Create a new repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/taskflow.git
git push -u origin main
```

---

## STEP 3 — Deploy Backend on Render (Free)

1. Go to https://render.com and sign up (free)
2. Click **New → Web Service**
3. Connect your GitHub repo
4. Fill in the settings:
   - **Name:** taskflow-api
   - **Root Directory:** backend
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Under **Environment Variables**, add:
   - Key: `ANTHROPIC_API_KEY`
   - Value: `sk-ant-your-key-here`
6. Click **Create Web Service**

Render will give you a URL like: `https://taskflow-api.onrender.com`

---

## STEP 4 — Update Frontend with Live API URL

Open `frontend/index.html` and change line:
```javascript
const API = "http://localhost:8000";
```
to:
```javascript
const API = "https://taskflow-api.onrender.com";
```

---

## STEP 5 — Deploy Frontend on Netlify (Free)

### Option A — Drag & Drop (easiest)
1. Go to https://netlify.com and sign up
2. Drag the `frontend/` folder onto the Netlify dashboard
3. Done! You get a URL like `https://taskflow-xyz.netlify.app`

### Option B — Via CLI
```bash
npm install -g netlify-cli
cd frontend
netlify deploy --prod --dir .
```

---

## API ENDPOINTS

| Method | Endpoint        | Description              |
|--------|-----------------|--------------------------|
| GET    | /               | Health check             |
| GET    | /tasks          | Get all tasks            |
| GET    | /tasks?filter=active | Get active tasks    |
| GET    | /tasks?filter=done   | Get completed tasks |
| GET    | /tasks?filter=high   | Get high priority   |
| POST   | /tasks          | Create a new task        |
| PATCH  | /tasks/{id}     | Update task (done/text)  |
| DELETE | /tasks/{id}     | Delete a task            |
| GET    | /stats          | Get completion stats     |

### POST /tasks body example:
```json
{
  "text": "Build the landing page",
  "priority": "high"
}
```

---

## NOTES

- SQLite database file (`taskflow.db`) is auto-created on first run
- On Render's free tier, the server sleeps after 15min of inactivity (wakes in ~30s)
- To persist data across Render deploys, upgrade to a paid plan or switch to PostgreSQL
- Never expose your ANTHROPIC_API_KEY in frontend code — always keep it server-side
