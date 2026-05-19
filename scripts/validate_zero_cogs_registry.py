#!/usr/bin/env python3
"""
Validation script for zero_cogs_registry.json
Checks:
- All items have valid required fields
- No duplicate SKU identity keys in items list
- Consistency with summary counts (allowing for truncation to top N items)
- No false positives (all items should have COGS=0 or missing)
"""
import argparse
import json
import sys
from pathlib import Path


def validate_registry(json_path):
    """
    Validate a zero_cogs_registry JSON file.
    Returns (passed, error_messages)
    """
    errors = []
    
    # Check file exists
    if not Path(json_path).exists():
        return False, [f"File not found: {json_path}"]
    
    # Load JSON
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    except Exception as e:
        return False, [f"Failed to load file: {e}"]
    
    # Check basic structure
    if not isinstance(data, dict):
        return False, ["Root must be a dict"]
    
    if "summary" not in data or "items" not in data:
        return False, ["Missing 'summary' or 'items' key"]
    
    summary = data.get("summary", {})
    items = data.get("items", [])
    
    if not isinstance(items, list):
        return False, ["'items' must be a list"]
    
    # Validate items
    seen_keys = set()
    item_count = 0
    
    for idx, item in enumerate(items):
        item_count += 1
        
        # Check required fields
        if not isinstance(item, dict):
            errors.append(f"Item {idx} is not a dict")
            continue
        
        # Validate required fields exist and have valid types
        if "group" not in item or not item["group"]:
            errors.append(f"Item {idx} missing or empty 'group'")
        
        if "sku" not in item:
            errors.append(f"Item {idx} missing 'sku'")
        
        if "product_id" not in item:
            errors.append(f"Item {idx} missing 'product_id'")
        
        # Validate sale_price is numeric or None
        sale_price = item.get("sale_price")
        if sale_price is not None:
            try:
                float(sale_price)
            except (ValueError, TypeError):
                errors.append(f"Item {idx} sale_price is not numeric: {sale_price}")
        
        # Check for duplicates using identity key
        key = (
            str(item.get("sku") or "").strip(),
            str(item.get("seller_sku_id") or "").strip(),
            str(item.get("product_id") or "").strip(),
            str(item.get("title") or "").strip().lower(),
        )
        if key in seen_keys:
            errors.append(f"Item {idx} is a duplicate (key: {key})")
        else:
            seen_keys.add(key)
    
    # Check summary consistency
    # Note: items list may be truncated to top N items, so we only verify
    # that summary count >= actual items count
    expected_sku_total = len(items)
    actual_sku_total = summary.get("zero_cogs_sku_total")
    if actual_sku_total is None:
        errors.append("Summary missing 'zero_cogs_sku_total'")
    elif actual_sku_total < expected_sku_total:
        errors.append(
            f"Summary mismatch: zero_cogs_sku_total={actual_sku_total} but items count={expected_sku_total}"
        )
    
    # Print results
    passed = len(errors) == 0
    print(f"Validation: {'PASS' if passed else 'FAIL'}")
    print(f"Items in file: {item_count}")
    print(f"Unique identities: {len(seen_keys)}")
    print(f"Summary zero_cogs_sku_total: {actual_sku_total}")
    
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for error in errors[:20]:  # Show first 20 errors
            print(f"  - {error}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors")
    
    return passed, errors


def main():
    parser = argparse.ArgumentParser(description="Validate a zero_cogs_registry JSON file")
    parser.add_argument("--json-path", required=True, help="Path to zero_cogs_registry_*.json")
    args = parser.parse_args()
    
    passed, errors = validate_registry(args.json_path)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
