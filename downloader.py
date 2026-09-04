"""
江西智慧教育平台学习园地资源批量下载工具
=========================================
用于批量下载 https://xxyd.jxeduyun.cn 学习园地中的教育资源

使用方法:
    python downloader.py [选项]

示例:
    # 列出所有可用的年级和学科
    python downloader.py --list
    
    # 下载所有资源
    python downloader.py --all
    
    # 下载七年级语文资源
    python downloader.py --grade 七年级 --subject 语文
    
    # 下载小学阶段所有资源
    python downloader.py --stage 小学
    
    # 下载指定年份的资源
    python downloader.py --year 2026 --limit 100
    
    # 下载资源到指定目录
    python downloader.py --grade 三年级 --output ./downloads
"""

import requests
import json
import os
import sys
import time
import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, unquote
from pathlib import Path

# 设置控制台编码为UTF-8
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 配置
BASE_URL = "https://xxyd.jxeduyun.cn"
API_BASE = f"{BASE_URL}/api/resources/front"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': f'{BASE_URL}/index',
}

# 默认输出目录
DEFAULT_OUTPUT_DIR = "./downloads"

# 年级和学段映射
STAGES = {
    "小学": "1984078087167053825",
    "初中": "1984079254966145025",
    "高中": "1984079284208832514",
}


class JXDownloader:
    """江西智慧教育平台资源下载器"""
    
    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR, max_workers=5):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.output_dir = output_dir
        self.max_workers = max_workers
        self._grades_cache = None
        self._subjects_cache = {}
        
    def _api_get(self, path, params=None):
        """发送GET请求到API"""
        url = f"{API_BASE}{path}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data.get('code') == 200:
                return data.get('data')
            else:
                print(f"API错误: {data.get('msg', '未知错误')}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            return None
    
    def get_grades(self):
        """获取所有年级列表"""
        if self._grades_cache is None:
            self._grades_cache = self._api_get("/grade/selectList")
        return self._grades_cache or []
    
    def get_subjects(self, stage_id):
        """获取指定学段的学科列表"""
        if stage_id not in self._subjects_cache:
            result = self._api_get(
                "/subject/selectListByStageId",
                params={"stageId": stage_id}
            )
            # 某些学段可能不支持学科查询，返回空列表
            self._subjects_cache[stage_id] = result if isinstance(result, list) else []
        return self._subjects_cache.get(stage_id) or []
    
    def get_resources(self, page_num=1, page_size=10, **filters):
        """获取资源列表"""
        params = {"page": page_num, "pageSize": page_size}
        params.update({k: v for k, v in filters.items() if v is not None})
        return self._api_get("/resource/selectResourcePage", params)
    
    def list_grades_and_subjects(self):
        """列出所有年级和学科"""
        print("\n" + "="*60)
        print("江西智慧教育平台 - 年级和学科列表")
        print("="*60)
        
        grades = self.get_grades()
        if not grades:
            print("无法获取年级列表")
            return
        
        # 按学段分组
        stage_grades = {}
        for grade in grades:
            stage_id = grade.get('stageId')
            if stage_id not in stage_grades:
                stage_grades[stage_id] = []
            stage_grades[stage_id].append(grade)
        
        # 学段名称
        stage_names = {v: k for k, v in STAGES.items()}
        
        for stage_id, stage_grades_list in stage_grades.items():
            stage_name = stage_names.get(stage_id, stage_id)
            print(f"\n【{stage_name}】")
            
            # 获取该学段的学科
            subjects = self.get_subjects(stage_id)
            subject_names = [s.get('name', '') for s in subjects] if subjects else []
            
            for grade in stage_grades_list:
                print(f"  {grade['name']} (ID: {grade['id']})")
                if subject_names:
                    print(f"    学科: {', '.join(subject_names)}")
        
        # 统计资源数量
        print("\n" + "-"*60)
        print("各学段资源统计:")
        for stage_name, stage_id in STAGES.items():
            data = self.get_resources(page_num=1, page_size=1, stageId=stage_id)
            if data:
                print(f"  {stage_name}: {data.get('total', 0)} 个资源")
        
        print("-"*60)
    
    def search_resources(self, stage=None, grade=None, subject=None, 
                         year=None, limit=50):
        """搜索资源"""
        filters = {}
        
        # 按学段过滤
        if stage:
            stage_id = STAGES.get(stage)
            if stage_id:
                filters['stageId'] = stage_id
            else:
                print(f"未知学段: {stage}")
                return []
        
        # 按年级过滤
        if grade:
            grades = self.get_grades()
            grade_obj = next((g for g in grades if grade in g.get('name', '')), None)
            if grade_obj:
                filters['gradeId'] = grade_obj['id']
            else:
                print(f"未知年级: {grade}")
                return []
        
        # 按学科过滤
        if subject:
            if 'stageId' in filters:
                subjects = self.get_subjects(filters['stageId'])
                subject_obj = next((s for s in subjects if subject in s.get('name', '')), None)
                if subject_obj:
                    filters['subjectId'] = subject_obj['id']
                else:
                    print(f"未知学科: {subject}")
                    return []
        
        # 按年份过滤
        if year:
            filters['year'] = year
        
        # 获取资源
        all_resources = []
        page_num = 1
        page_size = 50
        
        while len(all_resources) < limit:
            data = self.get_resources(
                page_num=page_num, 
                page_size=min(page_size, limit - len(all_resources)),
                **filters
            )
            if not data or not data.get('rows'):
                break
            
            all_resources.extend(data['rows'])
            
            if len(all_resources) >= data.get('total', 0):
                break
            
            page_num += 1
            time.sleep(0.5)  # 避免请求过快
        
        return all_resources[:limit]
    
    def download_file(self, url, save_path, max_retries=3):
        """下载单个文件"""
        if not url:
            return False, "URL为空"
        
        # 处理URL
        if url.startswith('//'):
            url = 'https:' + url
        elif not url.startswith('http'):
            url = BASE_URL + '/' + url.lstrip('/')
        
        for attempt in range(max_retries):
            try:
                # 检查文件是否已存在
                if os.path.exists(save_path):
                    existing_size = os.path.getsize(save_path)
                    return True, f"文件已存在 ({self._format_size(existing_size)})"
                
                # 下载文件
                response = self.session.get(url, timeout=120, stream=True)
                response.raise_for_status()
                
                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                
                # 保存文件
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                downloaded = 0
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                
                return True, f"下载成功 ({self._format_size(downloaded)})"
                
            except requests.exceptions.RequestException as e:
                # 删除不完整的文件
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                    except:
                        pass
                
                if attempt < max_retries - 1:
                    time.sleep(2)  # 等待后重试
                    continue
                
                return False, f"下载失败 (重试{max_retries}次): {e}"
    
    def _format_size(self, size):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
    
    def download_resource(self, resource, output_dir=None):
        """下载单个资源（包含学生书、教师书、音频等）"""
        if not output_dir:
            output_dir = self.output_dir
        
        resource_name = resource.get('resourceName', '未知资源')
        resource_id = resource.get('id', 'unknown')
        
        # 清理文件名中的非法字符
        safe_name = "".join(c for c in resource_name if c not in r'\/:*?"<>|')
        safe_name = safe_name.strip()
        if not safe_name:
            safe_name = resource_id
        
        results = []
        
        # 下载学生书（主要资源）
        storage_path = resource.get('storagePath')
        if storage_path:
            ext = os.path.splitext(urlparse(storage_path).path)[1] or '.pdf'
            save_path = os.path.join(output_dir, f"{safe_name}{ext}")
            success, msg = self.download_file(storage_path, save_path)
            results.append(('学生书', success, msg))
        
        # 下载教师书（答案）
        answer_path = resource.get('storageAnswerPath')
        if answer_path:
            ext = os.path.splitext(urlparse(answer_path).path)[1] or '.pdf'
            save_path = os.path.join(output_dir, f"{safe_name}_教师书{ext}")
            success, msg = self.download_file(answer_path, save_path)
            results.append(('教师书', success, msg))
        
        # 下载音频
        audio_paths = resource.get('storageAudioPath')
        if audio_paths:
            if isinstance(audio_paths, str):
                audio_paths = [audio_paths]
            elif isinstance(audio_paths, list):
                pass
            else:
                audio_paths = []
            
            for i, audio_path in enumerate(audio_paths):
                if audio_path:
                    ext = os.path.splitext(urlparse(audio_path).path)[1] or '.mp3'
                    save_path = os.path.join(output_dir, f"{safe_name}_音频{i+1}{ext}")
                    success, msg = self.download_file(audio_path, save_path)
                    results.append(('音频', success, msg))
        
        # 下载视频
        video_path = resource.get('storageVideoPath')
        if video_path:
            ext = os.path.splitext(urlparse(video_path).path)[1] or '.mp4'
            save_path = os.path.join(output_dir, f"{safe_name}_视频{ext}")
            success, msg = self.download_file(video_path, save_path)
            results.append(('视频', success, msg))
        
        return results
    
    def batch_download(self, resources, output_dir=None, show_progress=True):
        """批量下载资源"""
        if not resources:
            print("没有要下载的资源")
            return
        
        if not output_dir:
            output_dir = self.output_dir
        
        total = len(resources)
        success_count = 0
        fail_count = 0
        
        print(f"\n开始下载 {total} 个资源到 {output_dir}")
        print("="*60)
        
        for i, resource in enumerate(resources, 1):
            resource_name = resource.get('resourceName', '未知资源')
            print(f"\n[{i}/{total}] {resource_name}")
            
            results = self.download_resource(resource, output_dir)
            
            for file_type, success, msg in results:
                status = "✓" if success else "✗"
                print(f"  {status} {file_type}: {msg}")
                if success:
                    success_count += 1
                else:
                    fail_count += 1
            
            # 避免请求过快
            if i < total:
                time.sleep(0.3)
        
        print("\n" + "="*60)
        print(f"下载完成: 成功 {success_count} 个, 失败 {fail_count} 个")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='江西智慧教育平台学习园地资源批量下载工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --list                           # 列出所有年级和学科
  %(prog)s --grade 七年级 --subject 语文    # 下载七年级语文资源
  %(prog)s --stage 小学 --limit 50          # 下载小学前50个资源
  %(prog)s --year 2026 --output ./my_files  # 下载2026年资源到指定目录
        """
    )
    
    parser.add_argument('--list', action='store_true',
                       help='列出所有可用的年级和学科')
    parser.add_argument('--stage', type=str,
                       help='按学段过滤 (小学/初中/高中)')
    parser.add_argument('--grade', type=str,
                       help='按年级过滤 (如: 七年级)')
    parser.add_argument('--subject', type=str,
                       help='按学科过滤 (如: 语文)')
    parser.add_argument('--year', type=int,
                       help='按年份过滤 (如: 2026)')
    parser.add_argument('--limit', type=int, default=50,
                       help='限制下载数量 (默认: 50)')
    parser.add_argument('--output', '-o', type=str, default=DEFAULT_OUTPUT_DIR,
                       help=f'输出目录 (默认: {DEFAULT_OUTPUT_DIR})')
    parser.add_argument('--workers', type=int, default=1,
                       help='并发下载数 (默认: 1，建议不超过5)')
    parser.add_argument('--no-answers', action='store_true',
                       help='不下载教师书/答案')
    parser.add_argument('--no-audio', action='store_true',
                       help='不下载音频文件')
    
    args = parser.parse_args()
    
    # 创建下载器
    downloader = JXDownloader(
        output_dir=args.output,
        max_workers=args.workers
    )
    
    # 列出年级和学科
    if args.list:
        downloader.list_grades_and_subjects()
        return
    
    # 搜索资源
    print("\n正在搜索资源...")
    resources = downloader.search_resources(
        stage=args.stage,
        grade=args.grade,
        subject=args.subject,
        year=args.year,
        limit=args.limit
    )
    
    if not resources:
        print("未找到匹配的资源")
        return
    
    print(f"\n找到 {len(resources)} 个资源:")
    for i, r in enumerate(resources[:10], 1):
        name = r.get('resourceName', '未知')
        has_answer = "有答案" if r.get('storageAnswerPath') else "无答案"
        has_audio = "有音频" if r.get('storageAudioPath') else "无音频"
        print(f"  {i}. {name} ({has_answer}, {has_audio})")
    
    if len(resources) > 10:
        print(f"  ... 还有 {len(resources) - 10} 个资源")
    
    # 确认下载
    response = input(f"\n确认下载这 {len(resources)} 个资源? (y/n): ")
    if response.lower() != 'y':
        print("已取消下载")
        return
    
    # 开始下载
    downloader.batch_download(resources)


if __name__ == '__main__':
    main()