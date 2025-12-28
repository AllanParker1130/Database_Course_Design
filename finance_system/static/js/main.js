document.addEventListener('DOMContentLoaded', function() {
    // 自动关闭提示
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 4000);
    });

    // 设置当前时间
    const nowInput = document.querySelector('input[type="datetime-local"]');
    if (nowInput) {
        const now = new Date().toISOString().slice(0, 16);
        nowInput.value = now;
    }

    // 设置当前日期
    const todayInputs = document.querySelectorAll('input[type="date"]');
    const today = new Date().toISOString().slice(0, 10);
    todayInputs.forEach(input => {
        if (!input.value) {
            input.value = today;
        }
    });

    // 导航激活状态
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });

    // 移动端表格标签
    if (window.innerWidth <= 768) {
        const tables = document.querySelectorAll('.table');
        tables.forEach(table => {
            const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent);
            const rows = table.querySelectorAll('tbody tr');
            rows.forEach(row => {
                const cells = row.querySelectorAll('td');
                cells.forEach((cell, index) => {
                    if (headers[index]) {
                        cell.setAttribute('data-label', headers[index]);
                    }
                });
            });
        });
    }
});
