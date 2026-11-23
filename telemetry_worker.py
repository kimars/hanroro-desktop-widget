"""Read speaker loopback and system counters in a separate, killable process."""
import json,queue,sys,threading,time
from media_worker import stdio

BARS=32

def spectrum(samples,channels,rate):
    import numpy as np
    data=np.asarray(samples,dtype=np.float32)
    if channels>1:data=data[:len(data)//channels*channels].reshape(-1,channels).mean(axis=1)
    if len(data)<64:return [0.]*BARS
    data=data[-2048:];data=np.nan_to_num(data);amp=np.abs(np.fft.rfft(data*np.hanning(len(data))))*2/max(1,len(data));freq=np.fft.rfftfreq(len(data),1/rate)
    edges=np.geomspace(35,min(18000,rate*.48),BARS+1);out=[]
    for lo,hi in zip(edges[:-1],edges[1:]):
        bins=amp[(freq>=lo)&(freq<hi)]
        if not len(bins):value=float(amp[np.argmin(abs(freq-(lo+hi)/2))])
        else:value=float(np.max(bins))
        out.append(round(float(np.clip((20*np.log10(value+1e-7)+68)/65,0,1)),4))
    return out

class Counters:
    def __init__(self):
        import psutil
        self.psutil=psutil;psutil.cpu_percent(None);self.nvml=None;self.gpu=None
        try:
            import pynvml
            pynvml.nvmlInit();self.nvml=pynvml;self.gpu=pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:pass
    def sample(self):
        memory=self.psutil.virtual_memory();out={'cpu':round(self.psutil.cpu_percent(None),1),'ram':round(memory.percent,1),'ramUsed':round((memory.total-memory.available)/2**30,1),'ramTotal':round(memory.total/2**30,1),'gpu':None,'gpuUsed':None,'gpuTotal':None,'gpuName':''}
        if self.nvml and self.gpu:
            try:
                n=self.nvml;usage=n.nvmlDeviceGetUtilizationRates(self.gpu);mem=n.nvmlDeviceGetMemoryInfo(self.gpu);name=n.nvmlDeviceGetName(self.gpu)
                out.update(gpu=int(usage.gpu),gpuUsed=round(mem.used/2**30,1),gpuTotal=round(mem.total/2**30,1),gpuName=name.decode('utf-8','replace') if isinstance(name,bytes) else str(name))
            except Exception:pass
        return out
    def close(self):
        if self.nvml:
            try:self.nvml.nvmlShutdown()
            except Exception:pass

class Loopback:
    def __init__(self):
        self.enabled=False;self.stop=threading.Event();self.lock=threading.Lock();self.block=b'';self.channels=2;self.rate=48000;self.error='';self.device='';self.last_block=0
        threading.Thread(target=self.run,daemon=True).start()
    def snapshot(self):
        with self.lock:return (self.block if time.monotonic()-self.last_block<.25 else b''),self.channels,self.rate,self.error,self.device
    def run(self):
        while not self.stop.is_set():
            if not self.enabled:self.stop.wait(.2);continue
            try:
                import pyaudiowpatch as pa
                with pa.PyAudio() as audio:
                    device=audio.get_default_wasapi_loopback();channels=int(device['maxInputChannels']);rate=int(device['defaultSampleRate'])
                    def callback(data,count,timing,status):
                        with self.lock:self.block=data;self.last_block=time.monotonic();self.channels=channels;self.rate=rate;self.error='';self.device=str(device['name'])
                        return (None,pa.paContinue)
                    with audio.open(format=pa.paFloat32,channels=channels,rate=rate,frames_per_buffer=2048,input=True,input_device_index=device['index'],stream_callback=callback):
                        check=time.monotonic()
                        while self.enabled and not self.stop.wait(.1):
                            if time.monotonic()-check>3:
                                check=time.monotonic()
                                if audio.get_default_wasapi_loopback()['index']!=device['index']:break
            except Exception:
                with self.lock:self.error='출력 장치를 연결할 수 없습니다.';self.block=b''
                self.stop.wait(3)
            finally:
                with self.lock:self.block=b''

def run():
    out=None
    try:
        import numpy as np
        incoming=stdio('stdin',-10);out=stdio('stdout',-11);commands=queue.SimpleQueue();capture=Loopback();counters=Counters()
        def read():
            try:
                for line in incoming:
                    try:commands.put(json.loads(line))
                    except ValueError:pass
            finally:commands.put({'action':'stop'})
        threading.Thread(target=read,daemon=True).start();stats={};next_stats=0;next_emit=0;monitor=True;last_levels=[0.]*BARS
        try:
            while True:
                while not commands.empty():
                    command=commands.get()
                    if command.get('action')=='stop':return 0
                    if command.get('action')=='configure':capture.enabled=bool(command.get('audio'));monitor=bool(command.get('monitor'))
                now=time.monotonic()
                if now>=next_stats:
                    next_stats=now+1
                    if monitor:stats=counters.sample()
                if now>=next_emit:
                    next_emit=now+(.05 if capture.enabled else 1)
                    blob,channels,rate,error,device=capture.snapshot();levels=spectrum(np.frombuffer(blob,dtype=np.float32),channels,rate) if blob and capture.enabled else [0.]*BARS
                    last_levels=[max(value,old*.72) for value,old in zip(levels,last_levels)]
                    out.write(json.dumps({'levels':last_levels,'audioStatus':error if capture.enabled else '', 'device':device if capture.enabled else '',**stats})+'\n');out.flush()
                time.sleep(.01)
        finally:capture.stop.set();counters.close()
    except Exception as error:
        if out:out.write(json.dumps({'error':'시스템 정보 연결을 시작하지 못했습니다.','detail':str(error)[:300]})+'\n');out.flush()
        return 1
if __name__=='__main__':sys.exit(run())
