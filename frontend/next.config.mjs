/** @type {import('next').NextConfig} */
import { APP_PATHS } from './src/lib/routes.js';

const nextConfig = {
  reactCompiler: true,
  output: 'standalone',
  async redirects() {
    return [
      {
        source: APP_PATHS.projects,
        destination: APP_PATHS.modules,
        permanent: false,
      },
      {
        source: `${APP_PATHS.projects}/:path*`,
        destination: `${APP_PATHS.modules}/:path*`,
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
