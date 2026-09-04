export const dynamic = 'force-static';

const robots = `User-agent: *
Allow: /

Disallow: /admin/
Disallow: /dashboard
Disallow: /checkout
Disallow: /orders
Disallow: /profile
Disallow: /quotes
Disallow: /login
Disallow: /register
Disallow: /forgot-password
Disallow: /reset-password

Sitemap: https://www.medicii.net/sitemap.xml
`;

export function GET() {
  return new Response(robots, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
    },
  });
}
