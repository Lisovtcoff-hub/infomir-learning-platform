(function () {
  const classId = document.body.dataset.theoryClass;
  const defaultSubject = String(document.body.dataset.subject || "informatics").trim().toLowerCase();
  const contentEl = document.getElementById("theoryContent");
  const topicListEl = document.querySelector(".topic-list");
  const API_BASE = window.location.origin;
  const urlParams = new URLSearchParams(window.location.search);

  function createEl(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function fixMojibake(value) {
    const text = String(value ?? "");
    if (!/[ÐÑ]/.test(text)) return text;
    try {
      const bytes = Uint8Array.from(text, (ch) => ch.charCodeAt(0) & 0xff);
      const decoded = new TextDecoder("utf-8").decode(bytes);
      const sourceMarkers = (text.match(/[ÐÑ]/g) || []).length;
      const decodedMarkers = (decoded.match(/[ÐÑ]/g) || []).length;
      const hasCyrillic = /[А-Яа-яЁё]/.test(decoded);
      if (hasCyrillic && decodedMarkers < sourceMarkers) return decoded;
      return text;
    } catch (_) {
      return text;
    }
  }

  if (contentEl && !document.querySelector(".theory-reading-progress")) {
    const root = createEl("div", "theory-reading-progress");
    root.setAttribute("aria-hidden", "true");
    root.appendChild(createEl("span", "theory-reading-progress__fill"));
    document.body.appendChild(root);
  }

  if (!classId || !contentEl || !topicListEl) return;

  let theoryTopics = [];
  let currentSubject = defaultSubject;
  let topicItems = [];
  let topicsBySlug = {};
  const completedTopicIds = new Set();
  let currentTopicSlug = null;
  let readingProgressFillEl = null;
  const completedToastShown = new Set();
  let topicReadArmed = false;
  let userScrollIntent = false;
  let lockCompletionUntilTs = 0;
  let topicOpenedAtTs = 0;
  let lastUserScrollIntentTs = 0;

  function setActive(topicId) {
    topicItems.forEach((item) => item.classList.remove("active"));
    const active = topicItems.find((item) => item.dataset.topicId === topicId);
    if (active) active.classList.add("active");
  }

  function updateCompletedMarks() {
    topicItems.forEach((item) => {
      const slug = item.dataset.topicId;
      const topic = topicsBySlug[slug];
      const topicId = Number(topic?.id);
      const completed = topicId && completedTopicIds.has(topicId);
      item.classList.toggle("topic-completed", Boolean(completed));
    });
  }

  function ensureReadingProgressBar() {
    if (readingProgressFillEl) return;
    const existing = document.querySelector(".theory-reading-progress__fill");
    if (existing) {
      readingProgressFillEl = existing;
      return;
    }
    const root = createEl("div", "theory-reading-progress");
    root.setAttribute("aria-hidden", "true");
    readingProgressFillEl = createEl("span", "theory-reading-progress__fill");
    root.appendChild(readingProgressFillEl);
    document.body.appendChild(root);
  }

  function updateReadingProgressBar(percent) {
    if (!readingProgressFillEl) return;
    const safe = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
    readingProgressFillEl.style.width = `${safe}%`;
  }

  function showTopicPassedToast() {
    let container = document.getElementById("toastContainer");
    if (!container) {
      container = document.createElement("div");
      container.id = "toastContainer";
      container.className = "toast-container";
      document.body.appendChild(container);
    }
    const toast = createEl("div", "toast toast-success");
    toast.appendChild(createEl("div", "toast-title", "Тема пройдена"));
    toast.appendChild(createEl("div", "toast-message", "Можно переходить к следующей теме или к заданиям."));
    container.appendChild(toast);
    window.setTimeout(() => toast.classList.add("toast-hide"), 2200);
    window.setTimeout(() => toast.remove(), 2600);
  }

  function renderInlineContent(target, block) {
    const segments = Array.isArray(block?.segments) ? block.segments : null;
    if (segments && segments.length) {
      segments.forEach((seg) => {
        const text = fixMojibake(String(seg?.text || ""));
        const strong = Boolean(seg?.bold);
        const italic = Boolean(seg?.italic);
        if (strong || italic) {
          let node = document.createTextNode(text);
          if (strong) {
            const strongEl = document.createElement("strong");
            strongEl.appendChild(node);
            node = strongEl;
          }
          if (italic) {
            const emEl = document.createElement("em");
            emEl.appendChild(node);
            node = emEl;
          }
          target.appendChild(node);
        } else {
          target.appendChild(document.createTextNode(text));
        }
      });
      return;
    }

    target.textContent = fixMojibake(String(block?.text || ""));
  }

  function renderContentBlocks(blocks) {
    const safeBlocks = Array.isArray(blocks) ? blocks : [];
    safeBlocks.forEach((block) => {
      if (!block || typeof block !== "object") return;
      const type = String(block.type || "paragraph");

      if (type === "heading") {
        const level = Math.min(4, Math.max(2, Number(block.level) || 2));
        const heading = document.createElement(`h${level}`);
        heading.className = "card-title";
        renderInlineContent(heading, block);
        contentEl.appendChild(heading);
        return;
      }

      if (type === "callout") {
        const callout = createEl("div", "theory-callout theory-callout-gray");
        const title = fixMojibake(String(block.title || "")).trim();
        if (title) callout.appendChild(createEl("div", "theory-callout-title", title));
        const body = createEl("div", "theory-callout-text");
        renderInlineContent(body, block);
        callout.appendChild(body);
        contentEl.appendChild(callout);
        return;
      }

      if (type === "image") {
        const figure = createEl("figure", "theory-image-block");
        const img = document.createElement("img");
        img.className = "theory-image";
        img.src = String(block.src || "").trim();
        img.alt = fixMojibake(String(block.alt || ""));
        if (img.src) {
          figure.appendChild(img);
          const caption = fixMojibake(String(block.caption || "")).trim();
          if (caption) figure.appendChild(createEl("figcaption", "theory-image-caption", caption));
          contentEl.appendChild(figure);
        }
        return;
      }

      if (type === "list") {
        const ordered = String(block.style || "").toLowerCase() === "ordered";
        const list = document.createElement(ordered ? "ol" : "ul");
        list.className = "key-list";
        const items = Array.isArray(block.items) ? block.items : [];
        items.forEach((item) => {
          const li = document.createElement("li");
          if (typeof item === "string") {
            li.textContent = fixMojibake(item);
          } else {
            renderInlineContent(li, item);
          }
          list.appendChild(li);
        });
        contentEl.appendChild(list);
        return;
      }

      const p = createEl("p", "card-text");
      renderInlineContent(p, block);
      contentEl.appendChild(p);
    });
  }

  async function markTopicAsCompleted(topicSlug) {
    const api = window.infomirApi;
    const topic = topicsBySlug[topicSlug];
    const topicId = Number(topic?.id);
    if (!topicId || completedTopicIds.has(topicId)) return true;
    try {
      if (api?.completeTheoryTopic) {
        await api.completeTheoryTopic(topicId);
      } else {
        const response = await fetch(`${API_BASE}/api/theory/progress/${encodeURIComponent(topicId)}/complete`, {
          method: "POST",
          credentials: "include",
        });
        if (!response.ok) return false;
      }
      completedTopicIds.add(topicId);
      updateCompletedMarks();
      return true;
    } catch (_) {
      return false;
    }
  }

  async function completeCurrentTopicIfNeeded() {
    const topic = topicsBySlug[currentTopicSlug];
    const topicId = Number(topic?.id);
    if (!topicId || completedTopicIds.has(topicId)) return false;
    return await markTopicAsCompleted(currentTopicSlug);
  }

  function getTopicBounds() {
    const rect = contentEl.getBoundingClientRect();
    const startY = window.scrollY + rect.top;
    const endY = Math.max(startY, window.scrollY + rect.bottom - window.innerHeight);
    return { startY, endY };
  }

  function getTopicReadPercent() {
    const { startY, endY } = getTopicBounds();
    const currentY = window.scrollY;
    if (currentY <= startY) return 0;
    if (endY <= startY) return 100;
    const percent = ((currentY - startY) / (endY - startY)) * 100;
    return Math.max(0, Math.min(100, percent));
  }

  async function onReadingScroll() {
    if (!currentTopicSlug) return;
    const percent = getTopicReadPercent();
    updateReadingProgressBar(percent);

    if (Date.now() < lockCompletionUntilTs) return;

    const docBottomReached = window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2;
    const hasFreshUserIntent = lastUserScrollIntentTs > topicOpenedAtTs;
    if (!topicReadArmed) {
      if ((hasFreshUserIntent && userScrollIntent) || docBottomReached) {
        topicReadArmed = true;
      } else {
        return;
      }
    }

    if (percent >= 99 || docBottomReached) {
      updateReadingProgressBar(100);
      const justCompleted = await completeCurrentTopicIfNeeded();
      if (justCompleted && currentTopicSlug && !completedToastShown.has(currentTopicSlug)) {
        completedToastShown.add(currentTopicSlug);
        showTopicPassedToast();
      }
    }
  }

  function renderTheoryTopic(topicId) {
    const topic = topicsBySlug?.[topicId];
    if (!topic) return;
    currentTopicSlug = topicId;
    completedToastShown.delete(topicId);
    topicReadArmed = false;
    userScrollIntent = false;
    lockCompletionUntilTs = Date.now() + 800;
    topicOpenedAtTs = Date.now();

    contentEl.classList.remove("theory-fade-in");
    void contentEl.offsetWidth;
    contentEl.classList.add("theory-fade-in");

    contentEl.textContent = "";
    contentEl.appendChild(createEl("h2", "section-title", topic.title));
    renderContentBlocks(topic.content_json || []);

    const gradeNum = Number(classId);
    const trainingPage = gradeNum === 9 ? "training-oge.html" : `training-vpr-${gradeNum}.html`;
    const categoryId = Number(topic.category_id) || 0;
    const practiceBtn = createEl("a", "btn btn-primary", "Перейти к решению задач по теме");
    const q = new URLSearchParams();
    if (categoryId) q.set("category_id", String(categoryId));
    q.set("subject", currentSubject);
    practiceBtn.href = `${trainingPage}?${q.toString()}`;
    practiceBtn.style.marginTop = "16px";
    contentEl.appendChild(practiceBtn);

    const currentIndex = theoryTopics.findIndex((item) => item.slug === topicId);
    const nextTopic = currentIndex >= 0 ? theoryTopics[currentIndex + 1] : null;
    if (nextTopic) {
      const nextBtn = createEl("button", "btn btn-ghost", "Следующая тема");
      nextBtn.type = "button";
      nextBtn.style.marginTop = "10px";
      nextBtn.addEventListener("click", () => renderTheoryTopic(nextTopic.slug));
      contentEl.appendChild(nextBtn);
    }

    setActive(topicId);
    if (typeof contentEl.scrollTo === "function") contentEl.scrollTo({ top: 0, behavior: "smooth" });
    window.scrollTo({ top: 0, behavior: "smooth" });
    updateReadingProgressBar(0);
  }

  function bindTopicClicks() {
    topicItems.forEach((item) => {
      item.addEventListener("click", (e) => {
        e.preventDefault();
        renderTheoryTopic(item.dataset.topicId);
      });
    });
  }

  function buildMenuFromData() {
    const entries = theoryTopics.map((topic) => [topic.slug, topic]);
    topicListEl.textContent = "";

    if (!entries.length) {
      const li = document.createElement("li");
      li.appendChild(createEl("span", "topic-item", "Нет тем в базе данных"));
      topicListEl.appendChild(li);
      topicItems = [];
      return;
    }

    entries.forEach(([slug, topic], idx) => {
      const li = document.createElement("li");
      const a = createEl("a", `topic-item${idx === 0 ? " active" : ""}`, topic.title);
      a.href = "#";
      a.dataset.topicId = slug;
      li.appendChild(a);
      topicListEl.appendChild(li);
    });

    topicItems = Array.from(document.querySelectorAll(".topic-item[data-topic-id]"));
    bindTopicClicks();
    updateCompletedMarks();
  }

  async function loadCompletedTopics() {
    const api = window.infomirApi;
    const grade = Number(classId);
    try {
      let ids = [];
      if (api?.getMyCompletedTheoryTopics) {
        ids = await api.getMyCompletedTheoryTopics(Number.isFinite(grade) ? grade : undefined);
      } else {
        const qs = Number.isFinite(grade) ? `?grade=${encodeURIComponent(String(grade))}` : "";
        const response = await fetch(`${API_BASE}/api/theory/progress/my/topics${qs}`, { credentials: "include" });
        if (!response.ok) return;
        ids = await response.json();
      }
      if (!Array.isArray(ids)) return;
      ids.forEach((id) => {
        const n = Number(id);
        if (Number.isFinite(n) && n > 0) completedTopicIds.add(n);
      });
    } catch (_) {
      // ignore authorization errors
    }
  }

  async function loadTheoryData() {
    if (window.infomirApi?.getTheoryTopics) {
      const topics = await window.infomirApi.getTheoryTopics(Number(classId), currentSubject);
      if (!Array.isArray(topics)) throw new Error("Некорректный формат ответа /api/theory");
      return topics;
    }

    const response = await fetch(`/api/theory?grade=${encodeURIComponent(classId)}&subject=${encodeURIComponent(currentSubject)}`, { credentials: "include" });
    if (!response.ok) throw new Error(`API /api/theory вернул ${response.status}`);
    const topics = await response.json();
    if (!Array.isArray(topics)) throw new Error("Некорректный формат ответа /api/theory");
    return topics;
  }

  function normalizeTopic(topic) {
    const blocks = Array.isArray(topic?.content_json) ? topic.content_json : [];
    return {
      id: topic.id,
      category_id: topic.category_id,
      slug: topic.slug,
      title: fixMojibake(topic.title),
      content_json: blocks,
    };
  }

  function renderApiError(message) {
    contentEl.textContent = "";
    contentEl.appendChild(createEl("h2", "section-title", "Не удалось загрузить теорию"));
    contentEl.appendChild(createEl("p", "card-text", fixMojibake(message)));
  }

  async function init() {
    try {
      const subjectFromUrl = String(urlParams.get("subject") || "").trim().toLowerCase();
      if (subjectFromUrl) currentSubject = subjectFromUrl;
      ensureReadingProgressBar();
      const topics = await loadTheoryData();
      await loadCompletedTopics();
      theoryTopics = topics.map(normalizeTopic);
      topicsBySlug = theoryTopics.reduce((acc, topic) => {
        acc[topic.slug] = topic;
        return acc;
      }, {});
      buildMenuFromData();
      const requestedTopic = String(urlParams.get("topic") || "").trim();
      const requestedExists = requestedTopic && Object.prototype.hasOwnProperty.call(topicsBySlug, requestedTopic);
      if (requestedExists) {
        renderTheoryTopic(requestedTopic);
      } else {
        const first = topicItems.find((item) => item.classList.contains("active")) || topicItems[0];
        if (first) renderTheoryTopic(first.dataset.topicId);
      }

      window.addEventListener("wheel", () => {
        userScrollIntent = true;
        lastUserScrollIntentTs = Date.now();
      }, { passive: true });
      window.addEventListener("touchmove", () => {
        userScrollIntent = true;
        lastUserScrollIntentTs = Date.now();
      }, { passive: true });
      window.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown" || e.key === "PageDown" || e.key === " " || e.key === "End") {
          userScrollIntent = true;
          lastUserScrollIntentTs = Date.now();
        }
      });
      window.addEventListener("scroll", () => { void onReadingScroll(); }, { passive: true });
      window.addEventListener("resize", () => { void onReadingScroll(); }, { passive: true });
    } catch (err) {
      console.error("Theory API error:", err);
      renderApiError(err.message || "Ошибка API");
    }
  }

  void init();
})();
