import sys,os,re,tempfile,types,random,importlib,json,shutil
def loadmod(d):
    sys.modules['websockets']=types.ModuleType('websockets')
    for k in [k for k in sys.modules if k=='bridge_signals']: del sys.modules[k]
    sys.path.insert(0,d); m=importlib.import_module('bridge_signals'); sys.path.pop(0); return m
O=loadmod('bo'); N=loadmod('.')
res=[]
def ok(n,c,e=''): res.append(('PASS' if c else 'FAIL')+' '+n+(' '+e if e else ''))
# --- 9 regex
src=open('bridge_signals.py',encoding='utf-8').read()
rx=re.compile(re.search(r'_FRAME_SHIFT_RE = re.compile\(r"(.*)"\)',src).group(1))
ok('#9 새 형식(_) 인식',bool(rx.search('FRAME_SHIFT_SUSPECT:disp=190_actual=185')) and rx.search('FRAME_SHIFT_SUSPECT:disp=190_actual=185').groups()==('190','185'))
ok('#9 옛 형식(;) 계속 인식',rx.search('FRAME_SHIFT_SUSPECT:disp=190;actual=185').groups()==('190','185'))
# --- 10 purge differential on random NON-colliding files
def mkfile(d,lines):
    p=os.path.join(d,'sp500_yesspot_signals_Z26.txt'); open(p,'w').write('\n'.join(lines)+'\n'); return p
def run_purge(mod,lines,days,keep):
    d=tempfile.mkdtemp(); p=mkfile(d,lines)
    mod._set_pos(p,os.path.getsize(p)); mod.CONTRACTS_PATH='/x'
    r=mod.purge_file(p,days,keep); left=open(p).read().splitlines()
    ev=os.path.join(d,'purged_while_pending_evidence.log'); return (r['removed'],r['kept'],left,os.path.exists(ev))
def rand_lines(seed,collide=False):
    rnd=random.Random(seed); L=[]; used=set()
    for i in range(60):
        date=rnd.choice(['20260910','20260920','20260928']); tm='%02d:%02d:%02d'%(rnd.randint(0,23),rnd.randint(0,59),rnd.randint(0,59))
        kind=rnd.choice(['BULL1','BULL2','BEAR1','BEAR2']); price='%.2f'%(5000+rnd.randint(0,400)*0.25); tf=rnd.choice(['T0100','M0005','T0200'])
        key=(tf,date,tm)
        if not collide and key in used: continue
        used.add(key)
        L.append(f'SP500,{tf},{kind},{date},{tm},{price},0,0')
        L.append(f'SP500,{tf},REGISTERED,{date},{tm},{price},REAL')
        L.append(f'SP500,{tf},SAVE_SCHEDULED,{date},{tm},{price},{date} {tm},{kind}')
        if rnd.random()<0.5: L.append(f'SP500,{tf},STATUS_{rnd.choice(["ACHIEVED","INVALID"])},{date},{tm},{price},10:00:00(1H{rnd.randint(0,59)}M),reason,{kind}')
        if rnd.random()<0.2: L.append(f'SP500,{tf},STATS_IMMEDIATE,{date},{tm},{price},ACHIEVED,12.5,{kind}')
        if rnd.random()<0.1: L.append(f'SP500,HEARTBEAT_TICK,HEARTBEAT,{date},{tm},0,{tf}|{kind}|{date}|{tm}|{price}')
    return L
diffs=0;total=0
for seed in range(1,101):
    L=rand_lines(seed)
    for keep in (True,False):
        for days in (7,3650):
            a=run_purge(O,L,days,keep); b=run_purge(N,L,days,keep); total+=1
            if a[:3]!=b[:3]: diffs+=1
ok('#10 충돌 없는 데이터 100파일×4조건: 완전삭제 결과 수정 전후 동일',diffs==0,f'({total-diffs}/{total})')
# collision case
L=['SP500,T0100,BULL1,20260920,10:00:00,5000.00,0,0','SP500,T0100,REGISTERED,20260920,10:00:00,5000.00,REAL',
   'SP500,T0100,BEAR1,20260920,10:00:00,4990.00,0,0','SP500,T0100,STATUS_ACHIEVED,20260920,10:00:00,4990.00,14:00:00(1H0M),x,BEAR1']
a=run_purge(O,L,7,True); b=run_purge(N,L,7,True)
ok('#10 수정 전: 같은 시각 다른 신호 때문에 감시중 BULL1 삭제(버그 재현)',not any('BULL1' in l for l in a[2]))
ok('#10 수정 후: 감시중 BULL1 보존',any(',BULL1,' in l for l in b[2]) and any('REGISTERED' in l and '5000.00' in l for l in b[2]),str(b[2]))
ok('#10 수정 후: 판정 끝난 BEAR1/STATUS는 정상 삭제',not any('BEAR1' in l or 'STATUS' in l for l in b[2]))
# old-format STATUS (no kind field)
L2=['SP500,T0100,BULL1,20260920,10:00:00,5000.00,0,0','SP500,T0100,STATUS_ACHIEVED,20260920,10:00:00,5000.00,14:00:00(1H0M),x']
b2=run_purge(N,L2,7,True); ok('#10 구버전 판정줄(신호종류 없음)도 정상 삭제',b2[2]==[],str(b2[2]))
# --- 11 report double count + STATS dedupe
def report(mod,lines):
    d=tempfile.mkdtemp(); os.makedirs(d+'/sp500'); mod.DATA_DIR=d; mod.CONTRACTS_PATH='/x'
    open(d+'/sp500/sp500_yesspot_signals_Z26.txt','w').write('\n'.join(lines)+'\n')
    return {(r['isTick'],r['period']):(r['signals'],r['achieved'],r['invalid']) for r in mod.compute_report()['rows']}
R1=['SP500,T0100,BULL1,20260920,10:00:00,5000.00,0,0','SP500,T0100,STATUS_ACHIEVED,20260920,10:00:00,5000.00,14:00:00(1H0M),x,BULL1',
    'SP500,T0100,STATS_IMMEDIATE,20260920,10:00:00,5000.00,ACHIEVED,60.00,BULL1',
    'SP500,T0100,STATS_IMMEDIATE,20260920,11:00:00,5001.00,INVALID,30.00,BEAR1']
ro=report(O,R1); rn=report(N,R1)
ok('#11 수정 전 이중집계 재현',ro[(True,100)]==(3,2,1),str(ro))
ok('#11 수정 후: 실제 신호 1 + 진짜 즉시판정 1 = 신호2/달성1/무효1',rn[(True,100)]==(2,1,1),str(rn))
# no-duplicate data must be identical
same=0
for seed in range(1,60):
    L=rand_lines(seed)
    L=[l for l in L if 'STATS_IMMEDIATE' not in l]  # without stats lines, report identical
    if report(O,L)==report(N,L): same+=1
ok('#11 STATS_IMMEDIATE 없는 데이터 59파일: 보고서 수정 전후 동일',same==59,f'({same}/59)')
# purge archive path: STATS_IMMEDIATE duplicate not double archived
def purge_arch(mod,lines):
    d=tempfile.mkdtemp(); p=mkfile(d,lines); mod._set_pos(p,os.path.getsize(p)); mod.purge_file(p,7,False)
    a=json.load(open(p.replace('.txt','.stats.json'))); return a.get('T0100',{})
A=['SP500,T0100,BULL1,20260910,10:00:00,5000.00,0,0','SP500,T0100,STATUS_ACHIEVED,20260910,10:00:00,5000.00,14:00:00(1H0M),x,BULL1','SP500,T0100,STATS_IMMEDIATE,20260910,10:00:00,5000.00,ACHIEVED,60.00,BULL1']
ao=purge_arch(O,A); an=purge_arch(N,A)
ok('#11 완전삭제 아카이브: 수정 전 이중집계',ao.get('signals')==2 and ao.get('achieved')==2,str((ao.get('signals'),ao.get('achieved'))))
ok('#11 완전삭제 아카이브: 수정 후 1건',an.get('signals')==1 and an.get('achieved')==1,str((an.get('signals'),an.get('achieved'))))
print('\n'.join(res))
