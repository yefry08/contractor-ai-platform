/** @type {import('next').NextConfig} */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const isDev = process.env.NODE_ENV !== "production";

// What the site actually loads, and nothing else:
//  - the API (data), Spline (3D scene on the home page) and Cloudflare
//    Turnstile (bot check on forms);
//  - images from several hosts (partner logos, team photos), so img-src
//    allows any https origin -- an image can't run code.
// 'unsafe-inline' stays for scripts because Next.js and the theme script
// inject inline ones; the policy still stops scripts from any other domain,
// framing by other sites, plugins and form posts to third parties.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'${isDev ? " 'unsafe-eval'" : ""} https://challenges.cloudflare.com https://unpkg.com`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  "media-src 'self' data: blob:",
  `connect-src 'self' ${API_URL} https://prod.spline.design https://*.spline.design https://unpkg.com https://challenges.cloudflare.com${isDev ? " ws: http://localhost:* http://127.0.0.1:*" : ""}`,
  "frame-src https://challenges.cloudflare.com",
  "worker-src 'self' blob:",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "object-src 'none'",
  "form-action 'self'",
  ...(isDev ? [] : ["upgrade-insecure-requests"]),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

const nextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
