import { useState, useEffect } from 'react';
import useSWR from 'swr';

const fetcher = (url) => fetch(url).then((res) => res.json());

// Required documents with links to fetch from official sources
const REQUIRED_DOCS = {
  'AIS': {
    title: 'Annual Information Statement (AIS)',
    institution: 'Income Tax Department',
    link: 'https://www.incometax.gov.in/iec/foportal/downloads',
    description: 'Annual information of financial transactions reported to ITD by banks and financial institutions',
    how_to_get: [
      '1. Visit the Income Tax e-filing portal',
      '2. Login with your credentials',
      '3. Navigate to Documents > AIS',
      '4. Download PDF for the relevant financial year',
    ],
    formats: 'PDF',
  },
  '26AS': {
    title: 'Form 26AS (Tax Credit Statement)',
    institution: 'Income Tax Department',
    link: 'https://www.incometax.gov.in/iec/foportal/downloads',
    description: 'Statement showing all tax credits, TDS, TCS, and advance tax paid',
    how_to_get: [
      '1. Login to Income Tax e-filing portal',
      '2. Go to Documents > Form 26AS',
      '3. Select the relevant assessment year',
      '4. Download and save the PDF',
    ],
    formats: 'PDF',
  },
  'BANK_STATEMENT': {
    title: 'Bank Statements',
    institution: 'Your Bank',
    link: 'https://www.hdfcbank.com/personal',
    description: 'Statements showing all deposits, withdrawals, interest credited, and TDS',
    how_to_get: [
      '1. Login to your net banking portal',
      '2. Navigate to Statements/Downloads',
      '3. Select date range (full financial year)',
      '4. Download in PDF or Excel format',
    ],
    formats: 'PDF, Excel',
  },
  'INTEREST_CERT': {
    title: 'Bank Interest Certificate',
    institution: 'Your Bank',
    link: 'https://www.hdfcbank.com/personal',
    description: 'Certificate showing interest earned on savings accounts (Form 26AS may also cover)',
    how_to_get: [
      '1. Contact your bank or use net banking',
      '2. Request interest certificate for the FY',
      '3. Bank provides Form 16A or custom certificate',
      '4. Save as PDF',
    ],
    formats: 'PDF',
  },
  'SALARY_SLIP': {
    title: 'Salary Slips (Last 3 months)',
    institution: 'Your Employer',
    link: '',
    description: 'Most recent 3 salary slips showing gross, deductions, TDS, net pay',
    how_to_get: [
      '1. Request from HR department',
      '2. Usually available on employee portal',
      '3. Download in PDF',
      '4. Ensure slips are digitally signed by employer',
    ],
    formats: 'PDF',
  },
  'FORM16': {
    title: 'Form 16 / 16A (TDS Certificate)',
    institution: 'Your Employer',
    link: 'https://www.incometax.gov.in/',
    description: 'Annual TDS certificate showing salary and tax deducted by employer',
    how_to_get: [
      '1. Request from HR/Finance after March 31',
      '2. Usually mailed in April or available on portal',
      '3. Contains Part A (deductor info) and Part B (employee details)',
      '4. Use for reconciliation with AIS/26AS',
    ],
    formats: 'PDF',
  },
  'ZERODHA_HOLDINGS': {
    title: 'Zerodha Holdings Report',
    institution: 'Zerodha',
    link: 'https://console.zerodha.com',
    description: 'Year-end holdings statement showing equity and mutual fund positions',
    how_to_get: [
      '1. Login to Zerodha Console',
      '2. Navigate to Portfolio > Holdings',
      '3. Export as CSV or PDF',
      '4. Useful for reconciling capital gains',
    ],
    formats: 'CSV, PDF',
  },
  'ZERODHA_TAXPL': {
    title: 'Zerodha Tax P&L Report',
    institution: 'Zerodha',
    link: 'https://console.zerodha.com/reports',
    description: 'Profit & Loss statement for equity and derivatives trading',
    how_to_get: [
      '1. Go to Zerodha Console > Reports > Tax P&L',
      '2. Select financial year',
      '3. Export as CSV or PDF',
      '4. Shows realized gains/losses for ITR Section 112/111',
    ],
    formats: 'CSV, PDF',
  },
  'ZERODHA_DIVIDEND': {
    title: 'Zerodha Dividend Report',
    institution: 'Zerodha',
    link: 'https://console.zerodha.com/reports',
    description: 'All dividends received on equity shares and mutual funds',
    how_to_get: [
      '1. Go to Zerodha Console > Reports > Dividends',
      '2. Select the financial year',
      '3. Download CSV showing dividend name, date, amount, TDS',
      '4. Reconcile with AIS and 26AS',
    ],
    formats: 'CSV, PDF',
  },
  'ZERODHA_LEDGER': {
    title: 'Zerodha Ledger Report',
    institution: 'Zerodha',
    link: 'https://console.zerodha.com/reports',
    description: 'Complete cash and margin ledger showing all cash flows',
    how_to_get: [
      '1. Go to Zerodha Console > Reports > Ledger',
      '2. Select full financial year date range',
      '3. Export as CSV',
      '4. Helps verify total cash deposited/withdrawn',
    ],
    formats: 'CSV',
  },
  'MF_CAS': {
    title: 'Mutual Fund CAS (Consolidated Account Statement)',
    institution: 'CAMS or Kuvera',
    link: 'https://www.camsonline.com',
    description: 'Year-end CAS showing all mutual fund holdings, purchases, sales, and NAV',
    how_to_get: [
      '1. Visit CAMS portal or use Kuvera',
      '2. Login with PAN and password',
      '3. Download year-end CAS (usually by Jan 15)',
      '4. Shows cost basis for capital gains calculation',
    ],
    formats: 'PDF',
  },
  'MF_REDEMPTION': {
    title: 'Mutual Fund Redemption/Switch Confirmations',
    institution: 'Fund House or CAMS',
    link: 'https://www.camsonline.com',
    description: 'Confirmations for redemptions and switches showing NAV, units, and amount',
    how_to_get: [
      '1. Check email for confirmations after redemption',
      '2. Also available in CAMS/Kuvera transaction history',
      '3. Download PDFs of all redemptions in the FY',
      '4. Need for calculating capital gains (short/long term)',
    ],
    formats: 'PDF',
  },
  'HOME_LOAN_CERT': {
    title: 'Home Loan Interest & Principal Certificate',
    institution: 'Your Bank/NBFC',
    link: '',
    description: 'Certificate from lender showing interest paid, principal paid, pre-construction interest',
    how_to_get: [
      '1. Request from your bank/lender (usually auto-mailed in Jan-Feb)',
      '2. May be labeled "Annual Interest Certificate"',
      '3. Shows breakup: pre-construction, construction, post-completion',
      '4. Required for Section 24 and 80C deductions',
    ],
    formats: 'PDF',
  },
  'PROPERTY_DOCS': {
    title: 'Property Ownership Documents',
    institution: 'Your Records',
    link: '',
    description: 'Registration deed, latest property tax receipt, or utility bill',
    how_to_get: [
      '1. Retrieve from your file or registry office',
      '2. Registration deed has property details and dates',
      '3. Property tax receipt confirms ownership',
      '4. Needed to support possession date and ownership %',
    ],
    formats: 'PDF',
  },
  'INVESTMENT_PROOF': {
    title: 'Investment Proof (PPF, ELSS, NSC, etc.)',
    institution: 'Your Bank/Fund House',
    link: '',
    description: 'Receipts, account statements, and confirmations for 80C deductions',
    how_to_get: [
      '1. Collect receipts at time of investment',
      '2. For PPF: get statement from bank',
      '3. For ELSS/MF: get confirmations from CAMS',
      '4. For Life Insurance: get policy statement',
    ],
    formats: 'PDF',
  },
};

export default function DocumentsPage() {
  const [caseId, setCaseId] = useState(1);
  const [docs, setDocs] = useState([]);
  const [uploadStatus, setUploadStatus] = useState({});
  const [activeFilter, setActiveFilter] = useState('all');

  const { data: casesData } = useSWR(caseId ? `/api/cases/${caseId}` : null, fetcher);
  const { data: requiredData } = useSWR(caseId ? `/api/cases/${caseId}/documents/required` : null, fetcher);

  useEffect(() => {
    if (requiredData?.documents) {
      setDocs(requiredData.documents);
    }
  }, [requiredData]);

  const handleUpload = async (e, code) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('code', code);

    setUploadStatus((prev) => ({ ...prev, [code]: 'uploading' }));
    try {
      const res = await fetch(`/api/cases/${caseId}/documents/upload`, {
        method: 'POST',
        body: formData,
      });
      const result = await res.json();
      if (res.ok) {
        setUploadStatus((prev) => ({ ...prev, [code]: 'success' }));
        setTimeout(() => {
          setUploadStatus((prev) => ({ ...prev, [code]: null }));
        }, 2000);
      } else {
        setUploadStatus((prev) => ({ ...prev, [code]: 'error' }));
      }
    } catch (err) {
      setUploadStatus((prev) => ({ ...prev, [code]: 'error' }));
    }
  };

  const filteredDocs = activeFilter === 'all'
    ? Object.entries(REQUIRED_DOCS)
    : activeFilter === 'uploaded'
    ? Object.entries(REQUIRED_DOCS).filter(([code]) => docs.some(d => d.code === code && d.status === 'Uploaded'))
    : Object.entries(REQUIRED_DOCS).filter(([code]) => !docs.some(d => d.code === code && d.status === 'Uploaded'));

  return (
    <div style={{ padding: '20px', fontFamily: 'system-ui' }}>
      <h1>📄 Document Fetcher & Upload</h1>
      
      <div style={{ marginBottom: '20px', padding: '10px', backgroundColor: '#f0f8ff', borderRadius: '5px' }}>
        <p><strong>Purpose:</strong> Fetch required documents from official sources and upload to your case.</p>
        <p><strong>Privacy:</strong> Documents are stored locally in <code>private_data/case_{caseId}</code> — not shared with anyone.</p>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label>
          Select Case:
          <select value={caseId} onChange={(e) => setCaseId(parseInt(e.target.value))} style={{ marginLeft: '10px', padding: '5px' }}>
            <option value={1}>Nilesh (NRI) — AY 2026-27</option>
            <option value={2}>Avani (RNOR) — AY 2026-27</option>
          </select>
        </label>
      </div>

      <div style={{ marginBottom: '15px' }}>
        {['all', 'pending', 'uploaded'].map((filter) => (
          <button
            key={filter}
            onClick={() => setActiveFilter(filter)}
            style={{
              marginRight: '10px',
              padding: '8px 15px',
              backgroundColor: activeFilter === filter ? '#007bff' : '#e9ecef',
              color: activeFilter === filter ? 'white' : 'black',
              border: 'none',
              borderRadius: '5px',
              cursor: 'pointer',
            }}
          >
            {filter === 'all' ? '📋 All' : filter === 'pending' ? '⏳ Pending' : '✅ Uploaded'}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '15px' }}>
        {filteredDocs.map(([code, doc]) => {
          const isUploaded = docs.some(d => d.code === code && d.status === 'Uploaded');
          return (
            <div key={code} style={{
              border: '1px solid #ddd',
              borderRadius: '8px',
              padding: '15px',
              backgroundColor: isUploaded ? '#f0f9ff' : '#fff',
            }}>
              <h3 style={{ margin: '0 0 10px 0' }}>{doc.title}</h3>
              <p style={{ margin: '5px 0', fontSize: '0.9em', color: '#666' }}>
                <strong>From:</strong> {doc.institution}
              </p>
              <p style={{ margin: '5px 0', fontSize: '0.9em' }}>{doc.description}</p>

              <div style={{ marginTop: '10px', padding: '10px', backgroundColor: '#f8f9fa', borderRadius: '5px' }}>
                <strong style={{ display: 'block', marginBottom: '8px' }}>📥 How to get:</strong>
                <ul style={{ margin: '0', paddingLeft: '20px', fontSize: '0.85em' }}>
                  {doc.how_to_get.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ul>
              </div>

              <div style={{ marginTop: '10px', display: 'flex', gap: '10px', alignItems: 'center' }}>
                {doc.link && (
                  <a href={doc.link} target="_blank" rel="noopener noreferrer" style={{
                    padding: '8px 12px',
                    backgroundColor: '#28a745',
                    color: 'white',
                    textDecoration: 'none',
                    borderRadius: '5px',
                    fontSize: '0.9em',
                  }}>
                    🔗 Open Portal
                  </a>
                )}
                <label style={{
                  padding: '8px 12px',
                  backgroundColor: isUploaded ? '#6c757d' : '#007bff',
                  color: 'white',
                  cursor: 'pointer',
                  borderRadius: '5px',
                  fontSize: '0.9em',
                }}>
                  {isUploaded ? '✅ Uploaded' : '📤 Upload'}
                  <input
                    type="file"
                    onChange={(e) => handleUpload(e, code)}
                    style={{ display: 'none' }}
                    disabled={isUploaded}
                  />
                </label>
                {uploadStatus[code] === 'uploading' && <span>⏳ Uploading...</span>}
                {uploadStatus[code] === 'success' && <span style={{ color: 'green' }}>✅ Success!</span>}
                {uploadStatus[code] === 'error' && <span style={{ color: 'red' }}>❌ Error</span>}
              </div>

              <p style={{ margin: '10px 0 0 0', fontSize: '0.85em', color: '#999' }}>
                Format: {doc.formats}
              </p>
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: '30px', padding: '15px', backgroundColor: '#fff3cd', borderRadius: '5px' }}>
        <h3>💡 Tips</h3>
        <ul>
          <li>Download <strong>all documents</strong> from the official government portal or your bank's net banking.</li>
          <li>Save as <strong>PDF</strong> for consistency; ensure file quality is readable.</li>
          <li>The platform will automatically parse and extract key information for reconciliation.</li>
          <li>Always verify the period — most documents should be for FY 2025–26 (Apr 1 - Mar 31).</li>
        </ul>
      </div>
    </div>
  );
}
