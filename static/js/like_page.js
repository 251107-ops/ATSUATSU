document.addEventListener('DOMContentLoaded', () => {
    const cardsContainer = document.getElementById('cardsContainer');
    if (!cardsContainer) return;

    cardsContainer.querySelectorAll('.like-btn').forEach(button => {
        button.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation(); // カードのonclick(モーダル起動)に伝播させない

            if (button.disabled) return;
            button.disabled = true;

            const postId = button.dataset.postId;
            if (!postId) { button.disabled = false; return; }

            try {
                const response = await fetch('/posts/likes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ post_id: postId })
                });

                if (response.ok) {
                    const data = await response.json();
                    if (!data.is_liked) {
                        const targetCard = document.getElementById(`card-${postId}`) || button.closest('.card');
                        if (targetCard) targetCard.remove();
                        updateFavPageUI();
                    } else {
                        button.disabled = false;
                    }
                } else {
                    console.error('サーバーエラーが発生しました');
                    button.disabled = false;
                }
            } catch (error) {
                console.error('通信エラーが発生しました:', error);
                button.disabled = false;
            }
        });
    });

    function updateFavPageUI() {
        const remainingCards = document.querySelectorAll('#cardsContainer .card');
        const countSpan = document.getElementById('favCount');
        if (countSpan) countSpan.textContent = `(${remainingCards.length}件)`;
        if (remainingCards.length === 0) {
            cardsContainer.innerHTML = `
                <div class="no-posts">
                    <p>お気に入り登録した投稿はまだありません。</p>
                </div>
            `;
        }
    }

    window.updateFavPageUI = updateFavPageUI; // モーダル側から使うため公開
});