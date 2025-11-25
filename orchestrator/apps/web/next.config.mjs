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
  }
}

export default nextConfig
