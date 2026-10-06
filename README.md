# AI Challenge Starter

A multi-provider LLM starter template in Python that automatically falls back across **Groq**, **Gemini**, and **OpenRouter** APIs.

## 🚀 Features

- **Multi-Provider Resilience**: Tries LLM providers in sequence (`Groq` ➔ `Gemini` ➔ `OpenRouter`).
- **Automatic Fallback**: Seamlessly switches to the next provider on API errors, rate limits, or quota issues.
- **JSON Schema Validation**: Standardized JSON output extraction with optional Pydantic schema validation.
- **Environment Configured**: Easy setup via `.env` file.

## 📁 Project Structure

```
.
├── llm.py          # Core LLM wrapper supporting fallback execution & JSON parsing
├── .env            # API keys and provider model configurations
├── .env.example    # Template for environment variables
└── README.md       # Project documentation
```

## 🛠️ Getting Started

### 1. Environment Setup

Copy `.env.example` to `.env` and insert your API keys:

```bash
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
OPENROUTER_API_KEY=your_openrouter_api_key

GROQ_MODEL=llama-3.3-70b-versatile
GEMINI_MODEL=gemini-2.0-flash
OPENROUTER_MODEL=openai/gpt-oss-120b

PROVIDER_ORDER=groq,gemini,openrouter
```

### 2. Usage

Import and call `ask` or `ask_json` in Python:

```python
from llm import ask, ask_json

# Text generation
response = ask("Explain quantum computing in one sentence.")
print(response)

# Structured JSON response
data = ask_json("List 3 primary colors in JSON format under key 'colors'")
print(data)
```

## 📄 License

MIT License
