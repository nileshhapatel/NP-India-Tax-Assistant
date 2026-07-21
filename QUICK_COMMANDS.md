# Quick Commands Reference

## 🚀 System Management

### Start Everything
```bash
cd ~/Library/CloudStorage/OneDrive-Personal/Documents/IndiaTax/itr_family_workspace
docker compose up -d
```

### Stop Everything
```bash
docker compose down
```

### Restart API Only
```bash
docker compose restart api
```

### View Logs
```bash
docker logs -f itr_family_workspace-api-1
docker logs -f itr_family_workspace-frontend-1
```

---

## 🤖 LLM Provider Management

### Check Current Provider
```bash
curl http://localhost:8000/api/llm/status | jq '.'
```

### Switch to Claude
```bash
# 1. Edit .env file
nano .env

# Set:
# LLM_PROVIDER=claude
# CLAUDE_API_KEY=sk-ant-v0-YOUR_KEY

# 2. Restart
docker compose restart api

# 3. Verify
curl http://localhost:8000/api/llm/status | jq '.current_provider'
```

### Switch to ChatGPT
```bash
# 1. Edit .env file
nano .env

# Set:
# LLM_PROVIDER=chatgpt
# OPENAI_API_KEY=sk-proj-YOUR_KEY

# 2. Restart
docker compose restart api

# 3. Verify
curl http://localhost:8000/api/llm/status | jq '.current_provider'
```

### Switch to Rule-Based (No API Key)
```bash
# 1. Edit .env file
nano .env

# Set:
# LLM_PROVIDER=rule_based

# 2. Restart
docker compose restart api
```

---

## 📊 API Testing

### Household Summary
```bash
curl http://localhost:8000/api/household/summary | jq '.household_summary'
```

### Get All Members
```bash
curl http://localhost:8000/api/household/members | jq '.members'
```

### Filing Status
```bash
curl http://localhost:8000/api/household/consolidated-filing | \
  jq '.filing_status'
```

### Compare Two Cases
```bash
# Nilesh vs Avani
curl http://localhost:8000/api/cases/1/compare/2 | jq '.comparison'
```

### Test AI Chat
```bash
curl -X POST http://localhost:8000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is 80c deduction?"}' | jq '.response'
```

### Test AI Deductions
```bash
curl -X POST http://localhost:8000/api/ai/deductions \
  -H "Content-Type: application/json" \
  -d '{"case_id":1}' | jq '.suggestions'
```

### List Supported Document Types
```bash
curl http://localhost:8000/api/documents/supported-types | jq '.types'
```

### Parse Document
```bash
curl -X POST http://localhost:8000/api/documents/parse \
  -F "file=@path/to/AIS.pdf" \
  -F "doc_type=ais" | jq '.'
```

---

## 💾 Database Management

### Backup Database
```bash
pg_dump -Fc itr_family > itr_family.backup
```

### Restore Database
```bash
pg_restore -d itr_family itr_family.backup
```

### Connect to PostgreSQL
```bash
psql -U India_ITR_User -d India_ITR_Family -h localhost
```

### List All Income Entries
```sql
SELECT ie.id, ie.income_type, ie.gross_amount, ie.tds_amount, 
       tc.assessment_year, tp.name
FROM income_entries ie
JOIN tax_cases tc ON ie.case_id = tc.id
JOIN taxpayers tp ON tc.taxpayer_id = tp.id
ORDER BY tp.name;
```

### Check Taxpayer Cases
```sql
SELECT tp.id, tp.name, tc.id as case_id, tc.assessment_year, 
       tc.residential_status
FROM taxpayers tp
LEFT JOIN tax_cases tc ON tp.id = tc.taxpayer_id
ORDER BY tp.name;
```

---

## 🔌 Frontend Access

### Open Application
```
http://localhost:3000
```

### Pages Available
- Home: http://localhost:3000/
- Profile: http://localhost:3000/profile
- Income: http://localhost:3000/income
- Reconciliation: http://localhost:3000/reconciliation
- Documents: http://localhost:3000/documents
- Review: http://localhost:3000/review
- Chat: http://localhost:3000/chat

---

## 📁 Important Files

### Configuration
```
.env                    - API keys, database, LLM settings
docker-compose.yml      - Container orchestration
```

### Documentation
```
PHASE3_IMPLEMENTATION.md - Complete feature documentation
LLM_PROVIDER_GUIDE.md   - Provider switching guide
QUICK_COMMANDS.md       - This file
README.md               - Project overview
```

### Code
```
backend/app/main.py             - FastAPI endpoints
backend/app/llm_provider.py      - Multi-provider LLM
backend/app/document_parser.py   - PDF extraction
frontend/pages/                  - React components
```

### Data
```
private_data/           - Document uploads (Git ignored)
itr_family.backup       - Database backup
```

---

## 🆘 Troubleshooting

### API Not Responding
```bash
# Check if containers are running
docker ps

# Check API logs
docker logs itr_family_workspace-api-1

# Restart containers
docker compose down && docker compose up -d
```

### LLM Provider Not Switching
```bash
# 1. Check .env file
cat .env | grep LLM_PROVIDER

# 2. Ensure API key is set correctly
cat .env | grep CLAUDE_API_KEY

# 3. Full restart
docker compose down
docker compose up -d
sleep 10
curl http://localhost:8000/api/llm/status
```

### Database Connection Error
```bash
# Check if database is running
psql -U India_ITR_User -d India_ITR_Family -h localhost -c "SELECT 1"

# Check .env DATABASE_URL
cat .env | grep DATABASE_URL

# Restart PostgreSQL (if installed locally)
brew services restart postgresql
```

### PDF Parser Not Working
```bash
# Install pdfplumber
pip install pdfplumber

# Or PyPDF2
pip install PyPDF2

# Rebuild Docker (if using containers)
docker compose down
docker compose up --build -d
```

---

## 📈 Monitoring

### Check System Health
```bash
# API health
curl http://localhost:8000/health

# LLM status
curl http://localhost:8000/api/llm/status

# Database connection
psql -U India_ITR_User -d India_ITR_Family -h localhost -c "SELECT COUNT(*) FROM taxpayers"

# Container status
docker ps
```

### Monitor Logs
```bash
# Follow API logs
docker logs -f itr_family_workspace-api-1

# Follow Frontend logs
docker logs -f itr_family_workspace-frontend-1

# Search logs for errors
docker logs itr_family_workspace-api-1 2>&1 | grep ERROR
```

---

## 🔐 Security

### Change Database Password
```bash
psql -U postgres
ALTER USER India_ITR_User WITH PASSWORD 'new-strong-password';
\q

# Update .env
nano .env
# Update DATABASE_URL with new password
```

### Rotate API Keys
```bash
# Get new Claude key from https://console.anthropic.com/
# Get new ChatGPT key from https://platform.openai.com/api-keys

nano .env
# Update CLAUDE_API_KEY and/or OPENAI_API_KEY
docker compose restart api
```

### Backup Sensitive Data
```bash
# Backup database
pg_dump -Fc itr_family > backup_$(date +%Y%m%d).backup

# Backup .env file (keep in secure location)
cp .env ../backup/.env.backup

# Backup private documents
tar -czf private_data_$(date +%Y%m%d).tar.gz private_data/
```

---

## 📚 API Documentation

### Swagger UI
```
http://localhost:8000/docs
```

### ReDoc
```
http://localhost:8000/redoc
```

---

## 🎓 Common Tasks

### Add Income Entry
```bash
curl -X POST http://localhost:8000/api/cases/1/income \
  -H "Content-Type: application/json" \
  -d '{
    "income_type": "Salary",
    "gross_amount": 250000,
    "tds_amount": 25000,
    "description": "August salary"
  }'
```

### Get Income Entries
```bash
curl http://localhost:8000/api/cases/1/income | jq '.income_entries'
```

### Get Tax Report
```bash
curl http://localhost:8000/api/cases/1/reports/calculation | jq '.report'
```

### Get Reconciliation
```bash
curl http://localhost:8000/api/cases/1/reconciliation | jq '.'
```

---

## 🔄 Development Workflow

### Make Code Changes
```bash
# Edit files
nano backend/app/main.py

# Docker will auto-reload (with --reload flag)
# Check logs for changes
docker logs -f itr_family_workspace-api-1
```

### Install New Dependencies
```bash
# Add to requirements.txt
echo "new-package==1.0.0" >> requirements.txt

# Rebuild containers
docker compose down
docker compose up --build -d
```

### Run Tests (when available)
```bash
# Python tests
python -m pytest backend/tests/

# Frontend tests
npm test

# Integration tests
docker compose exec api python -m pytest
```

---

## 📞 Quick Support

**LLM Documentation:**
- Claude: https://docs.anthropic.com/
- OpenAI: https://platform.openai.com/docs/

**API Key Creation:**
- Claude: https://console.anthropic.com/
- OpenAI: https://platform.openai.com/api-keys

**Database:**
- PostgreSQL: https://www.postgresql.org/docs/

**Container Management:**
- Docker: https://docs.docker.com/

