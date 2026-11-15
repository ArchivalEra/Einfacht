from ledger import fact


def measure():
    return {"answer": fact(42, "python3 -c \"print(42)\"", "custom collector")}
