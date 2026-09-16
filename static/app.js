document.querySelectorAll('[data-confirm]').forEach((element) => { element.addEventListener('click', (event) => { if (!window.confirm(element.dataset.confirm)) event.preventDefault(); }); });

const themeToggle = document.querySelector('#theme-toggle');
const themeIcon = document.querySelector('#theme-icon');
const themeLabel = document.querySelector('#theme-label');

const applyTheme = (theme) => {
	document.body.dataset.theme = theme;
	const darkMode = theme === 'dark';
	document.documentElement.classList.toggle('theme-dark', darkMode);
	if (themeToggle) {
		themeToggle.setAttribute('aria-pressed', String(darkMode));
		themeToggle.setAttribute('aria-label', darkMode ? 'Switch to light mode' : 'Switch to dark mode');
		themeToggle.setAttribute('title', darkMode ? 'Switch to light mode' : 'Switch to dark mode');
	}
	if (themeIcon) themeIcon.textContent = darkMode ? '☀' : '☾';
	if (themeLabel) themeLabel.textContent = darkMode ? 'Light mode' : 'Dark mode';
};

applyTheme(localStorage.getItem('av-room-theme') === 'dark' ? 'dark' : 'light');

themeToggle?.addEventListener('click', () => {
	const nextTheme = document.body.dataset.theme === 'dark' ? 'light' : 'dark';
	localStorage.setItem('av-room-theme', nextTheme);
	applyTheme(nextTheme);
});

document.querySelectorAll('a[href]').forEach((link) => {
	link.addEventListener('click', (event) => {
		const target = link.getAttribute('target');
		const href = link.getAttribute('href');
		if (event.defaultPrevented || target === '_blank' || !href || href.startsWith('#') || href.startsWith('http')) return;
		document.body.classList.add('page-leaving');
	});
});

window.addEventListener('pageshow', () => document.body.classList.remove('page-leaving'));