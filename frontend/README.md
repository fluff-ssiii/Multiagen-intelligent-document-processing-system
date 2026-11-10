# The Doxor — Frontend

React + Vite frontend for **The Doxor** (Intelligent Documents. Smarter Workflows.), built against the nine FastAPI endpoints in the requirements brief. No mock data: every number, table and status comes from the API.

## Run it
```bash
npm install
cp .env.example .env      # set VITE_API_BASE_URL (default http://localhost:8000)
npm run dev               # http://localhost:5173
npm run build             # production build in dist/
```

## Connect to FastAPI
1. Start the backend and open `http://localhost:8000/docs`.
2. Enable CORS for the dev origin:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])
```
3. **Verify the contract** (the brief did not include response schemas):
   - `src/config.js` → `UPLOAD_FIELDS`: multipart field names. `file` is a guess; `document_type`, `tags`, `description` are sent as extra form fields (FastAPI ignores undeclared ones). Set any to `null` to hide/stop sending it. `visibility` is `null` (hidden) until the backend enforces it.
   - `src/services/adapters.js`: the **only** place with response-field guesses (`document_id`/`id`, `filename`, `status`, results/validation keys, list wrapper keys). Tighten these to the real names from `/openapi.json`. Unknown shapes fall back to showing raw values rather than failing.
   - `statusKey()` maps backend status strings to display buckets; adjust if your enum differs.
   - `src/services/reviewApi.js`: approve/reject send **no body**. Add one there only if OpenAPI requires it.

## Structure
```
src/
  app/            App.jsx, routes.jsx
  components/     layout, common, documents, processing, results, validation, reviews
  pages/          Dashboard, Upload, Documents, DocumentDetail, Processing, Results, Validation, HumanReview, Analytics, DocumentPicker
  services/       apiClient.js (base URL, errors, multipart), documentApi, reviewApi, healthApi, adapters
  hooks/          useAsync (abort + polling), useDocuments, useApiHealth, useDebounce
  utils/  styles/ config.js
```

## Behaviour notes
- Routes: the suggested per-document routes plus `/processing`, `/results`, `/validation` (sidebar tabs) which ask you to pick a document first.
- Processing shows an indeterminate bar, never a fake percentage; stage states come only from backend status/stage fields. Polling (3s) stops at a terminal status or on leaving the page.
- Preview renders only if a document includes an absolute `file_url`/`url`; the contract has no file endpoint.
- Analytics shows operational counts with sample size and date range; accuracy metrics are intentionally absent (no ground truth or aggregate endpoint).
- No document or extracted data is stored in localStorage.
