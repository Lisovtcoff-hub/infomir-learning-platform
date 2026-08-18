(function(){
  const T = {
    brand: 'Админка Infomir',
    logout: 'Выйти',
    theory: 'Теория',
    tasks: 'Задания',
    variants: 'Варианты',
    students: 'Ученики',
    teachers: 'Учителя',
    admins: 'Администраторы',
    tariffs: 'Тарифы',
    payments: 'Платежи',
    withdrawals: 'Выплаты',
    settings: 'Настройки',
    cls7: '7 класс', cls8: '8 класс', cls9: '9 класс',
    new: 'Новая', save: 'Сохранить', del: 'Удалить'
  };

  const SUBJECTS = [
    { v: 'informatics', l: 'Информатика' },
    { v: 'math', l: 'Математика' },
    { v: 'physics', l: 'Физика' },
  ];

  const api = async (path, opts={}) => {
    const res = await fetch(`/admin-api${path}`, { ...opts, headers: {'Content-Type':'application/json', 'X-Requested-With':'InfomirAdmin', ...(opts.headers||{})}, credentials:'include' });
    let data = null; try { data = await res.json(); } catch(_) {}
    if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
    return data;
  };

  const byId = (id) => document.getElementById(id);
  const setMsg = (t) => { const n=byId('adminMsg'); if(n) n.textContent=t; };
  const fillForm = (form, item) => [...form.elements].forEach((el)=>{ if(el.name) el.value = item?.[el.name] ?? ''; });
  const toObj = (form) => {
    const o = Object.fromEntries(new FormData(form).entries());
    const n = (v) => (String(v||'').trim()==='' ? null : Number(v));
    if ('grade' in o) o.grade = n(o.grade);
    if ('sort_order' in o) o.sort_order = Number(o.sort_order || 0);
    if ('category_id' in o) o.category_id = n(o.category_id);
    if ('time_limit_minutes' in o) o.time_limit_minutes = n(o.time_limit_minutes);
    if ('task_ids' in o) {
      o.task_ids = String(o.task_ids || '').split(',').map(x=>Number(x.trim())).filter(Number.isInteger);
    }
    return o;
  };

  const state = {
    tab:'home',
    theoryGrade:7,
    taskGrade:7,
    theorySubject:'informatics',
    taskSubject:'informatics',
    variantSubject:'informatics',
    articles:[],
    tests:[],
    variants:[],
  };

  const tabs = [
    {id:'home', label:'Главная', view:'home'},
    {id:'theory', label:T.theory, view:'theory', grades:[7,8,9], gradeKey:'theoryGrade'},
    {id:'tasks', label:T.tasks, view:'tasks', grades:[7,8,9], gradeKey:'taskGrade'},
    {id:'variants', label:T.variants, view:'variants'},
    {id:'students', label:T.students, view:'students'},
    {id:'teachers', label:T.teachers, view:'teachers'},
    {id:'admins', label:T.admins, view:'admins'},
    {id:'tariffs', label:T.tariffs, view:'tariffs'},
    {id:'payments', label:T.payments, view:'payments'},
    {id:'withdrawals', label:T.withdrawals, view:'withdrawals'},
    {id:'settings', label:T.settings, view:'settings'},
  ];

  function renderMenu(){
    byId('adminBrand').textContent = T.brand;
    byId('logoutBtn').textContent = T.logout;
    const root = byId('topMenu');
    root.innerHTML = '';
    tabs.forEach((t)=>{
      const li = document.createElement('li');
      const hasDropdown = Array.isArray(t.grades) && t.grades.length > 0;
      if (hasDropdown) li.classList.add('has-dropdown');

      const mainBtn = document.createElement('button');
      mainBtn.type = 'button';
      mainBtn.textContent = t.label;
      if (state.tab === t.id) mainBtn.classList.add('active');
      mainBtn.addEventListener('click', () => switchTab(t.id));
      li.appendChild(mainBtn);

      if (hasDropdown) {
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'dropdown-toggle';
        toggle.setAttribute('aria-label', `Submenu ${t.label}`);
        toggle.textContent = 'v';
        toggle.addEventListener('click', (e) => {
          e.stopPropagation();
          li.classList.toggle('open');
        });
        li.appendChild(toggle);

        const dropdown = document.createElement('ul');
        dropdown.className = 'dropdown';
        const currentGrade = Number(state[t.gradeKey]);
        t.grades.forEach((grade) => {
          const subLi = document.createElement('li');
          const subBtn = document.createElement('button');
          subBtn.type = 'button';
          subBtn.textContent = `${grade} класс`;
          if (state.tab === t.id && currentGrade === grade) subBtn.classList.add('active');
          subBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            state[t.gradeKey] = grade;
            await switchTab(t.id);
          });
          subLi.appendChild(subBtn);
          dropdown.appendChild(subLi);
        });
        li.appendChild(dropdown);
      }
      root.appendChild(li);
    });
  }

  function showView(id){
    document.querySelectorAll('.admin-view').forEach(v=>v.classList.remove('active'));
    byId(`view-${id}`).classList.add('active');
  }

  function renderClassSubmenu(rootId, current, onPick){
    const root = byId(rootId); if (!root) return;
    root.innerHTML='';
    [{v:7,l:T.cls7},{v:8,l:T.cls8},{v:9,l:T.cls9}].forEach(x=>{
      const b=document.createElement('button'); b.type='button'; b.className='btn btn-ghost'; b.textContent=x.l;
      if (x.v===current) b.classList.add('active');
      b.addEventListener('click', ()=>onPick(x.v));
      root.appendChild(b);
    });
  }

  function renderSubjectSubmenu(rootId, current, onPick){
    const root = byId(rootId); if (!root) return;
    root.innerHTML='';
    SUBJECTS.forEach(x=>{
      const b=document.createElement('button'); b.type='button'; b.className='btn btn-ghost'; b.textContent=x.l;
      if (x.v===current) b.classList.add('active');
      b.addEventListener('click', ()=>onPick(x.v));
      root.appendChild(b);
    });
  }

  function renderButtons(rootId, items, label){
    const r=byId(rootId); r.innerHTML='';
    items.forEach(x=>{ const b=document.createElement('button'); b.type='button'; b.className='btn btn-ghost'; b.textContent=`#${x.id} ${label(x)}`; b.dataset.id=String(x.id); r.appendChild(b); });
  }

  function renderTable(rootId, rows, cols){
    const root=byId(rootId);
    root.replaceChildren();
    const table=document.createElement('table'); table.className='admin-table';
    const thead=document.createElement('thead'); const header=document.createElement('tr');
    cols.forEach((col)=>{ const th=document.createElement('th'); th.textContent=col.h; header.appendChild(th); });
    thead.appendChild(header); table.appendChild(thead);
    const tbody=document.createElement('tbody');
    rows.forEach((row)=>{
      const tr=document.createElement('tr');
      cols.forEach((col)=>{
        const td=document.createElement('td');
        if (col.render) col.render(row,td);
        else td.textContent=String(col.v?.(row) ?? '');
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody); root.appendChild(table);
  }

  async function loadTheory(){
    byId('theoryTitle').textContent = `${T.theory}: ${state.theoryGrade} класс`;
    renderClassSubmenu('theorySubmenu', state.theoryGrade, async (g)=>{ state.theoryGrade=g; await loadTheory(); });
    renderSubjectSubmenu('theorySubjectSubmenu', state.theorySubject, async (s)=>{ state.theorySubject=s; await loadTheory(); });
    state.articles = await api(`/articles?grade=${state.theoryGrade}&subject=${encodeURIComponent(state.theorySubject)}`);
    renderButtons('articleList', state.articles, x=>x.slug);
  }

  async function loadTasks(){
    byId('tasksTitle').textContent = `${T.tasks}: ${state.taskGrade} класс`;
    renderClassSubmenu('tasksSubmenu', state.taskGrade, async (g)=>{ state.taskGrade=g; await loadTasks(); });
    renderSubjectSubmenu('tasksSubjectSubmenu', state.taskSubject, async (s)=>{ state.taskSubject=s; await loadTasks(); });
    state.tests = await api(`/tests?grade=${state.taskGrade}&subject=${encodeURIComponent(state.taskSubject)}`);
    renderButtons('testList', state.tests, x=>x.title);
  }

  async function loadVariants(){
    byId('variantsTitle').textContent = T.variants;
    renderSubjectSubmenu('variantsSubjectSubmenu', state.variantSubject, async (s)=>{ state.variantSubject=s; await loadVariants(); });
    state.variants = await api(`/variants?subject=${encodeURIComponent(state.variantSubject)}`);
    renderButtons('variantList', state.variants, x=>`${x.title} (${x.subject||'informatics'} ${x.exam_type||''} ${x.grade||''})`);
  }

  async function loadRole(role, rootId, titleId, title){
    byId(titleId).textContent = title;
    const rows = await api(`/users?role=${role}`);
    renderTable(rootId, rows, [
      {h:'ID', v:r=>r.id}, {h:'Имя', v:r=>r.name}, {h:'Email', v:r=>r.email},
      {h:'Роль', v:r=>r.role}, {h:'Класс', v:r=>r.grade}, {h:'Статус', v:r=>r.is_active ? 'Активен' : 'Отключён'},
      {h:'Действия', render:(row,td)=>{
        const edit=document.createElement('button'); edit.type='button'; edit.className='btn btn-ghost'; edit.textContent='Изменить';
        edit.addEventListener('click', async ()=>{
          const newRole=window.prompt('Роль: student, teacher или admin', row.role);
          if (newRole===null) return;
          const activeText=window.prompt('Активен: да или нет', row.is_active ? 'да' : 'нет');
          if (activeText===null) return;
          const isActive=['да','yes','true','1'].includes(activeText.trim().toLowerCase());
          const normalizedRole=newRole.trim().toLowerCase();
          let newPassword=null;
          if(normalizedRole==='admin' && row.role!=='admin'){
            newPassword=window.prompt('Новый пароль администратора: минимум 12 символов, верхний/нижний регистр и цифра');
            if(newPassword===null) return;
          }
          await api(`/users/${row.id}`,{method:'PATCH',body:JSON.stringify({role:normalizedRole,is_active:isActive,new_password:newPassword})});
          await loadRole(role,rootId,titleId,title); setMsg('Пользователь обновлён');
        });
        td.appendChild(edit);
      }}
    ]);
  }

  async function loadTariffs(){
    byId('tariffsTitle').textContent = T.tariffs;
    const rows = await api('/tariffs');
    renderTable('tariffsTable', rows, [
      {h:'ID', v:r=>r.id}, {h:'Код', v:r=>r.code}, {h:'Название', v:r=>r.title}, {h:'Цена', v:r=>r.price},
      {h:'Дней', v:r=>r.duration_days}, {h:'Активен', v:r=>r.is_active ? 'Да' : 'Нет'},
      {h:'Действия', render:(row,td)=>{
        const edit=document.createElement('button'); edit.type='button'; edit.className='btn btn-ghost'; edit.textContent='Изменить';
        edit.addEventListener('click', async ()=>{
          const title=window.prompt('Название тарифа',row.title); if(title===null)return;
          const price=window.prompt('Цена',String(row.price)); if(price===null)return;
          const days=window.prompt('Срок действия, дней',String(row.duration_days)); if(days===null)return;
          const features=window.prompt('Функции тарифа в JSON',row.features_json || '[]'); if(features===null)return;
          try { JSON.parse(features); } catch (_) { setMsg('Некорректный JSON функций'); return; }
          await api(`/tariffs/${row.id}`,{method:'PUT',body:JSON.stringify({title:title.trim(),price:Number(price),duration_days:Number(days),description:row.description,features_json:features,is_active:row.is_active})});
          await loadTariffs(); setMsg('Тариф обновлён');
        });
        td.appendChild(edit);
      }}
    ]);
  }

  async function loadPayments(){
    byId('paymentsTitle').textContent=T.payments;
    const rows=await api('/payments');
    renderTable('paymentsTable',rows,[
      {h:'ID',v:r=>r.id},{h:'Пользователь',v:r=>`${r.user_id} · ${r.user_email || ''}`},{h:'Тариф',v:r=>r.tariff_title || r.tariff_id},
      {h:'Сумма',v:r=>r.amount},{h:'Статус',v:r=>r.status},{h:'Создан',v:r=>r.created_at},
      {h:'Действия',render:(row,td)=>{
        if(row.status==='pending'){
          const paid=document.createElement('button'); paid.type='button'; paid.className='btn btn-primary'; paid.textContent='Подтвердить';
          paid.addEventListener('click',async()=>{await api(`/payments/${row.id}/mark-paid`,{method:'POST'});await loadPayments();setMsg('Платёж подтверждён');});
          td.appendChild(paid);
          const cancel=document.createElement('button'); cancel.type='button'; cancel.className='btn btn-ghost'; cancel.textContent='Отменить';
          cancel.addEventListener('click',async()=>{if(!window.confirm('Отменить платёжную заявку?'))return;await api(`/payments/${row.id}/cancel`,{method:'POST'});await loadPayments();setMsg('Заявка отменена');});
          td.appendChild(cancel);
        }
        if(row.status==='paid'){
          const refund=document.createElement('button'); refund.type='button'; refund.className='btn btn-ghost'; refund.textContent='Возврат';
          refund.addEventListener('click',async()=>{if(!window.confirm('Отменить подписку и оформить возврат?'))return;await api(`/payments/${row.id}/refund`,{method:'POST'});await loadPayments();setMsg('Возврат проведён');});
          td.appendChild(refund);
        }
      }}
    ]);
  }

  async function loadWithdrawals(){
    byId('withdrawalsTitle').textContent=T.withdrawals;
    const rows=await api('/withdrawals');
    renderTable('withdrawalsTable',rows,[
      {h:'ID',v:r=>r.id},{h:'Преподаватель',v:r=>`${r.teacher_id} · ${r.teacher_email || ''}`},{h:'Сумма',v:r=>r.amount},
      {h:'Статус',v:r=>r.status},{h:'Комментарий',v:r=>r.note},{h:'Создана',v:r=>r.created_at},
      {h:'Действия',render:(row,td)=>{
        const edit=document.createElement('button'); edit.type='button'; edit.className='btn btn-ghost'; edit.textContent='Статус';
        edit.addEventListener('click',async()=>{const status=window.prompt('requested, processing, paid или rejected',row.status);if(status===null)return;const note=window.prompt('Комментарий',row.note || '');if(note===null)return;await api(`/withdrawals/${row.id}`,{method:'PATCH',body:JSON.stringify({status:status.trim(),note:note.trim() || null})});await loadWithdrawals();setMsg('Заявка обновлена');});
        td.appendChild(edit);
      }}
    ]);
  }

  async function loadSettings(){
    byId('settingsTitle').textContent = T.settings;
    const me = await api('/auth/me');
    const box=byId('settingsBox'); box.replaceChildren();
    const account=document.createElement('p'); account.textContent=`Аккаунт: ${me.name} (${me.email})`;
    const host=document.createElement('p'); host.textContent=`Хост: ${window.location.host}`;
    box.append(account,host);
  }

  function makeHeroCard(title, text, actionsHtml, extraHtml = ''){
    return `<article class="admin-hero-card"><h3>${title}</h3><p>${text}</p>${extraHtml}<div class="admin-hero-actions">${actionsHtml}</div></article>`;
  }

  async function loadHome(){
    const root = byId('adminHomeCards');
    if (!root) return;

    let a7 = []; let a8 = []; let a9 = []; let variants = [];
    try {
      [a7, a8, a9, variants] = await Promise.all([
        api('/articles?grade=7&subject=informatics').catch(() => []),
        api('/articles?grade=8&subject=informatics').catch(() => []),
        api('/articles?grade=9&subject=informatics').catch(() => []),
        api('/variants?subject=informatics').catch(() => []),
      ]);
    } catch (_) {}

    const c7 = Array.isArray(a7) ? a7.length : 0;
    const c8 = Array.isArray(a8) ? a8.length : 0;
    const c9 = Array.isArray(a9) ? a9.length : 0;
    const variantsCount = Array.isArray(variants) ? variants.length : 0;

    root.innerHTML = [
      makeHeroCard(
        'Теория',
        'Количество статей по классам и быстрый переход к редактированию.',
        `<button type="button" class="btn btn-primary" data-go-tab="theory">Открыть теорию</button>
         <button type="button" class="btn btn-ghost" data-go-tab="theory" data-grade="7">7 класс</button>
         <button type="button" class="btn btn-ghost" data-go-tab="theory" data-grade="8">8 класс</button>
         <button type="button" class="btn btn-ghost" data-go-tab="theory" data-grade="9">9 класс</button>`,
        `<div class="admin-hero-stats"><span>7 класс: <strong>${c7}</strong></span><span>8 класс: <strong>${c8}</strong></span><span>9 класс: <strong>${c9}</strong></span></div>`
      ),
      makeHeroCard(
        'Задания',
        'Переход к редактированию заданий по классам.',
        `<button type="button" class="btn btn-primary" data-go-tab="tasks">Открыть задания</button>
         <button type="button" class="btn btn-ghost" data-go-tab="tasks" data-grade="7">7 класс</button>
         <button type="button" class="btn btn-ghost" data-go-tab="tasks" data-grade="8">8 класс</button>
         <button type="button" class="btn btn-ghost" data-go-tab="tasks" data-grade="9">9 класс</button>`
      ),
      makeHeroCard(
        'Варианты',
        `Всего вариантов: ${variantsCount}.`,
        `<button type="button" class="btn btn-primary" data-go-tab="variants">Перейти к редактированию</button>
         <button type="button" class="btn btn-ghost" data-go-tab="variants">Открыть список</button>`
      ),
      makeHeroCard('Ученики', 'Управление учениками.', `<button type="button" class="btn btn-primary" data-go-tab="students">Открыть</button>`),
      makeHeroCard('Учителя', 'Управление учителями.', `<button type="button" class="btn btn-primary" data-go-tab="teachers">Открыть</button>`),
      makeHeroCard('Админы', 'Управление администраторами.', `<button type="button" class="btn btn-primary" data-go-tab="admins">Открыть</button>`),
      makeHeroCard('Тарифы', 'Управление тарифами.', `<button type="button" class="btn btn-primary" data-go-tab="tariffs">Открыть</button>`),
      makeHeroCard('Настройки', 'Параметры текущего аккаунта.', `<button type="button" class="btn btn-primary" data-go-tab="settings">Открыть</button>`),
    ].join('');

    root.querySelectorAll('[data-go-tab]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const tab = String(btn.getAttribute('data-go-tab') || '').trim();
        const grade = Number(btn.getAttribute('data-grade') || 0);
        if (tab === 'theory' && grade) state.theoryGrade = grade;
        if (tab === 'tasks' && grade) state.taskGrade = grade;
        if (tab) await switchTab(tab);
      });
    });
  }

  async function switchTab(id){
    state.tab=id; renderMenu(); showView(id);
    if (id==='home') await loadHome();
    if (id==='theory') await loadTheory();
    if (id==='tasks') await loadTasks();
    if (id==='variants') await loadVariants();
    if (id==='students') await loadRole('student','studentsTable','studentsTitle',T.students);
    if (id==='teachers') await loadRole('teacher','teachersTable','teachersTitle',T.teachers);
    if (id==='admins') await loadRole('admin','adminsTable','adminsTitle',T.admins);
    if (id==='tariffs') await loadTariffs();
    if (id==='payments') await loadPayments();
    if (id==='withdrawals') await loadWithdrawals();
    if (id==='settings') await loadSettings();
  }

  async function initLogin(){
    const form = byId('adminLoginForm'); if(!form) return false;
    form.addEventListener('submit', async (e)=>{
      e.preventDefault();
      const fd = new FormData(form);
      try { await api('/auth/login',{method:'POST',body:JSON.stringify({login:fd.get('login'),password:fd.get('password')})}); window.location.href='/dashboard'; }
      catch(err){ byId('adminLoginMsg').textContent = err.message; }
    });
    return true;
  }

  async function initDashboard(){
    if (!byId('topMenu')) return;
    try { await api('/auth/me'); } catch(_) { window.location.href='/login'; return; }
    window.addEventListener('unhandledrejection',(event)=>{setMsg(event.reason?.message || 'Ошибка операции');});

    byId('logoutBtn').addEventListener('click', async ()=>{ await api('/auth/logout',{method:'POST'}); window.location.href='/login'; });

    byId('articleNew').textContent = `${T.new} ${T.theory.toLowerCase()}`;
    byId('articleSave').textContent = T.save;
    byId('articleDelete').textContent = T.del;
    byId('testNew').textContent = `${T.new} ${T.tasks.toLowerCase()}`;
    byId('testSave').textContent = T.save;
    byId('testDelete').textContent = T.del;
    byId('variantNew').textContent = `${T.new} ${T.variants.slice(0,-1).toLowerCase()}`;
    byId('variantSave').textContent = T.save;
    byId('variantDelete').textContent = T.del;

    const articleForm = byId('articleForm');
    byId('articleList').addEventListener('click',(e)=>{const id=Number(e.target?.dataset?.id||0);const item=state.articles.find(x=>x.id===id);if(item) fillForm(articleForm,item);});
    byId('articleNew').addEventListener('click',()=>fillForm(articleForm,{grade:state.theoryGrade,subject:state.theorySubject}));
    articleForm.addEventListener('submit', async (e)=>{e.preventDefault();const o=toObj(articleForm);const id=Number(o.id||0);delete o.id;await api(id?`/articles/${id}`:'/articles',{method:id?'PUT':'POST',body:JSON.stringify(o)});await loadTheory();setMsg('Статья сохранена');});
    byId('articleDelete').addEventListener('click', async ()=>{const id=Number(articleForm.id.value||0);if(!id)return;await api(`/articles/${id}`,{method:'DELETE'});fillForm(articleForm,{});await loadTheory();setMsg('Статья удалена');});

    const testForm = byId('testForm');
    byId('testList').addEventListener('click',(e)=>{const id=Number(e.target?.dataset?.id||0);const item=state.tests.find(x=>x.id===id);if(item) fillForm(testForm,item);});
    byId('testNew').addEventListener('click',()=>fillForm(testForm,{subject:state.taskSubject}));
    testForm.addEventListener('submit', async (e)=>{e.preventDefault();const o=toObj(testForm);const id=Number(o.id||0);delete o.id;await api(id?`/tests/${id}`:'/tests',{method:id?'PUT':'POST',body:JSON.stringify(o)});await loadTasks();setMsg('Задание сохранено');});
    byId('testDelete').addEventListener('click', async ()=>{const id=Number(testForm.id.value||0);if(!id)return;await api(`/tests/${id}`,{method:'DELETE'});fillForm(testForm,{});await loadTasks();setMsg('Задание удалено');});

    const variantForm = byId('variantForm');
    byId('variantList').addEventListener('click',(e)=>{const id=Number(e.target?.dataset?.id||0);const item=state.variants.find(x=>x.id===id);if(item) fillForm(variantForm,item);});
    byId('variantNew').addEventListener('click',()=>fillForm(variantForm,{subject:state.variantSubject}));
    variantForm.addEventListener('submit', async (e)=>{
      e.preventDefault();
      const o=toObj(variantForm); const id=Number(o.id||0); const taskIds=o.task_ids || [];
      delete o.id; delete o.task_ids;
      const saved=await api(id?`/variants/${id}`:'/variants',{method:id?'PUT':'POST',body:JSON.stringify(o)});
      const variantId=id || Number(saved.id);
      await api(`/variants/${variantId}/tasks`,{method:'PUT',body:JSON.stringify({task_ids:taskIds})});
      await loadVariants(); setMsg('Вариант и состав заданий сохранены');
    });
    byId('variantDelete').addEventListener('click', async ()=>{const id=Number(variantForm.id.value||0);if(!id)return;await api(`/variants/${id}`,{method:'DELETE'});fillForm(variantForm,{});await loadVariants();setMsg('Вариант удалён');});

    document.addEventListener('click', () => {
      document.querySelectorAll('#topMenu .has-dropdown.open').forEach((node) => node.classList.remove('open'));
    });

    renderMenu();
    await switchTab('home');
  }

  (async ()=>{ if(!(await initLogin())) await initDashboard(); })();
})();
