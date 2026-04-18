import axios from 'axios';
import { ParsedQuery, SearchResult, SearchResponse } from '../types';
import { searchGlobalWithSerper } from './serperSearch';

const SEC_HEADERS = {
    'User-Agent': 'FinancialReportFinder/1.0 (investor-finder-demo@example.com)',
    'Accept-Encoding': 'gzip, deflate',
    'Accept': 'application/json, text/html',
};

// Cache for SEC company tickers
let companyTickersCache: Record<string, { cik_str: string; ticker: string; title: string }> | null = null;
let cacheTimestamp: number = 0;
const CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 hours

/**
 * MAIN SEARCH FUNCTION - GLOBAL SUPPORT
 * 1. Try SEC EDGAR (Best for US Companies)
 * 2. Try Serper.dev (Best for Global Companies & PDFs)
 */
export async function searchDocuments(query: ParsedQuery): Promise<SearchResult[]> {
    const companyName = query.company || '';
    const documentType = query.documentType || 'annual';
    const year = query.year;

    console.log(`\n========================================`);
    console.log(`SEARCH: "${companyName}" - ${documentType} - Year: ${year || 'latest'}`);
    console.log(`========================================`);

    const results: SearchResult[] = [];
    const searchPromises: Promise<SearchResult[]>[] = [];

    // 1. SEC EDGAR Search (US)
    searchPromises.push(
        searchSECEdgar(companyName, documentType, year, query.ticker)
            .then(res => {
                if (res.length > 0) console.log(`✅ SEC Found: ${res.length} reports`);
                return res;
            })
            .catch(() => {
                // SEC search warning valid for non-US companies
                return [];
            })
    );

    // 2. Serper Global Search (International + Fallback)
    searchPromises.push(
        searchGlobalWithSerper(companyName, year, 'annual report')
            .then(res => {
                if (res.length > 0) console.log(`✅ Serper Found: ${res.length} PDFs`);
                return res;
            })
            .catch(err => {
                console.warn(`Serper Search warning: ${err.message}`);
                return []; // Fail gracefully if API key missing
            })
    );

    // Wait for all
    const allResults = await Promise.all(searchPromises);

    // Merge results
    for (const res of allResults) {
        results.push(...res);
    }

    // Deduplicate by URL
    const uniqueResults = results.filter((value, index, self) =>
        index === self.findIndex((t) => (
            t.url === value.url
        ))
    );

    // Fallback: If no API key and no results, provide a helpful note
    if (uniqueResults.length === 0 && !process.env.SERPER_API_KEY) {
        console.log('❌ No results. Serper API Key missing.');
    }

    return uniqueResults.slice(0, 10);
}

/**
 * Search SEC EDGAR for US companies
 */
async function searchSECEdgar(
    companyName: string,
    documentType: string,
    year?: number,
    ticker?: string
): Promise<SearchResult[]> {
    const results: SearchResult[] = [];

    // Get CIK for company
    const cik = await lookupCIK(companyName, ticker);
    if (!cik) {
        // Not a US listed company or not found in SEC database
        return results;
    }

    const filingType = documentType === 'quarterly' ? '10-Q' : '10-K';

    try {
        const apiUrl = `https://data.sec.gov/submissions/CIK${cik}.json`;

        const response = await axios.get(apiUrl, {
            timeout: 15000,
            headers: SEC_HEADERS
        });

        const data = response.data;
        const filings = data.filings?.recent;

        if (!filings) {
            return results;
        }

        // Find matching filings
        for (let i = 0; i < filings.form.length && results.length < 5; i++) {
            const form = filings.form[i];
            if (form === filingType || form === `${filingType}/A`) {
                const reportDate = filings.reportDate?.[i];
                const filingDate = filings.filingDate[i];
                const fiscalYearEnd = reportDate || filingDate;
                const fiscalYear = parseInt(fiscalYearEnd.substring(0, 4), 10);

                // Match year if specified
                if (year && fiscalYear !== year) {
                    continue;
                }

                const accessionNumber = filings.accessionNumber[i].replace(/-/g, '');
                const primaryDocument = filings.primaryDocument[i];
                const cikClean = cik.replace(/^0+/, '');

                // Direct link to the filing document
                const documentUrl = `https://www.sec.gov/Archives/edgar/data/${cikClean}/${accessionNumber}/${primaryDocument}`;

                results.push({
                    url: documentUrl,
                    title: `${data.name} - ${form} (FY${fiscalYear})`,
                    company: data.name,
                    ticker: data.tickers?.[0] || ticker,
                    documentType: documentType,
                    filingDate: filingDate,
                    fiscalYear: fiscalYear,
                    fiscalPeriodEnd: reportDate,
                    confidence: 1.0, // SEC is authoritative
                    source: 'sec-edgar',
                    fileFormat: primaryDocument.endsWith('.htm') ? 'HTML' : 'PDF',
                    linkVerified: true, // SEC links are always valid
                });
            }
        }
    } catch (error) {
        // SEC search might fail for non-US companies, which is fine
        // console.error('SEC EDGAR error:', error);
    }

    return results;
}

/**
 * Lookup CIK from SEC database
 */
async function lookupCIK(companyName: string, ticker?: string): Promise<string | undefined> {
    try {
        // Fetch and cache company tickers
        if (!companyTickersCache || Date.now() - cacheTimestamp > CACHE_DURATION) {
            const response = await axios.get('https://www.sec.gov/files/company_tickers.json', {
                timeout: 10000,
                headers: SEC_HEADERS
            });

            companyTickersCache = {};
            for (const key of Object.keys(response.data)) {
                const entry = response.data[key];
                const cikPadded = String(entry.cik_str).padStart(10, '0');
                companyTickersCache[entry.ticker.toUpperCase()] = { ...entry, cik_str: cikPadded };
                companyTickersCache[entry.title.toUpperCase()] = { ...entry, cik_str: cikPadded };
            }
            cacheTimestamp = Date.now();
        }

        // Try ticker first
        if (ticker && companyTickersCache[ticker.toUpperCase()]) {
            return companyTickersCache[ticker.toUpperCase()].cik_str;
        }

        // Try exact company name
        const upperName = companyName.toUpperCase();
        if (companyTickersCache[upperName]) {
            return companyTickersCache[upperName].cik_str;
        }

        // Try fuzzy match for SEC
        const searchWords = upperName.split(/\s+/).filter(w => w.length > 2);
        if (searchWords.length === 0) return undefined;

        const firstWord = searchWords[0];

        for (const [key, entry] of Object.entries(companyTickersCache)) {
            const keyWords = key.split(/\s+/);
            if (keyWords[0] === firstWord) {
                // Check if most words match
                const matchCount = searchWords.filter(sw => keyWords.includes(sw)).length;
                if (matchCount >= Math.min(2, searchWords.length)) {
                    return entry.cik_str;
                }
            }
        }

        return undefined;
    } catch (error) {
        return undefined;
    }
}

/**
 * Extended search with full metadata
 */
export async function searchDocumentsExtended(query: ParsedQuery): Promise<SearchResponse> {
    const results = await searchDocuments(query);

    // Check if we should warn about missing API key
    let notes: string | undefined;
    if (results.length === 0) {
        if (!process.env.SERPER_API_KEY) {
            notes = "Serper API Key is missing. Only US (SEC) companies are currently supported. Please add your key to search globally.";
        } else {
            notes = `No results found for "${query.company}".`;
        }
    }

    return {
        success: results.length > 0,
        company: results[0]?.company || query.company,
        requestedReport: `${query.documentType || 'annual'} report${query.year ? ` for ${query.year}` : ''}`,
        results: results,
        notes: notes,
    };
}
