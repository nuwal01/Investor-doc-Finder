document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('searchInput');
    const autocompleteResults = document.getElementById('autocompleteResults');

    if (!searchInput || !autocompleteResults || typeof companiesList === 'undefined') return;

    let debounceTimer;

    searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        const query = e.target.value.trim().toLowerCase();

        if (query.length < 2) {
            autocompleteResults.classList.add('hidden');
            return;
        }

        debounceTimer = setTimeout(() => {
            const matches = companiesList.filter(company =>
                company.name.toLowerCase().includes(query) ||
                company.ticker.toLowerCase().includes(query)
            ).slice(0, 5); // top 5 matches

            renderAutocomplete(matches, query);
        }, 150); // small debounce
    });

    // Hide dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target) && !autocompleteResults.contains(e.target)) {
            autocompleteResults.classList.add('hidden');
        }
    });

    function renderAutocomplete(matches, query) {
        if (matches.length === 0) {
            autocompleteResults.classList.add('hidden');
            return;
        }

        autocompleteResults.innerHTML = '';
        matches.forEach(match => {
            const div = document.createElement('div');
            div.className = 'autocomplete-item';
            div.innerHTML = `<strong>${match.name}</strong> <span style="color: var(--text-muted); font-size: 0.9em;">(${match.ticker})</span>`;

            div.addEventListener('click', () => {
                // Determine what to put in search box - maybe name + "earnings"?
                searchInput.value = `${match.name} `;
                autocompleteResults.classList.add('hidden');
                searchInput.focus();
            });

            autocompleteResults.appendChild(div);
        });

        autocompleteResults.classList.remove('hidden');
    }
});
