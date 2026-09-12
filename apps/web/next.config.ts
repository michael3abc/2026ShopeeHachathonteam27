import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Next gzips proxied responses, and a gzip buffer never flushes, so the SSE
  // stream reaches EventSource as a header and nothing else.
  compress: false,
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: `${process.env.API_BASE_URL ?? "http://127.0.0.1:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
