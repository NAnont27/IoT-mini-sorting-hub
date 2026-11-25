import type { NextConfig } from "next";

const backendUrl = (process.env.BACKEND_URL ?? "http://127.0.0.1:5000").replace(/\/$/, "");
// D026: OCR runs on this PC (Paddle segfaults on the Pi). ai/run_test_server.py serves /api/ai/test.
const aiServiceUrl = (process.env.AI_SERVICE_URL ?? "http://127.0.0.1:5100").replace(/\/$/, "");

const nextConfig: NextConfig = {
  outputFileTracingRoot: __dirname,
  // OCR test page: PaddleOCR on the Pi (first model load) can exceed the 30 s default proxy timeout.
  experimental: { proxyTimeout: 120_000 },
  async rewrites() {
    return [
      // First match wins: the OCR test page goes to the PC AI service, everything else to the Pi.
      { source: "/api/ai/test", destination: `${aiServiceUrl}/api/ai/test` },
      { source: "/api/:path*", destination: `${backendUrl}/api/:path*` },
    ];
  },
};

export default nextConfig;
