(function () {
  let selectedGroupForAction = null;

  function openGroupModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
  }

  function closeGroupModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
  }

  function closeAllGroupModals() {
    closeGroupModal('teacherGroupEditModal');
    closeGroupModal('teacherGroupDeleteModal');
  }

  function openNoticeModal(title, text) {
    const modal = document.getElementById('teacherNoticeModal');
    if (!modal) return;
    const titleEl = document.getElementById('teacherNoticeTitle');
    const textEl = document.getElementById('teacherNoticeText');
    if (titleEl) titleEl.textContent = String(title || 'Уведомление');
    if (textEl) textEl.textContent = String(text || '');
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
  }

  function closeNoticeModal() {
    const modal = document.getElementById('teacherNoticeModal');
    if (!modal) return;
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
  }

  async function teacherApiFallback(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    const response = await fetch(`${window.location.origin}${path}`, {
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
      throw new Error(data?.detail || `HTTP ${response.status}`);
    }
    return data;
  }

  function patchTeacherProfileLinks() {
    const profileMenu = document.querySelector('[data-profile-menu]');
    if (!profileMenu) return;
    const links = profileMenu.querySelectorAll('a');
    if (!links.length) return;
    links[0].setAttribute('href', '/templates/teacher/dashboard.html');
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

  function fillGroupSelect(groups) {
    const select = document.getElementById('teacherGroupSelect');
    if (!select) return;
    select.innerHTML = '';
    if (!groups.length) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'Сначала создайте группу';
      select.appendChild(option);
      return;
    }
    groups.forEach((g) => {
      const option = document.createElement('option');
      option.value = String(g.id);
      option.textContent = `${g.title} (учеников: ${g.students_count})`;
      select.appendChild(option);
    });
  }

  function formatMoney(value) {
    return `${new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value || 0))} ₽`;
  }

  function formatDateTime(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function renderEarningsHistory(history) {
    const listEl = document.getElementById('teacherEarningsHistoryList');
    if (!listEl) return;
    listEl.innerHTML = '';
    const items = Array.isArray(history?.items) ? history.items : [];
    const withdrawals = Array.isArray(history?.withdrawals) ? history.withdrawals : [];
    const timeline = [
      ...items.map((item) => ({ type: 'earning', at: item?.paid_at || '', payload: item })),
      ...withdrawals.map((item) => ({ type: 'withdrawal', at: item?.created_at || '', payload: item })),
    ].sort((a, b) => {
      const aTime = new Date(a.at || 0).getTime() || 0;
      const bTime = new Date(b.at || 0).getTime() || 0;
      return bTime - aTime;
    });
    if (!timeline.length) {
      setListItems(listEl, [], 'Начислений пока нет');
      return;
    }
    timeline.forEach((entry) => {
      const li = document.createElement('li');
      const left = document.createElement('span');
      const right = document.createElement('small');
      if (entry.type === 'withdrawal') {
        const item = entry.payload || {};
        li.classList.add('teacher-withdrawal-item');
        left.textContent = 'Вывод средств';
        const status = item.status === 'paid' ? 'выплачено' : item.status === 'rejected' ? 'отклонено' : 'на рассмотрении';
        right.textContent = `${formatDateTime(item.created_at)} • ${formatMoney(item.amount)} • ${status}`;
      } else {
        const item = entry.payload || {};
        const student = `${item.student_name || 'Ученик'} (ID ${item.student_id})`;
        const group = item.group_title ? `Группа: ${item.group_title}` : 'Группа: —';
        left.textContent = `${student} • ${item.tariff_title} • ${group}`;
        right.textContent = `${formatDateTime(item.paid_at)} • Оплата: ${formatMoney(item.tariff_price)} • Вам: ${formatMoney(item.teacher_share)}`;
      }
      li.appendChild(left);
      li.appendChild(right);
      listEl.appendChild(li);
    });
  }

  function renderEarningsSummary(history) {
    const totalEl = document.getElementById('teacherEarningsTotal');
    const balanceEl = document.getElementById('teacherEarningsBalance');
    const total = Number(history?.total_earned ?? 0);
    const balance = Number(history?.current_balance ?? total);
    if (totalEl) totalEl.textContent = formatMoney(total);
    if (balanceEl) balanceEl.textContent = formatMoney(balance);
  }

  function renderStats(stats) {
    const studentsEl = document.getElementById('teacherStatStudents');
    const avgEl = document.getElementById('teacherStatAverage');
    const earningsEl = document.getElementById('teacherStatEarnings');
    if (studentsEl) studentsEl.textContent = String(stats?.connected_students_count ?? 0);
    if (avgEl) {
      const value = Number(stats?.average_grade ?? 0);
      avgEl.textContent = value > 0 ? value.toFixed(1) : '—';
    }
    if (earningsEl) earningsEl.textContent = formatMoney(stats?.current_balance ?? stats?.earnings_total ?? 0);
  }

  function renderGroupedStudents(groups, api, reload) {
    const listEl = document.getElementById('teacherStudentsList');
    if (!listEl) return;
    listEl.innerHTML = '';

    if (!Array.isArray(groups) || !groups.length) {
      setListItems(listEl, [], 'Нет групп с учениками');
      return;
    }

    groups.forEach((group) => {
      const li = document.createElement('li');
      li.className = 'teacher-group-item';

      const details = document.createElement('details');
      details.className = 'teacher-group-details';

      const summary = document.createElement('summary');
      const head = document.createElement('div');
      head.className = 'teacher-group-head';
      const title = document.createElement('span');
      title.className = 'teacher-group-title';
      title.textContent = `${group.title} - учеников: ${group.students_count}`;
      const actions = document.createElement('span');
      actions.className = 'teacher-group-actions';

      const editBtn = document.createElement('button');
      editBtn.type = 'button';
      editBtn.className = 'teacher-group-icon-btn';
      editBtn.title = 'Редактировать группу';
      editBtn.setAttribute('aria-label', 'Редактировать группу');
      editBtn.textContent = '✎';
      editBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        e.stopPropagation();
        selectedGroupForAction = group;
        const input = document.getElementById('teacherGroupEditTitle');
        if (input) input.value = String(group.title || '');
        openGroupModal('teacherGroupEditModal');
      });

      const deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.className = 'teacher-group-icon-btn teacher-group-icon-btn-danger';
      deleteBtn.title = group.students_count > 0
        ? 'Удаление доступно только для пустой группы'
        : 'Удалить пустую группу';
      deleteBtn.setAttribute('aria-label', 'Удалить группу');
      deleteBtn.textContent = '🗑';
      deleteBtn.disabled = Number(group.students_count || 0) > 0;
      deleteBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (Number(group.students_count || 0) > 0) return;
        selectedGroupForAction = group;
        const text = document.getElementById('teacherGroupDeleteText');
        if (text) text.textContent = `Удалить группу "${group.title}"? Это действие нельзя отменить.`;
        openGroupModal('teacherGroupDeleteModal');
      });

      actions.appendChild(editBtn);
      actions.appendChild(deleteBtn);
      head.appendChild(title);
      head.appendChild(actions);
      summary.appendChild(head);
      details.appendChild(summary);

      const studentsWrap = document.createElement('div');
      studentsWrap.className = 'teacher-group-students';

      if (!group.students?.length) {
        const empty = document.createElement('p');
        empty.className = 'teacher-group-empty';
        empty.textContent = 'В группе пока нет учеников';
        studentsWrap.appendChild(empty);
      } else {
        group.students.forEach((student) => {
          const row = document.createElement('a');
          row.className = 'teacher-student-row';
          row.href = `/templates/teacher/student-details.html?student_id=${encodeURIComponent(student.id)}&group_id=${encodeURIComponent(group.id)}`;
          row.style.display = 'block';

          const name = document.createElement('strong');
          name.textContent = `${String(student.name || '').trim()} `;
          row.appendChild(name);

          const meta = document.createElement('small');
          const predicted = Number(student.predicted_grade || 0);
          const predictedLabel = predicted > 0 ? predicted.toFixed(1) : '—';
          const tariffLabel = student.tariff_title || 'Без тарифа';
          meta.textContent = `Предполагаемая оценка: ${predictedLabel} | Тариф: ${tariffLabel}`;
          row.appendChild(meta);

          studentsWrap.appendChild(row);
        });
      }

      details.appendChild(studentsWrap);
      li.appendChild(details);
      listEl.appendChild(li);
    });
  }

  async function loadData() {
    const api = window.infomirApi;
    if (!api) return;
    const [stats, groups, groupedStudents] = await Promise.all([
      api.getTeacherDashboardStats(),
      api.getTeacherGroups(),
      api.getTeacherGroupsWithStudents(),
    ]);

    renderStats(stats);
    fillGroupSelect(groups);
    renderGroupedStudents(groupedStudents, api, loadData);
  }

  async function init() {
    const api = window.infomirApi;
    if (!api) return;

    try {
      const teacherMe = await api.getTeacherMe();
      const codeEl = document.getElementById('teacherInviteCode');
      if (codeEl && teacherMe?.invite_code) {
        codeEl.textContent = teacherMe.invite_code;
        codeEl.setAttribute('data-copy-id', teacherMe.invite_code);
      }
      const commissionLabel=document.getElementById('teacherCommissionLabel');
      if(commissionLabel && Number.isFinite(Number(teacherMe?.commission_percent))){commissionLabel.textContent=`Заработано (${Number(teacherMe.commission_percent)}%)`;}
      patchTeacherProfileLinks();
    } catch (_) {
      window.location.assign('/templates/public/index.html');
      return;
    }

    try {
      await loadData();
    } catch (err) {
      setListItems(document.getElementById('teacherStudentsList'), [`Ошибка: ${err.message || 'не удалось загрузить учеников'}`]);
    }

    const createGroupForm = document.getElementById('teacherCreateGroupForm');
    if (createGroupForm) {
      createGroupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const title = String(document.getElementById('teacherGroupTitle')?.value || '').trim();
        if (!title) return;
        try {
          await api.createTeacherGroup(title);
          createGroupForm.reset();
          await loadData();
        } catch (_) {
          alert('Не удалось создать группу.');
        }
      });
    }

    const earningsBtn = document.getElementById('teacherStatEarningsBtn');
    if (earningsBtn) {
      earningsBtn.addEventListener('click', async () => {
        try {
          const history = await api.getTeacherEarningsHistory();
          renderEarningsSummary(history);
          renderEarningsHistory(history);
        } catch (err) {
          renderEarningsSummary({ total_earned: 0, current_balance: 0 });
          setListItems(
            document.getElementById('teacherEarningsHistoryList'),
            [`Ошибка загрузки истории: ${err?.message || 'неизвестная ошибка'}`]
          );
        }
      });
    }

    const withdrawBtn = document.getElementById('teacherWithdrawBtn');
    if (withdrawBtn) {
      withdrawBtn.addEventListener('click', async () => {
        try {
          await api.createTeacherWithdrawal();
          await loadData();
          const history = await api.getTeacherEarningsHistory();
          renderEarningsSummary(history);
          renderEarningsHistory(history);
          openNoticeModal('Уведомление', 'Вывод средств осуществлен');
        } catch (err) {
          if (err?.message === 'Current balance is zero') {
            openNoticeModal('Уведомление', 'Баланс нулевой');
            return;
          }
          openNoticeModal('Уведомление', `Не удалось выполнить вывод: ${err?.message || 'неизвестная ошибка'}`);
        }
      });
    }

    const noticeOkBtn = document.getElementById('teacherNoticeOkBtn');
    if (noticeOkBtn) noticeOkBtn.addEventListener('click', () => closeNoticeModal());
    document.querySelectorAll('[data-notice-close]').forEach((btn) => {
      btn.addEventListener('click', () => closeNoticeModal());
    });
    const noticeModal = document.getElementById('teacherNoticeModal');
    if (noticeModal) {
      noticeModal.addEventListener('click', (e) => {
        if (e.target === noticeModal) closeNoticeModal();
      });
    }

    document.querySelectorAll('[data-group-modal-close]').forEach((btn) => {
      btn.addEventListener('click', () => closeAllGroupModals());
    });
    document.querySelectorAll('#teacherGroupEditModal, #teacherGroupDeleteModal').forEach((modal) => {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) closeAllGroupModals();
      });
    });

    const editForm = document.getElementById('teacherGroupEditForm');
    if (editForm) {
      editForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const group = selectedGroupForAction;
        if (!group?.id) return;
        const clean = String(document.getElementById('teacherGroupEditTitle')?.value || '').trim();
        if (!clean || clean === String(group.title || '').trim()) {
          closeAllGroupModals();
          return;
        }
        try {
          if (api?.updateTeacherGroup) {
            await api.updateTeacherGroup(group.id, clean);
          } else {
            await teacherApiFallback(`/api/teacher/groups/${encodeURIComponent(group.id)}`, {
              method: 'PATCH',
              body: JSON.stringify({ title: clean }),
            });
          }
          closeAllGroupModals();
          await loadData();
        } catch (err) {
          alert(`Не удалось переименовать группу: ${err?.message || 'неизвестная ошибка'}`);
        }
      });
    }

    const deleteCancel = document.getElementById('teacherGroupDeleteCancel');
    if (deleteCancel) deleteCancel.addEventListener('click', () => closeAllGroupModals());
    const deleteConfirm = document.getElementById('teacherGroupDeleteConfirm');
    if (deleteConfirm) {
      deleteConfirm.addEventListener('click', async () => {
        const group = selectedGroupForAction;
        if (!group?.id) return;
        try {
          if (api?.deleteTeacherGroup) {
            await api.deleteTeacherGroup(group.id);
          } else {
            await teacherApiFallback(`/api/teacher/groups/${encodeURIComponent(group.id)}`, {
              method: 'DELETE',
            });
          }
          closeAllGroupModals();
          await loadData();
        } catch (err) {
          alert(`Не удалось удалить группу: ${err?.message || 'неизвестная ошибка'}`);
        }
      });
    }
  }

  if (window.infomirApi) {
    void init();
  } else {
    document.addEventListener('infomir:api-ready', () => { void init(); }, { once: true });
  }
})();
