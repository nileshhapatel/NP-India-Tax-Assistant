# Family ITR Workspace

A local, PostgreSQL-backed workspace built specifically for Nilesh and Avani's India income-tax return preparation.

## What it does

- Keeps one history across assessment years.
- Creates separate cases for Nilesh and Avani.
- Tracks NRI/RNOR status inputs and travel-day evidence.
- Tracks HDFC/Bank of Baroda NRE, NRO and savings accounts.
- Tracks Zerodha dividends, holdings, SIP/CAS records and sale/redemption confirmations.
- Tracks home-loan ownership, possession and FY-specific principal/interest.
- Stores uploaded evidence locally (not inside PostgreSQL).
- Reconciles source documents, AIS/26AS, bank credits and return amounts.
- Produces CSV/JSON filing-pack exports for review and portal entry.
- Includes warnings, review flags, audit history and progress percentages.

## Important boundary

This is a preparation and evidence-management system. It does **not** log in to, scrape, or submit an ITR to the Income Tax portal. The official portal/offline utility should be used for final validation and filing.

## 1. Create PostgreSQL database on macOS

Open Terminal:

```bash
psql postgres
```

Then run:

```sql
CREATE USER itr_user WITH PASSWORD 'choose-a-strong-password';
CREATE DATABASE itr_family OWNER itr_user;
\q
```

If `psql` is not on PATH (common with Postgres.app), add its bin directory to PATH or use the full path.

## 2. Open in VS Code

```bash
cd itr_family_workspace
code .
```

## 3. Create Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Configure

```bash
cp .env.example .env
```

Edit `.env` and replace `CHANGE_ME`.

## 5. Initialize tailored data

```bash
python -m itr_workspace.seed
```

This creates:

- Nilesh — NRI — AY 2026-27
- Avani — RNOR — AY 2026-27
- Tailored accounts, document requirements and filing tasks

The seed is idempotent; rerunning it will not duplicate the initial case.

## 6. Run

```bash
streamlit run app.py
```

Open the local address shown by Streamlit, normally `http://localhost:8501`.

## Recommended workflow

1. Dashboard → select taxpayer and assessment year.
2. Profile → verify PAN suffix, status and contact metadata.
3. Residency → enter India presence days and retain passport/travel evidence.
4. Documents → upload AIS, TIS, 26AS, bank statements, certificates, Zerodha reports, CAS and loan documents.
5. Income → enter gross amounts before TDS.
6. Tax credits → enter 26AS credits.
7. Reconciliation → compare records and resolve differences.
8. Property & loan → enter ownership, possession, interest and principal.
9. Review → clear blocking checks.
10. Export → generate a filing pack for CA/self-filing review.

## Data safety

- Uploaded documents are copied into `private_data/`.
- Do not commit `.env` or `private_data/`.
- Use FileVault on the Mac.
- Back up PostgreSQL with encryption:

```bash
pg_dump -Fc itr_family > itr_family.backup
```

- Back up `private_data/` with an encrypted backup.
- PAN is intentionally stored only as the last four characters in this starter.
- Never store the income-tax portal password, OTP, Aadhaar OTP or net-banking password.

## Starting a new year

Use the UI's **New assessment year** action. It copies reusable checklist structure but not amounts, completion states or uploaded documents.
