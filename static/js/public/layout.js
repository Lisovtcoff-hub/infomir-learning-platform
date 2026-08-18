(function () {
  const CACHE_VERSION = 'v3';
  const CACHE_PREFIX = `infomir:layout:${CACHE_VERSION}:`;

  function getCacheKey(url) {
    return `${CACHE_PREFIX}${url}`;
  }

  function getCachedPartial(url) {
    try {
      return sessionStorage.getItem(getCacheKey(url));
    } catch (_) {
      return null;
    }
  }

  function setCachedPartial(url, html) {
    try {
      sessionStorage.setItem(getCacheKey(url), html);
    } catch (_) {
      // ignore storage errors
    }
  }

  async function fetchWithTimeout(url, timeoutMs) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, {
        cache: 'default',
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeoutId);
    }
  }

  async function loadPartial(url, mountId) {
    const mount = document.getElementById(mountId);
    if (!mount) return;
    const cached = getCachedPartial(url);
    if (cached) {
      mount.outerHTML = cached;
      return;
    }

    const res = await fetchWithTimeout(url, 4000);
    if (!res.ok) throw new Error(`Failed to load ${url}`);
    const html = await res.text();
    setCachedPartial(url, html);
    mount.outerHTML = html;
  }

  async function initLayout() {
    try {
      await Promise.all([
        loadPartial('/templates/partials/header.html', 'siteHeaderMount'),
        loadPartial('/templates/partials/footer.html', 'siteFooterMount'),
      ]);
      document.dispatchEvent(new Event('infomir:layout-ready'));
    } catch (err) {
      console.error('Layout load error:', err);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLayout, { once: true });
  } else {
    initLayout();
  }
})();


