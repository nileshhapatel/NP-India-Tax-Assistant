# 🚀 Quick Start Guide - ITR Filing System

## ✅ System Status
- **Frontend**: Running on http://localhost:3000 ✓
- **Backend API**: Running on http://localhost:8000 ✓
- **Database**: PostgreSQL connected ✓
- **Status**: Ready to file tax returns

---

## 📋 Step-by-Step Filing Workflow

### Step 1: Access the Application
```
Open your browser and navigate to:
http://localhost:3000
```

### Step 2: Home Dashboard
You'll see:
- Welcome message
- 2 registered taxpayers (Nilesh & Avani)
- 4 core features
- 6-step getting started guide

### Step 3: Complete Your Profile
1. Click "Household Profile" or navigate to `/profile`
2. Enter personal details:
   - Name
   - PAN (last 4 digits)
   - Date of birth
   - Residential status (NRI/RNOR/ROR)
3. Click "Save Profile"

### Step 4: Fetch Required Documents
1. Click "Smart Document Fetcher" or navigate to `/documents`
2. Select your tax year (2026-27)
3. View required documents:
   - AIS (Annual Information Statement)
   - Form 26AS (TDS Summary)
   - Bank statements (for interest)
   - Zerodha reports (for dividend/capital gains)
   - Mutual fund CAS (capital appreciation)
   - Home loan certificate
4. Follow links to download from official sources

### Step 5: Upload Documents
1. Upload AIS PDF
   - System auto-extracts income, TDS
   - Stores in private_data/ folder
2. Upload Form 26AS
   - Auto-extracts TDS, tax credit
3. Upload other supporting docs
4. View extracted data

### Step 6: Enter Income & TDS
1. Navigate to Income entry section
2. Enter:
   - Salary (from salary certificate)
   - Interest income (from bank)
   - Dividend income (from broker)
   - Capital gains (from mutual fund CAS)
3. Enter TDS appearing in Form 26AS
4. System auto-calculates tax

### Step 7: View Reconciliation
1. Click "Reconciliation Dashboard"
2. See 3-way matching:
   - Source document amounts
   - AIS reported amounts
   - Your ITR entries
3. Review discrepancies:
   - GREEN: Perfect match ✓
   - YELLOW: Minor variance (timing)
   - ORANGE: Significant difference
   - RED: Critical mismatch

### Step 8: Review & Get AI Guidance
1. Navigate to "AI Tax Assistant" chat
2. Ask questions like:
   - "What deductions can I claim?"
   - "Should I use old or new regime?"
   - "How much tax will I pay?"
3. AI provides real-time guidance based on:
   - Your residency status
   - Actual income entered
   - Tax rules for 2026-27
   - Government latest circulars

### Step 9: Export & File
1. Navigate to Final Review page
2. View complete calculations:
   - Gross income: ₹X
   - Deductions: ₹Y
   - Taxable income: ₹Z
   - Tax liability: ₹T
3. Compare Old vs New regime
4. Choose export format:
   - **JSON**: Portal-compatible
   - **CSV**: Data backup
   - **XML**: For offline utility
5. Download exported file

### Step 10: File with Government
1. Go to income-tax.gov.in
2. Sign in to e-filing portal
3. Upload the exported JSON/XML
4. Choose signature method:
   - DSC (Digital Signature Certificate)
   - OTP (Mobile OTP)
   - Offline utility (sign locally)
5. Submit return
6. Save acknowledgment number

---

## 🎯 Quick Commands

### One-command setup and health check
```bash
./launch.sh
```

### Check system status
```bash
docker-compose ps
# Should show api and frontend both UP
```

### View API documentation
```
http://localhost:8000/docs
```

### Restart application
```bash
docker-compose restart
```

### View logs
```bash
docker-compose logs -f api
docker-compose logs -f frontend
```

### Stop application
```bash
docker-compose down
```

---

## 💡 Key Features by Taxpayer

### For Nilesh (NRI Status)
✓ Global income applicable  
✓ Foreign source income tracked  
✓ NRI-specific deduction restrictions  
✓ Form 26AS mandatory for reconciliation  
✓ Aadhaar OTP filing support  

### For Avani (RNOR Status)
✓ Indian income applicable  
✓ Optional: Global income inclusion  
✓ RNOR-specific rules enforced  
✓ Amendment capability within 1 year  
✓ Both DSC & OTP filing support  

---

## 📊 Tax Calculation Support

### Deductions Covered
- 80C: Life insurance, PPF, ELSS (₹1.5L limit)
- 80D: Health insurance (₹1L limit)
- 80E: Education loan interest (₹50K limit)
- 80G: Donations (50% of gross income)
- 80GG: Rent paid (₹60K limit)
- 24(b): Home loan interest (Unlimited)
- 80AC: NPS contribution (₹50K limit)

### Regime Comparison
- **Old Regime**: With deductions (max tax savings)
- **New Regime**: Standard deduction, no other deductions
- **Automatic recommendation** based on your profile

### Tax Optimization
AI suggests:
- Best deduction strategy
- Regime selection recommendation
- Tax-saving actions for next year
- Compliance alerts

---

## 🔒 Security & Privacy

✓ **Local Storage**: Documents in private_data/ (not cloud)  
✓ **Database**: Password-protected PostgreSQL  
✓ **Git**: .env and private_data/ excluded  
✓ **Encryption**: Ready for FileVault on Mac  
✓ **OTP Support**: Mobile verification for filing  

---

## ❓ Troubleshooting

### Application won't start
```bash
# Check Docker containers
docker-compose ps

# Restart
docker-compose down
docker-compose up -d
```

### Database connection error
```bash
# Verify PostgreSQL running
brew services list | grep postgres

# Check .env DATABASE_URL
cat .env | grep DATABASE_URL
```

### API not responding
```bash
# View API logs
docker-compose logs api

# Check port 8000
lsof -i :8000
```

### Frontend blank page
```bash
# View frontend logs
docker-compose logs frontend

# Restart frontend
docker-compose restart frontend
```

---

## 📞 Support

- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000
- **Database**: PostgreSQL on localhost:5432
- **Code**: All modular, well-commented

---

## ✅ Checklist Before Filing

- [ ] Profile completed (name, PAN, residency status)
- [ ] All documents uploaded (AIS, 26AS, bank statements)
- [ ] Income entered correctly
- [ ] TDS matched with Form 26AS
- [ ] Reconciliation reviewed (no RED flags)
- [ ] Deductions verified for eligibility
- [ ] Regime selected (old vs new)
- [ ] Form summary reviewed
- [ ] Calculations verified
- [ ] Export downloaded
- [ ] Ready to file on government portal

---

## 🎉 That's It!

Your ITR is ready. Export and file via income-tax.gov.in.

For amendments or corrections, use the Amendment Tracker.

**Happy Filing! 📋**
