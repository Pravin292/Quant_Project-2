import type { NextConfig } from "next";

// In production vercel.json routes /api/* to the Python function.
// In development the same paths are proxied to a local uvicorn (`make run`).
const nextConfig: NextConfig = {
  agentRules: false, // do not let `next dev` write AGENTS.md into the repo
  async rewrites() {
    return process.env.NODE_ENV === "development"
      ? [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" }]
      : [];
  },
};

export default nextConfig;
