# Frontend-Backend API Integration

## Overview
All frontend pages (Next.js React components) have been updated to use a centralized API client that correctly routes requests through the backend API service running on port 8000, preventing localhost:3000 routing errors.

## Architecture

### API Client (`frontend/lib/api.js`)
- **Purpose**: Centralized SWR fetcher for all API calls
- **Key Features**:
  - Uses `NEXT_PUBLIC_API_URL` environment variable
  - Falls back to `http://localhost:8000` in development
  - Works with both relative (`/api/...`) and absolute URLs
  - Compatible with SWR data fetching hooks

```javascript
// Example usage in components
import { fetcher } from '../lib/api';
import useSWR from 'swr';

const { data, error, isLoading } = useSWR(
  apiUrl('/api/household/members'),  // Full URL
  fetcher
);
```

### Updated Pages (All 9 pages)
1. **profile.js** - Display and edit household member information
2. **documents.js** - Upload and track tax documents
3. **income.js** - Enter and manage income sources
4. **reconciliation.js** - View 3-way reconciliation status
5. **calculations.js** - Display tax calculations
6. **export.js** - Export data in JSON/CSV/XML formats
7. **chat.js** - AI tax assistant interface
8. **review.js** - Final review before filing
9. **index.js** - Home/landing page

## Environment Configuration

### Docker Compose (`docker-compose.yml`)
```yaml
frontend:
  environment:
    NEXT_PUBLIC_API_URL: http://localhost:8000
```

### Next.js Config (`frontend/next.config.js`)
Includes API rewrites for development mode to properly route `/api/*` requests.

## API Endpoints

### Household Management
- `GET /api/household/members` - Get all taxpayers
- `GET /api/cases/{case_id}` - Get case details

### Documents
- `GET /api/documents/case/{case_id}` - List documents
- `POST /api/documents/upload` - Upload document
- `DELETE /api/documents/{doc_id}` - Delete document

### Income
- `GET /api/cases/{case_id}/income` - List income entries
- `POST /api/cases/{case_id}/income` - Add income entry
- `DELETE /api/cases/{case_id}/income/{income_id}` - Delete entry

### Tax Calculations
- `GET /api/calculations/case/{case_id}/summary` - Get calculation summary

### Reconciliation
- `GET /api/reconciliation/case/{case_id}` - Get reconciliation status

### Reports
- `GET /api/cases/{case_id}/reports/calculation` - Calculation report
- `GET /api/cases/{case_id}/reports/form-summary` - Form summary report

### Portal Integration (Phase 4)
- `GET /api/portal/export` - Export data (JSON/CSV/XML)
- `POST /api/portal/submit/dsc` - DSC-signed submission
- `POST /api/portal/submit/otp` - OTP verification
- `POST /api/portal/submit/offline` - Offline utility import
- `GET /api/portal/amendments` - Amendment history
- `POST /api/portal/amendments` - Track amendments
- `GET /api/portal/status` - Filing status

## Testing & Validation

### Integration Test Results
```
=== Testing All Pages ===
✓ / (200)                    - Home page
✓ /documents (200)           - Documents page
✓ /profile (200)             - Profile page
✓ /income (200)              - Income entry page
✓ /reconciliation (200)      - Reconciliation page
✓ /calculations (200)        - Calculations page
✓ /export (200)              - Export page
✓ /chat (200)                - AI Chat page
✓ /review (200)              - Final Review page
```

### Backend API Verification
```
✓ /api/household/members          - Returns 2 taxpayers (Nilesh & Avani)
✓ /api/cases/1                    - Nilesh's case (NRI, AY 2026-27)
✓ /api/cases/2                    - Avani's case (RNOR, AY 2026-27)
✓ /api/documents/case/1           - Document tracking
✓ /api/reconciliation/case/1      - Reconciliation status
✓ /api/calculations/case/1/summary - Tax calculations
```

## Data Flow

### Workflow Example: Loading Profile
1. Frontend: User navigates to `/profile`
2. React: Component mounts, calls `useSWR(apiUrl('/api/household/members'), fetcher)`
3. Fetcher: Resolves to `http://localhost:8000/api/household/members`
4. Backend: API responds with JSON containing Nilesh & Avani details
5. Component: Updates state, renders UI with data

### Error Handling
- **Network Error**: Shows AlertCircle icon + error message
- **Loading**: Shows Loader2 spinner while fetching
- **Success**: Displays data with confirmation messages

## Container Services

### Frontend (port 3000)
- Next.js development server
- Hot module reloading enabled
- Serves all 9 pages at `/` and `/pages/*`

### Backend (port 8000)
- FastAPI + Python 3.11
- PostgreSQL connection via `host.docker.internal:5432`
- All 22+ REST endpoints documented in `/docs`

### Database (PostgreSQL)
- User: `India_ITR_User`
- Database: `India_ITR_Family`
- Contains: Nilesh & Avani's tax records, documents, calculations

## Deployment Notes

### Development (Docker)
- `NEXT_PUBLIC_API_URL=http://localhost:8000`
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Use `docker-compose up` to run all services

### Production
- Update `NEXT_PUBLIC_API_URL` to production backend URL
- Ensure CORS headers allow frontend domain
- Use environment-specific `.env` files
- Consider using nginx reverse proxy

## Key Commits
- `902474e` - Update all frontend pages to use centralized API client
- `4edd737` - Clean up temporary test files
- `a4d4b93` - Fix income page JSX parsing error

## Future Enhancements
- Add loading skeletons for better UX
- Implement optimistic updates (mutate before API call)
- Add request/response interceptors for auth tokens
- Implement error retry logic with exponential backoff
- Add TypeScript types for API responses
- Add API response caching strategies

## CORS Configuration

### Problem
Frontend running on `http://localhost:3000` could not access backend API on `http://localhost:8000` due to browser's Cross-Origin Resource Sharing (CORS) policy:

```
Access to fetch at 'http://localhost:8000/api/...' from origin 'http://localhost:3000'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present.
```

### Solution
Added FastAPI CORS middleware to allow frontend requests:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost',
        'http://127.0.0.1',
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
```

### Result
All API requests from frontend now include proper `Access-Control-Allow-Origin` headers:

```
access-control-allow-origin: http://localhost:3000
access-control-allow-credentials: true
```

## Production Deployment

### CORS for Production
Update CORS origins for production domain:

```python
allow_origins=[
    'https://yourdomain.com',
    'https://www.yourdomain.com',
]
```

### Sensitive Headers
For production, restrict headers to only necessary ones:

```python
allow_headers=['Content-Type', 'Authorization'],
```

### Security Best Practices
1. Never use `allow_origins=['*']` in production with credentials
2. Explicitly list all allowed origins
3. Use HTTPS for all production traffic
4. Consider using environment variables for origin configuration

