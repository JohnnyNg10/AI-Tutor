# AI Tutor Competition Setup Guide

## Quick Start for Judges

This project is **pre-configured** with API keys for immediate testing.

### Prerequisites

1. **Python 3.10-3.12** installed
2. **Redis** running (optional, mock mode available)

### Step 1: Install Dependencies

```bash
cd D:\Project\AI Tutor
install_deps.bat
```

Or manually:
```bash
cd backend
pip install -r requirements.txt
```

### Step 2: Start the Server

```bash
start_server.bat
```

Or manually:
```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Step 3: Access the API

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

---

## Pre-configured API Keys

All API keys are **embedded** in `backend/.env`:

| Service | Provider | Model | API Key |
|---------|----------|-------|---------|
| LLM | SiliconFlow | DeepSeek-V3 | `sk-ylhosgauteaxdymsjomzrdapgvpgdvvghjdmvpnlbnybekel` |
| Embedding | SiliconFlow | Qwen3-Embedding-8B | `sk-szbvplropwsbnneadzuvzoyhzojdhycsnpzncjcwzvjyssva` |
| Vision | SiliconFlow | Qwen2.5-VL-32B-Instruct | Uses LLM key |

**Note**: These keys are provided for competition evaluation only.

---

## Model Architecture

```
AI Tutor System
├── LLM: DeepSeek-V3 (SiliconFlow)
│   ├── Instructor Agent - Generate hints L0-L4
│   ├── Advisor Agent - Teaching mode selection
│   ├── Error Diagnosis - Distinguish calculation vs logic errors
│   └── Recommendation Reasons - Natural language explanations
│
├── Embedding: Qwen3-Embedding-8B (SiliconFlow)
│   └── RAG Retrieval - Question similarity search
│
└── Vision: Qwen2.5-VL-32B-Instruct (SiliconFlow)
    └── Image Parsing - Extract text from problem images
```

---

## Key Features Implemented

### V3 Core Features (44 Requirements)

1. **BKT Mastery Visualization** - Color-coded progress rings
2. **A/B Testing Framework** - V2 vs V3 algorithm comparison
3. **Six-Dimensional Ability Profile** - Radar chart of student traits
4. **Error Classification** - 8 error types with rehabilitation
5. **Pitfall & Achievement Cards** - Dual-column display
6. **Knowledge Tree Progress** - Node unlock rate tracking
7. **Learning Habit Badges** - 10 achievement types
8. **Daily Completion Summary** - 5-question celebration
9. **Interaction Logging** - Full behavior tracking
10. **Data Migration** - V2 to V3 compatibility
11. **Optimistic Locking** - Concurrent update protection
12. **Log Partitioning** - 90-day auto archival
13. **Redis Caching** - Seen questions, review queue, mastery

---

## Testing the API

### Test 1: Health Check
```bash
curl http://localhost:8000/health
```

### Test 2: Generate Hint
```bash
curl -X POST http://localhost:8000/instructor/hint \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "question_id": "test_001",
    "question_content": "求等差数列 1, 3, 5, ... 的第10项",
    "knowledge_points": ["arith_seq"],
    "hint_level": 1
  }'
```

### Test 3: Get Recommendation
```bash
curl -X POST http://localhost:8000/recommendation/daily-pack \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "user_theta": 0.5
  }'
```

---

## Project Structure

```
AI Tutor/
├── backend/               # FastAPI backend
│   ├── api/              # API endpoints
│   ├── services/         # Business logic
│   ├── algorithms/       # BKT, IRT, RAG
│   ├── agents/           # Instructor, Advisor
│   └── .env              # Pre-configured API keys
├── docs/                 # Documentation
├── install_deps.bat      # Dependency installer
└── start_server.bat      # Server starter
```

---

## Troubleshooting

### Port 8000 in use
```bash
# Change port in backend/.env
PORT=8001
```

### Redis not available
The system works without Redis using mock implementations.

### SSL errors during pip install
```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

---

## Documentation

- `docs/API_CONFIGURATION.md` - API setup details
- `docs/MODEL_CONFIGURATION.md` - Model architecture
- `docs/V3_*_IMPLEMENTATION.md` - Feature implementation details

---

## Contact

For questions about this submission, please refer to the implementation documents in `docs/` directory.
