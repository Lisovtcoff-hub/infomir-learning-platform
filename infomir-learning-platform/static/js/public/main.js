function initMain() {
  if (!document.querySelector('.site-header')) return;
  if (document.body.dataset.mainInitialized === '1') return;
  document.body.dataset.mainInitialized = '1';
  const html = document.documentElement;
  const themeToggle = document.getElementById('themeToggle');
  const savedTheme = localStorage.getItem('infomir-theme');
  if (savedTheme) html.setAttribute('data-theme', savedTheme);

  const API_BASE = window.location.origin;
  const AUTH_TOKEN_KEY = 'infomir-auth-token';
  const AUTH_USER_KEY = 'infomir-auth-user';
  const inviteCodeFromUrl = new URLSearchParams(window.location.search).get('invite') || '';
  const subjectFromUrl = new URLSearchParams(window.location.search).get('subject') || '';
  const ROLE_HOME = {
    student: '/templates/student/student-dashboard.html',
    teacher: '/templates/teacher/dashboard.html',
    admin: '/admin',
  };

  const getToken = () => '';
  const setToken = () => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
  };

  const setStoredUser = (user) => {
    if (!user) {
      localStorage.removeItem(AUTH_USER_KEY);
      return;
    }
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
  };

  const getStoredUser = () => {
    try {
      const raw = localStorage.getItem(AUTH_USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  };

  async function apiFetch(path, options = {}) {
    const extractErrorMessage = (payload, status) => {
      const detail = payload?.detail;
      if (typeof detail === 'string' && detail.trim()) return detail;
      if (Array.isArray(detail) && detail.length) {
        const first = detail[0];
        if (typeof first === 'string') return first;
        if (first && typeof first === 'object') {
          if (typeof first.msg === 'string' && first.msg.trim()) return first.msg;
          if (Array.isArray(first.loc) && first.loc.length && typeof first.msg === 'string') {
            return `${first.loc.join('.')} - ${first.msg}`;
          }
        }
      }
      if (detail && typeof detail === 'object') {
        if (typeof detail.message === 'string' && detail.message.trim()) return detail.message;
        if (typeof detail.msg === 'string' && detail.msg.trim()) return detail.msg;
      }
      return `HTTP ${status}`;
    };

    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      credentials: 'include',
    });

    let data = null;
    try {
      data = await response.json();
    } catch (_) {
      data = null;
    }

    if (!response.ok) {
      const message = extractErrorMessage(data, response.status);
      const err = new Error(message);
      err.status = response.status;
      throw err;
    }

    return data;
  }

  window.infomirApi = {
    baseUrl: API_BASE,
    auth: {
      getToken,
      setToken,
      getStoredUser,
      setStoredUser,
      async register(payload) {
        return apiFetch('/api/auth/register', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
      },
      async login(payload) {
        return apiFetch('/api/auth/login', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
      },
      async me() {
        return apiFetch('/api/users/me');
      },
      async meProfile() {
        return apiFetch('/api/users/me/profile');
      },
      async logout() {
        try {
          await apiFetch('/api/auth/logout', { method: 'POST' });
        } catch (_) {
          // ignore logout transport errors; local cleanup still happens
        }
        setToken('');
        setStoredUser(null);
      },
    },
    async getTheoryTopics(grade, subject) {
      const params = new URLSearchParams();
      params.set('grade', String(grade));
      if (subject) params.set('subject', String(subject));
      return apiFetch(`/api/theory?${params.toString()}`);
    },
    async getMyTheoryProgress() {
      return apiFetch('/api/theory/progress/my');
    },
    async resetMyTheoryProgress() {
      return apiFetch('/api/theory/progress/my', { method: 'DELETE' });
    },
    async getMyCompletedTheoryTopics(grade) {
      const q = (grade === undefined || grade === null || grade === '')
        ? ''
        : `?grade=${encodeURIComponent(String(grade))}`;
      return apiFetch(`/api/theory/progress/my/topics${q}`);
    },
    async completeTheoryTopic(topicId) {
      return apiFetch(`/api/theory/progress/${encodeURIComponent(topicId)}/complete`, {
        method: 'POST',
      });
    },
    async getTasks(query = {}) {
      const params = new URLSearchParams();
      Object.entries(query).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') params.set(k, String(v));
      });
      const q = params.toString();
      return apiFetch(`/api/tasks${q ? `?${q}` : ''}`);
    },
    async getTaskCategories(query = {}) {
      const params = new URLSearchParams();
      Object.entries(query).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') params.set(k, String(v));
      });
      const q = params.toString();
      return apiFetch(`/api/tasks/categories${q ? `?${q}` : ''}`);
    },
    async checkTask(taskId, userAnswer) {
      return apiFetch(`/api/tasks/${taskId}/check`, {
        method: 'POST',
        body: JSON.stringify({ user_answer: userAnswer }),
      });
    },
    async startAttempt(payload) {
      return apiFetch('/api/attempts', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    async saveAttemptAnswer(attemptId, payload) {
      return apiFetch(`/api/attempts/${attemptId}/answers`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    async finishAttempt(attemptId) {
      return apiFetch(`/api/attempts/${attemptId}/finish`, { method: 'POST' });
    },
    async getAttemptResult(attemptId) {
      return apiFetch(`/api/attempts/${attemptId}/result`);
    },
    async getMyAttempts() {
      return apiFetch('/api/attempts/my');
    },
    async getMyAttemptStats() {
      return apiFetch('/api/attempts/my/stats');
    },
    async getMyWeekActivity() {
      return apiFetch('/api/attempts/my/activity-week');
    },
    async getMyRecommendedTopics() {
      return apiFetch('/api/attempts/my/recommended-topics');
    },
    async getMyLeaderboard() {
      return apiFetch('/api/users/me/leaderboard');
    },
    async getTariffs() {
      return apiFetch('/api/tariffs');
    },
    async setMyTariff(tariffCode) {
      return apiFetch('/api/users/me/tariff', {
        method: 'PATCH',
        body: JSON.stringify({ tariff_code: tariffCode }),
      });
    },
    async createPayment(tariffCode) {
      return apiFetch('/api/payments', {
        method: 'POST',
        body: JSON.stringify({ tariff_code: tariffCode }),
      });
    },
    async getMyPayments() {
      return apiFetch('/api/payments/my');
    },
    async getVariants(query = {}) {
      const params = new URLSearchParams();
      Object.entries(query).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') params.set(k, String(v));
      });
      const q = params.toString();
      return apiFetch(`/api/variants${q ? `?${q}` : ''}`);
    },
    async getVariantById(variantId) {
      return apiFetch(`/api/variants/${encodeURIComponent(variantId)}`);
    },
    async getTaskById(taskId) {
      return apiFetch(`/api/tasks/${encodeURIComponent(taskId)}`);
    },
    async getTeacherMe() {
      return apiFetch('/api/teacher/me');
    },
    async getTeacherStudents(query = {}) {
      const params = new URLSearchParams();
      Object.entries(query).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') params.set(k, String(v));
      });
      const q = params.toString();
      return apiFetch(`/api/teacher/students${q ? `?${q}` : ''}`);
    },
    async getTeacherGroups() {
      return apiFetch('/api/teacher/groups');
    },
    async createTeacherGroup(title) {
      return apiFetch('/api/teacher/groups', {
        method: 'POST',
        body: JSON.stringify({ title }),
      });
    },
    async removeTeacherGroupStudent(groupId, studentId) {
      return apiFetch(`/api/teacher/groups/${encodeURIComponent(groupId)}/students/${encodeURIComponent(studentId)}`, {
        method: 'DELETE',
      });
    },
  };

  const normalizeRole = (role) => String(role || '').trim().toLowerCase();

  const getRoleHomePath = (role) => {
    const normalized = normalizeRole(role);
    return ROLE_HOME[normalized] || '/templates/public/index.html';
  };

  function preserveSubjectInLinks() {
    const subject = String(subjectFromUrl || '').trim().toLowerCase();
    if (!subject) return;
    document.querySelectorAll('a[href]').forEach((link) => {
      const rawHref = String(link.getAttribute('href') || '').trim();
      if (!rawHref || rawHref.startsWith('#') || rawHref.startsWith('mailto:') || rawHref.startsWith('tel:')) return;
      if (/^https?:\/\//i.test(rawHref)) return;
      if (!/\.html(\?|$)/i.test(rawHref)) return;
      try {
        const u = new URL(rawHref, window.location.href);
        if (!u.searchParams.has('subject')) u.searchParams.set('subject', subject);
        const rel = `${u.pathname.split('/').pop() || ''}${u.search}${u.hash}`;
        link.setAttribute('href', rel);
      } catch (_) {
        // ignore invalid links
      }
    });
  }

  const redirectToRoleHome = (user) => {
    const target = getRoleHomePath(user?.role);
    const current = window.location.pathname;
    if (current !== target) {
      window.location.assign(target);
    }
  };
  document.dispatchEvent(new Event('infomir:api-ready'));

  function formatGrade(grade) {
    if (grade === null || grade === undefined || grade === '') return 'Класс не указан';
    return `${grade} класс`;
  }

  function buildAvatarText(name) {
    const raw = String(name || '').trim();
    if (!raw) return 'У';
    const parts = raw.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    return parts[0][0].toUpperCase();
  }

  function applyAvatar(el, user) {
    if (!el) return;
    if (user?.avatar_url) {
      el.style.backgroundImage = `url("${user.avatar_url}")`;
      el.classList.add('has-image');
      el.textContent = '';
      return;
    }
    el.style.backgroundImage = '';
    el.classList.remove('has-image');
    el.textContent = buildAvatarText(user?.name || '');
  }

  const examNavState = {
    saved: false,
    theoryClassName: '',
    theoryHref: '',
    theoryToggleDisplay: '',
    theoryDropdownDisplay: '',
    vprClassName: '',
    vprHref: '',
    toggleDisplay: '',
    dropdownDisplay: '',
    ogeDisplay: '',
  };

  function normalizeGrade(user) {
    const fromAny = (value) => {
      if (value === null || value === undefined) return null;
      const match = String(value).match(/\d+/);
      if (!match) return null;
      const parsed = Number(match[0]);
      return Number.isFinite(parsed) ? parsed : null;
    };

    return (
      fromAny(user?.grade)
      ?? fromAny(user?.className)
      ?? fromAny(user?.class_name)
      ?? null
    );
  }

  function setMenuItemVisible(item, visible, baseDisplay = '') {
    if (!item) return;
    item.hidden = !visible;
    item.style.display = visible ? baseDisplay : 'none';
  }

  function applyExamNavByGrade(user) {
    const theoryLink = document.querySelector('a[data-nav="theory"]');
    const vprLink = document.querySelector('a[data-nav="vpr"]');
    const ogeLink = document.querySelector('a[data-nav="oge"]');
    const theoryItem = theoryLink?.closest('.menu-item');
    const vprItem = vprLink?.closest('.menu-item');
    const ogeItem = ogeLink?.closest('.menu-item');
    if (!theoryLink || !theoryItem || !vprLink || !vprItem) return;

    const theoryToggle = theoryItem.querySelector('.dropdown-toggle');
    const theoryDropdown = theoryItem.querySelector('.dropdown');
    const theoryOptions = Array.from(theoryItem.querySelectorAll('.dropdown li'));
    const toggle = vprItem.querySelector('.dropdown-toggle');
    const dropdown = vprItem.querySelector('.dropdown');
    const vprOptions = Array.from(vprItem.querySelectorAll('.dropdown li'));

    if (!examNavState.saved) {
      examNavState.theoryClassName = theoryItem.className;
      examNavState.theoryHref = theoryLink.getAttribute('href') || 'theory.html';
      examNavState.theoryToggleDisplay = theoryToggle?.style.display || '';
      examNavState.theoryDropdownDisplay = theoryDropdown?.style.display || '';
      examNavState.vprClassName = vprItem.className;
      examNavState.vprHref = vprLink.getAttribute('href') || 'vpr.html';
      examNavState.toggleDisplay = toggle?.style.display || '';
      examNavState.dropdownDisplay = dropdown?.style.display || '';
      examNavState.ogeDisplay = ogeItem?.style.display || '';
      examNavState.saved = true;
    }

    setMenuItemVisible(theoryItem, true);
    theoryItem.className = examNavState.theoryClassName;
    theoryItem.classList.remove('open');
    theoryLink.setAttribute('href', examNavState.theoryHref);
    if (theoryToggle) theoryToggle.style.display = examNavState.theoryToggleDisplay;
    if (theoryDropdown) theoryDropdown.style.display = examNavState.theoryDropdownDisplay;
    theoryOptions.forEach((li) => {
      li.hidden = false;
    });

    setMenuItemVisible(vprItem, true);
    vprItem.className = examNavState.vprClassName;
    vprItem.classList.remove('open');
    vprLink.setAttribute('href', examNavState.vprHref);
    if (toggle) toggle.style.display = examNavState.toggleDisplay;
    if (dropdown) dropdown.style.display = examNavState.dropdownDisplay;
    setMenuItemVisible(ogeItem, true, examNavState.ogeDisplay);

    if (!user) return;

    const grade = normalizeGrade(user);
    if (grade === 7 || grade === 8) {
      theoryItem.classList.remove('has-dropdown', 'open');
      theoryLink.setAttribute('href', `/templates/public/theory-${grade}.html`);
      if (theoryToggle) theoryToggle.style.display = 'none';
      if (theoryDropdown) theoryDropdown.style.display = 'none';
      theoryOptions.forEach((li) => {
        const href = li.querySelector('a')?.getAttribute('href') || '';
        li.hidden = !href.includes(`-${grade}.html`);
      });

      vprItem.classList.remove('has-dropdown', 'open');
      vprLink.setAttribute('href', `/templates/public/vpr-${grade}.html`);
      if (toggle) toggle.style.display = 'none';
      if (dropdown) dropdown.style.display = 'none';
      vprOptions.forEach((li) => {
        const href = li.querySelector('a')?.getAttribute('href') || '';
        li.hidden = !href.includes(`-${grade}.html`);
      });
      setMenuItemVisible(ogeItem, false, examNavState.ogeDisplay);
      return;
    }

    if (grade === 9) {
      theoryItem.classList.remove('has-dropdown', 'open');
      theoryLink.setAttribute('href', '/templates/public/theory-9.html');
      if (theoryToggle) theoryToggle.style.display = 'none';
      if (theoryDropdown) theoryDropdown.style.display = 'none';
      theoryOptions.forEach((li) => {
        const href = li.querySelector('a')?.getAttribute('href') || '';
        li.hidden = !href.includes('-9.html');
      });
      setMenuItemVisible(vprItem, false);
    }
  }

  function applyAuthHeader(user) {
    const guestWrap = document.querySelector('[data-auth-guest]');
    const userWrap = document.querySelector('[data-auth-user]');
    if (!guestWrap || !userWrap) return;

    const showGuest = () => {
      guestWrap.hidden = false;
      guestWrap.style.display = 'flex';
      userWrap.hidden = true;
      userWrap.style.display = 'none';
    };

    const showUser = () => {
      guestWrap.hidden = true;
      guestWrap.style.display = 'none';
      userWrap.hidden = false;
      userWrap.style.display = '';
    };

    if (!user) {
      showGuest();
      applyExamNavByGrade(null);
      return;
    }

    showUser();

    const fullNameEl = userWrap.querySelector('[data-auth-fullname]');
    const gradeEl = userWrap.querySelector('[data-auth-grade]');
    const avatarEl = userWrap.querySelector('[data-auth-avatar]');
    const cabinetLinkEl = userWrap.querySelector('[data-profile-cabinet-link]');

    if (fullNameEl) fullNameEl.textContent = user.name || 'Ученик';
    if (gradeEl) gradeEl.textContent = formatGrade(user.grade);
    applyAvatar(avatarEl, user);
    if (cabinetLinkEl) cabinetLinkEl.setAttribute('href', getRoleHomePath(user.role));
    applyExamNavByGrade(user);
  }

  async function syncAuthState() {
    const cached = getStoredUser();
    if (cached) applyAuthHeader(cached);

    try {
      const me = await window.infomirApi.auth.me();
      try {
        const profile = await window.infomirApi.auth.meProfile();
        me.avatar_url = profile?.avatar_url || cached?.avatar_url || null;
      } catch (_) {
        me.avatar_url = cached?.avatar_url || null;
      }
      window.infomirApi.auth.setStoredUser(me);
      applyAuthHeader(me);
    } catch (_) {
      await window.infomirApi.auth.logout();
      applyAuthHeader(null);
    }
  }

  document.addEventListener('click', async (e) => {
    const logoutLink = e.target.closest('[data-logout-link]');
    if (!logoutLink) return;
    e.preventDefault();
    await window.infomirApi.auth.logout();
    applyAuthHeader(null);
    window.location.assign('/templates/public/index.html');
  });

  document.addEventListener('infomir:user-updated', (e) => {
    const user = e.detail || getStoredUser();
    applyAuthHeader(user || null);
  });

  void syncAuthState();

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', next);
      localStorage.setItem('infomir-theme', next);
    });
  }

  const getToastContainer = () => {
    let container = document.getElementById('toastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toastContainer';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  };

  const showToast = (type, title, message) => {
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
    setTimeout(() => toast.classList.add('toast-hide'), 2000);
    setTimeout(() => toast.remove(), 2400);
  };

  const copyText = async (text) => {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const temp = document.createElement('textarea');
    temp.value = text;
    document.body.appendChild(temp);
    temp.select();
    document.execCommand('copy');
    temp.remove();
  };

  document.addEventListener('click', async (e) => {
    const target = e.target.closest('[data-copy-id]');
    if (!target) return;
    const value = target.getAttribute('data-copy-id');
    if (!value) return;
    try {
      await copyText(value);
      showToast('success', 'ID скопирован', `${value} добавлен в буфер обмена.`);
    } catch (_) {
      showToast('error', 'Ошибка копирования', 'Не удалось скопировать ID.');
    }
  });

  const scrollTopBtn = document.getElementById('scrollTopBtn');
  if (scrollTopBtn) {
    const toggleScrollTopBtn = () => {
      scrollTopBtn.classList.toggle('show', window.scrollY > 300);
    };

    window.addEventListener('scroll', toggleScrollTopBtn, { passive: true });
    toggleScrollTopBtn();

    scrollTopBtn.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  const burgerBtn = document.getElementById('burgerBtn');
  const mainNav = document.getElementById('mainNav');
  if (burgerBtn && mainNav) {
    burgerBtn.addEventListener('click', () => {
      const open = mainNav.classList.toggle('open');
      burgerBtn.setAttribute('aria-expanded', String(open));
    });

    mainNav.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', () => {
        mainNav.classList.remove('open');
        burgerBtn.setAttribute('aria-expanded', 'false');
      });
    });
  }

  document.querySelectorAll('.has-dropdown .dropdown-toggle').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      btn.closest('.has-dropdown')?.classList.toggle('open');
    });
  });

  const profileToggle = document.querySelector('[data-profile-toggle]');
  const profileWrap = profileToggle?.closest('.profile-menu-wrap');
  if (profileToggle && profileWrap) {
    profileToggle.addEventListener('click', (e) => {
      e.preventDefault();
      const open = profileWrap.classList.toggle('open');
      profileToggle.setAttribute('aria-expanded', String(open));
    });

    document.addEventListener('click', (e) => {
      if (profileWrap.contains(e.target)) return;
      profileWrap.classList.remove('open');
      profileToggle.setAttribute('aria-expanded', 'false');
    });
  }

  const openModal = (id) => {
    const modal = document.getElementById(id);
    if (modal) {
      modal.classList.add('open');
      modal.setAttribute('aria-hidden', 'false');
    }
  };

  const applyInviteCodeToForm = () => {
    if (!inviteCodeFromUrl || !registerForm) return;
    let inviteInput = registerForm.querySelector('[name="invite_code"]');
    if (!inviteInput) {
      inviteInput = document.createElement('input');
      inviteInput.type = 'hidden';
      inviteInput.name = 'invite_code';
      registerForm.appendChild(inviteInput);
    }
    inviteInput.value = inviteCodeFromUrl;
  };

  const closeModal = (modal) => {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
  };

  document.querySelectorAll('[data-open-modal]').forEach((btn) => {
    btn.addEventListener('click', () => openModal(btn.dataset.openModal));
  });

  document.querySelectorAll('[data-close-modal]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.modal');
      if (modal) closeModal(modal);
    });
  });

  document.querySelectorAll('.modal').forEach((modal) => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal(modal);
    });
  });

  document.querySelectorAll('[data-switch-modal]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetId = btn.dataset.switchModal;
      document.querySelectorAll('.modal.open').forEach((m) => closeModal(m));
      openModal(targetId);
    });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal.open').forEach((m) => closeModal(m));
    }
  });

  preserveSubjectInLinks();

  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const formData = new FormData(loginForm);
      const email = String(formData.get('email') || '').trim();
      const password = String(formData.get('password') || '');
      if (!email || !password) {
        showToast('error', 'Ошибка входа', 'Введите email и пароль.');
        return;
      }

      try {
        const loginData = await window.infomirApi.auth.login({ email, password });
        window.infomirApi.auth.setToken(loginData?.access_token || '');
        const me = await window.infomirApi.auth.me();
        try {
          const profile = await window.infomirApi.auth.meProfile();
          me.avatar_url = profile?.avatar_url || getStoredUser()?.avatar_url || null;
        } catch (_) {
          me.avatar_url = getStoredUser()?.avatar_url || null;
        }
        window.infomirApi.auth.setStoredUser(me);
        showToast('success', 'Вход выполнен', 'Вы успешно авторизовались.');
        loginForm.reset();
        const modal = loginForm.closest('.modal');
        if (modal) closeModal(modal);
        applyAuthHeader(me);
        redirectToRoleHome(me);
      } catch (err) {
        const message = err?.status === 401 ? 'Неверный email или пароль.' : (err.message || 'Не удалось войти.');
        showToast('error', 'Ошибка входа', message);
      }
    });
  }

  const registerForm = document.getElementById('registerForm');
  if (registerForm) {
    applyInviteCodeToForm();
    if (inviteCodeFromUrl) openModal('registerModal');

    registerForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const formData = new FormData(registerForm);
      const firstName = String(formData.get('name') || '').trim();
      const lastName = String(formData.get('last_name') || '').trim();
      const gradeRaw = String(formData.get('grade') || '').trim();
      const grade = gradeRaw ? Number(gradeRaw) : null;
      const name = [firstName, lastName].filter(Boolean).join(' ').trim();
      const email = String(formData.get('email') || '').trim();
      const password = String(formData.get('password') || '');
      const passwordRepeat = String(formData.get('password_repeat') || '');
      const inviteCode = String(formData.get('invite_code') || '').trim();
      if (!firstName || !lastName || !email || !password || !grade) {
        showToast('error', 'Ошибка регистрации', 'Заполните имя, фамилию, класс, email и пароль.');
        return;
      }
      if (password !== passwordRepeat) {
        showToast('error', 'Ошибка регистрации', 'Пароли не совпадают.');
        return;
      }

      try {
        await window.infomirApi.auth.register({ name, email, password, grade, invite_code: inviteCode || null });
        const loginData = await window.infomirApi.auth.login({ email, password });
        window.infomirApi.auth.setToken(loginData?.access_token || '');
        const me = await window.infomirApi.auth.me();
        try {
          const profile = await window.infomirApi.auth.meProfile();
          me.avatar_url = profile?.avatar_url || null;
        } catch (_) {
          me.avatar_url = null;
        }
        window.infomirApi.auth.setStoredUser(me);
        showToast('success', 'Регистрация успешна', 'Вы автоматически вошли в аккаунт.');
        registerForm.reset();
        const modal = registerForm.closest('.modal');
        if (modal) closeModal(modal);
        applyAuthHeader(me);
        redirectToRoleHome(me);
      } catch (err) {
        showToast('error', 'Ошибка регистрации', err.message || 'Не удалось зарегистрироваться.');
      }
    });
  }

  document.querySelectorAll('.faq-item .faq-q').forEach((btn) => {
    btn.addEventListener('click', () => {
      btn.closest('.faq-item')?.classList.toggle('open');
    });
  });

  const page = window.location.pathname.split('/').pop() || 'index.html';
  const map = {
    'index.html': null,
    'vpr-7.html': 'vpr',
    'vpr-8.html': 'vpr',
    'vpr.html': 'vpr',
    'training-vpr-7.html': 'vpr',
    'training-vpr-8.html': 'vpr',
    'variant-vpr-7.html': 'vpr',
    'variant-vpr-8.html': 'vpr',
    'variant-vpr-7-task.html': 'vpr',
    'variant-vpr-8-task.html': 'vpr',
    'oge.html': 'oge',
    'training-oge.html': 'oge',
    'variant-oge.html': 'oge',
    'variant-oge-task.html': 'oge',
    'theory-7.html': 'theory',
    'theory-8.html': 'theory',
    'theory-9.html': 'theory',
    'theory.html': 'theory',
    'student-dashboard.html': 'progress',
    'student-settings.html': 'progress',
    'about.html': 'about',
    'tariffs.html': 'tariffs'
  };

  const activeKey = map[page];
  if (activeKey) {
    const activeLink = document.querySelector(`[data-nav="${activeKey}"]`);
    if (activeLink) activeLink.classList.add('active');
  }
}

document.addEventListener('DOMContentLoaded', initMain);
document.addEventListener('infomir:layout-ready', initMain);





