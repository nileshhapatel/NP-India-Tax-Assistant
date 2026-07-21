# LLM Provider Quick-Start Guide

## Current Status

```bash
$ curl http://localhost:8000/api/llm/status
{
  "ok": true,
  "current_provider": "rule_based",
  "provider_name": "Rule-Based AI",
  "available": true,
  "fallback_enabled": true,
  "has_claude_key": false,
  "has_openai_key": false
}
```

**Currently Using:** Rule-Based AI (No external API required)
**Status:** ✅ All features working

---

## 🎯 Switch to Claude (Anthropic)

### Step 1: Get Claude API Key
1. Go to: https://console.anthropic.com/
2. Sign in or create account
3. Click "API Keys" in left sidebar
4. Click "Create Key"
5. Copy the key (starts with `sk-ant-v0-`)

### Step 2: Update .env File
```bash
cd ~/Library/CloudStorage/OneDrive-Personal/Documents/IndiaTax/itr_family_workspace
nano .env
```

Find these lines:
```env
LLM_PROVIDER=claude
CLAUDE_API_KEY=sk-ant-...
OPENAI_API_KEY=
LLM_FALLBACK_TO_RULES=true
```

Replace `sk-ant-...` with your actual key:
```env
LLM_PROVIDER=claude
CLAUDE_API_KEY=sk-ant-v0-abc123defghijklmnop
OPENAI_API_KEY=
LLM_FALLBACK_TO_RULES=true
```

### Step 3: Restart API
```bash
docker compose restart api
```

### Step 4: Verify
```bash
curl http://localhost:8000/api/llm/status | jq '.current_provider'
# Should return: "claude"
```

### Step 5: Test Claude
```bash
curl -X POST http://localhost:8000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What tax deductions am I eligible for as an NRI?"}'
```

---

## 🎯 Switch to ChatGPT (OpenAI)

### Step 1: Get ChatGPT API Key
1. Go to: https://platform.openai.com/
2. Sign in or create account
3. Click "API Keys" in left sidebar
4. Click "Create new secret key"
5. Copy the key (starts with `sk-proj-`)
6. **IMPORTANT:** Set up billing/credit in OpenAI account

### Step 2: Update .env File
```bash
nano .env
```

Update to:
```env
LLM_PROVIDER=chatgpt
CLAUDE_API_KEY=
OPENAI_API_KEY=sk-proj-xyz123abcdefghijk
LLM_FALLBACK_TO_RULES=true
```

### Step 3: Restart API
```bash
docker compose restart api
```

### Step 4: Verify
```bash
curl http://localhost:8000/api/llm/status | jq '.current_provider'
# Should return: "chatgpt"
```

### Step 5: Test ChatGPT
```bash
curl -X POST http://localhost:8000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Explain Form 26AS to me"}'
```

---

## 📊 Provider Comparison

| Feature | Claude | ChatGPT | Rule-Based |
|---------|--------|---------|-----------|
| **Cost** | ~$0.003/1K tokens | ~$0.00015/1K tokens | Free |
| **Speed** | 2-3 seconds | <1 second | Instant |
| **Tax Knowledge** | Excellent | Good | Good |
| **Requires Key** | Yes | Yes | No |
| **Setup Time** | 2 minutes | 5 minutes (need billing) | Already set up |
| **Best For** | Complex analysis | Quick answers | Offline/testing |
| **Fallback** | Yes → Rule-Based | Yes → Rule-Based | - |

---

## 💰 Cost Estimates

### Claude (Anthropic)
- 1,000 input tokens ≈ 750 words
- 1,000 output tokens ≈ 750 words
- **Cost per tax question:** ~$0.01-0.05
- **Monthly (10 questions/day):** ~$3-15

### ChatGPT (OpenAI)
- Model: gpt-4o-mini (cheapest)
- 1,000 input tokens ≈ 750 words
- 1,000 output tokens ≈ 750 words
- **Cost per tax question:** ~$0.001-0.005
- **Monthly (10 questions/day):** ~$0.30-1.50

---

## 🔄 Switching Back to Rule-Based

```bash
nano .env
```

Update to:
```env
LLM_PROVIDER=rule_based
CLAUDE_API_KEY=
OPENAI_API_KEY=
LLM_FALLBACK_TO_RULES=true
```

Restart:
```bash
docker compose restart api
```

---

## 🧪 Test All Endpoints

### Test Chat (uses current provider)
```bash
curl -X POST http://localhost:8000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"what is 80c deduction"}'
```

### Test Deductions
```bash
curl -X POST http://localhost:8000/api/ai/deductions \
  -H "Content-Type: application/json" \
  -d '{"case_id":1}'
```

### Test Residency Analysis
```bash
curl -X POST http://localhost:8000/api/ai/residency \
  -H "Content-Type: application/json" \
  -d '{"case_id":1}'
```

### Get LLM Status
```bash
curl http://localhost:8000/api/llm/status | jq '.'
```

---

## ⚠️ Troubleshooting

### "Provider unavailable" error
**Cause:** API key not configured or invalid
**Fix:** 
1. Check `.env` file has correct key
2. Verify key isn't expired
3. Check API account has credits
4. Fallback will use rule-based AI automatically

### API key not being recognized
**Cause:** API key not reloaded after restart
**Fix:**
```bash
# Clear Docker cache and restart
docker compose down
docker compose up -d
```

### Slow responses
**Claude:** Normal (2-3 seconds)
**ChatGPT:** Should be <1 second
**If slow:** Check internet connection, API rate limits

### 401/403 Errors
**Cause:** Invalid or expired API key
**Fix:** Regenerate key from provider console and update `.env`

---

## 📖 API Documentation

### Providers Supported
```python
class LLMProvider(str, Enum):
    CLAUDE = "claude"
    CHATGPT = "chatgpt"
    RULE_BASED = "rule_based"
```

### Configuration
```env
LLM_PROVIDER=<claude|chatgpt|rule_based>
CLAUDE_API_KEY=<your-key-here>
OPENAI_API_KEY=<your-key-here>
LLM_FALLBACK_TO_RULES=<true|false>
```

### Environment Variables
- `LLM_PROVIDER`: Which provider to use (default: claude)
- `CLAUDE_API_KEY`: Anthropic API key
- `OPENAI_API_KEY`: OpenAI API key
- `LLM_FALLBACK_TO_RULES`: Use rule-based if provider fails (default: true)

---

## 🎓 How It Works Internally

```python
# 1. Check configuration
config = LLMConfig()

# 2. Try to use selected provider
if config.provider == "claude":
    provider = ClaudeProvider(config.claude_api_key)
elif config.provider == "chatgpt":
    provider = ChatGPTProvider(config.openai_api_key)
else:
    provider = RuleBasedProvider()

# 3. Make LLM call
response = provider.call(system_prompt, user_message)

# 4. If provider fails and fallback enabled
if not response and config.fallback_to_rules:
    provider = RuleBasedProvider()
    response = provider.call(system_prompt, user_message)

# 5. Return response with source info
return {
    "ok": True,
    "response": response,
    "source": "claude",
    "provider": "Claude (Anthropic)"
}
```

---

## 📞 Need Help?

**Claude Issues:** https://console.anthropic.com/ (check API status)
**OpenAI Issues:** https://status.openai.com/ (check API status)

**API Key locations:**
- Claude: https://console.anthropic.com/
- OpenAI: https://platform.openai.com/api-keys

**Documentation:**
- Claude: https://docs.anthropic.com/
- OpenAI: https://platform.openai.com/docs/

