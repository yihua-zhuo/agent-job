import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const backendOrigin =
      process.env.NEXT_PUBLIC_BACKEND_ORIGIN ??
      (process.env.NODE_ENV === "development"
        ? "http://localhost:8000"
        : "https://agent-job-production.up.railway.app");
    return [
      {
        source: "/api/:path*",
        destination: `${backendOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
