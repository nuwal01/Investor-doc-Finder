import { parseQuery } from './queryParser';

describe('Query Parser', () => {
    describe('Company Name Extraction', () => {
        test('extracts company name from ticker', async () => {
            const result = await parseQuery('AAPL 10-K');
            expect(result.company).toBe('Apple');
            expect(result.ticker).toBe('AAPL');
        });

        test('maps TSLA to Tesla', async () => {
            const result = await parseQuery('TSLA annual report');
            expect(result.company).toBe('Tesla');
            expect(result.ticker).toBe('TSLA');
        });

        test('maps MSFT to Microsoft', async () => {
            const result = await parseQuery('MSFT 10-Q');
            expect(result.company).toBe('Microsoft');
            expect(result.ticker).toBe('MSFT');
        });

        test('extracts full company name', async () => {
            const result = await parseQuery('Tesla 10-K 2023');
            expect(result.company).toBe('Tesla');
        });

        test('handles company names with & symbol', async () => {
            const result = await parseQuery('Johnson & Johnson annual report');
            // NLP should extract some form of the company name
            expect(result.company).toBeTruthy();
        });

        test('extracts company via NLP fallback', async () => {
            const result = await parseQuery('Pfizer 10-Q 2024');
            expect(result.company).toBeTruthy();
        });

        test('handles lowercase input', async () => {
            const result = await parseQuery('apple quarterly earnings');
            expect(result.company).toBeTruthy();
        });
    });

    describe('Document Type Extraction', () => {
        test('identifies 10-K as annual report', async () => {
            const result = await parseQuery('Apple 10-K');
            expect(result.documentType).toBe('annual');
            expect(result.filingType).toBe('10-K');
        });

        test('identifies 10K (no hyphen) as annual report', async () => {
            const result = await parseQuery('Apple 10K 2024');
            expect(result.documentType).toBe('annual');
            expect(result.filingType).toBe('10-K');
        });

        test('identifies "annual report" keyword', async () => {
            const result = await parseQuery('Tesla annual report 2023');
            expect(result.documentType).toBe('annual');
        });

        test('identifies 10-Q as quarterly report', async () => {
            const result = await parseQuery('Microsoft 10-Q');
            expect(result.documentType).toBe('quarterly');
            expect(result.filingType).toBe('10-Q');
        });

        test('identifies Q1-Q4 as quarterly', async () => {
            const queries = [
                { query: 'Apple Q1 earnings', quarter: 1 },
                { query: 'Apple Q2 earnings', quarter: 2 },
                { query: 'Apple Q3 earnings', quarter: 3 },
                { query: 'Apple Q4 earnings', quarter: 4 },
            ];

            for (const { query, quarter } of queries) {
                const result = await parseQuery(query);
                expect(result.documentType).toBe('quarterly');
                expect(result.quarter).toBe(quarter);
            }
        });

        test('identifies "quarterly earnings" keyword', async () => {
            const result = await parseQuery('Google quarterly earnings');
            expect(result.documentType).toBe('quarterly');
        });

        test('identifies 8-K as current report', async () => {
            const result = await parseQuery('Amazon 8-K filing');
            expect(result.documentType).toBe('current');
            expect(result.filingType).toBe('8-K');
        });

        test('identifies proxy statement', async () => {
            const result = await parseQuery('Netflix proxy statement');
            expect(result.documentType).toBe('proxy');
        });

        test('identifies investor presentation', async () => {
            const result = await parseQuery('Microsoft investor presentation');
            expect(result.documentType).toBe('investor-presentation');
        });

        test('identifies ESG report', async () => {
            const result = await parseQuery('Apple ESG report');
            expect(result.documentType).toBe('esg');
        });

        test('identifies sustainability report', async () => {
            const result = await parseQuery('Tesla sustainability report');
            expect(result.documentType).toBe('esg');
        });

        test('defaults to annual when no type specified', async () => {
            const result = await parseQuery('Apple 2024');
            expect(result.documentType).toBe('annual');
        });
    });

    describe('Year Extraction', () => {
        test('extracts 4-digit year', async () => {
            const result = await parseQuery('Tesla 10-K 2024');
            expect(result.year).toBe(2024);
        });

        test('extracts year from any position', async () => {
            const result = await parseQuery('2023 Apple annual report');
            expect(result.year).toBe(2023);
        });

        test('defaults to current year if not specified', async () => {
            const result = await parseQuery('Google 10-K');
            expect(result.year).toBe(new Date().getFullYear());
        });

        test('handles years from 2000-2030', async () => {
            const years = [2020, 2021, 2022, 2023, 2024, 2025, 2026];
            for (const year of years) {
                const result = await parseQuery(`Apple 10-K ${year}`);
                expect(result.year).toBe(year);
            }
        });
    });

    describe('Quarter Extraction', () => {
        test('extracts quarter from Q1', async () => {
            const result = await parseQuery('Apple Q1 2024');
            expect(result.quarter).toBe(1);
        });

        test('extracts quarter from Q2', async () => {
            const result = await parseQuery('Apple Q2 earnings');
            expect(result.quarter).toBe(2);
        });

        test('extracts quarter from Q3', async () => {
            const result = await parseQuery('Apple Q3 results');
            expect(result.quarter).toBe(3);
        });

        test('extracts quarter from Q4', async () => {
            const result = await parseQuery('Apple Q4 2024');
            expect(result.quarter).toBe(4);
        });

        test('extracts "first quarter"', async () => {
            const result = await parseQuery('Apple first quarter earnings');
            expect(result.quarter).toBe(1);
        });

        test('extracts "second quarter"', async () => {
            const result = await parseQuery('Apple second quarter report');
            expect(result.quarter).toBe(2);
        });

        test('extracts "third quarter"', async () => {
            const result = await parseQuery('Apple third quarter 2024');
            expect(result.quarter).toBe(3);
        });

        test('extracts "fourth quarter"', async () => {
            const result = await parseQuery('Apple fourth quarter earnings');
            expect(result.quarter).toBe(4);
        });
    });

    describe('Combined Queries', () => {
        test('parses complete query: Tesla Q3 2024 earnings report', async () => {
            const result = await parseQuery('Tesla Q3 2024 earnings report');
            expect(result.company).toBe('Tesla');
            expect(result.documentType).toBe('quarterly');
            expect(result.quarter).toBe(3);
            expect(result.year).toBe(2024);
        });

        test('parses complete query: AAPL 10-K 2023', async () => {
            const result = await parseQuery('AAPL 10-K 2023');
            expect(result.company).toBe('Apple');
            expect(result.ticker).toBe('AAPL');
            expect(result.documentType).toBe('annual');
            expect(result.filingType).toBe('10-K');
            expect(result.year).toBe(2023);
        });

        test('parses query with company name and document type', async () => {
            const result = await parseQuery('Microsoft investor presentation');
            expect(result.company).toBe('Microsoft');
            expect(result.documentType).toBe('investor-presentation');
        });

        test('parses query with only ticker', async () => {
            const result = await parseQuery('GOOG');
            expect(result.company).toBe('Google');
            expect(result.ticker).toBe('GOOG');
            // Should default to annual and current year
            expect(result.documentType).toBe('annual');
            expect(result.year).toBe(new Date().getFullYear());
        });
    });

    describe('Edge Cases', () => {
        test('handles empty string', async () => {
            const result = await parseQuery('');
            // Should still return valid structure
            expect(result.company).toBe('');
        });

        test('handles whitespace-only string', async () => {
            const result = await parseQuery('   ');
            expect(typeof result.company).toBe('string');
        });

        test('handles special characters', async () => {
            const result = await parseQuery('Apple! @#$% 10-K 2024');
            expect(result.year).toBe(2024);
        });

        test('is case insensitive for document types', async () => {
            const result1 = await parseQuery('Apple 10-k');
            const result2 = await parseQuery('Apple 10-K');
            expect(result1.filingType).toBe('10-K');
            expect(result2.filingType).toBe('10-K');
        });
    });
});
