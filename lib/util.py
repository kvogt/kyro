# Utility functions
def ip(data): 
    if not isinstance(data, str): data = unlong(data)
    return '.'.join([str(ord(c)) for c in data])
def unip(data): return ''.join(chr(int(s)) for s in data.split('.'))
def prefix(data): return 'prefix'
    
def short(data): return struct.unpack('!H', data)[0]
def unshort(data): return struct.pack('!H', data)
def long(data): 
    if len(data) < 4:
        data = (chr(0) * (4 - len(data))) + data
    return struct.unpack('!I', data)[0]
def unlong(data): return struct.pack('!I', data)
def pick(length):
    if length == 1: return ord
    elif length == 2: return short
    else: return str
    
# Config parsing
def parseConfig(data):
    conf = {}
    for line in data.split('\n'):
        l = line.strip()
        if l.startswith('#'): continue
        try:
            key = l.split()[0]
            if len(l.split()) > 2:
                val = l.split()[1:]
            else:
                val = l.split()[1]
        except:
            pass
        conf[key] = val
    return conf
