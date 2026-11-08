# TikTok Studio

Estúdio que **gera vídeos verticais (9:16) para TikTok com IA**. Você escreve a ideia, a IA cria o roteiro em cenas (gancho, legendas, narração, emojis, cores, hashtags) e o app monta o vídeo animado. Nada de gravar com câmera.

## Como usar

1. Escreva a ideia, escolha duração e tom → **Gerar vídeo com IA**
2. Ajuste legendas, narração, tempo e cores de cada cena
3. **Assistir** (com narração por voz do navegador) ou **Exportar vídeo** (arquivo WebM/MP4, sem áudio)

## Rodar

Precisa de Node 18+ (sem dependências).

```bash
cd tiktok-studio
export ANTHROPIC_API_KEY=sua_chave
npm start
```

Abra http://localhost:8000. Sem a chave, roda em **modo demo** com um roteiro de exemplo.

Variáveis opcionais: `PORT`, `ANTHROPIC_MODEL`.
