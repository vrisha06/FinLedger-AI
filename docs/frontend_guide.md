# FinLedger-AI — Frontend User & Developer Guide

## 1. Overview
The FinLedger-AI web application is a high-integrity, responsive fintech interface built using **React 19**, **TypeScript** (strict mode), **Vite**, and **Tailwind CSS**. It communicates directly with the real FastAPI backend over a typed HTTP client with strict role-based access control (RBAC), double-entry ledger transparency, and client-side idempotency tracking.

---

## 2. Prerequisites & Setup

### Prerequisites
- Node.js 20+ (Node 24.15.0 verified)
- npm 10+ (npm 11.12.1 verified)
- Running FinLedger-AI FastAPI backend (default: `http://localhost:8000`)

### Installation
Navigate to the `frontend` directory and install dependencies:
```powershell
cd frontend
npm install
```

### Environment Configuration
Copy `.env.example` to `.env`:
```powershell
cp .env.example .env
```
Inside `frontend/.env`:
```env
# FinLedger-AI API Gateway
VITE_API_BASE_URL=http://localhost:8000
```
> [!IMPORTANT]
> Never place PostgreSQL credentials, JWT signing keys, or server secrets in `frontend/.env`. Vite exposes variables prefixed with `VITE_` to client-side bundles.

---

## 3. Running & Testing

### Start Local Development Server
```powershell
cd frontend
npm run dev
```
The application will be accessible at: `http://localhost:5173`.

### Run Type Checking & Linter
```powershell
cd frontend
npm run lint
```
Executes `tsc -b` in strict mode.

### Run Automated Component & Unit Tests
```powershell
cd frontend
npm test
```
Executes Vitest with jsdom across all frontend test suites.

### Build for Production
```powershell
cd frontend
npm run build
```
Generates optimized static assets in `frontend/dist/`.

---

## 4. Application Architecture & Portals

### Authenticated Application Layout
- **Top Navbar**: Displays brand, current user legal name / email, active role badge (`CUSTOMER`, `STAFF`, `ADMIN`), and logout control.
- **Sidebar Navigation**: Dynamically renders links based on the authenticated user's role.
- **Protected Routes**: Redirects unauthenticated traffic to `/login` and guards role boundaries (`/unauthorized`).

---

### Customer Portal (`CUSTOMER` Role)

1. **Overview Dashboard** (`/dashboard`):
   - **Net Worth**: Total liquid savings + active investment valuations.
   - **Quick Actions**: "Deposit Funds" and "New Transfer".
   - **Active Accounts**: Real-time cached balances and account types.
   - **Recent Ledger Postings**: Live immutable double-entry ledger legs (credit/debit).
   - **Asset Allocation**: Category breakdown by product type.

2. **Accounts & Ledger** (`/accounts`):
   - Account selector cards showing account numbers, cached balances, and optimistic concurrency version numbers (`v1`).
   - Detailed ledger drilldown table with pagination showing sequence numbers, credit/debit legs, transaction UUIDs, and timestamps.
   - Opening funds deposit modal.

3. **Money Transfers** (`/transfers`):
   - **Atomic Transfer Wizard**:
     1. Select eligible source funding account.
     2. Input recipient destination account UUID.
     3. Enter amount (strictly positive, up to 2 decimal places, denominated in INR).
     4. Preview & Confirmation step showing source, destination, amount, and client-generated `Idempotency-Key` (UUIDv4).
     5. On transient network error, retry button preserves the **same** idempotency key to prevent double spending.
   - **Transaction Receipt Verification**:
     - Query and verify any transfer by UUID (`GET /api/v1/transfers/{id}`).

4. **Financial Products Catalogue** (`/products`):
   - Categorized catalogue: Fixed Deposits, Recurring Deposits, Mutual Funds, Treasury Bills.
   - Details: Annual yield rate (% p.a.), minimum subscription amount, term in months.
   - "Invest Now" modal with client-side idempotency UUIDv4 generation and balance validation.

5. **Portfolio & Holdings** (`/portfolio`):
   - Portfolio summary: total invested principal, current portfolio valuation, and nominal accrued yield.
   - Holdings register: Position reference, product code, invested amount, nominal daily yield, start date, maturity date, and status.

---

### Staff & Risk Operations Portal (`STAFF` & `ADMIN` Roles)

1. **Risk Dashboard** (`/staff`):
   - 14-day total transfer and investment volumes.
   - Pending unreviewed fraud alerts counter.
   - System reconciliation status badge (asserting zero global delta).

2. **Advisory AI Fraud Triage Queue** (`/staff/fraud`):
   - List advisory alerts scored by Random Forest and heuristic transaction rules.
   - Filter by review status (`PENDING`, `CLEARED`, `CONFIRMED_FRAUD`, `ESCALATED`) and risk severity (`HIGH_RISK`, `MEDIUM_RISK`, `LOW_RISK`).
   - **Forensic Investigation Drawer**:
     - Risk score percentage and model decision.
     - Rule flags triggered (`AMOUNT_THRESHOLD_50K`, `RAPID_BURST`, `OFF_HOURS`, etc.).
     - Human-readable forensic explanation.
     - Full feature vector JSON inspector.
     - Staff review decision form with **mandatory review notes** (`PATCH /api/v1/fraud/alerts/{id}/review`).

3. **System Accounts Explorer** (`/staff/accounts`):
   - Universal browser across all accounts (Customer Savings, Investments, and Internal Clearing).
   - Filter by customer UUID.
   - Inspect posted double-entry ledger legs for any account.

4. **Append-Only Audit Trail** (`/staff/audit`):
   - Chronological log of audit events (`AUTH_LOGIN_SUCCESS`, `TRANSFER_POSTED`, `INVESTMENT_PURCHASE_FAILED`, etc.).
   - Forensic client metadata: actor user ID, client IP address, user agent.
   - Interactive JSON metadata viewer.

5. **Ledger Reconciliation Audit** (`/staff/reconciliation`):
   - Real-time double-entry ledger reconciliation runner (`GET /api/v1/audit/reconciliation`).
   - Asserts that every account's cached balance matches the sum of its posted ledger entries: $\text{cached\_balance} == \sum \text{credits} - \sum \text{debits}$.
   - Asserts closed-ledger conservation: $\sum \text{Customer Liabilities} + \text{System Clearing Balance} == \text{INR 0.00}$.

6. **System Reporting & Analytics** (`/staff/reports`):
   - 14-day daily transactional volume breakdown table.
   - Customer account balance distribution tiers.
   - Product catalogue performance and total invested volume per product.
   - "Add Financial Product" modal for creating new products in the catalogue.

---

## 5. Security & Invariant Adherence

1. **Denomination**: Exclusively **INR** (`₹`). Amounts formatted with exact two decimal places (`₹20,000.00`). No floating-point roundoff artifacts.
2. **Idempotency**: Client generates a `UUIDv4` idempotency key per transaction intent and passes it via the `Idempotency-Key` HTTP header. Retries reuse the same key; new transactions generate a fresh key.
3. **Advisory AI**: AI models and rules never autonomously freeze accounts, alter balances, or reverse transfers. All review transitions strictly adhere to canonical enums: `PENDING`, `CLEARED`, `CONFIRMED_FRAUD`, `ESCALATED`.
4. **Authoritative Backend**: The UI does not simulate financial success. Receipts and balances are only rendered once confirmed by the server response.
