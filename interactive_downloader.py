"""
江西智慧教育平台学习园地资源批量下载工具（交互版）
====================================================
使用方法: python interactive_downloader.py
"""

import requests
import json
import os
import sys
import time
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


class InteractiveDownloader:
    """交互式资源下载器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.output_dir = DEFAULT_OUTPUT_DIR
        
        # 缓存数据
        self._stages = None
        self._grades = None
        self._subjects = {}
        self._years = None
        self._edu_tree = None
        
        # 用户选择的筛选条件
        self.filters = {}
    
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
            # 先尝试API获取
            result = self._api_get(
                "/subject/selectListByStageId",
                params={"stageId": stage_id}
            )
            
            # 如果API返回失败，使用通用学科列表（subjectId在所有学段通用）
            if not result or not isinstance(result, list):
                # 通用学科列表（从小学三年级到高三都适用）
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
                
                # 根据学段筛选适用的学科
                if stage_id == "1984078087167053825":  # 小学
                    result = [s for s in all_subjects if s['name'] in ['语文', '数学', '英语', '道德与法治']]
                elif stage_id == "1984079284208832514":  # 高中
                    result = all_subjects.copy()
                    # 高中将"道德与法治"改为"思想政治"
                    result = [s for s in result if s['name'] != '道德与法治']
                    result.append({"id": "1990253268894941185", "name": "思想政治"})
                else:
                    result = all_subjects.copy()
            
            self._subjects[stage_id] = result
        return self._subjects[stage_id]
    
    def get_years(self):
        """获取年份列表"""
        if self._years is None:
            self._years = self._api_get("/dir/getYearList") or []
        return self._years
    
    def get_edu_tree(self):
        """获取教育资源树（版本、册别）"""
        if self._edu_tree is None:
            data = self._api_get("/educationalResource/list")
            if data and isinstance(data, dict) and 'data' in data:
                self._edu_tree = data['data']
            else:
                self._edu_tree = []
        return self._edu_tree or []
    
    def get_versions_for_subject(self, stage_id, subject_id):
        """获取指定学段和学科的版本列表"""
        edu_tree = self.get_edu_tree()
        versions = []
        
        # 遍历树形结构找到对应的版本
        for version in edu_tree:
            # 检查该版本下是否有对应的学科和学段
            for volume in version.get('children', []):
                # volume实际上可能是subject或其他层级
                pass
            
            # 简化：直接返回所有版本
            versions.append({
                'id': version.get('id'),
                'name': version.get('name'),
                'volumes': version.get('children', [])
            })
        
        return versions
    
    def get_resource_types(self):
        """获取资源类型"""
        return [
            {"name": "全部", "value": ""},
            {"name": "同步作业", "value": "同步作业"},
            {"name": "复习作业", "value": "复习作业"},
            {"name": "备课授课资源", "value": "备课授课资源"},
            {"name": "专题资源", "value": "专题资源"},
        ]
    
    # ========== 交互菜单方法 ==========
    
    def main_menu(self):
        """主菜单"""
        while True:
            self.clear_screen()
            self.print_header("江西智慧教育平台 - 学习园地资源下载工具")
            
            options = [
                "按筛选条件搜索资源",
                "按版本和册别浏览资源",
                "查看当前筛选条件",
                "清空筛选条件",
                "设置下载目录",
                "帮助说明",
            ]
            self.print_menu(options)
            
            choice = self.get_input("请选择操作: ", range(0, len(options) + 1))
            
            if choice == 0:
                print("\n感谢使用，再见！")
                break
            elif choice == 1:
                self.select_filters()
            elif choice == 2:
                self.browse_by_version_volume()
            elif choice == 3:
                self.show_current_filters()
                input("\n按回车继续...")
            elif choice == 4:
                self.filters = {}
                print("\n筛选条件已清空")
                input("\n按回车继续...")
            elif choice == 5:
                self.set_output_dir()
            elif choice == 6:
                self.show_help()
    
    def select_filters(self):
        """选择筛选条件"""
        self.clear_screen()
        self.print_header("选择筛选条件")
        
        while True:
            print("\n当前筛选条件:")
            self._print_current_filters()
            
            options = [
                "选择年份",
                "选择学段",
                "选择年级",
                "选择学科",
                "选择版本",
                "选择册别",
                "选择资源类型",
                "确认筛选条件，开始搜索",
            ]
            self.print_menu(options, "\n请选择要设置的条件")
            
            choice = self.get_input("请选择: ", range(0, len(options) + 1))
            
            if choice == 0:
                break
            elif choice == 1:
                self._select_year()
            elif choice == 2:
                self._select_stage()
            elif choice == 3:
                self._select_grade()
            elif choice == 4:
                self._select_subject()
            elif choice == 5:
                self._select_version()
            elif choice == 6:
                self._select_volume()
            elif choice == 7:
                self._select_resource_type()
            elif choice == 8:
                self.search_and_download()
                break
    
    def _print_current_filters(self):
        """打印当前筛选条件"""
        if not self.filters:
            print("  （未设置任何筛选条件）")
            return
        
        filter_names = {
            'year': '年份',
            'stageId': '学段',
            'gradeId': '年级',
            'subjectId': '学科',
            'versionId': '版本',
            'volumeId': '册别',
            'resourceType': '资源类型',
        }
        
        for key, name in filter_names.items():
            if key in self.filters:
                value = self.filters[key]
                if isinstance(value, dict):
                    print(f"  {name}: {value.get('name', value.get('id', value))}")
                else:
                    print(f"  {name}: {value}")
    
    def _select_year(self):
        """选择年份"""
        years = self.get_years()
        if not years:
            print("\n无法获取年份列表")
            input("按回车继续...")
            return
        
        self.clear_screen()
        self.print_header("选择年份")
        
        options = [str(y) for y in years]
        options.append("全部年份")
        self.print_menu(options)
        
        choice = self.get_input("请选择年份: ", range(0, len(options) + 1))
        
        if choice == 0:
            return
        elif choice <= len(years):
            self.filters['year'] = years[choice - 1]
            print(f"\n已选择年份: {years[choice - 1]}")
        else:
            self.filters.pop('year', None)
            print("\n已选择全部年份")
        
        input("按回车继续...")
    
    def _select_stage(self):
        """选择学段"""
        stages = self.get_stages()
        if not stages:
            print("\n无法获取学段列表")
            input("按回车继续...")
            return
        
        self.clear_screen()
        self.print_header("选择学段")
        
        options = [s['name'] for s in stages]
        options.append("全部学段")
        self.print_menu(options)
        
        choice = self.get_input("请选择学段: ", range(0, len(options) + 1))
        
        if choice == 0:
            return
        elif choice <= len(stages):
            stage = stages[choice - 1]
            self.filters['stageId'] = stage['id']
            self.filters['_stage_name'] = stage['name']
            print(f"\n已选择学段: {stage['name']}")
        else:
            self.filters.pop('stageId', None)
            self.filters.pop('_stage_name', None)
            print("\n已选择全部学段")
        
        input("按回车继续...")
    
    def _select_grade(self):
        """选择年级"""
        # 如果已选择学段，只显示该学段的年级
        stage_id = self.filters.get('stageId')
        grades = self.get_grades(stage_id)
        
        if not grades:
            print("\n无法获取年级列表")
            input("按回车继续...")
            return
        
        self.clear_screen()
        self.print_header("选择年级")
        
        options = [g['name'] for g in grades]
        options.append("全部年级")
        self.print_menu(options)
        
        choice = self.get_input("请选择年级: ", range(0, len(options) + 1))
        
        if choice == 0:
            return
        elif choice <= len(grades):
            grade = grades[choice - 1]
            self.filters['gradeId'] = grade['id']
            self.filters['_grade_name'] = grade['name']
            print(f"\n已选择年级: {grade['name']}")
        else:
            self.filters.pop('gradeId', None)
            self.filters.pop('_grade_name', None)
            print("\n已选择全部年级")
        
        input("按回车继续...")
    
    def _select_subject(self):
        """选择学科"""
        stage_id = self.filters.get('stageId')
        if not stage_id:
            print("\n请先选择学段")
            input("按回车继续...")
            return
        
        subjects = self.get_subjects(stage_id)
        if not subjects:
            print(f"\n该学段暂无学科数据")
            input("按回车继续...")
            return
        
        self.clear_screen()
        self.print_header("选择学科")
        
        options = [s['name'] for s in subjects]
        options.append("全部学科")
        self.print_menu(options)
        
        choice = self.get_input("请选择学科: ", range(0, len(options) + 1))
        
        if choice == 0:
            return
        elif choice <= len(subjects):
            subject = subjects[choice - 1]
            self.filters['subjectId'] = subject['id']
            self.filters['_subject_name'] = subject['name']
            print(f"\n已选择学科: {subject['name']}")
        else:
            self.filters.pop('subjectId', None)
            self.filters.pop('_subject_name', None)
            print("\n已选择全部学科")
        
        input("按回车继续...")
    
    def _select_version(self):
        """选择版本"""
        edu_tree = self.get_edu_tree()
        if not edu_tree:
            print("\n无法获取版本列表")
            input("按回车继续...")
            return
        
        self.clear_screen()
        self.print_header("选择教材版本")
        
        options = [v['name'] for v in edu_tree]
        options.append("全部版本")
        self.print_menu(options)
        
        choice = self.get_input("请选择版本: ", range(0, len(options) + 1))
        
        if choice == 0:
            return
        elif choice <= len(edu_tree):
            version = edu_tree[choice - 1]
            self.filters['versionId'] = version['id']
            self.filters['_version_name'] = version['name']
            self.filters['_version_volumes'] = version.get('children', [])
            print(f"\n已选择版本: {version['name']}")
        else:
            self.filters.pop('versionId', None)
            self.filters.pop('_version_name', None)
            self.filters.pop('_version_volumes', None)
            print("\n已选择全部版本")
        
        input("按回车继续...")
    
    def _select_volume(self):
        """选择册别"""
        # 如果已选择版本，显示该版本的册别
        volumes = self.filters.get('_version_volumes', [])
        
        if not volumes:
            # 显示所有可用的册别
            edu_tree = self.get_edu_tree()
            all_volumes = {}
            for version in edu_tree:
                for volume in version.get('children', []):
                    vol_id = volume.get('id')
                    if vol_id not in all_volumes:
                        all_volumes[vol_id] = volume
            volumes = list(all_volumes.values())
        
        if not volumes:
            print("\n无法获取册别列表")
            input("按回车继续...")
            return
        
        self.clear_screen()
        self.print_header("选择册别")
        
        options = [v['name'] for v in volumes]
        options.append("全部册别")
        self.print_menu(options)
        
        choice = self.get_input("请选择册别: ", range(0, len(options) + 1))
        
        if choice == 0:
            return
        elif choice <= len(volumes):
            volume = volumes[choice - 1]
            self.filters['volumeId'] = volume['id']
            self.filters['_volume_name'] = volume['name']
            print(f"\n已选择册别: {volume['name']}")
        else:
            self.filters.pop('volumeId', None)
            self.filters.pop('_volume_name', None)
            print("\n已选择全部册别")
        
        input("按回车继续...")
    
    def _select_resource_type(self):
        """选择资源类型"""
        types = self.get_resource_types()
        
        self.clear_screen()
        self.print_header("选择资源类型")
        
        options = [t['name'] for t in types]
        self.print_menu(options)
        
        choice = self.get_input("请选择资源类型: ", range(0, len(options) + 1))
        
        if choice == 0:
            return
        elif choice <= len(types):
            res_type = types[choice - 1]
            if res_type['value']:
                self.filters['resourceType'] = res_type['value']
            else:
                self.filters.pop('resourceType', None)
            print(f"\n已选择资源类型: {res_type['name']}")
        
        input("按回车继续...")
    
    def show_current_filters(self):
        """显示当前筛选条件"""
        self.clear_screen()
        self.print_header("当前筛选条件")
        self._print_current_filters()
    
    def set_output_dir(self):
        """设置下载目录"""
        self.clear_screen()
        self.print_header("设置下载目录")
        
        print(f"\n当前下载目录: {self.output_dir}")
        new_dir = input("\n请输入新的下载目录路径（直接回车保持不变）: ").strip()
        
        if new_dir:
            self.output_dir = new_dir
            os.makedirs(self.output_dir, exist_ok=True)
            print(f"\n下载目录已设置为: {self.output_dir}")
        
        input("按回车继续...")
    
    def show_help(self):
        """显示帮助说明"""
        self.clear_screen()
        self.print_header("帮助说明")
        
        help_text = """
本工具用于批量下载江西智慧教育平台学习园地中的资源。

使用步骤：
1. 选择"选择筛选条件下载资源"
2. 依次设置年份、学段、年级、学科、版本、册别、资源类型
3. 选择"确认筛选条件，开始搜索"
4. 预览搜索结果
5. 确认下载

筛选条件说明：
- 年份：资源发布的年份
- 学段：小学、初中、高中
- 年级：三年级~六年级（小学）、七年级~九年级（初中）、高一~高三（高中）
- 学科：语文、数学、英语等
- 版本：人教版、北师大版、苏教版等教材版本
- 册别：上册、下册、必修第一册等
- 资源类型：同步作业、复习作业等

下载的文件将保存在设置的下载目录中。
        """
        print(help_text)
        input("\n按回车继续...")
    
    def browse_by_version_volume(self):
        """按版本和册别浏览资源"""
        self.clear_screen()
        self.print_header("按版本和册别浏览资源")
        
        # 获取教育资源树
        edu_tree = self.get_edu_tree()
        if not edu_tree:
            print("\n无法获取版本列表")
            input("按回车继续...")
            return
        
        # 选择版本
        print("\n请选择教材版本:")
        print("-"*40)
        options = [v['name'] for v in edu_tree]
        self.print_menu(options)
        
        choice = self.get_input("请选择版本: ", range(0, len(options) + 1))
        
        if choice == 0:
            return
        
        selected_version = edu_tree[choice - 1]
        version_name = selected_version.get('name', '')
        volumes = selected_version.get('children', [])
        
        if not volumes:
            print(f"\n{version_name} 没有册别信息")
            input("按回车继续...")
            return
        
        # 选择册别
        self.clear_screen()
        self.print_header(f"{version_name} - 选择册别")
        
        print("\n请选择册别:")
        print("-"*40)
        vol_options = [v['name'] for v in volumes]
        self.print_menu(vol_options)
        
        choice = self.get_input("请选择册别: ", range(0, len(vol_options) + 1))
        
        if choice == 0:
            return
        
        selected_volume = volumes[choice - 1]
        volume_name = selected_volume.get('name', '')
        volume_id = selected_volume.get('id', '')
        
        # 查询该册别的资源
        self.clear_screen()
        self.print_header(f"{version_name} - {volume_name}")
        
        print(f"\n正在查询资源...")
        
        data = self._api_get("/resource/selectResourcePage", {
            "page": 1,
            "pageSize": 10,
            "volumeId": volume_id
        })
        
        if not data or not data.get('rows'):
            print("\n未找到资源")
            input("按回车继续...")
            return
        
        resources = data['rows']
        total = data.get('total', 0)
        
        print(f"\n查询结果:")
        print(f"  - {version_name} {volume_name} 共有 {total} 个资源")
        print(f"  - 当前显示前 {len(resources)} 个资源")
        
        if total > 10:
            print(f"\n  注意: API限制每次最多显示10个资源")
        
        # 显示资源列表
        print("\n资源列表:")
        print("-"*40)
        for i, r in enumerate(resources, 1):
            name = r.get('resourceName', '未知')
            has_answer = "✓答案" if r.get('storageAnswerPath') else "✗答案"
            has_audio = "✓音频" if r.get('storageAudioPath') else "✗音频"
            print(f"  {i:2d}. {name[:45]:<45s} [{has_answer}] [{has_audio}]")
        
        # 选择下载
        print("\n" + "-"*40)
        print("  1. 下载全部显示的资源")
        print("  2. 选择特定资源下载")
        print("  0. 返回")
        
        choice = self.get_input("请选择: ", range(0, 3))
        
        if choice == 1:
            self._download_resources(resources)
        elif choice == 2:
            self._select_specific_resources(resources)
    
    def search_and_download(self):
        """搜索并下载资源"""
        self.clear_screen()
        self.print_header("搜索资源")
        
        print("\n正在搜索资源...")
        
        # 构建查询参数并分页获取所有资源
        all_resources = []
        seen_ids = set()
        
        for page in range(1, 100):
            params = {"page": page, "pageSize": 10}
            for key in ['year', 'stageId', 'gradeId', 'subjectId', 'versionId', 'volumeId', 'resourceType']:
                if key in self.filters:
                    params[key] = self.filters[key]
            
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
        
        if not all_resources:
            print("\n未找到匹配的资源")
            input("按回车继续...")
            return
        
        total = len(all_resources)
        
        print(f"\n搜索结果:")
        print(f"  - 找到资源: {total} 个")
        
        # 显示版本和册别统计
        if 'versionId' not in self.filters:
            print(f"\n  可用的版本:")
            edu_tree = self.get_edu_tree()
            for v in edu_tree[:5]:
                print(f"    - {v['name']}")
            if len(edu_tree) > 5:
                print(f"    ... 还有 {len(edu_tree) - 5} 个版本")
        
        # 显示搜索结果
        self.show_search_results(all_resources)
    
    def show_search_results(self, resources):
        """显示搜索结果"""
        self.clear_screen()
        self.print_header(f"搜索结果（共 {len(resources)} 个资源）")
        
        # 显示前20个资源
        display_count = min(20, len(resources))
        for i, r in enumerate(resources[:display_count], 1):
            name = r.get('resourceName', '未知')
            has_answer = "✓答案" if r.get('storageAnswerPath') else "✗答案"
            has_audio = "✓音频" if r.get('storageAudioPath') else "✗音频"
            print(f"  {i:2d}. {name[:40]:<40s} [{has_answer}] [{has_audio}]")
        
        if len(resources) > display_count:
            print(f"\n  ... 还有 {len(resources) - display_count} 个资源")
        
        # 选择下载数量
        print("\n" + "-"*40)
        print("  1. 下载全部资源")
        print("  2. 选择下载数量")
        print("  3. 选择特定资源下载")
        print("  0. 返回")
        
        choice = self.get_input("请选择: ", range(0, 4))
        
        if choice == 0:
            return
        elif choice == 1:
            self._download_resources(resources)
        elif choice == 2:
            count = self.get_input("请输入下载数量: ")
            if count and count > 0:
                self._download_resources(resources[:count])
        elif choice == 3:
            self._select_specific_resources(resources)
    
    def _select_specific_resources(self, resources):
        """选择特定资源下载"""
        print("\n请输入要下载的资源编号（多个编号用逗号分隔，如: 1,3,5-8）:")
        print("或输入 'all' 下载全部: ")
        
        selection = input("> ").strip()
        
        if selection.lower() == 'all':
            selected = resources
        else:
            selected_indices = self._parse_selection(selection, len(resources))
            selected = [resources[i] for i in selected_indices]
        
        if selected:
            self._download_resources(selected)
    
    def _parse_selection(self, selection, max_num):
        """解析用户选择（如: 1,3,5-8）"""
        indices = []
        parts = selection.split(',')
        
        for part in parts:
            part = part.strip()
            if '-' in part:
                start, end = part.split('-', 1)
                try:
                    start = int(start) - 1
                    end = int(end)
                    indices.extend(range(start, min(end, max_num)))
                except ValueError:
                    continue
            else:
                try:
                    idx = int(part) - 1
                    if 0 <= idx < max_num:
                        indices.append(idx)
                except ValueError:
                    continue
        
        return sorted(set(indices))
    
    def _download_resources(self, resources):
        """下载资源"""
        self.clear_screen()
        self.print_header("下载资源")
        
        # 询问下载选项
        print("\n下载选项:")
        print("  1. 下载学生书（主资源）")
        print("  2. 下载学生书 + 教师书（答案）")
        print("  3. 下载学生书 + 教师书 + 音频")
        print("  4. 全部下载（学生书 + 教师书 + 音频 + 视频）")
        
        choice = self.get_input("请选择: ", range(1, 5))
        
        download_student = True
        download_answer = choice >= 2
        download_audio = choice >= 3
        download_video = choice >= 4
        
        # 确认下载
        print(f"\n即将下载 {len(resources)} 个资源到 {self.output_dir}")
        confirm = input("确认下载? (y/n): ").strip().lower()
        
        if confirm != 'y':
            print("已取消下载")
            input("按回车继续...")
            return
        
        # 开始下载
        os.makedirs(self.output_dir, exist_ok=True)
        
        success_count = 0
        fail_count = 0
        
        for i, resource in enumerate(resources, 1):
            name = resource.get('resourceName', '未知')
            print(f"\n[{i}/{len(resources)}] {name[:50]}")
            
            # 下载学生书
            if download_student and resource.get('storagePath'):
                success, msg = self._download_file(
                    resource['storagePath'],
                    f"{name}.pdf"
                )
                print(f"  学生书: {msg}")
                success_count += 1 if success else 0
                fail_count += 0 if success else 1
            
            # 下载教师书
            if download_answer and resource.get('storageAnswerPath'):
                success, msg = self._download_file(
                    resource['storageAnswerPath'],
                    f"{name}_教师书.pdf"
                )
                print(f"  教师书: {msg}")
                success_count += 1 if success else 0
                fail_count += 0 if success else 1
            
            # 下载音频
            if download_audio and resource.get('storageAudioPath'):
                audio_paths = resource['storageAudioPath']
                if isinstance(audio_paths, str):
                    audio_paths = [audio_paths]
                elif not isinstance(audio_paths, list):
                    audio_paths = []
                
                for j, audio_path in enumerate(audio_paths):
                    if audio_path:
                        success, msg = self._download_file(
                            audio_path,
                            f"{name}_音频{j+1}.pdf"
                        )
                        print(f"  音频{j+1}: {msg}")
                        success_count += 1 if success else 0
                        fail_count += 0 if success else 1
            
            # 下载视频
            if download_video and resource.get('storageVideoPath'):
                success, msg = self._download_file(
                    resource['storageVideoPath'],
                    f"{name}_视频.mp4"
                )
                print(f"  视频: {msg}")
                success_count += 1 if success else 0
                fail_count += 0 if success else 1
            
            time.sleep(0.2)  # 避免请求过快
        
        print("\n" + "="*60)
        print(f"下载完成: 成功 {success_count} 个, 失败 {fail_count} 个")
        print(f"文件保存在: {os.path.abspath(self.output_dir)}")
        print("="*60)
        input("\n按回车继续...")
    
    def _download_file(self, url, filename, max_retries=3):
        """下载单个文件"""
        # 处理URL
        if url.startswith('//'):
            url = 'https:' + url
        elif not url.startswith('http'):
            url = BASE_URL + '/' + url.lstrip('/')
        
        # 清理文件名
        safe_filename = "".join(c for c in filename if c not in r'\/:*?"<>|')
        save_path = os.path.join(self.output_dir, safe_filename)
        
        for attempt in range(max_retries):
            try:
                # 检查文件是否已存在
                if os.path.exists(save_path):
                    size = os.path.getsize(save_path)
                    return True, f"已存在 ({self._format_size(size)})"
                
                # 下载文件
                response = self.session.get(url, timeout=120, stream=True)
                response.raise_for_status()
                
                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                
                # 保存文件
                downloaded = 0
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                
                return True, f"成功 ({self._format_size(downloaded)})"
                
            except Exception as e:
                # 删除不完整的文件
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                    except:
                        pass
                
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                
                return False, f"失败: {str(e)[:50]}"


def main():
    """主函数"""
    downloader = InteractiveDownloader()
    downloader.main_menu()


if __name__ == '__main__':
    main()