/* Offline support for "Add to Home Screen" (2026-10-02).

   The point: your shopping list has to open in an aisle with no signal. The list itself
   lives in localStorage, so what has to be cached is the app and its product data.

   - Pages and scripts (home.html, recipe.html, proto_shared.js): network first, so a new
     version shows up as soon as there's signal; the cached copy only when offline.
   - Product data and images (data/, assets/): served from the cache instantly and refreshed
     in the background (stale-while-revalidate) - the catalog is ~25 MB, too slow to wait for.
   - /api/* (recipe links, AI clean-up, label scan) is never cached: those need the server.

   Browsers only allow service workers on https or localhost, so on the home-Wi-Fi address
   this file does nothing; it switches on once the app is hosted. Bump VERSION to drop old caches. */
const VERSION = 'gs-v1';
const SHELL = ['home.html', 'recipe.html', 'proto_shared.js', 'manifest.webmanifest',
  'data/meals.json', 'data/makeable.json', 'data/meal_recipes.json', 'data/profiles.json',
  'scripts/flagged_ingredients.json', 'assets/icons/icon-192.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return;
  const page = /\.(html|js|webmanifest)$/.test(url.pathname) || url.pathname.endsWith('/');
  if (page) {
    e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open(VERSION).then(c => c.put(e.request, copy)); return r; })
      .catch(() => caches.match(e.request, { ignoreSearch: true })));
    return;
  }
  e.respondWith(caches.open(VERSION).then(async c => {
    const hit = await c.match(e.request);
    const fresh = fetch(e.request).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; }).catch(() => hit);
    return hit || fresh;
  }));
});
