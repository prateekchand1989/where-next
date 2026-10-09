"""Browser verification against browser_design_preview.py and headless Edge CDP.
Run with the existing Python environment. Saves artifacts to .browser_validation.
Checks both themes at requested desktop, tablet, and mobile widths; no live AI calls.
"""
import base64,json,time,urllib.request,sys
from pathlib import Path
from websockets.sync.client import connect
root=Path(__file__).resolve().parents[1]
mode='interactions'
out=root/'.browser_validation'
out.mkdir(exist_ok=True)
pages=json.load(urllib.request.urlopen('http://localhost:19224/json/list'))
page=next(p for p in sorted(pages, key=lambda p: '18653' not in p.get('url','')) if p['type']=='page')
with connect(page['webSocketDebuggerUrl'],max_size=32*1024*1024) as ws:
    counter=0
    def command(method,params=None):
        global counter
        counter+=1
        ws.send(json.dumps(dict(id=counter,method=method,params=params or {})))
        while True:
            r=json.loads(ws.recv())
            if r.get('id')==counter:
                if 'error' in r:raise RuntimeError(r['error'])
                return r.get('result',{})
    def js(expr):
        r=command('Runtime.evaluate',dict(expression=expr,returnByValue=True))
        if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
        return r.get('result',{}).get('value')
    def wait(expr):
        end=time.time()+60
        while time.time()<end:
            if js(expr):return
            time.sleep(.25)
        raise AssertionError(expr)
    def click(sel):
        pos=js('(()=>{let e=[...document.querySelectorAll('+json.dumps(sel)+')].find(e=>e.getBoundingClientRect().width>0);e.scrollIntoView({block:"center",behavior:"instant"});let r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()')
        command('Input.dispatchMouseEvent',dict(type='mouseMoved',x=pos['x'],y=pos['y']))
        time.sleep(.15)
        for kind in ['mousePressed','mouseReleased']:
            command('Input.dispatchMouseEvent',dict(type=kind,x=pos['x'],y=pos['y'],button='left',clickCount=1))
        time.sleep(1)
    def viewport(w):
        command('Emulation.setDeviceMetricsOverride',dict(width=w,height=1000,deviceScaleFactor=1,mobile=False))
        time.sleep(1)
    def capture(name):
        (out/(name+'.png')).write_bytes(base64.b64decode(command('Page.captureScreenshot',dict(format='png'))['data']))
    def idle():
        wait("document.querySelector('.stApp')?.getAttribute('data-test-script-state')==='notRunning'")
        time.sleep(.5)
        wait("[...document.querySelectorAll('[data-stale=true]')].every(e=>e.getBoundingClientRect().height===0)")
    import sys
    sys.path.insert(0,str(root))
    from core import load_data, score_counties, PRESETS
    from analysis_intent import STATES
    from question_targeting import STATE_NAMES
    data=load_data()[0]
    def key(name,code,modifiers=0):
        for kind in ['keyDown','keyUp']:
            command('Input.dispatchKeyEvent',dict(type=kind,key=name,windowsVirtualKeyCode=code,modifiers=modifiers,**({'text':'\r'} if name=='Enter' and kind=='keyDown' else {})))
    def calls():
        p=out/'ai_calls.jsonl'
        return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []
    def sidebar(opened=True):
        visible=js("document.querySelector('[data-testid=stSidebar]')?.getBoundingClientRect().right>100")
        if opened and not visible:
            click('[data-testid=stExpandSidebarButton]');idle()
        elif not opened and visible:
            click('[data-testid=stSidebar] [data-testid=stBaseButton-headerNoPadding]')
            time.sleep(.3)
    def selected():
        return js("[...document.querySelectorAll('.st-key-candidate_states [data-tag]')].map(e=>e.getAttribute('aria-label'))")
    def scope(expected):
        wait("JSON.stringify([...document.querySelectorAll('.st-key-candidate_states [data-tag]')].map(e=>e.getAttribute('aria-label')).sort())==="+json.dumps(json.dumps(sorted(expected),separators=(',',':'))))
        idle()
        assert js("[...document.querySelectorAll('.st-key-candidate_states [data-tag]')].every(e=>e.getBoundingClientRect().width>=42)")
        assert js("document.querySelector('.st-key-candidate_states [data-testid=stMultiSelect]').getBoundingClientRect().height<110")
    def add_state(code):
        js("document.querySelector('.st-key-candidate_states input').focus()")
        command('Input.insertText',dict(text=code))
        wait("!!document.querySelector('[role=option]')")
        key('ArrowDown',40);key('Enter',13)
        idle()
    def select_scenario(label):
        js("document.querySelector('.st-key-scenario input').focus()")
        key('a',65,2);command('Input.insertText',dict(text=label))
        wait("!!document.querySelector('[role=option]')")
        key('ArrowDown',40);key('Enter',13)
        wait("document.querySelector('.st-key-scenario input').value==="+json.dumps(label));idle()
    def nav(key_name):
        sidebar(True)
        selector='.st-key-'+key_name+' button'
        pos=js("(()=>{let e=document.querySelector("+json.dumps(selector)+"),r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
        for kind in ['mousePressed','mouseReleased']:
            command('Input.dispatchMouseEvent',dict(type=kind,button='left',clickCount=1,**pos))
        idle()
    def nav_geometry():
        rows=js("[...document.querySelectorAll('.st-key-primary_navigation button')].map(e=>{let r=e.getBoundingClientRect();return {label:e.textContent.trim(),w:r.width,h:r.height,hit:e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}})")
        assert len(rows)==3 and max(r['w'] for r in rows)-min(r['w'] for r in rows)<1 and all(r['h']==40 and r['hit'] for r in rows),rows
        assert not js("!!document.querySelector('.st-key-workspace_navigation')")
        assert not js('document.documentElement.scrollWidth>innerWidth')
        return rows
    def valid_answer(states):
        idle()
        wait("document.querySelector('.st-key-latest_answer')?.textContent.includes('Screening evidence')")
        assert js("(()=>{let e=document.querySelector('[data-testid=stText]');return !!e&&getComputedStyle(e).color===getComputedStyle(document.querySelector('.stApp')).color})()"), 'Current question must remain readable in both themes'
        result=calls()[-1]
        assert result['kind']=='answer' and result['candidate_states']==sorted(states),result
        w=list(result['weights'].values())
        scored=score_counties(data,w)
        ranked=scored[scored.complete & scored.state.isin(states)]
        assert result['target']==ranked.iloc[1].fips and abs(result['score']-ranked.iloc[1].score)<1e-8,result
        assert result['top_five']==[dict(fips=r.fips,county=r.county,state=r.state,score=r.score,rank=i) for i,(_,r) in enumerate(ranked.head(5).iterrows(),1)]
        assert js("document.querySelector('.st-key-latest_answer').textContent.includes("+json.dumps(ranked.iloc[1].county)+")")
        assert not js("document.body.textContent.includes('Ask again for an updated answer')")
    def theme(name):
        expected='rgb(8, 15, 13)' if name=='dark' else 'rgb(245, 248, 246)'
        if js("getComputedStyle(document.querySelector('.stApp')).backgroundColor")!=expected:
            click('.st-key-theme_toggle button');idle()
        wait("getComputedStyle(document.querySelector('.stApp')).backgroundColor==="+json.dumps(expected))
    command('Page.enable');command('Page.bringToFront')
    command('Emulation.setFocusEmulationEnabled',dict(enabled=True))
    command('Page.navigate',dict(url='http://localhost:18653'))
    wait("!!document.querySelector('.st-key-ask_where_next button')");idle()
    report=out/'surgical_browser_report.json'
    results=[]
    for width in ([int(v) for v in sys.argv[1:]] if len(sys.argv)>1 else [1440,390]):
        viewport(width)
        for name in ['dark','light']:
            theme(name)
            assert not js("!!document.querySelector('[data-testid=stSidebar]')")
            assert not js("!!document.querySelector('[data-testid=stExpandSidebarButton]')")
            assert not js("!!document.querySelector('.st-key-primary_navigation')")
            assert not js('document.documentElement.scrollWidth>innerWidth')
            capture(f'surgical_landing_{name}_{width}')
            start=len(calls())
            click('.st-key-explore_dashboard button');idle()
            sidebar(True);nav_geometry();scope(STATES)
            click('.st-key-candidate_states button[aria-label="Remove OH"]');scope([s for s in STATES if s!='OH'])
            add_state('OH');scope(STATES)
            assert len(calls())==start
            nav('start_new_question');idle()
            assert not js("!!document.querySelector('[data-testid=stSidebar]')")
            js("document.querySelector('.st-key-landing_question textarea').focus()")
            command('Input.insertText',dict(text='Which is the second-best county in NJ?'))
            click('.st-key-ask_where_next button');valid_answer(['NJ'])
            assert len(calls())==start+2
            original=calls()[-1]
            latest='.st-key-latest_answer details'
            assert js("document.querySelector("+json.dumps(latest)+").open")
            # A manually collapsed answer stays collapsed through analytical changes.
            if width<=1024:sidebar(False)
            click(latest+' summary')
            assert not js("document.querySelector("+json.dumps(latest)+").open")
            sidebar(True);add_state('PA');scope(['NJ','PA'])
            click('.st-key-candidate_states button[aria-label="Remove NJ"]');scope(['PA'])
            assert len(calls())==start+2
            assert not js("document.querySelector("+json.dumps(latest)+").open")
            assert js("document.querySelector('.st-key-latest_answer').textContent.includes('earlier analytical configuration')")
            if width<=1024:sidebar(False)
            click(latest+' summary')
            assert js("document.querySelector("+json.dumps(latest)+").open")
            assert js("document.querySelector('.st-key-latest_answer').textContent.includes('Historical answer')")
            assert js("document.querySelector('.st-key-latest_answer').textContent.includes('NJ')")
            sidebar(True)
            js("document.querySelector('input[type=range][aria-label=\"Market reach\"]').focus()")
            key('Home',36);time.sleep(2);idle()
            click('.st-key-apply_ai_weights button');idle()
            select_scenario('Temperature-controlled')
            assert len(calls())==start+2 and calls()[-1]==original
            assert js("document.querySelector("+json.dumps(latest)+").open")
            nav('nav_overview');nav_geometry()
            assert js("document.querySelector('.st-key-insights_overview')?.textContent.includes('earlier analytical configuration') || document.body.textContent.includes('earlier analytical configuration')")
            nav('nav_ask');nav_geometry()
            click('.st-key-theme_toggle button');idle();theme(name)
            assert len(calls())==start+2
            if width<=1024:sidebar(False)
            js("document.querySelector('.st-key-followup_question textarea').focus()")
            command('Input.insertText',dict(text='Which is the second-best county in PA now?'))
            key('Enter',13);time.sleep(2);valid_answer(['PA'])
            assert len(calls())==start+4
            assert js("[...document.querySelectorAll('.st-key-history_answers details')].every(e=>!e.open)")
            assert js("document.querySelector('.st-key-history_answers').textContent.includes('NJ')")
            capture(f'surgical_answers_{name}_{width}')
            if width==1440 and name=='light':
                (out/'mock_fail_next_answer').write_text('one mocked failure')
                js("document.querySelector('.st-key-followup_question textarea').focus()")
                command('Input.insertText',dict(text='Explain the second-best county in PA.'))
                key('Enter',13);time.sleep(2);idle()
                wait("!!document.querySelector('.st-key-retry_analysis button')")
                failed=len(calls())
                sidebar(True);add_state('NY');scope(['NY','PA'])
                assert len(calls())==failed
                if width<=1024:sidebar(False)
                click('.st-key-retry_analysis button');valid_answer(['NY','PA'])
                assert len(calls())==failed+1
            nav('start_new_question');idle()
            assert not js("!!document.querySelector('[data-testid=stSidebar]')")
            results.append(f'{width}px {name}: sidebar absent on landing; live controls without AI; historical panel state preserved; explicit follow-up uses current evidence')
            print('PASS '+results[-1],flush=True)
            report.write_text(json.dumps(dict(passed=results,live_api_requests=0),indent=2),encoding='utf-8')
