// admin.js - Tagpuan Frontend Admin Dashboard Controller
// -------------------------------------------------------------

(function () {
  'use strict';

  // Determine socket connection target (handles localhost server or direct file:// launch)
  const isHttp = window.location.protocol.startsWith('http');
  const serverOrigin = isHttp ? window.location.origin : 'http://localhost:3000';

  let socket = null;
  let requestsCache = [];
  let autoScroll = true;

  // DOM Elements
  const connectionPill = document.getElementById('connectionPill');
  const connectionDot = document.getElementById('connectionDot');
  const connectionLabel = document.getElementById('connectionLabel');

  const metricActiveWorkers = document.getElementById('metricActiveWorkers');
  const metricTotalWorkers = document.getElementById('metricTotalWorkers');
  const metricPendingUac = document.getElementById('metricPendingUac');
  const metricAlerts = document.getElementById('metricAlerts');
  const metricTotalRequests = document.getElementById('metricTotalRequests');

  const requestsTableBody = document.getElementById('requestsTableBody');
  const searchInput = document.getElementById('searchInput');
  const typeFilter = document.getElementById('typeFilter');

  const terminalStream = document.getElementById('terminalStream');
  const autoScrollToggle = document.getElementById('autoScrollToggle');
  const clearLogsBtn = document.getElementById('clearLogsBtn');
  const refreshBtn = document.getElementById('refreshBtn');

  // -----------------------------------------------------------
  // Initialize Socket.io Connection
  // -----------------------------------------------------------
  function initSocket() {
    if (typeof io === 'undefined') {
      logToTerminal('ERROR', 'Socket.io client library not loaded. Is server.js running?', 'SYSTEM');
      updateConnectionStatus('error', 'CLIENT SCRIPT MISSING');
      return;
    }

    socket = io(serverOrigin, {
      reconnectionAttempts: Infinity,
      reconnectionDelay: 2000,
      timeout: 10000
    });

    socket.on('connect', () => {
      updateConnectionStatus('connected', 'BROKER CONNECTED');
      logToTerminal('INFO', `Handshake established with broker at ${serverOrigin}`, 'SOCKET');
    });

    socket.on('disconnect', () => {
      updateConnectionStatus('disconnected', 'DISCONNECTED');
      logToTerminal('WARN', 'Lost connection to broker. Retrying...', 'SOCKET');
    });

    socket.on('connect_error', () => {
      updateConnectionStatus('disconnected', 'RETRYING...');
    });

    // Hydration event on initial join
    socket.on('init_state', (data) => {
      if (data.stats) updateMetrics(data.stats);
      if (Array.isArray(data.recentRequests)) {
        requestsCache = data.recentRequests;
        renderTable();
      }
    });

    // Incoming real-time request event
    socket.on('new_request', (record) => {
      requestsCache.unshift(record);
      if (requestsCache.length > 300) requestsCache.pop();
      renderTable();
      playNotificationBeep(record.type);
    });

    // Live metrics update
    socket.on('stats_update', (stats) => {
      updateMetrics(stats);
    });

    // Stream log message
    socket.on('log_stream', (log) => {
      logToTerminal(log.level || 'INFO', log.message, log.source || 'WORKER');
    });

    // Request status updated by admin action
    socket.on('request_updated', (item) => {
      const idx = requestsCache.findIndex(r => r.id === item.id);
      if (idx !== -1) {
        requestsCache[idx] = item;
        renderTable();
      }
    });
  }

  // -----------------------------------------------------------
  // UI Helpers & Renderers
  // -----------------------------------------------------------
  function updateConnectionStatus(state, label) {
    connectionLabel.textContent = label;
    if (state === 'connected') {
      connectionPill.className = 'flex items-center space-x-2 px-3 py-1.5 rounded-full text-xs font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30';
      connectionDot.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-pulse';
    } else if (state === 'error' || state === 'disconnected') {
      connectionPill.className = 'flex items-center space-x-2 px-3 py-1.5 rounded-full text-xs font-mono font-medium bg-rose-500/10 text-rose-400 border border-rose-500/30';
      connectionDot.className = 'w-2 h-2 rounded-full bg-rose-400';
    } else {
      connectionPill.className = 'flex items-center space-x-2 px-3 py-1.5 rounded-full text-xs font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/30';
      connectionDot.className = 'w-2 h-2 rounded-full bg-amber-400 animate-pulse';
    }
  }

  function updateMetrics(stats) {
    metricActiveWorkers.textContent = stats.activeWorkers || 0;
    metricTotalWorkers.textContent = stats.totalWorkers || 0;
    metricPendingUac.textContent = stats.pendingUac || 0;
    metricAlerts.textContent = stats.alertsCount || 0;
    metricTotalRequests.textContent = stats.totalRequests || 0;
  }

  function getBadgeClass(type, status) {
    if (type === 'UAC_REQUEST' || status === 'PENDING') {
      return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
    }
    if (status === 'ALERT' || status === 'ERROR') {
      return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
    }
    if (status === 'APPROVED' || status === 'SUCCESS') {
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
    }
    return 'bg-slate-700/40 text-slate-300 border-slate-600/40';
  }

  function renderTable() {
    const query = (searchInput.value || '').toLowerCase().trim();
    const type = typeFilter.value;

    const filtered = requestsCache.filter(item => {
      const matchType = type === 'ALL' || item.type === type;
      const matchQuery = !query ||
        item.deviceId.toLowerCase().includes(query) ||
        (item.hostname && item.hostname.toLowerCase().includes(query)) ||
        item.type.toLowerCase().includes(query) ||
        (item.message && item.message.toLowerCase().includes(query));
      return matchType && matchQuery;
    });

    if (filtered.length === 0) {
      requestsTableBody.innerHTML = `
        <tr>
          <td colspan="6" class="py-8 text-center text-slate-500 font-mono text-xs">
            No matching requests found.
          </td>
        </tr>`;
      return;
    }

    requestsTableBody.innerHTML = filtered.map(item => {
      const time = new Date(item.timestamp).toLocaleTimeString();
      const date = new Date(item.timestamp).toLocaleDateString();
      const badgeClass = getBadgeClass(item.type, item.status);
      const isUac = item.type === 'UAC_REQUEST' && item.status === 'PENDING';

      return `
        <tr class="hover:bg-slate-800/40 transition-colors">
          <td class="py-3 px-4 font-mono text-slate-400 whitespace-nowrap">
            <div>${time}</div>
            <div class="text-[10px] text-slate-600">${date}</div>
          </td>
          <td class="py-3 px-4 font-mono font-medium text-slate-200">
            <div>${escapeHtml(item.deviceId)}</div>
            <div class="text-[10px] text-slate-500">${escapeHtml(item.hostname || 'remote')} &bull; ${escapeHtml(item.os || 'Windows')}</div>
          </td>
          <td class="py-3 px-4 font-mono">
            <span class="px-2 py-0.5 rounded text-[10px] font-semibold border ${badgeClass}">
              ${escapeHtml(item.type)}
            </span>
          </td>
          <td class="py-3 px-4 font-mono text-xs">
            <span class="font-semibold ${item.status === 'PENDING' ? 'text-amber-400' : 'text-slate-300'}">
              ${escapeHtml(item.status)}
            </span>
          </td>
          <td class="py-3 px-4 text-slate-300 max-w-md truncate" title="${escapeHtml(item.message)}">
            ${escapeHtml(item.message)}
          </td>
          <td class="py-3 px-4 text-right whitespace-nowrap font-mono">
            ${isUac ? `
              <button onclick="window.resolveRequest('${item.id}', 'APPROVED')" class="px-2 py-1 text-[11px] bg-emerald-600 hover:bg-emerald-500 text-white rounded mr-1 transition shadow-sm">
                Approve
              </button>
              <button onclick="window.resolveRequest('${item.id}', 'DENIED')" class="px-2 py-1 text-[11px] bg-rose-600/80 hover:bg-rose-500 text-white rounded transition">
                Deny
              </button>
            ` : `
              <button onclick="window.resolveRequest('${item.id}', 'ACKNOWLEDGED')" class="px-2 py-1 text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded transition">
                Acknowledge
              </button>
            `}
          </td>
        </tr>
      `;
    }).join('');
  }

  function logToTerminal(level, message, source) {
    const row = document.createElement('div');
    const time = new Date().toLocaleTimeString();

    let levelColor = 'text-slate-400';
    if (level === 'ERROR' || level === 'ALERT') levelColor = 'text-rose-400 font-bold';
    else if (level === 'WARN' || level === 'PENDING') levelColor = 'text-amber-400 font-bold';
    else if (level === 'SUCCESS' || level === 'APPROVED') levelColor = 'text-emerald-400 font-bold';

    row.innerHTML = `
      <span class="text-slate-600">[${time}]</span>
      <span class="text-slate-500">&lt;${escapeHtml(source)}&gt;</span>
      <span class="${levelColor}">[${escapeHtml(level)}]</span>
      <span class="text-slate-200">${escapeHtml(message)}</span>
    `;

    terminalStream.appendChild(row);

    // Keep terminal limited to last 200 lines
    while (terminalStream.children.length > 200) {
      terminalStream.removeChild(terminalStream.firstChild);
    }

    if (autoScroll) {
      terminalStream.scrollTop = terminalStream.scrollHeight;
    }
  }

  function playNotificationBeep(type) {
    // Subtle audio feedback on critical UAC event using Web Audio API
    if (type !== 'UAC_REQUEST') return;
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, audioCtx.currentTime);
      gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.25);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.25);
    } catch (_) {}
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // -----------------------------------------------------------
  // Global Actions & Listeners
  // -----------------------------------------------------------
  window.resolveRequest = function (id, action) {
    fetch(`${serverOrigin}/api/requests/${encodeURIComponent(id)}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action })
    })
      .then(res => res.json())
      .then(() => {
        logToTerminal('INFO', `Request ${id} marked as ${action}`, 'ADMIN');
      })
      .catch(err => {
        logToTerminal('ERROR', `Failed to update ${id}: ${err.message}`, 'ADMIN');
      });
  };

  searchInput.addEventListener('input', renderTable);
  typeFilter.addEventListener('change', renderTable);

  autoScrollToggle.addEventListener('change', (e) => {
    autoScroll = e.target.checked;
  });

  clearLogsBtn.addEventListener('click', () => {
    terminalStream.innerHTML = '<div class="text-slate-500">[CONSOLE] Terminal logs cleared by user.</div>';
  });

  refreshBtn.addEventListener('click', () => {
    fetch(`${serverOrigin}/api/requests?limit=100`)
      .then(r => r.json())
      .then(data => {
        if (data.requests) {
          requestsCache = data.requests;
          renderTable();
          logToTerminal('INFO', 'Synchronized ledger from server API.', 'REST');
        }
      })
      .catch(err => logToTerminal('ERROR', `Refresh failed: ${err.message}`, 'REST'));
  });

  // Start initialization
  initSocket();

})();
