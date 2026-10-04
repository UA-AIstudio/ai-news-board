/* Latest AI News board: live behavior for the TV.
   Inlined into the page by scripts/build.py. Vanilla JS, no dependencies.
   Without JavaScript the page still shows every item; this only adds motion
   and live details (clock, studio status, NEW tags, carousel, reload). */
(function () {
  "use strict";

  var TZ = "America/Phoenix";
  var HOUR = 60 * 60 * 1000;
  var NEW_WINDOW = 48 * HOUR;
  var DAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
  var DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

  // ---- Pure helpers (also exported for tests) -----------------------------

  var partsFormat = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ, weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23"
  });

  /** Day of week (0 = Sunday) and minutes since midnight, in Arizona time. */
  function arizonaParts(ms) {
    var parts = partsFormat.formatToParts(new Date(ms));
    var out = { day: 0, minutes: 0 };
    var hour = 0;
    var minute = 0;
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      if (p.type === "weekday") out.day = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(p.value);
      if (p.type === "hour") hour = parseInt(p.value, 10) % 24;
      if (p.type === "minute") minute = parseInt(p.value, 10);
    }
    out.minutes = hour * 60 + minute;
    return out;
  }

  function toMinutes(hhmm) {
    var bits = hhmm.split(":");
    return parseInt(bits[0], 10) * 60 + parseInt(bits[1], 10);
  }

  /** 1080 -> "6pm", 690 -> "11:30am", 720 -> "12pm". */
  function formatHour(minutes) {
    var h = Math.floor(minutes / 60);
    var m = minutes % 60;
    var suffix = h < 12 ? "am" : "pm";
    var h12 = h % 12 === 0 ? 12 : h % 12;
    return h12 + (m ? ":" + (m < 10 ? "0" : "") + m : "") + suffix;
  }

  /** Studio status for a weekly hours object at time ms, or null if no hours. */
  function studioStatus(hours, ms) {
    if (!hours) return null;
    var now = arizonaParts(ms);
    var today = hours[DAY_KEYS[now.day]];
    if (today) {
      var open = toMinutes(today[0]);
      var close = toMinutes(today[1]);
      if (now.minutes >= open && now.minutes < close) {
        return { open: true, text: "Open now, until " + formatHour(close) };
      }
    }
    for (var offset = 0; offset < 8; offset++) {
      var day = (now.day + offset) % 7;
      var h = hours[DAY_KEYS[day]];
      if (!h) continue;
      var opens = toMinutes(h[0]);
      if (offset === 0 && now.minutes >= opens) continue;
      var when = offset === 0 ? "today" : DAY_NAMES[day];
      return { open: false, text: "Closed, opens " + when + " " + formatHour(opens) };
    }
    return { open: false, text: "Closed" };
  }

  /** True if an item dated YYYY-MM-DD (Arizona) is within 48 hours of ms. */
  function isNew(isoDate, ms) {
    var start = Date.parse(isoDate + "T00:00:00-07:00");
    if (isNaN(start)) return false;
    return ms - start <= NEW_WINDOW;
  }

  var exported = { arizonaParts: arizonaParts, formatHour: formatHour, studioStatus: studioStatus, isNew: isNew };
  if (typeof module === "object" && module.exports) module.exports = exported;
  if (typeof document === "undefined") return;

  // ---- Page behavior -------------------------------------------------------

  var root = document.documentElement;
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var loadedAt = Date.now();
  root.classList.add("js");
  if (reduced) root.classList.add("reduced");

  var $ = function (sel, el) { return (el || document).querySelector(sel); };
  var $$ = function (sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); };

  // NEW tags, fixed at page load.
  $$("[data-date]").forEach(function (el) {
    var tag = $(".tag-new", el);
    if (tag && isNew(el.getAttribute("data-date"), loadedAt)) tag.hidden = false;
  });

  // Clock.
  var clock = $("#clock");
  var clockFormat = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ, hour: "numeric", minute: "2-digit", second: "2-digit", hour12: true
  });
  function updateClock() {
    if (!clock) return;
    clock.textContent = clockFormat.format(new Date()).replace(/\s?AM$/, " am").replace(/\s?PM$/, " pm");
  }
  if (clock) { clock.hidden = false; updateClock(); }

  // Studio status badge.
  var statusEl = $("#studio-status");
  var hoursEl = $("#studio-hours");
  var hours = null;
  try { hours = hoursEl ? JSON.parse(hoursEl.textContent) : null; } catch (e) { hours = null; }
  function updateStatus() {
    if (!statusEl) return;
    var status = studioStatus(hours, Date.now());
    if (!status) { statusEl.hidden = true; return; }
    statusEl.hidden = false;
    statusEl.classList.toggle("is-open", status.open);
    $(".status-text", statusEl).textContent = status.text;
  }
  updateStatus();

  // Reachability check: every 10 minutes, reload if the site answers.
  // The reload waits for the next carousel slide change so it never cuts one off.
  var reloadPending = false;
  var carouselRunning = false;
  function checkReachable() {
    fetch(window.location.href, { cache: "no-store" })
      .then(function (response) {
        if (!response.ok) return;
        reloadPending = true;
        if (!carouselRunning) window.location.reload();
      })
      .catch(function () {});
  }

  // Burn-in care: shift the whole layout 0 to 2px, one step every 10 minutes.
  var stage = $("#stage");
  var SHIFTS = [[0, 0], [1, 0], [2, 1], [1, 2], [0, 1], [1, 1]];
  var shiftStep = 0;
  function shiftLayout() {
    if (!stage) return;
    shiftStep = (shiftStep + 1) % SHIFTS.length;
    var s = SHIFTS[shiftStep];
    stage.style.transform = s[0] || s[1] ? "translate(" + s[0] + "px, " + s[1] + "px)" : "";
  }

  // Spotlight carousel. The progress bar's CSS animation is the timer:
  // when it ends, the next slide shows. Pausing the animation pauses the carousel.
  var slides = $$(".slide");
  var dots = $$(".dot");
  var counter = $("#slide-count");
  var progress = $("#progress");
  var current = 0;
  var progressName = "a";

  function startProgress() {
    progressName = progressName === "a" ? "b" : "a";
    progress.setAttribute("data-run", progressName);
  }

  function showSlide(next) {
    var prev = slides[current];
    prev.classList.remove("is-active");
    prev.classList.add("is-leaving");
    prev.setAttribute("aria-hidden", "true");
    window.setTimeout(function () { prev.classList.remove("is-leaving"); }, 750);
    current = next;
    slides[current].classList.add("is-active");
    slides[current].removeAttribute("aria-hidden");
    dots.forEach(function (d, i) { d.classList.toggle("is-active", i === current); });
    if (counter) counter.textContent = (current + 1) + " of " + slides.length;
  }

  if (slides.length > 1 && progress && !reduced) {
    carouselRunning = true;
    progress.addEventListener("animationend", function () {
      if (reloadPending) { window.location.reload(); return; }
      showSlide((current + 1) % slides.length);
      startProgress();
    });
    startProgress();
  }

  // Ticker: set the duration so it scrolls at about 60px per second at 1920
  // wide (scaled with the screen). One layout read, once, at startup.
  var tickerTrack = $(".ticker-track");
  var tickerGroup = $(".ticker-group");
  if (tickerTrack && tickerGroup && !reduced) {
    var speed = 60 * (window.innerWidth / 1920);
    var seconds = Math.max(20, tickerGroup.getBoundingClientRect().width / speed);
    tickerTrack.style.setProperty("--ticker-duration", seconds.toFixed(1) + "s");
  }

  // Column highlight: every 2 seconds one column moves its highlight to its
  // next item, so each column steps every 6 seconds, staggered by 2 seconds.
  var columns = $$(".column").map(function (col) { return { items: $$(".item", col), index: -1 }; });
  var highlightStep = 0;
  function highlightNext() {
    if (!columns.length) return;
    var col = columns[highlightStep % columns.length];
    highlightStep++;
    if (!col.items.length) return;
    if (col.index >= 0) col.items[col.index].classList.remove("is-lit");
    col.index = (col.index + 1) % col.items.length;
    col.items[col.index].classList.add("is-lit");
  }

  // One scheduler for every timer. It counts only visible seconds, so all
  // timers pause while the page is hidden, and it re-aligns to the second.
  var visibleSeconds = 0;
  function tick() {
    window.setTimeout(tick, 1000 - (Date.now() % 1000) + 5);
    if (document.hidden) return;
    visibleSeconds++;
    updateClock();
    if (!reduced && visibleSeconds % 2 === 0) highlightNext();
    if (visibleSeconds % 60 === 0) updateStatus();
    if (visibleSeconds % 600 === 0) { checkReachable(); shiftLayout(); }
  }
  window.setTimeout(tick, 1000 - (Date.now() % 1000) + 5);

  function onVisibility() {
    root.classList.toggle("is-paused", document.hidden);
    if (!document.hidden) { updateClock(); updateStatus(); }
  }
  document.addEventListener("visibilitychange", onVisibility);
  onVisibility();
})();
