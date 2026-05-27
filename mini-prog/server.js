const express = require('express');
const path = require('path');

const app = express();
const PORT = 3000;

// OpenClaw Gateway chat completions endpoint
const GATEWAY = 'http://localhost:25404';
const AUTH_TOKEN = '71e6ae009424c99beee65ee38826a32030e9b875d8246ac1';

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Chat endpoint — streams response back via SSE
app.post('/chat', async (req, res) => {
  const { message, history } = req.body || {};
  if (!message) return res.status(400).json({ error: 'message required' });

  // Build conversation history (latest user message appended)
  const messages = [...(history || []), { role: 'user', content: message }];
  if (messages.length === 1) {
    messages.unshift({
      role: 'system',
      content: '你是巴菲特，飞浪的金融管家。回复简洁、严谨、数据驱动。'
    });
  }

  // Set headers for SSE streaming
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');

  try {
    const apiRes = await fetch(`${GATEWAY}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${AUTH_TOKEN}`
      },
      body: JSON.stringify({
        model: 'openclaw',
        messages,
        stream: true,
        max_tokens: 2048
      })
    });

    if (!apiRes.ok) {
      const errText = await apiRes.text();
      res.write(`data: ${JSON.stringify({ error: `Gateway error: ${apiRes.status} ${errText}` })}\n\n`);
      res.write('data: [DONE]\n\n');
      res.end();
      return;
    }

    // Stream the response line by line
    const reader = apiRes.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data: ')) continue;
        const payload = trimmed.slice(6);
        if (payload === '[DONE]') continue;

        try {
          const parsed = JSON.parse(payload);
          const content = parsed.choices?.[0]?.delta?.content || '';
          if (content) {
            res.write(`data: ${JSON.stringify({ content })}\n\n`);
          }
        } catch { /* skip malformed */ }
      }
    }

    res.write('data: [DONE]\n\n');
    res.end();
  } catch (err) {
    console.error('Proxy error:', err);
    res.write(`data: ${JSON.stringify({ error: err.message })}\n\n`);
    res.write('data: [DONE]\n\n');
    res.end();
  }
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 小程序后端已启动: http://localhost:${PORT}`);
});
