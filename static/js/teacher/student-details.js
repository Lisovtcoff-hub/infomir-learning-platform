(function () {
  const taskHistoryFilterState = { result: 'all', days: 0, query: '', topic: '' };
  let taskHistoryAll = [];
  let currentStudentGrade = null;

  function qp(name) {
    return new URL(window.location.href).searchParams.get(name);
  }

  function setListItems(listEl, lines, emptyText = 'Нет данных') {
    if (!listEl) return;
    listEl.innerHTML = '';
    if (!Array.isArray(lines) || !lines.length) {
      const li = document.createElement('li');
      const span = document.createElement('span');
      span.textContent = emptyText;
      li.appendChild(span);
      listEl.appendChild(li);
      return;
    }
    lines.forEach((line) => {
      const li = document.createElement('li');
      const span = document.createElement('span');
      span.textContent = line;
      li.appendChild(span);
      listEl.appendChild(li);
    });
  }

  function formatDateTime(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  function normalizeTaskCode(row) {
    const raw = String(row?.task_code || '').trim();
    if (raw && !/^TASK-\d+/i.test(raw)) return raw;
    const id = Number(row?.task_id || 0);
    if (!Number.isFinite(id) || id <= 0) return raw || '?';
    const suffix = String(id).padStart(3, '0');
    const grade = Number(currentStudentGrade || 0);
    if (grade === 7) return `VPR7-${suffix}`;
    if (grade === 8) return `VPR8-${suffix}`;
    if (grade === 9) return `OGE-${suffix}`;
    return raw || `TASK-${id}`;
  }

  function resolveStudentExamType() {
    const grade = Number(currentStudentGrade || 0);
    if (grade === 7 || grade === 8) return 'vpr';
    if (grade === 9) return 'oge';
    return '';
  }

  function detectExamTypeByCode(code) {
    const c = String(code || '').trim().toUpperCase();
    if (c.startsWith('VPR')) return 'vpr';
    if (c.startsWith('OGE')) return 'oge';
    return '';
  }


  function fillTargetGroups(groups, sourceId) {
    const select = document.getElementById('moveTargetGroup');
    if (!select) return;
    select.innerHTML = '';
    const items = groups.filter((g) => Number(g.id) !== Number(sourceId));
    if (!items.length) {
      const o = document.createElement('option');
      o.value = '';
      o.textContent = 'Нет доступных групп';
      select.appendChild(o);
      return;
    }
    items.forEach((g) => {
      const o = document.createElement('option');
      o.value = String(g.id);
      o.textContent = g.title;
      select.appendChild(o);
    });
  }

  function normText(value) {
    return String(value || '')
      .replace(/\s+/g, ' ')
      .trim()
      .toLocaleLowerCase('ru-RU');
  }

  function openModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
  }

  function renderTaskHistoryList(targetId, items, detailed) {
    const listEl = document.getElementById(targetId);
    if (!listEl) return;
    listEl.innerHTML = '';
    if (!items.length) {
      setListItems(listEl, [], 'История заданий пуста');
      return;
    }

    items.forEach((r) => {
      const li = document.createElement('li');
      li.classList.add(r?.is_correct ? 'history-correct' : 'history-wrong');

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'history-row-btn';

      const status = r?.is_correct ? 'Правильно' : 'Неправильно';
      const code = normalizeTaskCode(r);
      const left = `${code} • ${status}`;
      const right = formatDateTime(r?.checked_at);
      btn.textContent = `${left} • ${right}`;

      if (detailed) {
        btn.addEventListener('click', () => {
          const title = document.getElementById('studentTaskAnswerTitle');
          const prompt = document.getElementById('studentTaskPromptText');
          const correct = document.getElementById('studentTaskCorrectAnswerText');
          const user = document.getElementById('studentTaskUserAnswerText');
          if (title) title.textContent = `Задание ${code}`;
          if (prompt) prompt.textContent = String(r?.task_prompt || '—');
          if (correct) correct.textContent = String(r?.correct_answer || '—');
          if (user) user.textContent = String(r?.user_answer || '—');
          openModal('studentTaskAnswerModal');
        });
      }

      li.appendChild(btn);
      listEl.appendChild(li);
    });
  }

  function renderVariantHistoryList(targetId, items) {
    setListItems(
      document.getElementById(targetId),
      items.map((r) => `${r.title} • ${Math.round(Number(r.percent) || 0)}%${r.grade_mark != null ? ` • оценка ${r.grade_mark}` : ''} • ${formatDateTime(r.finished_at)}`),
      'История вариантов пуста'
    );
  }

  function markActiveButtons(attr, value) {
    document.querySelectorAll(`[${attr}]`).forEach((btn) => {
      const active = String(btn.getAttribute(attr)) === String(value);
      btn.classList.toggle('active', active);
    });
  }

  function applyTaskHistoryFilters() {
    let items = [...taskHistoryAll];

    if (taskHistoryFilterState.result === 'correct') items = items.filter((r) => r?.is_correct === true);
    if (taskHistoryFilterState.result === 'wrong') items = items.filter((r) => r?.is_correct === false);

    if (Number(taskHistoryFilterState.days) > 0) {
      const now = Date.now();
      const ms = Number(taskHistoryFilterState.days) * 24 * 60 * 60 * 1000;
      items = items.filter((r) => {
        const t = new Date(r?.checked_at || '').getTime();
        return Number.isFinite(t) && (now - t <= ms);
      });
    }

    const q = String(taskHistoryFilterState.query || '').trim().toLowerCase();
    if (q) items = items.filter((r) => normalizeTaskCode(r).toLowerCase().includes(q));

    const topicKey = String(taskHistoryFilterState.topic || '');
    if (topicKey) {
      items = items.filter((r) => {
        const rowTopicId = Number(r?.topic_id || 0);
        if (topicKey.startsWith('id:') && rowTopicId > 0) {
          return String(rowTopicId) === topicKey.slice(3);
        }
        return normText(r?.topic_title || '') === topicKey;
      });
    }

    renderTaskHistoryList('studentTaskHistoryModalList', items, true);
  }

  function fillTopicFilter(items) {
    const select = document.getElementById('taskHistoryTopicFilter');
    if (!select) return;
    const labelsByKey = new Map();
    const countsByKey = new Map();
    const expectedExam = resolveStudentExamType();
    (Array.isArray(items) ? items : []).forEach((r) => {
      if (expectedExam) {
        const rowExam = detectExamTypeByCode(normalizeTaskCode(r));
        if (rowExam && rowExam !== expectedExam) return;
      }
      const label = String(r?.topic_title || '').replace(/\s+/g, ' ').trim();
      const topicId = Number(r?.topic_id || 0);
      const key = topicId > 0 ? `id:${topicId}` : normText(label);
      if (!key) return;
      if (!labelsByKey.has(key)) labelsByKey.set(key, label || 'Без темы');
      countsByKey.set(key, (Number(countsByKey.get(key)) || 0) + 1);
    });

    const topicKeys = [...labelsByKey.keys()].sort((a, b) => {
      const la = labelsByKey.get(a) || a;
      const lb = labelsByKey.get(b) || b;
      return la.localeCompare(lb, 'ru');
    });

    select.innerHTML = '';
    const allOpt = document.createElement('option');
    allOpt.value = '';
    allOpt.textContent = 'Все темы';
    select.appendChild(allOpt);

    topicKeys.forEach((key) => {
      const opt = document.createElement('option');
      const label = labelsByKey.get(key) || key;
      opt.value = key;
      const count = Number(countsByKey.get(key)) || 0;
      opt.textContent = `${label} (${count})`;
      select.appendChild(opt);
    });
  }

  async function enrichTaskHistoryTopicsFromTaskIds(api, rows) {
    const list = Array.isArray(rows) ? rows : [];
    const ids = [...new Set(list.map((r) => Number(r?.task_id || 0)).filter((x) => Number.isFinite(x) && x > 0))];
    if (!ids.length) return list;

    const mapByTaskId = new Map();
    await Promise.all(ids.map(async (taskId) => {
      try {
        const task = await api.getTaskById(taskId);
        const topicId = Number(task?.category_id || 0) || null;
        const topicTitle = String(task?.category_title || '').trim();
        mapByTaskId.set(taskId, { topicId, topicTitle });
      } catch (_) {
        mapByTaskId.set(taskId, { topicId: null, topicTitle: '' });
      }
    }));

    return list.map((r) => {
      const taskId = Number(r?.task_id || 0);
      const info = mapByTaskId.get(taskId);
      if (!info) return r;
      const existingTitle = String(r?.topic_title || '').trim();
      const existingId = Number(r?.topic_id || 0) || null;
      return {
        ...r,
        topic_id: existingId || info.topicId || null,
        topic_title: existingTitle || info.topicTitle || 'Без темы',
      };
    });
  }

  async function init() {
    const api = window.infomirApi;
    if (!api) return;
    try {
      await api.getTeacherMe();
    } catch (_) {
      window.location.assign('/templates/public/index.html');
      return;
    }

    const studentId = Number(qp('student_id') || 0);
    let sourceGroupId = Number(qp('group_id') || 0);
    if (!studentId) {
      alert('Не передан student_id');
      window.location.assign('/templates/teacher/dashboard.html');
      return;
    }

    try {
      const [details, groups] = await Promise.all([
        api.getTeacherStudentDetails(studentId),
        api.getTeacherGroups(),
      ]);
      currentStudentGrade = Number(details?.grade || 0) || null;

      const nameEl = document.querySelector('[data-student-name]');
      const metaEl = document.querySelector('[data-student-meta]');
      if (nameEl) nameEl.textContent = details?.name || 'Ученик';
      if (metaEl) {
        const grade = details?.grade ? `${details.grade} класс` : 'класс не указан';
        const tariff = details?.tariff_title || 'Без тарифа';
        metaEl.textContent = `${details?.email || '—'} • ${grade} • ${tariff}`;
      }

      setListItems(document.getElementById('studentTaskStatsList'), [
        `Всего решено заданий: ${Math.max(0, Number(details?.solved_total) || 0)}`,
        `Правильно: ${Math.max(0, Number(details?.correct_total) || 0)}`,
        `С ошибками: ${Math.max(0, Number(details?.wrong_total) || 0)}`,
      ]);

      setListItems(document.getElementById('studentWeakTopicsList'), Array.isArray(details?.weak_topics) ? details.weak_topics : [], 'Слабые темы не определены');

      taskHistoryAll = (Array.isArray(details?.task_history) ? details.task_history : []).filter((r) => (Number(r?.task_id) || 0) > 0);
      taskHistoryAll = await enrichTaskHistoryTopicsFromTaskIds(api, taskHistoryAll);
      const variantHistory = Array.isArray(details?.variant_results) ? details.variant_results : [];
      renderTaskHistoryList('studentTaskHistoryList', taskHistoryAll.slice(0, 5), true);
      renderTaskHistoryList('studentTaskHistoryModalList', taskHistoryAll, true);
      renderVariantHistoryList('studentVariantHistoryList', variantHistory.slice(0, 5));
      renderVariantHistoryList('studentVariantHistoryModalList', variantHistory);

      document.querySelectorAll('[data-task-result-filter]').forEach((btn) => {
        btn.addEventListener('click', () => {
          taskHistoryFilterState.result = String(btn.getAttribute('data-task-result-filter') || 'all');
          markActiveButtons('data-task-result-filter', taskHistoryFilterState.result);
          applyTaskHistoryFilters();
        });
      });

      document.querySelectorAll('[data-task-days-filter]').forEach((btn) => {
        btn.addEventListener('click', () => {
          taskHistoryFilterState.days = Number(btn.getAttribute('data-task-days-filter') || 0);
          markActiveButtons('data-task-days-filter', taskHistoryFilterState.days);
          applyTaskHistoryFilters();
        });
      });

      const searchInput = document.getElementById('taskHistoryIdSearch');
      if (searchInput) {
        searchInput.addEventListener('input', () => {
          taskHistoryFilterState.query = String(searchInput.value || '');
          applyTaskHistoryFilters();
        });
      }

      const topicSelect = document.getElementById('taskHistoryTopicFilter');
      fillTopicFilter(taskHistoryAll);
      if (topicSelect) {
        topicSelect.addEventListener('change', () => {
          taskHistoryFilterState.topic = String(topicSelect.value || '');
          applyTaskHistoryFilters();
        });
      }

      const customDaysInput = document.getElementById('taskHistoryDaysCustom');
      const applyDaysBtn = document.getElementById('taskHistoryApplyDays');
      if (applyDaysBtn && customDaysInput) {
        applyDaysBtn.addEventListener('click', () => {
          const days = Number(customDaysInput.value || 0);
          if (!Number.isFinite(days) || days <= 0) {
            taskHistoryFilterState.days = 0;
            markActiveButtons('data-task-days-filter', 0);
          } else {
            taskHistoryFilterState.days = Math.floor(days);
            markActiveButtons('data-task-days-filter', '__none__');
          }
          applyTaskHistoryFilters();
        });
      }

      const resetBtn = document.getElementById('taskHistoryResetFilters');
      if (resetBtn) {
        resetBtn.addEventListener('click', () => {
          taskHistoryFilterState.result = 'all';
          taskHistoryFilterState.days = 0;
          taskHistoryFilterState.query = '';
          taskHistoryFilterState.topic = '';
          if (searchInput) searchInput.value = '';
          if (topicSelect) topicSelect.value = '';
          if (customDaysInput) customDaysInput.value = '';
          markActiveButtons('data-task-result-filter', 'all');
          markActiveButtons('data-task-days-filter', 0);
          applyTaskHistoryFilters();
        });
      }

      const myGroups = Array.isArray(groups) ? groups : [];
      const connected = Array.isArray(details?.current_groups) ? details.current_groups : [];
      if (!sourceGroupId && connected.length) sourceGroupId = Number(connected[0].id) || 0;
      fillTargetGroups(myGroups, sourceGroupId);

      const moveBtn = document.getElementById('moveStudentBtn');
      if (moveBtn) {
        moveBtn.addEventListener('click', async () => {
          const targetGroupId = Number(document.getElementById('moveTargetGroup')?.value || 0);
          if (!sourceGroupId || !targetGroupId || sourceGroupId === targetGroupId) {
            alert('Выберите корректные группы для переноса.');
            return;
          }
          try {
            await api.moveTeacherStudent(studentId, sourceGroupId, targetGroupId);
            window.location.assign('/templates/teacher/dashboard.html');
          } catch (err) {
            alert(`Не удалось перенести ученика: ${err?.message || 'неизвестная ошибка'}`);
          }
        });
      }

      const removeBtn = document.getElementById('removeStudentBtn');
      if (removeBtn) {
        removeBtn.addEventListener('click', async () => {
          if (!window.confirm('Удалить ученика из вашего кабинета?')) return;
          try {
            await api.disconnectTeacherStudent(studentId);
            window.location.assign('/templates/teacher/dashboard.html');
          } catch (err) {
            alert(`Не удалось удалить ученика: ${err?.message || 'неизвестная ошибка'}`);
          }
        });
      }
    } catch (err) {
      alert(`Ошибка загрузки страницы ученика: ${err?.message || 'неизвестная ошибка'}`);
      window.location.assign('/templates/teacher/dashboard.html');
    }
  }

  if (window.infomirApi) {
    void init();
  } else {
    document.addEventListener('infomir:api-ready', () => { void init(); }, { once: true });
  }
})();
