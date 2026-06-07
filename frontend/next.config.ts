import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  turbopack: {
    root: path.join(__dirname),
  },
  async rewrites() {
    if (!process.env.NEXT_PUBLIC_BACKEND_ORIGIN) {
      throw new Error(
        "NEXT_PUBLIC_BACKEND_ORIGIN is not set. Set it in .env.local (or your deployment environment) before starting the app."
      );
    }
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_BACKEND_ORIGIN}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
