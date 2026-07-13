document.addEventListener('DOMContentLoaded', () => {

  const MAX_AVATAR_BYTES = 3 * 1024 * 1024; // 3MB
  const ALLOWED_MIME_TYPES = ['image/png', 'image/jpeg', 'image/gif'];
  const MAX_SKILL_LEN = 30;
  const MAX_SKILLS_PER_TYPE = 20;
  const MAX_BIO_LEN = 500;

  /* ---------------------------------------
     1. アバター画像のアップロード＆プレビュー
  --------------------------------------- */
  const avatarInput = document.getElementById('avatarInput');
  const avatarImg = document.getElementById('avatarImg');
  const avatarPlaceholder = document.getElementById('avatarPlaceholder');
  const avatarCamBtn = document.getElementById('avatarCamBtn');
  const avatarChangeBtn = document.getElementById('avatarChangeBtn');

  const headerAvatarImg = document.getElementById('headerAvatarImg');
  const headerAvatarInitial = document.getElementById('headerAvatarInitial');

  function openFilePicker() {
    avatarInput.click();
  }

  if (avatarCamBtn) avatarCamBtn.addEventListener('click', openFilePicker);
  if (avatarChangeBtn) avatarChangeBtn.addEventListener('click', openFilePicker);

  if (avatarInput) {
    avatarInput.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      // 種類チェック
      if (!ALLOWED_MIME_TYPES.includes(file.type)) {
        showToast('対応していない画像形式です（PNG / JPEG / GIF）');
        avatarInput.value = '';
        return;
      }

      // サイズチェック
      if (file.size > MAX_AVATAR_BYTES) {
        showToast('画像サイズが大きすぎます（3MBまで）');
        avatarInput.value = '';
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        const dataUrl = event.target.result;

        avatarImg.src = dataUrl;
        avatarImg.classList.remove('is-hidden');
        if (avatarPlaceholder) avatarPlaceholder.classList.add('is-hidden');

        if (headerAvatarImg) {
          headerAvatarImg.src = dataUrl;
          headerAvatarImg.classList.remove('is-hidden');
        }
        if (headerAvatarInitial) headerAvatarInitial.classList.add('is-hidden');
      };
      reader.readAsDataURL(file);
    });
  }

  /* ---------------------------------------
     2. スキルタグの追加・削除
  --------------------------------------- */
  function getTagNames(listEl) {
    return Array.from(listEl.querySelectorAll('.tag'))
      .map((t) => t.childNodes[0].textContent.trim().toLowerCase());
  }

  // タグを削除する処理
  function attachRemoveHandler(removeBtn) {
    removeBtn.onclick = function () {
      const tag = this.closest('.tag');
      if (tag) tag.remove();
    };
  }

  // 最初から画面にある削除ボタンにイベントをつける
  document.querySelectorAll('.tag__remove').forEach(attachRemoveHandler);

  // 「＋ 追加」ボタンを押したときの処理
  document.querySelectorAll('.tag-add').forEach((addBtn) => {
    addBtn.onclick = function () {
      const listId = this.dataset.target;
      const variant = this.dataset.variant; // 'teach' または 'learn'
      const list = document.getElementById(listId);

      const currentCount = list.querySelectorAll('.tag').length;
      if (currentCount >= MAX_SKILLS_PER_TYPE) {
        showToast(`スキルは${MAX_SKILLS_PER_TYPE}件までです`);
        return;
      }

      // 入力ポップアップを表示
      const skillName = window.prompt(
        variant === 'teach'
          ? '追加したい「教えたいスキル」を入力してください'
          : '追加したい「学びたいスキル」を入力してください'
      );

      let trimmed = skillName && skillName.trim();
      if (!trimmed) return; // 空文字なら何もしない

      if (trimmed.length > MAX_SKILL_LEN) {
        trimmed = trimmed.slice(0, MAX_SKILL_LEN);
      }

      // 重複チェック（大文字小文字を無視）
      if (getTagNames(list).includes(trimmed.toLowerCase())) {
        showToast('そのスキルはすでに追加されています');
        return;
      }

      // 新しいタグ要素（span）を作成
      const tag = document.createElement('span');
      tag.className = `tag tag--${variant}`;
      tag.textContent = trimmed; // スキル名をセット（textContentなのでXSSの心配なし）

      // 削除ボタン（×）を作成してタグの中に追加
      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'tag__remove';
      removeBtn.setAttribute('aria-label', `${trimmed}を削除`);
      removeBtn.textContent = '×';
      attachRemoveHandler(removeBtn); // 削除機能をつける

      tag.appendChild(removeBtn);

      // 「+ 追加」ボタンの直前に新しいタグを挿入
      list.insertBefore(tag, this);
    };
  });

  /* ---------------------------------------
     3. サイドバーのメニュー切り替え
  --------------------------------------- */
  const sideLinks = document.querySelectorAll('.side-link');
  sideLinks.forEach((link) => {
    link.addEventListener('click', () => {
      sideLinks.forEach((l) => l.classList.remove('side-link--active'));
      link.classList.add('side-link--active');
    });
  });

  /* ---------------------------------------
     4. 自己紹介の文字数カウンター
  --------------------------------------- */
  const bioInput = document.getElementById('bio');
  const bioCounter = document.getElementById('bioCounter');

  function updateBioCounter() {
    if (!bioInput || !bioCounter) return;
    bioCounter.textContent = `${bioInput.value.length} / ${MAX_BIO_LEN}`;
  }

  if (bioInput) {
    updateBioCounter();
    bioInput.addEventListener('input', updateBioCounter);
  }

  /* ---------------------------------------
     5. 保存・キャンセル（バックエンド通信）
  --------------------------------------- */
  const profileForm = document.getElementById('profileForm');
  const cancelBtn = document.getElementById('cancelBtn');
  const submitBtn = document.getElementById('submitBtn');
  const toast = document.getElementById('toast');

  let toastTimer = null;
  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.remove('is-hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.add('is-hidden');
    }, 2400);
  }

  if (profileForm) {
    profileForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      const nameInput = document.getElementById('name');
      if (!nameInput.value.trim()) {
        showToast('名前を入力してください');
        nameInput.focus();
        return;
      }

      // 安全に×ボタン以外のテキストだけを取得する
      const teachSkills = getTagNames(document.getElementById('teachSkillList'))
        .map((s) => s); // 既に trim/lowercase 済み表示用ではないので下で元の大小文字を取り直す

      const teachSkillsDisplay = Array.from(document.querySelectorAll('#teachSkillList .tag'))
        .map((t) => t.childNodes[0].textContent.trim());
      const learnSkillsDisplay = Array.from(document.querySelectorAll('#learnSkillList .tag'))
        .map((t) => t.childNodes[0].textContent.trim());

      const formData = new FormData();
      formData.append('csrf_token', document.querySelector('input[name="csrf_token"]').value);
      formData.append('name', nameInput.value.trim());
      formData.append('grade', document.getElementById('grade').value);
      formData.append('department', document.getElementById('department').value);
      formData.append('bio', bioInput ? bioInput.value : '');

      formData.append('teachSkills', JSON.stringify(teachSkillsDisplay));
      formData.append('learnSkills', JSON.stringify(learnSkillsDisplay));

      if (avatarInput && avatarInput.files[0]) {
        formData.append('avatar', avatarInput.files[0]);
      }

      // 連打による二重送信防止
      submitBtn.disabled = true;
      submitBtn.textContent = '保存中...';

      try {
        const response = await fetch('/profile', {
          method: 'POST',
          body: formData
        });

        const result = await response.json();

        if (response.ok) {
          showToast(result.message || 'プロフィールを保存しました');
          setTimeout(() => { location.reload(); }, 1000);
        } else {
          showToast(result.message || '保存に失敗しました');
          submitBtn.disabled = false;
          submitBtn.textContent = '保存する';
        }
      } catch (error) {
        console.error('エラー:', error);
        showToast('通信エラーが発生しました');
        submitBtn.disabled = false;
        submitBtn.textContent = '保存する';
      }
    });
  }

  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
      if (!window.confirm('変更を破棄してもよろしいですか？')) return;
      profileForm.reset();
      showToast('変更をキャンセルしました');
      setTimeout(() => { location.reload(); }, 800);
    });
  }

});