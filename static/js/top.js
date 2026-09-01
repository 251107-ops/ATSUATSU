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

    if (modal) {
        // カードクリック時のモーダル表示処理
        document.querySelectorAll('.card').forEach(card => {
            card.addEventListener('click', () => {
                const data = card.dataset;

                // ログイン中のユーザーIDを取得（top.htmlのhidden inputより）
                const currentUserIdInput = document.getElementById('currentUserId');
                const currentUserId = currentUserIdInput ? currentUserIdInput.value : '';

                // 各要素への値のセット
                document.getElementById('modalPostId').value = data.postId || '';
                document.getElementById('modalReceiverId').value = data.userId || '';
                document.getElementById('modalIcon').src = data.icon || '';
                document.getElementById('modalName').textContent = data.name || '';
                document.getElementById('modalMeta').textContent = data.meta || '';
                document.getElementById('modalCategory').textContent = data.category || '';
                document.getElementById('modalSkill').textContent = data.skill || '';
                document.getElementById('modalBody').textContent = data.body || '';
                document.getElementById('modalLikes').textContent = data.likes || '0';

                //ユーザーアイコン・名前のリンク先を動的にセット
                const userProfileUrl = '/profile/${data.userId}';
                const modalUserLink = document.getElementById('modalUserLink');
                if (modalUserLink) {
                    modalUserLink.href = '/profile/' + data.userId;
                }

                // バッジ状態の反映
                const modalType = document.getElementById('modalType');
                modalType.textContent = data.type || '';
                modalType.className = `badge ${data.type === '教えたい' ? 'teach' : 'learn'}`;

                // 💡 【修正点】カードを開いた時にそのまま画像も表示する処理
                const attachmentArea = document.getElementById('modalAttachmentArea');
                const previewImg = document.getElementById('modalPreviewImg');

                if (attachmentArea) {
                    if (data.image) {
                        // 画像要素（#modalPreviewImg）が存在する場合はsrcを設定
                        if (previewImg) {
                            previewImg.src = data.image;
                            previewImg.style.display = 'block';
                        }
                        attachmentArea.style.display = 'block';
                    } else {
                        if (previewImg) {
                            previewImg.src = '';
                            previewImg.style.display = 'none';
                        }
                        attachmentArea.style.display = 'none';
                    }
                }

                // ボタン要素を取得
                const requestBtn = document.getElementById('requestBtn');

                // 毎回ボタンの連打・無効化状態をリセット
                requestBtn.disabled = false;
                requestBtn.style.opacity = '1';
                requestBtn.style.cursor = 'pointer';

                // 自分の投稿かどうか判定
                if (currentUserId && String(currentUserId) === String(data.userId)) {
                    // 自分の投稿の場合はボタンを無効化
                    requestBtn.disabled = true;
                    requestBtn.textContent = '自分の投稿です';
                    requestBtn.style.opacity = '0.5';
                    requestBtn.style.cursor = 'not-allowed';
                } else {
                    // 他人の投稿の場合はテキスト切り替え
                    if (data.type === '教えたい') {
                        requestBtn.textContent = '教わりたい（リクエストを送る）';
                    } else {
                        requestBtn.textContent = '教えたい（オファーを送る）';
                    }
                }

                // モーダルを開く
                modal.classList.add('active');
            });
        });

        // フォーム送信時に連打を防止（二重送信防止ガード）
        if (requestForm) {
            requestForm.addEventListener('submit', function() {
                const requestBtn = document.getElementById('requestBtn');
                if (requestBtn) {
                    requestBtn.disabled = true;
                    requestBtn.textContent = '送信中...';
                    requestBtn.style.opacity = '0.6';
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