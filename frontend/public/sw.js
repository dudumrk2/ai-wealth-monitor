/*
 * Service worker — app-shell + static-asset caching for the installed PWA.
 *
 * Strategy:
 *   - Navigations  → network-first (always pick up the latest index.html, which
 *                    points at the newest hashed assets), falling back to the
 *                    cached shell when offline.
 *   - Static assets (hashed JS/CSS/img) → cache-first; they're immutable so the
 *                    installed app paints instantly without hitting the network.
 *
 * Only same-origin GETs are touched. The backend API and Firebase live on other
 * origins and are deliberately never cached — no financial data is stored here.
 */
const CACHE = 'wm-static-v1';
const SHELL_URL = '/index.html';

// Cap the asset cache so it can't grow unbounded across deploys (old hashed
// chunks are never referenced again once index.html updates). Cache.keys()
// returns entries in insertion order, so we evict oldest-first — but never the
// app shell, which must stay available for offline navigations.
const MAX_ASSET_ENTRIES = 60;

async function putAndTrim(cache, request, response) {
  await cache.put(request, response);
  let keys = await cache.keys();
  while (keys.length > MAX_ASSET_ENTRIES) {
    const victim = keys.find((k) => new URL(k.url).pathname !== SHELL_URL);
    if (!victim) break;
    await cache.delete(victim);
    keys = keys.filter((k) => k !== victim);
  }
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.add(SHELL_URL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // never cache API / Firebase

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(SHELL_URL, copy));
          return res;
        })
        .catch(() => caches.match(SHELL_URL))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ||
        fetch(request).then((res) => {
          if (res.ok && res.type === 'basic') {
            const copy = res.clone();
            caches.open(CACHE).then((c) => putAndTrim(c, request, copy));
          }
          return res;
        })
    )
  );
});
