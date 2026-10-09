"""Browser verification against browser_design_preview.py and headless Edge CDP.
Run with the existing Python environment. Saves artifacts to .browser_validation.
Checks both themes at requested desktop, tablet, and mobile widths; no live AI calls.
"""
import base64,json,time,urllib.request,sys,os
from pathlib import Path
from websockets.sync.client import connect
root=Path(__file__).resolve().parents[1]
mode=sys.argv[1] if len(sys.argv)>1 else 'after'
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
    command('Page.enable')
    command('Page.bringToFront')
    command('Emulation.setFocusEmulationEnabled',dict(enabled=True))
    command('Page.navigate',dict(url='http://localhost:18653'))
    wait("!!document.querySelector('.st-key-ask_where_next button')")
    idle()
    viewport(1440)
    capture(mode+'_landing_1440')
    if mode=='before':
        js("document.querySelector('.st-key-landing_question textarea').focus()")
        command('Input.insertText',dict(text='Best county in PA'))
        click('.st-key-ask_where_next button')
        wait("!!document.querySelector('.st-key-nav_overview button')")
        click('.st-key-nav_overview button')
        idle()
        js("document.querySelector('.wn-summary-grid').scrollIntoView({block:'start',behavior:'instant'})")
        capture('before_dashboard_1440')
        print('Captured before landing and dashboard.')
    else:
        results=[]
        ax=command('Accessibility.getFullAXTree')['nodes']
        assert any(n.get('role',{}).get('value')=='button' and 'Switch to' in n.get('name',{}).get('value','') for n in ax), 'Theme button has no accessible name'
        for theme in ['dark','light']:
            if theme=='light':click('.st-key-theme_toggle button');idle()
            for width in [1440,1280,1024,768,390]:
                viewport(width)
                assert not js('document.documentElement.scrollWidth>innerWidth'),(theme,width,'landing overflow')
                assert js("(()=>{let r=[...document.querySelectorAll('.st-key-theme_toggle button')].find(e=>e.getBoundingClientRect().width>0).getBoundingClientRect();return r.width>=30&&r.width<=36&&r.right<=innerWidth&&r.top>=0})()")
                capture(f'after_landing_{theme}_{width}')
        click('.st-key-explore_dashboard button')
        wait("!!document.querySelector('.wn-summary-card')")
        idle()
        assert js("getComputedStyle(document.querySelector('.stApp')).backgroundColor==='rgb(245, 248, 246)'")
        # Theme changes must retain values, priorities, scenario, selection, and no AI requests.
        def state():
            return js("JSON.stringify({cards:[...document.querySelectorAll('.wn-summary-value')].map(e=>e.innerText),weights:[...document.querySelectorAll('input[type=range]')].map(e=>e.value),scenario:document.querySelector('.st-key-scenario input')?.value,selected:[...document.querySelectorAll('.st-key-chosen_counties [data-tag]')].map(e=>e.innerText)})")
        for theme in ['light','dark']:
            if theme=='dark':
                before=state();click('.st-key-theme_toggle button');idle();assert state()==before
            for width in [1440,1280,1024,768,390]:
                viewport(width)
                # Collapse native sidebar on narrow layouts.
                if width<=1024 and js("document.querySelector('[data-testid=stSidebar]')?.getBoundingClientRect().right>100"):
                    click('[data-testid=stSidebar] [data-testid=stBaseButton-headerNoPadding]')
                js("document.querySelector('.wn-summary-grid').scrollIntoView({block:'start',behavior:'instant'})")
                assert not js('document.documentElement.scrollWidth>innerWidth'),(theme,width,'dashboard overflow')
                assert js("[...document.querySelectorAll('.wn-summary-card')].every(e=>e.scrollWidth<=e.clientWidth&&e.scrollHeight<=e.clientHeight)"),(theme,width,'card clipping')
                capture(f'after_dashboard_{theme}_{width}')
                js("document.querySelector('.st-key-map_rankings').scrollIntoView({block:'start',behavior:'instant'})")
                capture(f'after_map_rankings_{theme}_{width}')
                js("document.querySelector('.st-key-analysis_overview').scrollIntoView({block:'start',behavior:'instant'})")
                capture(f'after_analysis_{theme}_{width}')
                results.append(f'{theme} {width}px: toggle, overflow, cards and screenshots')
        before=state()
        js("[...document.querySelectorAll('.st-key-theme_toggle button')].find(e=>e.getBoundingClientRect().width>0).focus()")
        for kind in ['keyDown','keyUp']:
            command('Input.dispatchKeyEvent',dict(type=kind,key='Enter',code='Enter',windowsVirtualKeyCode=13,nativeVirtualKeyCode=13,**({'text':'\r'} if kind=='keyDown' else {})))
        wait("getComputedStyle(document.querySelector('.stApp')).backgroundColor==='rgb(245, 248, 246)'")
        idle()
        assert state()==before
        assert not js("document.body.innerText.includes('Traceback')||document.body.innerText.includes('StreamlitAPIException')")
        (out/'design_visual_report.json').write_text(json.dumps(dict(passed=results),indent=2))
        print('\n'.join(results))
