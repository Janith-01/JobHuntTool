---
description: How to run the JobHuntTool project (backend + frontend)
---

## Running JobHuntTool

### Prerequisites
- Python 3.12+ with virtual environment
- Node.js 18+
- MongoDB running locally on port 27017

### Steps

1. Activate the Python virtual environment
// turbo
```bash
.\venv\Scripts\activate
```

2. Start MongoDB (if not already running)
```bash
# If using Docker:
docker run -d -p 27017:27017 --name mongo mongo:7
# Or start your local MongoDB service
```

3. Initialize the project (first time only)
```bash
python -m backend init
```

// turbo
4. Start the backend API server
```bash
python -m backend server --reload
```

// turbo
5. Start the frontend dev server (in a new terminal)
```bash
cd frontend && npm run dev
```

6. Open the dashboard at http://localhost:5173

### Running Scrapers via CLI

// turbo
7. Run all scrapers
```bash
python -m backend scrape --query "Software Intern" --location "Sri Lanka"
```

// turbo
8. Run a specific platform
```bash
python -m backend scrape --platform linkedin --max-results 20
```

// turbo
9. Show database statistics
```bash
python -m backend stats
```
