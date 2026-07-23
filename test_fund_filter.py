"""Regression tests for fund_filter.is_fund_query."""
from fund_filter import is_fund_query


def test_wisdomtree_company_not_fund_only():
    # WisdomTree Inc. (NYSE: WT) is an operating company; neither the bare name nor
    # the annual-report query must be blocked as a fund/ETF.
    assert is_fund_query("WisdomTree")[0] is False
    assert is_fund_query("WisdomTree 2025 annual report")[0] is False


def test_wisdomtree_etf_product_still_rejected():
    # The fund/ETF VEHICLE markers still catch an actual WisdomTree fund product.
    is_fund, signal = is_fund_query("WisdomTree Emerging Markets Fund annual report")
    assert is_fund is True
    assert signal.lower() == "fund"


if __name__ == "__main__":
    test_wisdomtree_company_not_fund_only()
    test_wisdomtree_etf_product_still_rejected()
    print("ok")
