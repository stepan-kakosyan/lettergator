self.addEventListener('install', event => {
  event.waitUntil(
    caches.open('lettergator-v1').then(cache => {
      return cache.addAll([
        '/',
        '/offline/',
        '/static/img/logo512.png',
        '/static/img/favicon.png',
      ]);
    })
  );
});


self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request).catch(() => {
      return caches.match(event.request).then(response => {
        return response || caches.match('/offline/');
      });
    })
  );
});
