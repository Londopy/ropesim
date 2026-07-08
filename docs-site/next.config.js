/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',              // fully static — no Node server
  images: { unoptimized: true }, // required for static export
  basePath: process.env.NODE_ENV === 'production' ? '/ropesim' : '',
  trailingSlash: true,
};

module.exports = nextConfig;
