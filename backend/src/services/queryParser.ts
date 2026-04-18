import nlp from 'compromise';
import { ParsedQuery } from '../types';

// Common ticker to company name mappings
const TICKER_MAP: Record<string, string> = {
    'AAPL': 'Apple',
    'TSLA': 'Tesla',
    'MSFT': 'Microsoft',
    'GOOGL': 'Google',
    'GOOG': 'Google',
    'AMZN': 'Amazon',
    'META': 'Meta',
    'NVDA': 'NVIDIA',
    'JPM': 'JPMorgan',
    'V': 'Visa',
    'WMT': 'Walmart',
    'JNJ': 'Johnson & Johnson',
    'PG': 'Procter & Gamble',
    'UNH': 'UnitedHealth',
    'HD': 'Home Depot',
    'MA': 'Mastercard',
    'DIS': 'Disney',
    'PYPL': 'PayPal',
    'NFLX': 'Netflix',
    'INTC': 'Intel',
    'AMD': 'AMD',
    'CRM': 'Salesforce',
    'ORCL': 'Oracle',
    'IBM': 'IBM',
    'GS': 'Goldman Sachs',
    'BA': 'Boeing',
    'CAT': 'Caterpillar',
    'MMM': '3M',
    'GE': 'General Electric',
    'F': 'Ford',
    'GM': 'General Motors'
};

// Document type patterns
const DOC_TYPE_PATTERNS: { pattern: RegExp; type: ParsedQuery['documentType']; filing?: string }[] = [
    { pattern: /\b10-?k\b/i, type: 'annual', filing: '10-K' },
    { pattern: /\bannual\s*report\b/i, type: 'annual', filing: '10-K' },
    { pattern: /\b10-?q\b/i, type: 'quarterly', filing: '10-Q' },
    { pattern: /\bquarterly\s*(report|earnings|results)?\b/i, type: 'quarterly', filing: '10-Q' },
    { pattern: /\bq[1-4]\b/i, type: 'quarterly', filing: '10-Q' },
    { pattern: /\bearnings?\s*(report|release|call)?\b/i, type: 'quarterly' },
    { pattern: /\binvestor\s*(presentation|deck|day)\b/i, type: 'investor-presentation' },
    { pattern: /\bproxy\b/i, type: 'proxy', filing: 'DEF 14A' },
    { pattern: /\b8-?k\b/i, type: 'current', filing: '8-K' },
    { pattern: /\besg\b/i, type: 'esg' },
    { pattern: /\bsustainability\b/i, type: 'esg' },
];

// Quarter patterns
const QUARTER_PATTERNS = [
    { pattern: /\bq1\b/i, quarter: 1 },
    { pattern: /\bq2\b/i, quarter: 2 },
    { pattern: /\bq3\b/i, quarter: 3 },
    { pattern: /\bq4\b/i, quarter: 4 },
    { pattern: /\bfirst\s*quarter\b/i, quarter: 1 },
    { pattern: /\bsecond\s*quarter\b/i, quarter: 2 },
    { pattern: /\bthird\s*quarter\b/i, quarter: 3 },
    { pattern: /\bfourth\s*quarter\b/i, quarter: 4 },
];

export async function parseQuery(query: string): Promise<ParsedQuery> {
    const result: ParsedQuery = {
        company: '',
    };

    let workingQuery = query;

    // Extract year (4 digits, typically 1990-2059)
    const yearMatch = workingQuery.match(/\b(199[0-9]|20[0-5][0-9])\b/);
    if (yearMatch) {
        result.year = parseInt(yearMatch[1], 10);
        // Remove year from working query to avoid confusing NLP
        workingQuery = workingQuery.replace(yearMatch[0], '');
    }

    // Extract quarter
    for (const { pattern, quarter } of QUARTER_PATTERNS) {
        if (pattern.test(workingQuery)) {
            result.quarter = quarter;
            // Remove quarter from working query
            workingQuery = workingQuery.replace(pattern, ' ');
            break;
        }
    }

    // Extract document type
    for (const { pattern, type, filing } of DOC_TYPE_PATTERNS) {
        if (pattern.test(workingQuery)) {
            result.documentType = type;
            if (filing) {
                result.filingType = filing;
            }
            // Remove document type from working query
            workingQuery = workingQuery.replace(pattern, ' ');
            break;
        }
    }

    // Debug: see what's left
    // console.log('Working query after stripping:', workingQuery);

    // Check for ticker symbols (uppercase 1-5 letters) in the ORIGINAL query (tickers might be mixed)
    // But safer to check workingQuery to avoid parts of words? 
    // actually tickers are usually distinct.
    const tickerMatch = query.match(/\b([A-Z]{1,5})\b/);
    if (tickerMatch) {
        const potentialTicker = tickerMatch[1];
        if (TICKER_MAP[potentialTicker]) {
            result.ticker = potentialTicker;
            result.company = TICKER_MAP[potentialTicker];
            // Don't return early - let it fall through to set defaults
        }
    }

    // Use NLP on the CLEANED query
    if (!result.company) {
        // Clean up extra whitespace
        workingQuery = workingQuery.replace(/\s+/g, ' ').trim();

        // First, try to extract company names with common suffixes/patterns
        // Match patterns like "Eli Lilly And Co", "Apple Inc", "Microsoft Corp", etc.
        const companyPatterns = [
            /^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*(?:\s+(?:And|&)\s+[A-Z][a-zA-Z]+)*(?:\s+(?:Co|Inc|Corp|Corporation|Ltd|LLC|Company|Group|Holdings))?)/i,
            /^((?:[A-Z][a-zA-Z]+\s+)+(?:And|&)\s+[A-Z][a-zA-Z]+)/i,  // "X And Y" pattern
            /^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,4})/i,  // Up to 5 capitalized words
        ];

        for (const pattern of companyPatterns) {
            const match = workingQuery.match(pattern);
            if (match && match[1]) {
                const potentialCompany = match[1].trim();
                // Make sure it's not just a common word
                const excludeWords = ['The', 'For', 'Year', 'Report', 'Annual', 'Quarterly'];
                if (!excludeWords.includes(potentialCompany)) {
                    result.company = potentialCompany;
                    console.log(`Extracted company via pattern: ${result.company}`);
                    break;
                }
            }
        }

        // Fall back to NLP if pattern matching didn't work
        if (!result.company) {
            const doc = nlp(workingQuery);

            // Look for organizations
            const orgs = doc.organizations().out('array');
            if (orgs.length > 0) {
                result.company = orgs[0];
                console.log(`Extracted company via NLP organizations: ${result.company}`);
            } else {
                // Try to find proper nouns that might be company names
                const nouns = doc.nouns().out('array');

                const excludeWords = new Set([
                    'report', 'annual', 'quarterly', 'earnings', 'presentation',
                    'investor', 'proxy', 'statement', 'filing', 'results',
                    'fiscal', 'year', 'financial', 'statement'
                ]);

                for (const noun of nouns) {
                    const lowerNoun = noun.toLowerCase();
                    // Simple heuristic: ignore small words or excluded words
                    if (!excludeWords.has(lowerNoun) && noun.length > 2) {
                        // If it's capitalized, good candidate
                        if (/^[A-Z]/.test(noun)) {
                            result.company = noun;
                            console.log(`Extracted company via NLP nouns: ${result.company}`);
                            break;
                        }
                    }
                }
            }
        }
    }

    // Fallback: splitting the cleaned string
    if (!result.company) {
        // Remove any remaining common terms that regex might have missed or are just noise
        const cleaned = workingQuery
            .replace(/[^\w\s]/g, '') // remove punctuation
            .trim();

        const words = cleaned.split(/\s+/).filter(w => w.length > 1);
        if (words.length > 0) {
            // Return the title cased version of the first significant word if it looks promising
            const word = words[0];
            // Basic check: starts with capital or we force it?
            // Let's force title case for the fallback
            result.company = word.charAt(0).toUpperCase() + word.slice(1);
        }
    }

    // Default document type if not specified
    if (!result.documentType) {
        result.documentType = 'annual';
    }

    // Default year to current year if not specified
    if (!result.year) {
        result.year = new Date().getFullYear();
    }

    return result;
}
