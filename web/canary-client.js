"use strict";

// This runs only when a person or browser opens the local canary page.
// It reports a fixed list of browser-provided environment values and, if
// permitted, location to the same local server. It does not read files,
// cookies or communication contents.
(async () => {
  const script = document.currentScript;
  const eventId = Number(script?.dataset.eventId);
  const nonce = script?.dataset.nonce || "";
  if (!Number.isSafeInteger(eventId) || eventId < 1 || !/^[A-Za-z0-9_-]{32}$/.test(nonce)) return;

  const locationNonce = script?.dataset.locationNonce || "";
  const locationButton = document.getElementById("canary-location-request");
  const locationStatus = document.getElementById("canary-location-status");
  const japanese = document.documentElement.lang === "ja";
  if (/^[A-Za-z0-9_-]{32}$/.test(locationNonce) && locationButton && locationStatus) {
    let locationInFlight = false;
    let locationSent = false;
    const reportLocation = async (status, position = {}) => {
      try {
        const response = await fetch("/api/local-canary-location", {
          method: "POST", headers: {"Content-Type": "application/json"}, credentials: "omit",
          referrerPolicy: "no-referrer", keepalive: true,
          body: JSON.stringify({event_id: eventId, nonce: locationNonce, status, position}),
        });
        return response.ok;
      } catch (_) { return false; }
    };
    const requestLocation = () => {
      if (locationInFlight || locationSent) return;
      if (!window.isSecureContext || !navigator.geolocation) {
        locationStatus.textContent = japanese ? "位置情報を利用できません。" : "Location is unavailable.";
        locationButton.disabled = true;
        void reportLocation("unsupported");
        return;
      }
      locationInFlight = true;
      locationButton.disabled = true;
      locationStatus.textContent = japanese ? "位置情報の許可を確認しています。" : "Waiting for location permission.";
      try {
        navigator.geolocation.getCurrentPosition(async result => {
          const coords = result.coords;
          const position = {latitude: coords.latitude, longitude: coords.longitude,
            accuracy: coords.accuracy, timestamp: result.timestamp};
          for (const [key, value] of [["altitude", coords.altitude], ["altitude_accuracy", coords.altitudeAccuracy],
            ["heading", coords.heading], ["speed", coords.speed]]) {
            if (typeof value === "number" && Number.isFinite(value)) position[key] = value;
          }
          const ok = await reportLocation("granted", position);
          locationInFlight = false;
          locationSent = ok;
          locationButton.disabled = ok;
          locationStatus.textContent = ok
            ? (japanese ? "位置情報を記録しました。" : "Location recorded.")
            : (japanese ? "位置情報を記録できませんでした。" : "Location could not be recorded.");
        }, async error => {
          const status = error.code === 1 ? "denied" : error.code === 3 ? "timeout" : "unavailable";
          await reportLocation(status);
          locationInFlight = false;
          locationButton.disabled = false;
          locationStatus.textContent = status === "denied"
            ? (japanese ? "位置情報の使用が許可されませんでした。" : "Location permission was not granted.")
            : (japanese ? "位置情報を取得できませんでした。" : "Location could not be obtained.");
        }, {enableHighAccuracy: true, timeout: 30000, maximumAge: 0});
      } catch (_) {
        locationInFlight = false;
        locationButton.disabled = false;
        locationStatus.textContent = japanese ? "位置情報を取得できませんでした。" : "Location could not be obtained.";
        void reportLocation("unavailable");
      }
    };
    locationButton.hidden = false;
    locationButton.addEventListener("click", requestLocation);
    requestLocation();
  }

  const environment = {};
  const put = (key, value) => {
    if (typeof value === "string" && value) environment[key] = value.slice(0, 512);
    else if (typeof value === "boolean") environment[key] = value;
    else if (typeof value === "number" && Number.isFinite(value) && Math.abs(value) <= 10000000) environment[key] = value;
  };
  const read = (key, getter) => { try { put(key, getter()); } catch (_) { /* Not exposed by this browser. */ } };

  read("language", () => navigator.language);
  read("languages", () => Array.from(navigator.languages || []).slice(0, 16).join(", "));
  read("platform", () => navigator.platform);
  read("vendor", () => navigator.vendor);
  read("user_agent", () => navigator.userAgent);
  read("plugins", () => Array.from(navigator.plugins || []).slice(0, 20).map(item => item.name).join(", "));
  read("mime_types", () => Array.from(navigator.mimeTypes || []).slice(0, 20).map(item => item.type).join(", "));
  read("do_not_track", () => navigator.doNotTrack);
  read("timezone", () => Intl.DateTimeFormat().resolvedOptions().timeZone);
  read("timezone_offset", () => new Date().getTimezoneOffset());
  read("screen_width", () => screen.width);
  read("screen_height", () => screen.height);
  read("screen_available_width", () => screen.availWidth);
  read("screen_available_height", () => screen.availHeight);
  read("screen_orientation", () => screen.orientation?.type);
  read("viewport_width", () => window.innerWidth);
  read("viewport_height", () => window.innerHeight);
  read("color_depth", () => screen.colorDepth);
  read("pixel_ratio", () => window.devicePixelRatio);
  read("hardware_concurrency", () => navigator.hardwareConcurrency);
  read("device_memory", () => navigator.deviceMemory);
  read("max_touch_points", () => navigator.maxTouchPoints);
  read("touch_capable", () => "ontouchstart" in window || navigator.maxTouchPoints > 0);
  read("webdriver", () => navigator.webdriver);
  read("cookies_enabled", () => navigator.cookieEnabled);
  read("online", () => navigator.onLine);
  read("pdf_viewer", () => navigator.pdfViewerEnabled);
  read("global_privacy_control", () => navigator.globalPrivacyControl);
  read("reduced_motion", () => matchMedia("(prefers-reduced-motion: reduce)").matches);
  read("dark_mode", () => matchMedia("(prefers-color-scheme: dark)").matches);
  read("connection_type", () => navigator.connection?.effectiveType);
  read("connection_downlink", () => navigator.connection?.downlink);
  read("connection_rtt", () => navigator.connection?.rtt);
  read("connection_save_data", () => navigator.connection?.saveData);

  try {
    const gl = document.createElement("canvas").getContext("webgl", {failIfMajorPerformanceCaveat: true});
    if (gl) {
      put("webgl_vendor", gl.getParameter(gl.VENDOR));
      put("webgl_renderer", gl.getParameter(gl.RENDERER));
      put("webgl_version", gl.getParameter(gl.VERSION));
      const debug = gl.getExtension("WEBGL_debug_renderer_info");
      if (debug) {
        put("gpu_vendor", gl.getParameter(debug.UNMASKED_VENDOR_WEBGL));
        put("gpu_renderer", gl.getParameter(debug.UNMASKED_RENDERER_WEBGL));
      }
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    }
  } catch (_) { /* Graphics information may be unavailable or blocked. */ }

  try {
    const ua = navigator.userAgentData;
    if (ua) {
      put("ua_mobile", ua.mobile);
      put("ua_platform", ua.platform);
      put("ua_brands", (ua.brands || []).slice(0, 16).map(item => `${item.brand} ${item.version}`).join(", "));
      if (typeof ua.getHighEntropyValues === "function") {
        const requested = ["architecture", "bitness", "model", "platformVersion", "fullVersionList", "wow64", "formFactors"];
        const pending = requested.map(hint => Promise.resolve().then(() => ua.getHighEntropyValues([hint])).then(hints => {
          put("ua_architecture", hints.architecture);
          put("ua_bitness", hints.bitness);
          put("ua_model", hints.model);
          put("ua_platform_version", hints.platformVersion);
          put("ua_wow64", hints.wow64);
          put("ua_form_factors", (hints.formFactors || []).slice(0, 16).join(", "));
          put("ua_full_versions", (hints.fullVersionList || []).slice(0, 16).map(item => `${item.brand} ${item.version}`).join(", "));
        }).catch(() => {}));
        await Promise.race([Promise.all(pending), new Promise(resolve => setTimeout(resolve, 1500))]);
      }
    }
  } catch (_) { /* Optional client hints may be unavailable or denied. */ }

  try {
    await fetch("/api/local-canary-browser", {
      method: "POST", headers: {"Content-Type": "application/json"}, credentials: "omit",
      referrerPolicy: "no-referrer", keepalive: true,
      body: JSON.stringify({event_id: eventId, nonce, environment}),
    });
  } catch (_) { /* The initial HTTP contact is recorded independently. */ }
})();
