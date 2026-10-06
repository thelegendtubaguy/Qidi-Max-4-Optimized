"""Offline control-flow checks; GPIO readiness/data are synthetic, not hardware evidence."""
import ast
import hashlib
import sys
import json
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
ROOT=Path(sys.argv[1])
BASE=0x08008000; OBJ=0x20001000; ARGS=0x20002000; TABLE=0x20000300; EXIT=0x08010f00
GPIO=0x40010c00; DWT=0xe0001004
IMAGE=(ROOT/'firmware/QD_MAX4_THR_02.02.01.08_20260303.bin').read_bytes()
assert hashlib.sha256(IMAGE).hexdigest() == '1d34b4b0142f2a2047f08c2fae59d827bcee0adbd1563b4bd1de311dff8b2d62'

def firmware_case(samples, *, handler=0x0800dbcc, initialized=True, shutdown=False):
    u=Uc(UC_ARCH_ARM, UC_MODE_THUMB|UC_MODE_MCLASS)
    for addr,size in ((BASE,0x9000),(0x20000000,0x10000),(0x40010000,0x20000),(0xe0001000,0x1000)):
        u.mem_map(addr,size)
    u.mem_write(BASE,IMAGE)
    def put(addr,value): u.mem_write(addr,struct.pack('<I',value&0xffffffff))
    def get(addr): return struct.unpack('<I',u.mem_read(addr,4))[0]
    u.mem_write(0x2000006c,b'\x06');put(0x20000070,TABLE)
    put(TABLE+40,0x0800d479);put(TABLE+44,OBJ);put(ARGS,5)
    put(OBJ+0xc,GPIO);put(OBJ+0x10,16);put(OBJ+0x14,GPIO);put(OBJ+0x18,8);put(OBJ+0x24,20)
    if initialized:
        u.mem_write(OBJ+0x39,b'\x04');u.mem_write(OBJ+0x3a,b'\x11\x22\x33\x00')
    put(0x20000174,0x654321);put(OBJ+0x88,0x3f800000)
    u.mem_write(0x20000009,bytes([int(shutdown)]))
    pending=list(samples);current=[None];high=[False];edges=[0];clock=[0]
    transactions=[];responses=[];failure=[]
    def ret(): u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def read(uc,access,address,size,value,user):
        if address==DWT:
            clock[0]+=64;put(DWT,clock[0])
        elif address==GPIO+8:
            if high[0] and current[0] is not None and edges[0]<=24:
                bit=(current[0]>>(24-edges[0]))&1
            else:
                bit=int(not pending and current[0] is None)
            put(GPIO+8,bit*16)
    def write(uc,access,address,size,value,user):
        if address!=GPIO+0x10:return
        if value&8:
            high[0]=True;edges[0]+=1
        if value&(8<<16):high[0]=False
    def code(uc,addr,size,user):
        if addr==EXIT:uc.emu_stop();return
        if addr==0x0800da7c:
            assert pending,'read attempted without synthetic ready sample'
            current[0]=pending.pop(0);edges[0]=0
        if addr==0x0800db0e:
            transactions.append({'input':hex(current[0]),'decoded':hex(uc.reg_read(UC_ARM_REG_R0)),'clock_pulses':edges[0]})
            current[0]=None
        if addr==0x0800d140:
            # Stub pin reconfiguration only, preserving the requested descriptor.
            dest=uc.reg_read(UC_ARM_REG_R0);pin=uc.reg_read(UC_ARM_REG_R1)
            assert pin==20,pin
            put(dest,GPIO);put(dest+4,16);ret();return
        if addr==0x0800848c:
            desc=uc.reg_read(UC_ARM_REG_R0);n=uc.reg_read(UC_ARM_REG_R2);ptr=uc.reg_read(UC_ARM_REG_R3)
            wire_id=struct.unpack('<H',uc.mem_read(desc,2))[0]
            responses.append({'id':wire_id-128,'data':bytes(uc.mem_read(ptr,n)).hex()})
            ret();return
        if addr in (0x080099f8,0x080082d4):
            failure.append({'shutdown_function':hex(addr),'reason':uc.reg_read(UC_ARM_REG_R0)});uc.emu_stop()
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ,read);u.hook_add(UC_HOOK_MEM_WRITE,write)
    u.reg_write(UC_ARM_REG_SP,0x20007800);u.reg_write(UC_ARM_REG_LR,EXIT|1);u.reg_write(UC_ARM_REG_R0,ARGS)
    u.emu_start(handler|1,EXIT,count=100000)
    return {'transactions':transactions,'responses':responses,'shutdown':failure,'returned':u.reg_read(UC_ARM_REG_PC)==EXIT,'budget_exhausted':not failure and u.reg_read(UC_ARM_REG_PC)!=EXIT,'reference':hex(get(0x20000174)),'homing_reference_bits':hex(get(OBJ+0x88))}

firmware={
 'positive':firmware_case([0x123456]),
 'negative':firmware_case([0xfabcde]),
 'not_ready_existing_buffer':firmware_case([]),
 'not_ready_empty_buffer':firmware_case([],initialized=False),
 'zero_then_valid':firmware_case([0,0x123456]),
 'all_ones_then_valid':firmware_case([0xffffff,0x123456]),
 'four_all_ones':firmware_case([0xffffff]*4),
 'saturation':firmware_case([0x800000]),
 'saturation_already_shutdown':firmware_case([0x800000],shutdown=True),
 'zero_command_never_ready':firmware_case([],handler=0x0800dc20),
}
assert firmware['positive']['responses']==[{'id':-8,'data':'56341200'}]
assert firmware['negative']['responses']==[{'id':-8,'data':'debcfa00'}]
assert firmware['not_ready_existing_buffer']['responses'][0]['data']=='11223300'
assert firmware['not_ready_empty_buffer']['responses'][0]['data']==''
assert firmware['zero_then_valid']['responses'][0]['data']=='56341200'
assert firmware['all_ones_then_valid']['responses'][0]['data']=='56341200'
assert firmware['four_all_ones']['responses'][0]['data']=='ffffff00'
assert firmware['saturation']['shutdown'] and not firmware['saturation']['responses']
assert firmware['saturation_already_shutdown']['responses'][0]['data']=='00008000'
assert firmware['zero_command_never_ready']['budget_exhausted']
for case in firmware.values():
    for t in case['transactions']:
        assert t['input']==t['decoded']
        assert t['clock_pulses']==27

# Execute the exact extracted class, without importing serial devices or C helpers.
tree=ast.parse((ROOT/'host/serialhdl.py').read_text())
node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SerialRetryCommand')
namespace={'error':RuntimeError}
exec(compile(ast.Module(body=[node],type_ignores=[]),'serialhdl.py:SerialRetryCommand','exec'),namespace)
class Reactor:
    def __init__(self,serial):self.serial=serial;self.now=0.;self.pauses=[]
    def monotonic(self):return self.now
    def pause(self,t):
        self.pauses.append(t-self.now);self.now=t
        if self.serial.delivery=='during_wait':self.serial.callback({'data':b'first response'})
class Serial:
    def __init__(self,delivery):self.delivery=delivery;self.sends=0;self.callback=None;self.reactor=Reactor(self)
    def register_response(self,callback,name,oid):self.callback=callback
    def raw_send_wait_ack(self,*args):
        self.sends+=1
        if self.delivery=='before_ack':self.callback({'data':b'immediate'})
    raw_send=raw_send_wait_ack
host={}
for delivery in ('before_ack','during_wait','never'):
    s=Serial(delivery);q=namespace['SerialRetryCommand'](s,'query_cs1237_data',5)
    failure=None
    try:q.get_response([b'encoded-command'],1)
    except RuntimeError as exc:failure=str(exc)
    host[delivery]={'sends':s.sends,'pause_seconds':s.reactor.pauses,'error':failure,'handler_removed':s.callback is None}
assert host['before_ack']['sends']==1
assert host['during_wait']['sends']==2
assert host['never']['sends']==6
assert all(x['handler_removed'] for x in host.values())
print(json.dumps({'firmware':firmware,'host_retry':host},indent=2))
