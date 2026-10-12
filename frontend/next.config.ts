import type { NextConfig } from "next";

// On Vercel the API lives elsewhere (for example a Hugging Face Space). Proxying /api through the web app keeps the
// browser on one origin, so the sign-in cookie, live run events and screenshots all work without cross-site cookies.
const backend = process.env.BACKEND_URL?.replace(/\/$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return backend ? [{ source: "/api/:path*", destination: `${backend}/api/:path*` }] : [];
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
