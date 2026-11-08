'use strict';
const W = 720, H = 1280;
const $ = id => document.getElementById(id);
const canvas = $('canvas'), ctx = canvas.getContext('2d');

let plan = null;            // {title, description, hashtags, scenes}
let playing = false, t0 = 0, raf = 0, spoken = -1;
let recorder = null, chunks = [];

const total = () => plan ? plan.scenes.reduce((s, c) => s + c.seconds, 0) : 0;
function sceneAt(t) {
  let acc = 0;
  for (let i = 0; i < plan.scenes.length; i++) {
    const s = plan.scenes[i];
    if (t < acc + s.seconds) return { i, s, local: t - acc };
    acc += s.seconds;
  }
  return null;
}

// ---------- Desenho ----------
function wrap(text, maxW) {
  const words = text.split(/\s+/), lines = []; let line = '';
  for (const w of words) {
    const test = line ? line + ' ' + w : w;
    if (ctx.measureText(test).width > maxW && line) { lines.push(line); line = w; } else line = test;
  }
  if (line) lines.push(line);
  return lines;
}
function drawScene(s, local, i) {
  const [c1, c2] = s.colors || ['#fe2c55', '#7b2ff7'];
  const a = (i * 0.7 + local * 0.25) % (Math.PI * 2);
  const g = ctx.createLinearGradient(W / 2 + Math.cos(a) * W, 0, W / 2 - Math.cos(a) * W, H);
  g.addColorStop(0, c1); g.addColorStop(1, c2);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  // círculos flutuantes
  ctx.fillStyle = 'rgba(255,255,255,.08)';
  for (let k = 0; k < 6; k++) {
    const x = (k * 157 + local * 40 * (k % 2 ? 1 : -1) + 900) % (W + 200) - 100;
    const y = (k * 233 + local * 30) % (H + 200) - 100;
    ctx.beginPath(); ctx.arc(x, y, 60 + k * 25, 0, 7); ctx.fill();
  }
  // emoji com "pulo"
  const pop = Math.min(1, local / 0.35), bounce = Math.sin(local * 3) * 14;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.font = `${Math.round(260 * (0.4 + 0.6 * pop))}px system-ui, "Apple Color Emoji", "Noto Color Emoji", sans-serif`;
  ctx.fillStyle = '#fff'; ctx.fillText(s.emoji || '✨', W / 2, 380 + bounce);
  // legenda palavra por palavra
  ctx.font = '800 68px system-ui, sans-serif';
  const words = (s.caption || '').split(/\s+/).filter(Boolean);
  const shown = Math.min(words.length, Math.floor(local / Math.max(0.2, (s.seconds * 0.7) / words.length)) + 1);
  const lines = wrap(words.slice(0, shown).join(' '), W - 120);
  const lh = 84, y0 = 800 - (lines.length * lh) / 2;
  ctx.lineJoin = 'round'; ctx.lineWidth = 12; ctx.strokeStyle = 'rgba(0,0,0,.7)';
  lines.forEach((ln, k) => { ctx.strokeText(ln, W / 2, y0 + k * lh); ctx.fillStyle = '#fff'; ctx.fillText(ln, W / 2, y0 + k * lh); });
}
function idle() {
  const g = ctx.createLinearGradient(0, 0, W, H);
  g.addColorStop(0, '#16161d'); g.addColorStop(1, '#2a1030');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.font = '160px system-ui, "Noto Color Emoji", sans-serif'; ctx.fillText('🎬', W / 2, 520);
  ctx.font = '700 44px system-ui, sans-serif'; ctx.fillText('Escreva uma ideia', W / 2, 700);
  ctx.fillText('e gere seu vídeo', W / 2, 760);
}
function frame() {
  if (!playing) return;
  const t = (performance.now() - t0) / 1000;
  const cur = sceneAt(t);
  if (!cur) return endPlayback();
  drawScene(cur.s, cur.local, cur.i);
  // barra de progresso
  ctx.fillStyle = 'rgba(255,255,255,.35)'; ctx.fillRect(0, H - 10, W, 10);
  ctx.fillStyle = '#fff'; ctx.fillRect(0, H - 10, W * (t / total()), 10);
  if (cur.i !== spoken) { spoken = cur.i; speak(cur.s.narration); }
  raf = requestAnimationFrame(frame);
}
idle();

// ---------- Reprodução / narração ----------
function speak(text) {
  if (!('speechSynthesis' in window) || !text) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text); u.lang = 'pt-BR'; u.rate = 1.05;
  speechSynthesis.speak(u);
}
function start(narrate = true) {
  if (!plan) return;
  playing = true; spoken = narrate ? -1 : 9999; t0 = performance.now();
  $('play').disabled = true; $('stop').disabled = false; $('export').disabled = true;
  raf = requestAnimationFrame(frame);
}
function endPlayback() {
  playing = false; cancelAnimationFrame(raf);
  if ('speechSynthesis' in window) speechSynthesis.cancel();
  $('play').disabled = false; $('stop').disabled = true; $('export').disabled = false;
  if (recorder && recorder.state !== 'inactive') recorder.stop();
}
$('play').onclick = () => start(true);
$('stop').onclick = endPlayback;

// ---------- Exportar (renderiza o canvas em arquivo) ----------
$('export').onclick = () => {
  if (!window.MediaRecorder) return ($('expHint').textContent = 'Seu navegador não suporta exportar.');
  const mime = ['video/webm;codecs=vp9', 'video/webm', 'video/mp4'].find(m => MediaRecorder.isTypeSupported(m));
  chunks = [];
  recorder = new MediaRecorder(canvas.captureStream(30), { mimeType: mime, videoBitsPerSecond: 5e6 });
  recorder.ondataavailable = e => e.data.size && chunks.push(e.data);
  recorder.onstop = () => {
    const ext = (recorder.mimeType || mime).includes('mp4') ? 'mp4' : 'webm';
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(chunks, { type: recorder.mimeType || mime }));
    a.download = (plan.title || 'video').replace(/[^\w\-]+/g, '_') + '.' + ext; a.click();
    $('expHint').textContent = 'Vídeo exportado (sem áudio — a narração só toca no player).';
  };
  recorder.start(); $('expHint').textContent = 'Renderizando…'; start(false);
};

// ---------- Geração ----------
$('gen').onclick = async () => {
  const idea = $('idea').value.trim();
  if (!idea) return ($('status').textContent = 'Escreva uma ideia primeiro.');
  $('gen').disabled = true; $('status').textContent = 'Gerando roteiro…';
  try {
    const r = await fetch('/api/generate', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ idea, seconds: +$('secs').value, tone: $('tone').value }) });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error);
    plan = data;
    plan.scenes = (plan.scenes || []).map(s => ({ ...s, seconds: Math.min(8, Math.max(2, +s.seconds || 3)) }));
    if (!plan.scenes.length) throw new Error('A IA não devolveu cenas. Tente de novo.');
    renderEditor();
    $('status').textContent = plan.demo ? 'Modo demo (sem chave de IA configurada).' : 'Pronto! Ajuste o que quiser e clique em Assistir.';
  } catch (e) { $('status').textContent = 'Erro: ' + e.message; }
  $('gen').disabled = false;
};

function renderEditor() {
  $('result').hidden = false;
  $('title').value = plan.title || '';
  $('title').oninput = () => (plan.title = $('title').value);
  $('tags').textContent = (plan.hashtags || []).map(h => '#' + h).join(' ') + (plan.description ? '\n' + plan.description : '');
  const box = $('scenes'); box.innerHTML = '';
  plan.scenes.forEach((s, i) => {
    const el = document.createElement('div'); el.className = 'scene';
    el.innerHTML = `<div class="top"><b>${i + 1}</b>
      <input type="text" data-k="emoji" size="3" style="width:56px">
      <input type="text" data-k="caption" value="">
      <input type="number" data-k="seconds" min="2" max="8" value="${s.seconds}">s
      <input type="color" data-k="c1" value="${s.colors?.[0] || '#fe2c55'}">
      <input type="color" data-k="c2" value="${s.colors?.[1] || '#7b2ff7'}"></div>
      <textarea data-k="narration" rows="2"></textarea>`;
    el.querySelector('[data-k=emoji]').value = s.emoji || '';
    el.querySelector('[data-k=caption]').value = s.caption || '';
    el.querySelector('[data-k=narration]').value = s.narration || '';
    el.oninput = e => {
      const k = e.target.dataset.k, v = e.target.value;
      if (k === 'c1' || k === 'c2') s.colors = [k === 'c1' ? v : (s.colors?.[0] || '#fe2c55'), k === 'c2' ? v : (s.colors?.[1] || '#7b2ff7')];
      else if (k === 'seconds') s.seconds = Math.min(8, Math.max(2, +v || 3));
      else s[k] = v;
    };
    box.append(el);
  });
  $('play').disabled = false; $('export').disabled = false;
}
