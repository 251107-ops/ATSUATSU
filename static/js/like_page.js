document.addEventListener('DOMContentLoaded', () => {
    // イベント委譲（親要素でクリックを監視）を使って確実にキャッチ
    const cardsContainer = document.getElementById('cardsContainer');

    if (!cardsContainer) return;

    cardsContainer.addEventListener('click', async (e) => {
        // クリックされた要素が .like-btn またはその子要素か判定
        const button = e.target.closest('.like-btn');
        if (!button) return;

        e.preventDefault();
        e.stopPropagation();

        const postId = button.dataset.postId;
        if (!postId) return;

        try {
            const response = await fetch('/posts/likes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ post_id: postId })
            });

            if (response.ok) {
                const data = await response.json();

                // いいね解除された場合（liked: false）
                if (!data.liked) {
                    // ID検索、またはボタンの親要素(.card)から対象カードを取得して削除
                    const targetCard = document.getElementById(`card-${postId}`) || button.closest('.card');
                    if (targetCard) {
                        targetCard.remove();
                    }
                    updateFavPageUI();
                }
            } else {
                console.error('サーバーエラーが発生しました');
            }
        } catch (error) {
            console.error('通信エラーが発生しました:', error);
        }
    });

    // 件数と「0件表示」の更新処理
    function updateFavPageUI() {
        const remainingCards = document.querySelectorAll('#cardsContainer .card');
        const countSpan = document.getElementById('favCount');

        if (countSpan) {
            countSpan.textContent = `(${remainingCards.length}件)`;
        }

        if (remainingCards.length === 0) {
            cardsContainer.innerHTML = `
                <div class="no-posts">
                    <p>お気に入り登録した投稿はまだありません。</p>
                </div>
            `;
        }
    }
});