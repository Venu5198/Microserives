def test_cart_item_subtotals():
    items = [
        {"product_id": "p1", "product_name": "Item 1", "unit_price": 1500, "quantity": 2},
        {"product_id": "p2", "product_name": "Item 2", "unit_price": 2500, "quantity": 1},
    ]

    total_amount = sum(it["unit_price"] * it["quantity"] for it in items)
    total_items = sum(it["quantity"] for it in items)

    assert total_amount == 5500
    assert total_items == 3

