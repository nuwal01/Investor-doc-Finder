import axios from 'axios';
import { SearchResult } from '../types';

/**
 * OFFICIAL WEBSITE DATABASE
 * Maps company names to their official investor relations pages
 * This is the ONLY source of truth for report URLs
 */
const COMPANY_OFFICIAL_WEBSITES: Record<string, {
    name: string;
    officialWebsite: string;
    investorRelationsPage: string;
    annualReportsPage: string;
    quarterlyReportsPage?: string;
    aliases: string[];
    country: string;
}> = {
    // ==================== INDIAN BANKS ====================
    'STATE BANK OF INDIA': {
        name: 'State Bank of India',
        officialWebsite: 'https://www.sbi.co.in',
        investorRelationsPage: 'https://www.sbi.co.in/web/investor-relations/annual-reports',
        annualReportsPage: 'https://www.sbi.co.in/web/investor-relations/annual-reports',
        quarterlyReportsPage: 'https://www.sbi.co.in/web/investor-relations/quarterly-results',
        aliases: ['SBI', 'STATE BANK', 'SBIN'],
        country: 'IN'
    },
    'AXIS BANK': {
        name: 'Axis Bank Ltd',
        officialWebsite: 'https://www.axisbank.com',
        investorRelationsPage: 'https://www.axisbank.com/shareholders-corner/annual-reports',
        annualReportsPage: 'https://www.axisbank.com/shareholders-corner/annual-reports',
        quarterlyReportsPage: 'https://www.axisbank.com/shareholders-corner/quarterly-updates',
        aliases: ['AXIS BANK LTD', 'AXISBANK'],
        country: 'IN'
    },
    'HDFC BANK': {
        name: 'HDFC Bank Ltd',
        officialWebsite: 'https://www.hdfcbank.com',
        investorRelationsPage: 'https://www.hdfcbank.com/personal/about-us/investor-relations/annual-reports',
        annualReportsPage: 'https://www.hdfcbank.com/personal/about-us/investor-relations/annual-reports',
        quarterlyReportsPage: 'https://www.hdfcbank.com/personal/about-us/investor-relations/quarterly-results',
        aliases: ['HDFC', 'HDFCBANK'],
        country: 'IN'
    },
    'ICICI BANK': {
        name: 'ICICI Bank Ltd',
        officialWebsite: 'https://www.icicibank.com',
        investorRelationsPage: 'https://www.icicibank.com/aboutus/annual-reports',
        annualReportsPage: 'https://www.icicibank.com/aboutus/annual-reports',
        quarterlyReportsPage: 'https://www.icicibank.com/aboutus/investor-relations/quarterly-results',
        aliases: ['ICICI', 'ICICIBANK'],
        country: 'IN'
    },
    'KOTAK MAHINDRA BANK': {
        name: 'Kotak Mahindra Bank Ltd',
        officialWebsite: 'https://www.kotak.com',
        investorRelationsPage: 'https://www.kotak.com/en/investor-relations/financial-results/annual-reports.html',
        annualReportsPage: 'https://www.kotak.com/en/investor-relations/financial-results/annual-reports.html',
        aliases: ['KOTAK', 'KOTAK BANK', 'KOTAKBANK'],
        country: 'IN'
    },
    'INDUSIND BANK': {
        name: 'IndusInd Bank Ltd',
        officialWebsite: 'https://www.indusind.com',
        investorRelationsPage: 'https://www.indusind.com/in/en/investors/investor-landing/annual-reports.html',
        annualReportsPage: 'https://www.indusind.com/in/en/investors/investor-landing/annual-reports.html',
        aliases: ['INDUSIND', 'INDUSINDBK'],
        country: 'IN'
    },
    'PUNJAB NATIONAL BANK': {
        name: 'Punjab National Bank',
        officialWebsite: 'https://www.pnbindia.in',
        investorRelationsPage: 'https://www.pnbindia.in/annual-report.html',
        annualReportsPage: 'https://www.pnbindia.in/annual-report.html',
        aliases: ['PNB', 'PUNJAB NATIONAL'],
        country: 'IN'
    },
    'BANK OF BARODA': {
        name: 'Bank of Baroda',
        officialWebsite: 'https://www.bankofbaroda.in',
        investorRelationsPage: 'https://www.bankofbaroda.in/annual-reports',
        annualReportsPage: 'https://www.bankofbaroda.in/annual-reports',
        aliases: ['BOB', 'BANKBARODA'],
        country: 'IN'
    },
    'CANARA BANK': {
        name: 'Canara Bank',
        officialWebsite: 'https://canarabank.com',
        investorRelationsPage: 'https://canarabank.com/annual-reports',
        annualReportsPage: 'https://canarabank.com/annual-reports',
        aliases: ['CANARABANK'],
        country: 'IN'
    },

    // ==================== INDIAN IT COMPANIES ====================
    'TATA CONSULTANCY SERVICES': {
        name: 'Tata Consultancy Services Ltd',
        officialWebsite: 'https://www.tcs.com',
        investorRelationsPage: 'https://www.tcs.com/investor-relations/annual-reports',
        annualReportsPage: 'https://www.tcs.com/investor-relations/annual-reports',
        quarterlyReportsPage: 'https://www.tcs.com/investor-relations/financial-data/quarterly-results',
        aliases: ['TCS', 'TATA CONSULTANCY'],
        country: 'IN'
    },
    'INFOSYS': {
        name: 'Infosys Ltd',
        officialWebsite: 'https://www.infosys.com',
        investorRelationsPage: 'https://www.infosys.com/investors/reports-filings/annual-report.html',
        annualReportsPage: 'https://www.infosys.com/investors/reports-filings/annual-report.html',
        quarterlyReportsPage: 'https://www.infosys.com/investors/reports-filings/quarterly-results.html',
        aliases: ['INFY'],
        country: 'IN'
    },
    'WIPRO': {
        name: 'Wipro Ltd',
        officialWebsite: 'https://www.wipro.com',
        investorRelationsPage: 'https://www.wipro.com/investors/annual-reports/',
        annualReportsPage: 'https://www.wipro.com/investors/annual-reports/',
        aliases: [],
        country: 'IN'
    },
    'HCL TECHNOLOGIES': {
        name: 'HCL Technologies Ltd',
        officialWebsite: 'https://www.hcltech.com',
        investorRelationsPage: 'https://www.hcltech.com/investors/results-reports',
        annualReportsPage: 'https://www.hcltech.com/investors/results-reports#annual-reports',
        aliases: ['HCL TECH', 'HCLTECH', 'HCL'],
        country: 'IN'
    },
    'TECH MAHINDRA': {
        name: 'Tech Mahindra Ltd',
        officialWebsite: 'https://www.techmahindra.com',
        investorRelationsPage: 'https://www.techmahindra.com/en-in/investors/annual-reports/',
        annualReportsPage: 'https://www.techmahindra.com/en-in/investors/annual-reports/',
        aliases: ['TECHM'],
        country: 'IN'
    },

    // ==================== INDIAN CONGLOMERATES ====================
    'RELIANCE INDUSTRIES': {
        name: 'Reliance Industries Ltd',
        officialWebsite: 'https://www.ril.com',
        investorRelationsPage: 'https://www.ril.com/InvestorRelations/AnnualReports.aspx',
        annualReportsPage: 'https://www.ril.com/InvestorRelations/AnnualReports.aspx',
        aliases: ['RELIANCE', 'RIL'],
        country: 'IN'
    },
    'TATA MOTORS': {
        name: 'Tata Motors Ltd',
        officialWebsite: 'https://www.tatamotors.com',
        investorRelationsPage: 'https://www.tatamotors.com/investors/annual-reports/',
        annualReportsPage: 'https://www.tatamotors.com/investors/annual-reports/',
        aliases: ['TATAMOTORS'],
        country: 'IN'
    },
    'TATA STEEL': {
        name: 'Tata Steel Ltd',
        officialWebsite: 'https://www.tatasteel.com',
        investorRelationsPage: 'https://www.tatasteel.com/investors/annual-report/',
        annualReportsPage: 'https://www.tatasteel.com/investors/annual-report/',
        aliases: ['TATASTEEL'],
        country: 'IN'
    },
    'MAHINDRA & MAHINDRA': {
        name: 'Mahindra & Mahindra Ltd',
        officialWebsite: 'https://www.mahindra.com',
        investorRelationsPage: 'https://www.mahindra.com/investors/annual-report',
        annualReportsPage: 'https://www.mahindra.com/investors/annual-report',
        aliases: ['MAHINDRA', 'M&M'],
        country: 'IN'
    },
    'ADANI ENTERPRISES': {
        name: 'Adani Enterprises Ltd',
        officialWebsite: 'https://www.adanienterprises.com',
        investorRelationsPage: 'https://www.adanienterprises.com/investors/Annual-Reports',
        annualReportsPage: 'https://www.adanienterprises.com/investors/Annual-Reports',
        aliases: ['ADANI', 'ADANIENT'],
        country: 'IN'
    },
    'LARSEN & TOUBRO': {
        name: 'Larsen & Toubro Ltd',
        officialWebsite: 'https://www.larsentoubro.com',
        investorRelationsPage: 'https://www.larsentoubro.com/investors/investor-essentials/annual-reports/',
        annualReportsPage: 'https://www.larsentoubro.com/investors/investor-essentials/annual-reports/',
        aliases: ['L&T', 'LT'],
        country: 'IN'
    },
    'ITC': {
        name: 'ITC Ltd',
        officialWebsite: 'https://www.itcportal.com',
        investorRelationsPage: 'https://www.itcportal.com/about-itc/shareholder-value/annual-reports.aspx',
        annualReportsPage: 'https://www.itcportal.com/about-itc/shareholder-value/annual-reports.aspx',
        aliases: [],
        country: 'IN'
    },
    'BHARTI AIRTEL': {
        name: 'Bharti Airtel Ltd',
        officialWebsite: 'https://www.airtel.in',
        investorRelationsPage: 'https://www.airtel.in/about-bharti/equity/annual-reports',
        annualReportsPage: 'https://www.airtel.in/about-bharti/equity/annual-reports',
        aliases: ['AIRTEL', 'BHARTIARTL'],
        country: 'IN'
    },

    // ==================== US TECH COMPANIES ====================
    'APPLE': {
        name: 'Apple Inc.',
        officialWebsite: 'https://www.apple.com',
        investorRelationsPage: 'https://investor.apple.com/',
        annualReportsPage: 'https://investor.apple.com/sec-filings/default.aspx',
        quarterlyReportsPage: 'https://investor.apple.com/sec-filings/default.aspx',
        aliases: ['AAPL', 'APPLE INC'],
        country: 'US'
    },
    'MICROSOFT': {
        name: 'Microsoft Corporation',
        officialWebsite: 'https://www.microsoft.com',
        investorRelationsPage: 'https://www.microsoft.com/en-us/Investor',
        annualReportsPage: 'https://www.microsoft.com/en-us/Investor/annual-reports.aspx',
        aliases: ['MSFT', 'MICROSOFT CORP'],
        country: 'US'
    },
    'GOOGLE': {
        name: 'Alphabet Inc.',
        officialWebsite: 'https://abc.xyz',
        investorRelationsPage: 'https://abc.xyz/investor/',
        annualReportsPage: 'https://abc.xyz/investor/',
        aliases: ['ALPHABET', 'GOOGL', 'GOOG'],
        country: 'US'
    },
    'AMAZON': {
        name: 'Amazon.com, Inc.',
        officialWebsite: 'https://www.amazon.com',
        investorRelationsPage: 'https://ir.aboutamazon.com/',
        annualReportsPage: 'https://ir.aboutamazon.com/annual-reports-proxies-and-shareholder-letters/default.aspx',
        aliases: ['AMZN', 'AMAZON.COM'],
        country: 'US'
    },
    'META': {
        name: 'Meta Platforms, Inc.',
        officialWebsite: 'https://about.meta.com',
        investorRelationsPage: 'https://investor.fb.com/',
        annualReportsPage: 'https://investor.fb.com/financials/default.aspx',
        aliases: ['FACEBOOK', 'FB', 'META PLATFORMS'],
        country: 'US'
    },
    'NVIDIA': {
        name: 'NVIDIA Corporation',
        officialWebsite: 'https://www.nvidia.com',
        investorRelationsPage: 'https://investor.nvidia.com/',
        annualReportsPage: 'https://investor.nvidia.com/financial-info/annual-reports/default.aspx',
        aliases: ['NVDA'],
        country: 'US'
    },
    'TESLA': {
        name: 'Tesla, Inc.',
        officialWebsite: 'https://www.tesla.com',
        investorRelationsPage: 'https://ir.tesla.com/',
        annualReportsPage: 'https://ir.tesla.com/#quarterly-disclosure',
        aliases: ['TSLA'],
        country: 'US'
    },

    // ==================== INTERNATIONAL ====================
    'SAUDI ARAMCO': {
        name: 'Saudi Arabian Oil Company (Aramco)',
        officialWebsite: 'https://www.aramco.com',
        investorRelationsPage: 'https://www.aramco.com/en/investors',
        annualReportsPage: 'https://www.aramco.com/en/investors/reports-presentations/annual-report',
        aliases: ['ARAMCO', '2222.SR'],
        country: 'SA'
    },
    'SHELL': {
        name: 'Shell plc',
        officialWebsite: 'https://www.shell.com',
        investorRelationsPage: 'https://www.shell.com/investors.html',
        annualReportsPage: 'https://www.shell.com/investors/financial-reporting/annual-publications.html',
        aliases: ['ROYAL DUTCH SHELL', 'SHEL'],
        country: 'GB'
    },
    'NESTLE': {
        name: 'Nestlé S.A.',
        officialWebsite: 'https://www.nestle.com',
        investorRelationsPage: 'https://www.nestle.com/investors',
        annualReportsPage: 'https://www.nestle.com/investors/annual-report',
        aliases: ['NESN'],
        country: 'CH'
    },
};

// Build lookup map for fast searching
const COMPANY_LOOKUP: Map<string, string> = new Map();
for (const [key, data] of Object.entries(COMPANY_OFFICIAL_WEBSITES)) {
    COMPANY_LOOKUP.set(key.toUpperCase(), key);
    COMPANY_LOOKUP.set(data.name.toUpperCase(), key);
    for (const alias of data.aliases) {
        COMPANY_LOOKUP.set(alias.toUpperCase(), key);
    }
}

/**
 * Find company in our database
 */
export function findCompanyInDatabase(searchTerm: string): typeof COMPANY_OFFICIAL_WEBSITES[string] | null {
    const normalized = searchTerm.toUpperCase().trim();

    // Direct match
    const directKey = COMPANY_LOOKUP.get(normalized);
    if (directKey) {
        return COMPANY_OFFICIAL_WEBSITES[directKey];
    }

    // Partial match
    for (const [key, masterKey] of COMPANY_LOOKUP.entries()) {
        if (key.includes(normalized) || normalized.includes(key)) {
            return COMPANY_OFFICIAL_WEBSITES[masterKey];
        }
    }

    // Word-based match
    const searchWords = normalized.split(/\s+/).filter(w => w.length > 2);
    for (const [key, masterKey] of COMPANY_LOOKUP.entries()) {
        const keyWords = key.split(/\s+/);
        const matchCount = searchWords.filter(sw => keyWords.some(kw => kw.includes(sw) || sw.includes(kw))).length;
        if (matchCount >= 2 || (matchCount >= 1 && searchWords.length === 1)) {
            return COMPANY_OFFICIAL_WEBSITES[masterKey];
        }
    }

    return null;
}

/**
 * Validate if a URL is accessible
 */
export async function validateUrl(url: string): Promise<{ valid: boolean; status?: number; error?: string }> {
    try {
        const response = await axios.head(url, {
            timeout: 10000,
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
            maxRedirects: 5,
            validateStatus: (status) => status < 500,
        });

        if (response.status === 200 || response.status === 301 || response.status === 302) {
            return { valid: true, status: response.status };
        }

        return { valid: false, status: response.status, error: `HTTP ${response.status}` };
    } catch (error) {
        return { valid: false, error: error instanceof Error ? error.message : 'Unknown error' };
    }
}

/**
 * Search for company reports from OFFICIAL WEBSITE ONLY
 */
export async function searchOfficialWebsite(
    companyName: string,
    documentType: 'annual' | 'quarterly' | 'financial',
    year?: number
): Promise<{
    success: boolean;
    company?: string;
    officialWebsite?: string;
    reportsPage?: string;
    results: SearchResult[];
    notes: string;
}> {
    // Step 1: Find company in our database
    const company = findCompanyInDatabase(companyName);

    if (!company) {
        return {
            success: false,
            results: [],
            notes: `Company "${companyName}" not found in our database. We only return reports from official company websites. Please check the company name or contact support to add this company.`
        };
    }

    // Step 2: Determine the correct reports page
    const reportsPage = documentType === 'quarterly' && company.quarterlyReportsPage
        ? company.quarterlyReportsPage
        : company.annualReportsPage;

    // Step 3: Validate the reports page is accessible
    const pageValidation = await validateUrl(reportsPage);

    const result: SearchResult = {
        url: reportsPage,
        title: `${company.name} - ${documentType === 'annual' ? 'Annual Reports' : 'Quarterly Reports'}${year ? ` (${year})` : ''}`,
        company: company.name,
        documentType: documentType,
        filingDate: year ? `${year}` : undefined,
        fiscalYear: year,
        confidence: pageValidation.valid ? 0.95 : 0.5,
        source: 'company-website',
        market: company.country,
        linkVerified: pageValidation.valid,
        officialReportsPage: reportsPage,
    };

    return {
        success: true,
        company: company.name,
        officialWebsite: company.officialWebsite,
        reportsPage: reportsPage,
        results: [result],
        notes: pageValidation.valid
            ? `Found official reports page for ${company.name}. Please visit the page to download the specific ${year ? year + ' ' : ''}${documentType} report.`
            : `Official reports page found but may be temporarily unavailable (${pageValidation.error}). Try visiting the investor relations page directly.`
    };
}

/**
 * Get all supported companies
 */
export function getSupportedCompanies(): string[] {
    return Object.values(COMPANY_OFFICIAL_WEBSITES).map(c => c.name);
}

export { COMPANY_OFFICIAL_WEBSITES };
