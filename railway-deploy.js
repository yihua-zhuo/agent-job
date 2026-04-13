#!/usr/bin/env node
const { execSync } = require('child_process');
const path = require('path');

const token = process.env.RAILWAY_TOKEN;
if (!token) {
  console.error('RAILWAY_TOKEN environment variable is required');
  process.exit(1);
}
const railwayPath = path.join(__dirname, 'railway-cli-bin', 'bin', 'railway.js');

try {
  console.log('Testing Railway CLI...');
  execSync(`node ${railwayPath} --version`, { stdio: 'inherit' });
} catch (e) {
  console.log('Direct invocation failed, trying npx...');
  execSync('npx --yes @railway/cli@latest login --token ' + token, { stdio: 'inherit' });
}