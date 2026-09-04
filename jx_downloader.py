"""
江西智慧教育平台学习园地资源批量下载工具（完整版）
====================================================
支持按版本、册别、学科、年级、作业类型、单元筛选和下载
"""

import requests
import json
import os
import sys
import time
import re
from collections import defaultdict
from urllib.parse import urlparse

# 设置控制台编码
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

DEFAULT_OUTPUT_DIR = "./downloads"


class JXResourceDownloader:
    """江西智慧教育平台资源下载器"""
    
    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.output_dir = output_dir
        
        # 缓存数据
        self._stages = None
        self._grades = None
        self._subjects = {}
        self._edu_tree = None
    
    def _api_get(self, path, params=None):
        """发送GET请求到API"""
        url = f"{API_BASE}{path}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data.get('code') == 200:
                return data.get('data')
            return None
        except Exception as e:
            return None
    
    def _format_size(self, size):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
    
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self, title):
        """打印标题"""
        print("\n" + "="*60)
        print(f"  {title}")
        print("="*60)
    
    def print_menu(self, options, title="请选择"):
        """打印菜单"""
        print(f"\n{title}:")
        print("-"*40)
        for i, option in enumerate(options, 1):
            print(f"  {i}. {option}")
        print("-"*40)
        print(f"  0. 返回上级菜单")
    
    def get_input(self, prompt, valid_range=None):
        """获取用户输入"""
        while True:
            try:
                choice = input(f"\n{prompt}").strip()
                if choice == '0':
                    return 0
                num = int(choice)
                if valid_range and num not in valid_range:
                    print(f"请输入 {min(valid_range)}-{max(valid_range)} 之间的数字")
                    continue
                return num
            except ValueError:
                print("请输入数字")
    
    # ========== 数据获取方法 ==========
    
    def get_stages(self):
        """获取学段列表"""
        if self._stages is None:
            grades = self._api_get("/grade/selectList")
            if grades:
                stages = {}
                for grade in grades:
                    stage_id = grade.get('stageId')
                    if stage_id not in stages:
                        stages[stage_id] = {
                            'id': stage_id,
                            'name': self._get_stage_name(stage_id),
                            'grades': []
                        }
                    stages[stage_id]['grades'].append(grade)
                self._stages = list(stages.values())
        return self._stages or []
    
    def _get_stage_name(self, stage_id):
        """根据stageId获取学段名称"""
        stage_names = {
            "1984078087167053825": "小学",
            "1984079254966145025": "初中",
            "1984079284208832514": "高中"
        }
        return stage_names.get(stage_id, "未知学段")
    
    def get_grades(self, stage_id=None):
        """获取年级列表"""
        if self._grades is None:
            self._grades = self._api_get("/grade/selectList") or []
        if stage_id:
            return [g for g in self._grades if g.get('stageId') == stage_id]
        return self._grades
    
    def get_subjects(self, stage_id):
        """获取学科列表"""
        if stage_id not in self._subjects:
            result = self._api_get(
                "/subject/selectListByStageId",
                params={"stageId": stage_id}
            )
            
            if not result or not isinstance(result, list):
                all_subjects = [
                    {"id": "1984193942848700417", "name": "语文"},
                    {"id": "1984194148180852738", "name": "数学"},
                    {"id": "1984194229030256642", "name": "英语"},
                    {"id": "1984194249171304449", "name": "物理"},
                    {"id": "1984194267819180034", "name": "化学"},
                    {"id": "1984194289243684865", "name": "生物学"},
                    {"id": "1984194308029972481", "name": "历史"},
                    {"id": "1984194326703013890", "name": "地理"},
                    {"id": "1990253268894941185", "name": "道德与法治"},
                ]
                
                if stage_id == "1984078087167053825":
                    result = [s for s in all_subjects if s['name'] in ['语文', '数学', '英语', '道德与法治']]
                elif stage_id == "1984079284208832514":
                    result = all_subjects.copy()
                    result = [s for s in result if s['name'] != '道德与法治']
                    result.append({"id": "1990253268894941185", "name": "思想政治"})
                else:
                    result = all_subjects.copy()
            
            self._subjects[stage_id] = result
        return self._subjects[stage_id]
    
    def get_edu_tree(self):
        """获取教育资源树（版本、册别）"""
        if self._edu_tree is None:
            data = self._api_get("/educationalResource/list")
            if data and isinstance(data, dict) and 'data' in data:
                self._edu_tree = data['data']
            else:
                self._edu_tree = []
        return self._edu_tree or []
    
    # ========== 资源查询方法 ==========
    
    def query_resources(self, **filters):
        """查询资源列表（第一页）"""
        params = {"page": 1, "pageSize": 10}
        for key in ['year', 'stageId', 'gradeId', 'subjectId', 'versionId', 'volumeId', 'resourceType']:
            if key in filters and filters[key]:
                params[key] = filters[key]
        
        data = self._api_get("/resource/selectResourcePage", params)
        if data and data.get('rows'):
            return data['rows'], data.get('total', 0)
        return [], 0
    
    def query_all_resources_by_page(self, **filters):
        """查询所有资源（使用分页参数page）"""
        all_resources = []
        seen_ids = set()
        
        for page in range(1, 100):
            params = {"page": page, "pageSize": 10}
            for key in ['year', 'stageId', 'gradeId', 'subjectId', 'versionId', 'volumeId', 'resourceType']:
                if key in filters and filters[key]:
                    params[key] = filters[key]
            
            data = self._api_get("/resource/selectResourcePage", params)
            if not data or not data.get('rows'):
                break
            
            rows = data.get('rows', [])
            if not rows:
                break
            
            new_count = 0
            for row in rows:
                rid = row.get('id')
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    all_resources.append(row)
                    new_count += 1
            
            if new_count == 0:
                break
            
            time.sleep(0.3)
        
        return all_resources
    
    def query_all_resources(self, **filters):
        """查询所有资源（通过组合查询）"""
        all_resources = []
        seen_ids = set()
        
        # 获取教育资源树
        edu_tree = self.get_edu_tree()
        
        # 构建查询条件
        query_params = {}
        for key in ['year', 'stageId', 'gradeId', 'subjectId', 'resourceType']:
            if key in filters and filters[key]:
                query_params[key] = filters[key]
        
        # 如果指定了版本，只查询该版本
        if filters.get('versionId'):
            for version in edu_tree:
                if version.get('id') == filters['versionId']:
                    for volume in version.get('children', []):
                        params = {**query_params, "volumeId": volume.get('id')}
                        data = self._api_get("/resource/selectResourcePage", params)
                        if data and data.get('rows'):
                            for row in data['rows']:
                                if row.get('id') not in seen_ids:
                                    seen_ids.add(row['id'])
                                    all_resources.append(row)
        # 如果指定了册别，只查询该册别
        elif filters.get('volumeId'):
            params = {**query_params, "volumeId": filters['volumeId']}
            data = self._api_get("/resource/selectResourcePage", params)
            if data and data.get('rows'):
                for row in data['rows']:
                    if row.get('id') not in seen_ids:
                        seen_ids.add(row['id'])
                        all_resources.append(row)
        # 否则查询所有版本的册别
        else:
            for version in edu_tree:
                for volume in version.get('children', []):
                    params = {**query_params, "volumeId": volume.get('id')}
                    data = self._api_get("/resource/selectResourcePage", params)
                    if data and data.get('rows'):
                        for row in data['rows']:
                            if row.get('id') not in seen_ids:
                                seen_ids.add(row['id'])
                                all_resources.append(row)
        
        return all_resources
    
    def extract_unit_from_name(self, name):
        """从资源名称中提取单元信息"""
        # 匹配中文单元格式: 第X单元
        match = re.search(r'第[一二三四五六七八九十\d]+单元', name)
        if match:
            return match.group(0)
        
        # 匹配英文单元格式: UnitX
        match = re.search(r'Unit\s*\d+', name, re.IGNORECASE)
        if match:
            return match.group(0).replace(' ', '')
        
        # 匹配课时格式: 第X课时
        match = re.search(r'第[一二三四五六七八九十\d]+课时', name)
        if match:
            return match.group(0)
        
        return "其他"
    
    def extract_homework_type(self, name):
        """从资源名称中提取作业类型"""
        if '基础' in name:
            return '基础性作业'
        elif '提升' in name:
            return '提升性作业'
        elif '复习' in name:
            return '复习作业'
        elif '同步' in name:
            return '同步作业'
        else:
            return '其他'
    
    def group_resources_by_unit(self, resources):
        """按单元分组资源"""
        units = defaultdict(list)
        for resource in resources:
            name = resource.get('resourceName', '')
            unit = self.extract_unit_from_name(name)
            units[unit].append(resource)
        return dict(units)
    
    def group_resources_by_type(self, resources):
        """按作业类型分组资源"""
        types = defaultdict(list)
        for resource in resources:
            name = resource.get('resourceName', '')
            hw_type = self.extract_homework_type(name)
            types[hw_type].append(resource)
        return dict(types)
    
    # ========== 下载方法 ==========
    
    def download_file(self, url, filename, max_retries=2):
        """下载单个文件"""
        if url.startswith('//'):
            url = 'https:' + url
        elif not url.startswith('http'):
            url = BASE_URL + '/' + url.lstrip('/')
        
        # 跳过jxeduyun.cn域名的文件（该域名文件不可用）
        if 'jxeduyun.cn' in url and '/view/' in url:
            return False, "文件不可用(域名限制)"
        
        safe_filename = "".join(c for c in filename if c not in r'\/:*?"<>|')
        save_path = os.path.join(self.output_dir, safe_filename)
        
        for attempt in range(max_retries):
            try:
                if os.path.exists(save_path):
                    size = os.path.getsize(save_path)
                    return True, f"已存在 ({self._format_size(size)})"
                
                response = self.session.get(url, timeout=15, stream=True)
                
                if response.status_code == 404:
                    return False, "文件不存在(404)"
                
                response.raise_for_status()
                
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                downloaded = 0
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                
                return True, f"成功 ({self._format_size(downloaded)})"
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return False, "超时"
            except Exception as e:
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                    except:
                        pass
                
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                
                return False, f"失败: {str(e)[:50]}"
    
    def download_resource(self, resource, download_options=None):
        """下载单个资源"""
        if download_options is None:
            download_options = {'student': True, 'teacher': True, 'audio': True, 'video': True}
        
        name = resource.get('resourceName', '未知')
        safe_name = "".join(c for c in name if c not in r'\/:*?"<>|')[:50]
        
        results = []
        
        # 下载学生书
        if download_options.get('student') and resource.get('storagePath'):
            success, msg = self.download_file(resource['storagePath'], f"{safe_name}.pdf")
            results.append(('学生书', success, msg))
        
        # 下载教师书
        if download_options.get('teacher') and resource.get('storageAnswerPath'):
            success, msg = self.download_file(resource['storageAnswerPath'], f"{safe_name}_教师书.pdf")
            results.append(('教师书', success, msg))
        
        # 下载音频
        if download_options.get('audio') and resource.get('storageAudioPath'):
            audio_paths = resource['storageAudioPath']
            if isinstance(audio_paths, str):
                audio_paths = [audio_paths]
            elif not isinstance(audio_paths, list):
                audio_paths = []
            
            for i, audio_path in enumerate(audio_paths):
                if audio_path:
                    success, msg = self.download_file(audio_path, f"{safe_name}_音频{i+1}.pdf")
                    results.append(('音频', success, msg))
        
        # 下载视频
        if download_options.get('video') and resource.get('storageVideoPath'):
            success, msg = self.download_file(resource['storageVideoPath'], f"{safe_name}_视频.mp4")
            results.append(('视频', success, msg))
        
        return results
    
    def batch_download(self, resources, download_options=None):
        """批量下载资源"""
        if not resources:
            print("\n没有要下载的资源")
            return
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        success_count = 0
        fail_count = 0
        
        for i, resource in enumerate(resources, 1):
            name = resource.get('resourceName', '未知')
            print(f"\n[{i}/{len(resources)}] {name[:50]}")
            
            results = self.download_resource(resource, download_options)
            
            for file_type, success, msg in results:
                status = "✓" if success else "✗"
                print(f"  {status} {file_type}: {msg}")
                if success:
                    success_count += 1
                else:
                    fail_count += 1
            
            time.sleep(0.2)
        
        print("\n" + "="*60)
        print(f"下载完成: 成功 {success_count} 个, 失败 {fail_count} 个")
        print(f"文件保存在: {os.path.abspath(self.output_dir)}")
        print("="*60)


def main():
    """主函数"""
    downloader = JXResourceDownloader()
    
    while True:
        downloader.clear_screen()
        downloader.print_header("江西智慧教育平台 - 学习园地资源下载工具")
        
        options = [
            "按条件搜索并下载资源",
            "按版本和册别浏览下载",
            "设置下载目录",
            "退出程序",
        ]
        downloader.print_menu(options)
        
        try:
            choice = downloader.get_input("请选择操作: ", range(0, len(options) + 1))
        except:
            choice = 0
        
        if choice == 0:
            print("\n感谢使用，再见！")
            break
        elif choice == 1:
            search_and_download(downloader)
        elif choice == 2:
            browse_and_download(downloader)
        elif choice == 3:
            set_output_dir(downloader)
        elif choice == 4:
            print("\n感谢使用，再见！")
            break


def search_and_download(downloader):
    """搜索并下载资源"""
    downloader.clear_screen()
    downloader.print_header("按条件搜索资源")
    
    filters = {}
    
    # 选择学段
    stages = downloader.get_stages()
    print("\n可用学段:")
    for i, stage in enumerate(stages, 1):
        print(f"  {i}. {stage['name']}")
    print(f"  0. 全部学段")
    
    choice = downloader.get_input("请选择学段: ", range(0, len(stages) + 1))
    if choice > 0:
        filters['stageId'] = stages[choice - 1]['id']
        filters['_stage_name'] = stages[choice - 1]['name']
    
    # 选择年级
    stage_id = filters.get('stageId')
    grades = downloader.get_grades(stage_id)
    print("\n可用年级:")
    for i, grade in enumerate(grades, 1):
        print(f"  {i}. {grade['name']}")
    print(f"  0. 全部年级")
    
    choice = downloader.get_input("请选择年级: ", range(0, len(grades) + 1))
    if choice > 0:
        filters['gradeId'] = grades[choice - 1]['id']
        filters['_grade_name'] = grades[choice - 1]['name']
    
    # 选择学科
    if stage_id:
        subjects = downloader.get_subjects(stage_id)
        print("\n可用学科:")
        for i, subject in enumerate(subjects, 1):
            print(f"  {i}. {subject['name']}")
        print(f"  0. 全部学科")
        
        choice = downloader.get_input("请选择学科: ", range(0, len(subjects) + 1))
        if choice > 0:
            filters['subjectId'] = subjects[choice - 1]['id']
            filters['_subject_name'] = subjects[choice - 1]['name']
    
    # 选择版本
    edu_tree = downloader.get_edu_tree()
    print("\n可用版本:")
    for i, version in enumerate(edu_tree[:10], 1):
        print(f"  {i}. {version['name']}")
    if len(edu_tree) > 10:
        print(f"  ... 还有 {len(edu_tree) - 10} 个版本")
    print(f"  0. 全部版本")
    
    choice = downloader.get_input("请选择版本: ", range(0, min(10, len(edu_tree)) + 1))
    if choice > 0:
        filters['versionId'] = edu_tree[choice - 1]['id']
        filters['_version_name'] = edu_tree[choice - 1]['name']
    
    # 查询资源（使用分页获取所有）
    print("\n正在查询所有资源...")
    resources = downloader.query_all_resources_by_page(**filters)
    
    if not resources:
        print("\n未找到匹配的资源")
        input("\n按回车继续...")
        return
    
    print(f"\n找到 {len(resources)} 个资源")
    
    # 按单元分组
    units = downloader.group_resources_by_unit(resources)
    print(f"\n按单元分组:")
    for unit, res_list in sorted(units.items()):
        print(f"  {unit}: {len(res_list)}个资源")
    
    # 选择下载方式
    print("\n下载方式:")
    print("  1. 下载全部资源")
    print("  2. 按单元下载")
    print("  3. 返回")
    
    choice = downloader.get_input("请选择: ", range(0, 4))
    
    if choice == 1:
        downloader.batch_download(resources)
    elif choice == 2:
        download_by_unit(downloader, units)
    
    input("\n按回车继续...")


def download_by_unit(downloader, units):
    """按单元下载"""
    print("\n选择要下载的单元:")
    unit_list = sorted(units.keys())
    for i, unit in enumerate(unit_list, 1):
        print(f"  {i}. {unit} ({len(units[unit])}个资源)")
    print(f"  0. 返回")
    
    choice = downloader.get_input("请选择单元: ", range(0, len(unit_list) + 1))
    
    if choice > 0:
        selected_unit = unit_list[choice - 1]
        resources = units[selected_unit]
        
        print(f"\n{selected_unit} 共有 {len(resources)} 个资源:")
        for i, r in enumerate(resources[:10], 1):
            print(f"  {i}. {r.get('resourceName', '未知')}")
        if len(resources) > 10:
            print(f"  ... 还有 {len(resources) - 10} 个资源")
        
        # 选择下载选项
        print("\n下载选项:")
        print("  1. 只下载学生书")
        print("  2. 下载学生书 + 教师书")
        print("  3. 全部下载")
        
        choice = downloader.get_input("请选择: ", range(1, 4))
        
        download_options = {'student': True, 'teacher': choice >= 2, 'audio': choice >= 3, 'video': choice >= 3}
        
        confirm = input(f"\n确认下载 {selected_unit} 的 {len(resources)} 个资源? (y/n): ").strip().lower()
        if confirm == 'y':
            downloader.batch_download(resources, download_options)


def browse_and_download(downloader):
    """按版本和册别浏览下载"""
    downloader.clear_screen()
    downloader.print_header("按版本和册别浏览")
    
    edu_tree = downloader.get_edu_tree()
    
    print("\n选择版本:")
    for i, version in enumerate(edu_tree[:10], 1):
        print(f"  {i}. {version['name']}")
    if len(edu_tree) > 10:
        print(f"  ... 还有 {len(edu_tree) - 10} 个版本")
    print(f"  0. 返回")
    
    choice = downloader.get_input("请选择版本: ", range(0, min(10, len(edu_tree)) + 1))
    
    if choice == 0:
        return
    
    selected_version = edu_tree[choice - 1]
    volumes = selected_version.get('children', [])
    
    print(f"\n{selected_version['name']} 的册别:")
    for i, volume in enumerate(volumes, 1):
        print(f"  {i}. {volume['name']}")
    print(f"  0. 返回")
    
    choice = downloader.get_input("请选择册别: ", range(0, len(volumes) + 1))
    
    if choice == 0:
        return
    
    selected_volume = volumes[choice - 1]
    
    # 查询资源（使用分页获取所有）
    print(f"\n正在查询 {selected_version['name']} {selected_volume['name']} 的所有资源...")
    
    resources = downloader.query_all_resources_by_page(volumeId=selected_volume['id'])
    total = len(resources)
    
    if not resources:
        print("\n未找到资源")
        input("\n按回车继续...")
        return
    
    print(f"\n找到 {total} 个资源")
    
    # 按单元分组
    units = downloader.group_resources_by_unit(resources)
    print(f"\n按单元分组:")
    for unit, res_list in sorted(units.items()):
        print(f"  {unit}: {len(res_list)}个资源")
    
    # 选择下载方式
    print("\n下载方式:")
    print("  1. 下载全部显示的资源")
    print("  2. 按单元下载")
    print("  3. 返回")
    
    choice = downloader.get_input("请选择: ", range(0, 4))
    
    if choice == 1:
        downloader.batch_download(resources)
    elif choice == 2:
        download_by_unit(downloader, units)
    
    input("\n按回车继续...")


def set_output_dir(downloader):
    """设置下载目录"""
    downloader.clear_screen()
    downloader.print_header("设置下载目录")
    
    print(f"\n当前下载目录: {downloader.output_dir}")
    new_dir = input("\n请输入新的下载目录路径（直接回车保持不变）: ").strip()
    
    if new_dir:
        downloader.output_dir = new_dir
        os.makedirs(downloader.output_dir, exist_ok=True)
        print(f"\n下载目录已设置为: {downloader.output_dir}")
    
    input("按回车继续...")


if __name__ == '__main__':
    main()