// static/js/ads.js
document.addEventListener("DOMContentLoaded", () => {
  const {
    bannerFiles,
    fullscreenFiles,
    staticUrl,
    initialBanner,
    initialFS
  } = window.adsConfig;

  let bannerIdx = Math.max(1, bannerFiles.indexOf(initialBanner) + 1);
  let fsIdx     = Math.max(1, fullscreenFiles.indexOf(initialFS) + 1);

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
      vid.style.cssText = "width:100%;height:100%;object-fit:cover;";
      cont.appendChild(vid);
    } else {
      const img = document.createElement("img");
      img.src    = url;
      img.alt    = "Pubblicità";
      img.style.cssText = "width:100%;height:100%;object-fit:cover;";
      cont.appendChild(img);
    }
  }

  // override showBanner per ciclare lato “banner”
  const origShowBanner = adManager.showBanner.bind(adManager);
  adManager.showBanner = () => {
    setMedia("ad-container", bannerFiles[bannerIdx % bannerFiles.length], "ads/banners");
    bannerIdx++;
    origShowBanner();
  };

  // override showFullScreen per ciclare lato “full‐screen”
  const origShowFS = adManager.showFullScreen.bind(adManager);
  adManager.showFullScreen = () => {
    const fn = fullscreenFiles[fsIdx % fullscreenFiles.length];
    setMedia("ad-fullscreen", fn, "ads/fullscreen");
    fsIdx++;
    origShowFS();
  };

  // inizializza prima chiamata
  if (initialBanner)   setMedia("ad-container", initialBanner, "ads/banners");
  if (initialFS)       setMedia("ad-fullscreen", initialFS,   "ads/fullscreen");
});
