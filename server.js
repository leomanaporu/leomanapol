// server.js - Tagpuan Unified Remote Administration Server
// -------------------------------------------------------------
const express = require('express');
const http = require('http');
const path = require('path');
const fs = require('fs');
const { Server } = require('socket.io');

const app = express();
const server = http.createServer(app);

// Enable Socket.io with open CORS so admin.html works both served or opened locally
const io = new Server(server, {
  cors: {
    origin: '*',
    methods: ['GET', 'POST']
  }
});

const PORT = process.env.PORT || 3000;
const DATA_DIR = path.join(__dirname, 'data');
const DB_FILE = path.join(DATA_DIR, 'requests.json');

// Ensure data directory exists
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// -------------------------------------------------------------
// Safe JSON Storage Engine (Avoids flat-file locking issues)
// -------------------------------------------------------------
let state = {
  requests: [],
  workers: {},
  stats: {
    totalRequests: 0,
    alertsCount: 0
  }
};

// Load existing records on startup
try {
  if (fs.existsSync(DB_FILE)) {
    const raw = fs.readFileSync(DB_FILE, 'utf-8');
    const parsed = JSON.parse(raw);
    state.requests = Array.isArray(parsed.requests) ? parsed.requests : [];
    state.stats = parsed.stats || state.stats;
    console.log(`[Storage] Loaded ${state.requests.length} historical records.`);
  }
} catch (err) {
  console.warn('[Storage] Notice: Starting with fresh state:', err.message);
}

// Atomic non-blocking save
let isSaving = false;
let pendingSave = false;
function saveState() {
  if (isSaving) {
    pendingSave = true;
    return;
  }
  isSaving = true;
  const tempPath = `${DB_FILE}.tmp`;
  const data = JSON.stringify(
    {
      updatedAt: new Date().toISOString(),
      stats: state.stats,
      requests: state.requests.slice(0, 500) // keep last 500 records
    },
    null,
    2
  );

  fs.writeFile(tempPath, data, 'utf-8', (err) => {
    isSaving = false;
    if (!err) {
      fs.rename(tempPath, DB_FILE, () => {});
    }
    if (pendingSave) {
      pendingSave = false;
      saveState();
    }
  });
}

// -------------------------------------------------------------
// Middleware & Static Asset Serving
// -------------------------------------------------------------
app.use(express.json({ limit: '2mb' }));
app.use(express.urlencoded({ extended: true }));

// CORS headers for REST endpoints
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

// Serve modern public directory first, then root as fallback
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.static(__dirname));

// Route shortcut for admin dashboard
app.get('/admin', (req, res) => {
  const publicAdmin = path.join(__dirname, 'public', 'admin.html');
  if (fs.existsSync(publicAdmin)) {
    return res.sendFile(publicAdmin);
  }
  res.sendFile(path.join(__dirname, 'admin.html'));
});

// -------------------------------------------------------------
// REST API Endpoints
// -------------------------------------------------------------

// Helper: Calculate live summary metrics
function getComputedStats() {
  const now = Date.now();
  const activeThreshold = 60 * 1000; // seen within 60s
  const workerList = Object.values(state.workers);
  const activeWorkers = workerList.filter(w => (now - w.lastSeen) < activeThreshold).length;
  const pendingUac = state.requests.filter(r => r.type === 'UAC_REQUEST' && r.status === 'PENDING').length;

  return {
    totalWorkers: workerList.length,
    activeWorkers,
    pendingUac,
    alertsCount: state.stats.alertsCount,
    totalRequests: state.stats.totalRequests
  };
}

// 1. Health check
app.get('/api/health', (req, res) => {
  res.json({
    status: 'online',
    service: 'Tagpuan Command Server',
    uptime: process.uptime(),
    timestamp: new Date().toISOString()
  });
});

// 2. Fetch Dashboard Statistics
app.get('/api/stats', (req, res) => {
  res.json(getComputedStats());
});

// 3. Fetch Recent Requests / Logs
app.get('/api/requests', (req, res) => {
  const limit = parseInt(req.query.limit, 10) || 100;
  res.json({
    count: state.requests.length,
    requests: state.requests.slice(0, limit)
  });
});

// 4. Fetch Registered Workers
app.get('/api/workers', (req, res) => {
  const now = Date.now();
  const workers = Object.values(state.workers).map(w => ({
    ...w,
    isOnline: (now - w.lastSeen) < 60000
  }));
  res.json(workers);
});

// 5. Ingestion Endpoint for Remote Python Workers (silent_worker.py)
app.post('/api/requests', (req, res) => {
  const body = req.body || {};
  const deviceId = (body.deviceId || body.device_id || 'UNKNOWN-NODE').trim();
  const requestType = (body.type || body.request_type || 'STATUS_UPDATE').toUpperCase();
  const status = (body.status || 'INFO').toUpperCase();
  const message = body.message || 'Worker event received';
  const metadata = body.metadata || body.details || {};

  const record = {
    id: `REQ-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
    deviceId,
    hostname: body.hostname || 'remote-host',
    os: body.os || 'Windows',
    type: requestType,
    status,
    message,
    metadata,
    timestamp: new Date().toISOString(),
    epoch: Date.now()
  };

  // Update in-memory state
  state.requests.unshift(record);
  if (state.requests.length > 500) state.requests.pop();
  state.stats.totalRequests += 1;
  if (status === 'ALERT' || status === 'ERROR') {
    state.stats.alertsCount += 1;
  }

  // Update worker registry
  state.workers[deviceId] = {
    deviceId,
    hostname: record.hostname,
    os: record.os,
    lastSeen: Date.now(),
    lastStatus: status,
    lastType: requestType
  };

  // Persist to disk asynchronously
  saveState();

  // Real-time broadcast to all connected Admin dashboards
  io.emit('new_request', record);
  io.emit('stats_update', getComputedStats());
  io.emit('log_stream', {
    level: status,
    timestamp: record.timestamp,
    source: deviceId,
    message: `[${requestType}] ${message}`
  });

  console.log(`[API] Event from ${deviceId} (${requestType}/${status}): ${message}`);
  return res.status(201).json({
    success: true,
    message: 'Event logged and broadcast successfully',
    id: record.id,
    timestamp: record.timestamp
  });
});

// 6. Admin Action on a Request (e.g. Approve/Acknowledge)
app.post('/api/requests/:id/action', (req, res) => {
  const { id } = req.params;
  const { action, resolution } = req.body;
  const item = state.requests.find(r => r.id === id);

  if (!item) {
    return res.status(404).json({ error: 'Request not found' });
  }

  item.status = (action || 'RESOLVED').toUpperCase();
  item.resolution = resolution || 'Processed by Administrator';
  item.resolvedAt = new Date().toISOString();

  saveState();
  io.emit('request_updated', item);
  io.emit('stats_update', getComputedStats());

  return res.json({ success: true, item });
});

// -------------------------------------------------------------
// Real-Time Socket.io Connection Management
// -------------------------------------------------------------
io.on('connection', (socket) => {
  console.log(`[WebSocket] Admin/Client connected: ${socket.id}`);

  // Send initial hydration payload to client
  socket.emit('init_state', {
    stats: getComputedStats(),
    recentRequests: state.requests.slice(0, 50),
    workers: Object.values(state.workers)
  });

  socket.on('admin_ping', () => {
    socket.emit('admin_pong', { time: Date.now() });
  });

  socket.on('disconnect', () => {
    console.log(`[WebSocket] Client disconnected: ${socket.id}`);
  });
});

// -------------------------------------------------------------
// Server Start
// -------------------------------------------------------------
server.listen(PORT, () => {
  console.log('====================================================');
  console.log(` TAGPUAN Remote Administrative Command Server`);
  console.log(` Dashboard URL:  http://localhost:${PORT}/admin`);
  console.log(` Ingestion API:  http://localhost:${PORT}/api/requests`);
  console.log(` Storage Path:   ${DB_FILE}`);
  console.log('====================================================');
});
