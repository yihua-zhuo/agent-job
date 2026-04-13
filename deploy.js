#!/usr/bin/env node
/**
 * Railway deployment script
 */
const https = require('https');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const TOKEN = '2dc2f4ae-4e33-4ec4-a715-474a16792c00';
const REPO = 'yihua-zhuo/agent-job';

function apiRequest(method, path, body = null) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'railway.app',
      path,
      method,
      headers: {
        'Authorization': `Bearer ${TOKEN}`,
        'Content-Type': 'application/json'
      }
    };
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch { resolve(data); }
      });
    });
    req.on('error', reject);
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

async function main() {
  console.log('Checking Railway token...');
  const me = await apiRequest('GET', '/api/v1/user');
  console.log('User:', JSON.stringify(me).slice(0, 200));

  console.log('\nListing projects...');
  const projects = await apiRequest('GET', '/api/v1/projects');
  console.log('Projects:', JSON.stringify(projects).slice(0, 300));
}

main().catch(console.error);