#!/usr/bin/env python3
"""查询飞书需求池中"方案设计中"状态的需求"""

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
    
    print('=== 方案设计中状态的需求 ===')
    print()
    
    count = 0
    for idx, record in enumerate(records, 1):
        name = record[0]
        status = record[13][0] if record[13] else '未知'
        priority = record[16][0] if record[16] else '未知'
        
        if status == '方案设计中':
            count += 1
            print(f'{idx}. {name}')
            print(f'   优先级: {priority}')
            print()
    
    print(f'总计: {count}个需求处于"方案设计中"状态')

if __name__ == '__main__':
    main()
