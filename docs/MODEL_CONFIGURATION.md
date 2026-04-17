# AI Tutor Model Configuration Guide

This document describes all AI models used in AI Tutor and their purposes.

## Model Architecture Overview

```
AI Tutor System
├── LLM Layer (Large Language Models)
│   ├── Instructor Agent - Teaching & Hints
│   ├── Advisor Agent - Strategy & Control
│   └── Reason Generation - Recommendation explanations
├── Embedding Layer (Vector Models)
│   ├── Question Retrieval - RAG candidate pool
│   └── Knowledge Matching - Similarity search
└── Vision Layer (Optional)
    └── Image Understanding - Parse problem images
```

## 1. LLM Models (Required)

### Primary LLM
**Purpose**: Core reasoning for all AI tutoring functions
**Used by**: 
- Instructor Agent (hint generation L0-L4)
- Advisor Agent (mode selection, instructions)
- Recommendation reasons (natural language generation)
- Error diagnosis (calculation error detection)

**Configuration**:
```env
# Option 1: SiliconFlow (Recommended for China)
OPENAI_API_KEY=sk-your-key
OPENAI_API_BASE=https://api.siliconflow.cn/v1
LLM_MODEL=Qwen/Qwen2.5-72B-Instruct

# Option 2: OpenAI (International)
OPENAI_API_KEY=sk-your-key
OPENAI_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-3.5-turbo

# Option 3: DashScope
DASHSCOPE_API_KEY=sk-your-key
DASHSCOPE_API_BASE=https://dashscope.aliyuncs.com/api/v1
```

**Model Requirements**:
- Must support Chinese well (for math problem understanding)
- Should support function calling (for structured output)
- Recommended: 32B+ parameters for complex math reasoning

**Shared vs Separate**: 
- ✅ Current: Instructor and Advisor share ONE LLM API
- ✅ Reason: Same model ensures consistent teaching style
- ✅ Cost: Single API key reduces complexity

### Vision Model (Optional)
**Purpose**: Parse math problem images
**Used by**: Image upload feature

**Configuration**:
```env
VISION_MODEL=Qwen/Qwen2-VL-72B-Instruct
```

**Note**: Only needed if you want students to upload problem images.

## 2. Embedding Models (Required)

### Primary Embedding Model
**Purpose**: Convert text to vectors for similarity search
**Used by**:
- RAG candidate pool building
- Question recommendation
- Similar problem retrieval

**Configuration**:
```env
# Option 1: Chaosuansuan (Competition Model)
CHAOSUAN_API_KEY=your-key
CHAOSUAN_API_BASE=https://api.scnet.cn/v1
CHAOSUAN_EMBEDDING_MODEL=Qwen3-Embedding-8B

# Option 2: DashScope
DASHSCOPE_API_KEY=sk-your-key
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v3

# Option 3: SiliconFlow
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
```

**Model Comparison**:
| Model | Dimension | Language | Use Case |
|-------|-----------|----------|----------|
| Qwen3-Embedding-8B | 4096 | Chinese | Competition requirement |
| text-embedding-v3 | 1536 | Multilingual | General purpose |
| bge-large-zh-v1.5 | 1024 | Chinese | Cost-effective |

## 3. Model Usage by Feature

### Feature: Hint Generation (L0-L4)
**Model**: Primary LLM
**API**: LLMService.generate_hint()
**Prompt Type**: Structured with constraints
**Example**:
```python
# L1: Direction hint
"Give only problem-solving direction, no formulas, no steps, no answer"

# L4: Complete answer
"Provide full solution with all intermediate steps"
```

### Feature: Advisor Mode Selection
**Model**: Primary LLM
**API**: AdvisorAgent.determine_teaching_mode()
**Logic**: Rule-based + LLM enhancement
**Modes**:
- SCAFFOLD: P(L) < 0.4 or consecutive_wrong >= 2
- CHALLENGE: P(L) > 0.8 and high accuracy
- ENCOURAGE: consecutive_wrong >= 3
- NORMAL: Default

### Feature: Recommendation Reasons
**Model**: Primary LLM
**API**: LLMService.generate_recommendation_reason()
**Output**: 30-character natural language explanation
**Example**: "距离上次做错这道放缩法已经过去2天，测测肌肉记忆还在不在？"

### Feature: Error Diagnosis
**Model**: Primary LLM
**API**: CalculationErrorHandler.diagnose()
**Purpose**: Distinguish calculation errors from logic errors
**Output**: Error type + confidence score

### Feature: Question Retrieval (RAG)
**Model**: Embedding Model
**API**: RAGCandidatePoolBuilder.recall_by_weak_kps()
**Process**:
1. Embed weak knowledge points
2. Vector similarity search in ChromaDB
3. Return top-k similar questions

## 4. Minimum Required Configuration

### For Basic Functionality:
```env
# One LLM provider (required)
OPENAI_API_KEY=sk-your-key
OPENAI_API_BASE=https://api.siliconflow.cn/v1
LLM_MODEL=Qwen/Qwen2.5-72B-Instruct

# One Embedding provider (required)
CHAOSUAN_API_KEY=your-key
CHAOSUAN_EMBEDDING_MODEL=Qwen3-Embedding-8B
```

### For Full Functionality:
```env
# LLM
OPENAI_API_KEY=sk-your-key
OPENAI_API_BASE=https://api.siliconflow.cn/v1
LLM_MODEL=Qwen/Qwen2.5-72B-Instruct

# Vision (optional)
VISION_MODEL=Qwen/Qwen2-VL-72B-Instruct

# Embedding
CHAOSUAN_API_KEY=your-key
CHAOSUAN_EMBEDDING_MODEL=Qwen3-Embedding-8B

# Fallback embedding
DASHSCOPE_API_KEY=sk-your-key
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v3
```

## 5. Model Fallback Chain

If primary model fails, the system uses:

```
LLM:
  Primary: Configured LLM (SiliconFlow/OpenAI/DashScope)
  Fallback: Mock responses (for development)

Embedding:
  Primary: Chaosuansuan Qwen3-Embedding-8B
  Fallback 1: DashScope text-embedding-v3
  Fallback 2: SiliconFlow BAAI/bge-large-zh-v1.5
```

## 6. Cost Optimization

### Recommended Setup for Competition:
```env
# Primary: SiliconFlow (good balance of quality and cost)
OPENAI_API_KEY=sk-siliconflow-key
OPENAI_API_BASE=https://api.siliconflow.cn/v1
LLM_MODEL=Qwen/Qwen2.5-72B-Instruct

# Embedding: Chaosuansuan (competition requirement)
CHAOSUAN_API_KEY=your-key
CHAOSUAN_EMBEDDING_MODEL=Qwen3-Embedding-8B
```

**Estimated Cost per Student per Day**:
- LLM calls: ~50 requests × ¥0.01 = ¥0.50
- Embedding calls: ~20 requests × ¥0.001 = ¥0.02
- **Total**: ~¥0.52 per student per day

## 7. Model Performance Tuning

### Temperature Settings:
```python
# Hints: Lower temperature for consistency
TEMPERATURE=0.3  # for L1-L3 hints

# Creative tasks: Higher temperature
TEMPERATURE=0.7  # for recommendation reasons
```

### Max Tokens:
```python
LLM_MAX_TOKENS=4096  # For complex math problems
```

## 8. Summary Table

| Component | Model Type | Required | Shared | Purpose |
|-----------|-----------|----------|--------|---------|
| Instructor | LLM | ✅ Yes | ✅ Yes | Generate hints L0-L4 |
| Advisor | LLM | ✅ Yes | ✅ Yes | Mode selection, control |
| Reason Gen | LLM | ✅ Yes | ✅ Yes | Recommendation explanations |
| Error Diagnosis | LLM | ✅ Yes | ✅ Yes | Distinguish error types |
| RAG Retrieval | Embedding | ✅ Yes | N/A | Question similarity search |
| Image Parse | Vision | ❌ No | N/A | Parse problem images |

**Key Points**:
- ✅ Only **ONE LLM API** needed (shared by all components)
- ✅ **ONE Embedding API** needed (for RAG)
- ❌ Vision model optional (only for image upload feature)
- ✅ All components use the same LLM for consistency
