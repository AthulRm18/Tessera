# Fixture: sample_repo

A tiny Python app (calculator + shopping cart) with a green pytest suite.

Used to develop and test the pipeline's gates without needing the real
supplied repo.  The test command is simply `pytest`.

## Files
- `calculator.py` — add, subtract, multiply, divide
- `cart.py` — Cart class with add/remove/subtotal/clear
- `test_baseline.py` — 16 tests covering all current behaviour
- `pytest.ini` — config so `pytest` works from this directory
