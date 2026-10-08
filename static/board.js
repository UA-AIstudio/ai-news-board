/* Latest AI News board: live behavior for the TV.
   Inlined into the page by scripts/build.py. Vanilla JS, no dependencies.
   Without JavaScript each column shows its first page and the ticker still
   lists every headline; this adds motion and live details (clock, studio
   status, NEW tags, carousel, column pages, reload). */
(function () {
  "use strict";

  var TZ = "America/Phoenix";
  var HOUR = 60 * 60 * 1000;
  var DAY = 24 * HOUR;
  var NEW_WINDOW = 48 * HOUR;
  var DAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
  var DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  var MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"];

  // ---- Pure helpers (also exported for tests) -----------------------------

  var partsFormat = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ, weekday: "short", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23"
  });

  /** Arizona date (YYYY-MM-DD), day of week (0 = Sunday) and minutes since midnight. */
  function arizonaParts(ms) {
    var parts = partsFormat.formatToParts(new Date(ms));
    var v = {};
    for (var i = 0; i < parts.length; i++) v[parts[i].type] = parts[i].value;
    return {
      date: v.year + "-" + v.month + "-" + v.day,
      day: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(v.weekday),
      minutes: (parseInt(v.hour, 10) % 24) * 60 + parseInt(v.minute, 10)
    };
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

  /**
   * Studio status at time ms, or null if there are no hours.
   * hours: {mon: ["11:00", "18:00"], ..., sun: null}
   * closures: [{date: "YYYY-MM-DD", note: "..."}], dates closed despite the hours.
   */
  function studioStatus(hours, ms, closures) {
    if (!hours) return null;
    var closed = {};
    (closures || []).forEach(function (c) { closed[c.date] = c.note; });
    var now = arizonaParts(ms);
    if (Object.prototype.hasOwnProperty.call(closed, now.date)) {
      return { open: false, text: "Closed today, " + closed[now.date] };
    }
    var today = hours[DAY_KEYS[now.day]];
    if (today) {
      var open = toMinutes(today[0]);
      var close = toMinutes(today[1]);
      if (now.minutes >= open && now.minutes < close) {
        return { open: true, text: "Open now, until " + formatHour(close) };
      }
    }
    // Next opening, skipping closure dates. Look ahead far enough for a long break.
    for (var offset = 0; offset < 60; offset++) {
      var then = arizonaParts(ms + offset * DAY);
      var h = hours[DAY_KEYS[then.day]];
      if (!h || Object.prototype.hasOwnProperty.call(closed, then.date)) continue;
      var opens = toMinutes(h[0]);
      if (offset === 0 && now.minutes >= opens) continue;
      var when = offset === 0 ? "today" : offset < 7 ? DAY_NAMES[then.day]
        : MONTH_NAMES[parseInt(then.date.slice(5, 7), 10) - 1] + " " + parseInt(then.date.slice(8), 10);
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

  // Column paging: each card shows 2 items and turns its page every 10
  // seconds (15 with reduced motion). Columns start 3 seconds apart so they
  // never turn together.
  var PAGE_SECONDS = 10;
  var REDUCED_PAGE_SECONDS = 15;
  var PAGE_STAGGER = 3;

  /** True if column `index` turns its page after `second` visible seconds. */
  function pageDue(second, index, reducedMotion) {
    var period = reducedMotion ? REDUCED_PAGE_SECONDS : PAGE_SECONDS;
    var since = second - index * PAGE_STAGGER;
    return since > 0 && since % period === 0;
  }

  var exported = {
    arizonaParts: arizonaParts, formatHour: formatHour, studioStatus: studioStatus,
    isNew: isNew, pageDue: pageDue
  };
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
  var studio = null;
  try { studio = hoursEl ? JSON.parse(hoursEl.textContent) : null; } catch (e) { studio = null; }
  function updateStatus() {
    if (!statusEl) return;
    var status = studio ? studioStatus(studio.hours, Date.now(), studio.closures) : null;
    if (!status) { statusEl.hidden = true; return; }
    statusEl.hidden = false;
    statusEl.classList.toggle("is-open", status.open);
    $(".status-text", statusEl).textContent = status.text;
  }
  updateStatus();

  // Reachability check: every 10 minutes, reload if the site answers.
  // The reload waits for the next column page change (or, with no paging, the
  // next slide change) and happens in its place, so it never cuts one off.
  var reloadPending = false;
  var carouselRunning = false;
  var pagingRunning = false;
  function checkReachable() {
    fetch(window.location.href, { cache: "no-store" })
      .then(function (response) {
        if (!response.ok) return;
        reloadPending = true;
        if (!carouselRunning && !pagingRunning) window.location.reload();
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
  var dots = $$(".spotlight .dot");
  var SLIDE_MS = 750;
  var slideBusyUntil = 0;
  var counter = $("#slide-count");
  var progress = $("#progress");
  var current = 0;
  var progressName = "a";

  function startProgress() {
    progressName = progressName === "a" ? "b" : "a";
    progress.setAttribute("data-run", progressName);
  }

  function showSlide(next) {
    slideBusyUntil = Date.now() + SLIDE_MS;
    var prev = slides[current];
    prev.classList.remove("is-active");
    prev.classList.add("is-leaving");
    prev.setAttribute("aria-hidden", "true");
    window.setTimeout(function () { prev.classList.remove("is-leaving"); }, SLIDE_MS);
    current = next;
    slides[current].classList.add("is-active");
    slides[current].removeAttribute("aria-hidden");
    dots.forEach(function (d, i) { d.classList.toggle("is-active", i === current); });
    if (counter) counter.textContent = (current + 1) + " of " + slides.length;
  }

  if (slides.length > 1 && progress && !reduced) {
    carouselRunning = true;
    progress.addEventListener("animationend", function () {
      if (reloadPending && !pagingRunning) { window.location.reload(); return; }
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

  // Card text size: find the largest --fit (0.8 to 1.5) at which the tallest
  // page of every card still fits, so short items fill the card and long ones
  // never get cut off. Layout reads happen only here: at load and on resize.
  var FIT_MIN = 0.8;
  var FIT_MAX = 1.5;
  var cards = $$(".column");
  function setFit(fit) {
    cards.forEach(function (col) { col.style.setProperty("--fit", fit.toFixed(3)); });
  }
  function cardsFit() {
    var unit = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    return cards.every(function (col) {
      var style = window.getComputedStyle(col);
      var room = col.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom)
        - $(".column-head", col).offsetHeight;
      // Leave room for the 8px a page slides up as it fades in.
      var pages = $(".pages", col);
      return !pages || pages.offsetHeight <= room - 12 * unit;
    });
  }
  function fitCards() {
    if (!cards.length) return;
    setFit(FIT_MAX);
    if (cardsFit()) return;
    var lo = FIT_MIN;
    var hi = FIT_MAX;
    for (var step = 0; step < 9; step++) {
      var mid = (lo + hi) / 2;
      setFit(mid);
      if (cardsFit()) lo = mid; else hi = mid;
    }
    setFit(lo);
  }
  fitCards();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitCards);
  var resizeTimer = 0;
  window.addEventListener("resize", function () {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(fitCards, 200);
  });

  // Column pages. All pages share one grid cell (see style.css), so a page
  // change never moves the card. A change waits while a spotlight slide is
  // moving, so the two never animate together.
  var PAGE_MS = 600;
  var columns = $$(".column").map(function (col) {
    return { pages: $$(".page", col), dots: $$(".dot", col), count: $(".page-count", col), index: 0 };
  });
  pagingRunning = columns.some(function (col) { return col.pages.length > 1; });

  function showPage(col, next) {
    var prev = col.pages[col.index];
    prev.classList.remove("is-active");
    prev.classList.add("is-leaving");
    prev.setAttribute("aria-hidden", "true");
    window.setTimeout(function () { prev.classList.remove("is-leaving"); }, PAGE_MS);
    col.index = next;
    col.pages[next].classList.add("is-active");
    col.pages[next].removeAttribute("aria-hidden");
    col.dots.forEach(function (d, i) { d.classList.toggle("is-active", i === next); });
    if (col.count) col.count.textContent = (next + 1) + " of " + col.pages.length;
  }

  function turnPage(col) {
    var wait = slideBusyUntil - Date.now();
    if (wait > 0) { window.setTimeout(function () { turnPage(col); }, wait); return; }
    if (reloadPending) { window.location.reload(); return; }
    showPage(col, (col.index + 1) % col.pages.length);
  }

  // One scheduler for every timer. It counts only visible seconds, so all
  // timers pause while the page is hidden, and it re-aligns to the second.
  var visibleSeconds = 0;
  function tick() {
    window.setTimeout(tick, 1000 - (Date.now() % 1000) + 5);
    if (document.hidden) return;
    visibleSeconds++;
    updateClock();
    columns.forEach(function (col, i) {
      if (col.pages.length > 1 && pageDue(visibleSeconds, i, reduced)) turnPage(col);
    });
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
