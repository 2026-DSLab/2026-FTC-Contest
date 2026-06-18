import json
import sys

with open('c:/Users/user/Desktop/code/2026-FTC-Contest/results/20260618_162626_여러_건설사가_공공기관이_발주한_공사.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

laws = data.get('_pipeline_trace', {}).get('mcp', {}).get('laws', [])
for law in laws:
    print('Title:', law.get('title'))
    content = law.get('content', '')
    print('Length:', len(content))
    print('Has 제19조:', '제19조' in content)
    print('Has 제40조:', '제40조' in content)
    print('-'*40)
