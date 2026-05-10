# Sample fixture for orders_import tests

The Python tests build a tiny in-memory pandas DataFrame matching the Fresho
`delivery_runs` export columns and write it to a temp .xlsx — see
`tests/test_orders_import.py`. We don't ship a binary fixture here because
real customer data shouldn't end up in git history.
