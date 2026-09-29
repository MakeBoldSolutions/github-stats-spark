/**
 * Service Worker for GitHub Stats Spark Dashboard
 * Provides offline functionality and asset precaching
 */

// Base path for custom domain
const BASE_PATH = '/';

// Service Worker Version - replaced by Vite at build time with v1790646584167
const CACHE_VERSION = 'v1790646584167';
const CACHE_NAME = `github-stats-spark-${CACHE_VERSION}`;

// Assets to precache on install
const PRECACHE_ASSETS = [
  BASE_PATH,
  `${BASE_PATH}index.html`,
  `${BASE_PATH}manifest.json`,
  `${BASE_PATH}favicon.svg`
];

// Runtime cache configuration
const RUNTIME_CACHE = {
  maxEntries: 50,
  maxAgeSeconds: 7 * 24 * 60 * 60 // 7 days
};

/**
 * Install Event - Precache assets
 */
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[Service Worker] Precaching assets');
        return cache.addAll(PRECACHE_ASSETS.filter(url => !url.includes('*')));
      })
      .then(() => self.skipWaiting()) // Activate immediately
  );
});

/**
 * Activate Event - Cleanup old caches
 */
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating...');
  
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((cacheName) => cacheName !== CACHE_NAME)
            .map((cacheName) => {
              console.log('[Service Worker] Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            })
        );
      })
      .then(() => self.clients.claim()) // Take control immediately
  );
});

/**
 * Fetch Event - Cache-first strategy with network fallback
 */
self.addEventListener('fetch', (event) => {
  const { request } = event;
  
  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }
  
  // Skip cross-origin requests
  const url = new URL(request.url);
  if (!url.pathname.startsWith(BASE_PATH)) {
    return;
  }
  
  if (url.pathname.includes('/data/') && url.pathname.endsWith('/repositories.json')) {
    event.respondWith(fetch(request, { cache: 'no-store' }));
    return;
  }

  event.respondWith(
    caches.match(request)
      .then((cachedResponse) => {
        if (cachedResponse) {
          // Return cached response and update in background
          const fetchPromise = fetch(request)
            .then((networkResponse) => {
              if (networkResponse && networkResponse.status === 200) {
                const responseToCache = networkResponse.clone();
                caches.open(CACHE_NAME).then((cache) => {
                  cache.put(request, responseToCache);
                });
              }
              return networkResponse;
            })
            .catch(() => cachedResponse); // Return cached on network error
          
          return cachedResponse;
        }
        
        // Not in cache - fetch from network
        return fetch(request)
          .then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              const responseToCache = networkResponse.clone();
              caches.open(CACHE_NAME).then((cache) => {
                cache.put(request, responseToCache);
              });
            }
            return networkResponse;
          });
      })
      .catch((error) => {
        console.error('[Service Worker] Fetch error:', error);
        
        // Return offline fallback for navigation requests
        if (request.mode === 'navigate') {
          return caches.match(`${BASE_PATH}index.html`);
        }
        
        throw error;
      })
  );
});

/**
 * Message Event - Handle messages from clients
 */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'CACHE_URLS') {
    event.waitUntil(
      caches.open(CACHE_NAME).then((cache) => {
        return cache.addAll(event.data.urls);
      })
    );
  }
  
  if (event.data && event.data.type === 'GET_VERSION') {
    event.ports[0].postMessage({ version: CACHE_VERSION });
  }
});

/**
 * Background Sync Event - Handle background sync
 */
self.addEventListener('sync', (event) => {
  console.log('[Service Worker] Background sync:', event.tag);
  
  if (event.tag === 'sync-repositories') {
    event.waitUntil(
      fetch(`${BASE_PATH}data/repositories.json`)
        .then((response) => response.json())
        .then((data) => {
          return caches.open(CACHE_NAME).then((cache) => {
            return cache.put(`${BASE_PATH}data/repositories.json`, new Response(JSON.stringify(data)));
          });
        })
        .then(() => {
          // Notify clients of successful sync
          return self.clients.matchAll().then((clients) => {
            clients.forEach((client) => {
              client.postMessage({
                type: 'SYNC_COMPLETE',
                tag: event.tag
              });
            });
          });
        })
        .catch((error) => {
          console.error('[Service Worker] Sync failed:', error);
        })
    );
  }
});

console.log('[Service Worker] Loaded version:', CACHE_VERSION);
