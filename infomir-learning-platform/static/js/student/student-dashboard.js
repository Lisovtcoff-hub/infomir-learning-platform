(function () {
  function getStoredUser() {
    try {
      const raw = localStorage.getItem('infomir-auth-user');
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  function normalizeGrade(user) {
    const match = String(user?.grade ?? '').match(/\d+/);
    if (!match) return null;
    const num = Number(match[0]);
    return Number.isFinite(num) ? num : null;
  }

  function setText(selector, value) {
    document.querySelectorAll(selector).forEach((node) => {
      node.textContent = String(value);
    });
  }

  function setTariffTitle(user) {
    const title = String(user?.paid_tariff_title || '').trim() || 'Бесплатный';
    const expires=user?.paid_tariff_expires_at ? new Date(user.paid_tariff_expires_at) : null;
    const expiryText=expires && !Number.isNaN(expires.getTime())
      ? (expires.getTime() <= Date.now() ? ` (истёк ${expires.toLocaleDateString('ru-RU')})` : ` до ${expires.toLocaleDateString('ru-RU')}`)
      : '';
    setText('[data-user-tariff]', `${title}${expiryText}`);
  }

  function setMetric(selector, value, digits = 0) {
    const n = Number(value);
    const safe = Number.isFinite(n) ? n : 0;
    const text = digits > 0 ? safe.toFixed(digits) : Math.round(safe).toString();
    const node = document.querySelector(selector);
    if (node) node.textContent = text;
  }

  function applyPredictedGradeStyle(value) {
    const gradeValue = Number(value) || 0;
    const card = document.querySelector('[data-stat-grade]')?.closest('.mini-metric');
    if (!card) return;

    card.classList.remove('grade-2', 'grade-3', 'grade-4', 'grade-5');

    if (gradeValue >= 4.5) card.classList.add('grade-5');
    else if (gradeValue >= 3.5) card.classList.add('grade-4');
    else if (gradeValue >= 2.5) card.classList.add('grade-3');
    else card.classList.add('grade-2');
  }

  function setMainProgress(percent, label) {
    const safe = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
    const num = document.querySelector('[data-progress-number]');
    const bar = document.querySelector('[data-progress-bar]');
    const text = document.querySelector('[data-progress-text]');
    if (num) num.textContent = `${safe}%`;
    if (bar) bar.style.width = `${safe}%`;
    if (text) text.textContent = label;
  }

  function setWeakTopicText(value) {
    const node = document.querySelector('[data-weak-topic-text]');
    if (!node) return;
    node.textContent = value;
  }

  function setMainProgressTitle(grade) {
    const title = document.querySelector('[data-progress-title]');
    if (!title) return;
    title.textContent = grade === 9 ? 'Подготовка к ОГЭ по информатике' : 'Подготовка к ВПР';
  }

  function formatDate(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString('ru-RU');
  }

  function formatDateTime(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function formatDurationMmSs(totalSeconds) {
    const safe = Math.max(0, Number(totalSeconds) || 0);
    const minutes = Math.floor(safe / 60);
    const seconds = Math.floor(safe % 60);
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }

  function resolveSpentSeconds(attempt) {
    const explicit = Number(attempt?.spent_seconds);
    if (Number.isFinite(explicit) && explicit > 0) return explicit;
    const start = new Date(attempt?.started_at || '');
    const finish = new Date(attempt?.finished_at || '');
    if (Number.isNaN(start.getTime()) || Number.isNaN(finish.getTime())) return 0;
    return Math.max(Math.round((finish.getTime() - start.getTime()) / 1000), 0);
  }

  function modeLabel(mode) {
    const m = String(mode || '').toLowerCase();
    if (m.includes('oge')) return 'ОГЭ';
    if (m.includes('vpr')) return 'ВПР';
    return 'Тренировка';
  }

  function medalByRank(rank) {
    if (rank === 1) return '🥇';
    if (rank === 2) return '🥈';
    if (rank === 3) return '🥉';
    return '🏅';
  }

  function hasBrokenNameEncoding(value) {
    const text = String(value || '').trim();
    if (!text) return true;
    const qCount = (text.match(/\?/g) || []).length;
    return qCount > 0 && qCount >= Math.ceil(text.length * 0.4);
  }

  function renderLeaderboardSummary(summary) {
    const placeEl = document.querySelector('[data-leaderboard-place]');
    if (!placeEl) return;
    const total = Number(summary?.total_students) || 0;
    const rank = Number(summary?.current_user_rank) || 1;
    const medal = medalByRank(rank);
    placeEl.textContent = `${medal} Вы на ${rank} месте из ${Math.max(total, 1)}`;
  }

  function renderLeaderboardTop(selector, list) {
    const container = document.querySelector(selector);
    if (!container) return;
    container.innerHTML = '';

    const rows = Array.isArray(list) ? list : [];
    if (!rows.length) {
      const li = document.createElement('li');
      const span = document.createElement('span');
      span.textContent = 'Нет данных';
      li.appendChild(span);
      container.appendChild(li);
      return;
    }

    const topRows = rows.slice(0, 3);
    topRows.forEach((row) => {
      const li = document.createElement('li');
      const left = document.createElement('span');
      const right = document.createElement('small');
      const medal = medalByRank(Number(row.rank) || 0);
      const gradeText = row.grade ? `${row.grade} кл.` : '— кл.';
      const isCurrentUser = Number(row.user_id) === Number(window.__infomirCurrentUserId || 0);
      const rawName = String(row.name || '').trim();
      const safeName = hasBrokenNameEncoding(rawName)
        ? `Ученик #${Number(row.user_id) || '—'}`
        : rawName;
      const nameParts = safeName.split(/\s+/).filter(Boolean);
      const shortName = nameParts.length >= 2
        ? `${nameParts[0]} ${String(nameParts[1][0] || '').toUpperCase()}.`
        : (nameParts[0] || 'Ученик');
      const displayName = isCurrentUser ? 'Вы' : shortName;
      left.textContent = `${medal} #${row.rank} ${displayName} (${gradeText})`;
      if (isCurrentUser) {
        li.classList.add('leaderboard-you');
      }
      right.textContent = `${Math.round(Number(row.rating) || 0)} очк.`;
      li.appendChild(left);
      li.appendChild(right);
      container.appendChild(li);
    });

    const currentUserId = Number(window.__infomirCurrentUserId || 0);
    const currentUserRow = rows.find((row) => Number(row.user_id) === currentUserId);
    const inTop3 = topRows.some((row) => Number(row.user_id) === currentUserId);
    if (currentUserRow && !inTop3) {
      const li = document.createElement('li');
      const left = document.createElement('span');
      const right = document.createElement('small');
      const gradeText = currentUserRow.grade ? `${currentUserRow.grade} кл.` : '— кл.';
      left.textContent = `🏅 #${currentUserRow.rank} Вы (${gradeText})`;
      li.classList.add('leaderboard-you');
      right.textContent = `${Math.round(Number(currentUserRow.rating) || 0)} очк.`;
      li.appendChild(left);
      li.appendChild(right);
      container.appendChild(li);
    }
  }

  function renderLeaderboard(leaderboard) {
    const overall = leaderboard?.overall || {};
    const weekly = leaderboard?.weekly || {};
    renderLeaderboardSummary(overall);
    renderLeaderboardTop('[data-leaderboard-overall-top]', overall.top || []);
    renderLeaderboardTop('[data-leaderboard-weekly-top]', weekly.top || []);
  }

  function renderAchievements(stats, theoryProgress, attempts, leaderboard) {
    const container = document.getElementById('dashboardAchievements');
    const tooltip = document.querySelector('[data-achievements-tooltip]');
    if (!container) return;
    container.innerHTML = '';

    const attemptsTotal = Number(stats?.attempts_total) || 0;
    const solvedTasks = Number(stats?.solved_tasks_total) || 0;
    const predictedGrade = Number(stats?.predicted_exam_grade ?? stats?.average_grade) || 0;
    const theoryCompleted = Number(theoryProgress?.completed_topics) || 0;
    const readiness = Number(stats?.readiness_vpr_percent) || 0;
    const weeklyRank = Number(leaderboard?.weekly?.current_user_rank) || 9999;
    const overallRank = Number(leaderboard?.overall?.current_user_rank) || 9999;

    const defs = [
      { title: 'Первые шаги', color: 'blue', ok: attemptsTotal >= 1, desc: 'Сделайте 1 завершённую попытку.' },
      { title: 'Практик', color: 'green', ok: solvedTasks >= 25, desc: 'Решите 25+ заданий.' },
      { title: 'Интенсив', color: 'purple', ok: attemptsTotal >= 10, desc: 'Сделайте 10+ попыток.' },
      { title: 'Теоретик', color: 'blue', ok: theoryCompleted >= 8, desc: 'Пройдите 8+ тем теории.' },
      { title: 'Стабильность', color: 'green', ok: readiness >= 65, desc: 'Достигните готовности 65%+.' },
      { title: 'Отличник', color: 'yellow', ok: predictedGrade >= 4.5, desc: 'Прогноз оценки 4.5 и выше.' },
      { title: 'Рывок недели', color: 'purple', ok: weeklyRank <= 10, desc: 'Попадите в топ-10 за неделю.' },
      { title: 'Лидер', color: 'yellow', ok: overallRank <= 3, desc: 'Попадите в топ-3 общего рейтинга.' },
    ];

    const earned = defs.filter((item) => item.ok);
    const pending = defs.filter((item) => !item.ok);

    if (!earned.length) {
      const badge = document.createElement('span');
      badge.className = 'ach-badge locked';
      badge.textContent = 'Пока нет открытых достижений';
      container.appendChild(badge);
    }

    earned.forEach((item) => {
      const badge = document.createElement('span');
      badge.className = `ach-badge ${item.color}`;
      badge.textContent = `✓ ${item.title}`;
      badge.title = item.desc;
      container.appendChild(badge);
    });

    if (tooltip) {
      if (!pending.length) {
        tooltip.innerHTML = 'Все достижения выполнены. Отличная работа!';
      } else {
        tooltip.innerHTML = pending
          .map((item, idx) => `${idx + 1}) ${item.title}<br>${item.desc}`)
          .join('<br><br>');
      }
    }
  }

  function variantLabel(attempt) {
    if (!attempt || attempt.variant_id == null) return '';
    const title = String(attempt.variant_title || '').trim();
    return title ? ` • ${title}` : ` • Вариант #${attempt.variant_id}`;
  }

  function renderRecentAttempts(attempts) {
    const container = document.getElementById('dashboardRecentResults');
    if (!container) return;
    container.innerHTML = '';

    if (!attempts.length) {
      const li = document.createElement('li');
      const span = document.createElement('span');
      span.textContent = 'Нет данных по попыткам';
      li.appendChild(span);
      container.appendChild(li);
      return;
    }

    attempts.slice(0, 4).forEach((attempt) => {
      const li = document.createElement('li');
      const left = document.createElement('span');
      const right = document.createElement('small');
      const variantNo = attempt.variant_id != null ? `Вариант №${attempt.variant_id}` : modeLabel(attempt.mode);
      const gradeText = attempt.grade_mark != null ? `Оценка ${attempt.grade_mark}` : 'Оценка —';
      left.textContent = `${variantNo} • ${gradeText}`;
      right.textContent = formatDateTime(attempt.finished_at || attempt.started_at) || 'Без даты';
      li.appendChild(left);
      li.appendChild(right);
      container.appendChild(li);
    });
  }



  function renderAttemptHistory(attempts) {
    const container = document.getElementById('dashboardAttemptHistoryList');
    if (!container) return;
    container.innerHTML = '';

    if (!attempts.length) {
      const li = document.createElement('li');
      const span = document.createElement('span');
      span.textContent = 'Нет данных по попыткам';
      li.appendChild(span);
      container.appendChild(li);
      return;
    }

    attempts.forEach((attempt) => {
      const li = document.createElement('li');
      const left = document.createElement('span');
      const right = document.createElement('small');
      const percent = Number(attempt.percent) || 0;
      const gradeMark = attempt.grade_mark ? ` • Оценка ${attempt.grade_mark}` : '';
      const spent = formatDurationMmSs(resolveSpentSeconds(attempt));
      const solvedAt = formatDateTime(attempt.finished_at || attempt.started_at) || 'Без даты';

      left.textContent = `${modeLabel(attempt.mode)} • ${percent}%${gradeMark}${variantLabel(attempt)}`;
      right.textContent = `${solvedAt} • ${spent}`;
      li.appendChild(left);
      li.appendChild(right);
      container.appendChild(li);
    });
  }

  function syncAttemptViews(attempts) {
    const list = Array.isArray(attempts) ? attempts : [];
    renderRecentAttempts(list);
    renderAttemptHistory(list);
  }

  function renderWeekActivityChart(activity) {
    const chart = document.getElementById('dashboardWeekChart');
    if (!chart) return;
    chart.innerHTML = '';

    const dayLabels = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
    const now = new Date();
    const days = [];
    const dayKey = (d) => {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      return `${y}-${m}-${dd}`;
    };

    for (let i = 6; i >= 0; i -= 1) {
      const d = new Date(now);
      d.setHours(0, 0, 0, 0);
      d.setDate(now.getDate() - i);
      days.push({
        key: dayKey(d),
        label: dayLabels[d.getDay()],
        attempts: 0,
        tasks: 0,
        total: 0,
      });
    }

    const bucket = new Map(days.map((item) => [item.key, item]));
    (Array.isArray(activity?.days) ? activity.days : []).forEach((day) => {
      const item = bucket.get(String(day?.date || ''));
      if (!item) return;
      item.attempts = Number(day?.attempts) || 0;
      item.tasks = Number(day?.tasks) || 0;
      item.total = Number(day?.total) || (item.attempts + item.tasks);
    });

    const maxCount = Math.max(...days.map((item) => item.total), 0);
    const minPx = 10;
    const maxPx = 120;
    days.forEach((item) => {
      const col = document.createElement('div');
      const bar = document.createElement('span');
      const label = document.createElement('small');
      const px = maxCount > 0
        ? Math.max(minPx, Math.round((item.total / maxCount) * maxPx))
        : minPx;
      bar.style.height = `${px}px`;
      bar.title = `Активность: ${item.total}\nВарианта: ${item.attempts}\nЗадания: ${item.tasks}`;
      label.textContent = item.label;
      col.appendChild(bar);
      col.appendChild(label);
      chart.appendChild(col);
    });
  }

  function examTypeLabel(examType) {
    const value = String(examType || '').toUpperCase();
    if (value === 'OGE') return 'ОГЭ';
    if (value === 'VPR') return 'ВПР';
    return 'Тренировка';
  }

  function resolveTrainingPage(item, fallbackGrade) {
    const exam = String(item?.exam_type || '').toUpperCase();
    if (exam === 'OGE' || Number(fallbackGrade) === 9) return '/templates/public/training-oge.html';
    if (Number(fallbackGrade) === 8) return '/templates/public/training-vpr-8.html';
    return '/templates/public/training-vpr-7.html';
  }

  function buildPracticeLink(item, fallbackGrade) {
    const params = new URLSearchParams();
    if (item?.category_id != null) params.set('category_id', String(item.category_id));
    const query = params.toString();
    const page = resolveTrainingPage(item, fallbackGrade);
    return `${page}${query ? `?${query}` : ''}`;
  }

  function buildTheoryLink(item, fallbackGrade) {
    const grade = Number(fallbackGrade) === 9 ? 9 : Number(fallbackGrade) === 8 ? 8 : 7;
    const params = new URLSearchParams();
    const slug = String(item?.theory_slug || '').trim();
    if (slug) params.set('topic', slug);
    const query = params.toString();
    return `/templates/public/theory-${grade}.html${query ? `?${query}` : ''}`;
  }

  function renderRecommendedTopics(recommended, grade) {
    const container = document.querySelector('.recommended-card .rec-grid');
    if (!container) return;
    container.innerHTML = '';

    const items = Array.isArray(recommended?.items) ? recommended.items : [];
    if (!items.length) {
      const empty = document.createElement('div');
      empty.className = 'rec-item';
      empty.innerHTML = '<p>Пока недостаточно данных для рекомендаций</p><div class="bar rec-bar"><span style="width:0%"></span></div>';
      container.appendChild(empty);
      return;
    }

    items.forEach((item) => {
      const progress = Math.max(0, Math.min(100, Math.round(Number(item?.progress_percent) || 0)));
      const card = document.createElement('div');
      card.className = 'rec-item';

      const title = document.createElement('p');
      title.textContent = `${examTypeLabel(item?.exam_type)} • ${String(item?.title || 'Тема')}`;

      const bar = document.createElement('div');
      bar.className = 'bar rec-bar';
      const fill = document.createElement('span');
      fill.style.width = `${progress}%`;
      bar.appendChild(fill);

      const actions = document.createElement('div');
      actions.className = 'rec-actions';

      const theoryAction = document.createElement('a');
      theoryAction.className = 'btn btn-ghost';
      theoryAction.href = buildTheoryLink(item, grade);
      theoryAction.textContent = 'Теория';

      const practiceAction = document.createElement('a');
      practiceAction.className = 'btn btn-primary';
      practiceAction.href = buildPracticeLink(item, grade);
      practiceAction.textContent = 'Задания';

      card.appendChild(title);
      card.appendChild(bar);
      actions.appendChild(theoryAction);
      actions.appendChild(practiceAction);
      card.appendChild(actions);
      container.appendChild(card);
    });
  }

  function pickWeakestTopic(recommended, grade) {
    const items = Array.isArray(recommended?.items) ? recommended.items : [];
    if (!items.length) return null;

    const targetExam = Number(grade) === 9 ? 'OGE' : 'VPR';
    const preferred = items.filter((item) => String(item?.exam_type || '').toUpperCase() === targetExam);
    const pool = preferred.length ? preferred : items;

    const scored = pool
      .map((item) => ({
        title: String(item?.title || '').trim() || 'Тема',
        progress: Math.max(0, Math.min(100, Math.round(Number(item?.progress_percent) || 0))),
      }))
      .sort((a, b) => a.progress - b.progress || a.title.localeCompare(b.title, 'ru'));

    return scored[0] || null;
  }

  function applyUserHeader(user) {
    const displayName = String(user?.name || 'Ученик');
    const grade = normalizeGrade(user);
    const displayClass = grade ? `${grade} класс` : 'Без класса';
    const initial = displayName.trim() ? displayName.trim()[0].toUpperCase() : 'У';

    setText('[data-student-fullname], [data-student-fullname-large]', displayName);
    setText('[data-student-class], [data-student-class-large]', displayClass);

    document.querySelectorAll('[data-student-avatar], [data-auth-avatar]').forEach((node) => {
      node.style.backgroundImage = '';
      node.classList.remove('has-image');
      node.textContent = initial;
    });

    const groupTitle = String(user?.connected_group_title || '').trim();
    const teacherName = String(user?.connected_teacher_name || '').trim();
    const isConnected = Boolean(groupTitle || teacherName);
    const accessRow = document.querySelector('[data-student-access-row]');
    const connectionRow = document.querySelector('[data-student-connection-row]');
    const groupTitleEl = document.querySelector('[data-student-group-title]');
    const teacherNameEl = document.querySelector('[data-student-teacher-name]');
    if (isConnected) {
      if (accessRow) accessRow.hidden = true;
      if (connectionRow) connectionRow.hidden = false;
      if (groupTitleEl) groupTitleEl.textContent = groupTitle || '—';
      if (teacherNameEl) teacherNameEl.textContent = teacherName || '—';
    } else {
      if (accessRow) accessRow.hidden = false;
      if (connectionRow) connectionRow.hidden = true;
    }
  }

  async function initDashboard() {
    const api = window.infomirApi;
    if (!api?.auth) return;

    const user = getStoredUser() || {};
    window.__infomirCurrentUserId = Number(user?.id) || 0;
    const grade = normalizeGrade(user);
    setTariffTitle(user);
    applyUserHeader(user);
    setMainProgressTitle(grade);
    renderWeekActivityChart({ days: [] });

    const connectForm = document.getElementById('studentTeacherConnectForm');
    if (connectForm) {
      connectForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const code = String(document.getElementById('studentTeacherCode')?.value || '').trim().toUpperCase();
        if (!code) return;
        try {
          const updated = await api.connectTeacher(code);
          api.auth.setStoredUser(updated);
          applyUserHeader(updated);
          connectForm.reset();
        } catch (error) {
          alert(error?.message || 'Не удалось подключиться к учителю');
        }
      });
    }

    const disconnectBtn = document.getElementById('studentTeacherDisconnectBtn');
    if (disconnectBtn) {
      disconnectBtn.addEventListener('click', async () => {
        if (!window.confirm('Отключиться от текущего учителя?')) return;
        try {
          const updated = await api.disconnectTeacher();
          api.auth.setStoredUser(updated);
          applyUserHeader(updated);
        } catch (error) {
          alert(error?.message || 'Не удалось отключиться от учителя');
        }
      });
    }

    try {
      try {
        const me = await api.auth.me();
        if (me && typeof me === 'object') {
          setTariffTitle(me);
          if (api?.auth?.setStoredUser) {
            const merged = { ...user, ...me };
            api.auth.setStoredUser(merged);
            applyUserHeader(merged);
          }
        }
      } catch (_) {
        // ignore tariff refresh errors
      }

      // Fallback refresh to guarantee connection flags are applied even after stale cache.
      try {
        const freshMe = await api.auth.me();
        if (freshMe && typeof freshMe === 'object') {
          const current = api?.auth?.getStoredUser ? (api.auth.getStoredUser() || {}) : {};
          const mergedFresh = { ...current, ...freshMe };
          if (api?.auth?.setStoredUser) api.auth.setStoredUser(mergedFresh);
          applyUserHeader(mergedFresh);
        }
      } catch (_) {
        // ignore
      }

      const [stats, attempts, theoryProgress, leaderboard, weekActivity, recommendedTopics] = await Promise.all([
        api.getMyAttemptStats(),
        api.getMyAttempts(),
        api.getMyTheoryProgress(),
        api.getMyLeaderboard(),
        api.getMyWeekActivity(),
        api.getMyRecommendedTopics(),
      ]);

      setMetric('[data-stat-topics]', theoryProgress?.completed_topics ?? 0);
      setMetric('[data-stat-tasks]', stats?.solved_tasks_total ?? 0);
      const predictedGrade = Number(stats?.predicted_exam_grade ?? stats?.average_grade ?? 0);
      setMetric('[data-stat-grade]', predictedGrade, 1);
      applyPredictedGradeStyle(predictedGrade);
      setMetric('[data-stat-attempts]', stats?.attempts_total ?? 0);

      const avg = Number(stats?.readiness_vpr_percent) || 0;
      const hasAttempts = Array.isArray(attempts) && attempts.length > 0;
      setMainProgress(
        avg,
        hasAttempts
          ? `Варианты: ${Math.round(Number(stats?.variant_average_percent) || 0)}% • Теория: ${Math.round(Number(stats?.theory_completion_percent) || 0)}%`
          : 'Пока нет данных',
      );
      const weakestTopic = pickWeakestTopic(recommendedTopics, grade);
      setWeakTopicText(
        weakestTopic
          ? `Слабая тема: ${weakestTopic.title} (${weakestTopic.progress}%)`
          : 'Слабая тема: пока нет данных',
      );

      syncAttemptViews(attempts);
      renderWeekActivityChart(weekActivity);
      renderRecommendedTopics(recommendedTopics, grade);
      renderLeaderboard(leaderboard);
      renderAchievements(stats, theoryProgress, attempts, leaderboard);
    } catch (_) {
      setMetric('[data-stat-topics]', 0);
      setMetric('[data-stat-tasks]', 0);
      setMetric('[data-stat-grade]', 0, 1);
      applyPredictedGradeStyle(0);
      setMetric('[data-stat-attempts]', 0);
      setMainProgress(0, 'Не удалось загрузить данные');
      setWeakTopicText('Слабая тема: пока нет данных');
      setTariffTitle(user);
      syncAttemptViews([]);
      renderWeekActivityChart({ days: [] });
      renderRecommendedTopics({ items: [] }, grade);
      renderLeaderboard({
        overall: { total_students: 1, current_user_rank: 1, top: [] },
        weekly: { top: [] },
      });
      renderAchievements({}, {}, [], {});
    }
  }

  if (window.infomirApi?.auth) {
    void initDashboard();
  } else {
    document.addEventListener('infomir:api-ready', () => {
      void initDashboard();
    }, { once: true });
  }
})();
