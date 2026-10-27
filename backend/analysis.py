"""Descriptive English stylometry. No feature is an authorship classifier."""
import math
import re
import statistics
from collections import Counter
from typing import Protocol

VERSION = 'descriptive-en-1.0.0'
UNAVAILABLE = 'AI authorship probability unavailable — insufficient validated evidence'
WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
FUNCTION_WORDS = set('the a an and or but to of in on at for with by from as is are was were be been it this that these those he she they we you i'.split())
TRANSITIONS = ('however', 'furthermore', 'moreover', 'in conclusion', 'therefore', 'nevertheless', 'additionally', 'consequently')

class Detector(Protocol):
    """An adapter must supply independent evaluation and calibration provenance."""
    name: str
    version: str
    def predict(self, text: str, language: str) -> dict: ...

class AbstainingDetector:
    name = 'No validated detector configured'
    version = None
    def predict(self, text: str, language: str) -> dict:
        return {'status': 'abstained', 'probability': None, 'message': UNAVAILABLE,
                'model': self.name, 'version': self.version, 'calibrated': False}

def words(text):
    return WORD.findall(text.lower())

def mean(items):
    return round(statistics.mean(items), 3) if items else 0

def segment(text):
    # Preserve original offsets; protect common abbreviations and decimal points.
    masked = re.sub(r'\b(?:Mr|Mrs|Ms|Dr|Prof|e\.g|i\.e|etc)\.', lambda m: m[0].replace('.', '·'), text, flags=re.I)
    masked = re.sub(r'(?<=\d)\.(?=\d)', '·', masked)
    spans = []
    for m in re.finditer(r'[^.!?]+(?:[.!?]+["”’\']?|$)', masked):
        start, end = m.span()
        while start < end and text[start].isspace(): start += 1
        if words(text[start:end]): spans.append((start, end))
    return spans

def analyze(text, language='en', detector=None):
    if language != 'en':
        raise ValueError('Only English descriptive analysis is supported. Select English only for English text.')
    tokens = words(text)
    if not tokens: raise ValueError('Enter English prose containing words.')
    latin = len(re.findall('[A-Za-z]', text))
    letters = sum(c.isalpha() for c in text)
    if letters and latin / letters < .8:
        raise ValueError('The text appears to use an unsupported script. Only English is supported.')
    counts = Counter(tokens)
    sentences = []
    spans = segment(text)
    openings = Counter(' '.join(words(text[a:b])[:2]) for a,b in spans)
    lengths = [len(words(text[a:b])) for a,b in spans]
    avg = mean(lengths)
    sd = statistics.pstdev(lengths) if len(lengths)>1 else 0
    for i,(a,b) in enumerate(spans):
        st = text[a:b]
        ws = words(st)
        findings = []
        if len(ws)>35: findings.append('Long sentence: more than 35 words.')
        opening = ' '.join(ws[:2])
        if len(ws)>2 and openings[opening]>1: findings.append(f'Repeated opening “{opening}” appears {openings[opening]} times.')
        if len(lengths)>=5 and sd and abs(len(ws)-avg)>2*sd: findings.append('Sentence length differs by more than two standard deviations from this document mean.')
        transitions = [p for p in TRANSITIONS if re.search(r'\b'+p+r'\b', st.lower())]
        sentences.append({'index':i,'start':a,'end':b,'text':st,'words':len(ws),'lexical_diversity':round(len(set(ws))/len(ws),3) if ws else 0,'findings':findings,'transitions':transitions})
    paragraphs = []
    for i,m in enumerate(re.finditer(r'\S[^\n]*(?:\n(?!\s*\n)[^\n]+)*', text)):
        ws = words(m[0])
        if ws: paragraphs.append({'index':i,'words':len(ws),'mean_word_length':mean([len(w) for w in ws]),'lexical_diversity':round(len(set(ws))/len(ws),3),'text':m[0]})
    windows = [tokens[i:i+50] for i in range(0,len(tokens)-49,25)]
    warnings = ['These are descriptive measurements, not evidence of who wrote the document.', 'English is user-declared; script checks cannot reliably identify every unsupported language.']
    if len(tokens)<100: warnings.append('Short sample: fewer than 100 words. Style measurements are unstable.')
    if len(lengths)<5: warnings.append('Fewer than five sentences: limited evidence for variation comparisons.')
    return {'engine_version':VERSION,'language':language,'characters':len(text),'word_count':len(tokens),'sentence_count':len(sentences),'paragraph_count':len(paragraphs),
        'features':{'mean_sentence_words':avg,'sentence_stddev':round(sd,3),'sentence_cv':round(sd/avg,3) if avg else 0,'lexical_diversity':round(len(counts)/len(tokens),3),'windowed_lexical_diversity':mean([len(set(w))/50 for w in windows]) if windows else None,'mean_word_length':mean([len(w) for w in tokens]),'function_word_fraction':round(sum(counts[w] for w in FUNCTION_WORDS)/len(tokens),3),'paragraph_word_stddev':round(statistics.pstdev([p['words'] for p in paragraphs]),3) if paragraphs else 0},
        'repeated_words':[{'word':w,'count':n} for w,n in counts.most_common(20) if n>1 and w not in FUNCTION_WORDS],
        'repeated_openings':[{'opening':w,'count':n} for w,n in openings.items() if n>1],
        'punctuation':{c:text.count(c) for c in ',;:—!?()'},'sentences':sentences,'paragraphs':paragraphs,
        'detector':(detector or AbstainingDetector()).predict(text,language),'warnings':warnings,
        'coverage':{'linguistic_features':True,'pos_tagging':False,'perplexity':False,'external_similarity':False},
        'limitations':['No validated classifier, POS model, or language model is installed. Perplexity, entropy and AI probability are unavailable.','Lexical diversity depends on sample length. Paragraph differences can reflect headings, quotations, revisions or collaboration.','Sentence segmentation is rule based; abbreviations and unusual punctuation can affect boundaries.']}
