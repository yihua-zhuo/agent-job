# 前端基建引导 · 创建 React/Vite 脚手架

| 元数据 | 值 |
|---|---|
| Issue | #768 |
| 分类 | [90-frontend](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [0770-add-sortabletable-shared-component-and-campaignfilters-compo](0770-add-sortabletable-shared-component-and-campaignfilters-compo.md), [0771-add-campaignservice-and-usecampaignlist-hook](0771-add-campaignservice-and-usecampaignlist-hook.md), [0772-add-campaigntable-component-and-campaignlist-page](0772-add-campaigntable-component-and-campaignlist-page.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The CRM has no frontend layer yet. All work on the Campaign feature (issues #770–#772) requires a running React app with Vite bundler as a prerequisite. Without a scaffold, no component, hook, or page can be developed, tested, or previewed locally.

### 1.2 做完后

- **用户视角**：No user-facing changes — this is pure infrastructure.
- **开发者视角**：`npm install && npm run dev` starts a Vite dev server at `http://localhost:5173` serving a React app with React Router. A placeholder `/campaigns` route is registered and renders a stub. The codebase has a working `src/ui/` tree ready for component development.

### 1.3 不做什么（剔除）

- [ ] No real CampaignList UI — only a placeholder component
- [ ] No Tailwind config customization beyond the baseline `postcss.config.js` + `tailwind.config.js` skeleton
- [ ] No backend API integration (no `fetch` calls to FastAPI yet)
- [ ] No Docker/podman containerization of the frontend

### 1.4 关键 KPI

- `npm install && npm run dev` starts dev server with exit code 0 (no build errors)
- `package.json` contains all required entries: `react`, `react-dom`, `react-router-dom`, `vite`, `@vitejs/plugin-react`
- `vite.config.ts` resolves path alias `@/` → `src/`
- `src/ui/App.tsx` mounts `<BrowserRouter>` with a `/campaigns` route
- `src/ui/main.tsx` renders the App and injects base CSS

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - `package.json` — create with React/Vite dependencies (new, but in-place of any existing root package.json)
- 要建：
  - `package.json` — npm project manifest with React 18 + Vite 5 + TypeScript 5 + React Router 6 + Tailwind 3
  - `vite.config.ts` — Vite config with `@vitejs/plugin-react` and `@/` alias
  - `tsconfig.json` — TypeScript config extending `tsconfig.node.json`, `"jsx": "react-jsx"`
  - `tsconfig.node.json` — TypeScript config for Vite config file
  - `index.html` — Vite entry HTML with `<div id="root">` and `<script type="module" src="/src/ui/main.tsx">`
  - `postcss.config.js` — PostCSS with Tailwind
  - `tailwind.config.js` — Tailwind config scanning `src/ui/**/*.{ts,tsx}`
  - `src/ui/main.tsx` — React app mount point
  - `src/ui/App.tsx` — `<BrowserRouter>` with `/campaigns` placeholder route
  - `src/ui/index.css` — Tailwind base directives
  - `src/ui/pages/CampaignList.tsx` — placeholder CampaignList page (stub `div`)

### 2.3 缺什么

- [ ] No `package.json` at project root — npm cannot install any frontend packages
- [ ] No Vite configuration — no bundler, no HMR dev server
- [ ] No TypeScript configuration for the frontend
- [ ] No React entry point (`main.tsx`)
- [ ] No `<BrowserRouter>` router setup with routes
- [ ] No Tailwind CSS baseline

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `package.json` | npm manifest: React 18, Vite 5, TypeScript 5, React Router 6, Tailwind 3, @vitejs/plugin-react, @types/* |
| `vite.config.ts` | Vite bundler config with `@vitejs/plugin-react` and `@/` path alias resolving to `src/` |
| `tsconfig.json` | Frontend TypeScript config extending tsconfig.node.json |
| `tsconfig.node.json` | TypeScript config for Vite config files (vite.config.ts) |
| `index.html` | Vite entry HTML, mounts `<div id="root">`, references `/src/ui/main.tsx` |
| `postcss.config.js` | PostCSS config with Tailwind plugin |
| `tailwind.config.js` | Tailwind config scanning `src/ui/**/*.{ts,tsx}` |
| `src/ui/main.tsx` | React 18 app mount: `createRoot(...).render(<App />)` |
| `src/ui/App.tsx` | `<BrowserRouter>` + `<Routes>` + `<Route path="/campaigns" element={<CampaignList />} />` |
| `src/ui/index.css` | Tailwind `@tailwind` directives |
| `src/ui/pages/CampaignList.tsx` | Placeholder stub page (returns `<div>CampaignList — TBD</div>`) |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD | No existing files are modified in this step — all files are created fresh |

### 3.3 新增能力

- **NPM packages**: `react@^18`, `react-dom@^18`, `react-router-dom@^6`, `vite@^5`, `@vitejs/plugin-react@^4`, `tailwindcss@^3`, `postcss@^8`, `autoprefixer@^10`, `typescript@^5`, `@types/react@^18`, `@types/react-dom@^18`
- **Vite dev server**: `npm run dev` → `http://localhost:5173`
- **Route**: `GET /campaigns` renders `<CampaignList />` placeholder (React Router 6)

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Vite over CRA or webpack**: Vite offers native ESM HMR with zero config for React + TypeScript, faster cold starts, and is the current community standard for new React projects.
- **Tailwind CSS v3**: Utility-first CSS — no component library coupling, integrates via PostCSS, works with Vite out of the box.
- **React Router v6**: Standard routing for React; uses `<Route>` + `<Routes>` declarative API (not the v5 `<Switch>` pattern).
- **`@/` alias over relative paths**: Alias `src/` at build time avoids `../../../../` path gymnastics in components; Vite resolves it in both browser and IDE.
- **`npm` over `pnpm` or `yarn`**: Consistent with the backend (no lock file conflict), `package-lock.json` is already gitignored.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `react` | `^18` | Latest stable major; React 18 concurrent features not needed now but `createRoot` requires it |
| `react-dom` | `^18` | Must match react version |
| `react-router-dom` | `^6` | v6 is current stable; v7 is not yet widely adopted in enterprise React |
| `vite` | `^5` | Current stable; `@vitejs/plugin-react@^4` targets it |
| `@vitejs/plugin-react` | `^4` | Enables SWC/Babel transform for JSX without extra config |
| `tailwindcss` | `^3` | v4 requires a different PostCSS setup not yet standard; v3 is stable |
| `typescript` | `^5` | Aligns with Python-side mypy ecosystem and modern TypeScript features |
| `@types/react` / `@types/react-dom` | `^18` | Required for TypeScript type checking in `.tsx` files |

### 4.3 兼容性约束

- `vite.config.ts` must use ESM syntax (`export default defineConfig({ ... })`) — not CommonJS.
- `tsconfig.json` must include `"jsx": "react-jsx"` (the modern JSX transform, not `"react"`).
- `src/ui/main.tsx` must use `createRoot` from `react-dom/client` (React 18 API, not the legacy `ReactDOM.render`).
- Tailwind content globs must include `src/ui/**/*.{ts,tsx}` so all `.tsx` files are scanned for class names.

### 4.4 已知坑

1. **Tailwind JIT not scanning files after rename or new creation** → Symptom: classes missing after adding new component → Workaround: restart the Vite dev server (Tailwind scans on startup); ensure `tailwind.config.js` content glob is broad enough (`src/ui/**/*.{ts,tsx}`).

---

## 5. 实现步骤（按顺序）

### Step 1: Create package.json and install dependencies

Create `package.json` at the project root with all required entries, then run `npm install`.

package.json:
```json
{
  "name": "dev-agent-ui",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.17",
    "typescript": "^5.6.3",
    "vite": "^5.4.11"
  }
}
```

**完成判定**: `npm install` exits 0; `node_modules/react` and `node_modules/vite` exist

---

### Step 2: Create TypeScript configuration files

Create `tsconfig.json` and `tsconfig.node.json`.

`tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

`tsconfig.node.json`:
```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

**完成判定**: `tsc --noEmit` on a stub file exits 0 (requires Step 3 files to exist first — verify after Step 3)

---

### Step 3: Create vite.config.ts

Create `vite.config.ts` with `@vitejs/plugin-react` and `@/` alias:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

Note: `@types/node` is not required as a devDependency for the alias to work at runtime since Vite handles it internally, but add it if `path` is not recognized during `tsc --noEmit`.

**完成判定**: `npx vite --version` exits 0; file compiles without TypeScript errors

---

### Step 4: Create index.html

Create `index.html` at the project root:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>dev-agent-ui</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/ui/main.tsx"></script>
  </body>
</html>
```

**完成判定**: `index.html` exists at project root with correct `<script type="module" src="/src/ui/main.tsx">`

---

### Step 5: Create Tailwind CSS configuration

Create `tailwind.config.js` and `postcss.config.js`.

`tailwind.config.js`:
```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/ui/**/*.{ts,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

`postcss.config.js`:
```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

Create `src/ui/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

**完成判定**: Both config files exist; `src/ui/index.css` contains all three `@tailwind` directives

---

### Step 6: Create React entry point and App component

Create `src/ui/main.tsx` and `src/ui/App.tsx`.

`src/ui/main.tsx`:
```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
```

`src/ui/App.tsx`:
```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import CampaignList from './pages/CampaignList'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/campaigns" element={<CampaignList />} />
        <Route path="/" element={<div>Home — TBD</div>} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
```

Create `src/ui/pages/CampaignList.tsx`:
```tsx
export default function CampaignList() {
  return <div>CampaignList — TBD</div>
}
```

**完成判定**: `src/ui/main.tsx`, `src/ui/App.tsx`, and `src/ui/pages/CampaignList.tsx` all exist; `src/ui/App.tsx` imports `BrowserRouter`, `Routes`, `Route` from `react-router-dom` and registers `/campaigns` path

---

### Step 7: Run npm install and verify dev server starts

```bash
npm install
npm run dev -- --port 5173 &
sleep 5
curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/
```

Expected: `npm install` exits 0; `curl` returns `200`.

**完成判定**: `npm install` exits 0; `npm run dev` starts Vite server on port 5173 with no build errors

---

## 6. 验收

- [ ] `npm install` exits 0; `node_modules/.bin/vite` exists
- [ ] `npx tsc --noEmit` (after all files created) exits 0
- [ ] `npx vite --version` exits 0 and prints Vite version
- [ ] `npm run dev` starts dev server; `curl http://localhost:5173/` returns HTTP 200
- [ ] `src/ui/App.tsx` contains `<BrowserRouter>` with `<Route path="/campaigns" element={<CampaignList />} />`
- [ ] `src/ui/index.css` contains `@tailwind base;`, `@tailwind components;`, `@tailwind utilities;`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `npm install` fails due to network/registry issues in CI | 低 | 中 — CI pipeline blocked | Pin packages to known-good versions; cache `node_modules` in CI; fallback to `--prefer-offline` |
| Port 5173 already in use on developer machine | 低 | 低 — developer inconvenience | Document `npm run dev -- --port <free-port>` override; add `.env` with `VITE_PORT=5174` |
| Tailwind classes not applying in dev (JIT cache stale) | 低 | 中 — UI broken in dev | Restart `npm run dev`; clear `node_modules/.vite` cache directory |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add package.json vite.config.ts tsconfig.json tsconfig.node.json index.html \
       postcss.config.js tailwind.config.js src/ui/
git commit -m "feat(ui): bootstrap React/Vite scaffold under src/ui/"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(ui): bootstrap React/Vite frontend scaffold under src/ui/" \
  --body "Closes #768

## What
- Initialize package.json with React 18, Vite 5, TypeScript 5, React Router 6, Tailwind 3
- Configure vite.config.ts with @/ alias and @vitejs/plugin-react
- Create src/ui/main.tsx (React 18 createRoot entry), src/ui/App.tsx (BrowserRouter + /campaigns route)
- Add Tailwind baseline (postcss.config.js, tailwind.config.js, src/ui/index.css)
- Register placeholder /campaigns route rendering src/ui/pages/CampaignList.tsx stub

## Acceptance
- npm install && npm run dev starts Vite dev server with exit 0" #768
```

---

## 9. 参考

- 同类参考实现：N/A — greenfield frontend; no existing React/Vite code in this repo
- 第三方文档：[Vite Getting Started](https://vite.dev/guide/)
- 第三方文档：[React Router v6](https://reactrouter.com/docs/en/main/start/overview)
- 第三方文档：[Tailwind CSS with Vite](https://tailwindcss.com/docs/guides/vite)
- 父 issue / 关联：#531

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-31 | 创建 | TBD |
