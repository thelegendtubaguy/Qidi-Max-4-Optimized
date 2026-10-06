import struct, json, sys, hashlib
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn.arm_const import *
BASE=0x08008000
BIN=(Path(sys.argv[1])/'firmware/QD_MAX4_THR_02.02.01.08_20260303.bin').read_bytes()
assert hashlib.sha256(BIN).hexdigest() == '1d34b4b0142f2a2047f08c2fae59d827bcee0adbd1563b4bd1de311dff8b2d62'
OBJ=0x20001000; ARGS=0x20002000; TABLE=0x20000300; EXIT=0x08010f00
GPIO=0x40010c00; DWT=0xe0001004

def run(handler, ready=True, adc=0x123456, rest_ticks=None):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    for addr,size in [(BASE,0x9000),(0x20000000,0x10000),(0x40010000,0x20000),(0xe0001000,0x1000)]:u.mem_map(addr,size)
    u.mem_write(BASE,BIN)
    def put(a,v):u.mem_write(a,struct.pack('<I',v & 0xffffffff))
    def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    u.mem_write(0x2000006c,b'\x06');put(0x20000070,TABLE)
    put(TABLE+5*8,0x0800d479);put(TABLE+5*8+4,OBJ)
    put(ARGS,5);put(ARGS+4,rest_ticks or 0);put(ARGS+8,0)
    put(OBJ+0xc,GPIO);put(OBJ+0x10,16);put(OBJ+0x14,GPIO);put(OBJ+0x18,8)
    put(OBJ+0x24,20);put(OBJ+0x78,0xabcdef)
    u.mem_write(OBJ+0x39,b'\x04');u.mem_write(OBJ+0x3a,b'\x11\x22\x33\x00')
    put(0x20000174,0x654321);put(OBJ+0x88,0x3f800000)
    put(GPIO+8,0 if ready else 16)
    reads=[];responses=[];events=[];clock=[0]
    before={'reference':get(0x20000174),'threshold_reference_bits':get(OBJ+0x88)}
    def on_read(uc,access,address,size,value,user):
        if address==DWT:
            clock[0]+=10000;put(DWT,clock[0])
    def code(uc,addr,size,user):
        if addr==EXIT:uc.emu_stop();return
        if addr==0x0800da7c:
            reads.append(adc);uc.reg_write(UC_ARM_REG_R0,adc);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if addr in (0x08008270,0x080081f8):
            events.append({'timer_call':hex(addr),'object':hex(uc.reg_read(UC_ARM_REG_R0))})
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if addr==0x0800848c:
            desc=uc.reg_read(UC_ARM_REG_R0);oid=uc.reg_read(UC_ARM_REG_R1);n=uc.reg_read(UC_ARM_REG_R2);ptr=uc.reg_read(UC_ARM_REG_R3)
            wire_id=struct.unpack('<H',uc.mem_read(desc,2))[0]
            record={'response_id':wire_id-128,'oid':oid,'r2':n,'r3':hex(ptr)}
            if wire_id-128 in (-8,-12,-13):record['data']=bytes(uc.mem_read(ptr,n)).hex()
            responses.append(record);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if addr in (0x080099f8,0x080082d4):raise RuntimeError('firmware shutdown '+hex(addr))
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ,on_read)
    u.reg_write(UC_ARM_REG_SP,0x20007800);u.reg_write(UC_ARM_REG_LR,EXIT|1);u.reg_write(UC_ARM_REG_R0,ARGS)
    u.emu_start(handler|1,EXIT,count=200000)
    if u.reg_read(UC_ARM_REG_PC)!=EXIT:raise RuntimeError('instruction budget exhausted')
    return {'handler':hex(handler),'ready':ready,'adc_reads':len(reads),'responses':responses,'timer_events':events,'poll_interval_ticks':get(OBJ+0x30),'before':before,'after':{'reference':get(0x20000174),'threshold_reference_bits':get(OBJ+0x88)}}

cases={
 'raw_ready':run(0x0800dbcc),
 'raw_not_ready':run(0x0800dbcc,ready=False),
 'raw_zero_rejected':run(0x0800dbcc,adc=0),
 'raw_all_ones_fourth_attempt':run(0x0800dbcc,adc=0xffffff),
 'zero_read_only':run(0x0800bd74),
 'zero':run(0x0800dc20),
 'periodic_start_72000':run(0x0800c00c,rest_ticks=72000),
 'periodic_start_144000':run(0x0800c00c,rest_ticks=144000),
 'periodic_stop':run(0x0800c00c,rest_ticks=0),
}
assert cases['raw_ready']['responses'][0]['data']=='56341200'
assert cases['raw_not_ready']['responses'][0]['data']=='11223300'
assert cases['raw_ready']['before']==cases['raw_ready']['after']
assert cases['raw_zero_rejected']['responses'][0]['data']=='11223300'
assert cases['raw_all_ones_fourth_attempt']['responses'][0]['data']=='ffffff00'
assert cases['raw_all_ones_fourth_attempt']['adc_reads']==4
assert cases['zero_read_only']['adc_reads']==0
assert cases['zero']['adc_reads']==10
assert cases['zero']['after']['reference']==0x123456
assert cases['periodic_start_72000']['poll_interval_ticks']==36000
assert cases['periodic_start_144000']['poll_interval_ticks']==36000
print(json.dumps(cases,indent=2))
