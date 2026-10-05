/* Optional fragment bridge. The header, download and original work without JS. */
(() => {
  'use strict';
  const frame = document.getElementById('reader-report');
  const original = new URL(frame.getAttribute('src'), location.href);
  const isOriginal = () => {
    try {
      return frame.contentWindow.location.origin === original.origin &&
        frame.contentWindow.location.pathname === original.pathname;
    } catch (_) { return false; }
  };
  function showFragment() {
    if (!isOriginal() || location.hash === '#reader-report') return;
    if (frame.contentWindow.location.hash !== location.hash) {
      // replace avoids adding a second entry to the browser's joint history.
      frame.contentWindow.location.replace(original.href + location.hash);
    }
  }
  function reflectFragment() {
    if (!isOriginal()) return;
    const hash = frame.contentWindow.location.hash;
    if (location.hash !== hash) history.replaceState(null, '', location.pathname + location.search + hash);
  }
  frame.addEventListener('load', () => {
    showFragment();
    if (isOriginal()) frame.contentWindow.addEventListener('hashchange', reflectFragment);
  });
  window.addEventListener('hashchange', showFragment);
  // A cached iframe may have loaded before this deferred script ran.
  if (frame.contentDocument?.readyState === 'complete' && isOriginal()) {
    showFragment();
    frame.contentWindow.addEventListener('hashchange', reflectFragment);
  }
  document.querySelector('.reader-skip').addEventListener('click', event => {
    event.preventDefault();
    frame.focus();
  });
})();
