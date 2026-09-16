document.querySelectorAll('[data-confirm]').forEach((element) => { element.addEventListener('click', (event) => { if (!window.confirm(element.dataset.confirm)) event.preventDefault(); }); });

document.querySelectorAll('a[href]').forEach((link) => {
	link.addEventListener('click', (event) => {
		const target = link.getAttribute('target');
		const href = link.getAttribute('href');
		if (event.defaultPrevented || target === '_blank' || !href || href.startsWith('#') || href.startsWith('http')) return;
		document.body.classList.add('page-leaving');
	});
});

window.addEventListener('pageshow', () => document.body.classList.remove('page-leaving'));