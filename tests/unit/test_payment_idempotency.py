def test_payment_idempotency_key_logic():
    idempotency_store = {}

    def process_charge(order_id: str, amount: int, key: str):
        if key in idempotency_store:
            return idempotency_store[key], False  # Existing, not charged again

        tx = {
            "payment_id": f"pay-{key[:8]}",
            "order_id": order_id,
            "amount": amount,
            "status": "SUCCEEDED",
            "idempotency_key": key,
        }
        idempotency_store[key] = tx
        return tx, True  # Freshly processed

    res1, charged1 = process_charge("ord-1", 5000, "idem-key-abc-123")
    assert charged1 is True
    assert res1["status"] == "SUCCEEDED"

    # Second submission with identical key
    res2, charged2 = process_charge("ord-1", 5000, "idem-key-abc-123")
    assert charged2 is False
    assert res2 == res1
