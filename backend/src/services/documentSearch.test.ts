import { searchDocuments } from './documentSearch';
import { ParsedQuery } from '../types';

// Mock axios to prevent actual network calls in tests
jest.mock('axios', () => ({
    get: jest.fn(),
    head: jest.fn()
}));

const axios = require('axios');

describe('Document Search Service', () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });

    describe('searchDocuments', () => {
        test('returns empty array when company is not provided', async () => {
            const query: ParsedQuery = { company: '' };
            const results = await searchDocuments(query);
            expect(results).toEqual([]);
        });

        test('searches SEC EDGAR for known companies with CIK', async () => {
            const mockResponse = {
                data: {
                    name: 'Apple Inc',
                    tickers: ['AAPL'],
                    filings: {
                        recent: {
                            form: ['10-K', '10-Q', '8-K'],
                            filingDate: ['2024-11-01', '2024-08-01', '2024-07-15'],
                            accessionNumber: ['0001-24-000001', '0001-24-000002', '0001-24-000003'],
                            primaryDocument: ['aapl-20241001.htm', 'aapl-20240801.htm', 'aapl-20240715.htm']
                        }
                    }
                }
            };

            axios.get.mockResolvedValueOnce(mockResponse);

            const query: ParsedQuery = {
                company: 'Apple',
                documentType: 'annual',
                year: 2024
            };

            const results = await searchDocuments(query);

            // Verify axios was called with SEC EDGAR API
            expect(axios.get).toHaveBeenCalledWith(
                expect.stringContaining('data.sec.gov/submissions/CIK'),
                expect.objectContaining({ timeout: 15000 })
            );

            // Verify results is an array
            expect(Array.isArray(results)).toBe(true);
        });

        test('handles SEC EDGAR API errors gracefully', async () => {
            axios.get.mockRejectedValueOnce(new Error('Network error'));

            const query: ParsedQuery = {
                company: 'Apple',
                documentType: 'annual',
                year: 2024
            };

            // Should not throw, returns empty array on error
            const results = await searchDocuments(query);
            expect(Array.isArray(results)).toBe(true);
        });

        test('falls back to name search for unknown companies', async () => {
            const mockSearchResponse = {
                data: {
                    hits: {
                        hits: [
                            {
                                _source: {
                                    ciks: ['0001234567'],
                                    adsh: '0001-24-000001',
                                    form: '10-K',
                                    file_date: '2024-11-01',
                                    display_names: ['Unknown Corp'],
                                    tickers: ['UNKN']
                                }
                            }
                        ]
                    }
                }
            };

            const mockIndexResponse = {
                data: {
                    directory: {
                        item: [
                            { name: 'unkn-10k-2024.htm' }
                        ]
                    }
                }
            };

            axios.get
                .mockResolvedValueOnce(mockSearchResponse)
                .mockResolvedValueOnce(mockIndexResponse);

            const query: ParsedQuery = {
                company: 'Unknown Company',
                documentType: 'annual'
            };

            const results = await searchDocuments(query);
            expect(Array.isArray(results)).toBe(true);
        });

        test('limits results to top 5', async () => {
            const mockResponse = {
                data: {
                    name: 'Test Corp',
                    filings: {
                        recent: {
                            form: ['10-K', '10-K', '10-K', '10-K', '10-K', '10-K', '10-K'],
                            filingDate: ['2024-01', '2023-01', '2022-01', '2021-01', '2020-01', '2019-01', '2018-01'],
                            accessionNumber: ['1', '2', '3', '4', '5', '6', '7'],
                            primaryDocument: ['a.htm', 'b.htm', 'c.htm', 'd.htm', 'e.htm', 'f.htm', 'g.htm']
                        }
                    }
                }
            };

            axios.get.mockResolvedValueOnce(mockResponse);

            const query: ParsedQuery = {
                company: 'Apple'
            };

            const results = await searchDocuments(query);
            expect(results.length).toBeLessThanOrEqual(5);
        });

        test('sorts results by confidence score', async () => {
            const mockResponse = {
                data: {
                    name: 'Apple Inc',
                    tickers: ['AAPL'],
                    filings: {
                        recent: {
                            form: ['10-K', '10-K'],
                            filingDate: ['2024-01-01', '2023-01-01'],
                            accessionNumber: ['0001-24-000001', '0001-23-000001'],
                            primaryDocument: ['aapl-2024.htm', 'aapl-2023.htm']
                        }
                    }
                }
            };

            axios.get.mockResolvedValueOnce(mockResponse);

            const query: ParsedQuery = {
                company: 'Apple',
                year: 2024
            };

            const results = await searchDocuments(query);

            // Results should be sorted by confidence (descending)
            for (let i = 1; i < results.length; i++) {
                expect(results[i - 1].confidence).toBeGreaterThanOrEqual(results[i].confidence);
            }
        });
    });
});
