(function () {
  const cfgEl = document.getElementById('variantConfig');
  const listEl = document.getElementById('variantTaskList');
  if (!cfgEl || !listEl) return;

  let api = window.infomirApi || null;
  const API_BASE = window.location.origin;
  const exam = cfgEl.dataset.exam;
  const durationSec = Number(cfgEl.dataset.durationSec || 2700);
  const params = new URLSearchParams(window.location.search);
  const subject = String(params.get('subject') || cfgEl.dataset.subject || 'informatics').trim().toLowerCase();
  const selectedVariantId = Number(params.get('variant') || params.get('variant_id') || 0);

  const difficultyLabel = { easy: 'Лёгкие', medium: 'Средние', hard: 'Сложные' };
  const timerEl = document.getElementById('variantTimer');
  const submitBtn = document.getElementById('submitVariantBtn');
  const modal = document.getElementById('resultsModal');
  const closeBtns = document.querySelectorAll('#closeResultsModal, .close-results-btn');
  const retryBtn = document.getElementById('retryVariantBtn');
  const backBtn = document.querySelector('[data-back-with-reset]');
  const detailsEl = document.getElementById('resultsDetails');
  const progressEl = document.getElementById('scoreFill');

  let tasks = [];
  let timeLeft = durationSec;
  let timerInt = null;
  let currentAttemptId = null;
  let resolvedVariantId = selectedVariantId || null;

  function showDecisionModal(message, { confirmText = 'Проверить', cancelText = 'Продолжить', hideCancel = false } = {}) {
    return new Promise((resolve) => {
      const overlay = document.createElement('div');
      overlay.className = 'modal open';
      overlay.setAttribute('aria-hidden', 'false');

      const dialog = document.createElement('div');
      dialog.className = 'modal-dialog';

      const title = document.createElement('h3');
      title.textContent = 'Подтверждение';

      const body = document.createElement('p');
      body.className = 'card-text';
      body.textContent = message;

      const actions = document.createElement('div');
      actions.className = 'hero-actions';
      actions.style.marginTop = '12px';

      const cancelBtn = document.createElement('button');
      cancelBtn.type = 'button';
      cancelBtn.className = 'btn btn-ghost';
      cancelBtn.textContent = cancelText;

      const confirmBtn = document.createElement('button');
      confirmBtn.type = 'button';
      confirmBtn.className = 'btn btn-primary';
      confirmBtn.textContent = confirmText;

      function close(value) {
        overlay.remove();
        resolve(value);
      }

      if (!hideCancel) {
        actions.appendChild(cancelBtn);
        cancelBtn.addEventListener('click', () => close(false));
      }
      actions.appendChild(confirmBtn);
      confirmBtn.addEventListener('click', () => close(true));

      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) close(false);
      });

      dialog.appendChild(title);
      dialog.appendChild(body);
      dialog.appendChild(actions);
      overlay.appendChild(dialog);
      document.body.appendChild(overlay);
    });
  }


  function resolveExamQuery() {
    if (exam === 'vpr7') return { exam_type: 'vpr', grade: 7 };
    if (exam === 'vpr8') return { exam_type: 'vpr', grade: 8 };
    return { exam_type: 'oge', grade: 9 };
  }

  async function loadTasksFromApi() {
    if (!api?.getTasks) throw new Error('API клиент недоступен');
    let response = [];

    if (selectedVariantId && api?.getVariantById && api?.getTaskById) {
      try {
        const variant = await api.getVariantById(selectedVariantId);
        if (variant?.id) resolvedVariantId = Number(variant.id) || resolvedVariantId;
        const orderedTaskIds = (variant?.variant_tasks || [])
          .slice()
          .sort((a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0))
          .map((x) => Number(x.task_id))
          .filter((x) => Number.isFinite(x));

        if (orderedTaskIds.length) {
          const loadedTasks = await Promise.all(
            orderedTaskIds.map(async (taskId) => {
              try {
                return await api.getTaskById(taskId);
              } catch (_) {
                return null;
              }
            })
          );
          response = loadedTasks.filter(Boolean);
        }
      } catch (_) {
        throw new Error('Этот вариант доступен после оплаты подходящего тарифа.');
      }
    }

    if (!response.length) {
      response = await api.getTasks({ ...resolveExamQuery(), subject });
    }

    if (!Array.isArray(response) || !response.length) {
      throw new Error('Нет заданий для варианта в базе');
    }

    const idPrefix = exam === 'vpr7' ? 'VPR7' : exam === 'vpr8' ? 'VPR8' : 'OGE';
    return response.map((item, idx) => ({
      id: item.id,
      publicId: `${idPrefix}-${String(item.id).padStart(3, '0')}`,
      typeTitle: item.title || `Задание ${idx + 1}`,
      difficulty: item.difficulty || ['easy', 'medium', 'hard'][idx % 3],
      text: item.question,
      hint: item.hint || '',
      userAnswer: '',
    }));
  }

  async function startAttemptIfNeeded() {
    if (currentAttemptId || !api?.startAttempt) return;
    try {
      const attempt = await api.startAttempt({ mode: 'variant', variant_id: resolvedVariantId });
      currentAttemptId = attempt.id;
    } catch (err) {
      if (err?.status === 401 || err?.status === 403) {
        throw new Error('Войдите в аккаунт, чтобы начать вариант.');
      }
      throw err;
    }
  }

  function renderError(message) {
    listEl.innerHTML = '';
    const article = document.createElement('article');
    article.className = 'task-card';
    const p = document.createElement('p');
    p.className = 'card-text';
    p.textContent = message;
    article.appendChild(p);
    listEl.appendChild(article);
    submitBtn.disabled = true;
  }

  function formatTime(sec) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return h > 0 ? `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  function renderTasks() {
    listEl.innerHTML = '';
    tasks.forEach((t) => {
      const card = document.createElement('article');
      card.className = 'variant-card';

      const meta = document.createElement('div');
      meta.className = 'task-meta';

      const idBadge = document.createElement('span');
      idBadge.className = 'task-badge task-id-badge';
      idBadge.setAttribute('data-copy-id', String(t.publicId || t.id));
      idBadge.title = 'Нажмите, чтобы скопировать ID';
      idBadge.textContent = `ID: ${t.publicId || t.id}`;
      meta.appendChild(idBadge);

      const numBadge = document.createElement('span');
      numBadge.className = 'task-badge';
      numBadge.textContent = `Задание ${t.id}`;
      meta.appendChild(numBadge);

      const typeBadge = document.createElement('span');
      typeBadge.className = 'task-badge';
      typeBadge.textContent = t.typeTitle;
      meta.appendChild(typeBadge);

      const diffBadge = document.createElement('span');
      diffBadge.className = 'task-badge';
      diffBadge.textContent = difficultyLabel[t.difficulty] || 'Средние';
      meta.appendChild(diffBadge);

      const question = document.createElement('p');
      question.textContent = t.text;

      const hint=document.createElement('details');
      const hintTitle=document.createElement('summary'); hintTitle.textContent='Показать подсказку'; hint.appendChild(hintTitle);
      const hintText=document.createElement('p'); hintText.textContent=t.hint || 'Для этого задания подсказка пока не добавлена.'; hint.appendChild(hintText);

      const input = document.createElement('input');
      input.className = 'answer-input';
      input.setAttribute('data-task-id', String(t.id));
      input.type = 'text';
      input.placeholder = 'Введите ответ';
      input.value = t.userAnswer;

      card.appendChild(meta);
      card.appendChild(question);
      card.appendChild(hint);
      card.appendChild(input);
      listEl.appendChild(card);
    });
  }

  function lockInputs() {
    document.querySelectorAll('#variantTaskList .answer-input').forEach((i) => { i.disabled = true; });
    submitBtn.disabled = true;
  }

  function startTimer() {
    if (timerInt) clearInterval(timerInt);
    timerEl.textContent = formatTime(timeLeft);
    timerInt = setInterval(() => {
      timeLeft -= 1;
      timerEl.textContent = formatTime(Math.max(timeLeft, 0));
      if (timeLeft <= 0) {
        clearInterval(timerInt);
        checkVariant();
      }
    }, 1000);
  }

  function calcGrade(correct, total) {
    const percent = total ? (correct / total) * 100 : 0;
    if (percent < 40) return 2;
    if (percent < 60) return 3;
    if (percent < 85) return 4;
    return 5;
  }

  async function saveAttemptAnswers(results) {
    if (!api?.saveAttemptAnswer) return;
    if (!currentAttemptId) {
      await startAttemptIfNeeded();
    }
    if (!currentAttemptId) throw new Error('Не удалось создать попытку для сохранения результата.');
    for (const row of results) {
      if (!row.userAnswer) continue;
      await api.saveAttemptAnswer(currentAttemptId, {
        task_id: row.id,
        user_answer: row.userAnswer,
      });
    }
  }

  async function finishAttempt() {
    if (!api?.finishAttempt) return;
    if (!currentAttemptId) {
      await startAttemptIfNeeded();
    }
    if (!currentAttemptId) throw new Error('Не удалось завершить попытку: попытка не создана.');
    return api.finishAttempt(currentAttemptId);
  }

  async function checkVariant() {
    clearInterval(timerInt);
    lockInputs();
    await startAttemptIfNeeded();

    document.querySelectorAll('#variantTaskList .answer-input').forEach((input) => {
      const id = Number(input.dataset.taskId);
      const t = tasks.find((x) => x.id === id);
      t.userAnswer = input.value.trim().toLowerCase();
    });

    let results = tasks.map((t)=>({ ...t, ok:false, skipped:!t.userAnswer }));
    await saveAttemptAnswers(results);
    const summary = await finishAttempt();
    if (!api?.getAttemptResult) throw new Error('API результатов попытки недоступен.');
    const serverResult = await api.getAttemptResult(currentAttemptId);
    const resultByTask = new Map((serverResult?.answers || []).map((row)=>[Number(row.task_id),row]));
    results = results.map((row)=>{
      const checked=resultByTask.get(Number(row.id));
      return {...row,ok:Boolean(checked?.is_correct),skipped:!checked?.user_answer,correctAnswer:checked?.correct_answer || '',explanation:checked?.explanation || ''};
    });

    const correct = Number(summary?.score ?? results.filter((r) => r.ok).length);
    const total = Number(summary?.max_score ?? results.length);
    const points = correct;
    const grade = Number(summary?.grade_mark ?? calcGrade(correct, total));
    const spentSec = durationSec - Math.max(timeLeft, 0);

    document.getElementById('sumCorrect').textContent = String(correct);
    document.getElementById('sumTotal').textContent = String(total);
    document.getElementById('sumPoints').textContent = String(points);
    document.getElementById('sumGrade').textContent = String(grade);
    document.getElementById('sumTime').textContent = formatTime(spentSec);

    const gradeEl = document.getElementById('sumGrade');
    const gradeCard = gradeEl ? gradeEl.closest('.card') : null;
    if (gradeCard) {
      gradeCard.classList.remove('grade-2', 'grade-3', 'grade-4', 'grade-5');
      gradeCard.classList.add(`grade-${grade}`);
    }

    progressEl.style.width = `${Math.round((correct / total) * 100)}%`;

    detailsEl.innerHTML = '';
    results.forEach((r) => {
      const item = document.createElement('div');
      item.className = 'result-accordion-item';
      const statusClass = r.skipped ? 'skip' : r.ok ? 'ok' : 'bad';
      const statusText = r.skipped ? 'Пропущено' : r.ok ? 'Верно' : 'Неверно';

      const toggleBtn = document.createElement('button');
      toggleBtn.type = 'button';
      toggleBtn.textContent = `Задание ${r.id}: ${statusText}`;

      const body = document.createElement('div');
      body.className = 'body result-task-info';

      const idP = document.createElement('p');
      const idStrong = document.createElement('strong');
      idStrong.textContent = 'ID задания:';
      idP.appendChild(idStrong);
      idP.appendChild(document.createTextNode(' '));
      const idSpan = document.createElement('span');
      idSpan.className = 'task-badge task-id-badge';
      idSpan.setAttribute('data-copy-id', String(r.publicId || r.id));
      idSpan.title = 'Нажмите, чтобы скопировать ID';
      idSpan.textContent = String(r.publicId || r.id);
      idP.appendChild(idSpan);

      const numP = document.createElement('p');
      const numStrong = document.createElement('strong');
      numStrong.textContent = 'Задание №:';
      numP.appendChild(numStrong);
      numP.appendChild(document.createTextNode(` ${r.id}`));

      const typeP = document.createElement('p');
      const typeStrong = document.createElement('strong');
      typeStrong.textContent = 'Тип:';
      typeP.appendChild(typeStrong);
      typeP.appendChild(document.createTextNode(` ${r.typeTitle}`));

      const answerP = document.createElement('p');
      const answerStrong = document.createElement('strong');
      answerStrong.textContent = 'Ваш ответ:';
      answerP.appendChild(answerStrong);
      answerP.appendChild(document.createTextNode(` ${r.userAnswer || 'Нет ответа'}`));

      const statusP = document.createElement('p');
      statusP.className = `result-line ${statusClass}`;
      const statusStrong = document.createElement('strong');
      statusStrong.textContent = 'Статус:';
      statusP.appendChild(statusStrong);
      statusP.appendChild(document.createTextNode(` ${statusText}`));

      body.appendChild(idP);
      body.appendChild(numP);
      body.appendChild(typeP);
      body.appendChild(answerP);
      body.appendChild(statusP);
      const correctP=document.createElement('p');
      const correctStrong=document.createElement('strong'); correctStrong.textContent='Правильный ответ:';
      correctP.append(correctStrong,document.createTextNode(` ${r.correctAnswer || '—'}`)); body.appendChild(correctP);
      if(r.explanation){const explanationP=document.createElement('p');const explanationStrong=document.createElement('strong');explanationStrong.textContent='Разбор:';explanationP.append(explanationStrong,document.createTextNode(` ${r.explanation}`));body.appendChild(explanationP);}

      item.appendChild(toggleBtn);
      item.appendChild(body);
      toggleBtn.addEventListener('click', () => item.classList.toggle('open'));
      detailsEl.appendChild(item);
    });

    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
  }

  function closeModal() {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
  }

  function resetVariant() {
    tasks.forEach((t) => { t.userAnswer = ''; });
    currentAttemptId = null;
    timeLeft = durationSec;
    renderTasks();
    submitBtn.disabled = false;
    const gradeEl = document.getElementById('sumGrade');
    const gradeCard = gradeEl ? gradeEl.closest('.card') : null;
    if (gradeCard) {
      gradeCard.classList.remove('grade-2', 'grade-3', 'grade-4', 'grade-5');
    }
    closeModal();
    startTimer();
  }

  listEl.addEventListener('input', (e) => {
    if (!e.target.classList.contains('answer-input')) return;
    const id = Number(e.target.dataset.taskId);
    const t = tasks.find((x) => x.id === id);
    if (t) t.userAnswer = e.target.value;
  });

  submitBtn.addEventListener('click', async () => {
    document.querySelectorAll('#variantTaskList .answer-input').forEach((input) => {
      const id = Number(input.dataset.taskId);
      const t = tasks.find((x) => x.id === id);
      if (t) t.userAnswer = input.value.trim().toLowerCase();
    });

    const answeredCount = tasks.filter((item) => String(item.userAnswer || '').trim().length > 0).length;
    const totalCount = tasks.length;

    if (answeredCount === 0) {
      await showDecisionModal('Вы не ответили ни на одно задание. Заполните хотя бы один ответ перед проверкой.', {
        confirmText: 'Продолжить',
        hideCancel: true,
      });
      return;
    }

    const ok = await showDecisionModal(
      `Вы ответили на ${answeredCount} из ${totalCount} заданий. Вы уверены, что хотите отправить на проверку?`,
      { confirmText: 'Проверить', cancelText: 'Продолжить' }
    );
    if (!ok) return;

    try {
      await checkVariant();
    } catch (err) {
      renderError(err.message || 'Ошибка проверки варианта через API');
    }
  });

  if (backBtn) {
    backBtn.addEventListener('click', () => {
      const ok = window.confirm('Если вернуться назад, текущий прогресс будет сброшен. Продолжить?');
      if (!ok) return;
      const targetUrl = backBtn.getAttribute('data-back-url') || 'index.html';
      window.location.href = targetUrl;
    });
  }
  closeBtns.forEach((btn) => btn.addEventListener('click', closeModal));
  retryBtn.addEventListener('click', resetVariant);
  modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

  async function init() {
    try {
      tasks = await loadTasksFromApi();
      renderTasks();
      startTimer();
    } catch (err) {
      renderError(err.message || 'Не удалось загрузить вариант через API');
    }
  }

  if (window.infomirApi) {
    void init();
  } else {
    document.addEventListener('infomir:api-ready', () => {
      api = window.infomirApi || null;
      void init();
    }, { once: true });
  }
})();

