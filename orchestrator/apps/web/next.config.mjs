/** @type {import("next").NextConfig} */
const nextConfig = {
  typedRoutes: true,
  experimental: {
    serverActions: {
      bodySizeLimit: "2mb"
    }
  },
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
