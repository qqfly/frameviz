"""Common API microbenchmark; no renderer, hardware-GPU or end-user performance claim."""
import json,os,pathlib,subprocess,tempfile,time
import numpy as np
from frameviz.client import FrameVizClient
from host_smoke import free_port
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=pathlib.Path(os.environ.get('FRAMEVIZ_EVIDENCE',ROOT/'.validation/evidence'))
results=[]
for label,exe in [('baseline',ROOT/'.validation/baseline-bin/frameviz-server'),('candidate',ROOT/'packages/frameviz-server/target/debug/frameviz-server')]:
    for run in range(3):
        with tempfile.TemporaryDirectory(prefix='frameviz-perf-') as temp:
            tmp=pathlib.Path(temp);port=free_port();discovery=tmp/'host.json';log=open(tmp/'server.log','w')
            process=subprocess.Popen([str(exe),str(port)],env=dict(os.environ,FRAMEVIZ_DISCOVERY_PATH=str(discovery),FRAMEVIZ_LOG_DIR=str(tmp/'logs')),stdout=log,stderr=log)
            c=None
            try:
                for _ in range(100):
                    if discovery.exists():break
                    time.sleep(.05)
                token=json.loads(discovery.read_text())['token'];c=FrameVizClient(f'ws://127.0.0.1:{port}',token=token);c.connect()
                scene=c.send_command('create_scene',{})['scene_id'];samples=[]
                for i in range(330):
                    start=time.perf_counter()
                    h=c.send_command('add_primitive',{'scene_id':scene,'type':'box'})['handle']
                    c.send_command('remove_object',{'scene_id':scene,'handle':h})
                    if i>=30:samples.append((time.perf_counter()-start)*1000)
                results.append({'variant':label,'run':run+1,'cycles':len(samples),'p50_ms':float(np.percentile(samples,50)),'p95_ms':float(np.percentile(samples,95))})
            finally:
                if c:c.close()
                process.terminate();process.wait(timeout=10);log.close()
OUT.mkdir(parents=True,exist_ok=True);(OUT/'host-comparison.json').write_text(json.dumps({'scope':'same current Python SDK, sequential box add/remove, debug Host, no viewer; 30 warmup + 300 measured cycles per run','results':results},indent=2))
print(json.dumps(results,indent=2))
