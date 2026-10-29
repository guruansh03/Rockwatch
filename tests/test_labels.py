"""Label tests on SYNTHETIC events (test-only)."""
import pandas as pd

from rockwatch.data.labels import label_panel


def test_label_panel():
    keys = pd.DataFrame({"zone_id": ["a", "a", "b"], "date": pd.to_datetime(["2010-01-01", "2010-01-02", "2010-01-01"])})
    ev = pd.DataFrame({"event_id": ["1", "2", "3", "4"], "zone_id": ["a", "a", "b", "b"],
                       "date_min": pd.to_datetime(["2010-01-01", "2010-01-01", "2010-01-01", "2010-01-01"]),
                       "date_max": pd.to_datetime(["2010-01-01"] * 4), "date_kind": ["exact", "exact", "short_range", "exact"],
                       "type_family": ["fall", "slide", "fall", "slide"], "confidence": [5, 3, 5, 3],
                       "eq_inventory": [False, False, False, True]})
    out = label_panel(keys, ev)
    assert list(out["y"]) == [1, 0, 1]
    assert list(out["n_events"]) == [2, 0, 1]
    assert list(out["y_fall"]) == [1, 0, 0]       # short-range fall in b is not an exact positive
    assert list(out["y_no_eq"]) == [1, 0, 0]
    assert list(out["y_c5"]) == [1, 0, 0]
