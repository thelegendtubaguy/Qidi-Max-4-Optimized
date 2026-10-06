import json, struct, hashlib, sys, zlib
from pathlib import Path
root=Path(sys.argv[1])
b=(root/'firmware/QD_MAX4_THR_02.02.01.08_20260303.bin').read_bytes()
assert hashlib.sha256(b).hexdigest() == '1d34b4b0142f2a2047f08c2fae59d827bcee0adbd1563b4bd1de311dff8b2d62'
j=json.loads(zlib.decompress(b[0x7534:]))
base=0x08008000;table=0x080101c4
commands={}
for name, ident in j['commands'].items():
    offset=table-base+16*ident
    msgid,numargs,flags,numparams,types,func=struct.unpack_from('<HBBIII',b,offset)
    assert msgid==ident,(name,msgid,ident)
    assert func&1 and base <= (func&~1) < base+len(b),(name,func)
    commands[name]={'id':ident,'record':hex(table+16*ident),'handler':hex(func&~1),'args':numargs,'param_count':numparams}
responses={}
by_id={ident:name for name,ident in j['responses'].items()}
for addr in range(0x0800f494,0x0800f4d4,8):
    wire_id,maxsize,nparams,params=struct.unpack_from('<HBBI',b,addr-base)
    msgid=wire_id-128
    if msgid in by_id:responses[by_id[msgid]]={'id':msgid,'descriptor':hex(addr),'max_size':maxsize,'parameter_count':nparams}
report={'sha256':hashlib.sha256(b).hexdigest(),'flash_base':hex(base),'command_table':hex(table),'commands_checked':len(commands),'cs1237_commands':{k:v for k,v in commands.items() if '1237' in k},'sensor_responses':responses}
print(json.dumps(report,indent=2))
