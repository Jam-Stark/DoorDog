(() => {
  const setText = (el, text) => { if (el) el.textContent = text; };
  document.querySelectorAll('[data-stepper]').forEach((root) => {
    const buttons = [...root.querySelectorAll('[data-step]')]; const detail = root.querySelector('[data-step-detail]'); const live = root.querySelector('[data-step-live]'); const steps = JSON.parse(root.dataset.steps);
    const render = (index) => { const item = steps[index]; buttons.forEach((button, i) => { const active = i === index; button.dataset.active = String(active); button.setAttribute('aria-pressed', String(active)); }); detail.innerHTML = `<h3>${item.title}</h3><p>${item.body}</p><div class="formula">${item.formula}</div><p><strong>追问：</strong>${item.follow}</p>`; setText(live, `已选择：${item.title}`); };
    buttons.forEach((button, i) => button.addEventListener('click', () => render(i))); render(0);
  });
  document.querySelectorAll('[data-timeline]').forEach((root) => {
    const steps = [...root.querySelectorAll('.time-step')]; const next = root.querySelector('[data-next]'); const prev = root.querySelector('[data-prev]'); const live = root.querySelector('[data-timeline-live]'); let current = 0;
    const render = () => { steps.forEach((step, index) => step.dataset.active = String(index === current)); setText(live, `生命周期第 ${current + 1} 步：${steps[current].querySelector('strong').textContent}`); };
    next?.addEventListener('click', () => { current = (current + 1) % steps.length; render(); }); prev?.addEventListener('click', () => { current = (current - 1 + steps.length) % steps.length; render(); }); render();
  });
  document.querySelectorAll('[data-stageboard]').forEach((root) => {
    const buttons = [...root.querySelectorAll('[data-stage]')]; const detail = root.querySelector('[data-stage-detail]'); const live = root.querySelector('[data-stage-live]'); const info = JSON.parse(root.dataset.stages);
    const choose = (index) => { const item = info[index]; buttons.forEach((button, i) => { button.closest('.stage').dataset.active = String(i === index); button.setAttribute('aria-pressed', String(i === index)); }); detail.innerHTML = `<strong>${item.title}</strong><br>${item.body}`; setText(live, `已选择 ${item.title}`); };
    buttons.forEach((button, i) => button.addEventListener('click', () => choose(i))); choose(0);
  });
  document.querySelectorAll('[data-teacher-ratio]').forEach((root) => {
    const input = root.querySelector('input[type="range"]'); const label = root.querySelector('[data-ratio-label]'); const grid = root.querySelector('[data-mask-grid]'); const total = Number(root.dataset.batch || 16);
    const render = () => { const ratio = Number(input.value) / 100; const count = Math.round(total * ratio); setText(label, `Teacher ${count} / ${total}，Student ${total - count} / ${total}`); grid.innerHTML = Array.from({ length: total }, (_, i) => `<span class="tag ${i < count ? '' : 'inspected'}">${i < count ? 'T' : 'S'}${i + 1}</span>`).join(''); };
    input.addEventListener('input', render); render();
  });
  document.querySelectorAll('[data-flashcards]').forEach((root) => {
    const cards = JSON.parse(root.dataset.cards); const question = root.querySelector('[data-question]'); const answer = root.querySelector('[data-answer]'); const indexText = root.querySelector('[data-card-index]'); const live = root.querySelector('[data-flash-live]'); const flip = root.querySelector('[data-flip]'); let index = 0; let front = true;
    const render = () => { const card = cards[index]; question.innerHTML = `<p class="flash-index">${card.group} · ${index + 1}/${cards.length}</p><h2>${card.q}</h2><p>先自己组织 30–60 秒回答，再按 <span class="kbd">Space</span> 或按钮翻面。</p>`; answer.innerHTML = `<p class="flash-index">参考回答</p><h2>${card.q}</h2><p>${card.a}</p><div class="formula">${card.formula}</div><p><strong>追问：</strong>${card.follow}</p><p><code>${card.source}</code></p>`; question.dataset.active = String(front); answer.dataset.active = String(!front); setText(indexText, `第 ${index + 1} 张，共 ${cards.length} 张`); setText(live, `已切换至第 ${index + 1} 张卡片${front ? '问题面' : '答案面'}`); };
    const toggle = () => { front = !front; render(); }; flip.addEventListener('click', toggle); root.querySelector('[data-prev-card]').addEventListener('click', () => { index = (index - 1 + cards.length) % cards.length; front = true; render(); }); root.querySelector('[data-next-card]').addEventListener('click', () => { index = (index + 1) % cards.length; front = true; render(); }); document.addEventListener('keydown', (event) => { const target = event.target; const usesSpace = target instanceof HTMLButtonElement || target instanceof HTMLInputElement || target instanceof HTMLAnchorElement; if (event.code === 'Space' && !usesSpace) { event.preventDefault(); toggle(); } }); render();
  });
})();
