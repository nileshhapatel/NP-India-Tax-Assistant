# ITR Family Workspace - Automated Setup Guide

This application includes **automatic setup scripts** that handle all installation steps in one go.

## Quick Start (Recommended)

### Option 1: Fully Automated Setup (macOS/Linux)

```bash
cd itr_family_workspace
python3 setup.py
```

This automatically:
- ✅ Locates PostgreSQL 18+
- ✅ Tests database connection
- ✅ Creates database user (`India_ITR_User`)
- ✅ Creates database (`India_ITR_Family`)
- ✅ Generates `.env` configuration
- ✅ Creates Python virtual environment
- ✅ Installs dependencies
- ✅ Initializes database with seed data
- ✅ Verifies the complete setup

**You will be prompted for:**
- Database username (default: `India_ITR_User`)
- Database name (default: `India_ITR_Family`)
- Database password (hidden input)
- Password hint (optional)

### Option 2: Headless Setup (CI/CD, Automation)

Set environment variables and run setup:

```bash
export ITR_DB_USER=India_ITR_User
export ITR_DB_NAME=India_ITR_Family
export ITR_DB_PASSWORD=Nilh2399$@#1620
export ITR_DB_HINT="Personal MacBook Password"

python3 setup.py
```

No prompts will appear — all configuration comes from environment.

### Option 3: Manual Step-by-Step

If you prefer manual control:

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Create .env from template
cp .env.example .env
# Edit .env with your database credentials

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create PostgreSQL user and database
psql postgres
```

Inside PostgreSQL:
```sql
CREATE USER "India_ITR_User" WITH PASSWORD 'Nilh2399$@#1620';
CREATE DATABASE "India_ITR_Family" OWNER "India_ITR_User";
\q
```

Then initialize:
```bash
python -m itr_workspace.seed
```

---

## After Setup: Starting the Application

Once setup completes successfully:

```bash
# Activate environment
source .venv/bin/activate

# Start Streamlit
streamlit run app.py
```

The app will open at: **http://localhost:8501**

---

## Database Configuration

### What Gets Created

The setup script creates:

**PostgreSQL User:**
- Username: `India_ITR_User` (configurable)
- Password: Your choice (encrypted in `.env`)
- Hint: Your choice (for password recovery reference)

**PostgreSQL Database:**
- Name: `India_ITR_Family` (configurable)
- Owner: `India_ITR_User`
- Encoding: UTF-8 (default)

### Connection Details

The `.env` file stores:
```env
DATABASE_URL=postgresql+psycopg://[username]:[password]@localhost:5432/[database]
ITR_DATA_DIR=./private_data
ITR_DB_HINT=Personal MacBook Password
```

**Security Note:** 
- `.env` is restricted to `600` (owner read/write only)
- Never commit `.env` to Git (included in `.gitignore`)
- Back up `.env` separately

---

## Troubleshooting

### PostgreSQL Not Found

**Error:**
```
PostgreSQL not found!
```

**Solution:**
```bash
# Install PostgreSQL 18 via Homebrew
brew install postgresql@18

# Start the service
brew services start postgresql@18

# Verify
brew services list | grep postgres
```

### Cannot Connect to Database

**Error:**
```
authentication failed for user "India_ITR_User"
```

**Solutions:**

1. **Wrong password:**
   - Check `.env` DATABASE_URL
   - Verify the password is correct
   - Recreate user:
     ```bash
     psql -U postgres
     DROP USER IF EXISTS "India_ITR_User";
     CREATE USER "India_ITR_User" WITH PASSWORD 'correct-password';
     ```

2. **PostgreSQL not running:**
   ```bash
   brew services start postgresql@18
   ```

3. **Database doesn't exist:**
   ```bash
   psql -U postgres
   CREATE DATABASE "India_ITR_Family" OWNER "India_ITR_User";
   \q
   ```

### Virtual Environment Issues

**Recreate venv:**
```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Seed Data Not Loading

**Check logs:**
```bash
source .venv/bin/activate
python -m itr_workspace.seed 2>&1 | head -50
```

**Reset and reseed:**
```bash
# Backup current database (if needed)
pg_dump -Fc India_ITR_Family > itr_backup.sql

# Drop and recreate
psql -U postgres -c "DROP DATABASE IF EXISTS \"India_ITR_Family\";"
psql -U postgres -c "CREATE DATABASE \"India_ITR_Family\" OWNER \"India_ITR_User\";"

# Reseed
python -m itr_workspace.seed
```

---

## Portability & Redeployment

### On a New Machine

The setup script works identically on any macOS/Linux system:

```bash
# Copy entire directory to new machine
scp -r itr_family_workspace user@newmachine:~/projects/

# On new machine
cd itr_family_workspace
python3 setup.py

# Restore database from backup (if needed)
pg_restore -d India_ITR_Family < itr_backup.sql
```

### With Docker (Optional)

You can extend this setup for containerization:

```dockerfile
FROM python:3.13-slim

# Install PostgreSQL client
RUN apt-get update && apt-get install -y postgresql-client

WORKDIR /app
COPY . .

# Run setup with environment variables
ENV ITR_DB_HOST=db
ENV ITR_DB_USER=India_ITR_User
ENV ITR_DB_PASSWORD=$DB_PASSWORD

RUN python3 setup.py && \
    . .venv/bin/activate && \
    pip install -r requirements.txt

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

---

## Environment Variables Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `ITR_DB_USER` | `India_ITR_User` | PostgreSQL username |
| `ITR_DB_NAME` | `India_ITR_Family` | Database name |
| `ITR_DB_PASSWORD` | (required) | Database password |
| `ITR_DB_HINT` | (optional) | Password hint for reference |
| `DATABASE_URL` | (auto-generated) | Full connection string |
| `ITR_DATA_DIR` | `./private_data` | Path for uploaded documents |

---

## Backup & Recovery

### Full Backup

```bash
# Backup database
pg_dump -Fc India_ITR_Family > itr_family.backup

# Backup .env and private data
tar -czf itr_config_and_data.tar.gz .env private_data/
```

### Restore Database

```bash
# Drop current database
psql -U postgres -c "DROP DATABASE IF EXISTS \"India_ITR_Family\";"

# Recreate and restore
psql -U postgres -c "CREATE DATABASE \"India_ITR_Family\" OWNER \"India_ITR_User\";"
pg_restore -d India_ITR_Family < itr_family.backup
```

### Restore Configuration

```bash
tar -xzf itr_config_and_data.tar.gz
```

---

## Next Steps After Setup

1. **Open Profile** → Enter PAN (last 4 chars only)
2. **Residency Worksheet** → Confirm NRI/RNOR status
3. **Upload Documents** → AIS, TIS, 26AS, bank statements
4. **Income Entry** → Gross income amounts
5. **Tax Credits** → TDS from 26AS
6. **Reconciliation** → Three-way matching
7. **Review & Export** → Generate filing package

See `README.md` for full workflow documentation.

---

## Support

- **Issues?** Check the troubleshooting section above
- **Questions?** See `README.md` for detailed documentation
- **Setup help?** Run `python setup.py --help` (coming soon)

---

## Security Notes

✅ **Private data never transmitted** - uploads stored locally in `private_data/`
✅ **Full PAN never stored** - only last 4 characters in database
✅ **No password storage** - only `.env` contains credentials (locally encrypted)
✅ **FileVault recommended** - enable Mac encryption for full protection
✅ **Regular backups** - database + `private_data/` + `.env`

---

**Setup Version:** 1.0  
**Last Updated:** 2026-07-20  
**Compatible:** macOS 11+ / Ubuntu 20.04+ / PostgreSQL 18+
