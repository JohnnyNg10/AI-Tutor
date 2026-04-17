#!/usr/bin/env python3
"""查询飞书需求池中所有需求及其行号"""

import json
import subprocess

def main():
    result = subprocess.run([
        'lark-cli', 'base', '+record-list',
        '--base-token', 'Bv3zbmsObahXOUsOSgBcSSlin1c',
        '--table-id', 'AI Tutor需求收集管理',
        '--limit', '50'
    ], capture_output=True, text=True)
    
    data = json.loads(result.stdout)
    records = data['data']['data']
    
    print('=== 所有需求列表（按行号） ===\n')
    for idx, record in enumerate(records, 1):
        name = record[0]
        status = record[13][0] if record[13] else '未知'
        priority = record[16][0] if record[16] else '未知'
        
        marker = ""
        if status == '方案设计中':
            marker = " 【方案设计中】"
        
        print(f'{idx}. {name}{marker}')
        print(f'   状态: {status} | 优先级: {priority}')
        print()

if __name__ == '__main__':
    main()
