import { searchCompanies, SP500_COMPANIES, TICKER_TO_COMPANY, NAME_TO_COMPANY } from './sp500';

describe('S&P 500 Company Data', () => {

    describe('Data Integrity', () => {
        test('has at least 100 companies', () => {
            expect(SP500_COMPANIES.length).toBeGreaterThanOrEqual(100);
        });

        test('all companies have required fields', () => {
            for (const company of SP500_COMPANIES) {
                expect(company.name).toBeTruthy();
                expect(company.ticker).toBeTruthy();
                expect(typeof company.name).toBe('string');
                expect(typeof company.ticker).toBe('string');
            }
        });

        test('tickers are uppercase', () => {
            for (const company of SP500_COMPANIES) {
                // Allow period for BRK.B style tickers
                expect(company.ticker).toMatch(/^[A-Z.]+$/);
            }
        });

        test('CIK numbers are properly formatted when present', () => {
            for (const company of SP500_COMPANIES) {
                if (company.cik) {
                    expect(company.cik).toMatch(/^\d{10}$/);
                }
            }
        });
    });

    describe('Lookup Maps', () => {
        test('TICKER_TO_COMPANY maps correctly', () => {
            expect(TICKER_TO_COMPANY['AAPL']).toBeDefined();
            expect(TICKER_TO_COMPANY['AAPL'].name).toBe('Apple');

            expect(TICKER_TO_COMPANY['MSFT']).toBeDefined();
            expect(TICKER_TO_COMPANY['MSFT'].name).toBe('Microsoft');
        });

        test('NAME_TO_COMPANY maps correctly (case insensitive keys)', () => {
            expect(NAME_TO_COMPANY['apple']).toBeDefined();
            expect(NAME_TO_COMPANY['apple'].ticker).toBe('AAPL');

            expect(NAME_TO_COMPANY['microsoft']).toBeDefined();
            expect(NAME_TO_COMPANY['microsoft'].ticker).toBe('MSFT');
        });
    });

    describe('searchCompanies', () => {
        test('returns empty array for empty query', () => {
            expect(searchCompanies('')).toEqual([]);
            expect(searchCompanies(null as unknown as string)).toEqual([]);
        });

        test('finds company by exact ticker', () => {
            const results = searchCompanies('AAPL');
            expect(results.length).toBeGreaterThan(0);
            expect(results[0].ticker).toBe('AAPL');
        });

        test('finds company by partial ticker', () => {
            const results = searchCompanies('AAP');
            expect(results.some(c => c.ticker === 'AAPL')).toBe(true);
        });

        test('finds company by exact name', () => {
            const results = searchCompanies('Apple');
            expect(results.length).toBeGreaterThan(0);
            expect(results[0].name).toBe('Apple');
        });

        test('finds company by partial name', () => {
            const results = searchCompanies('Micro');
            expect(results.some(c => c.name === 'Microsoft')).toBe(true);
        });

        test('search is case insensitive', () => {
            const results1 = searchCompanies('apple');
            const results2 = searchCompanies('APPLE');
            const results3 = searchCompanies('Apple');

            expect(results1[0].ticker).toBe('AAPL');
            expect(results2[0].ticker).toBe('AAPL');
            expect(results3[0].ticker).toBe('AAPL');
        });

        test('respects limit parameter', () => {
            const results = searchCompanies('a', 5);
            expect(results.length).toBeLessThanOrEqual(5);
        });

        test('returns unique companies (no duplicates)', () => {
            const results = searchCompanies('google');
            const tickers = results.map(c => c.ticker);
            const uniqueTickers = new Set(tickers);
            expect(tickers.length).toBe(uniqueTickers.size);
        });

        test('prioritizes exact matches over partial matches', () => {
            const results = searchCompanies('TSLA');
            expect(results[0].ticker).toBe('TSLA');
        });

        test('handles special characters gracefully', () => {
            // Should not throw
            expect(() => searchCompanies('Johnson & Johnson')).not.toThrow();
            const results = searchCompanies('Johnson');
            expect(results.some(c => c.name.includes('Johnson'))).toBe(true);
        });
    });
});
