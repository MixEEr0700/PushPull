// Test-only: active worker deliberately claims clients only after a message.
// No application assets, cache, IndexedDB or localStorage are touched.
self.addEventListener('message', event => {
  if (event.data === 'claim') event.waitUntil(
    self.clients.claim());
});
