import difflib
import io
import json
import os
import threading
import time
import uuid
import zipfile
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from .analysis import analyze
from .storage import connect, decode

app=FastAPI(title='AEGIS AI',version='0.1.0')
MAX_BYTES=10*1024*1024
jobs={}
lock=threading.Lock()
requests=defaultdict(deque)

@app.middleware('http')
async def security(request: Request, call_next):
    if request.url.path.startswith('/api'):
        origin=request.headers.get('origin')
        if origin and origin.rstrip('/') != str(request.base_url).rstrip('/') and origin not in os.getenv('AEGIS_ALLOWED_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(','):
            return Response('Origin not allowed',403)
        key=request.client.host if request.client else 'local'
        now=time.monotonic()
        with lock:
            q=requests[key]
            while q and q[0]<now-60: q.popleft()
            if len(q)>=120: return Response('Rate limit exceeded',429)
            q.append(now)
        if request.method in ('POST','PUT','PATCH'):
            body=await request.body()
            if len(body)>MAX_BYTES+65536:
                return Response('Request too large',413)
    r=await call_next(request)
    r.headers['X-Content-Type-Options']='nosniff'
    r.headers['Referrer-Policy']='no-referrer'
    r.headers['X-Frame-Options']='DENY'
    r.headers['Cache-Control']='no-store'
    r.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'"
    return r

class Submission(BaseModel):
    title: str=Field(default='Untitled document',min_length=1,max_length=160)
    text: str=Field(min_length=1,max_length=200000)
    language: str='en'
    kind: str=Field(default='General text',max_length=60)
    group_id: str=Field(default='',max_length=80)
    notes: str=Field(default='',max_length=2000)

def get_analysis(id):
    with connect() as db: row=db.execute('SELECT * FROM analyses WHERE id=?',(id,)).fetchone()
    if not row: raise HTTPException(404,'Analysis not found (it may have expired).')
    return decode(row)

@app.get('/api/health')
def health():
    with connect() as db: db.execute('SELECT 1').fetchone()
    return {'status':'ok','mode':'private-single-user','detector':'unavailable','external_processing':False}

@app.post('/api/extract')
async def extract(file: UploadFile=File(...)):
    raw=await file.read(MAX_BYTES+1)
    await file.close()
    if len(raw)>MAX_BYTES: raise HTTPException(413,'Upload limit is 10 MB.')
    ext=Path(file.filename or '').suffix.lower()
    try:
        if ext=='.txt': text=raw.decode('utf-8-sig')
        elif ext=='.pdf':
            if not raw.startswith(b'%PDF-'): raise ValueError('Invalid PDF signature.')
            reader=PdfReader(io.BytesIO(raw))
            if reader.is_encrypted: raise ValueError('Password-protected PDFs are unsupported.')
            if len(reader.pages)>200: raise ValueError('PDF limit is 200 pages.')
            text='\n\n'.join(p.extract_text(extraction_mode='layout') or '' for p in reader.pages)
        elif ext=='.docx':
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                if sum(i.file_size for i in z.infolist())>30*1024*1024: raise ValueError('Expanded DOCX exceeds 30 MB.')
                if 'word/document.xml' not in z.namelist(): raise ValueError('Invalid DOCX document.')
            doc=Document(io.BytesIO(raw))
            from docx.table import Table
            from docx.text.paragraph import Paragraph as DocParagraph
            parts=[]
            for item in doc.iter_inner_content():
                if isinstance(item,DocParagraph): parts.append(item.text)
                elif isinstance(item,Table): parts.extend('\t'.join(c.text for c in row.cells) for row in item.rows)
            text='\n\n'.join(parts)
        else: raise HTTPException(415,'Supported files: UTF-8 TXT, PDF and DOCX.')
        if not text.strip(): raise ValueError('No extractable text. Image-only files require OCR, which is not configured.')
        if len(text)>200000: raise ValueError('Extracted text exceeds 200,000 characters.')
        return {'text':text,'filename':file.filename,'warning':'Check extraction order, especially for tables and multi-column PDFs.'}
    except HTTPException: raise
    except Exception as e:
        message=str(e) if isinstance(e,(ValueError,UnicodeError)) else 'Corrupted or unsupported document.'
        raise HTTPException(422,message)

def process(id, data):
    try:
        with lock:
            if jobs[id]['status']=='cancelled': return
            jobs[id]['status']='analyzing'
        result=analyze(data['text'],data['language'])
        with lock:
            if jobs[id]['status']=='cancelled': return
            jobs[id].update(status='completed',result=result)
    except Exception as e:
        with lock: jobs[id].update(status='failed',error=str(e))

@app.post('/api/jobs',status_code=202)
def submit(data: Submission):
    with lock:
        if sum(j['status'] in ('queued','analyzing') for j in jobs.values())>=4: raise HTTPException(429,'Analysis capacity reached. Try again shortly.')
        # Bounded ephemeral results. Saved documents are held in the database.
        for key in list(jobs):
            if time.monotonic()-jobs[key]['started']>3600: del jobs[key]
        if len(jobs)>=100: raise HTTPException(429,'Temporary result capacity reached. Delete a result or wait for expiry.')
        id=str(uuid.uuid4())
        jobs[id]={'id':id,'status':'queued','started':time.monotonic(),'submission':data.model_dump()}
    threading.Thread(target=process,args=(id,data.model_dump()),daemon=True).start()
    return {'id':id}

@app.get('/api/jobs/{id}')
def job(id:str):
    with lock:
        if id not in jobs: raise HTTPException(404,'Job expired or not found.')
        return {k:v for k,v in jobs[id].items() if k!='started'}

@app.delete('/api/jobs/{id}',status_code=204)
def cancel(id:str):
    with lock:
        if id in jobs:
            if jobs[id]['status'] in ('queued','analyzing'): jobs[id]={'id':id,'status':'cancelled','started':time.monotonic()}
            else: del jobs[id]

@app.post('/api/jobs/{id}/save')
def save(id:str):
    j=job(id)
    if j['status']!='completed': raise HTTPException(409,'Analysis is not complete.')
    d=j['submission']; created=datetime.now(timezone.utc).isoformat()
    with connect() as db:
        db.execute('INSERT OR IGNORE INTO analyses VALUES (?,?,?,?,?,?,?,?)',(id,created,d['title'],d['text'],d['kind'],d['group_id'] or id,d['notes'],json.dumps(j['result'])))
    return get_analysis(id)

@app.get('/api/analyses')
def history():
    with connect() as db: return [decode(r,False) for r in db.execute('SELECT * FROM analyses ORDER BY created DESC')]

@app.get('/api/analyses/{id}')
def detail(id:str): return get_analysis(id)

@app.delete('/api/analyses/{id}',status_code=204)
def delete(id:str):
    with connect() as db: db.execute('DELETE FROM analyses WHERE id=?',(id,))
    with lock: jobs.pop(id,None)

@app.get('/api/compare')
def compare(left:str,right:str):
    a,b=get_analysis(left),get_analysis(right)
    return {'left':a,'right':b,'diff':list(difflib.unified_diff(a['text'].splitlines(),b['text'].splitlines(),fromfile=a['title'],tofile=b['title'],lineterm='')),'changes':{k:round(b['result']['features'][k]-v,3) for k,v in a['result']['features'].items() if isinstance(v,(int,float)) and isinstance(b['result']['features'].get(k),(int,float))}}

class Profile(BaseModel):
    consent: bool
    analysis_ids: list[str]=Field(min_length=1,max_length=30)

@app.put('/api/profile')
def profile_save(data:Profile):
    if not data.consent: raise HTTPException(422,'Explicit consent is required.')
    for id in data.analysis_ids: get_analysis(id)
    with connect() as db: db.execute('INSERT OR REPLACE INTO profile VALUES(1,?,?)',(datetime.now(timezone.utc).isoformat(),json.dumps(data.analysis_ids)))
    return profile()

@app.get('/api/profile')
def profile():
    with connect() as db:
        row=db.execute('SELECT * FROM profile').fetchone()
        if not row: return {'references':[],'features':{},'consent':None}
        ids=json.loads(row['analysis_ids'])
        refs=[decode(r,False) for r in db.execute('SELECT * FROM analyses') if r['id'] in ids]
    keys=('mean_sentence_words','mean_word_length','lexical_diversity','function_word_fraction')
    return {'consent':row['consent'],'references':[{'id':r['id'],'title':r['title']} for r in refs],'features':{k:round(sum(r['result']['features'][k] for r in refs)/len(refs),3) for k in keys} if refs else {}}

@app.delete('/api/profile',status_code=204)
def profile_delete():
    with connect() as db: db.execute('DELETE FROM profile')

class Settings(BaseModel):
    retention_days: int=Field(ge=0,le=3650)

@app.get('/api/settings')
def settings():
    with connect() as db: return dict(db.execute('SELECT retention_days FROM settings WHERE id=1').fetchone())

@app.put('/api/settings')
def settings_save(data:Settings):
    with connect() as db: db.execute('UPDATE settings SET retention_days=? WHERE id=1',(data.retention_days,))
    return settings()

@app.delete('/api/data',status_code=204)
def clear():
    with connect() as db:
        db.execute('DELETE FROM profile'); db.execute('DELETE FROM analyses')
    with lock:
        for id in jobs: jobs[id]={'id':id,'status':'cancelled','started':time.monotonic()}

class Question(BaseModel):
    topic:str=Field(max_length=80)

@app.post('/api/analyses/{id}/assistant')
def assistant(id:str,q:Question):
    r=get_analysis(id)['result']
    answers={'variation':f"This document has {r['sentence_count']} sentences, with mean length {r['features']['mean_sentence_words']} words and standard deviation {r['features']['sentence_stddev']}. Variation reflects structure, genre and editing, not authorship.",
    'highlights':f"{sum(bool(s['findings']) for s in r['sentences'])} sentences have descriptive flags. Select each sentence to see the measured reason. Long sentences and repeated openings can be normal rhetorical choices.",
    'reliability':r['detector']['message']+'. No numeric authorship estimate is produced. Human and AI writing can share the same stylistic characteristics.',
    'diversity':f"Type-token ratio is {r['features']['lexical_diversity']}: distinct lowercase words divided by all words. It decreases with longer samples and is not comparable across arbitrary lengths."}
    return {'answer':answers.get(q.topic,'Choose variation, highlights, diversity or reliability. This local report guide uses measured results; a conversational model is not configured.'),'source':'Local deterministic report guide; no external AI service'}

def summary(d):
    r=d['result']
    return '\n'.join(['AEGIS AI — Writing analysis',d['title'],d['created'],r['detector']['message'],f"Words: {r['word_count']} | Sentences: {r['sentence_count']}",f"Engine: {r['engine_version']}",'Measured features:']+[f'{k}: {v}' for k,v in r['features'].items()]+['Limitations:']+r['warnings']+r['limitations'])

@app.get('/api/analyses/{id}/export/{format}')
def export(id:str,format:str):
    d=get_analysis(id)
    if format=='json': content=json.dumps(d,ensure_ascii=False,indent=2).encode(); media='application/json'
    elif format=='txt': content=summary(d).encode(); media='text/plain; charset=utf-8'
    elif format=='pdf':
        buf=io.BytesIO(); styles=getSampleStyleSheet()
        story=[]
        for line in summary(d).splitlines(): story.extend([Paragraph(escape(line),styles['BodyText']),Spacer(1,8)])
        story.extend([Spacer(1,16),Paragraph('Passage findings',styles['Heading2'])])
        for s in d['result']['sentences']:
            if s['findings']: story.append(Paragraph(escape(s['text']+' — '+' '.join(s['findings'])),styles['BodyText']))
        SimpleDocTemplate(buf).build(story); content=buf.getvalue(); media='application/pdf'
    else: raise HTTPException(404,'Unsupported export format.')
    return Response(content,media_type=media,headers={'Content-Disposition':f'attachment; filename="aegis-{id}.{format}"'})

DIST=Path(__file__).resolve().parent.parent/'frontend'/'dist'
if DIST.exists(): app.mount('/',StaticFiles(directory=DIST,html=True),name='frontend')
