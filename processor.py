"""
Polygon to Pintia - 核心处理逻辑

负责：
1. 从 zip 中查找 tests 文件夹
2. 解析和校验测试文件
3. 转换为 Unix 格式 (UTF-8, LF)
4. 生成目标 zip 包
"""

import io
import os
import re
import zipfile
from typing import Callable


class ProcessingError(Exception):
    """处理过程中的致命错误"""
    pass


class ProcessingWarning:
    """处理过程中的警告信息"""
    def __init__(self, level: str, message: str):
        self.level = level  # 'warning' | 'error'
        self.message = message
    
    def __str__(self):
        return f"[{self.level.upper()}] {self.message}"


def find_tests_folder(zf: zipfile.ZipFile) -> str | None:
    """
    在 zip 文件中查找 tests 文件夹。
    支持 Windows 和 Unix 路径分隔符。
    返回 tests 文件夹在 zip 内的路径前缀（以 / 结尾），若未找到返回 None。
    """
    all_names = zf.namelist()
    
    # 收集所有目录
    dirs = set()
    for name in all_names:
        # 规范化路径分隔符
        normalized = name.replace('\\', '/')
        # 提取目录部分
        parts = normalized.rsplit('/', 1)
        if len(parts) > 1:
            dirs.add(parts[0] + '/')
        # 如果 name 本身以 / 结尾，它就是一个目录
        if normalized.endswith('/'):
            dirs.add(normalized)
    
    # 查找名为 "tests" 的目录（不区分大小写）
    candidates = []
    for d in dirs:
        # 获取目录的最后一部分名称
        d_clean = d.rstrip('/')
        dir_name = d_clean.rsplit('/', 1)[-1] if '/' in d_clean else d_clean
        if dir_name.lower() == 'tests':
            # 计算深度（越浅越好）
            depth = d_clean.count('/')
            candidates.append((depth, d))
    
    # 也检查根目录下的 tests（可能目录条目不完整）
    for name in all_names:
        normalized = name.replace('\\', '/')
        parts = normalized.split('/')
        for i, part in enumerate(parts):
            if part.lower() == 'tests' and i < len(parts) - 1:
                prefix = '/'.join(parts[:i+1]) + '/'
                if prefix not in [c[1] for c in candidates]:
                    depth = i
                    candidates.append((depth, prefix))
    
    if not candidates:
        return None
    
    # 返回最浅的 tests 目录
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def parse_test_files(zf: zipfile.ZipFile, tests_prefix: str):
    """
    解析 tests 文件夹中的文件。
    
    返回:
        test_data: dict, key=id(int), value={'input': path, 'output': path|None}
        orphan_outputs: list of paths (只有 .a 没有对应输入的文件)
        invalid_names: list of paths (名称不符合格式的文件)
        warnings: list of ProcessingWarning
    """
    all_names = zf.namelist()
    tests_prefix_norm = tests_prefix.replace('\\', '/')
    
    # 收集 tests 文件夹下的所有文件（不包括子目录）
    test_files = []
    for name in all_names:
        normalized = name.replace('\\', '/')
        if normalized.startswith(tests_prefix_norm) and not normalized.endswith('/'):
            relative = normalized[len(tests_prefix_norm):]
            # 只处理直接子文件，不处理子目录中的文件
            if '/' not in relative:
                test_files.append((normalized, relative))
    
    # 解析文件名
    # 输入文件: {id}（无后缀）
    # 输出文件: {id}.a
    input_pattern = re.compile(r'^(\d+)$')
    output_pattern = re.compile(r'^(\d+)\.a$', re.IGNORECASE)
    
    input_files: dict[int, str] = {}   # id -> zip_path
    output_files: dict[int, str] = {}  # id -> zip_path
    invalid_names: list[str] = []
    warnings: list[ProcessingWarning] = []
    
    for zip_path, filename in test_files:
        m_input = input_pattern.match(filename)
        m_output = output_pattern.match(filename)
        
        if m_input:
            file_id = int(m_input.group(1))
            if file_id in input_files:
                warnings.append(ProcessingWarning(
                    'warning',
                    f'发现重复的输入文件 ID={file_id}: "{filename}"，将使用后发现的文件'
                ))
            input_files[file_id] = zip_path
        elif m_output:
            file_id = int(m_output.group(1))
            if file_id in output_files:
                warnings.append(ProcessingWarning(
                    'warning',
                    f'发现重复的输出文件 ID={file_id}: "{filename}"，将使用后发现的文件'
                ))
            output_files[file_id] = zip_path
        else:
            invalid_names.append(filename)
    
    # 警告无效文件名
    if invalid_names:
        warnings.append(ProcessingWarning(
            'warning',
            f'发现 {len(invalid_names)} 个名称不符合格式的文件（已忽略）: {", ".join(invalid_names[:10])}'
            + ('...' if len(invalid_names) > 10 else '')
        ))
    
    # 构建 test_data
    all_ids = set(input_files.keys()) | set(output_files.keys())
    test_data: dict[int, dict] = {}
    orphan_inputs: list[int] = []
    orphan_outputs: list[int] = []
    
    for file_id in sorted(all_ids):
        inp = input_files.get(file_id)
        out = output_files.get(file_id)
        
        if inp and out:
            test_data[file_id] = {'input': inp, 'output': out}
        elif inp and not out:
            test_data[file_id] = {'input': inp, 'output': None}
            orphan_inputs.append(file_id)
        elif out and not inp:
            test_data[file_id] = {'input': None, 'output': out}
            orphan_outputs.append(file_id)
    
    # 警告孤儿文件
    if orphan_inputs:
        warnings.append(ProcessingWarning(
            'warning',
            f'以下 ID 只找到了输入文件（缺少对应的 .a 输出文件）: {", ".join(map(str, orphan_inputs))}'
        ))
    if orphan_outputs:
        warnings.append(ProcessingWarning(
            'warning',
            f'以下 ID 只找到了输出文件（缺少对应的输入文件）: {", ".join(map(str, orphan_outputs))}'
        ))
    
    # 验证 ID 连续性
    if test_data:
        ids = sorted(test_data.keys())
        
        # 检查是否均为正整数
        non_positive = [i for i in ids if i <= 0]
        if non_positive:
            warnings.append(ProcessingWarning(
                'warning',
                f'发现非正整数的 ID: {", ".join(map(str, non_positive))}'
            ))
        
        positive_ids = [i for i in ids if i > 0]
        if positive_ids:
            # 检查连续性
            min_id = min(positive_ids)
            max_id = max(positive_ids)
            expected = set(range(min_id, max_id + 1))
            missing = sorted(expected - set(positive_ids))
            if missing:
                warnings.append(ProcessingWarning(
                    'warning',
                    f'测试 ID 不连续，缺少以下 ID: {", ".join(map(str, missing))}'
                ))
            
            # 检查是否从 1 开始
            if min_id != 1:
                warnings.append(ProcessingWarning(
                    'warning',
                    f'测试 ID 不是从 1 开始（最小 ID: {min_id}）'
                ))
    
    return test_data, invalid_names, warnings


def convert_to_unix_utf8(raw_bytes: bytes) -> bytes:
    """
    将文件内容转换为 Unix 格式（UTF-8 编码，LF 换行符）。
    
    尝试多种编码来解码原始内容，然后以 UTF-8 重新编码，
    并统一换行符为 LF。
    """
    text = None
    detected_encoding = None
    
    # 尝试常见编码
    encodings_to_try = [
        'utf-8',
        'utf-8-sig',
        'gbk',
        'gb2312',
        'gb18030',
        'big5',
        'cp1252',
        'latin-1',
        'cp1251',  # Cyrillic
    ]
    
    # 首先检查 BOM
    if raw_bytes.startswith(b'\xef\xbb\xbf'):
        # UTF-8 BOM
        text = raw_bytes[3:].decode('utf-8')
        detected_encoding = 'utf-8-sig'
    elif raw_bytes.startswith(b'\xff\xfe'):
        # UTF-16 LE BOM
        text = raw_bytes[2:].decode('utf-16-le')
        detected_encoding = 'utf-16-le'
    elif raw_bytes.startswith(b'\xfe\xff'):
        # UTF-16 BE BOM
        text = raw_bytes[2:].decode('utf-16-be')
        detected_encoding = 'utf-16-be'
    
    if text is None:
        for encoding in encodings_to_try:
            try:
                text = raw_bytes.decode(encoding)
                detected_encoding = encoding
                break
            except (UnicodeDecodeError, LookupError):
                continue
    
    if text is None:
        # 最后手段：latin-1 不会失败
        text = raw_bytes.decode('latin-1')
        detected_encoding = 'latin-1'
    
    # 统一换行符为 LF
    # 先处理 \r\n -> \n，再处理剩余的 \r -> \n
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # 编码为 UTF-8（不带 BOM）
    return text.encode('utf-8')


# 单个 zip 文件的大小上限（80MB，Pintia 平台限制）
MAX_ZIP_SIZE = 80 * 1024 * 1024  # 80,000,000 字节


def _measure_compressed_size(files: list[tuple[str, bytes]]) -> int:
    """测量一组文件在 DEFLATE 压缩后的实际大小（字节）。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for arcname, content in files:
            zf.writestr(arcname, content)
    return buf.tell()


def create_output_zips(
    zf: zipfile.ZipFile,
    test_data: dict,
    base_name: str,
    temp_dir: str,
    progress_callback: Callable[[int, int, str], None] | None = None
) -> tuple[list[dict], list[ProcessingWarning]]:
    """
    创建目标 zip 包（支持超过 80MB 时自动分卷）。

    先收集所有文件内容及其解压后的大小，按 ID 顺序分组，
    保证每组解压后总大小 ≤ MAX_ZIP_SIZE（从而压缩后一定 ≤ 80MB），
    然后将每组写入独立的 zip 文件。

    参数:
        zf: 原始 zip 文件
        test_data: {id: {'input': path, 'output': path}}
        base_name: 基础文件名（不含扩展名）
        temp_dir: 临时目录
        progress_callback: 进度回调

    返回:
        (outputs, warnings)
        outputs: [{'path': str, 'name': str, 'size': int, 'test_count': int, 'id_range': str}, ...]
    """
    warnings = []
    total = len(test_data)

    # —— 第 1 步：收集所有文件内容（内存中） ——
    if progress_callback:
        progress_callback(0, total, '正在读取测试文件...')

    all_files = []  # [(arcname, content_bytes), ...]
    for file_id in sorted(test_data.keys()):
        data = test_data[file_id]

        if data['input']:
            try:
                raw = zf.read(data['input'])
                converted = convert_to_unix_utf8(raw)
                all_files.append((f"{file_id}.in", converted))
            except Exception as e:
                warnings.append(ProcessingWarning(
                    'warning',
                    f'处理输入文件 ID={file_id} 时出错: {str(e)}'
                ))

        if data['output']:
            try:
                raw = zf.read(data['output'])
                converted = convert_to_unix_utf8(raw)
                all_files.append((f"{file_id}.out", converted))
            except Exception as e:
                warnings.append(ProcessingWarning(
                    'warning',
                    f'处理输出文件 ID={file_id} 时出错: {str(e)}'
                ))

    if not all_files:
        return [], warnings

    # —— 第 2 步：从原始 zip 计算实际压缩比率（零额外开销） ——
    if progress_callback:
        progress_callback(0, total, '正在估算压缩比率...')

    # 从原始 zip 中获取测试文件的压缩统计
    total_orig_uncomp = 0.0
    total_orig_comp = 0.0
    for file_id in sorted(test_data.keys()):
        data = test_data[file_id]
        for key in ('input', 'output'):
            if data[key]:
                try:
                    info = zf.getinfo(data[key])
                    total_orig_uncomp += info.file_size
                    total_orig_comp += info.compress_size
                except Exception:
                    pass

    if total_orig_uncomp > 0:
        orig_ratio = total_orig_comp / total_orig_uncomp
    else:
        orig_ratio = 0.5

    # 加 10% 安全余量（UTF-8 转换可能略微改变大小）
    ratio = min(orig_ratio * 1.10, 1.0)

    # —— 第 3 步：按估算大小贪心分组（O(n)） ——
    if progress_callback:
        progress_callback(0, total, '正在规划分卷...')

    groups = []          # [[(arcname, bytes), ...], ...]
    current_group = []
    current_est = 0.0
    SAFETY = 0.95        # 在 80MB 基础上再留 5% 余量
    limit = MAX_ZIP_SIZE * SAFETY

    for arcname, content in all_files:
        est = len(content) * ratio
        if current_est + est > limit and current_group:
            groups.append(current_group)
            current_group = []
            current_est = 0.0
        current_group.append((arcname, content))
        current_est += est

    if current_group:
        groups.append(current_group)

    # —— 第 4 步：写入 zip 文件并验证大小 ——
    outputs = []
    num_groups = len(groups)
    total_files_processed = 0

    for group_idx, group in enumerate(groups, 1):
        if num_groups > 1:
            output_name = f"{base_name}-tests-pintia-{group_idx}.zip"
        else:
            output_name = f"{base_name}-tests-pintia.zip"

        output_path = os.path.join(temp_dir, output_name)
        if os.path.exists(output_path):
            os.remove(output_path)

        if progress_callback:
            progress_callback(
                group_idx, num_groups,
                f'正在生成第 {group_idx}/{num_groups} 个压缩包...'
            )

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as out_zf:
            for arcname, content in group:
                out_zf.writestr(arcname, content)
                total_files_processed += 1

        output_size = os.path.getsize(output_path)

        # 验证实际大小未超限
        if output_size > MAX_ZIP_SIZE:
            warnings.append(ProcessingWarning(
                'warning',
                f'{output_name} 实际大小 ({output_size / 1024 / 1024:.1f} MB) 超过 80MB 限制，'
                f'请手动检查或拆分'
            ))

        # 计算该分卷的 ID 范围
        ids_in_group = set()
        for arcname, _ in group:
            try:
                file_id = int(arcname.split('.')[0])
                ids_in_group.add(file_id)
            except ValueError:
                pass
        if ids_in_group:
            id_range = f"{min(ids_in_group)}-{max(ids_in_group)}"
        else:
            id_range = "?"

        outputs.append({
            'path': output_path,
            'name': output_name,
            'size': output_size,
            'test_count': len(ids_in_group),
            'id_range': id_range,
        })

    if num_groups > 1:
        warnings.append(ProcessingWarning(
            'info',
            f'压缩包超过 80MB，已自动分为 {num_groups} 个分卷'
        ))

    return outputs, warnings


def process_polygon_zip(
    zip_path: str,
    temp_dir: str,
    progress_callback: Callable[[int, int, str], None] | None = None
) -> dict:
    """
    处理 Polygon 包的主函数。
    
    参数:
        zip_path: 输入 zip 文件路径
        temp_dir: 临时目录路径
        progress_callback: 进度回调
    
    返回:
        result: {
            'success': bool,
            'output_path': str | None,
            'output_name': str | None,
            'output_size': int | None,
            'test_count': int,
            'warnings': list[ProcessingWarning],
            'error': str | None,
            'test_summary': list[dict] | None,  # 每个测试用例的摘要
        }
    """
    result = {
        'success': False,
        'output_path': None,
        'output_name': None,
        'output_size': None,
        'outputs': [],    # 所有输出 zip 的列表（支持分卷）
        'test_count': 0,
        'warnings': [],
        'error': None,
        'test_summary': None,
        'statements': [],  # 题面处理结果
    }
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # 1. 查找 tests 文件夹
            if progress_callback:
                progress_callback(0, 100, '正在查找 tests 文件夹...')
            
            tests_prefix = find_tests_folder(zf)
            if tests_prefix is None:
                result['error'] = '未在压缩包中找到 tests 文件夹。\n请确认该压缩包是 Polygon 的 Full 包。'
                result['warnings'].append(ProcessingWarning('error', '未找到 tests 文件夹'))
                return result
            
            # 2. 解析测试文件
            if progress_callback:
                progress_callback(0, 100, f'找到 tests 文件夹: {tests_prefix}，正在解析文件...')
            
            test_data, invalid_names, parse_warnings = parse_test_files(zf, tests_prefix)
            result['warnings'].extend(parse_warnings)
            
            if not test_data:
                result['error'] = f'tests 文件夹 ({tests_prefix}) 中没有找到任何有效的测试文件。'
                result['warnings'].append(ProcessingWarning('error', 'tests 文件夹为空'))
                return result
            
            # 3. 生成基础文件名
            input_basename = os.path.splitext(os.path.basename(zip_path))[0]
            
            # 4. 创建输出 zip（支持分卷）
            if progress_callback:
                progress_callback(0, len(test_data), '正在生成目标压缩包...')
            
            outputs, convert_warnings = create_output_zips(
                zf, test_data, input_basename, temp_dir, progress_callback
            )
            result['warnings'].extend(convert_warnings)
            
            if not outputs:
                result['error'] = '未能生成任何输出文件。'
                result['warnings'].append(ProcessingWarning('error', '输出为空'))
                return result
            
            # 5. 填充结果（兼容单文件和多分卷）
            result['outputs'] = outputs
            result['output_path'] = outputs[0]['path']
            result['output_name'] = outputs[0]['name']
            result['output_size'] = outputs[0]['size']
            result['test_count'] = len(test_data)
            
            # 6. 生成测试摘要
            test_summary = []
            for file_id in sorted(test_data.keys()):
                info = {'id': file_id, 'input': None, 'output': None}
                
                if test_data[file_id]['input']:
                    try:
                        raw = zf.read(test_data[file_id]['input'])
                        info['input'] = {
                            'original_name': os.path.basename(test_data[file_id]['input']),
                            'new_name': f'{file_id}.in',
                            'size': len(raw),
                        }
                    except Exception:
                        info['input'] = {
                            'original_name': os.path.basename(test_data[file_id]['input']),
                            'new_name': f'{file_id}.in',
                            'size': 0,
                        }
                
                if test_data[file_id]['output']:
                    try:
                        raw = zf.read(test_data[file_id]['output'])
                        info['output'] = {
                            'original_name': os.path.basename(test_data[file_id]['output']),
                            'new_name': f'{file_id}.out',
                            'size': len(raw),
                        }
                    except Exception:
                        info['output'] = {
                            'original_name': os.path.basename(test_data[file_id]['output']),
                            'new_name': f'{file_id}.out',
                            'size': 0,
                        }
                
                test_summary.append(info)
            
            # 7. 处理题面文件
            if progress_callback:
                progress_callback(0, 0, '正在查找题面文件...')
            
            statement_files = find_statement_files(zf)
            if statement_files:
                statement_results = process_statements(
                    zf, statement_files, temp_dir, input_basename
                )
                result['statements'] = statement_results
                for sr in statement_results:
                    result['warnings'].append(ProcessingWarning(
                        'info',
                        f'已转换 [{sr["lang_display"]}] 题面: {sr["output_name"]}'
                    ))
            else:
                result['warnings'].append(ProcessingWarning(
                    'warning',
                    '未找到题面文件 (statements/*/problem.tex)'
                ))
            
            result['success'] = True
            result['test_summary'] = test_summary
            
    except zipfile.BadZipFile:
        result['error'] = '无法打开压缩包：文件可能已损坏或不是有效的 zip 文件。'
        result['warnings'].append(ProcessingWarning('error', '无效的 zip 文件'))
    except PermissionError:
        result['error'] = '权限不足：无法读取文件或写入临时目录。'
        result['warnings'].append(ProcessingWarning('error', '权限不足'))
    except Exception as e:
        result['error'] = f'处理过程中发生未知错误:\n{type(e).__name__}: {str(e)}'
        result['warnings'].append(ProcessingWarning('error', str(e)))
    
    return result


def find_statement_files(zf: zipfile.ZipFile) -> dict[str, str]:
    """
    在 zip 文件中查找题面文件。
    
    查找路径: statements/{lang}/problem.tex
    例如: statements/english/problem.tex, statements/chinese/problem.tex
    
    返回: {语言代码: zip内路径} 的字典
    """
    statements = {}
    all_names = zf.namelist()
    
    # 匹配 statements/{lang}/problem.tex 模式
    pattern = re.compile(r'^statements/([^/]+)/problem\.tex$', re.IGNORECASE)
    
    for name in all_names:
        normalized = name.replace('\\', '/')
        m = pattern.match(normalized)
        if m:
            lang = m.group(1).lower()
            statements[lang] = normalized
    
    return statements


def process_statements(
    zf: zipfile.ZipFile,
    statement_files: dict[str, str],
    temp_dir: str,
    input_basename: str,
) -> list[dict]:
    """
    处理题面文件：读取、转换、保存为 .md 文件。
    
    返回: [
        {
            'lang': str,           # 语言代码
            'lang_display': str,    # 显示名称
            'output_name': str,     # 输出文件名
            'output_path': str,    # 输出路径
            'output_size': int,     # 文件大小
            'original_path': str,   # zip 内原始路径
            'preview': str,         # 前 500 字符预览
        },
        ...
    ]
    """
    from tex_converter import convert_tex_to_md
    
    results = []
    lang_display_map = {
        'english': 'English',
        'chinese': 'Chinese',
        'russian': 'Russian',
    }
    
    for lang, zip_path in sorted(statement_files.items()):
        try:
            raw = zf.read(zip_path)
            tex_content = raw.decode('utf-8')
        except UnicodeDecodeError:
            try:
                tex_content = raw.decode('latin-1')
            except Exception:
                continue
        except Exception:
            continue
        
        # 构建 file_reader：从同一 statements/{lang}/ 目录读取示例文件
        # zip_path 如 "statements/english/problem.tex"
        stmt_dir = '/'.join(zip_path.replace('\\', '/').split('/')[:-1])  # "statements/english"
        
        def make_file_reader(zipped_file: zipfile.ZipFile, base_dir: str):
            def reader(filename: str) -> str | None:
                # 尝试多种路径组合
                candidates = [
                    f"{base_dir}/{filename}",
                    f"{base_dir}\\{filename}",
                    filename,
                ]
                for candidate in candidates:
                    try:
                        raw_bytes = zipped_file.read(candidate)
                        text = raw_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            text = raw_bytes.decode('latin-1')
                        except Exception:
                            continue
                    except Exception:
                        continue
                    # 统一换行符为 LF
                    text = text.replace('\r\n', '\n').replace('\r', '\n')
                    return text
                return None
            return reader
        
        file_reader = make_file_reader(zf, stmt_dir)
        
        # 转换为 Markdown
        md_content = convert_tex_to_md(tex_content, file_reader=file_reader)
        md_bytes = md_content.encode('utf-8')
        
        # 生成输出文件
        output_name = f"{input_basename}-{lang}-problem.md"
        output_path = os.path.join(temp_dir, output_name)
        
        # 如果已存在同名文件，删除
        if os.path.exists(output_path):
            os.remove(output_path)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        output_size = os.path.getsize(output_path)
        display_name = lang_display_map.get(lang, lang.capitalize())
        
        # 生成预览（前 500 字符，去除 Markdown 标记以便在纯文本控件中显示）
        preview = _strip_markdown_for_preview(md_content[:500])
        if len(md_content) > 500:
            preview += '\n\n... (更多内容未显示)'
        
        results.append({
            'lang': lang,
            'lang_display': display_name,
            'output_name': output_name,
            'output_path': output_path,
            'output_size': output_size,
            'original_path': zip_path,
            'preview': preview,
        })
    
    return results


def _strip_markdown_for_preview(text: str) -> str:
    """去除 Markdown 标记以便在纯文本控件中预览显示。"""
    import re as _re
    # 去粗体/斜体标记（保留内容）
    text = _re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = _re.sub(r'\*(.+?)\*', r'\1', text)
    # 去行内代码标记
    text = _re.sub(r'`(.+?)`', r'\1', text)
    # 去标题 # 标记
    text = _re.sub(r'^#{1,6}\s+', '', text, flags=_re.MULTILINE)
    # 去列表标记
    text = _re.sub(r'^(\s*)[*\-+]\s+', r'\1  ', text, flags=_re.MULTILINE)
    text = _re.sub(r'^(\s*)\d+\.\s+', r'\1  ', text, flags=_re.MULTILINE)
    # 去掉 $$ 数学块标记
    text = text.replace('$$', '')
    # 去掉多余的空白行
    text = _re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小为可读形式"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
