/** @type {import("next").NextConfig} */
const nextConfig = {
  typedRoutes: true,
  experimental: {
    serverActions: {
      bodySizeLimit: "2mb"
    }
  },
  // Prevent bundling of server-side only packages
  serverExternalPackages: ['pino', 'pino-pretty', 'thread-stream'],
  // Enable server logging in production
  logging: {
    fetches: {
      fullUrl: true
    }
  },
  // Empty turbopack config to silence the webpack warning
  turbopack: {}
}

export default nextConfig
