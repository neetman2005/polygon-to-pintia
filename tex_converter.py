"""
LaTeX → Markdown 转换器

将 Polygon 题面的 .tex 文件转换为 Markdown 格式。
处理常见的 LaTeX 标记，保留 Markdown 兼容的语法。
"""

import re
from typing import Callable


# 读取示例文件的回调: (filename: str) -> str | None
FileReader = Callable[[str], str | None]


def convert_tex_to_md(tex_content: str, file_reader: FileReader | None = None) -> str:
    """
    将 LaTeX 题面内容转换为 Markdown 格式。
    
    参数:
        tex_content: .tex 文件内容
        file_reader: 用于读取 \\exmpfile 引用文件的回调
    
    转换规则:
    - \\textbf{...} → **...**
    - \\textit{...} → *...*
    - \\emph{...} → *...*
    - \\text{...} (独立) → **...**
    - \\texttt{...} → `...`
    - \\begin{itemize} / \\end{itemize} → Markdown 列表
    - \\begin{enumerate} / \\end{enumerate} → Markdown 有序列表
    - \\item → * / 1.
    - $...$ / $$...$$ → 保留
    - \\section{...} → ## ...
    - \\subsection{...} → ### ...
    - \\url{...} → 保留
    - \\InputFile → ### 输入格式:
    - \\OutputFile → ### 输出格式:
    - \\Note → ### 样例解释
    - \\Examples → ### 样例
    - \\exmpfile{input}{output} \\to 展开为 Markdown 代码块
    """
    lines = tex_content.split('\n')
    result_lines = []
    
    # 状态跟踪
    in_itemize = False      # itemize 环境
    in_enumerate = False    # enumerate 环境
    enumerate_counter = 0   # enumerate 计数器
    in_math_block = False   # $$...$$ 块级数学模式
    prev_blank = False      # 前一行是否为空
    in_example = False      # \\begin{example}...\\end{example}
    in_problem = False      # \\begin{problem}...\\end{problem}
    example_index = 0       # 样例编号
    
    for line in lines:
        stripped = line.strip()
        
        # === 处理块级数学模式（$$...$$） ===
        if stripped.startswith('$$') and not in_math_block:
            result_lines.append(stripped)
            in_math_block = True
            prev_blank = False
            continue
        if stripped.endswith('$$') and in_math_block:
            result_lines.append(stripped)
            in_math_block = False
            prev_blank = False
            continue
        if in_math_block:
            result_lines.append(line)
            prev_blank = False
            continue
        
        # === 处理 \\begin{problem} / \\end{problem} ===
        m_begin_problem = re.match(r'\\begin\{problem\}', stripped)
        if m_begin_problem:
            in_problem = True
            prev_blank = False
            continue
        
        m_end_problem = re.match(r'\\end\{problem\}', stripped)
        if m_end_problem:
            in_problem = False
            prev_blank = False
            continue
        
        # === 处理 \\begin{example} / \\end{example} ===
        m_begin_example = re.match(r'\\begin\{example\}', stripped)
        if m_begin_example:
            in_example = True
            prev_blank = False
            continue
        
        if in_example:
            m_end_example = re.match(r'\\end\{example\}', stripped)
            if m_end_example:
                in_example = False
                prev_blank = False
                continue
            
            # 处理 \\exmpfile{input}{output}
            m_exmp = re.match(r'\\exmpfile\{(.+?)\}\{(.+?)\}%?', stripped)
            if m_exmp:
                inp_name = m_exmp.group(1)
                out_name = m_exmp.group(2)
                example_index += 1
                
                if file_reader:
                    inp_content = file_reader(inp_name)
                    out_content = file_reader(out_name)
                    
                    if inp_content is not None:
                        inp_content = inp_content.rstrip('\n')
                        result_lines.append('')
                        result_lines.append(f'### 输入样例{example_index}:')
                        result_lines.append('')
                        result_lines.append('```in')
                        result_lines.append(inp_content)
                        result_lines.append('```')
                        result_lines.append('')
                    
                    if out_content is not None:
                        out_content = out_content.rstrip('\n')
                        result_lines.append(f'### 输出样例{example_index}:')
                        result_lines.append('')
                        result_lines.append('```out')
                        result_lines.append(out_content)
                        result_lines.append('```')
                        result_lines.append('')
                else:
                    # 无法读取文件时，保留引用信息
                    result_lines.append('')
                    result_lines.append(f'*[样例 {example_index}: `{inp_name}` / `{out_name}`]*')
                    result_lines.append('')
                
                prev_blank = True
                continue
            
            # example 内的其他行：跳过
            continue
        
        # === 处理 enumerate 环境 ===
        m_begin_enum = re.match(r'\\begin\{enumerate\}', stripped)
        if m_begin_enum:
            in_enumerate = True
            enumerate_counter = 0
            result_lines.append('')  # 空行分隔
            prev_blank = True
            continue
        
        if in_enumerate:
            m_end_enum = re.match(r'\\end\{enumerate\}', stripped)
            if m_end_enum:
                in_enumerate = False
                enumerate_counter = 0
                result_lines.append('')  # 空行分隔
                prev_blank = True
                continue
            
            m_item = re.match(r'\\item\s+(.*)', stripped)
            if m_item:
                enumerate_counter += 1
                content = _convert_inline(m_item.group(1))
                result_lines.append(f'{enumerate_counter}. {content}')
                prev_blank = False
                continue
            else:
                # enumerate 内的非 item 行：附加到上一个 item
                if result_lines and not prev_blank:
                    result_lines[-1] += ' ' + _convert_inline(stripped)
                else:
                    result_lines.append(_convert_inline(stripped))
                prev_blank = False
                continue
        
        # === 处理 itemize 环境 ===
        m_begin_itemize = re.match(r'\\begin\{itemize\}', stripped)
        if m_begin_itemize:
            in_itemize = True
            result_lines.append('')  # 空行分隔
            prev_blank = True
            continue
        
        if in_itemize:
            m_end_itemize = re.match(r'\\end\{itemize\}', stripped)
            if m_end_itemize:
                in_itemize = False
                result_lines.append('')  # 空行分隔
                prev_blank = True
                continue
            
            m_item = re.match(r'\\item\s+(.*)', stripped)
            if m_item:
                content = _convert_inline(m_item.group(1))
                result_lines.append(f'* {content}')
                prev_blank = False
                continue
            else:
                # itemize 内的非 item 行：附加到上一个 item
                if result_lines and not prev_blank:
                    result_lines[-1] += ' ' + _convert_inline(stripped)
                else:
                    result_lines.append(_convert_inline(stripped))
                prev_blank = False
                continue
        
        # === 处理特殊命令（无参数的独立命令） ===
        if re.match(r'\\InputFile\s*$', stripped):
            result_lines.append('')
            result_lines.append('### 输入格式:')
            result_lines.append('')
            prev_blank = True
            continue
        
        if re.match(r'\\OutputFile\s*$', stripped):
            result_lines.append('')
            result_lines.append('### 输出格式:')
            result_lines.append('')
            prev_blank = True
            continue
        
        if re.match(r'\\Note\s*$', stripped):
            result_lines.append('')
            result_lines.append('### 样例解释')
            result_lines.append('')
            prev_blank = True
            continue
        
        if re.match(r'\\Examples\s*$', stripped):
            result_lines.append('')
            result_lines.append('### 样例')
            result_lines.append('')
            prev_blank = True
            continue
        
        # === 处理 section 命令 ===
        m_section = re.match(r'\\section\{(.+)\}', stripped)
        if m_section:
            result_lines.append('')
            result_lines.append(f'## {m_section.group(1)}')
            result_lines.append('')
            prev_blank = True
            continue
        
        m_subsection = re.match(r'\\subsection\{(.+)\}', stripped)
        if m_subsection:
            result_lines.append('')
            result_lines.append(f'### {m_subsection.group(1)}')
            result_lines.append('')
            prev_blank = True
            continue
        
        # === 空行处理 ===
        if stripped == '':
            result_lines.append('')
            prev_blank = True
            continue
        
        # === 普通文本行：内联转换 ===
        converted = _convert_inline(stripped)
        result_lines.append(converted)
        prev_blank = False
    
    # 清理多余空行
    cleaned = []
    prev_empty = False
    for line in result_lines:
        if line.strip() == '':
            if not prev_empty:
                cleaned.append(line)
            prev_empty = True
        else:
            cleaned.append(line)
            prev_empty = False
    
    return '\n'.join(cleaned).strip() + '\n'


def _convert_inline(text: str) -> str:
    """
    转换内联 LaTeX 标记为 Markdown。
    保护 $...$ 数学模式内的内容不被修改。
    """
    # 先保护数学模式
    math_regions = []
    
    def _save_math(m):
        math_regions.append(m.group(0))
        return f'\x00MATH{len(math_regions) - 1}\x00'
    
    # 保护 $$...$$（通常已被换行处理，但防御性保留）
    text = re.sub(r'\$\$.+?\$\$', _save_math, text, flags=re.DOTALL)
    # 保护 $...$
    text = re.sub(r'\$[^$]+\$', _save_math, text)
    
    # === 转换 LaTeX 命令（按嵌套深度处理） ===
    # \textbf{...} → **...**
    text = _replace_nested('\\textbf{', '}', text, '**', '**')
    
    # \textit{...} → *...*
    text = _replace_nested('\\textit{', '}', text, '*', '*')
    
    # \emph{...} → *...*
    text = _replace_nested('\\emph{', '}', text, '*', '*')
    
    # \texttt{...} → `...`
    text = _replace_nested('\\texttt{', '}', text, '`', '`')
    
    # \text{...} (独立，不在数学模式内) → **...**
    # 注意：这会匹配 \text{...} 但需要小心嵌套
    text = _replace_nested('\\text{', '}', text, '**', '**')
    
    # \underline{...} → 保留原文
    # 不转换，移除外层 \underline{ 和 }
    text = _replace_nested('\\underline{', '}', text, '', '')
    
    # \url{...} → 保留原文
    text = _replace_nested('\\url{', '}', text, '', '')
    
    # \texttt{...} 如果在 math 外被保留，现在已经是 `...` 了
    
    # 处理 \texttt{...} 未被匹配的情况（可能跨行等原因）
    # 已经在上面处理
    
    # 恢复数学模式
    for i, region in enumerate(math_regions):
        text = text.replace(f'\x00MATH{i}\x00', region)
    
    return text


def _replace_nested(prefix: str, suffix: str, text: str, 
                    md_open: str, md_close: str) -> str:
    """
    替换嵌套的 LaTeX 命令为 Markdown 格式。
    
    例如: \\textbf{foo \\textit{bar}} → **foo *bar***
    
    使用手动扫描来处理任意深度的嵌套。
    """
    result = []
    i = 0
    plen = len(prefix)
    
    while i < len(text):
        # 查找 prefix
        if text[i:i+plen] == prefix and i + plen < len(text):
            # 找到开始，扫描匹配的 }
            j = i + plen
            depth = 1
            k = j
            while k < len(text) and depth > 0:
                if text[k] == '{':
                    depth += 1
                elif text[k] == '}':
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            
            if depth == 0:
                # 找到了匹配的 }
                inner = text[j:k]
                # 递归处理内部
                inner_converted = _replace_nested(prefix, suffix, inner, md_open, md_close)
                result.append(md_open + inner_converted + md_close)
                i = k + 1
                continue
        
        result.append(text[i])
        i += 1
    
    return ''.join(result)
