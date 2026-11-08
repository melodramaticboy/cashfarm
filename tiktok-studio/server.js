'use strict';
// Servidor sem dependências: serve /public e expõe POST /api/generate.
// A chave da API fica só aqui no servidor (variável ANTHROPIC_API_KEY).
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 8000;
const MODEL = process.env.ANTHROPIC_MODEL || 'claude-sonnet-5-5';
const KEY = process.env.ANTHROPIC_API_KEY;
const PUB = path.join(__dirname, 'public');
const TYPES = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript' };

const SYSTEM = `Você é roteirista de vídeos curtos verticais para TikTok. Responda SOMENTE com JSON válido, sem markdown, neste formato:
{"title":string,"description":string,"hashtags":[string],
 "scenes":[{"narration":string,"caption":string,"emoji":string,"colors":["#rrggbb","#rrggbb"],"seconds":number}]}
Regras: a primeira cena é um gancho forte; "caption" tem no máximo 8 palavras; "narration" é a fala natural em português do Brasil; "seconds" entre 2 e 6; use cores vibrantes com bom contraste para texto branco; hashtags sem o símbolo #.`;

function demoPlan(idea) {
  return {
    demo: true, title: 'Demo: ' + idea, description: 'Roteiro de exemplo (defina ANTHROPIC_API_KEY para gerar com IA).',
    hashtags: ['demo', 'tiktok', 'ia'],
    scenes: [
      { narration: 'Você sabia disso?', caption: 'Você sabia disso?', emoji: '🤯', colors: ['#fe2c55', '#7b2ff7'], seconds: 3 },
      { narration: idea, caption: idea.slice(0, 50), emoji: '✨', colors: ['#25f4ee', '#0072ff'], seconds: 4 },
      { narration: 'Segue para mais!', caption: 'Segue para mais!', emoji: '🔥', colors: ['#f7971e', '#ffd200'], seconds: 3 },
    ],
  };
}

async function generate({ idea, seconds, tone }) {
  if (!KEY) return demoPlan(idea);
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-api-key': KEY, 'anthropic-version': '2023-06-01' },
    body: JSON.stringify({
      model: MODEL, max_tokens: 2000, system: SYSTEM,
      messages: [{ role: 'user', content: `Ideia: ${idea}\nDuração total aproximada: ${seconds}s\nTom: ${tone}` }],
    }),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error?.message || 'Erro na API (' + r.status + ')');
  const text = data.content.map(b => b.text || '').join('');
  const json = text.slice(text.indexOf('{'), text.lastIndexOf('}') + 1);
  return JSON.parse(json);
}

http.createServer(async (req, res) => {
  if (req.method === 'POST' && req.url === '/api/generate') {
    let body = '';
    req.on('data', c => { body += c; if (body.length > 1e5) req.destroy(); });
    req.on('end', async () => {
      try {
        const { idea, seconds = 30, tone = 'divertido' } = JSON.parse(body);
        if (!idea || !idea.trim()) throw new Error('Escreva uma ideia.');
        const plan = await generate({ idea: idea.trim().slice(0, 500), seconds: Math.min(+seconds || 30, 90), tone });
        res.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify(plan));
      } catch (e) {
        res.writeHead(400, { 'content-type': 'application/json' }).end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }
  const rel = req.url.split('?')[0] === '/' ? '/index.html' : req.url.split('?')[0];
  const file = path.normalize(path.join(PUB, rel));
  if (!file.startsWith(PUB + path.sep)) return res.writeHead(403).end();
  fs.readFile(file, (err, buf) => {
    if (err) return res.writeHead(404).end('Not found');
    res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream' }).end(buf);
  });
}).listen(PORT, () => console.log(`TikTok Studio em http://localhost:${PORT}` + (KEY ? '' : '  (modo demo: sem ANTHROPIC_API_KEY)')));
