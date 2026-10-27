"""Evaluate externally generated probabilities; never train or fabricate predictions.
Input JSONL fields: split, text, label (0 human / 1 AI), probability, group.
Labels for edited or mixed text require a documented policy before evaluation.
"""
import argparse
import hashlib
import json
import math
from collections import defaultdict
from difflib import SequenceMatcher


def metrics(rows, threshold=.5):
    n=len(rows)
    if not n:return {'count':0}
    tp=sum(r['label']==1 and r['probability']>=threshold for r in rows)
    fp=sum(r['label']==0 and r['probability']>=threshold for r in rows)
    fn=sum(r['label']==1 and r['probability']<threshold for r in rows)
    tn=n-tp-fp-fn
    ratio=lambda a,b:a/b if b else None
    precision=ratio(tp,tp+fp);recall=ratio(tp,tp+fn)
    ece=0
    for i in range(10):
        bucket=[r for r in rows if min(int(r['probability']*10),9)==i]
        if bucket:ece+=len(bucket)/n*abs(sum(r['label'] for r in bucket)/len(bucket)-sum(r['probability'] for r in bucket)/len(bucket))
    pos=[r['probability'] for r in rows if r['label']==1];neg=[r['probability'] for r in rows if r['label']==0]
    auc=sum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg)) if pos and neg else None
    # Average precision, tie-aware at each distinct score threshold.
    ap=0; previous=0
    if pos:
        for score in sorted({r['probability'] for r in rows},reverse=True):
            selected=[r for r in rows if r['probability']>=score]
            hits=sum(r['label'] for r in selected);rec=hits/len(pos)
            ap+=(rec-previous)*hits/len(selected);previous=rec
    return {'count':n,'precision':precision,'recall':recall,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,'false_positive_rate':ratio(fp,fp+tn),'false_negative_rate':ratio(fn,fn+tp),'roc_auc':auc,'average_precision':ap if pos else None,'expected_calibration_error_10_bins':ece,'brier_score':sum((r['probability']-r['label'])**2 for r in rows)/n}

def evaluate(rows):
    seen=[]
    for row in rows:
        if row['split'] not in ('train','validation','test'): raise ValueError('Invalid split')
        if row['label'] not in (0,1) or not math.isfinite(row['probability']) or not 0<=row['probability']<=1: raise ValueError('Invalid label or probability')
        text=' '.join(row['text'].lower().split())
        if not text:raise ValueError('Empty text')
        for split,prior in seen:
            if split!=row['split'] and (text==prior or SequenceMatcher(None,text,prior,autojunk=False).ratio()>.9):
                raise ValueError('Cross-split exact or near-duplicate leakage detected')
        seen.append((row['split'],text))
    test=[r for r in rows if r['split']=='test']
    if not test:raise ValueError('No held-out test records')
    groups=defaultdict(list)
    for r in test:
        groups['writer/domain:'+r['group']].append(r)
        length=len(r['text'].split());groups['length:'+('short' if length<100 else 'medium' if length<500 else 'long')].append(r)
    return {'overall':metrics(test),'groups':{k:metrics(v) for k,v in groups.items()},'note':'Evaluation only; does not register or validate a detector. Threshold 0.5 is a reporting default, not an approved decision or abstention threshold.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('jsonl');args=p.parse_args()
    with open(args.jsonl) as f:rows=[json.loads(line) for line in f if line.strip()]
    print(json.dumps(evaluate(rows),indent=2))
