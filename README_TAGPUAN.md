# TAGPUAN: Unified Remote Administrative Architecture

**Tagpuan** is a remote administrative command broker and telemetry hub designed to collect, review, and acknowledge remote worker status reports and UAC elevation requests via high-performance REST APIs and real-time WebSockets.

---

## 1. Reorganized Directory Layout

```text
Tagpuan/
├── public/                       # Static Frontend Assets
│   ├── admin.html               # Tailwind CSS Modern Admin Console
│   ├── css/                     # Custom stylesheet overrides (if needed)
│   └── js/
│       └── admin.js             # Real-time WebSocket & REST dashboard controller
│
├── server/                      # Server-side Business Logic
│   └── (modular routes, storage engine)
│
├── client/                      # Client-side Python Workers
│   ├── silent_worker.py         # Modern Python worker communicating via requests
│   └── consent_handler.py       # User elevation and consent verification
│
├── data/                        # Persistent Storage
│   └── requests.json            # Non-blocking atomic JSON ledger (no flat-file locks)
│
├── server.js                    # Express + Socket.io Server Entry Point
├── package.json                 # Node.js dependencies
└── setup_skair.bat              # One-click Windows setup / shortcut generator
```

---

## 2. API Reference (`/api`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Broker health check, uptime, and service status |
| `GET` | `/api/stats` | Real-time computed dashboard metrics |
| `GET` | `/api/requests` | Fetch recent ledger requests (supports `?limit=100`) |
| `GET` | `/api/workers` | List registered nodes and online/offline states |
| `POST` | `/api/requests` | Ingest worker events, heartbeats, and UAC elevation notices |
| `POST` | `/api/requests/:id/action` | Admin actions (Approve, Deny, Acknowledge) |

---

## 3. How to Run & Test

### Step 1: Start the Node.js Server
```powershell
node server.js
```
The server will boot on port `3000`:
- **Admin Dashboard:** `http://localhost:3000/admin`
- **Ingestion Endpoint:** `http://localhost:3000/api/requests`

### Step 2: Run a Remote Python Worker
```powershell
python client/silent_worker.py
```
*(Requires `.authorized` consent file in directory to begin transmission)*

### Step 3: Open the Dashboard
Visit `http://localhost:3000/admin` (or double-click `admin.html`). You will see:
- Real-time connection badge
- Real-time telemetry cards updating dynamically
- Incoming UAC requests with one-click **Approve** / **Deny** buttons
- A live streaming log terminal component with auto-scroll and filtering
