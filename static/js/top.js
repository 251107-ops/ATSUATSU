// 見出しの文字を1文字ずつspanで包んで、順番にフェードインさせる
document.addEventListener('DOMContentLoaded', () => {
    const heroTitle = document.getElementById('heroTitle');
    if (!heroTitle) return;

    const text = heroTitle.textContent;
    heroTitle.textContent = '';

    [...text].forEach((char, i) => {
        const span = document.createElement('span');
        span.className = 'char';
        span.textContent = char === ' ' ? '\u00A0' : char; // 半角スペース対応
        span.style.animationDelay = `${i * 0.05}s`;
        heroTitle.appendChild(span);
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const heroTitle = document.getElementById('heroTitle');
    if (!heroTitle) return;

    const text = heroTitle.textContent;
    heroTitle.textContent = '';

    [...text].forEach((char, i) => {
        const span = document.createElement('span');
        span.className = 'char';
        span.textContent = char === ' ' ? '\u00A0' : char;
        span.style.animationDelay = `${i * 0.05}s`;
        heroTitle.appendChild(span);
    });
});

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.like-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const postId = btn.dataset.postId;
            const response = await fetch('/posts/likes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `post_id=${postId}`
            });
            if (response.ok) {
                const result = await response.json();
                const countSpan = btn.querySelector('.like-count');
                let count = parseInt(countSpan.textContent);

                if (result.liked) {
                    count += 1;
                    btn.dataset.liked = 'true';
                } else {
                    count -= 1;
                    btn.dataset.liked = 'false';
                }
                countSpan.textContent = count;
            }
        });
    });
});