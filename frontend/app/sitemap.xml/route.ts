export const dynamic = 'force-static';

const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.medicii.net/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>
  <url><loc>https://www.medicii.net/how-it-works</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>
  <url><loc>https://www.medicii.net/security</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>
  <url><loc>https://www.medicii.net/faq</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>
  <url><loc>https://www.medicii.net/contact</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>
  <url><loc>https://www.medicii.net/user-agreement</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>
</urlset>`;

export function GET() {
  return new Response(sitemap, {
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
    },
  });
}
