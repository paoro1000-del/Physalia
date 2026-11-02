"use strict";
(() => {
  const script = document.currentScript;
  const eventId = script?.dataset.eventId || "";
  const nonce = script?.dataset.nonce || "";
  if (!/^[A-Za-z0-9_-]{20,40}$/.test(eventId) || !/^[A-Za-z0-9_-]{24,40}$/.test(nonce)) return;

  const japanese = !navigator.language.toLowerCase().startsWith("en");
  document.documentElement.lang = japanese ? "ja" : "en";
  document.title = japanese ? "カナリアページ" : "Canary page";
  for (const element of document.querySelectorAll("[data-ja][data-en]")) {
    element.textContent = japanese ? element.dataset.ja : element.dataset.en;
  }
  document.getElementById("event-reference").textContent = japanese ? `記録ID: ${eventId}` : `Event ID: ${eventId}`;
  const button = document.getElementById("location-button");
  const status = document.getElementById("location-status");
  const send = async (environment, location) => {
    try {
      await fetch("/api/contact", {
        method:"POST", headers:{"Content-Type":"application/json"}, credentials:"omit",
        referrerPolicy:"no-referrer", keepalive:true,
        body:JSON.stringify({event_id:eventId, nonce, environment, location}),
      });
    } catch (_) { /* The page request itself is logged by the server. */ }
  };
  const environment = {
    language:navigator.language || "", languages:Array.isArray(navigator.languages) ? navigator.languages.slice(0, 10).join(",") : "",
    platform:navigator.platform || "", vendor:navigator.vendor || "", user_agent:navigator.userAgent || "",
    plugins:Array.from(navigator.plugins || []).slice(0, 20).map(item => item.name).join(", "),
    mime_types:Array.from(navigator.mimeTypes || []).slice(0, 20).map(item => item.type).join(", "),
    do_not_track:navigator.doNotTrack || "", timezone:(() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (_) { return ""; } })(),
    screen_orientation:screen.orientation?.type || "",
    screen_width:screen.width, screen_height:screen.height, screen_available_width:screen.availWidth,
    screen_available_height:screen.availHeight, viewport_width:innerWidth, viewport_height:innerHeight,
    color_depth:screen.colorDepth, pixel_ratio:devicePixelRatio, timezone_offset:new Date().getTimezoneOffset(),
    hardware_concurrency:navigator.hardwareConcurrency || 0, device_memory:navigator.deviceMemory || 0,
    max_touch_points:navigator.maxTouchPoints || 0, webdriver:Boolean(navigator.webdriver),
    cookies_enabled:Boolean(navigator.cookieEnabled), online:Boolean(navigator.onLine),
    pdf_viewer:Boolean(navigator.pdfViewerEnabled), global_privacy_control:Boolean(navigator.globalPrivacyControl),
    touch_capable:navigator.maxTouchPoints > 0, reduced_motion:matchMedia("(prefers-reduced-motion: reduce)").matches,
    dark_mode:matchMedia("(prefers-color-scheme: dark)").matches,
  };
  const connection = navigator.connection;
  if (connection) {
    environment.connection_type = connection.effectiveType || "";
    environment.connection_downlink = connection.downlink;
    environment.connection_rtt = connection.rtt;
    environment.connection_save_data = Boolean(connection.saveData);
  }
  try {
    const gl = document.createElement("canvas").getContext("webgl", {failIfMajorPerformanceCaveat:true});
    if (gl) {
      environment.webgl_vendor = gl.getParameter(gl.VENDOR);
      environment.webgl_renderer = gl.getParameter(gl.RENDERER);
      environment.webgl_version = gl.getParameter(gl.VERSION);
      const debug = gl.getExtension("WEBGL_debug_renderer_info");
      if (debug) { environment.gpu_vendor = gl.getParameter(debug.UNMASKED_VENDOR_WEBGL); environment.gpu_renderer = gl.getParameter(debug.UNMASKED_RENDERER_WEBGL); }
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    }
  } catch (_) { /* Graphics values may be blocked or unavailable. */ }
  if (navigator.userAgentData) {
    environment.ua_mobile = Boolean(navigator.userAgentData.mobile);
    environment.ua_platform = navigator.userAgentData.platform || "";
    environment.ua_brands = (navigator.userAgentData.brands || []).slice(0, 16).map(item => `${item.brand} ${item.version}`).join(", ");
    void navigator.userAgentData.getHighEntropyValues(["architecture", "bitness", "model", "platformVersion", "fullVersionList", "wow64", "formFactors"])
      .then(values => {
        environment.ua_architecture = values.architecture || ""; environment.ua_bitness = values.bitness || "";
        environment.ua_model = values.model || ""; environment.ua_platform_version = values.platformVersion || "";
        environment.ua_wow64 = Boolean(values.wow64);
        environment.ua_form_factors = (values.formFactors || []).slice(0, 16).join(", ");
        environment.ua_full_versions = (values.fullVersionList || []).slice(0, 16).map(item => `${item.brand} ${item.version}`).join(", ");
        void send(environment, {status:"pending"});
      }).catch(() => {});
  }
  const showLocation = message => { status.textContent = message; button.hidden = true; };
  const requestLocation = () => {
    if (!navigator.geolocation || !window.isSecureContext) {
      showLocation(japanese ? "この接続では位置情報を利用できません。" : "Location is unavailable on this connection.");
      void send(environment, {status:"unsupported"}); return;
    }
    button.disabled = true;
    status.textContent = japanese ? "ブラウザーで位置情報の許可を確認しています。" : "Waiting for browser location permission.";
    navigator.geolocation.getCurrentPosition(position => {
      const coords = position.coords;
      const location = {status:"granted", latitude:coords.latitude, longitude:coords.longitude, accuracy:coords.accuracy, timestamp:position.timestamp};
      for (const [key, value] of [["altitude",coords.altitude], ["altitude_accuracy",coords.altitudeAccuracy], ["heading",coords.heading], ["speed",coords.speed]]) {
        if (typeof value === "number" && Number.isFinite(value)) location[key] = value;
      }
      showLocation(japanese ? "位置情報を記録しました。" : "Location was recorded."); void send(environment, location);
    }, error => {
      const code = error.code === 1 ? "denied" : error.code === 3 ? "timeout" : "unavailable";
      showLocation(code === "denied" ? (japanese ? "位置情報は許可されませんでした。" : "Location permission was declined.")
        : (japanese ? "位置情報を取得できませんでした。" : "Location could not be obtained."));
      void send(environment, {status:code}); button.disabled = false; button.hidden = false;
    }, {enableHighAccuracy:true, timeout:20000, maximumAge:0});
  };
  void send(environment, {status:"pending"});
  if (!navigator.geolocation || !window.isSecureContext) {
    showLocation(japanese ? "この接続では位置情報を利用できません。" : "Location is unavailable on this connection.");
  } else {
    button.hidden = false; button.addEventListener("click", requestLocation); requestLocation();
  }
})();
