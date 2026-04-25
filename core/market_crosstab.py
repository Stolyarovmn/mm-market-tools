#!/usr/bin/env python3
"""
Extensions to analyze_competitor_market.py
- group × price_band cross-tabulation
- HHI calculation by price_band
- Coverage gaps identification
- Entry window prioritization with novelty_proxy factoring
- Configurable price band boundaries
"""

from collections import defaultdict
import statistics


def calculate_hhi_by_band(items_by_band):
    """
    Calculate Herfindahl-Hirschman Index (HHI) for each price band.
    HHI = sum of squared market shares (in percentage points, 0-10000 scale)
    """
    result = {}
    for band, items in items_by_band.items():
        if not items:
            result[band] = None
            continue
        
        seller_orders = defaultdict(float)
        for item in items:
            seller_orders[item["seller_id"]] += item["orders"]
        
        total_orders = sum(seller_orders.values())
        if total_orders <= 0:
            result[band] = None
            continue
        
        hhi = sum((orders / total_orders * 100) ** 2 for orders in seller_orders.values())
        result[band] = round(hhi, 2)
    
    return result


def build_group_price_band_crosstab(items, my_group_prices=None):
    """
    Create a group × price_band cross-tabulation.
    Shows SKU count for market vs shop across all groups and bands.
    """
    crosstab = defaultdict(lambda: defaultdict(int))
    shop_coverage = defaultdict(lambda: defaultdict(int))
    
    # Count market items by group and price_band
    for item in items:
        group = item.get("group")
        band = item.get("price_band")
        if group and band:
            crosstab[group][band] += 1
    
    # Count shop items (if provided)
    if my_group_prices:
        for group, data in my_group_prices.items():
            # We'll estimate shop coverage based on my_sku_count across bands
            # This is a simplified approach; in real scenarios, you'd track shop skus by band
            shop_coverage[group]["*"] = data.get("my_sku_count", 0)
    
    # Convert to flat list format
    crosstab_data = []
    for group in sorted(crosstab.keys()):
        for band in sorted(crosstab[group].keys()):
            crosstab_data.append({
                "group": group,
                "price_band": band,
                "count": crosstab[group][band],
                "source": "market",
            })
    
    for group in sorted(shop_coverage.keys()):
        for band in shop_coverage[group]:
            crosstab_data.append({
                "group": group,
                "price_band": band,
                "count": shop_coverage[group][band],
                "source": "shop",
            })
    
    return crosstab_data


def identify_coverage_gaps(items, my_group_prices, hhi_by_band):
    """
    Identify coverage gaps where:
    - Shop has SKUs but market is empty (expansion opportunity)
    - Market has SKUs but shop is empty (competitive pressure)
    """
    gaps = []
    
    # Build market coverage by group and band
    market_coverage = defaultdict(lambda: defaultdict(list))
    for item in items:
        group = item.get("group")
        band = item.get("price_band")
        if group and band:
            market_coverage[group][band].append(item)
    
    # Identify gaps
    for group, data in (my_group_prices or {}).items():
        sku_count = data.get("my_sku_count", 0)
        if sku_count == 0:
            continue
        
        # For simplicity, we check each band the market has for this group
        for band in market_coverage.get(group, {}):
            market_items = market_coverage[group][band]
            if not market_items:
                gap_type = "shop_only"
                gap_score = 30.0  # Shop has products, market doesn't
            else:
                gap_type = "shared"
                gap_score = 10.0
            
            market_orders = sum(item["orders"] for item in market_items)
            market_avg_price = round(
                statistics.mean([item["price"] for item in market_items if item["price"] > 0]),
                2
            ) if market_items else 0
            novelty_index = statistics.mean(
                [item.get("novelty_proxy_score", 0) for item in market_items]
            ) if market_items else 0
            
            gaps.append({
                "group": group,
                "price_band": band,
                "shop_sku_count": sku_count,
                "market_sku_count": len(market_items),
                "gap_type": gap_type,
                "gap_score": gap_score,
                "market_volume_orders": market_orders,
                "market_avg_price": market_avg_price,
                "market_hhi_by_band": hhi_by_band.get(band),
                "novelty_proxy_index": round(novelty_index, 2),
            })
    
    return gaps


def calculate_entry_window_with_novelty_factoring(entry_windows, novelty_proxy_index=None):
    """
    Adjust entry window scoring by factoring in novelty_proxy_index.
    This separates genuine freshness signals from proxy artifacts.
    """
    for window in entry_windows:
        base_score = window.get("entry_window_score", 50.0)
        novelty_idx = window.get("novelty_proxy_index")
        
        # Novelty adjustment: boost score if market shows genuine newness
        novelty_adjustment = 0.0
        if novelty_idx is not None:
            if novelty_idx >= 65:
                novelty_adjustment = 15.0  # Strong freshness signal
            elif novelty_idx >= 40:
                novelty_adjustment = 8.0   # Moderate freshness signal
            # Below 40 is mature market - no adjustment
        
        # Apply novelty factoring while capping the score
        adjusted_score = round(min(100.0, base_score + novelty_adjustment), 2)
        window["entry_window_score_adjusted"] = adjusted_score
        window["novelty_adjustment_factor"] = round(novelty_adjustment, 2)
    
    return entry_windows


def apply_configurable_price_bands(items, price_band_boundaries=None):
    """
    Re-classify items into custom price band boundaries.
    Default: [0-50, 50-200, 200-500, 500+]
    """
    if price_band_boundaries is None:
        price_band_boundaries = [50, 200, 500]
    
    def classify_to_custom_band(price, boundaries):
        price = float(price or 0)
        if price <= 0:
            return "unknown"
        for i, bound in enumerate(sorted(boundaries)):
            if price < bound:
                if i == 0:
                    return f"0-{bound}"
                else:
                    return f"{boundaries[i-1]}-{bound}"
        return f"{boundaries[-1]}+"
    
    for item in items:
        item["price_band_custom"] = classify_to_custom_band(
            item.get("price"), price_band_boundaries
        )
    
    return items


def add_coverage_gap_to_entry_windows(entry_windows, gaps_by_window):
    """
    Integrate coverage gap scores into entry window prioritization.
    Prioritization: (1) coverage_gap, (2) market_volume, (3) economics
    """
    for window in entry_windows:
        window_key = (window.get("group"), window.get("price_band"))
        gap_info = gaps_by_window.get(window_key, {})
        
        window["coverage_gap_score"] = gap_info.get("gap_score", 0.0)
        window["coverage_gap_type"] = gap_info.get("gap_type", "unknown")
        
        # Recalculate prioritization score
        # Priority formula: (1) coverage_gap (40%) + (2) market_volume (35%) + (3) economics (25%)
        gap_score = gap_info.get("gap_score", 0.0)
        volume_score = min(100.0, (window.get("orders_sum", 0) / 100.0))  # Normalize to 0-100
        economics_score = window.get("market_margin_fit_pct", 50.0)  # Use margin fit if available
        
        priority_score = (
            (gap_score * 0.40) +
            (volume_score * 0.35) +
            (economics_score * 0.25)
        )
        window["entry_priority_score"] = round(min(100.0, priority_score), 2)
    
    return entry_windows

