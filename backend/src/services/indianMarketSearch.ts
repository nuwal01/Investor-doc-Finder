
import { SearchResult } from '../types';

// BSE/NSE company code mappings for major Indian companies
const INDIAN_COMPANY_CODES: Record<string, { bse?: string; nse?: string; name: string }> = {
    'RELIANCE': { bse: '500325', nse: 'RELIANCE', name: 'Reliance Industries Ltd' },
    'TCS': { bse: '532540', nse: 'TCS', name: 'Tata Consultancy Services Ltd' },
    'INFOSYS': { bse: '500209', nse: 'INFY', name: 'Infosys Ltd' },
    'HDFC BANK': { bse: '500180', nse: 'HDFCBANK', name: 'HDFC Bank Ltd' },
    'ICICI BANK': { bse: '532174', nse: 'ICICIBANK', name: 'ICICI Bank Ltd' },
    'WIPRO': { bse: '507685', nse: 'WIPRO', name: 'Wipro Ltd' },
    'BHARTI AIRTEL': { bse: '532454', nse: 'BHARTIARTL', name: 'Bharti Airtel Ltd' },
    'ITC': { bse: '500875', nse: 'ITC', name: 'ITC Ltd' },
    'KOTAK MAHINDRA BANK': { bse: '500247', nse: 'KOTAKBANK', name: 'Kotak Mahindra Bank Ltd' },
    'HINDUSTAN UNILEVER': { bse: '500696', nse: 'HINDUNILVR', name: 'Hindustan Unilever Ltd' },
    'TATA MOTORS': { bse: '500570', nse: 'TATAMOTORS', name: 'Tata Motors Ltd' },
    'TATA STEEL': { bse: '500470', nse: 'TATASTEEL', name: 'Tata Steel Ltd' },
    'SBI': { bse: '500112', nse: 'SBIN', name: 'State Bank of India' },
    'AXIS BANK': { bse: '532215', nse: 'AXISBANK', name: 'Axis Bank Ltd' },
    'MARUTI SUZUKI': { bse: '532500', nse: 'MARUTI', name: 'Maruti Suzuki India Ltd' },
    'BAJAJ FINANCE': { bse: '500034', nse: 'BAJFINANCE', name: 'Bajaj Finance Ltd' },
    'ASIAN PAINTS': { bse: '500820', nse: 'ASIANPAINT', name: 'Asian Paints Ltd' },
    'LARSEN & TOUBRO': { bse: '500510', nse: 'LT', name: 'Larsen & Toubro Ltd' },
    'HCL TECH': { bse: '532281', nse: 'HCLTECH', name: 'HCL Technologies Ltd' },
    'ADANI ENTERPRISES': { bse: '512599', nse: 'ADANIENT', name: 'Adani Enterprises Ltd' },
    'ADANI PORTS': { bse: '532921', nse: 'ADANIPORTS', name: 'Adani Ports and SEZ Ltd' },
    'TITAN': { bse: '500114', nse: 'TITAN', name: 'Titan Company Ltd' },
    'SUN PHARMA': { bse: '524715', nse: 'SUNPHARMA', name: 'Sun Pharmaceutical Industries Ltd' },
    'ULTRATECH CEMENT': { bse: '532538', nse: 'ULTRACEMCO', name: 'UltraTech Cement Ltd' },
    'POWER GRID': { bse: '532898', nse: 'POWERGRID', name: 'Power Grid Corporation of India Ltd' },
    'NTPC': { bse: '532555', nse: 'NTPC', name: 'NTPC Ltd' },
    'ONGC': { bse: '500312', nse: 'ONGC', name: 'Oil and Natural Gas Corporation Ltd' },
    'COAL INDIA': { bse: '533278', nse: 'COALINDIA', name: 'Coal India Ltd' },
    'TECH MAHINDRA': { bse: '532755', nse: 'TECHM', name: 'Tech Mahindra Ltd' },
    'MAHINDRA': { bse: '500520', nse: 'M&M', name: 'Mahindra & Mahindra Ltd' },
    'BAJAJ FINSERV': { bse: '532978', nse: 'BAJAJFINSV', name: 'Bajaj Finserv Ltd' },
    'NESTLE INDIA': { bse: '500790', nse: 'NESTLEIND', name: 'Nestle India Ltd' },
    'BRITANNIA': { bse: '500825', nse: 'BRITANNIA', name: 'Britannia Industries Ltd' },
    'INDUSIND BANK': { bse: '532187', nse: 'INDUSINDBK', name: 'IndusInd Bank Ltd' },
    'DIVIS LAB': { bse: '532488', nse: 'DIVISLAB', name: 'Divi\'s Laboratories Ltd' },
    'EICHER MOTORS': { bse: '505200', nse: 'EICHERMOT', name: 'Eicher Motors Ltd' },
    'GRASIM': { bse: '500300', nse: 'GRASIM', name: 'Grasim Industries Ltd' },
    'CIPLA': { bse: '500087', nse: 'CIPLA', name: 'Cipla Ltd' },
    'DR REDDY': { bse: '500124', nse: 'DRREDDY', name: 'Dr. Reddy\'s Laboratories Ltd' },
    'HERO MOTOCORP': { bse: '500182', nse: 'HEROMOTOCO', name: 'Hero MotoCorp Ltd' },
    'SHREE CEMENT': { bse: '500387', nse: 'SHREECEM', name: 'Shree Cement Ltd' },
    'HINDALCO': { bse: '500440', nse: 'HINDALCO', name: 'Hindalco Industries Ltd' },
    'VEDANTA': { bse: '500295', nse: 'VEDL', name: 'Vedanta Ltd' },
    'JSW STEEL': { bse: '500228', nse: 'JSWSTEEL', name: 'JSW Steel Ltd' },
    'BHARAT PETROLEUM': { bse: '500547', nse: 'BPCL', name: 'Bharat Petroleum Corporation Ltd' },
    'INDIAN OIL': { bse: '530965', nse: 'IOC', name: 'Indian Oil Corporation Ltd' },
    'ZOMATO': { bse: '543320', nse: 'ZOMATO', name: 'Zomato Ltd' },
    'PAYTM': { bse: '543396', nse: 'PAYTM', name: 'One97 Communications Ltd' },
    'NYKAA': { bse: '543384', nse: 'NYKAA', name: 'FSN E-Commerce Ventures Ltd' },
    'POLICYBAZAAR': { bse: '543390', nse: 'POLICYBZR', name: 'PB Fintech Ltd' },
};



interface IndianCompanyMatch {
    code: string;
    bse?: string;
    nse?: string;
    name: string;
}

/**
 * Find Indian company by name
 */
export function findIndianCompany(companyName: string): IndianCompanyMatch | null {
    const searchName = companyName.toUpperCase().trim();

    // Direct match
    if (INDIAN_COMPANY_CODES[searchName]) {
        return { code: searchName, ...INDIAN_COMPANY_CODES[searchName] };
    }

    // Partial match
    for (const [code, data] of Object.entries(INDIAN_COMPANY_CODES)) {
        if (code.includes(searchName) || searchName.includes(code) ||
            data.name.toUpperCase().includes(searchName)) {
            return { code, ...data };
        }
    }

    return null;
}

/**
 * Search BSE for company filings
 */
export async function searchBSE(companyName: string, documentType: string, year?: number): Promise<SearchResult[]> {
    const results: SearchResult[] = [];

    const company = findIndianCompany(companyName);
    if (!company || !company.bse) {
        return results;
    }

    try {
        // BSE corporate filings page
        const bseUrl = `https://www.bseindia.com/corporates/ann.html?scrip=${company.bse}`;



        // For now, provide direct links to BSE pages
        results.push({
            url: bseUrl,
            title: `${company.name} - BSE Corporate Announcements`,
            company: company.name,
            ticker: company.bse,
            documentType: documentType || 'annual',
            filingDate: year ? `${year}` : undefined,
            confidence: 0.8,
            source: 'bse-india' as any,
            fileFormat: 'HTML'
        });

        if (documentType === 'annual' || !documentType) {
            results.push({
                url: `https://www.bseindia.com/stock-share-price/${company.name.toLowerCase().replace(/\s+/g, '-')}/${company.bse}/annual-reports`,
                title: `${company.name} - Annual Reports (BSE)`,
                company: company.name,
                ticker: company.bse,
                documentType: 'annual',
                filingDate: year ? `${year}` : undefined,
                confidence: 0.85,
                source: 'bse-india' as any,
                fileFormat: 'PDF'
            });
        }

    } catch (error) {
        console.error('BSE search failed:', error);
    }

    return results;
}

/**
 * Search NSE for company filings
 */
export async function searchNSE(companyName: string, documentType: string, year?: number): Promise<SearchResult[]> {
    const results: SearchResult[] = [];

    const company = findIndianCompany(companyName);
    if (!company || !company.nse) {
        return results;
    }

    try {
        // NSE company page with corporate actions and filings
        const nseUrl = `https://www.nseindia.com/get-quotes/equity?symbol=${company.nse}`;



        results.push({
            url: nseUrl,
            title: `${company.name} - NSE Company Page`,
            company: company.name,
            ticker: company.nse,
            documentType: documentType || 'annual',
            filingDate: year ? `${year}` : undefined,
            confidence: 0.8,
            source: 'nse-india' as any,
            fileFormat: 'HTML'
        });

        // Direct link to annual report on NSE
        if (documentType === 'annual' || !documentType) {
            results.push({
                url: `https://www.nseindia.com/companies-listing/corporate-filings-annual-reports?symbol=${company.nse}`,
                title: `${company.name} - Annual Reports (NSE)`,
                company: company.name,
                ticker: company.nse,
                documentType: 'annual',
                filingDate: year ? `${year}` : undefined,
                confidence: 0.85,
                source: 'nse-india' as any,
                fileFormat: 'PDF'
            });
        }

    } catch (error) {
        console.error('NSE search failed:', error);
    }

    return results;
}

/**
 * Main function to search Indian markets
 */
export async function searchIndianMarkets(
    companyName: string,
    documentType: string,
    year?: number
): Promise<SearchResult[]> {
    const results: SearchResult[] = [];

    // Search both BSE and NSE
    const [bseResults, nseResults] = await Promise.all([
        searchBSE(companyName, documentType, year),
        searchNSE(companyName, documentType, year)
    ]);

    results.push(...bseResults, ...nseResults);

    // Sort by confidence
    results.sort((a, b) => b.confidence - a.confidence);

    return results;
}

/**
 * Check if a company name looks like an Indian company
 */
export function isLikelyIndianCompany(companyName: string): boolean {
    const indianIndicators = [
        'LIMITED', 'LTD', 'INDIA', 'INDIAN', 'BHARAT',
        'HINDUSTAN', 'TATA', 'RELIANCE', 'ADANI', 'BAJAJ',
        'MAHINDRA', 'BIRLA', 'INFOSYS', 'WIPRO', 'HCL',
        'SBI', 'ICICI', 'HDFC', 'KOTAK', 'AXIS'
    ];

    const upperName = companyName.toUpperCase();
    return indianIndicators.some(indicator => upperName.includes(indicator)) ||
        findIndianCompany(companyName) !== null;
}

export { INDIAN_COMPANY_CODES };
