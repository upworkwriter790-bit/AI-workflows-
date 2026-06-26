import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The deterministic engine and AI services are framework-agnostic TS, so no
  // special webpack/turbopack config is needed.
};

export default nextConfig;
