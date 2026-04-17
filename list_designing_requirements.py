#!/usr/bin/env python3
"""查询所有方案设计中状态的需求"""

import json
import subprocess
import sys

def main():
    try:
        result = subprocess.run([
            'lark-cli', 'base', '+record-list',
            '--base-token', 'Bv3zbmsObahXOUsOSgBcSSlin1c',
            '--table-id', 'AI Tutor需求收集管理',
            '--limit', '50'
        ], capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode != 0:
            print(f"Error: {result.stderr}", file=sys.stderr)
            return
        
        data = json.loads(result.stdout)
        
        if 'data' not in data or 'data' not in data['data']:
            print("No data found")
            return
        
        records = data['data']['data']
        
        print('=== 方案设计中状态的需求 ===\n')
        
        count = 0
        for idx, record in enumerate(records, 1):
            name = record[0] if len(record) > 0 else 'Unknown'
            status = record[13][0] if len(record) > 13 and record[13] else '未知'
            priority = record[16][0] if len(record) > 16 and record[16] else '未知'
            
            if status == '方案设计中':
                count += 1
                print(f'{idx}. {name}')
                print(f'   优先级: {priority}')
                print()
        
        print(f'总计: {count}个需求处于"方案设计中"状态')
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)

if __name__ == '__main__':
    main()
