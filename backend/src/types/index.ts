export interface ParsedQuery {
    company: string;
    ticker?: string;
    documentType?: 'annual' | 'quarterly' | 'investor-presentation' | 'proxy' | 'current' | 'esg';
    year?: number;
    quarter?: number;
    filingType?: string; // 10-K, 10-Q, 8-K, etc.
}

export interface SearchResult {
    url: string;
    title: string;
    company: string;
    ticker?: string;
    documentType: string;
    filingDate?: string;
    fiscalYear?: number;      // The fiscal year the report covers (e.g., 2024)
    fiscalPeriodEnd?: string; // The fiscal period end date (e.g., 2024-09-28)
    fileFormat?: string;
    fileSize?: string;
    confidence: number;
    source: 'company-website' | 'sec-edgar' | 'bse-india' | 'nse-india' | 'lse' | 'sgx' | 'tadawul' | 'other';
    market?: string; // Country/market code
    linkVerified?: boolean; // Whether the link was validated as working
    officialReportsPage?: string; // The official page where reports are listed
    notes?: string; // Additional info or snippet
}

export interface SearchResponse {
    success: boolean;
    company?: string;
    requestedReport?: string;
    officialWebsite?: string;
    reportsPage?: string;
    results: SearchResult[];
    notes?: string; // Explanation if something failed
}
