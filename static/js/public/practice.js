(function () {
  const cfgEl = document.getElementById('practiceConfig');
  const listEl = document.getElementById('taskList');
  if (!cfgEl || !listEl) return;

  const exam = cfgEl.dataset.exam;
  const defaultSubject = (cfgEl.dataset.subject || 'informatics').trim().toLowerCase();
  const api = window.infomirApi;
  const API_BASE = window.location.origin;
  const urlParams = new URLSearchParams(window.location.search);

  const filters = { typeId: 'all', difficulty: 'all', status: 'all', result: 'all', search: '', subject: defaultSubject };
  const difficultyLabel = { easy: 'Лёгкие', medium: 'Средние', hard: 'Сложные' };

  let tasks = [];
  let categories = [];
  let currentAttemptId = null;

  const typesContainer = document.getElementById('typeList');
  const els = {
    difficulty: document.getElementById('difficultyFilter'),
    status: document.getElementById('statusFilter'),
    result: document.getElementById('resultFilter'),
    search: document.getElementById('searchFilter'),
    reset: document.getElementById('resetFilters')
  };

  function resolveExamQuery() {
    if (exam === 'vpr7') return { exam_type: 'vpr', grade: 7 };
    if (exam === 'vpr8') return { exam_type: 'vpr', grade: 8 };
    return { exam_type: 'oge', grade: 9 };
  }

  function ensureSubjectSelect() {
    let sel = document.getElementById('subjectFilter');
    if (sel) return sel;
    const panel = document.querySelector('.filters-panel');
    if (!panel) return null;
    const label = document.createElement('label');
    label.textContent = 'Предмет';
    sel = document.createElement('select');
    sel.id = 'subjectFilter';
    sel.innerHTML = [
      '<option value=\"informatics\">Информатика</option>',
      '<option value=\"math\">Математика</option>',
      '<option value=\"physics\">Физика</option>'
    ].join('');
    label.appendChild(sel);
    panel.prepend(label);
    return sel;
  }

  function normalizeAnswer(value) {
    return String(value).trim().toLowerCase().replace(/\s+/g, ' ');
  }

  async function directApiFetch(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: 'include' });

    let data = null;
    try {
      data = await response.json();
    } catch (_) {
      data = null;
    }

    if (!response.ok) {
      throw new Error(data?.detail || `HTTP ${response.status}`);
    }

    return data;
  }

  async function getTasksApi(query) {
    if (api?.getTasks) return api.getTasks(query);
    const params = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => params.set(k, String(v)));
    return directApiFetch(`/api/tasks?${params.toString()}`);
  }

  async function getTaskCategoriesApi(query) {
    if (api?.getTaskCategories) return api.getTaskCategories(query);
    const params = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => params.set(k, String(v)));
    return directApiFetch(`/api/tasks/categories?${params.toString()}`);
  }

  async function checkTaskApi(taskId, userAnswer) {
    if (api?.checkTask) return api.checkTask(taskId, userAnswer);
    return directApiFetch(`/api/tasks/${taskId}/check`, {
      method: 'POST',
      body: JSON.stringify({ user_answer: userAnswer }),
    });
  }

  async function startAttemptApi() {
    if (api?.startAttempt) return api.startAttempt({ mode: 'practice', variant_id: null });
    return directApiFetch('/api/attempts', {
      method: 'POST',
      body: JSON.stringify({ mode: 'practice', variant_id: null }),
    });
  }

  async function saveAttemptAnswerApi(attemptId, taskId, userAnswer) {
    if (api?.saveAttemptAnswer) {
      return api.saveAttemptAnswer(attemptId, { task_id: taskId, user_answer: userAnswer });
    }
    return directApiFetch(`/api/attempts/${attemptId}/answers`, {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId, user_answer: userAnswer }),
    });
  }

  async function finishAttemptApi(attemptId) {
    if (api?.finishAttempt) return api.finishAttempt(attemptId);
    return directApiFetch(`/api/attempts/${attemptId}/finish`, { method: 'POST' });
  }

  function getToastContainer() {
    let container = document.getElementById('toastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toastContainer';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  function showToast(type, title, message) {
    const container = getToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const titleEl = document.createElement('div');
    titleEl.className = 'toast-title';
    titleEl.textContent = title;
    const messageEl = document.createElement('div');
    messageEl.className = 'toast-message';
    messageEl.textContent = message;
    toast.appendChild(titleEl);
    toast.appendChild(messageEl);
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('toast-hide'), 2500);
    setTimeout(() => toast.remove(), 3000);
  }

  async function loadTasksFromApi() {
    const query = { ...resolveExamQuery(), subject: filters.subject };
    const [result, rawCategories] = await Promise.all([
      getTasksApi(query),
      getTaskCategoriesApi(query),
    ]);

    categories = Array.isArray(rawCategories) ? rawCategories : [];
    if (!Array.isArray(result) || !result.length) {
      throw new Error('По выбранным параметрам нет заданий в базе');
    }

    const idPrefix = exam === 'vpr7' ? 'VPR7' : exam === 'vpr8' ? 'VPR8' : 'OGE';
    return result.map((task, idx) => ({
      id: task.id,
      publicId: `${idPrefix}-${String(task.id).padStart(3, '0')}`,
      typeId: task.category_id || idx + 1,
      typeTitle: task.category_title || task.title || `Задание ${idx + 1}`,
      typeSortOrder: Number(task.category_sort_order ?? 9999),
      difficulty: task.difficulty || 'medium',
      text: task.question,
      hint: task.hint || '',
      userAnswer: '',
      solved: false,
      correct: null,
      correctAnswer: '',
      explanation: '',
    }));
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
    if (typesContainer) typesContainer.innerHTML = '';
  }

  function renderTypes() {
    typesContainer.innerHTML = '';
    const allBtn = document.createElement('button');
    allBtn.className = `task-type-item ${filters.typeId === 'all' ? 'active' : ''}`;
    allBtn.textContent = 'Все типы';
    allBtn.onclick = () => { filters.typeId = 'all'; renderTypes(); renderTasks(); };
    typesContainer.appendChild(allBtn);

    const fromTasks = Array.from(
      new Map(
        tasks.map((task) => [
          String(task.typeId),
          {
            id: String(task.typeId),
            title: task.typeTitle,
            sort_order: Number(task.typeSortOrder ?? 9999),
          },
        ])
      ).values()
    );

    const categoryMap = new Map(categories.map((c) => [String(c.id), c]));
    const mergedTypes = fromTasks
      .map((item) => {
        const linked = categoryMap.get(item.id);
        return linked
          ? { id: String(linked.id), title: linked.title, sort_order: Number(linked.sort_order ?? 9999) }
          : item;
      })
      .sort((a, b) => (a.sort_order - b.sort_order) || a.title.localeCompare(b.title, 'ru'));

    mergedTypes.forEach((t, i) => {
      const b = document.createElement('button');
      b.className = `task-type-item ${String(t.id) === String(filters.typeId) ? 'active' : ''}`;
      b.textContent = `Тема ${i + 1}. ${t.title}`;
      b.onclick = () => { filters.typeId = String(t.id); renderTypes(); renderTasks(); };
      typesContainer.appendChild(b);
    });
  }

  function matches(task) {
    const query = filters.search.trim().toLowerCase();
    const matchesSearch = !query
      || task.text.toLowerCase().includes(query)
      || String(task.publicId || task.id).toLowerCase().includes(query)
      || task.typeTitle.toLowerCase().includes(query);

    const selectedTypeId = filters.typeId === 'all' ? null : String(filters.typeId);
    if (selectedTypeId && String(task.typeId) !== selectedTypeId) return false;
    if (filters.difficulty !== 'all' && task.difficulty !== filters.difficulty) return false;
    if (filters.status === 'solved' && !task.solved) return false;
    if (filters.status === 'unsolved' && task.solved) return false;
    if (filters.result === 'correct' && task.correct !== true) return false;
    if (filters.result === 'wrong' && task.correct !== false) return false;
    if (!matchesSearch) return false;
    return true;
  }

  async function startAttemptIfNeeded() {
    if (currentAttemptId) return;
    try {
      const attempt = await startAttemptApi();
      currentAttemptId = attempt.id;
    } catch (_) {
      // practice works in guest mode too; attempts are optional
    }
  }

  async function saveAnswerToAttempt(task, userAnswer) {
    if (!currentAttemptId) await startAttemptIfNeeded();
    if (!currentAttemptId) return;
    await saveAttemptAnswerApi(currentAttemptId, task.id, userAnswer);
  }

  const finishPracticeBtn=document.createElement('button');
  finishPracticeBtn.type='button'; finishPracticeBtn.className='btn btn-ghost'; finishPracticeBtn.textContent='Завершить тренировку';
  els.reset?.insertAdjacentElement('afterend',finishPracticeBtn);
  finishPracticeBtn.addEventListener('click',async()=>{
    if(!currentAttemptId){showToast('error','Нет активной тренировки','Сначала проверьте хотя бы одно задание.');return;}
    try{const summary=await finishAttemptApi(currentAttemptId);currentAttemptId=null;showToast('success','Тренировка завершена',`Результат: ${summary.score} из ${summary.max_score}`);}catch(err){showToast('error','Ошибка',err.message || 'Не удалось завершить тренировку');}
  });

  function renderTasks() {
    listEl.innerHTML = '';
    const filtered = tasks.filter(matches);
    if (!filtered.length) {
      const article = document.createElement('article');
      article.className = 'task-card';
      const p = document.createElement('p');
      p.className = 'card-text';
      p.textContent = 'По текущим фильтрам задания не найдены.';
      article.appendChild(p);
      listEl.appendChild(article);
      return;
    }

    filtered.forEach((task) => {
      const card = document.createElement('article');
      card.className = `task-card ${task.correct === true ? 'task-correct' : task.correct === false ? 'task-wrong' : ''}`;
      const meta = document.createElement('div');
      meta.className = 'task-meta';

      const idBadge = document.createElement('span');
      idBadge.className = 'task-badge task-id-badge';
      idBadge.setAttribute('data-copy-id', String(task.publicId || task.id));
      idBadge.title = 'Нажмите, чтобы скопировать ID';
      idBadge.textContent = `ID: ${task.publicId || task.id}`;
      meta.appendChild(idBadge);

      const numBadge = document.createElement('span');
      numBadge.className = 'task-badge';
      numBadge.textContent = `№ ${task.id}`;
      meta.appendChild(numBadge);

      const typeBadge = document.createElement('span');
      typeBadge.className = 'task-badge';
      typeBadge.textContent = task.typeTitle;
      meta.appendChild(typeBadge);

      const diffBadge = document.createElement('span');
      diffBadge.className = 'task-badge';
      diffBadge.textContent = difficultyLabel[task.difficulty] || 'Средние';
      meta.appendChild(diffBadge);

      const solvedBadge = document.createElement('span');
      solvedBadge.className = 'task-badge';
      solvedBadge.textContent = task.solved ? 'Решено' : 'Не решено';
      meta.appendChild(solvedBadge);

      if (task.correct !== null) {
        const resultBadge = document.createElement('span');
        resultBadge.className = `result-badge ${task.correct ? 'result-success' : 'result-error'}`;
        resultBadge.textContent = task.correct ? 'Верно' : 'Неверно';
        meta.appendChild(resultBadge);
      }

      const question = document.createElement('p');
      question.textContent = task.text;

      const hint=document.createElement('details');
      const hintTitle=document.createElement('summary'); hintTitle.textContent='Показать подсказку'; hint.appendChild(hintTitle);
      const hintText=document.createElement('p'); hintText.textContent=task.hint || 'Для этого задания подсказка пока не добавлена.'; hint.appendChild(hintText);

      const input = document.createElement('input');
      input.className = 'answer-input';
      input.type = 'text';
      input.value = task.userAnswer;
      input.placeholder = 'Введите ответ';
      input.disabled = task.solved;

      const checkBtn = document.createElement('button');
      checkBtn.className = 'btn btn-primary check-answer-btn';
      checkBtn.type = 'button';
      checkBtn.disabled = task.solved;
      checkBtn.textContent = 'Проверить';

      const resultPlace = document.createElement('div');
      resultPlace.className = 'task-check-result';
      if (task.correct !== null) {
        const inlineBadge = document.createElement('span');
        inlineBadge.className = `result-badge ${task.correct ? 'result-success' : 'result-error'}`;
        inlineBadge.textContent = task.correct ? 'Верно' : 'Неверно';
        resultPlace.appendChild(inlineBadge);
        const answerLine=document.createElement('p'); answerLine.textContent=`Правильный ответ: ${task.correctAnswer || '—'}`;
        resultPlace.appendChild(answerLine);
        if(task.explanation){const explanationLine=document.createElement('p');explanationLine.textContent=`Разбор: ${task.explanation}`;resultPlace.appendChild(explanationLine);}
      }

      card.appendChild(meta);
      card.appendChild(question);
      card.appendChild(hint);
      card.appendChild(input);
      card.appendChild(checkBtn);
      card.appendChild(resultPlace);

      input.addEventListener('input', (e) => {
        task.userAnswer = e.target.value;
      });

      checkBtn.addEventListener('click', async () => {
        const userAnswer = normalizeAnswer(task.userAnswer);
        if (!userAnswer) {
          showToast('error', 'Введите ответ', 'Сначала заполните поле ответа.');
          return;
        }

        try {
          const res = await checkTaskApi(task.id, userAnswer);
          const isCorrect = Boolean(res?.is_correct);

          task.userAnswer = task.userAnswer.trim();
          task.solved = true;
          task.correct = isCorrect;
          task.correctAnswer = String(res?.correct_answer || '');
          task.explanation = String(res?.explanation || '');

          await saveAnswerToAttempt(task, task.userAnswer);

          showToast(
            isCorrect ? 'success' : 'error',
            isCorrect ? 'Верно!' : 'Неверно',
            isCorrect ? 'Отлично, ответ засчитан.' : 'Ответ не совпадает. Ниже показан разбор.'
          );
          renderTasks();
        } catch (err) {
          showToast('error', 'Ошибка API', err.message || 'Не удалось проверить ответ');
        }
      });

      listEl.appendChild(card);
    });
  }

  els.difficulty.addEventListener('change', (e) => { filters.difficulty = e.target.value; renderTasks(); });
  els.status.addEventListener('change', (e) => { filters.status = e.target.value; renderTasks(); });
  els.result.addEventListener('change', (e) => { filters.result = e.target.value; renderTasks(); });
  els.search.addEventListener('input', (e) => { filters.search = e.target.value; renderTasks(); });
  els.reset.addEventListener('click', () => {
    filters.typeId = 'all';
    filters.difficulty = 'all';
    filters.status = 'all';
    filters.result = 'all';
    filters.search = '';
    els.difficulty.value = 'all';
    els.status.value = 'all';
    els.result.value = 'all';
    els.search.value = '';
    renderTypes();
    renderTasks();
  });

  async function init() {
    try {
      const subjectSel = ensureSubjectSelect();
      const subjectFromUrl = String(urlParams.get('subject') || '').trim().toLowerCase();
      if (subjectFromUrl) filters.subject = subjectFromUrl;
      if (subjectSel) subjectSel.value = filters.subject;
      if (subjectSel) {
        subjectSel.addEventListener('change', async (e) => {
          filters.subject = String(e.target.value || 'informatics').toLowerCase();
          tasks = await loadTasksFromApi();
          renderTypes();
          renderTasks();
        });
      }
      tasks = await loadTasksFromApi();
      const categoryFromUrl = String(urlParams.get('category_id') || '').trim();
      if (categoryFromUrl) filters.typeId = categoryFromUrl;
      renderTypes();
      renderTasks();
    } catch (err) {
      renderError(err.message || 'Не удалось загрузить задания из API');
    }
  }

  init();
})();
