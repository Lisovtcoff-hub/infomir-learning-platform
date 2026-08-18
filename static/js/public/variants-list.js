(function () {
  const cfg = document.getElementById('variantsListConfig');
  const grid = document.getElementById('variantsListGrid');
  if (!cfg || !grid) return;

  const examType = String(cfg.dataset.examType || '').trim();
  const gradeRaw = String(cfg.dataset.grade || '').trim();
  const taskPage = String(cfg.dataset.taskPage || '').trim();
  const subject = String(cfg.dataset.subject || 'informatics').trim();
  const grade = gradeRaw ? Number(gradeRaw) : null;

  function createCard(variant, index) {
    const article = document.createElement('article');
    article.className = 'card';

    const icon = document.createElement('div');
    icon.className = 'card-icon';
    const img = document.createElement('img');
    img.src = '../static/images/exam.svg';
    img.alt = variant.title || `Вариант ${index + 1}`;
    icon.appendChild(img);

    const h3 = document.createElement('h3');
    h3.className = 'card-title';
    h3.textContent = variant.title || `Вариант ${index + 1}`;

    const p = document.createElement('p');
    p.className = 'card-text';
    const duration = variant.time_limit_minutes ? ` · ${variant.time_limit_minutes} мин` : '';
    p.textContent = `${variant.description || 'Тренировочный вариант для практики и самопроверки.'}${duration}`;

    const footer = document.createElement('div');
    footer.className = 'card-footer';
    const a = document.createElement('a');
    a.className = 'btn btn-primary';
    a.href = `${taskPage}?variant=${encodeURIComponent(variant.id)}&subject=${encodeURIComponent(subject)}`;
    a.textContent = 'Начать';
    footer.appendChild(a);

    article.appendChild(icon);
    article.appendChild(h3);
    article.appendChild(p);
    article.appendChild(footer);
    return article;
  }

  function renderEmpty() {
    grid.innerHTML = '';
    const article = document.createElement('article');
    article.className = 'card';
    const h3 = document.createElement('h3');
    h3.className = 'card-title';
    h3.textContent = 'Варианты пока не добавлены';
    const p = document.createElement('p');
    p.className = 'card-text';
    p.textContent = 'Скоро здесь появятся варианты из базы данных.';
    article.appendChild(h3);
    article.appendChild(p);
    grid.appendChild(article);
  }

  function renderError(message) {
    grid.innerHTML = '';
    const article = document.createElement('article');
    article.className = 'card';
    const h3 = document.createElement('h3');
    h3.className = 'card-title';
    h3.textContent = 'Не удалось загрузить варианты';
    const p = document.createElement('p');
    p.className = 'card-text';
    p.textContent = message || 'Проверьте подключение к API.';
    article.appendChild(h3);
    article.appendChild(p);
    grid.appendChild(article);
  }

  async function init() {
    const api = window.infomirApi;
    if (!api?.getVariants || !examType || !taskPage) return;
    try {
      const variants = await api.getVariants({ exam_type: examType, grade, subject });
      if (!Array.isArray(variants) || !variants.length) {
        renderEmpty();
        return;
      }
      grid.innerHTML = '';
      variants.forEach((variant, index) => {
        grid.appendChild(createCard(variant, index));
      });
    } catch (err) {
      renderError(err?.message || 'Ошибка API');
    }
  }

  if (window.infomirApi?.getVariants) {
    void init();
  } else {
    document.addEventListener('infomir:api-ready', () => void init(), { once: true });
  }
})();
