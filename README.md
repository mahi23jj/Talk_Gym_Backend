# TalkGym Backend

**AI-Powered Interview Coaching Engine**

TalkGym is an intelligent behavioral interview training platform that analyzes both **what candidates say** and **how they say it**, then delivers adaptive coaching to improve interview performance through structured practice and measurable feedback.

This repository contains the backend architecture powering TalkGym’s multimodal analysis pipeline.

---

# Overview

TalkGym helps candidates practice and improve behavioral interviews using a dual-analysis system:

- **Semantic Interview Analysis**
  - Evaluates STAR structure
  - Detects ownership, initiative, and impact signals
  - Measures relevance, clarity, and specificity
  - Generates behavioral coaching prompts

- **Voice Delivery Analysis**
  - Speech pacing analysis
  - Pause detection
  - Confidence estimation
  - Nervousness scoring
  - Monotony detection
  - Vocal rhythm consistency evaluation

The system combines these outputs into adaptive coaching pathways that guide users toward stronger interview performance.

---

# Core Features

## 1. Audio Transcription Pipeline

Converts uploaded interview audio into structured sentence-level transcripts.

**Supports**

- Faster-Whisper transcription
- Background async processing
- Sentence segmentation
- Indexed transcript normalization

Example output:

```json
[
  {
    "idx": 0,
    "sentence": "I led the redesign of our backend architecture"
  },
  {
    "idx": 1,
    "sentence": "This reduced latency by 35 percent"
  }
]
```

---

## 2. Behavioral Intelligence Analysis

Evaluates interview answers using rubric-based behavioral scoring.

Measures:

- Ownership
- Initiative
- Impact
- Specificity
- STAR completeness
- Relevance
- Clarity

Flags:

- Rambling
- Blaming language
- Weak ownership
- Low specificity
- Missing measurable impact

---

## 3. Voice Delivery Intelligence

Extracts acoustic performance metrics using signal processing.

Analyzes:

- Speech rate
- Silence ratio
- Long pause frequency
- Pitch variation
- Monotony score
- Confidence estimation
- Nervousness detection

Built using:

- librosa
- numpy
- DSP feature extraction

---

## 4. Adaptive Coaching Engine

Routes users into personalized coaching flows.

### Structural Coaching

Breaks weak answers into STAR components:

- Situation
- Task
- Action
- Result

Allows targeted reconstruction practice.

---

### Behavioral Coaching

Targets weak behavioral signals:

- Weak ownership
- Low initiative
- Missing measurable impact

Generates follow-up coaching prompts and evaluates rewrites.

---

## 5. Final Simulation Comparison

Users can reattempt interviews after coaching.

TalkGym compares:

- Original performance
- Improved response
- Structural improvement delta
- Behavioral growth delta
- Delivery confidence progression

This creates measurable learning feedback loops.

---

# System Architecture

```text
Mobile App
    ↓
FastAPI API Layer
    ↓
Redis Queue
    ↓
Async Worker Pool
    ↓
Parallel Processing
    ├── Transcription Engine
    ├── Voice DSP Analysis
    ├── Behavioral Evaluation
    └── Coaching Recommendation Engine
    ↓
Merged Analysis Response
    ↓
Client Coaching UI
```

---

# Tech Stack

## Backend Framework

- FastAPI
- AsyncIO
- Redis
- Uvicorn

## AI / NLP

- Faster-Whisper
- LLM-based analysis layer
- Rule-engine fallback scoring

## Audio Processing

- librosa
- numpy
- imageio-ffmpeg

## Infrastructure

- Render deployment
- Background worker services
- Async queue orchestration

---

# Concurrency Model

TalkGym uses a semaphore-controlled worker pool for safe parallel job execution.

```python
MAX_CONCURRENT_JOBS = 5
```

Prevents:

- CPU overload
- transcription bottlenecks
- runaway task spawning

Includes timeout protection for:

- transcription tasks
- voice feature extraction
- stalled processing recovery

---

# Fault Tolerance

Built-in resilience includes:

- async task isolation
- worker recovery
- timeout cancellation
- rule-based fallback analysis
- exception-safe job cleanup

If AI analysis fails, deterministic scoring still produces useful coaching feedback.

---

# API Workflow

## Submit Interview

Uploads interview audio for async processing.

Returns:

```json
{
  "job_id": 42,
  "status": "queued"
}
```

---

## Processing

Worker executes:

1. Transcription
2. Transcript normalization
3. Voice feature extraction
4. Behavioral analysis
5. Coaching generation
6. Response merge

---

## Fetch Result

Returns full structured evaluation:

```json
{
  "overall_score": 7.8,
  "content": {},
  "behavioral": {},
  "voice_metrics": {},
  "flags": [],
  "sentence_feedback": [],
  "behavioral_questions": [],
  "star_example": {},
  "primary_training_mode": "behavioral_training"
}
```

---

# Production Deployment

Deployed on Render with:

- FastAPI web service
- Dedicated background worker
- Redis integration
- cold-start mitigation via health warmup endpoint

---

# Why TalkGym?

Traditional interview prep tools only score text.

TalkGym evaluates:

- **What you say**
- **How you say it**
- **Why your answer succeeds or fails**
- **How to improve through adaptive practice**

This creates a realistic interview training loop closer to real behavioral interview coaching.

---

# Project Vision

TalkGym aims to make high-quality interview coaching accessible through scalable AI systems that simulate real-world feedback and measurable improvement.

---

# Author

Built by **Mahlet Solomon**

Backend Engineering • AI Systems • Async Architecture • Applied Interview Intelligence

# Talk Gym Backend

Professional FastAPI project scaffold with clear layering for scaling features.

## Project Structure

```
Talk_Gym_Backend/
├── app/
│   ├── api/
│   │   ├── router.py
│   │   └── v1/
│   │       └── endpoints/
│   │           └── health.py
│   ├── core/
│   │   └── config.py
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── main.py
├── tests/
│   └── test_health.py
└── README.md
```

## Run Locally

1. Install dependencies:

	```bash
	pip install -r requirements.txt
	```

2. Start the API:

	```bash
	uvicorn main:app --reload
	```

3. Open docs:

	- Swagger UI: `http://127.0.0.1:8000/docs`
	- ReDoc: `http://127.0.0.1:8000/redoc`

## Environment Variables

Optional `.env` keys:

- `APP_NAME`
- `APP_VERSION`
- `API_V1_PREFIX`
- `POSTGRES_URL` (or legacy `postgres_url`)

## Next Development Pattern

- Add request/response schemas in `app/schemas/`
- Add domain models in `app/models/`
- Keep business logic in `app/services/`
- Keep route handlers thin in `app/api/v1/endpoints/`
