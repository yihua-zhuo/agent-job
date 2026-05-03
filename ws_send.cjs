#!/usr/bin/env node
/**
 * ws_send.cjs - 通过 WebSocket 直接链接 OpenClaw Gateway 给 agent 发消息
 *
 * 使用 Node.js 内置 ws 库 (/app/node_modules/ws)
 * 无需额外安装，不受 Origin header 问题影响
 *
 * 运行: node ws_send.cjs [message]
 */

const { WebSocket } = require('/app/node_modules/ws');

const GATEWAY_HOST = '127.0.0.1';
const GATEWAY_PORT = 18789;
const TOKEN = '92833302a219bce42d1a57d87a3583e244074bfac2163941';
const TARGET_KEY = 'agent:liting:main';
const MESSAGE = process.argv[2] || 'Hello from Node.js ws library!';

function main() {
    const url = `ws://${GATEWAY_HOST}:${GATEWAY_PORT}`;
    console.log(`[connecting] ${url}`);

    const ws = new WebSocket(url, {
        headers: { Authorization: `Bearer ${TOKEN}` }
    });

    let step = 0;

    ws.on('open', () => {
        console.log('[open] WebSocket connected');
    });

    ws.on('message', (data) => {
        const msg = JSON.parse(data.toString());

        // Step 1: 收到 challenge，发起 connect
        if (msg.event === 'connect.challenge' && step === 0) {
            step = 1;
            console.log(`[1] Got challenge: ${msg.payload.nonce.slice(0, 16)}...`);
            ws.send(JSON.stringify({
                type: 'req',
                id: 'r1',
                method: 'connect',
                params: {
                    minProtocol: 3,
                    maxProtocol: 3,
                    client: {
                        id: 'gateway-client',
                        version: '1.0',
                        platform: 'linux',
                        mode: 'backend'
                    },
                    role: 'operator',
                    scopes: ['operator.read', 'operator.write', 'operator.admin'],
                    caps: [],
                    commands: [],
                    permissions: {},
                    auth: { token: TOKEN },
                    locale: 'en-US',
                    userAgent: 'openclaw-cli/1.0'
                }
            }));
            console.log('[2] Sent connect request');
            return;
        }

        // Step 2: connect 成功，发送消息
        if (msg.id === 'r1' && msg.ok && step === 1) {
            step = 2;
            const connId = msg.payload && msg.payload.server && msg.payload.server.connId || '?';
            console.log(`[3] Connected! connId=${connId}`);
            ws.send(JSON.stringify({
                type: 'req',
                id: 'r2',
                method: 'sessions.send',
                params: {
                    key: TARGET_KEY,
                    message: MESSAGE
                }
            }));
            console.log('[4] Sent sessions.send request');
            return;
        }

        // connect 失败
        if (msg.id === 'r1' && !msg.ok) {
            console.log('[!] Connect failed:', JSON.stringify(msg.error));
            ws.close();
            return;
        }

        // 收到发送结果
        if (msg.id === 'r2') {
            if (msg.ok) {
                const runId = msg.payload && msg.payload.runId || '?';
                const status = msg.payload && msg.payload.status || '?';
                console.log(`[5] Message sent! runId=${runId} status=${status}`);
            } else {
                console.log('[!] Send failed:', JSON.stringify(msg.error));
            }
            ws.close();
            return;
        }
    });

    ws.on('error', (err) => {
        console.log('[error]', err.message);
    });

    ws.on('close', () => {
        console.log('[closed]');
    });
}

main();