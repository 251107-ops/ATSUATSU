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