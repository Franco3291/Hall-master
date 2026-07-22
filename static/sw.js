const CACHE_NAME = 'campus-matrix-v1';
const ASSETS_TO_CACHE = [
  '/app.html',
  '/static/logo.png',
  '/static/manifest.json',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
  'https://cdn.jsdelivr.net/npm/hls.js@latest'
];

// Install event - cache core assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

// Activate event - clean old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(name => name !== CACHE_NAME).map(name => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', event => {
  // Only handle GET requests
  if (event.request.method !== 'GET') return;

  // For API calls, always go to network (no cache)
  if (event.request.url.includes('/api/') || 
      event.request.url.includes('/students/') || 
      event.request.url.includes('/admin/') ||
      event.request.url.includes('/rooms/') ||
      event.request.url.includes('/navigate') ||
      event.request.url.includes('/verify') ||
      event.request.url.includes('/health')) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then(cachedResponse => {
      if (cachedResponse) return cachedResponse;
      return fetch(event.request).then(response => {
        // Cache successful responses for future
        if (response && response.status === 200) {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseClone);
          });
        }
        return response;
      }).catch(() => {
        // Offline fallback for app.html
        if (event.request.url.includes('app.html')) {
          return caches.match('/app.html');
        }
        return new Response('Offline', { status: 503 });
      });
    })
  );
});