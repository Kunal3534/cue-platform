/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async redirects() {
    return [
      // Legacy upload route
      {
        source: "/upload",
        destination: "/projects/new",
        permanent: true,
      },
      // Legacy projects/:id → new singular route
      {
        source: "/projects/:id((?!new).*)",
        destination: "/project/:id",
        permanent: false,
      },
    ];
  },
  async rewrites() {
    // In production the browser talks to the API same-origin under /api
    // (NEXT_PUBLIC_API_URL=/api) and this proxy forwards to the API app.
    // Evaluated at build time — set API_PROXY_TARGET as a build arg.
    const target = process.env.API_PROXY_TARGET;
    if (!target) return [];
    return [
      {
        source: "/api/:path*",
        destination: `${target.replace(/\/$/, "")}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
