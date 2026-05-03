
/**
 * ws_send.js - 通过 WebSocket 直接链接 OpenClaw Gateway 给 agent 发消息
 */

const WebSocket = require('/app/node_modules/ws');

const GATEWAY_HOST = '127.0.0.1';
const GATEWAY_PORT = 18789;
const TOKEN = '你的gateway-token';

const TARGET_KEY = 'agent:liting:main';
const MESSAGE = 'Kim from main: 嗨！这是一条通过 WS API 直接发送的测试消息';

const ws = new WebSocket(`ws://${GATEWAY_HOST}:${GATEWAY_PORT}`, {
  headers: { 'Authorization': 'Bearer ' + TOKEN }
});

let step = 0;

ws.on('message', (data) => {
  const msg = JSON.parse(data.toString());

  if (msg.event === 'connect.challenge' && step === 0) {
    step = 1;
    console.log('[2] 收到 challenge，发起 connect...');
    ws.send(JSON.stringify({
      type: 'req', id: 'r1', method: 'connect', params: {
        minProtocol: 3, maxProtocol: 3,
        client: { id: 'gateway-client', version: '1.0', platform: 'linux', mode: 'backend' },
        role: 'operator',
        scopes: ['operator.read', 'operator.write', 'operator.admin'],
        caps: [], commands: [], permissions: {},
        auth: { token: TOKEN }, locale: 'en-US', userAgent: 'openclaw-cli/1.0'
      }
    }));
  }

  if (msg.id === 'r1' && msg.ok && step === 1) {
    step = 2;
    console.log('[3] Connected! connId:', msg.payload.server?.connId);
    console.log('[4] 发送 sessions.send...');
    ws.send(JSON.stringify({
      type: 'req', id: 'r2', method: 'sessions.send',
      params: { key: TARGET_KEY, message: MESSAGE }
    }));
  }

  if (msg.id === 'r1' && !msg.ok) {
    console.error('[!] Connect 失败:', msg.error);
    ws.close();
  }

  if (msg.id === 'r2') {
    if (msg.ok) {
      console.log('[5] 消息发送成功! runId:', msg.payload.runId);
    } else {
      console.error('[!] 发送失败:', msg.error);
    }
    ws.close();
  }
});

ws.on('error', (err) => { console.error('[WS error]', err.message); });
ws.on('close', () => process.exit(0));
setTimeout(() => { console.log('[timeout]'); ws.close(); process.exit(1); }, 10000);
