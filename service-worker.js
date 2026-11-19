const CACHE_NAME = "flowboard-v11";
const APP_SHELL = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./assets/icons/flowboard-mark.svg?v=1",
  "./assets/icons/flowboard-mark-192.png?v=1",
  "./assets/icons/flowboard-mark-512.png?v=1",
  "./css/style.css?v=9",
  "./css/base.css?v=9",
  "./css/components.css?v=9",
  "./css/overlays.css?v=9",
  "./css/variables.css?v=9",
  "./js/main.js",
  "./js/api.js",
  "./js/automations.js",
  "./js/boards.js",
  "./js/drag-drop.js",
  "./js/filters.js",
  "./js/i18n.js",
  "./js/sorting.js",
  "./js/state.js",
  "./js/statistics.js",
  "./js/storage.js",
  "./js/tasks.js",
  "./js/ui.js",
  "./js/workflow.js"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)),
    )),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match("./index.html"))),
  );
});

self.addEventListener("push", (event) => {
  const payload = event.data?.json?.() ?? { title: "Flowboard", body: event.data?.text?.() ?? "" };
  event.waitUntil(self.registration.showNotification(payload.title || "Flowboard", {
    body: payload.body || "",
    data: { url: payload.url || "./" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data?.url || "./"));
});
