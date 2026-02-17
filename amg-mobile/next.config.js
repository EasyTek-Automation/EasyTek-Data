/** @type {import('next').NextConfig} */
const nextConfig = {
  // Output standalone para Docker
  output: 'standalone',

  // Desabilitar telemetria
  telemetry: false,

  // Configuração de imagens
  images: {
    domains: [],
    unoptimized: true, // Para ambientes sem otimização de imagem
  },

  // Strict mode
  reactStrictMode: true,

  // Configuração de paths
  async rewrites() {
    return [
      // Proxy para API do Flask (em desenvolvimento)
      {
        source: '/api/v1/:path*',
        destination: process.env.NEXT_PUBLIC_API_URL || 'http://webapp:8050/api/v1/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
