import pytest
from backend.evaluate import metrics,evaluate

def test_metrics():
    rows=[{'label':1,'probability':.9},{'label':0,'probability':.1}]
    r=metrics(rows)
    assert r['f1']==1 and r['roc_auc']==1 and r['average_precision']==1
    assert r['expected_calibration_error_10_bins']==pytest.approx(.1)
    assert r['brier_score']==pytest.approx(.01)

def test_leakage_and_empty_test():
    with pytest.raises(ValueError,match='leakage'):
        evaluate([{'text':'same text','label':1,'probability':.8,'group':'a','split':s} for s in ['train','test']])
    with pytest.raises(ValueError,match='test'):
        evaluate([])
