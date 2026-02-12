import os

def tail(filename, n=100):
    if not os.path.exists(filename):
        print(f"{filename} not found")
        return
    with open(filename, 'rb') as f:
        f.seek(0, 2)
        size = f.tell()
        block = -1
        data = []
        while size > 0 and len(data) < n:
            if size - 1024 > 0:
                f.seek(size - 1024)
                data.insert(0, f.read(1024))
            else:
                f.seek(0)
                data.insert(0, f.read(size))
            size -= 1024
            lines = b''.join(data).splitlines()
            if len(lines) > n:
                break
    
    print(f"--- TAIL {filename} ---")
    for line in lines[-n:]:
        try:
            print(line.decode('utf-8'))
        except:
            print(line)

tail("perplexity_server/requests.log")
print("\n" + "="*50 + "\n")
tail("perplexity_server/bridge_debug.log")
