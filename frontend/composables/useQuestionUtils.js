import katex from 'katex'
import 'katex/dist/katex.min.css'

export function renderMath(text) {
  if (!text) return ''
  let content = String(text)
  const mathBlocks = []

  content = content
    .replace(/\\\[([\s\S]*?)\\\]/g, (_, f) => `$$${f}$$`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_, f) => `$${f}$`)

  content = content.replace(/\$\$([\s\S]*?)\$\$/g, (_, formula) => {
    try {
      const html = katex.renderToString(formula.trim(), { throwOnError: false, displayMode: true })
      const token = `@@MATH${mathBlocks.length}@@`
      mathBlocks.push(html)
      return token
    } catch { return `<span class="latex-error">${formula}</span>` }
  })

  content = content.replace(/\$([^\n$]+?)\$/g, (_, formula) => {
    try {
      const html = katex.renderToString(formula.trim(), { throwOnError: false, displayMode: false })
      const token = `@@MATH${mathBlocks.length}@@`
      mathBlocks.push(html)
      return token
    } catch { return `<span class="latex-error">${formula}</span>` }
  })

  content = content
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
  content = content.replace(/@@MATH(\d+)@@/g, (_, i) => mathBlocks[Number(i)] || '')
  return content
}

export function isChoice(item) {
  return ['single_choice', 'multiple_choice', 'choice'].includes(
    (item.question_type || '').toLowerCase()
  )
}

export function parseChoices(content) {
  if (!content) return []
  const splitReg = /(?:^|\n)\s*[（(]?A[）)．.\s]/
  const splitIdx = content.search(splitReg)
  const optionStr = splitIdx >= 0 ? content.slice(splitIdx) : content

  const parts = optionStr.split(/\n?\s*[（(]?([B-D])[）)．.\s]/)
  const opts = []

  if (parts.length >= 3) {
    const firstMatch = optionStr.match(/[（(]?A[）)．.\s]\s*(.+?)(?=\s*[（(]?B[）)．.\s]|$)/s)
    if (firstMatch) opts.push({ key: 'A', text: firstMatch[1].trim() })
    for (let i = 1; i + 1 < parts.length; i += 2) {
      opts.push({ key: parts[i], text: parts[i + 1].trim() })
    }
  }

  if (opts.length < 2) {
    const lines = content.split('\n')
    for (const line of lines) {
      const m = line.trim().match(/^[（(]?([A-D])[）)．.\s]\s*(.+)/)
      if (m) opts.push({ key: m[1], text: m[2].trim() })
    }
  }
  return opts
}

const TYPE_MAP = { single_choice: '单选', multiple_choice: '多选', fill_blank: '填空', essay: '大题', choice: '选择' }
export const typeLabel = (t) => TYPE_MAP[t] || (t || '未知题型')

const DIFF_MAP = { 1: '简单', 2: '中等', 3: '困难' }
export const diffLabel = (d) => DIFF_MAP[d] || (d ? `难度${d}` : '未知')

export const diffClass = (d) => {
  if (d === 1) return 'diff-easy'
  if (d === 2) return 'diff-medium'
  if (d === 3) return 'diff-hard'
  return ''
}

export const isImageAvatar = (av) => typeof av === 'string' && (av.startsWith('http') || av.startsWith('/'))
