This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

---

## Setup

1. **Install dependencies**

```bash
npm install
```

2. **Configure environment variables**

```bash
cp .env.local.example .env.local
```

Edit `.env.local` and fill in the required values:
- `NEXT_PUBLIC_API_BASE_URL` — set to `http://localhost:8000` for local development
- `NEXT_PUBLIC_AUTH_KEY` — a random 32-character hex string for client-side obfuscation of auth tokens in localStorage. Generate one with:

```bash
node -e "console.log(require('crypto').randomBytes(16).toString('hex'))"
```

> **Note:** In production, the `next.config.ts` rewrite handles routing automatically and `NEXT_PUBLIC_API_BASE_URL` is not required.

3. **Start the dev server**

```bash
npm run dev
```

The app runs at `http://localhost:3000`. All `/api/*` requests are proxied to the backend (`http://localhost:8000` in development).

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start the Next.js dev server |
| `npm run build` | Build for production |
| `npm run start` | Start the production server |
| `npm run lint` | Run ESLint + Prettier checks |
| `npm run format` | Format all files with Prettier |
| `npm run format:check` | Check formatting (no changes) |
| `npm run test` | Run unit tests (Vitest) |
| `npm run test:watch` | Run tests in watch mode |
