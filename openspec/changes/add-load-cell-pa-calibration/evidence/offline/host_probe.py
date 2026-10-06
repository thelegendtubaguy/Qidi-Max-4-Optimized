import sys, types, json
pkg=types.ModuleType('extras'); pkg.__path__=[sys.argv[1]]; sys.modules['extras']=pkg
for name in ('bus','hx711','mcu'):
    mod=types.ModuleType(name);sys.modules[name]=mod;sys.modules['extras.'+name]=mod;setattr(pkg,name,mod)
import extras.cs1237 as c
print('MODULE', sorted(x for x in dir(c) if not x.startswith('__')))
print('CLASS', sorted(x for x in dir(c.CS1237) if not x.startswith('__')))
class Command:
    def __init__(self, name): self.name=name
    def send(self,*args,**kwargs):
        print('SEND',self.name,repr(args),repr(kwargs))
        return {'data':b'\x34\x12\x00\x00','config':60,'homing':0,'trigger_clock':0}
class MCU:
    def lookup_command(self,*args,**kwargs): print('LOOKUP',args,kwargs);return Command(args[0])
    lookup_query_command=lookup_command
    def add_config_cmd(self,*args,**kwargs): print('CONFIG',args,kwargs)
    def register_response(self,*args,**kwargs): print('REGISTER',repr(args[1:]),kwargs)
    def alloc_command_queue(self): return 1
    def print_time_to_clock(self,t): return int(t*72000000)
    def is_fileoutput(self): return False
    def clock32_to_clock64(self,c): return c
    def clock_to_print_time(self,c): return c/72000000
class Printer:
    def get_reactor(self):return types.SimpleNamespace(monotonic=lambda:0)
obj=c.CS1237.__new__(c.CS1237)
obj.mcu=MCU();obj.oid=5;obj.dout_pin='PB4';obj.sclk_pin='PB3';obj.printer=Printer();obj.cmd_queue=1;obj.dout_params={'pin':'PB4'};obj.sck_params={'pin':'PB3'};obj.cs_fil_f=90;obj.trigger_force=100;obj.trigger_threshold=100;obj.adc_voltage_diff=100
for method,args in [('_build_config',()),('_handle_ready',()),('read_origin_data',()),('zero_home',()),('setup_home',(10.0,1,1,2,0.001)),('clear_home',())]:
    print('METHOD',method)
    try: print('RESULT',getattr(obj,method)(*args))
    except Exception as e: print(type(e).__name__,str(e))
print('ATTRS',obj.__dict__)
