/**
 * S&P 500 Company Data
 * Used for autocomplete suggestions and validation
 * This is a subset of the top 100 S&P 500 companies by market cap
 */

export interface Company {
    name: string;
    ticker: string;
    cik?: string;
}

export const SP500_COMPANIES: Company[] = [
    // Technology
    { name: 'Apple', ticker: 'AAPL', cik: '0000320193' },
    { name: 'Microsoft', ticker: 'MSFT', cik: '0000789019' },
    { name: 'Alphabet', ticker: 'GOOGL', cik: '0001652044' },
    { name: 'Google', ticker: 'GOOG', cik: '0001652044' },
    { name: 'Amazon', ticker: 'AMZN', cik: '0001018724' },
    { name: 'NVIDIA', ticker: 'NVDA', cik: '0001045810' },
    { name: 'Meta Platforms', ticker: 'META', cik: '0001326801' },
    { name: 'Meta', ticker: 'META', cik: '0001326801' },
    { name: 'Tesla', ticker: 'TSLA', cik: '0001318605' },
    { name: 'Broadcom', ticker: 'AVGO', cik: '0001730168' },
    { name: 'Oracle', ticker: 'ORCL', cik: '0001341439' },
    { name: 'Salesforce', ticker: 'CRM', cik: '0001108524' },
    { name: 'Adobe', ticker: 'ADBE', cik: '0000796343' },
    { name: 'Cisco', ticker: 'CSCO', cik: '0000858877' },
    { name: 'Accenture', ticker: 'ACN', cik: '0001467373' },
    { name: 'IBM', ticker: 'IBM', cik: '0000051143' },
    { name: 'Intel', ticker: 'INTC', cik: '0000050863' },
    { name: 'AMD', ticker: 'AMD', cik: '0000002488' },
    { name: 'Qualcomm', ticker: 'QCOM', cik: '0000804328' },
    { name: 'Texas Instruments', ticker: 'TXN', cik: '0000097476' },
    { name: 'Applied Materials', ticker: 'AMAT', cik: '0000006951' },
    { name: 'Intuit', ticker: 'INTU', cik: '0000896878' },
    { name: 'ServiceNow', ticker: 'NOW', cik: '0001373715' },
    { name: 'Micron Technology', ticker: 'MU', cik: '0000723125' },
    { name: 'Lam Research', ticker: 'LRCX', cik: '0000707549' },
    { name: 'Palo Alto Networks', ticker: 'PANW', cik: '0001327567' },
    { name: 'Synopsys', ticker: 'SNPS', cik: '0000883241' },
    { name: 'Cadence Design Systems', ticker: 'CDNS', cik: '0000813672' },
    { name: 'Autodesk', ticker: 'ADSK', cik: '0000769397' },
    { name: 'Arista Networks', ticker: 'ANET', cik: '0001547282' },

    // Financial Services
    { name: 'Berkshire Hathaway', ticker: 'BRK.B', cik: '0001067983' },
    { name: 'JPMorgan Chase', ticker: 'JPM', cik: '0000019617' },
    { name: 'JPMorgan', ticker: 'JPM', cik: '0000019617' },
    { name: 'Visa', ticker: 'V', cik: '0001403161' },
    { name: 'Mastercard', ticker: 'MA', cik: '0001141391' },
    { name: 'Bank of America', ticker: 'BAC', cik: '0000070858' },
    { name: 'Wells Fargo', ticker: 'WFC', cik: '0000072971' },
    { name: 'Morgan Stanley', ticker: 'MS', cik: '0000895421' },
    { name: 'Goldman Sachs', ticker: 'GS', cik: '0000886982' },
    { name: 'Charles Schwab', ticker: 'SCHW', cik: '0000316709' },
    { name: 'BlackRock', ticker: 'BLK', cik: '0001364742' },
    { name: 'American Express', ticker: 'AXP', cik: '0000004962' },
    { name: 'Citigroup', ticker: 'C', cik: '0000831001' },
    { name: 'S&P Global', ticker: 'SPGI', cik: '0000064040' },
    { name: 'CME Group', ticker: 'CME', cik: '0001156375' },
    { name: 'PayPal', ticker: 'PYPL', cik: '0001633917' },
    { name: 'Intercontinental Exchange', ticker: 'ICE', cik: '0001571949' },
    { name: 'Progressive', ticker: 'PGR', cik: '0000080661' },
    { name: 'Marsh McLennan', ticker: 'MMC', cik: '0000062996' },
    { name: 'Aon', ticker: 'AON', cik: '0000000315' },

    // Healthcare
    { name: 'UnitedHealth Group', ticker: 'UNH', cik: '0000731766' },
    { name: 'UnitedHealth', ticker: 'UNH', cik: '0000731766' },
    { name: 'Eli Lilly', ticker: 'LLY', cik: '0000059478' },
    { name: 'Johnson & Johnson', ticker: 'JNJ', cik: '0000200406' },
    { name: 'Merck', ticker: 'MRK', cik: '0000310158' },
    { name: 'AbbVie', ticker: 'ABBV', cik: '0001551152' },
    { name: 'Pfizer', ticker: 'PFE', cik: '0000078003' },
    { name: 'Thermo Fisher Scientific', ticker: 'TMO', cik: '0000097745' },
    { name: 'Abbott Laboratories', ticker: 'ABT', cik: '0000001800' },
    { name: 'Danaher', ticker: 'DHR', cik: '0000313616' },
    { name: 'Amgen', ticker: 'AMGN', cik: '0000318154' },
    { name: 'Bristol-Myers Squibb', ticker: 'BMY', cik: '0000014272' },
    { name: 'Cigna', ticker: 'CI', cik: '0001739940' },
    { name: 'CVS Health', ticker: 'CVS', cik: '0000064803' },
    { name: 'Gilead Sciences', ticker: 'GILD', cik: '0000882095' },
    { name: 'Intuitive Surgical', ticker: 'ISRG', cik: '0001035267' },
    { name: 'Vertex Pharmaceuticals', ticker: 'VRTX', cik: '0000875320' },
    { name: 'Regeneron Pharmaceuticals', ticker: 'REGN', cik: '0000872589' },
    { name: 'Elevance Health', ticker: 'ELV', cik: '0001156039' },
    { name: 'Boston Scientific', ticker: 'BSX', cik: '0000885725' },
    { name: 'Stryker', ticker: 'SYK', cik: '0000310764' },

    // Consumer
    { name: 'Walmart', ticker: 'WMT', cik: '0000104169' },
    { name: 'Costco', ticker: 'COST', cik: '0000909832' },
    { name: 'Procter & Gamble', ticker: 'PG', cik: '0000080424' },
    { name: 'Coca-Cola', ticker: 'KO', cik: '0000021344' },
    { name: 'PepsiCo', ticker: 'PEP', cik: '0000077476' },
    { name: 'Home Depot', ticker: 'HD', cik: '0000354950' },
    { name: 'Nike', ticker: 'NKE', cik: '0000320187' },
    { name: 'McDonald\'s', ticker: 'MCD', cik: '0000063908' },
    { name: 'Starbucks', ticker: 'SBUX', cik: '0000829224' },
    { name: 'Target', ticker: 'TGT', cik: '0000027419' },
    { name: 'Lowe\'s', ticker: 'LOW', cik: '0000060667' },
    { name: 'TJX Companies', ticker: 'TJX', cik: '0000109198' },
    { name: 'Booking Holdings', ticker: 'BKNG', cik: '0001075531' },
    { name: 'Mondelez International', ticker: 'MDLZ', cik: '0001103982' },
    { name: 'Colgate-Palmolive', ticker: 'CL', cik: '0000021665' },
    { name: 'Philip Morris International', ticker: 'PM', cik: '0001413329' },
    { name: 'Altria Group', ticker: 'MO', cik: '0000764180' },
    { name: 'Estee Lauder', ticker: 'EL', cik: '0001001250' },
    { name: 'Kimberly-Clark', ticker: 'KMB', cik: '0000055785' },
    { name: 'General Mills', ticker: 'GIS', cik: '0000040704' },

    // Communication Services
    { name: 'Netflix', ticker: 'NFLX', cik: '0001065280' },
    { name: 'Walt Disney', ticker: 'DIS', cik: '0001744489' },
    { name: 'Disney', ticker: 'DIS', cik: '0001744489' },
    { name: 'Comcast', ticker: 'CMCSA', cik: '0001166691' },
    { name: 'Verizon', ticker: 'VZ', cik: '0000732712' },
    { name: 'AT&T', ticker: 'T', cik: '0000732717' },
    { name: 'T-Mobile US', ticker: 'TMUS', cik: '0001283699' },
    { name: 'Charter Communications', ticker: 'CHTR', cik: '0001271462' },
    { name: 'Activision Blizzard', ticker: 'ATVI', cik: '0000718877' },
    { name: 'Electronic Arts', ticker: 'EA', cik: '0000712515' },
    { name: 'Take-Two Interactive', ticker: 'TTWO', cik: '0000946581' },
    { name: 'Warner Bros Discovery', ticker: 'WBD', cik: '0001437107' },

    // Energy
    { name: 'Exxon Mobil', ticker: 'XOM', cik: '0000034088' },
    { name: 'ExxonMobil', ticker: 'XOM', cik: '0000034088' },
    { name: 'Chevron', ticker: 'CVX', cik: '0000093410' },
    { name: 'ConocoPhillips', ticker: 'COP', cik: '0001163165' },
    { name: 'EOG Resources', ticker: 'EOG', cik: '0000821189' },
    { name: 'Schlumberger', ticker: 'SLB', cik: '0000087347' },
    { name: 'Phillips 66', ticker: 'PSX', cik: '0001534701' },
    { name: 'Marathon Petroleum', ticker: 'MPC', cik: '0001510295' },
    { name: 'Valero Energy', ticker: 'VLO', cik: '0001035002' },
    { name: 'Pioneer Natural Resources', ticker: 'PXD', cik: '0001038357' },
    { name: 'Occidental Petroleum', ticker: 'OXY', cik: '0000797468' },
    { name: 'Devon Energy', ticker: 'DVN', cik: '0001090012' },
    { name: 'Hess', ticker: 'HES', cik: '0000004447' },
    { name: 'Kinder Morgan', ticker: 'KMI', cik: '0001506307' },
    { name: 'Williams Companies', ticker: 'WMB', cik: '0000107263' },
    { name: 'Baker Hughes', ticker: 'BKR', cik: '0001701605' },

    // Industrials
    { name: 'General Electric', ticker: 'GE', cik: '0000040545' },
    { name: 'Caterpillar', ticker: 'CAT', cik: '0000018230' },
    { name: 'Boeing', ticker: 'BA', cik: '0000012927' },
    { name: 'Raytheon Technologies', ticker: 'RTX', cik: '0000101829' },
    { name: 'RTX', ticker: 'RTX', cik: '0000101829' },
    { name: 'Union Pacific', ticker: 'UNP', cik: '0000100885' },
    { name: 'Honeywell', ticker: 'HON', cik: '0000773840' },
    { name: 'United Parcel Service', ticker: 'UPS', cik: '0001090727' },
    { name: 'UPS', ticker: 'UPS', cik: '0001090727' },
    { name: 'Lockheed Martin', ticker: 'LMT', cik: '0000936468' },
    { name: 'Deere & Company', ticker: 'DE', cik: '0000315189' },
    { name: 'Northrop Grumman', ticker: 'NOC', cik: '0001133421' },
    { name: '3M', ticker: 'MMM', cik: '0000066740' },
    { name: 'General Dynamics', ticker: 'GD', cik: '0000040533' },
    { name: 'Illinois Tool Works', ticker: 'ITW', cik: '0000049826' },
    { name: 'FedEx', ticker: 'FDX', cik: '0001048911' },
    { name: 'Parker Hannifin', ticker: 'PH', cik: '0000076334' },
    { name: 'PACCAR', ticker: 'PCAR', cik: '0000075362' },
    { name: 'Eaton', ticker: 'ETN', cik: '0001551182' },
    { name: 'Emerson Electric', ticker: 'EMR', cik: '0000032604' },

    // Utilities & Real Estate
    { name: 'NextEra Energy', ticker: 'NEE', cik: '0000753308' },
    { name: 'Southern Company', ticker: 'SO', cik: '0000092122' },
    { name: 'Duke Energy', ticker: 'DUK', cik: '0001326160' },
    { name: 'Dominion Energy', ticker: 'D', cik: '0000715957' },
    { name: 'American Electric Power', ticker: 'AEP', cik: '0000004904' },
    { name: 'Exelon', ticker: 'EXC', cik: '0001109357' },
    { name: 'Sempra', ticker: 'SRE', cik: '0001032208' },
    { name: 'Xcel Energy', ticker: 'XEL', cik: '0000072903' },
    { name: 'Public Service Enterprise', ticker: 'PEG', cik: '0000788784' },
    { name: 'WEC Energy Group', ticker: 'WEC', cik: '0000783325' },
    { name: 'American Tower', ticker: 'AMT', cik: '0001053507' },
    { name: 'Prologis', ticker: 'PLD', cik: '0001045609' },
    { name: 'Crown Castle', ticker: 'CCI', cik: '0001051470' },
    { name: 'Equinix', ticker: 'EQIX', cik: '0001101239' },
    { name: 'Public Storage', ticker: 'PSA', cik: '0001393311' },
    { name: 'Digital Realty Trust', ticker: 'DLR', cik: '0001297996' },

    // Materials
    { name: 'Linde', ticker: 'LIN', cik: '0001707925' },
    { name: 'Sherwin-Williams', ticker: 'SHW', cik: '0000089800' },
    { name: 'Air Products', ticker: 'APD', cik: '0000002969' },
    { name: 'Ecolab', ticker: 'ECL', cik: '0000031462' },
    { name: 'Freeport-McMoRan', ticker: 'FCX', cik: '0000831259' },
    { name: 'Newmont', ticker: 'NEM', cik: '0001164727' },
    { name: 'Nucor', ticker: 'NUE', cik: '0000073309' },
    { name: 'Dow', ticker: 'DOW', cik: '0001751788' },
    { name: 'Corteva', ticker: 'CTVA', cik: '0001755672' },
    { name: 'PPG Industries', ticker: 'PPG', cik: '0000079879' },

    // Automotive
    { name: 'Ford', ticker: 'F', cik: '0000037996' },
    { name: 'General Motors', ticker: 'GM', cik: '0001467858' },
    { name: 'Rivian', ticker: 'RIVN', cik: '0001874178' },
    { name: 'Lucid Group', ticker: 'LCID', cik: '0001811210' },
];

// Create lookup maps for faster searching
export const TICKER_TO_COMPANY: Record<string, Company> = {};
export const NAME_TO_COMPANY: Record<string, Company> = {};

SP500_COMPANIES.forEach(company => {
    TICKER_TO_COMPANY[company.ticker] = company;
    NAME_TO_COMPANY[company.name.toLowerCase()] = company;
});

/**
 * Search companies by name or ticker
 * Returns matching companies sorted by relevance
 */
export function searchCompanies(query: string, limit: number = 10): Company[] {
    if (!query || query.length < 1) return [];

    const lowerQuery = query.toLowerCase();
    const results: { company: Company; score: number }[] = [];

    for (const company of SP500_COMPANIES) {
        let score = 0;

        // Exact ticker match - highest priority
        if (company.ticker.toLowerCase() === lowerQuery) {
            score = 100;
        }
        // Exact name match - high priority
        else if (company.name.toLowerCase() === lowerQuery) {
            score = 95;
        }
        // Ticker starts with query
        else if (company.ticker.toLowerCase().startsWith(lowerQuery)) {
            score = 80;
        }
        // Name starts with query
        else if (company.name.toLowerCase().startsWith(lowerQuery)) {
            score = 75;
        }
        // Ticker contains query
        else if (company.ticker.toLowerCase().includes(lowerQuery)) {
            score = 50;
        }
        // Name contains query
        else if (company.name.toLowerCase().includes(lowerQuery)) {
            score = 40;
        }

        if (score > 0) {
            results.push({ company, score });
        }
    }

    // Sort by score descending, then by name alphabetically
    results.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        return a.company.name.localeCompare(b.company.name);
    });

    // Remove duplicates (same company with different name variations)
    const seen = new Set<string>();
    const unique: Company[] = [];

    for (const { company } of results) {
        if (!seen.has(company.ticker)) {
            seen.add(company.ticker);
            unique.push(company);
            if (unique.length >= limit) break;
        }
    }

    return unique;
}
