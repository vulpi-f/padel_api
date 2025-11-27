// static/js/ads.js
document.addEventListener("DOMContentLoaded", () => {
  const {
    bannerFiles,
    fullscreenFiles,
    staticUrl,
    initialBanner,
    initialFS,
    bannerSize = { width: 1024, height: 259 }
  } = window.adsConfig;

  let bannerIdx = Math.max(1, bannerFiles.indexOf(initialBanner) + 1);
  let fsIdx     = Math.max(1, fullscreenFiles.indexOf(initialFS) + 1);
  let validBannerFiles = [];
  let validated = false;
  const bannerRatio = bannerSize.width > 0 ? (bannerSize.height / bannerSize.width) : 0;

  function setBannerHeight() {
    const cont = document.getElementById("ad-container");
    if (!cont || !bannerRatio) return;
    const width = cont.offsetWidth || window.innerWidth || bannerSize.width;
    const height = Math.round(width * bannerRatio);
    cont.style.height = `${height}px`;
    document.documentElement.style.setProperty('--banner-height', `${height}px`);
  }

  const resizeHandler = () => {
    if (document.querySelector('.game-content')?.classList.contains('show-ads')) {
      setBannerHeight();
    }
  };
  window.addEventListener('resize', resizeHandler);

  function loadImageMeta(url) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
      img.onerror = reject;
      img.src = url;
    });
  }

  function loadVideoMeta(url) {
    return new Promise((resolve, reject) => {
      const vid = document.createElement("video");
      vid.preload = "metadata";
      vid.onloadedmetadata = () => resolve({ width: vid.videoWidth, height: vid.videoHeight });
      vid.onerror = reject;
      vid.src = url;
    });
  }

  async function isBannerValid(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const url = `${staticUrl}ads/banners/${filename}`;
    try {
      const meta = ["mp4", "webm"].includes(ext)
        ? await loadVideoMeta(url)
        : await loadImageMeta(url);
      return meta.width === bannerSize.width && meta.height === bannerSize.height;
    } catch (e) {
      console.warn(`Banner non valido o non caricato: ${filename}`, e);
      return false;
    }
  }

  async function buildValidBannerList() {
    if (validated) return;
    const valids = [];
    for (const file of bannerFiles) {
      if (await isBannerValid(file)) valids.push(file);
    }
    validBannerFiles = valids;
    validated = true;
  }

  function nextValidBanner() {
    if (!validBannerFiles.length) return null;
    const file = validBannerFiles[bannerIdx % validBannerFiles.length];
    bannerIdx++;
    return file;
  }

  function setMedia(containerId, filename, subdir) {
    const ext  = filename.split('.').pop().toLowerCase();
    const url  = staticUrl + subdir + "/" + filename;
    const cont = document.getElementById(containerId);
    cont.innerHTML = ""; // svuota

    if (["mp4","webm"].includes(ext)) {
      const vid = document.createElement("video");
      vid.src    = url;
      vid.autoplay = true;
      vid.loop     = true;
      vid.muted    = true;
      vid.style.cssText = "width:100%;height:100%;object-fit:contain;";
      cont.appendChild(vid);
    } else {
      const img = document.createElement("img");
      img.src    = url;
      img.alt    = "Pubblicità";
      img.style.cssText = "width:100%;height:100%;object-fit:contain;";
      cont.appendChild(img);
    }
  }

  // override showBanner per ciclare lato “banner”
  const origShowBanner = adManager.showBanner.bind(adManager);
  adManager.showBanner = (persistent = false) => {
    buildValidBannerList().then(() => {
      const file = nextValidBanner();
      if (!file) {
        console.warn("Nessun banner con dimensioni valide disponibile");
        return;
      }
      setMedia("ad-container", file, "ads/banners");
      setBannerHeight();
      origShowBanner(persistent);
    });
  };

  // override showFullScreen per ciclare lato “full-screen”
  const origShowFS = adManager.showFullScreen.bind(adManager);
  adManager.showFullScreen = () => {
    const fn = fullscreenFiles[fsIdx % fullscreenFiles.length];
    setMedia("ad-fullscreen", fn, "ads/fullscreen");
    fsIdx++;
    origShowFS();
  };

  // inizializza prima chiamata
  (async () => {
    await buildValidBannerList();
    const initialValid = initialBanner && validBannerFiles.includes(initialBanner)
      ? initialBanner
      : validBannerFiles[0];
    if (initialValid) {
      setMedia("ad-container", initialValid, "ads/banners");
      setBannerHeight();
    }
    if (initialFS) setMedia("ad-fullscreen", initialFS,   "ads/fullscreen");
  })();
});
