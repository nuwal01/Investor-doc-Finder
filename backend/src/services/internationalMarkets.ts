import { SearchResult } from '../types';

// Supported markets configuration
export interface MarketConfig {
    name: string;
    country: string;
    countryCode: string;
    exchange?: string;
    regulatorUrl?: string;
    investorRelationsPattern?: string;
    supported: 'full' | 'partial' | 'limited';
    notes?: string;
}

export const SUPPORTED_MARKETS: Record<string, MarketConfig> = {
    // Full support - API integration
    'US': {
        name: 'United States',
        country: 'United States',
        countryCode: 'US',
        exchange: 'NYSE/NASDAQ',
        regulatorUrl: 'https://www.sec.gov/cgi-bin/browse-edgar',
        supported: 'full',
        notes: 'Full SEC EDGAR integration'
    },
    'IN': {
        name: 'India',
        country: 'India',
        countryCode: 'IN',
        exchange: 'BSE/NSE',
        regulatorUrl: 'https://www.sebi.gov.in/',
        supported: 'full',
        notes: 'BSE and NSE integration'
    },

    // Partial support - Known company IR links
    'GB': {
        name: 'United Kingdom',
        country: 'United Kingdom',
        countryCode: 'GB',
        exchange: 'LSE',
        regulatorUrl: 'https://find-and-update.company-information.service.gov.uk/',
        supported: 'partial',
        notes: 'Companies House and LSE filings'
    },
    'CN': {
        name: 'China',
        country: 'China',
        countryCode: 'CN',
        exchange: 'SSE/SZSE',
        supported: 'partial',
        notes: 'Limited English content'
    },
    'SG': {
        name: 'Singapore',
        country: 'Singapore',
        countryCode: 'SG',
        exchange: 'SGX',
        regulatorUrl: 'https://www.sgx.com/securities/company-announcements',
        supported: 'partial'
    },
    'AE': {
        name: 'United Arab Emirates',
        country: 'United Arab Emirates',
        countryCode: 'AE',
        exchange: 'DFM/ADX',
        supported: 'partial'
    },
    'SA': {
        name: 'Saudi Arabia',
        country: 'Saudi Arabia',
        countryCode: 'SA',
        exchange: 'Tadawul',
        regulatorUrl: 'https://www.tadawul.com.sa/',
        supported: 'partial'
    },
    'BR': {
        name: 'Brazil',
        country: 'Brazil',
        countryCode: 'BR',
        exchange: 'B3',
        regulatorUrl: 'https://www.b3.com.br/',
        supported: 'partial'
    },
    'CA': {
        name: 'Canada',
        country: 'Canada',
        countryCode: 'CA',
        exchange: 'TSX',
        regulatorUrl: 'https://www.sedar.com/',
        supported: 'partial',
        notes: 'SEDAR filings'
    },
    'MX': {
        name: 'Mexico',
        country: 'Mexico',
        countryCode: 'MX',
        exchange: 'BMV',
        supported: 'partial'
    },

    // Limited support - IR website search only
    'AR': { name: 'Argentina', country: 'Argentina', countryCode: 'AR', supported: 'limited' },
    'AZ': { name: 'Azerbaijan', country: 'Azerbaijan', countryCode: 'AZ', supported: 'limited' },
    'BH': { name: 'Bahrain', country: 'Bahrain', countryCode: 'BH', supported: 'limited' },
    'BE': { name: 'Belgium', country: 'Belgium', countryCode: 'BE', supported: 'limited' },
    'KY': { name: 'Cayman Islands', country: 'Cayman Islands', countryCode: 'KY', supported: 'limited' },
    'CL': { name: 'Chile', country: 'Chile', countryCode: 'CL', supported: 'limited' },
    'CO': { name: 'Colombia', country: 'Colombia', countryCode: 'CO', supported: 'limited' },
    'CY': { name: 'Cyprus', country: 'Cyprus', countryCode: 'CY', supported: 'limited' },
    'EG': { name: 'Egypt', country: 'Egypt', countryCode: 'EG', supported: 'limited' },
    'ID': { name: 'Indonesia', country: 'Indonesia', countryCode: 'ID', supported: 'limited' },
    'KZ': { name: 'Kazakhstan', country: 'Kazakhstan', countryCode: 'KZ', supported: 'limited' },
    'KW': { name: 'Kuwait', country: 'Kuwait', countryCode: 'KW', supported: 'limited' },
    'LT': { name: 'Lithuania', country: 'Lithuania', countryCode: 'LT', supported: 'limited' },
    'LU': { name: 'Luxembourg', country: 'Luxembourg', countryCode: 'LU', supported: 'limited' },
    'MU': { name: 'Mauritius', country: 'Mauritius', countryCode: 'MU', supported: 'limited' },
    'NL': { name: 'Netherlands', country: 'Netherlands', countryCode: 'NL', supported: 'limited' },
    'NG': { name: 'Nigeria', country: 'Nigeria', countryCode: 'NG', supported: 'limited' },
    'NO': { name: 'Norway', country: 'Norway', countryCode: 'NO', supported: 'limited' },
    'OM': { name: 'Oman', country: 'Oman', countryCode: 'OM', supported: 'limited' },
    'QA': { name: 'Qatar', country: 'Qatar', countryCode: 'QA', supported: 'limited' },
    'RU': { name: 'Russia', country: 'Russia', countryCode: 'RU', supported: 'limited' },
    'ZA': { name: 'South Africa', country: 'South Africa', countryCode: 'ZA', supported: 'limited' },
    'CH': { name: 'Switzerland', country: 'Switzerland', countryCode: 'CH', supported: 'limited' },
    'TR': { name: 'Turkey', country: 'Turkey', countryCode: 'TR', supported: 'limited' },
    'UA': { name: 'Ukraine', country: 'Ukraine', countryCode: 'UA', supported: 'limited' },
    'UZ': { name: 'Uzbekistan', country: 'Uzbekistan', countryCode: 'UZ', supported: 'limited' },

    // Multilateral organizations
    'TDB': { name: 'Trade and Development Bank', country: 'Multilateral', countryCode: 'TDB', supported: 'limited' },
    'AFREXIM': { name: 'Afreximbank', country: 'Multilateral', countryCode: 'AFREXIM', supported: 'limited' },
};

// Major international companies with known investor relations URLs
export const INTERNATIONAL_COMPANIES: Record<string, { name: string; country: string; irUrl: string; ticker?: string }> = {
    // UK Companies
    'SHELL': { name: 'Shell plc', country: 'GB', irUrl: 'https://www.shell.com/investors.html', ticker: 'SHEL' },
    'BP': { name: 'BP plc', country: 'GB', irUrl: 'https://www.bp.com/en/global/corporate/investors.html', ticker: 'BP' },
    'HSBC': { name: 'HSBC Holdings plc', country: 'GB', irUrl: 'https://www.hsbc.com/investors', ticker: 'HSBA' },
    'UNILEVER': { name: 'Unilever plc', country: 'GB', irUrl: 'https://www.unilever.com/investors/', ticker: 'ULVR' },
    'ASTRAZENECA': { name: 'AstraZeneca plc', country: 'GB', irUrl: 'https://www.astrazeneca.com/investor-relations.html', ticker: 'AZN' },
    'GLAXOSMITHKLINE': { name: 'GSK plc', country: 'GB', irUrl: 'https://www.gsk.com/en-gb/investors/', ticker: 'GSK' },
    'BARCLAYS': { name: 'Barclays plc', country: 'GB', irUrl: 'https://home.barclays/investor-relations/', ticker: 'BARC' },
    'RIO TINTO': { name: 'Rio Tinto plc', country: 'GB', irUrl: 'https://www.riotinto.com/en/investors', ticker: 'RIO' },
    'VODAFONE': { name: 'Vodafone Group plc', country: 'GB', irUrl: 'https://investors.vodafone.com/', ticker: 'VOD' },

    // China Companies
    'ALIBABA': { name: 'Alibaba Group', country: 'CN', irUrl: 'https://www.alibabagroup.com/en-US/investor-relations', ticker: 'BABA' },
    'TENCENT': { name: 'Tencent Holdings', country: 'CN', irUrl: 'https://www.tencent.com/en-us/investors.html', ticker: '0700' },
    'JD': { name: 'JD.com', country: 'CN', irUrl: 'https://ir.jd.com/', ticker: 'JD' },
    'BAIDU': { name: 'Baidu Inc', country: 'CN', irUrl: 'https://ir.baidu.com/', ticker: 'BIDU' },
    'XIAOMI': { name: 'Xiaomi Corporation', country: 'CN', irUrl: 'https://ir.mi.com/investor-relations', ticker: '1810' },
    'NIO': { name: 'NIO Inc', country: 'CN', irUrl: 'https://ir.nio.com/', ticker: 'NIO' },
    'BYDCOMPANY': { name: 'BYD Company', country: 'CN', irUrl: 'https://www.byd.com/en/InvestorRelations', ticker: '1211' },
    'PINDUODUO': { name: 'PDD Holdings', country: 'CN', irUrl: 'https://investor.pddholdings.com/', ticker: 'PDD' },

    // Singapore Companies
    'DBS': { name: 'DBS Group', country: 'SG', irUrl: 'https://www.dbs.com/investor/index.html', ticker: 'D05' },
    'SINGTEL': { name: 'Singapore Telecommunications', country: 'SG', irUrl: 'https://www.singtel.com/about-us/investor-relations', ticker: 'Z74' },
    'OCBC': { name: 'OCBC Bank', country: 'SG', irUrl: 'https://www.ocbc.com/group/investors.page', ticker: 'O39' },
    'UOB': { name: 'United Overseas Bank', country: 'SG', irUrl: 'https://www.uobgroup.com/investor-relations/', ticker: 'U11' },

    // Saudi Arabia Companies
    'ARAMCO': { name: 'Saudi Aramco', country: 'SA', irUrl: 'https://www.aramco.com/en/investors', ticker: '2222' },
    'SABIC': { name: 'SABIC', country: 'SA', irUrl: 'https://www.sabic.com/en/investors', ticker: '2010' },
    'STC': { name: 'Saudi Telecom Company', country: 'SA', irUrl: 'https://www.stc.com.sa/content/stc/en/investors.html', ticker: '7010' },
    'ALRAJHI': { name: 'Al Rajhi Bank', country: 'SA', irUrl: 'https://www.alrajhibank.com.sa/en/investor-relations', ticker: '1120' },

    // UAE Companies
    'ETISALAT': { name: 'Emirates Telecommunications', country: 'AE', irUrl: 'https://www.etisalat.ae/en/ir.html', ticker: 'ETISALAT' },
    'EMAAR': { name: 'Emaar Properties', country: 'AE', irUrl: 'https://www.emaar.com/en/investor-relations', ticker: 'EMAAR' },
    'EMIRATES NBD': { name: 'Emirates NBD', country: 'AE', irUrl: 'https://www.emiratesnbd.com/en/investor-relations/', ticker: 'EMIRATESNBD' },

    // Brazil Companies
    'PETROBRAS': { name: 'Petrobras', country: 'BR', irUrl: 'https://www.investidorpetrobras.com.br/en/', ticker: 'PBR' },
    'VALE': { name: 'Vale S.A.', country: 'BR', irUrl: 'https://www.vale.com/investors', ticker: 'VALE' },
    'ITAU': { name: 'Itaú Unibanco', country: 'BR', irUrl: 'https://www.itau.com.br/relacoes-com-investidores/', ticker: 'ITUB' },
    'AMBEV': { name: 'Ambev S.A.', country: 'BR', irUrl: 'https://ri.ambev.com.br/en/', ticker: 'ABEV' },
    'NUBANK': { name: 'Nu Holdings', country: 'BR', irUrl: 'https://international.nubank.com.br/investors/', ticker: 'NU' },

    // Canada Companies
    'RBC': { name: 'Royal Bank of Canada', country: 'CA', irUrl: 'https://www.rbc.com/investor-relations/', ticker: 'RY' },
    'TD BANK': { name: 'Toronto-Dominion Bank', country: 'CA', irUrl: 'https://www.td.com/investor-relations/', ticker: 'TD' },
    'SHOPIFY': { name: 'Shopify Inc', country: 'CA', irUrl: 'https://investors.shopify.com/', ticker: 'SHOP' },
    'ENBRIDGE': { name: 'Enbridge Inc', country: 'CA', irUrl: 'https://www.enbridge.com/investment-center', ticker: 'ENB' },
    'SUNCOR': { name: 'Suncor Energy', country: 'CA', irUrl: 'https://www.suncor.com/en-ca/investors', ticker: 'SU' },

    // Switzerland Companies
    'NESTLE': { name: 'Nestlé S.A.', country: 'CH', irUrl: 'https://www.nestle.com/investors', ticker: 'NESN' },
    'NOVARTIS': { name: 'Novartis AG', country: 'CH', irUrl: 'https://www.novartis.com/investors', ticker: 'NVS' },
    'ROCHE': { name: 'Roche Holding AG', country: 'CH', irUrl: 'https://www.roche.com/investors/', ticker: 'ROG' },
    'UBS': { name: 'UBS Group AG', country: 'CH', irUrl: 'https://www.ubs.com/global/en/investor-relations.html', ticker: 'UBS' },
    'CREDIT SUISSE': { name: 'Credit Suisse', country: 'CH', irUrl: 'https://www.credit-suisse.com/about-us/en/investor-relations.html', ticker: 'CS' },

    // Netherlands Companies
    'ASML': { name: 'ASML Holding', country: 'NL', irUrl: 'https://www.asml.com/en/investors', ticker: 'ASML' },
    'PHILIPS': { name: 'Koninklijke Philips', country: 'NL', irUrl: 'https://www.philips.com/a-w/about/investor-relations.html', ticker: 'PHG' },
    'ING': { name: 'ING Group', country: 'NL', irUrl: 'https://www.ing.com/Investor-relations.htm', ticker: 'ING' },

    // South Africa Companies
    'NASPERS': { name: 'Naspers Limited', country: 'ZA', irUrl: 'https://www.naspers.com/investors', ticker: 'NPN' },
    'MTN': { name: 'MTN Group', country: 'ZA', irUrl: 'https://www.mtn.com/investors/', ticker: 'MTN' },
    'SASOL': { name: 'Sasol Limited', country: 'ZA', irUrl: 'https://www.sasol.com/investor-centre', ticker: 'SSL' },

    // Multilateral Organizations
    'TDB': { name: 'Trade and Development Bank', country: 'TDB', irUrl: 'https://www.tdbgroup.org/investor-relations/', ticker: 'TDB' },
    'AFREXIMBANK': { name: 'African Export-Import Bank', country: 'AFREXIM', irUrl: 'https://www.afreximbank.com/investor-relations/', ticker: 'AFREXIM' },
};

/**
 * Find international company by name
 */
export function findInternationalCompany(companyName: string): { key: string; data: typeof INTERNATIONAL_COMPANIES[string] } | null {
    const searchName = companyName.toUpperCase().replace(/[^A-Z0-9\s]/g, '').trim();

    // Direct match
    if (INTERNATIONAL_COMPANIES[searchName]) {
        return { key: searchName, data: INTERNATIONAL_COMPANIES[searchName] };
    }

    // Partial match
    for (const [key, data] of Object.entries(INTERNATIONAL_COMPANIES)) {
        const normalizedKey = key.replace(/[^A-Z0-9\s]/g, '');
        const normalizedName = data.name.toUpperCase().replace(/[^A-Z0-9\s]/g, '');

        if (normalizedKey.includes(searchName) || searchName.includes(normalizedKey) ||
            normalizedName.includes(searchName) || searchName.includes(normalizedName.split(' ')[0])) {
            return { key, data };
        }
    }

    return null;
}

/**
 * Search for international company documents
 */
export async function searchInternationalCompany(
    companyName: string,
    documentType: string,
    year?: number
): Promise<SearchResult[]> {
    const results: SearchResult[] = [];

    const match = findInternationalCompany(companyName);
    if (!match) {
        return results;
    }

    const { data } = match;

    // Add investor relations page
    results.push({
        url: data.irUrl,
        title: `${data.name} - Investor Relations`,
        company: data.name,
        ticker: data.ticker,
        documentType: documentType || 'annual',
        filingDate: year ? `${year}` : undefined,
        confidence: 0.9,
        source: 'company-website',
        fileFormat: 'HTML'
    });

    // Add annual report link (estimated pattern)
    if (documentType === 'annual' || !documentType) {
        const annualReportUrl = data.irUrl.includes('?')
            ? `${data.irUrl}&section=annual-reports`
            : `${data.irUrl}#annual-reports`;

        results.push({
            url: annualReportUrl,
            title: `${data.name} - Annual Reports`,
            company: data.name,
            ticker: data.ticker,
            documentType: 'annual',
            filingDate: year ? `${year}` : undefined,
            confidence: 0.85,
            source: 'company-website',
            fileFormat: 'PDF'
        });
    }

    return results;
}

/**
 * Get market info for a country
 */
export function getMarketInfo(countryCode: string): MarketConfig | undefined {
    return SUPPORTED_MARKETS[countryCode.toUpperCase()];
}

/**
 * Get list of all supported countries
 */
export function getSupportedCountries(): string[] {
    return Object.values(SUPPORTED_MARKETS).map(m => m.country);
}
