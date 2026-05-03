#!/usr/bin/env python3
"""
ws_send.py - 通过 WebSocket 直接链接 OpenClaw Gateway 给 agent 发消息

依赖: pip install websocket-client

关键: 必须去掉 Origin header，否则 Gateway auth.scopes 为空
"""

import websocket
import json

GATEWAY_HOST = '127.0.0.1'
GATEWAY_PORT = 18789
TOKEN = '你的gateway-token'
TARGET_KEY = 'agent:liting:main'
MESSAGE = 'Kim from main: hello from WS!'


def main():
    # 去掉 Origin header（Gateway 对 Origin 处理有问题）
    import websocket._handshake as hs
    _orig = hs._get_handshake_headers
    def _patch(r, u, h, p, o):
        hdrs, key = _orig(r, u, h, p, o)
        return [x for x in hdrs if not x.startswith('Origin:')], key
    hs._get_handshake_headers = _patch

    ws = websocket.create_connection(
        f'ws://{GATEWAY_HOST}:{GATEWAY_PORT}',
        header={'Authorization': f'Bearer {TOKEN}'}
    )

    step = 0
    while True:
        msg = json.loads(ws.recv())

        if msg.get('event') == 'connect.challenge' and step == 0:
            step = 1
            print('[1] Got challenge')
            ws.send(json.dumps({
                'type': 'req', 'id': 'r1', 'method': 'connect',
                'params': {
                    'minProtocol': 3, 'maxProtocol': 3,
                    'client': {'id': 'gateway-client', 'version': '1.0',
                               'platform': 'linux', 'mode': 'backend'},
                    'role': 'operator',
                    'scopes': ['operator.read', 'operator.write', 'operator.admin'],
                    'caps': [], 'commands': [], 'permissions': {},
                    'auth': {'token': TOKEN}, 'locale': 'en-US',
                    'userAgent': 'openclaw-cli/1.0'
                }
            }))

        if msg.get('id') == 'r1' and msg.get('ok') and step == 1:
            step = 2
            print(f'[2] Connected! connId={msg["payload"]["server"]["connId"]}')
            ws.send(json.dumps({
                'type': 'req', 'id': 'r2', 'method': 'sessions.send',
                'params': {'key': TARGET_KEY, 'message': MESSAGE}
            }))

        if msg.get('id') == 'r1' and not msg.get('ok'):
            print(f'[!] Connect failed: {msg.get("error")}')
            break

        if msg.get('id') == 'r2':
            print(f'[3] Result: ok={msg.get("ok")} payload={msg.get("payload")}')
            break

    ws.close()


if __name__ == '__main__':
    main()
