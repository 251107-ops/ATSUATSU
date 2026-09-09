/* ==========================================
   グローバル関数（HTMLのonchange属性などから呼び出し）
   ========================================== */

/**
 * URLクエリパラメーターを更新してページをリロードする関数
 */
function updateFilter(key, value) {
    const urlParams = new URLSearchParams(window.location.search);
    if (value) {
        urlParams.set(key, value);
    } else {
        urlParams.delete(key);
    }
    window.location.search = urlParams.toString();
}

/**
 * 添付画像拡大モーダルを開く関数（必要に応じて単体画像用に使用）
 */
function openImageModal(imgSrc) {
    const imageModal = document.getElementById('imageModal');
    const modalImg = document.getElementById('imgModalTarget');
    if (imageModal && modalImg) {
        modalImg.src = imgSrc;
        imageModal.style.display = 'flex';
    }
}

/**
 * 添付画像拡大モーダルを閉じる関数
 */
function closeImageModal() {
    const imageModal = document.getElementById('imageModal');
    if (imageModal) {
        imageModal.style.display = 'none';
    }
}


/* ==========================================
   DOM構築後のイベント設定
   ========================================== */
document.addEventListener('DOMContentLoaded', () => {

    /* ==========================================
       1. ヒーロータイトルの文字アニメーション
       ========================================== */
    const heroTitle = document.getElementById('heroTitle');
    if (heroTitle) {
        const text = heroTitle.textContent;
        heroTitle.textContent = '';

        [...text].forEach((char, i) => {
            const span = document.createElement('span');
            span.className = 'char';
            span.textContent = char === ' ' ? '\u00A0' : char; // 半角スペース対応
            span.style.animationDelay = `${i * 0.05}s`;
            heroTitle.appendChild(span);
        });
    }

    /* ==========================================
       2. いいね機能（非同期通信）
       ========================================== */
    document.querySelectorAll('.like-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            // カード本体へのクリックイベント伝播を防止（モーダルが開くのを防ぐ）
            e.stopPropagation();

            const postId = btn.dataset.postId;
            try {
                const response = await fetch('/posts/likes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: `post_id=${postId}`
                });

                if (response.ok) {
                    const result = await response.json();
                    const countSpan = btn.querySelector('.like-count');
                    let count = parseInt(countSpan.textContent, 10);

                    if (result.liked) {
                        count += 1;
                        btn.dataset.liked = 'true';
                    } else {
                        count -= 1;
                        btn.dataset.liked = 'false';
                    }
                    countSpan.textContent = count;
                }
            } catch (error) {
                console.error('いいね処理エラー:', error);
            }
        });
    });

    /* ==========================================
       3. スキルカード拡大表示（モーダル） & リクエスト
       ========================================== */
       const modal = document.getElementById('cardModal');
       const modalClose = document.getElementById('modalClose');
       const requestForm = document.getElementById('requestForm');
   
       // ★追加: バナー表示用の要素と関数
       const topBanner = document.getElementById('topBanner');
       let bannerTimer = null;
   
       function showBanner(message, type = 'success') {
           if (!topBanner) return;
           topBanner.textContent = message;
           topBanner.className = `top-banner show ${type}`;
   
           window.scrollTo({ top: 0, behavior: 'smooth' });
   
           clearTimeout(bannerTimer);
           bannerTimer = setTimeout(() => {
               topBanner.className = 'top-banner';
           }, 3500);
       }
   
    if (modal) {
        // カードクリック時のモーダル表示処理
        document.querySelectorAll('.card').forEach(card => {
            card.addEventListener('click', () => {
                const data = card.dataset;
                const currentUserIdInput = document.getElementById('currentUserId');
                const currentUserId = currentUserIdInput ? currentUserIdInput.value : '';
                const requestBtn = document.getElementById('requestBtn');
        
                if (data.cardType === 'project') {
                    requestForm.action = '/project/apply';
                    document.getElementById('modalPostId').value = '';
                    document.getElementById('modalReceiverId').value = '';
                    document.getElementById('modalProjectId').value = data.projectId || '';
        
                    document.getElementById('modalIcon').src = data.icon || '';
                    document.getElementById('modalName').textContent = data.projectName || '';
                    document.getElementById('modalMeta').textContent = data.name + 'さん募集中';
                    document.getElementById('modalCategory').textContent = data.category || '';
                    document.getElementById('modalSkill').textContent = data.skill || '';
                    document.getElementById('modalBody').textContent = data.body || '';
                    document.getElementById('modalLikes').textContent = '';
        
                    const modalType = document.getElementById('modalType');
                    modalType.textContent = `${data.currentMembers}/${data.recruitCount}人`;
                    modalType.className = 'badge';
        
                    const modalUserLink = document.getElementById('modalUserLink');
                    if (modalUserLink) modalUserLink.href = '/users/' + data.userId;
        
                    requestBtn.disabled = false;
                    requestBtn.style.opacity = '1';
                    requestBtn.style.cursor = 'pointer';
        
                    if (data.alreadyMember === 'true') {
                        requestBtn.disabled = true;
                        requestBtn.textContent = 'すでに参加しています';
                        requestBtn.style.opacity = '0.5';
                        requestBtn.style.cursor = 'not-allowed';
                    } else if (data.isOwner === 'true') {
                        requestBtn.disabled = true;
                        requestBtn.textContent = '自分のプロジェクトです';
                        requestBtn.style.opacity = '0.5';
                        requestBtn.style.cursor = 'not-allowed';
                    } else if (data.alreadyApplied === 'true') {
                        requestBtn.disabled = true;
                        requestBtn.textContent = '申請済みです';
                        requestBtn.style.opacity = '0.5';
                        requestBtn.style.cursor = 'not-allowed';
                    } else {
                        requestBtn.textContent = 'プロジェクト参加申請';
                    }
        
                    const attachmentArea = document.getElementById('modalAttachmentArea');
                    if (attachmentArea) attachmentArea.style.display = 'none';
        
                    modal.classList.add('active');
                    return;
                }
        
                // 既存のスキルカード処理
                requestForm.action = '/requests';
                document.getElementById('modalProjectId').value = '';
                document.getElementById('modalPostId').value = data.postId || '';
                document.getElementById('modalReceiverId').value = data.userId || '';
                document.getElementById('modalIcon').src = data.icon || '';
                document.getElementById('modalName').textContent = data.name || '';
                document.getElementById('modalMeta').textContent = data.meta || '';
                document.getElementById('modalCategory').textContent = data.category || '';
                document.getElementById('modalSkill').textContent = data.skill || '';
                document.getElementById('modalBody').textContent = data.body || '';
                document.getElementById('modalLikes').textContent = data.likes || '0';
        
                const modalUserLink = document.getElementById('modalUserLink');
                if (modalUserLink) modalUserLink.href = '/users/' + data.userId;
        
                const modalType = document.getElementById('modalType');
                modalType.textContent = data.type || '';
                modalType.className = `badge ${data.type === '教えたい' ? 'teach' : 'learn'}`;
        
                const attachmentArea = document.getElementById('modalAttachmentArea');
                const previewImg = document.getElementById('modalPreviewImg');
                const previewPdf = document.getElementById('modalPreviewPdf');
        
                if (attachmentArea) {
                    const filePath = data.image ? data.image.trim() : '';
                    if (filePath !== '') {
                        attachmentArea.style.display = 'block';
                        if (filePath.toLowerCase().endsWith('.pdf')) {
                            if (previewImg) previewImg.style.display = 'none';
                            if (previewPdf) { previewPdf.href = filePath; previewPdf.style.display = 'block'; }
                        } else {
                            if (previewPdf) previewPdf.style.display = 'none';
                            if (previewImg) { previewImg.src = filePath; previewImg.style.display = 'block'; }
                        }
                    } else {
                        attachmentArea.style.display = 'none';
                        if (previewImg) { previewImg.src = ''; previewImg.style.display = 'none'; }
                        if (previewPdf) { previewPdf.href = '#'; previewPdf.style.display = 'none'; }
                    }
                }
        
                requestBtn.disabled = false;
                requestBtn.style.opacity = '1';
                requestBtn.style.cursor = 'pointer';
        
                if (currentUserId && String(currentUserId) === String(data.userId)) {
                    requestBtn.disabled = true;
                    requestBtn.textContent = '自分の投稿です';
                    requestBtn.style.opacity = '0.5';
                    requestBtn.style.cursor = 'not-allowed';
                } else {
                    requestBtn.textContent = data.type === '教えたい' ? '教わりたい（リクエストを送る）' : '教えたい（オファーを送る）';
                }
        
                modal.classList.add('active');
            });
        });

        // ★修正点2: フォーム送信時に連打を防止（二重送信防止ガード）
        // if (requestForm) {
        //     requestForm.addEventListener('submit', function() {
        //         const requestBtn = document.getElementById('requestBtn');
        //         if (requestBtn) {
        //             requestBtn.disabled = true;
        //             requestBtn.textContent = '送信中...';
        //             requestBtn.style.opacity = '0.6';
        //         }
        //     });
        // }

        // ★修正点2: フォーム送信をfetch化（ページ遷移なしでリクエスト送信）
        if (requestForm) {
            requestForm.addEventListener('submit', async function(e) {
                e.preventDefault(); // ← これが最重要。ブラウザ標準のページ遷移を止める

                const requestBtn = document.getElementById('requestBtn');
                if (requestBtn) {
                    requestBtn.disabled = true;
                    requestBtn.textContent = '送信中...';
                    requestBtn.style.opacity = '0.6';
                }

                const formData = new FormData(requestForm); // post_id, receiver_id を自動収集

                try {
                    const response = await fetch(requestForm.action, {
                        method: 'POST',
                        headers: { 'X-Requested-With': 'XMLHttpRequest' }, // ← これでバックエンドのis_asyncがTrueになる
                        body: formData
                    });
                    const result = await response.json();

                    if (response.ok && result.success) {
                        showBanner(result.message || 'リクエストを送信しました！', 'success');
                        if (modal) modal.classList.remove('active');
                        requestForm.reset();
                    } else {
                        showBanner(result.message || '送信に失敗しました。', 'error');
                    
                        // ★「自分の投稿」「重複送信」の場合は、押しても解決しないのでモーダルごと閉じる
                        const shouldCloseAnyway = ['own_post', 'duplicate', 'own_project', 'already_member'].includes(result.reason);
                    
                        if (shouldCloseAnyway) {
                            if (modal) modal.classList.remove('active');
                            requestForm.reset();
                        } else if (requestBtn) {
                            // それ以外(通信エラーなど)は再送信できるようにボタンを戻す
                            requestBtn.disabled = false;
                            requestBtn.style.opacity = '1';
                            requestBtn.style.cursor = 'pointer';
                            requestBtn.textContent = '再送信する';
                        }
                    }
                } catch (err) {
                    console.error('リクエスト送信エラー:', err);
                    showBanner('通信エラーが発生しました。', 'error');
                    if (requestBtn) {
                        requestBtn.disabled = false;
                        requestBtn.style.opacity = '1';
                        requestBtn.style.cursor = 'pointer';
                        requestBtn.textContent = '再送信する';
                    }
                }
            });
        }

        // モーダルを閉じる処理（閉じるボタン）
        if (modalClose) {
            modalClose.addEventListener('click', () => {
                modal.classList.remove('active');
            });
        }

        // モーダル外側（背景）クリック時のみ閉じる
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    }

    /* ==========================================
       4. 添付画像プレビューモーダルのイベント設定
       ========================================== */
    const imageModal = document.getElementById('imageModal');
    if (imageModal) {
        // 画像モーダルの背景クリックで閉じる
        imageModal.addEventListener('click', (e) => {
            if (e.target === imageModal || e.target.classList.contains('close-modal')) {
                closeImageModal();
            }
        });
    }
});