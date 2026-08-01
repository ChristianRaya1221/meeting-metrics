
// ══════════════════════════════════════════
//  TYPEWRITER — status text for loader
// ══════════════════════════════════════════
const LOADER_MESSAGES = [
  'Authenticating',
  'Reading sheets',
  'Normalizing data',
  'Rendering charts',
];

let _typewriterInterval = null;
let _twIndex = 0;

function startTypewriter() {
  stopTypewriter();
  _twIndex = 0;
  typeMessage(LOADER_MESSAGES[0]);
}

function stopTypewriter() {
  if (_typewriterInterval) {
    clearTimeout(_typewriterInterval);
    _typewriterInterval = null;
  }
}

function typeMessage(msg) {
  const el = document.getElementById('loader-typewriter');
  if (!el) return;
  let i = 0;
  el.innerHTML = '<span class="tw-cursor">▍</span>';

  const typeStep = () => {
    if (i <= msg.length) {
      el.innerHTML = msg.slice(0, i) + '<span class="tw-cursor">▍</span>';
      i++;
      _typewriterInterval = setTimeout(typeStep, 30);  // fast typing
    } else {
      _typewriterInterval = setTimeout(eraseStep, 1200);  // hold before erase
    }
  };

  const eraseStep = () => {
    if (i > 0) {
      i--;
      el.innerHTML = msg.slice(0, i) + '<span class="tw-cursor">▍</span>';
      _typewriterInterval = setTimeout(eraseStep, 20);  // faster erase
    } else {
      _twIndex = (_twIndex + 1) % LOADER_MESSAGES.length;
      _typewriterInterval = setTimeout(() => typeMessage(LOADER_MESSAGES[_twIndex]), 200);
    }
  };

  typeStep();
}

// ══════════════════════════════════════════
//  TOAST
// ══════════════════════════════════════════
let _toastTimer = null;

function showToast(title, msg, duration = 6000) {
  const toast = document.getElementById('toast');
  document.getElementById('toast-title').textContent = title;
  document.getElementById('toast-msg').textContent   = msg;
  toast.classList.add('show');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(hideToast, duration);
}

function hideToast() {
  document.getElementById('toast').classList.remove('show');
  clearTimeout(_toastTimer);
}

// ── Register Chart.js datalabels plugin ──
Chart.register(ChartDataLabels);

// ══════════════════════════════════════════
//  COLOR PALETTES
// ══════════════════════════════════════════
const PALETTES = {
  'Professional':  ['#2563eb','#dc2626','#7c3aed','#059669','#d97706','#0891b2','#9333ea','#16a34a'],
  'Cyber-Neon':    ['#7c3aed','#10b981','#f59e0b','#ef4444','#3b82f6','#ec4899','#06b6d4','#84cc16'],
  'Vivid':         ['#6d28d9','#2563eb','#0891b2','#047857','#b45309','#be185d','#7c3aed','#0e7490'],
  'Pastel':        ['#f9a8d4','#a5f3fc','#bbf7d0','#fde68a','#c7d2fe','#fed7aa','#d9f99d','#e9d5ff'],
  'Vibrant':       ['#8b5cf6','#f97316','#06b6d4','#84cc16','#f43f5e','#eab308','#22d3ee','#a3e635'],
  'Dark Gradient': ['#1e3a5f','#4c1d95','#1e1b4b','#14532d','#451a03','#be185d','#0e7490','#3f6212'],
};

let selectedPalette = 'Professional';

// ══════════════════════════════════════════
//  STATE
// ══════════════════════════════════════════
const state = {
  years:     [],
  quarters:  [],
  meetings:  [],
  yearObj:   null,   // {id, name}
  quarterObj:null,
  scope:     'quarter',
  meetingObj:null,
  chartData: null,
  loading:   false,
};

let charts = { year: null, gender: null, major: null };

// ══════════════════════════════════════════
//  INIT
// ══════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  buildPaletteGrid();
  loadYears();
  wireSelects();
});

// ══════════════════════════════════════════
//  PALETTE GRID
// ══════════════════════════════════════════
function buildPaletteGrid() {
  const grid = document.getElementById('palette-grid');
  grid.innerHTML = '';
  for (const [name, colors] of Object.entries(PALETTES)) {
    const sw = document.createElement('div');
    sw.className = 'palette-swatch' + (name === selectedPalette ? ' selected' : '');
    sw.title = name;
    colors.slice(0, 5).forEach(c => {
      const dot = document.createElement('div');
      dot.className = 'palette-dot';
      dot.style.background = c;
      sw.appendChild(dot);
    });
    sw.addEventListener('click', () => {
      selectedPalette = name;
      document.querySelectorAll('.palette-swatch').forEach(s => s.classList.remove('selected'));
      sw.classList.add('selected');
      if (state.chartData) renderCharts(state.chartData);
    });
    grid.appendChild(sw);
  }
}

// ══════════════════════════════════════════
//  WIRE SELECT EVENTS
// ══════════════════════════════════════════
function wireSelects() {
  document.getElementById('year-select').addEventListener('change', onYearChange);
  document.getElementById('quarter-select').addEventListener('change', onQuarterChange);
  document.getElementById('meeting-select').addEventListener('change', onMeetingChange);
  ['year-chart-type','gender-chart-type','major-chart-type'].forEach(id => {
    document.getElementById(id).addEventListener('change', () => {
      if (state.chartData) renderCharts(state.chartData);
    });
  });
}

// ══════════════════════════════════════════
//  STEP 1: Load years
// ══════════════════════════════════════════
async function loadYears() {
  const sel = document.getElementById('year-select');
  sel.innerHTML = '<option value="">Loading years…</option>';
  sel.disabled = true;
  try {
    const res  = await fetch('/api/years');
    const data = await res.json();
    state.years = data;
    sel.innerHTML = '<option value="">Select a year…</option>';
    data.forEach(y => {
      const opt = document.createElement('option');
      opt.value = y.id;
      opt.textContent = y.name;
      sel.appendChild(opt);
    });
    sel.disabled = false;
    unlockStep(1);
  } catch (e) {
    sel.innerHTML = '<option value="">Failed to load — refresh page</option>';
  }
}

async function onYearChange() {
  const sel = document.getElementById('year-select');
  const id  = sel.value;
  state.yearObj    = id ? state.years.find(y => y.id === id) : null;
  state.quarterObj = null;
  state.meetingObj = null;
  state.chartData  = null;

  resetQuarter();
  resetMeeting();
  clearCharts();
  updateGenBtn();
  updateBreadcrumb();

  if (!id) return;
  lockStep(2); lockStep(3);
  await loadQuarters(id);
}

// ══════════════════════════════════════════
//  STEP 2: Load quarters
// ══════════════════════════════════════════
async function loadQuarters(yearId) {
  const sel = document.getElementById('quarter-select');
  sel.innerHTML = '<option value="">Loading…</option>';
  sel.disabled = true;
  try {
    const res  = await fetch(`/api/quarters?year_id=${yearId}`);
    const data = await res.json();
    if (!res.ok) {
      sel.innerHTML = '<option value="">No quarters found</option>';
      showToast(
        'No quarters found',
        data.error || 'Could not find Fall, Winter, or Spring folders under this year.'
      );
      return;
    }
    state.quarters = data.quarters;
    sel.innerHTML = '<option value="">Select a quarter…</option>';
    data.quarters.forEach(q => {
      const opt = document.createElement('option');
      opt.value = q.id;
      opt.textContent = q.name;
      sel.appendChild(opt);
    });
    sel.disabled = false;
    unlockStep(2);
  } catch (e) {
    sel.innerHTML = '<option value="">Failed to load quarters</option>';
    showToast('Failed to load quarters', e.message);
  }
}

async function onQuarterChange() {
  const sel = document.getElementById('quarter-select');
  const id  = sel.value;
  state.quarterObj = id ? state.quarters.find(q => q.id === id) : null;
  state.meetingObj = null;
  state.chartData  = null;

  resetMeeting();
  clearCharts();
  updateGenBtn();
  updateBreadcrumb();

  if (!id) return;
  lockStep(3);
  await loadMeetings(id);
}

// ══════════════════════════════════════════
//  STEP 3: Load meetings
// ══════════════════════════════════════════
async function loadMeetings(quarterId) {
  const sel = document.getElementById('meeting-select');
  sel.innerHTML = '<option value="">Loading…</option>';
  try {
    const res  = await fetch(`/api/meetings?quarter_id=${quarterId}`);
    const data = await res.json();

    if (!res.ok) {
      sel.innerHTML = '<option value="">Failed to load</option>';
      showToast('Failed to load meetings', data.error || 'Could not read this quarter folder.');
      return;
    }

    state.meetings = data;

    if (data.length === 0) {
      sel.innerHTML = '<option value="">No meetings found</option>';
      showToast(
        'No meetings found',
        'No spreadsheets were found under this quarter. Make sure the response sheets are stored here.'
      );
      lockStep(3);
      updateGenBtn();
      return;
    }

    sel.innerHTML = '<option value="">Select a meeting…</option>';
    sel.disabled = false;
    data.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.name;
      sel.appendChild(opt);
    });
    unlockStep(3);
    updateGenBtn();
  } catch (e) {
    sel.innerHTML = '<option value="">Error loading meetings</option>';
    showToast('Failed to load meetings', e.message);
  }
}

function onMeetingChange() {
  const sel = document.getElementById('meeting-select');
  const id  = sel.value;
  state.meetingObj = id ? state.meetings.find(m => m.id === id) : null;
  state.chartData  = null;
  clearCharts();
  updateGenBtn();
  updateBreadcrumb();
}

// ══════════════════════════════════════════
//  SCOPE TOGGLE
// ══════════════════════════════════════════
function setScope(scope) {
  state.scope = scope;
  state.meetingObj = null;
  state.chartData  = null;
  clearCharts();

  document.getElementById('btn-quarter').classList.toggle('active', scope === 'quarter');
  document.getElementById('btn-meeting').classList.toggle('active', scope === 'meeting');

  const meetSel = document.getElementById('meeting-select');
  meetSel.style.display = scope === 'meeting' ? 'block' : 'none';
  meetSel.value = '';

  updateGenBtn();
  updateBreadcrumb();
}

// ══════════════════════════════════════════
//  GENERATE
// ══════════════════════════════════════════
async function generate() {
  if (!canGenerate()) return;

  // Build file list
  let files;
  if (state.scope === 'quarter') {
    files = state.meetings.map(m => ({ id: m.id, name: m.name }));
  } else {
    files = [{ id: state.meetingObj.id, name: state.meetingObj.name }];
  }

  setLoading(true);
  showPanel('loading');

  try {
    const res  = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files }),
    });
    const data = await res.json();
    if (!res.ok) {
      const msg = data.error || 'Server error';
      // "No data" means the spreadsheet exists but has no recognised columns
      if (msg.toLowerCase().includes('no data')) {
        showToast(
          'No metrics found',
          'This meeting\'s spreadsheet doesn\'t contain recognised Year, Gender, or Major columns.'
        );
        showPanel('empty');
        setStatus('', 'Ready');
        return;
      }
      throw new Error(msg);
    }

    state.chartData = data;
    updateStats(data);
    renderCharts(data);
    showPanel('charts');
    setStatus('active', 'Data loaded');
    updateBreadcrumb();
  } catch (e) {
    showPanel('error');
    document.getElementById('error-msg').textContent = e.message;
    setStatus('error', 'Error');
    showToast('Failed to load data', e.message);
  } finally {
    setLoading(false);
  }
}

// ══════════════════════════════════════════
//  STATS
// ══════════════════════════════════════════
function updateStats(data) {
  document.getElementById('stat-total').textContent =
    data.total != null ? data.total.toLocaleString() : '—';
  document.getElementById('stat-meetings').textContent =
    data.meetings_count != null ? data.meetings_count : '—';

  // Gender ratio
  if (data.gender) {
    const m = data.gender['Male'] || 0;
    const f = data.gender['Female'] || 0;
    document.getElementById('stat-gender').textContent = `${m} / ${f}`;
  } else {
    document.getElementById('stat-gender').textContent = '—';
  }

  // Top major
  if (data.major) {
    const top = Object.entries(data.major).sort((a,b) => b[1]-a[1])[0];
    document.getElementById('stat-major').textContent = top ? top[0] : '—';
  } else {
    document.getElementById('stat-major').textContent = '—';
  }
}

// ══════════════════════════════════════════
//  RENDER CHARTS
// ══════════════════════════════════════════
function renderCharts(data) {
  const palette   = PALETTES[selectedPalette] || PALETTES['Professional'];
  const yearType  = document.getElementById('year-chart-type').value;
  const genType   = document.getElementById('gender-chart-type').value;
  const majType   = document.getElementById('major-chart-type').value;

  const prefix = buildTitlePrefix();

  // Destroy old charts
  Object.values(charts).forEach(c => c && c.destroy());
  charts = { year: null, gender: null, major: null };

  const visible = [yearType, genType, majType].filter(t => t !== 'none').length;
  const grid = document.getElementById('charts-grid');
  grid.className = `charts-grid col-${Math.max(visible, 1)}`;

  // Year
  const yCard = document.getElementById('year-card');
  if (yearType === 'none' || !data.year) {
    yCard.style.display = 'none';
  } else {
    yCard.style.display = '';
    document.getElementById('year-title').textContent = `${prefix} — Year Distribution`;
    const total = Object.values(data.year).reduce((a,b)=>a+b,0);
    document.getElementById('year-sub').textContent = `Total: ${total.toLocaleString()} responses`;
    charts.year = buildChart('year-canvas', yearType, data.year, palette);
  }

  // Gender
  const gCard = document.getElementById('gender-card');
  if (genType === 'none' || !data.gender) {
    gCard.style.display = 'none';
  } else {
    gCard.style.display = '';
    document.getElementById('gender-title').textContent = `${prefix} — Gender Distribution`;
    const total = Object.values(data.gender).reduce((a,b)=>a+b,0);
    document.getElementById('gender-sub').textContent = `Total: ${total.toLocaleString()} responses`;
    charts.gender = buildChart('gender-canvas', genType, data.gender, palette);
  }

  // Major
  const mCard = document.getElementById('major-card');
  if (majType === 'none' || !data.major) {
    mCard.style.display = 'none';
  } else {
    mCard.style.display = '';
    document.getElementById('major-title').textContent = `${prefix} — Major Distribution`;
    const total = Object.values(data.major).reduce((a,b)=>a+b,0);
    document.getElementById('major-sub').textContent = `Total: ${total.toLocaleString()} responses`;
    charts.major = buildChart('major-canvas', majType, data.major, palette);
  }
}

function buildChart(canvasId, type, dataObj, palette) {
  const canvas = document.getElementById(canvasId);
  const labels = Object.keys(dataObj);
  const values = Object.values(dataObj);
  const colors = labels.map((_, i) => palette[i % palette.length]);

  const isPie  = type === 'pie';
  const isHBar = type === 'horizontalBar';

  const baseFont = { family: 'Inter, system-ui, sans-serif', color: '#94a3b8' };

  const commonPlugins = {
    legend: {
      display: isPie,
      labels: { color: '#e2e8f0', font: { size: 11 }, boxWidth: 12, padding: 14 },
    },
    tooltip: {
      backgroundColor: 'rgba(13,13,40,0.92)',
      titleColor: '#e2e8f0',
      bodyColor: '#94a3b8',
      borderColor: 'rgba(124,58,237,0.4)',
      borderWidth: 1,
      padding: 10,
      callbacks: {
        label: ctx => {
          const v = isPie ? ctx.parsed : (isHBar ? ctx.parsed.x : ctx.parsed.y);
          const total = values.reduce((a,b)=>a+b,0);
          const pct = ((v/total)*100).toFixed(1);
          return isPie
            ? ` ${ctx.label}: ${v} (${pct}%)`
            : ` ${v} (${pct}%)`;
        }
      }
    },
    datalabels: {
      display: !isPie,
      color: '#e2e8f0',
      font: { size: 11, weight: '600' },
      formatter: v => v,
      anchor: isHBar ? 'end' : 'end',
      align:  isHBar ? 'right' : 'top',
      offset: 4,
      clip: false,
    },
  };

  if (isPie) {
    return new Chart(canvas, {
      type: 'pie',
      data: {
        labels,
        datasets: [{ data: values, backgroundColor: colors, borderColor: 'rgba(8,8,24,0.8)', borderWidth: 2 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          ...commonPlugins,
          datalabels: { display: false },
          legend: {
            display: true,
            position: 'bottom',
            labels: { color: '#e2e8f0', font: { size: 11 }, boxWidth: 12, padding: 12 },
          },
        },
      },
    });
  }

  const isH = isHBar;
  return new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors.map(c => c + 'cc'),
        borderColor:     colors,
        borderWidth: 1.5,
        borderRadius: 5,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: isH ? 'y' : 'x',
      layout: { padding: { top: isH ? 0 : 22, right: isH ? 40 : 4 } },
      scales: {
        x: {
          grid:  { color: 'rgba(255,255,255,0.05)' },
          ticks: { color: '#64748b', font: { size: 11 }, maxRotation: isH ? 0 : 35 },
          border:{ color: 'rgba(255,255,255,0.08)' },
        },
        y: {
          grid:  { color: 'rgba(255,255,255,0.05)' },
          ticks: { color: '#64748b', font: { size: 11 } },
          border:{ color: 'rgba(255,255,255,0.08)' },
        },
      },
      plugins: commonPlugins,
    },
  });
}

// ══════════════════════════════════════════
//  DOWNLOAD
// ══════════════════════════════════════════
function downloadChart(canvasId, name) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  // Render onto a dark-background offscreen canvas
  const off = document.createElement('canvas');
  off.width  = canvas.width  * 2;
  off.height = canvas.height * 2;
  const ctx = off.getContext('2d');
  ctx.scale(2, 2);
  ctx.fillStyle = '#111130';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(canvas, 0, 0);

  const a = document.createElement('a');
  a.href     = off.toDataURL('image/png');
  a.download = `${name}.png`;
  a.click();
}

// ══════════════════════════════════════════
//  UI HELPERS
// ══════════════════════════════════════════
function showPanel(panel) {
  ['empty-state','loading-state','error-state','charts-area'].forEach(id => {
    document.getElementById(id).style.display = 'none';
  });
  const map = {
    empty:   'empty-state',
    loading: 'loading-state',
    error:   'error-state',
    charts:  'charts-area',
  };
  if (map[panel]) document.getElementById(map[panel]).style.display = '';

  // Start typewriter when loader shows, stop when it hides
  if (panel === 'loading') {
    startTypewriter();
  } else {
    stopTypewriter();
  }
}

function setStatus(type, text) {
  const chip = document.getElementById('status-chip');
  chip.className = `status-chip ${type}`;
  document.getElementById('status-text').textContent = text;
}

function setLoading(val) {
  state.loading = val;
  document.getElementById('gen-btn').disabled = val || !canGenerate();
  if (val) setStatus('loading', 'Loading…');
}

function canGenerate() {
  if (!state.quarterObj || state.meetings.length === 0) return false;
  if (state.scope === 'meeting' && !state.meetingObj) return false;
  return true;
}

function updateGenBtn() {
  document.getElementById('gen-btn').disabled = !canGenerate() || state.loading;
}

function updateBreadcrumb() {
  const parts = [];
  if (state.yearObj)    parts.push(state.yearObj.name);
  if (state.quarterObj) parts.push(state.quarterObj.name);
  if (state.scope === 'meeting' && state.meetingObj) parts.push(state.meetingObj.name);
  else if (state.scope === 'quarter' && state.quarterObj) parts.push('Entire Quarter');

  document.getElementById('topbar-crumb').textContent =
    parts.length ? parts.join(' → ') : 'Select data from the left panel to get started';
}

function buildTitlePrefix() {
  const parts = [];
  if (state.quarterObj) parts.push(state.quarterObj.name);
  if (state.yearObj) {
    const y = state.yearObj.name.replace(/SHPE\s*/i, '').trim();
    parts.push(y);
  }
  return parts.join(' ');
}

function clearCharts() {
  Object.values(charts).forEach(c => c && c.destroy());
  charts = { year: null, gender: null, major: null };
  showPanel('empty');
  setStatus('', 'Ready');
  document.getElementById('stat-total').textContent    = '—';
  document.getElementById('stat-meetings').textContent = '—';
  document.getElementById('stat-gender').textContent   = '—';
  document.getElementById('stat-major').textContent    = '—';
}

function resetQuarter() {
  const sel = document.getElementById('quarter-select');
  sel.innerHTML = '<option value="">Select a year first</option>';
  sel.disabled = true;
  state.quarters = [];
  lockStep(2);
}

function resetMeeting() {
  const sel = document.getElementById('meeting-select');
  sel.innerHTML = '<option value="">Select a meeting…</option>';
  sel.value = '';
  state.meetings = [];
  lockStep(3);
}

function unlockStep(n) {
  const pill = document.getElementById(`pill-${n}`);
  if (pill) pill.classList.remove('locked');
}

function lockStep(n) {
  const pill = document.getElementById(`pill-${n}`);
  if (pill) pill.classList.add('locked');
}
