"""Makes VK Auto Parts installable as a phone/desktop app (a Progressive Web
App) -- free, no app store account needed. The shop owner opens the site in
Chrome (Android) or Safari (iPhone) and taps "Add to Home Screen" / "Install
app"; after that it has its own icon, opens full-screen with no browser bar,
and works from any device without anyone re-typing the web address.

This is intentionally NOT full offline support: stock levels, invoices, and
customer balances live in the shared database, so showing old cached data
while offline would be actively misleading for a live shop. The service
worker below only speeds up loading of static assets (css/icons) and lets
the browser consider the app "installable" -- every real page load always
goes to the network for current data.
"""

import json
from flask import Blueprint, Response, url_for, request, g
from db import get_setting, get_db
import themes

bp = Blueprint("pwa", __name__)


@bp.route("/manifest.webmanifest")
def manifest():
    db = get_db()
    shop_name = get_setting(db, "shop_name", "VK Auto Parts")
    logo_data = get_setting(db, "logo_data", "")
    theme = themes.get_theme(get_setting(db, "pos_theme", themes.DEFAULT_THEME))

    icons = [
        {"src": url_for("static", filename="img/icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": url_for("static", filename="img/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
    ]
    if logo_data:
        # the shop's own uploaded logo, shown as the install icon too if present
        icons.insert(0, {"src": logo_data, "sizes": "any", "type": "image/png", "purpose": "any"})

    manifest_data = {
        "name": shop_name,
        "short_name": shop_name[:12] if shop_name else "VK Parts",
        "description": "Inventory, billing and accounts for " + (shop_name or "VK Auto Parts"),
        "start_url": url_for("dashboard.index"),
        "id": "/",
        "display": "standalone",
        "background_color": theme["surface"],
        "theme_color": theme["primary"],
        "orientation": "any",
        "icons": icons,
    }
    return Response(json.dumps(manifest_data), mimetype="application/manifest+json")


@bp.route("/sw.js")
def service_worker():
    js = """
const CACHE_NAME = 'vkap-static-v1';
const STATIC_ASSETS = [
  '/static/css/style.css',
  '/static/img/icon-192.png',
  '/static/img/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

// Only ever serve cached copies of our own static assets (css/icons).
// Every page request (dashboard, POS, invoices, stock...) always goes to
// the network, since this app's data changes constantly and must never be
// shown stale.
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (!STATIC_ASSETS.some((p) => url.pathname === p)) return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const network = fetch(event.request).then((resp) => {
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, resp.clone()));
        return resp;
      }).catch(() => cached);
      return cached || network;
    })
  );
});
"""
    return Response(js, mimetype="application/javascript")
