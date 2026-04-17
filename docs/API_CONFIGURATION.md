# AI Tutor API Configuration Guide

This document describes all API keys and models supported by AI Tutor.

## Required APIs

### 1. LLM API (One of the following)

#### Option A: OpenAI (Recommended for international users)
```env
OPENAI_API_KEY=sk-your-openai-key
OPENAI_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-3.5-turbo
```

**Supported Models:**
- `gpt-3.5-turbo` (default, cost-effective)
- `gpt-4`
- `gpt-4-turbo`
- `gpt-4o`

#### Option B: SiliconFlow (硅基流动 - Recommended for China users)
```env
OPENAI_API_KEY=sk-your-siliconflow-key
OPENAI_API_BASE=https://api.siliconflow.cn/v1
LLM_MODEL=Qwen/Qwen2.5-72B-Instruct
VISION_MODEL=Qwen/Qwen2-VL-72B-Instruct
```

**Supported Models:**
- `Qwen/Qwen2.5-72B-Instruct` (default)
- `Qwen/Qwen2-VL-72B-Instruct` (vision)
- `deepseek-ai/DeepSeek-V2.5`
- `THUDM/glm-4-9b-chat`

**Website:** https://siliconflow.cn

#### Option C: DashScope (阿里通义千问)
```env
DASHSCOPE_API_KEY=sk-your-dashscope-key
DASHSCOPE_API_BASE=https://dashscope.aliyuncs.com/api/v1
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v3
```

**Supported Models:**
- `qwen-turbo`
- `qwen-plus`
- `qwen-max`
- `text-embedding-v3` (embedding)

**Website:** https://dashscope.aliyun.com

#### Option D: VolcEngine (字节跳动豆包)
```env
VOLC_ACCESS_KEY=your-access-key
VOLC_SECRET_KEY=your-secret-key
VOLC_REGION=cn-beijing
VOLC_ENDPOINT=ark.cn-beijing.volces.com
VOLC_MODEL=your-model-endpoint
```

**Website:** https://www.volcengine.com

### 2. Embedding API (Optional - has fallbacks)

#### Option A: Chaosuansuan (超算互联网 - Competition Model)
```env
CHAOSUAN_API_KEY=your-chaosuan-key
CHAOSUAN_API_BASE=https://api.scnet.cn/v1
CHAOSUAN_EMBEDDING_MODEL=Qwen3-Embedding-8B
```

**Note:** This is the competition-specified embedding model.

#### Option B: DashScope
```env
DASHSCOPE_API_KEY=sk-your-dashscope-key
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v3
```

## Complete .env Template

```env
# ===========================================
# AI Tutor Environment Configuration
# ===========================================

# App Settings
APP_NAME=AI Tutor
APP_VERSION=3.0.0
DEBUG=true
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8000

# Database (Choose one)
# SQLite (Development)
DATABASE_URL=sqlite+aiosqlite:///./ai_tutor.db

# MySQL (Production)
# DATABASE_URL=mysql+aiomysql://user:password@localhost/ai_tutor

# Redis
REDIS_URL=redis://localhost:6379/0

# ===========================================
# LLM Configuration (Choose ONE provider)
# ===========================================

# --- Option 1: OpenAI ---
# OPENAI_API_KEY=sk-your-openai-key
# OPENAI_API_BASE=https://api.openai.com/v1
# LLM_MODEL=gpt-3.5-turbo

# --- Option 2: SiliconFlow (Recommended for China) ---
OPENAI_API_KEY=sk-your-siliconflow-key
OPENAI_API_BASE=https://api.siliconflow.cn/v1
LLM_MODEL=Qwen/Qwen2.5-72B-Instruct
VISION_MODEL=Qwen/Qwen2-VL-72B-Instruct
TEMPERATURE=0.7
LLM_MAX_TOKENS=4096

# --- Option 3: DashScope ---
# DASHSCOPE_API_KEY=sk-your-dashscope-key
# DASHSCOPE_API_BASE=https://dashscope.aliyuncs.com/api/v1

# --- Option 4: VolcEngine ---
# VOLC_ACCESS_KEY=your-access-key
# VOLC_SECRET_KEY=your-secret-key
# VOLC_REGION=cn-beijing

# ===========================================
# Embedding Configuration (Optional)
# ===========================================

# Chaosuansuan (Competition Model)
CHAOSUAN_API_KEY=your-chaosuan-key
CHAOSUAN_API_BASE=https://api.scnet.cn/v1
CHAOSUAN_EMBEDDING_MODEL=Qwen3-Embedding-8B

# DashScope (Alternative)
# DASHSCOPE_EMBEDDING_MODEL=text-embedding-v3

# ===========================================
# CORS Settings
# ===========================================
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080","http://localhost:5173"]

# ===========================================
# File Paths
# ===========================================
LOG_DIR=logs
UPLOAD_DIR=uploads
CHROMA_PERSIST_DIR=chroma_db
KG_PERSIST_DIR=knowledge_graph

# ===========================================
# Security
# ===========================================
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

## API Provider Comparison

| Provider | Location | Speed | Cost | Recommendation |
|----------|----------|-------|------|----------------|
| OpenAI | International | Medium | High | International users |
| SiliconFlow | China | Fast | Low | China users |
| DashScope | China | Fast | Medium | Alibaba ecosystem |
| VolcEngine | China | Fast | Low | ByteDance ecosystem |

## Getting API Keys

### SiliconFlow (Recommended)
1. Visit: https://siliconflow.cn
2. Register an account
3. Go to "API Keys" section
4. Create a new API key
5. Copy the key starting with `sk-`

### OpenAI
1. Visit: https://platform.openai.com
2. Create an account
3. Go to "API Keys" section
4. Create a new secret key

### DashScope
1. Visit: https://dashscope.aliyun.com
2. Login with Alibaba Cloud account
3. Apply for API access
4. Create API key in console

## Testing API Connection

After configuring, test with:

```bash
cd backend
python -c "
from services.llm_service import LLMService
service = LLMService()
response = service.generate_hint('Solve 1+1', 1)
print(response.content)
"
```

## Troubleshooting

### SSL Certificate Errors
If you encounter SSL errors in China, try:
```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

### API Timeout
Increase timeout in `.env`:
```env
LLM_TIMEOUT=60
```

### Rate Limiting
Switch to a different provider or upgrade your plan.

## Fallback Behavior

If no API key is configured, the system will:
1. Use mock responses for development
2. Log warnings about missing configuration
3. Continue with limited functionality

For production deployment, at least one LLM provider must be configured.
