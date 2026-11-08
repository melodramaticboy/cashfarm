'use strict';
const W = 720, H = 1280;
const $ = id => document.getElementById(id);
const canvas = $('canvas'), ctx = canvas.getContext('2d');
const video = document.createElement('video');
video.playsInline = true; video.loop = true;

let stream = null;       // camera stream
let fileUrl = null;      // uploaded file object URL
let texts = [];          // {text,color,x,y,size}
let dragging = null;
let recorder = null, chunks = [], recStart = 0, timerId = null;
const clips = [];        // {url, liked}

// ---------- Render loop ----------
function draw() {
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
  if (video.readyState >= 2 && video.videoWidth) {
    const vw = video.videoWidth, vh = video.videoHeight;
    const s = Math.max(W / vw, H / vh);           // "cover" fit
    const dw = vw * s, dh = vh * s;
    ctx.save();
    ctx.filter = $('filter').value;
    if (stream && $('mirror').checked) { ctx.translate(W, 0); ctx.scale(-1, 1); }
    ctx.drawImage(video, (W - dw) / 2, (H - dh) / 2, dw, dh);
    ctx.restore();
  }
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  for (const t of texts) {
    ctx.font = `800 ${t.size}px system-ui, sans-serif`;
    ctx.lineWidth = 8; ctx.strokeStyle = '#000'; ctx.lineJoin = 'round';
    ctx.strokeText(t.text, t.x, t.y);
    ctx.fillStyle = t.color; ctx.fillText(t.text, t.x, t.y);
  }
  requestAnimationFrame(draw);
}
draw();

// ---------- Sources ----------
function setStatus(msg) { $('status').textContent = msg; }
function stopSources() {
  if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
  if (fileUrl) { URL.revokeObjectURL(fileUrl); fileUrl = null; }
  video.pause(); video.srcObject = null; video.removeAttribute('src');
}

$('btnCam').onclick = async () => {
  try {
    stopSources();
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } }, audio: true });
    video.srcObject = stream; video.muted = true; await video.play();
    $('btnRec').disabled = false; setStatus('Câmera pronta.');
  } catch (e) { setStatus('Não foi possível acessar a câmera: ' + e.message); }
};

$('file').onchange = async e => {
  const f = e.target.files[0]; if (!f) return;
  stopSources();
  fileUrl = URL.createObjectURL(f);
  video.src = fileUrl; video.muted = false;
  try { await video.play(); } catch { video.muted = true; await video.play(); }
  $('btnRec').disabled = false; setStatus('Vídeo carregado: ' + f.name);
};

// ---------- Text overlays ----------
$('addTxt').onclick = () => {
  const text = $('txt').value.trim(); if (!text) return;
  texts.push({ text, color: $('txtColor').value, x: W / 2, y: H / 2, size: 72 });
  $('txt').value = '';
};
function canvasPos(ev) {
  const r = canvas.getBoundingClientRect();
  return { x: (ev.clientX - r.left) * W / r.width, y: (ev.clientY - r.top) * H / r.height };
}
function hit(p) {
  for (let i = texts.length - 1; i >= 0; i--) {
    const t = texts[i]; ctx.font = `800 ${t.size}px system-ui, sans-serif`;
    const w = ctx.measureText(t.text).width;
    if (Math.abs(p.x - t.x) < w / 2 && Math.abs(p.y - t.y) < t.size / 2) return i;
  }
  return -1;
}
canvas.addEventListener('pointerdown', e => {
  const p = canvasPos(e), i = hit(p);
  if (i >= 0) { dragging = { i, dx: texts[i].x - p.x, dy: texts[i].y - p.y }; canvas.setPointerCapture(e.pointerId); }
});
canvas.addEventListener('pointermove', e => {
  if (!dragging) return;
  const p = canvasPos(e), t = texts[dragging.i];
  t.x = p.x + dragging.dx; t.y = p.y + dragging.dy;
});
canvas.addEventListener('pointerup', () => { dragging = null; });
canvas.addEventListener('dblclick', e => { const i = hit(canvasPos(e)); if (i >= 0) texts.splice(i, 1); });

// ---------- Recording ----------
function pickMime() {
  const list = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4'];
  return list.find(m => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || '';
}
function audioTracks() {
  if (stream) return stream.getAudioTracks();
  if (fileUrl && video.captureStream) return video.captureStream().getAudioTracks();
  return [];
}
function countdown(n) {
  const el = $('countdown'); el.hidden = false;
  return new Promise(res => {
    const tick = () => { if (n === 0) { el.hidden = true; res(); return; } el.textContent = n--; setTimeout(tick, 1000); };
    tick();
  });
}

$('btnRec').onclick = async () => {
  if (!window.MediaRecorder) return setStatus('Seu navegador não suporta gravação.');
  $('btnRec').disabled = true;
  await countdown(3);
  const out = canvas.captureStream(30);
  audioTracks().forEach(t => out.addTrack(t));
  const mimeType = pickMime();
  chunks = [];
  recorder = new MediaRecorder(out, mimeType ? { mimeType, videoBitsPerSecond: 5_000_000 } : undefined);
  recorder.ondataavailable = e => e.data.size && chunks.push(e.data);
  recorder.onstop = finishRecording;
  recorder.start(250);
  recStart = Date.now(); $('rec').hidden = false; $('btnStop').disabled = false;
  timerId = setInterval(() => {
    const s = Math.floor((Date.now() - recStart) / 1000);
    $('timer').textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  }, 250);
  setStatus('Gravando…');
};

$('btnStop').onclick = () => { if (recorder && recorder.state !== 'inactive') recorder.stop(); };

function finishRecording() {
  clearInterval(timerId); $('rec').hidden = true;
  $('btnStop').disabled = true; $('btnRec').disabled = false;
  const type = recorder.mimeType || 'video/webm';
  const url = URL.createObjectURL(new Blob(chunks, { type }));
  clips.unshift({ url, liked: false, ext: type.includes('mp4') ? 'mp4' : 'webm' });
  renderFeed();
  setStatus('Vídeo salvo! Veja no Feed.');
}

// ---------- Feed ----------
function renderFeed() {
  const box = $('videos'); box.innerHTML = '';
  $('empty').hidden = clips.length > 0;
  clips.forEach((c, i) => {
    const item = document.createElement('div'); item.className = 'item';
    const v = document.createElement('video');
    v.src = c.url; v.loop = true; v.playsInline = true; v.controls = false;
    v.onclick = () => (v.paused ? v.play() : v.pause());
    const act = document.createElement('div'); act.className = 'actions';
    const like = document.createElement('button');
    like.textContent = c.liked ? '❤️' : '🤍'; like.title = 'Curtir';
    like.onclick = () => { c.liked = !c.liked; like.textContent = c.liked ? '❤️' : '🤍'; };
    const dl = document.createElement('a');
    dl.href = c.url; dl.download = `tiktok-studio-${clips.length - i}.${c.ext}`;
    dl.innerHTML = '<button title="Baixar">⬇️</button>';
    act.append(like, dl); item.append(v, act); box.append(item);
  });
  observe();
}
let io;
function observe() {
  if (io) io.disconnect();
  io = new IntersectionObserver(es => es.forEach(e => {
    const v = e.target.querySelector('video');
    if (e.isIntersecting) v.play().catch(() => {}); else v.pause();
  }), { threshold: 0.7 });
  document.querySelectorAll('.item').forEach(el => io.observe(el));
}

// ---------- Tabs ----------
function show(tab) {
  $('studio').hidden = tab !== 'studio'; $('feed').hidden = tab !== 'feed';
  $('tabStudio').classList.toggle('active', tab === 'studio');
  $('tabFeed').classList.toggle('active', tab === 'feed');
  if (tab === 'feed') observe();
}
$('tabStudio').onclick = () => show('studio');
$('tabFeed').onclick = () => show('feed');
renderFeed();
