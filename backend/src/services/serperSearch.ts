import axios from 'axios';
import { SearchResult } from '../types';

const SERPER_API_URL = 'https://google.serper.dev/search';

/**
 * Known company domains for validation
 */
const KNOWN_COMPANY_DOMAINS: Record<string, string[]> = {
    'TCS': ['tcs.com'],
    'TATA CONSULTANCY': ['tcs.com'],
    'INFOSYS': ['infosys.com'],
    'WIPRO': ['wipro.com'],
    'RELIANCE': ['ril.com', 'relianceindustries.com'],
    'HDFC': ['hdfcbank.com', 'hdfc.com'],
    'ICICI': ['icicibank.com'],
    'SBI': ['sbi.co.in', 'bank.sbi'],
    'AXIS': ['axisbank.com'],
    'KOTAK': ['kotak.com'],
    'GRASIM': ['grasim.com', 'adityabirla.com'],
    'HINDALCO': ['hindalco.com', 'adityabirla.com'],
    'ULTRATECH': ['ultratechcement.com', 'adityabirla.com'],
    'TATA MOTORS': ['tatamotors.com'],
    'TATA STEEL': ['tatasteel.com'],
    'MARUTI': ['marutisuzuki.com'],
    'ITC': ['itcportal.com'],
    'BHARTI': ['airtel.in', 'bharti.com'],
    'ADANI': ['adani.com', 'adanienterprises.com'],
    'APPLE': ['apple.com'],
    'MICROSOFT': ['microsoft.com'],
    'GOOGLE': ['google.com', 'abc.xyz'],
    'AMAZON': ['amazon.com', 'aboutamazon.com'],
    'TESLA': ['tesla.com'],
    'NVIDIA': ['nvidia.com'],
    'META': ['meta.com', 'facebook.com'],
    'SAMSUNG': ['samsung.com'],
    'TOYOTA': ['toyota.com', 'toyota-global.com'],
    'VOLKSWAGEN': ['volkswagen.com', 'vw.com'],
};

/**
 * Search globally using Serper.dev (Google Search API)
 * Optimized for finding official PDF reports
 */
export async function searchGlobalWithSerper(
    company: string,
    year?: number,
    documentType: string = 'annual report'
): Promise<SearchResult[]> {
    const apiKey = process.env.SERPER_API_KEY;

    if (!apiKey) {
        console.warn('⚠️ SERPER_API_KEY is missing in .env file. Global search skipped.');
        return [];
    }

    const results: SearchResult[] = [];

    // For Indian fiscal years: FY2019 = April 2018 - March 2019
    // Search for both formats to improve matches
    let yearQuery = '';
    if (year) {
        const prevYear = year - 1;
        yearQuery = `("${prevYear}-${year}" OR "${prevYear}-${String(year).slice(2)}" OR "${year}")`;
    }

    // Construct an optimized search query
    const searchQuery = `"${company}" ${documentType} ${yearQuery} filetype:pdf`;

    console.log(`🌐 Serper Query: ${searchQuery}`);

    try {
        const response = await axios.post(
            SERPER_API_URL,
            {
                q: searchQuery,
                num: 15, // Fetch more results to filter
            },
            {
                headers: {
                    'X-API-KEY': apiKey,
                    'Content-Type': 'application/json'
                },
                timeout: 10000
            }
        );

        const organicResults = response.data.organic || [];

        // Get known domains for this company
        const companyUpper = company.toUpperCase();
        const knownDomains = KNOWN_COMPANY_DOMAINS[companyUpper] ||
            Object.entries(KNOWN_COMPANY_DOMAINS)
                .filter(([key]) => companyUpper.includes(key))
                .flatMap(([, domains]) => domains);

        for (const item of organicResults) {
            // Only accept actual PDFs
            if (!item.link.toLowerCase().endsWith('.pdf')) {
                continue;
            }

            const url = item.link.toLowerCase();
            const urlDomain = new URL(url).hostname.replace('www.', '');

            // If we have known domains for this company, prioritize them
            const isOfficialDomain = knownDomains.length === 0 ||
                knownDomains.some(domain => urlDomain.includes(domain));

            // Skip clearly unrelated domains
            const blockedDomains = ['scribd.com', 'coursehero.', 'studylib.', 'academia.edu'];
            if (blockedDomains.some(blocked => urlDomain.includes(blocked))) {
                continue;
            }

            // Calculate confidence based on domain match
            const confidence = isOfficialDomain ? 0.95 : 0.70;

            const title = item.title || `${company} ${documentType} ${year || ''}`;

            results.push({
                url: item.link,
                title: title,
                company: company,
                documentType: 'annual',
                fiscalYear: year,
                confidence: confidence,
                source: isOfficialDomain ? 'company-website' : 'other',
                fileFormat: 'PDF',
                linkVerified: true,
                notes: item.snippet
            });

            if (results.length >= 5) break; // Limit to 5 PDFs
        }

        // Sort by confidence (official domains first)
        results.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));

        console.log(`✅ Serper found ${results.length} PDFs for ${company}`);
    } catch (error) {
        console.error('❌ Serper API failed:', error instanceof Error ? error.message : error);
    }

    return results;
}
