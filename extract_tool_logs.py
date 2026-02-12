"""Extract tool-related log entries from bridge_debug.log -> output file"""
import os

log_path = 'perplexity_server/bridge_debug.log'
out_path = 'tool_log_extract.txt'
size = os.path.getsize(log_path)

with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
    f.seek(max(0, size - 500000))
    f.readline()
    lines = f.readlines()

keywords = ['Tool Parser', 'tool_use', 'read_file', 'TOOL_CALL', 
            'Parsed tool', 'Correcting', 'Claude Prompt] Found', 'tools_available',
            'Session] Updated', 'Session] Using', 'Parsed Chinese',
            'content_block_start', 'stop_reason']

results = []
for i, line in enumerate(lines):
    line_s = line.rstrip()
    for kw in keywords:
        if kw in line_s:
            results.append(f"[{i:5d}] {line_s[:500]}")
            break

with open(out_path, 'w', encoding='utf-8') as f:
    f.write(f"Log size: {size:,} bytes, Lines scanned: {len(lines)}, Matches: {len(results)}\n\n")
    for r in results:
        f.write(r + '\n')

print(f"Done. {len(results)} matches written to {out_path}")
