const CACHE_VERSION = 'tablesys-mobile-v1';
const APP_SHELL_CACHE = `app-shell-${CACHE_VERSION}`;
const API_CACHE = `api-${CACHE_VERSION}`;
const APP_SHELL_URLS = ['/', '/student', '/manifest.webmanifest', '/tablesys-pwa-icon.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(APP_SHELL_CACHE).then((cache) => cache.addAll(APP_SHELL_URLS)).catch(() => undefined),
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => ![APP_SHELL_CACHE, API_CACHE].includes(key))
          .map((key) => caches.delete(key)),
      ),
    ),
  );
  self.clients.claim();
});

const isMobileApiRequest = (requestUrl, request) =>
  requestUrl.pathname.startsWith('/api/v1/mobile/') && request.method === 'GET';

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const requestUrl = new URL(request.url);

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(APP_SHELL_CACHE).then((cache) => cache.put('/student', copy)).catch(() => undefined);
          return response;
        })
        .catch(async () => (await caches.match('/student')) || caches.match('/')),
    );
    return;
  }

  if (isMobileApiRequest(requestUrl, request)) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(API_CACHE).then((cache) => cache.put(request, copy)).catch(() => undefined);
          }
          return response;
        })
        .catch(async () => caches.match(request)),
    );
    return;
  }

  if (request.method === 'GET' && requestUrl.origin === self.location.origin) {
    event.respondWith(
      caches.match(request).then(
        (cachedResponse) =>
          cachedResponse ||
          fetch(request).then((response) => {
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }

            const copy = response.clone();
            caches.open(APP_SHELL_CACHE).then((cache) => cache.put(request, copy)).catch(() => undefined);
            return response;
          }),
      ),
    );
  }
});
