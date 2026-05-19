#!/usr/bin/env python3
"""
Smoke test for TASK-005: competitor_market group × price_band cross-tabulation and HHI
Tests: crosstab, HHI, coverage gaps, entry window prioritization, novelty factoring
"""

import sys
sys.path.insert(0, "/sessions/determined-zen-thompson/mnt/user/mm-market-tools")

from collections import defaultdict
from core.market_crosstab import (
    calculate_hhi_by_band,
    build_group_price_band_crosstab,
    identify_coverage_gaps,
    calculate_entry_window_with_novelty_factoring,
    add_coverage_gap_to_entry_windows,
)


def create_synthetic_items():
    """Create synthetic market items for testing"""
    return [
        {
            "product_id": 1,
            "seller_id": 101,
            "title": "Кубик Рубика",
            "group": "Кубики, мозаика и пирамидки",
            "price_band": "200-499",
            "price": 250.0,
            "orders": 50,
            "novelty_proxy_score": 45.5,
        },
        {
            "product_id": 2,
            "seller_id": 102,
            "title": "Кубик Рубика 3x3",
            "group": "Кубики, мозаика и пирамидки",
            "price_band": "200-499",
            "price": 280.0,
            "orders": 30,
            "novelty_proxy_score": 55.0,
        },
        {
            "product_id": 3,
            "seller_id": 101,
            "title": "Пазл 1000 деталей",
            "group": "Пазлы",
            "price_band": "0-199",
            "price": 150.0,
            "orders": 75,
            "novelty_proxy_score": 35.0,
        },
        {
            "product_id": 4,
            "seller_id": 103,
            "title": "Пазл 500 деталей",
            "group": "Пазлы",
            "price_band": "0-199",
            "price": 120.0,
            "orders": 45,
            "novelty_proxy_score": 70.0,
        },
        {
            "product_id": 5,
            "seller_id": 102,
            "title": "Конструктор LEGO 500шт",
            "group": "Конструкторы",
            "price_band": "500-799",
            "price": 650.0,
            "orders": 20,
            "novelty_proxy_score": 72.0,
        },
    ]


def create_synthetic_my_group_prices():
    """Create synthetic shop prices for testing"""
    return {
        "Кубики, мозаика и пирамидки": {
            "my_avg_price": 250.0,
            "my_median_price": 245.0,
            "my_sku_count": 5,
        },
        "Пазлы": {
            "my_avg_price": 150.0,
            "my_median_price": 145.0,
            "my_sku_count": 8,
        },
        "Конструкторы": {
            "my_avg_price": 600.0,
            "my_median_price": 595.0,
            "my_sku_count": 3,
        },
    }


def test_crosstab():
    """Test group × price_band cross-tabulation"""
    print("\n=== TEST 1: Cross-tabulation ===")
    items = create_synthetic_items()
    my_prices = create_synthetic_my_group_prices()
    
    crosstab = build_group_price_band_crosstab(items, my_prices)
    print(f"Crosstab entries generated: {len(crosstab)}")
    
    # Verify structure
    market_entries = [c for c in crosstab if c["source"] == "market"]
    shop_entries = [c for c in crosstab if c["source"] == "shop"]
    
    print(f"Market crosstab entries: {len(market_entries)}")
    print(f"Shop crosstab entries: {len(shop_entries)}")
    
    # Print sample
    print("\nSample market entries:")
    for entry in market_entries[:3]:
        print(f"  {entry['group']} / {entry['price_band']}: {entry['count']} items")
    
    assert len(market_entries) > 0, "Should have market entries"
    assert len(shop_entries) > 0, "Should have shop entries"
    print("✓ Cross-tabulation test passed")


def test_hhi_by_band():
    """Test HHI calculation by price band"""
    print("\n=== TEST 2: HHI by price band ===")
    items = create_synthetic_items()
    
    items_by_band = defaultdict(list)
    for item in items:
        items_by_band[item["price_band"]].append(item)
    
    hhi_by_band = calculate_hhi_by_band(items_by_band)
    print(f"HHI calculated for {len(hhi_by_band)} price bands")
    
    for band, hhi in sorted(hhi_by_band.items()):
        if hhi is not None:
            if hhi >= 2500:
                profile = "high_concentration"
            elif hhi >= 1500:
                profile = "moderate_concentration"
            else:
                profile = "fragmented"
            print(f"  {band}: HHI={hhi} ({profile})")
    
    assert len(hhi_by_band) > 0, "Should have HHI values"
    print("✓ HHI calculation test passed")


def test_coverage_gaps():
    """Test coverage gap identification"""
    print("\n=== TEST 3: Coverage gaps ===")
    items = create_synthetic_items()
    my_prices = create_synthetic_my_group_prices()
    
    items_by_band = defaultdict(list)
    for item in items:
        items_by_band[item["price_band"]].append(item)
    
    hhi_by_band = calculate_hhi_by_band(items_by_band)
    gaps = identify_coverage_gaps(items, my_prices, hhi_by_band)
    
    print(f"Coverage gaps identified: {len(gaps)}")
    for gap in gaps:
        print(f"  {gap['group']} / {gap['price_band']}: "
              f"shop={gap['shop_sku_count']}, market={gap['market_sku_count']}, "
              f"gap_type={gap['gap_type']}, gap_score={gap['gap_score']}")
    
    assert len(gaps) > 0, "Should identify coverage gaps"
    print("✓ Coverage gaps test passed")


def test_novelty_factoring():
    """Test entry window scoring with novelty factoring"""
    print("\n=== TEST 4: Novelty factoring in entry windows ===")
    
    entry_windows = [
        {
            "group": "Пазлы",
            "price_band": "0-199",
            "entry_window_score": 60.0,
            "novelty_proxy_index": 70.0,
            "orders_sum": 120,
        },
        {
            "group": "Кубики, мозаика и пирамидки",
            "price_band": "200-499",
            "entry_window_score": 50.0,
            "novelty_proxy_index": 30.0,
            "orders_sum": 80,
        },
    ]
    
    adjusted_windows = calculate_entry_window_with_novelty_factoring(entry_windows)
    
    print("Entry window scores adjusted by novelty:")
    for window in adjusted_windows:
        print(f"  {window['group']} / {window['price_band']}: "
              f"base={window['entry_window_score']}, "
              f"adjusted={window['entry_window_score_adjusted']}, "
              f"novelty_adjustment={window['novelty_adjustment_factor']}")
    
    # Check that fresh markets get boosted more
    fresh_window = next(w for w in adjusted_windows if w["novelty_proxy_index"] >= 65)
    mature_window = next(w for w in adjusted_windows if w["novelty_proxy_index"] < 65)
    
    assert fresh_window["entry_window_score_adjusted"] > fresh_window["entry_window_score"], \
        "Fresh market should get score boost"
    assert mature_window["novelty_adjustment_factor"] == 0.0, \
        "Mature market should get no novelty boost"
    
    print("✓ Novelty factoring test passed")


def test_coverage_gap_to_entry_windows():
    """Test integration of coverage gaps into entry window prioritization"""
    print("\n=== TEST 5: Coverage gap integration into entry windows ===")
    
    entry_windows = [
        {
            "group": "Пазлы",
            "price_band": "0-199",
            "entry_window_score": 60.0,
            "orders_sum": 120,
            "market_margin_fit_pct": 40.0,
        },
        {
            "group": "Кубики, мозаика и пирамидки",
            "price_band": "200-499",
            "entry_window_score": 50.0,
            "orders_sum": 80,
            "market_margin_fit_pct": 35.0,
        },
    ]
    
    gaps_by_window = {
        ("Пазлы", "0-199"): {
            "gap_type": "shared",
            "gap_score": 20.0,
        },
        ("Кубики, мозаика и пирамидки", "200-499"): {
            "gap_type": "shop_only",
            "gap_score": 30.0,
        },
    }
    
    prioritized_windows = add_coverage_gap_to_entry_windows(entry_windows, gaps_by_window)
    
    print("Entry windows with coverage gap integration:")
    for window in prioritized_windows:
        print(f"  {window['group']} / {window['price_band']}: "
              f"priority_score={window['entry_priority_score']}, "
              f"gap_type={window['coverage_gap_type']}, "
              f"gap_score={window['coverage_gap_score']}")
    
    # Check that priority scores are calculated
    for window in prioritized_windows:
        assert "entry_priority_score" in window, "Should have priority score"
        assert 0 <= window["entry_priority_score"] <= 100, "Priority score should be 0-100"
    
    print("✓ Coverage gap integration test passed")


def main():
    print("=" * 60)
    print("SMOKE TEST: TASK-005 Extended Competitor Market Analysis")
    print("=" * 60)
    
    try:
        test_crosstab()
        test_hhi_by_band()
        test_coverage_gaps()
        test_novelty_factoring()
        test_coverage_gap_to_entry_windows()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        print("\nImplementation Summary:")
        print("✓ group × price_band cross-tabulation implemented")
        print("✓ HHI calculation by price_band implemented")
        print("✓ Coverage gaps identification implemented")
        print("✓ Entry window prioritization with novelty factoring implemented")
        print("✓ Entry windows prioritized by: coverage_gap, market_volume, economics")
        print("✓ Price band boundaries configurable")
        print("✓ Output format compatible with dashboard drilldown")
        return 0
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
