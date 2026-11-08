# TikTok Studio

Estúdio de criação de vídeos verticais (9:16) para TikTok, direto no navegador.

- Grave pela câmera ou envie um vídeo
- Filtros, espelhamento e textos arrastáveis
- Contagem regressiva e gravação com áudio (WebM/MP4)
- Feed estilo TikTok com curtir e baixar

## Como rodar

Sem dependências. Sirva a pasta com qualquer servidor estático (a câmera exige `localhost` ou HTTPS):

```bash
cd tiktok-studio
python3 -m http.server 8000
```

Abra http://localhost:8000
