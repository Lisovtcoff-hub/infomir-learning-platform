(function () {
  const grid = document.getElementById('tariffsGrid');
  if (!grid) return;
  const featureLabels={theory_basic:'Базовая теория',practice_basic:'Базовые тренировки',theory_full:'Полная теория',practice_full:'Полный банк заданий',variants:'Экзаменационные варианты',advanced_stats:'Расширенная статистика'};

  function parseFeatures(raw) {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw.map((x) => String(x));
    try {
      const parsed = JSON.parse(String(raw));
      return Array.isArray(parsed) ? parsed.map((x) => String(x)) : [];
    } catch (_) {
      return String(raw)
        .split(/[\n,;]+/)
        .map((x) => x.trim())
        .filter(Boolean);
    }
  }

  function getIconByCode(code) {
    const normalized = String(code || '').toLowerCase();
    if (normalized.includes('opt')) return '/static/images/shield.svg';
    if (normalized.includes('base')) return '/static/images/tasks.svg';
    return '/static/images/book.svg';
  }

  function getStoredUser() {
    try {
      const raw = localStorage.getItem('infomir-auth-user');
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  function setStoredUser(user) {
    if (!user) return;
    localStorage.setItem('infomir-auth-user', JSON.stringify(user));
  }

  function renderError(message) {
    grid.innerHTML = '';
    const article = document.createElement('article');
    article.className = 'card tariff-card';
    const h3 = document.createElement('h3');
    h3.className = 'card-title';
    h3.textContent = 'Не удалось загрузить тарифы';
    const p = document.createElement('p');
    p.className = 'card-text';
    p.textContent = message || 'Проверьте подключение к API.';
    article.appendChild(h3);
    article.appendChild(p);
    grid.appendChild(article);
  }

  function renderTariffs(tariffs, currentTariffCode, onChoose, pendingTariffIds = new Set()) {
    grid.innerHTML = '';
    tariffs.forEach((tariff) => {
      const features = parseFeatures(tariff.features_json);
      const card = document.createElement('article');
      card.className = 'card tariff-card';
      if (String(tariff.code) === 'optimum') {
        card.classList.add('recommended');
        const badge = document.createElement('span');
        badge.className = 'tariff-badge';
        badge.textContent = 'Рекомендуем';
        card.appendChild(badge);
      }

      const icon = document.createElement('div');
      icon.className = 'card-icon';
      const img = document.createElement('img');
      img.src = getIconByCode(tariff.code);
      img.alt = tariff.title;
      icon.appendChild(img);

      const title = document.createElement('h3');
      title.className = 'card-title';
      title.textContent = tariff.title;

      const price = document.createElement('p');
      price.className = 'tariff-price';
      const priceNum = Number(tariff.price || 0);
      const formattedPrice = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(priceNum);
      price.textContent = priceNum > 0 ? `${formattedPrice} ₽ / ${Number(tariff.duration_days || 30)} дней` : 'Бесплатно';

      const list = document.createElement('ul');
      list.className = 'feature-list';
      features.forEach((feature) => {
        const li = document.createElement('li');
        li.textContent = featureLabels[feature] || feature;
        list.appendChild(li);
      });

      const footer = document.createElement('div');
      footer.className = 'card-footer';
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn btn-primary';

      const isCurrent = String(currentTariffCode || '') === String(tariff.code || '');
      const isPending = pendingTariffIds.has(Number(tariff.id));
      button.textContent = isCurrent ? 'Текущий тариф' : isPending ? 'Ожидает оплаты' : 'Выбрать тариф';
      if (isCurrent || isPending) button.disabled = true;

      button.addEventListener('click', async () => {
        button.disabled = true;
        const oldText = button.textContent;
        button.textContent = 'Сохраняем...';
        try {
          const selection = await onChoose(String(tariff.code || ''));
          if(selection?.payment?.tariff_id) pendingTariffIds.add(Number(selection.payment.tariff_id));
          const newCode = String(selection?.user?.paid_tariff_code || currentTariffCode || 'free');
          const refreshed = tariffs.map((t) => ({ ...t }));
          renderTariffs(refreshed, newCode, onChoose, pendingTariffIds);
        } catch (e) {
          button.textContent = oldText;
          button.disabled = false;
          alert(e?.message || 'Не удалось выбрать тариф');
        }
      });

      footer.appendChild(button);
      card.appendChild(icon);
      card.appendChild(title);
      card.appendChild(price);
      card.appendChild(list);
      card.appendChild(footer);
      grid.appendChild(card);
    });
  }

  async function init() {
    const api = window.infomirApi;
    if (!api) return;

    try {
      const tariffs = await api.getTariffs();
      let user = getStoredUser();
      const pendingTariffIds = new Set();

      try {
        user = await api.auth.me();
        setStoredUser(user);
        if(api?.getMyPayments){const payments=await api.getMyPayments();(payments || []).filter((item)=>item.status==='pending').forEach((item)=>pendingTariffIds.add(Number(item.tariff_id)));}
      } catch (_) {
        // guest mode: selection disabled below
      }

      const expiry=user?.paid_tariff_expires_at ? new Date(user.paid_tariff_expires_at) : null;
      const expired=expiry && !Number.isNaN(expiry.getTime()) && expiry.getTime() <= Date.now();
      const currentTariffCode = expired ? 'free' : String(user?.paid_tariff_code || 'free');

      const onChoose = async (code) => {
        if (!user) throw new Error('Сначала войдите в аккаунт');
        if (code === 'free') throw new Error('Бесплатный тариф уже доступен без оплаты');
        if (!api?.createPayment) throw new Error('API оплаты недоступно');
        const payment = await api.createPayment(code);
        alert(`Заявка на оплату №${payment.id} создана. Статус: ${payment.status}.\n\n${payment.payment_instructions || 'Следуйте инструкции администратора.'}`);
        return {user,payment};
      };

      renderTariffs(Array.isArray(tariffs) ? tariffs : [], currentTariffCode, onChoose, pendingTariffIds);
    } catch (err) {
      renderError(err?.message || 'Ошибка API');
    }
  }

  if (window.infomirApi) {
    void init();
  } else {
    document.addEventListener('infomir:api-ready', () => void init(), { once: true });
  }
})();
