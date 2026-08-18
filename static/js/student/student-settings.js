(function () {
  const form = document.getElementById('studentSettingsForm');
  if (!form) return;

  const firstNameInput = document.getElementById('firstName');
  const lastNameInput = document.getElementById('lastName');
  const classInput = document.getElementById('studentClass');
  const emailInput = document.getElementById('studentEmail');
  const saveBtn = document.getElementById('saveSettingsBtn');
  const cancelBtn = document.getElementById('cancelSettingsBtn');
  const successMsg = document.getElementById('settingsSuccessMsg');
  const changeAvatarBtn = document.getElementById('changeAvatarBtn');
  const avatarFileInput = document.getElementById('avatarFileInput');
  const passwordForm = document.getElementById('passwordChangeForm');
  const passwordMsg = document.getElementById('passwordChangeMsg');
  const resetTheoryProgressBtn = document.getElementById('resetTheoryProgressBtn');
  const resetTheoryProgressMsg = document.getElementById('resetTheoryProgressMsg');
  const getApi = () => window.infomirApi;


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
    setTimeout(() => toast.classList.add('toast-hide'), 2200);
    setTimeout(() => toast.remove(), 2600);
  }

  function extractApiErrorMessage(data, fallback) {
    const normalize = (text) =>
      String(text || '')
        .replace(/^Value error,\s*/i, '')
        .trim();

    if (!data) return fallback;
    if (typeof data.detail === 'string' && data.detail.trim()) return normalize(data.detail);
    if (Array.isArray(data.detail) && data.detail.length) {
      const first = data.detail[0];
      if (typeof first === 'string' && first.trim()) return normalize(first);
      if (first && typeof first.msg === 'string' && first.msg.trim()) return normalize(first.msg);
    }
    return fallback;
  }

  function buildAuthHeaders() {
    const api = getApi();
    const headers = { 'Content-Type': 'application/json' };
    const token = api?.auth?.getToken?.();
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
  }

  const defaultProfile = {
    firstName: 'Ученик',
    lastName: '',
    className: '8 класс',
    avatarUrl: '',
    email: '',
  };

  let baselineProfile = { ...defaultProfile };

  function setFieldError(fieldName, message) {
    const errorEl = document.querySelector(`[data-error-for="${fieldName}"]`);
    const inputEl = form.elements[fieldName];
    if (!errorEl || !inputEl) return;
    errorEl.textContent = message || '';
    inputEl.classList.toggle('is-invalid', Boolean(message));
  }

  function clearErrors() {
    setFieldError('firstName', '');
    setFieldError('lastName', '');
  }

  function buildProfile() {
    return {
      firstName: firstNameInput.value.trim(),
      lastName: lastNameInput.value.trim(),
      className: classInput.value,
      avatarUrl: baselineProfile.avatarUrl || '',
      email: baselineProfile.email || '',
    };
  }





  function getInitial(name, fallback) {
    const value = String(name || '').trim();
    return value ? value[0].toUpperCase() : fallback;
  }

  function applyAvatar(el, avatarUrl, fallbackInitial) {
    if (!el) return;
    if (avatarUrl) {
      el.style.backgroundImage = `url("${avatarUrl}")`;
      el.classList.add('has-image');
      el.textContent = '';
      return;
    }
    el.style.backgroundImage = '';
    el.classList.remove('has-image');
    el.textContent = fallbackInitial;
  }

  function applyProfile(profile) {
    const fullName = `${profile.firstName} ${profile.lastName}`.trim();
    const initial = getInitial(profile.firstName, 'У');

    document.querySelectorAll('[data-student-fullname]').forEach((el) => {
      el.textContent = fullName;
    });
    document.querySelectorAll('[data-student-class]').forEach((el) => {
      el.textContent = profile.className;
    });
    document.querySelectorAll('[data-student-fullname-large]').forEach((el) => {
      el.textContent = fullName;
    });
    document.querySelectorAll('[data-student-class-large]').forEach((el) => {
      el.textContent = profile.className;
    });

    document.querySelectorAll('[data-student-avatar], [data-auth-avatar]').forEach((el) => {
      applyAvatar(el, profile.avatarUrl, initial);
    });
    document.querySelectorAll('[data-student-avatar-large]').forEach((el) => {
      applyAvatar(el, profile.avatarUrl, initial);
    });
  }

  function syncForm(profile) {
    firstNameInput.value = profile.firstName;
    lastNameInput.value = profile.lastName;
    classInput.value = profile.className;
    if (emailInput) emailInput.value = profile.email || '';
  }

  function validate() {
    const profile = buildProfile();
    let valid = true;

    if (!profile.firstName) {
      setFieldError('firstName', 'Введите имя');
      valid = false;
    } else {
      setFieldError('firstName', '');
    }

    if (!profile.lastName) {
      setFieldError('lastName', 'Введите фамилию');
      valid = false;
    } else {
      setFieldError('lastName', '');
    }

    saveBtn.disabled = !valid;
    return valid;
  }

  function splitFullName(fullName) {
    const parts = String(fullName || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return { firstName: defaultProfile.firstName, lastName: defaultProfile.lastName };
    return { firstName: parts[0], lastName: parts.slice(1).join(' ') };
  }

  function classNameFromGrade(grade) {
    if (!grade) return defaultProfile.className;
    return `${grade} класс`;
  }

  function gradeFromClassName(className) {
    const gradeMatch = String(className).match(/\d+/);
    return gradeMatch ? Number(gradeMatch[0]) : null;
  }

  async function loadProfileFromApi() {
    const api = getApi();
    if (!api?.auth?.me) return null;
    const me = await api.auth.me();
    const meProfile = await api.auth.meProfile();
    const nameParts = splitFullName(me.name);
    return {
      firstName: nameParts.firstName,
      lastName: nameParts.lastName || defaultProfile.lastName,
      className: classNameFromGrade(me.grade),
      avatarUrl: meProfile?.avatar_url || '',
      email: me.email || '',
    };
  }

  async function patchUserMain(profile) {
    const api = getApi();
    const fullName = `${profile.firstName} ${profile.lastName}`.trim();
    const grade = gradeFromClassName(profile.className);
    const response = await fetch(`${api.baseUrl}/api/users/me`, {
      method: 'PATCH',
      headers: buildAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify({ name: fullName, grade }),
    });
    if (!response.ok) throw new Error('Не удалось сохранить данные профиля');
    return response.json();
  }

  async function patchUserAvatar(avatarUrl) {
    const api = getApi();
    const response = await fetch(`${api.baseUrl}/api/users/me/profile`, {
      method: 'PATCH',
      headers: buildAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify({ avatar_url: avatarUrl }),
    });
    if (!response.ok) throw new Error('Не удалось сохранить аватар');
    return response.json();
  }


  function emitUserUpdated(profile) {
    const api = getApi();
    const stored = api?.auth?.getStoredUser?.() || {};
    const merged = {
      ...stored,
      name: `${profile.firstName} ${profile.lastName}`.trim(),
      grade: gradeFromClassName(profile.className),
      avatar_url: profile.avatarUrl || null,
    };
    api?.auth?.setStoredUser?.(merged);
    document.dispatchEvent(new CustomEvent('infomir:user-updated', { detail: merged }));
  }

  async function init() {
    const api = getApi();
    if (!api?.auth) return;
    try {
      const profile = (await loadProfileFromApi()) || { ...defaultProfile };
      baselineProfile = { ...profile };
      syncForm(profile);
      applyProfile(profile);
      validate();
    } catch (_) {
      successMsg.textContent = 'Не удалось загрузить данные профиля';
      successMsg.style.color = '#c03a35';
    }
  }

  form.addEventListener('input', () => {
    successMsg.textContent = '';
    successMsg.style.color = '';
    validate();
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    successMsg.textContent = '';
    successMsg.style.color = '';
    if (!validate()) return;

    const profile = buildProfile();
    applyProfile(profile);

    try {
      await patchUserMain(profile);
      baselineProfile = { ...profile };
      emitUserUpdated(profile);
      successMsg.textContent = 'Настройки успешно сохранены';
    } catch (err) {
      successMsg.textContent = err.message || 'Ошибка сохранения настроек';
      successMsg.style.color = '#c03a35';
    }
  });

  cancelBtn.addEventListener('click', () => {
    syncForm(baselineProfile);
    applyProfile(baselineProfile);
    clearErrors();
    successMsg.textContent = '';
    successMsg.style.color = '';
    validate();
  });

  if (changeAvatarBtn && avatarFileInput) {
    changeAvatarBtn.addEventListener('click', () => avatarFileInput.click());
    avatarFileInput.addEventListener('change', async () => {
      const file = avatarFileInput.files?.[0];
      if (!file) return;
      if (!file.type.startsWith('image/')) {
        successMsg.textContent = 'Выберите файл изображения';
        successMsg.style.color = '#c03a35';
        return;
      }
      if (file.size > 2 * 1024 * 1024) {
        successMsg.textContent = 'Максимальный размер аватара: 2 МБ';
        successMsg.style.color = '#c03a35';
        return;
      }

      const reader = new FileReader();
      reader.onload = async () => {
        const avatarUrl = String(reader.result || '');
        const next = { ...baselineProfile, avatarUrl };
        applyProfile(next);
        successMsg.textContent = '';
        successMsg.style.color = '';
        try {
          await patchUserAvatar(avatarUrl);
          baselineProfile = next;
          emitUserUpdated(next);
          successMsg.textContent = 'Аватар успешно обновлён';
        } catch (err) {
          applyProfile(baselineProfile);
          successMsg.textContent = err.message || 'Не удалось сохранить аватар';
          successMsg.style.color = '#c03a35';
        } finally {
          avatarFileInput.value = '';
        }
      };
      reader.readAsDataURL(file);
    });
  }

  async function changePassword(oldPassword, newPassword) {
    const api = getApi();
    if (!api?.baseUrl) {
      throw new Error('Требуется авторизация');
    }
    const response = await fetch(`${api.baseUrl}/api/users/me/password`, {
      method: 'PATCH',
      headers: buildAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify({
        old_password: oldPassword,
        new_password: newPassword,
      }),
    });
    if (!response.ok) {
      let message = 'Не удалось изменить пароль';
      try {
        const data = await response.json();
        if (data?.detail === 'Current password is incorrect') {
          message = 'Старый пароль указан неверно';
        } else {
          message = extractApiErrorMessage(data, message);
        }
      } catch (_) {
        // no-op
      }
      throw new Error(message);
    }
  }

  if (passwordForm) {
    passwordForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (passwordMsg) {
        passwordMsg.textContent = '';
        passwordMsg.style.color = '';
      }

      const oldPassword = String(passwordForm.oldPassword?.value || '');
      const newPassword = String(passwordForm.newPassword?.value || '');
      const confirmNewPassword = String(passwordForm.confirmNewPassword?.value || '');

      if (!oldPassword || !newPassword || !confirmNewPassword) {
        if (passwordMsg) {
          passwordMsg.textContent = 'Заполните все поля пароля';
          passwordMsg.style.color = '#c03a35';
        }
        return;
      }

      if (newPassword.length < 8) {
        if (passwordMsg) {
          passwordMsg.textContent = 'Новый пароль должен быть не короче 8 символов';
          passwordMsg.style.color = '#c03a35';
        }
        return;
      }

      if (newPassword !== confirmNewPassword) {
        if (passwordMsg) {
          passwordMsg.textContent = 'Подтверждение пароля не совпадает';
          passwordMsg.style.color = '#c03a35';
        }
        return;
      }

      try {
        await changePassword(oldPassword, newPassword);
        passwordForm.reset();
        if (passwordMsg) {
          passwordMsg.textContent = 'Пароль успешно изменён';
        }
      } catch (err) {
        if (passwordMsg) {
          passwordMsg.textContent = err.message || 'Ошибка смены пароля';
          passwordMsg.style.color = '#c03a35';
        }
      }
    });
  }

  if (resetTheoryProgressBtn) {
    resetTheoryProgressBtn.addEventListener('click', async () => {
      const api = getApi();
      resetTheoryProgressBtn.disabled = true;
      if (resetTheoryProgressMsg) {
        resetTheoryProgressMsg.textContent = '';
        resetTheoryProgressMsg.style.color = '';
      }
      try {
        let result = null;
        if (api?.resetMyTheoryProgress) {
          result = await api.resetMyTheoryProgress();
        } else {
          const response = await fetch('/api/theory/progress/my', {
            method: 'DELETE',
            credentials: 'include',
            headers: buildAuthHeaders(),
          });
          if (!response.ok) {
            let message = 'Не удалось сбросить прогресс тем';
            try {
              const data = await response.json();
              message = extractApiErrorMessage(data, message);
            } catch (_) {
              // no-op
            }
            throw new Error(message);
          }
          result = await response.json();
        }
        const deleted = Number(result?.deleted || 0);
        if (resetTheoryProgressMsg) {
          resetTheoryProgressMsg.textContent = '';
        }
        showToast(
          'success',
          'Прогресс сброшен',
          deleted > 0
            ? `Удалено отметок: ${deleted}.`
            : 'Пройденные темы очищены.'
        );
      } catch (err) {
        if (resetTheoryProgressMsg) {
          resetTheoryProgressMsg.textContent = '';
          resetTheoryProgressMsg.style.color = '#c03a35';
        }
        showToast('error', 'Ошибка сброса', err?.message || 'Не удалось сбросить прогресс тем');
      } finally {
        resetTheoryProgressBtn.disabled = false;
      }
    });
  }



  if (window.infomirApi?.auth) {
    init();
  } else {
    document.addEventListener('infomir:api-ready', init, { once: true });
  }
})();
