import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination:
          process.env.NODE_ENV === "development"
            ? "http://localhost:8000/api/:path*"
            : "https://agent-job-production.up.railway.app/api/:path*",
      },
    ];
  },
};

export default nextConfig;
