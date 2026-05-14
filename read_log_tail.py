import sys
logfile = sys.argv[1] if len(sys.argv) > 1 else r'D:\JM\cgxr\CGXR\train_log.txt'
with open(logfile, 'rb') as f:
    f.seek(0, 2)
    size = f.tell()
    print(f"File size: {size} bytes")
    f.seek(max(0, size - 4096))
    tail = f.read().decode('utf-8', errors='replace')
import re
lines = re.split(r'[\r\n]+', tail)
non_empty = [l.strip() for l in lines if l.strip()]
for l in non_empty[-30:]:
    print(l)
