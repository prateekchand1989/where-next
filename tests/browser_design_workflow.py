"""Browser verification against browser_design_preview.py and headless Edge CDP.
Run with the existing Python environment. Saves artifacts to .browser_validation.
Checks both themes at requested desktop, tablet, and mobile widths; no live AI calls.
"""
import base64,json,time,urllib.request,sys,os
from pathlib import Path
from websockets.sync.client import connect
root=Path(__file__).resolve().parents[1]
mode='workflow'
out=root/'.browser_validation'
out.mkdir(exist_ok=True)
pages=json.load(urllib.request.urlopen('http://localhost:19224/json/list'))
page=next(p for p in pages if p['id']==os.environ['WHERE_NEXT_BROWSER_PAGE_ID']) if os.environ.get('WHERE_NEXT_BROWSER_PAGE_ID') else next(p for p in sorted(pages, key=lambda p: '18653' not in p.get('url','')) if p['type']=='page')
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
    import sys
    sys.path.insert(0,str(root))
    import pandas as pd
    import numpy as np
    from core import LABELS, PRESETS, load_data, score_counties
    assert len(LABELS)==4
    downloads=out/'main_downloads'
    downloads.mkdir(exist_ok=True)
    command('Browser.setDownloadBehavior',dict(behavior='allowAndName',downloadPath=str(downloads),eventsEnabled=True))
    def calls():
        path=out/os.environ.get('WHERE_NEXT_MOCK_LOG', 'ai_calls.jsonl')
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    def key(name,code,modifiers=0):
        for kind in ['keyDown','keyUp']:
            command('Input.dispatchKeyEvent',dict(type=kind,key=name,windowsVirtualKeyCode=code,modifiers=modifiers))
    def sidebar(opened=True):
        idle()
        visible=js("document.querySelector('[data-testid=stSidebar]')?.getBoundingClientRect().right>100")
        if opened and not visible:
            click('[data-testid=stExpandSidebarButton]')
            wait("document.querySelector('[data-testid=stSidebar]')?.getBoundingClientRect().right>100")
        elif not opened and visible:
            click('[data-testid=stSidebar] [data-testid=stBaseButton-headerNoPadding]')
    def select(widget,label):
        js("document.querySelector('.st-key-"+widget+" input').focus()")
        key('a',65,2)
        command('Input.insertText',dict(text=label))
        wait("!!document.querySelector('[role=option]')")
        key('ArrowDown',40)
        command('Input.dispatchKeyEvent',dict(type='keyDown',key='Enter',code='Enter',windowsVirtualKeyCode=13,text='\r'))
        command('Input.dispatchKeyEvent',dict(type='keyUp',key='Enter',code='Enter',windowsVirtualKeyCode=13))
        wait("document.querySelector('.st-key-"+widget+" input').value==="+json.dumps(label))
        idle()
    def weights():
        wait("(()=>{let w=[...document.querySelectorAll('input[type=range]')].map(e=>Number(e.value));return w.length===4&&w.reduce((a,b)=>a+b,0)===100&&document.querySelector('.stApp')?.getAttribute('data-test-script-state')==='notRunning'})()")
        return js("[...document.querySelectorAll('input[type=range]')].map(e=>Number(e.value))")
    data,_=load_data()
    def check_results():
        w=weights()
        scored=score_counties(data,w)
        ranked=scored[scored.complete]
        expected=[f'{row.county}, {row.state}' for _,row in ranked.head(5).iterrows()]
        wait("JSON.stringify([...document.querySelectorAll('.wn-table tbody th[scope=row]')].map(e=>e.textContent))==="+json.dumps(json.dumps(expected,separators=(',',':'))))
        assert js("[...document.querySelectorAll('.wn-table tbody .wn-score')].map(e=>e.textContent)")==[f'{value:.1f}' for value in ranked.head(5).score]
        wait("(()=>{let t=document.querySelector('.st-key-county_map .js-plotly-plot')?._fullData.find(t=>t.colorbar?.title?.text==='Score');let z="+json.dumps(ranked.score.tolist())+";return t&&Array.from(t.z).length===z.length&&Array.from(t.z).every((v,i)=>Math.abs(v-z[i])<1e-8)})()")
        map_values=js("(()=>{let t=document.querySelector('.st-key-county_map .js-plotly-plot')._fullData.find(t=>t.colorbar?.title?.text==='Score');return {fips:Array.from(t.locations),values:Array.from(t.z)}})()")
        assert map_values['fips']==ranked.fips.tolist()
        assert np.allclose(map_values['values'],ranked.score)
        return scored,ranked
    command('Page.enable')
    command('Page.bringToFront')
    command('Emulation.setFocusEmulationEnabled',dict(enabled=True))
    command('Page.navigate',dict(url='http://localhost:' + os.environ.get('WHERE_NEXT_MOCK_PORT', '18653')))
    wait("!!document.querySelector('.st-key-explore_dashboard button')")
    idle()
    viewport(1440)
    start_calls=len(calls())
    click('.st-key-explore_dashboard button')
    wait("!!document.querySelector('.wn-summary-card')")
    idle()
    assert len(calls())==start_calls
    completed=[]
    for width in [1440,768,390]:
        viewport(width)
        sidebar(True)
        for scenario in PRESETS:
            if js("document.querySelector('.st-key-scenario input').value")!=scenario:
                select('scenario',scenario)
            click('.st-key-default_weights button')
            wait("JSON.stringify([...document.querySelectorAll('input[type=range]')].map(e=>Number(e.value)))==="+json.dumps(json.dumps(PRESETS[scenario],separators=(',',':'))))
            idle()
            before,ranked=check_results()
            js("document.querySelector('input[type=range][aria-label=\"Market reach\"]').focus()")
            key('Home',36)
            wait("document.querySelector('input[type=range][aria-label=\"Market reach\"]').value==='0'")
            check_results()
            click('.st-key-default_weights button')
            wait("JSON.stringify([...document.querySelectorAll('input[type=range]')].map(e=>Number(e.value)))==="+json.dumps(json.dumps(PRESETS[scenario],separators=(',',':'))))
            idle()
            check_results()
            assert len(calls())==start_calls
            if scenario=='Temperature-controlled':
                assert js("[...document.querySelectorAll('.wn-table tbody tr')].every(e=>e.cells[3].textContent==='Unavailable')")
            if width<1024:sidebar(False)
            assert not js('document.documentElement.scrollWidth>innerWidth')
            completed.append(f'{width}px {scenario}: four-factor controls, ranks, map, unavailable rent, no AI calls')
            print('PASS '+completed[-1],flush=True)
            sidebar(True)
    viewport(1280)
    sidebar(True)
    select('scenario','General merchandise')
    click('.st-key-default_weights button')
    idle()
    scored,ranked=check_results()
    target=ranked.iloc[2]
    select('ranking_selection',f'{target.county}, {target.state}')
    wait("document.querySelector('.wn-summary-value').textContent==="+json.dumps(f'{target.county}, {target.state}'))
    wait("document.querySelector('.wn-table tr[aria-current=true] th').textContent==="+json.dumps(f'{target.county}, {target.state}'))
    marker=js("(()=>{let t=document.querySelector('.st-key-county_map .js-plotly-plot')._fullData.find(t=>t.type==='scattermap');return {lat:Array.from(t.lat),lon:Array.from(t.lon)}})()")
    assert marker=={'lat':[target.lat],'lon':[target.lon]}
    check_results()
    # Download main's original result schema and compare its actual scores.
    previous={p:p.stat().st_mtime_ns for p in downloads.iterdir() if p.is_file()}
    command('Runtime.evaluate',dict(expression="document.querySelector('[data-testid=stDownloadButton] button').click()",userGesture=True))
    end=time.time()+45
    changed=[]
    while time.time()<end:
        changed=[p for p in downloads.iterdir() if p.is_file() and not p.name.endswith('.crdownload') and (p not in previous or p.stat().st_mtime_ns!=previous[p])]
        if changed:break
        time.sleep(.25)
    assert changed,'CSV download did not finish'
    frame=pd.read_csv(changed[0],dtype={'fips':str})
    assert frame.fips.tolist()==scored.fips.tolist()
    assert np.allclose(frame.score,scored.score,equal_nan=True)
    assert 'score_coverage' not in frame and 'leasing_cost_psf_year' not in frame
    # Ask twice with the main-only mock provider, then inspect saved history.
    click('.st-key-nav_ask button')
    wait("!!document.querySelector('textarea[data-testid=stChatInputTextArea]')")
    for number,question in enumerate(['Explain the current leader','Explain number three'],1):
        js("document.querySelector('textarea[data-testid=stChatInputTextArea]').focus()")
        command('Input.insertText',dict(text=question))
        key('Enter',13)
        wait("document.querySelector('.st-key-latest_answer')?.textContent.includes('Screening evidence')")
        wait("document.querySelector('.stApp')?.getAttribute('data-test-script-state')==='notRunning'")
        end=time.time()+30
        while len(calls())<start_calls+number*2 and time.time()<end:time.sleep(.25)
        assert len(calls())==start_calls+number*2
    assert calls()[-1]['target']==target.fips
    assert calls()[-1]['score']==target.score
    wait("!!document.querySelector('.st-key-response_1 details')")
    count=len(calls())
    click('.st-key-theme_toggle button')
    idle()
    assert len(calls())==count
    click('.st-key-nav_overview button')
    wait("!!document.querySelector('.st-key-nav_ask button')")
    idle()
    check_results()
    assert len(calls())==count
    capture('main_workflow_verified')
    completed.append('1280px: synchronized county selection, original CSV schema, two mocked answers, saved history, theme/navigation without new calls')
    assert not js("document.body.textContent.includes('StreamlitAPIException')||document.body.textContent.includes('Traceback')")
    (out/'main_workflow_report.json').write_text(json.dumps(dict(passed=completed,live_model_calls=0),indent=2))
    print('PASS '+completed[-1],flush=True)
