/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
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
};

module.exports = nextConfig;
