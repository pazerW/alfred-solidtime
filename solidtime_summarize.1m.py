#!/usr/bin/python3
# filepath: /Users/wang/Library/Mobile Documents/com~apple~CloudDocs/swiftbar/solidtime/solidtime.1s.py

# <xbar.title>SolidTime Statistical Report </xbar.title>
# <xbar.version>v1.1</xbar.version>
# <xbar.author>PazerStudio</xbar.author>
# <xbar.author.github>PazerW</xbar.author.github>
# <xbar.desc>Displays whether SolidTime is currently tracking time.</xbar.desc>
# <xbar.dependencies>python</xbar.dependencies>
# <xbar.abouturl>https://github.com/your-repo</xbar.abouturl>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>
# <swiftbar.hideSwiftBar>true</swiftbar.hideSwiftBar>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>

import requests
import time, calendar
import json
import re
import os
import sys
from datetime import datetime, timedelta, timezone
import urllib.parse


# 读取配置文件
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
try:
    with open(CONFIG_PATH, "r") as config_file:
        config = json.load(config_file)
        BASE_URL = config["BASE_URL"]
        API_TOKEN = config["API_TOKEN"]
except FileNotFoundError:
    print("Error: 配置文件 config.json 未找到！")
    BASE_URL = None
    API_TOKEN = None

ORGANIZATION_ID = None  # 全局变量，用于缓存组织ID
                                                       

# 可删除缓存目录
DELETABLE_CACHE_DIR = "/tmp/swiftbar/solidtime/tmp/"
# 不可删除缓存目录
UNDELETABLE_CACHE_DIR = "/tmp/swiftbar/solidtime/"

BASH_COMMOND_STRING = "param2='&&' param3='sleep' param4='30' param5='&&' param6='rm' param7='-rf' param8='{DELETABLE_CACHE_DIR}' refresh=true terminal=false"

def get_cache_dir(deletable=True):
    return DELETABLE_CACHE_DIR if deletable else UNDELETABLE_CACHE_DIR

# 缓存字典
CACHE = {}
# 最后请求时间记录请求时间
REQUEST_TIME = ""

def api_request(endpoint, method="GET", data=None, use_cache=True, cache_duration=60*60):
    """
    统一的API请求方法，支持缓存
    :param endpoint: API端点
    :param method: HTTP方法 (GET, POST)
    :param data: POST请求数据
    :param use_cache: 是否使用缓存
    :param cache_duration: 缓存时间（秒）
    """
    global CACHE
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    url = f"{BASE_URL}{endpoint}"

    # 检查缓存
    cache_key = f"{method}:{url}:{json.dumps(data, sort_keys=True)}"
    current_time = time.time()
    if use_cache:
        # 将缓存键转换为文件名
        sanitized_cache_key = re.sub(r'[^\w\-_.]', '_', cache_key)
        TMP_PATH = get_cache_dir()
        cache_file = f"{TMP_PATH}{sanitized_cache_key}_solidtime_cache.json"
        try:
            # 读取缓存文件
            with open(cache_file, "r") as f:
                file_cache = json.load(f)
                cached_data = file_cache.get(cache_key, {})
                timestamp = cached_data.get("timestamp", 0)
                if current_time - timestamp < cache_duration:
                    return cached_data.get("response")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        else:
            raise ValueError("Unsupported HTTP method")
        response.raise_for_status()
        result = response.json()

        # 更新缓存
        if use_cache:
            # 将响应缓存到本地文件
            sanitized_cache_key = re.sub(r'[^\w\-_.]', '_', cache_key)
            TMP_PATH = get_cache_dir()
            cache_file = f".{TMP_PATH}{sanitized_cache_key}_solidtime_cache.json"
            try:
                # 确保缓存目录存在
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                file_cache = {} 
                # 读取现有缓存
                try:
                    with open(cache_file, "r") as f:
                        file_cache = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    file_cache = {}

                # 更新缓存
                file_cache[cache_key] = {"response": result, "timestamp": current_time}

                # 写入缓存文件
                with open(cache_file, "w") as f:
                    json.dump(file_cache, f)
            except Exception as e:
                print(f"Error writing cache file: {e}")

            # 更新内存缓存
            CACHE[cache_key] = (result, current_time)

        return result
    except requests.RequestException as e:
        return {"error": str(e)}

def get_organization_id():
    """获取并缓存组织ID"""
    global ORGANIZATION_ID
    if ORGANIZATION_ID:
        return ORGANIZATION_ID
    response = api_request("/users/me/memberships")
    if "error" in response:
        print(f"Error: {response['error']}")
        return None
    memberships = response.get("data", [])
    if memberships:
        ORGANIZATION_ID = memberships[0]["organization"]["id"]
        return ORGANIZATION_ID
    return None

def get_projects(organization_id):
    """获取组织下的所有项目"""
    response = api_request(f"/organizations/{organization_id}/projects")
    if "error" in response:
        print(f"Error: {response['error']}")
        return []
    return response.get("data", [])

def get_tasks(project_id,organization_id):
    """获取项目下的所有任务"""
    response = api_request(f"/organizations/{organization_id}/tasks?project_id={project_id}")
    if "error" in response:
        print(f"Error: {response['error']}")
        return []
    return response.get("data", [])

def get_today_time_entries(organization_id):
    """获取今天的时间条目"""

    # 这里 today 变量可用于日期参数，start_of_day/end_of_day 可用于精确时间范围
    # 获取本地时区的今天的开始和结束时间（ISO 8601 格式，带时区）

    # 获取本地时区信息
    # 获取本地时区的今天的开始和结束时间（ISO 8601 格式，带时区）
    now = datetime.now().astimezone()
    today = now.date()
    start_of_day = datetime.combine(today, datetime.min.time(), tzinfo=now.tzinfo).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_of_day = datetime.combine(today, datetime.max.time(), tzinfo=now.tzinfo).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    response = api_request(f"/organizations/{organization_id}/time-entries?start={start_of_day}&end={end_of_day}",use_cache=False)
    if "error" in response:
        print(f"Error: {response}")
        return []
    return response.get("data", [])

def get_tags(organization_id):
    """获取组织下的所有标签"""
    response = api_request(f"/organizations/{organization_id}/tags")
    if "error" in response:
        print(f"Error: {response['error']}")
        return []
    return response.get("data", [])

def summarize_time_entries(entries):
    """
    汇总时间条目，计算总时长和每个任务的时长
    :param entries: 时间条目列表
    :return: 总时长（分钟）和每个任务的时长字典
    """
    total_duration = 0
    total_count = 0
    organization_id = get_organization_id()
    projects = get_projects(organization_id)

    for entry in entries:
        total_count += 1
        start_time = entry["start"]
        entry["project"] = next((project for project in projects if project["id"] == entry["project_id"]), None)
        tasks = get_tasks(entry["project_id"], organization_id)
        entry["task"] = next((task for task in tasks if task["id"] == entry["task_id"]), None)
        if entry["duration"] == 0:
            # entry["start"] is likely a string, so parse it to datetime

            if isinstance(start_time, str):
                try:
                    # Try parsing ISO 8601 format
                    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                except Exception:
                    # Fallback for other formats if needed
                    start_dt = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            elapsed_seconds = (datetime.now().astimezone() - start_dt).total_seconds()
            entry["duration"] = int(elapsed_seconds)  # 将秒转换为整数
            total_duration += elapsed_seconds / 60
        else:
            total_duration += entry["duration"] / 60  # 将秒转换为分钟

    hours = int(total_duration // 60)
    minutes = int(total_duration % 60)
    return f"{hours}:{minutes:02d}", total_count ,entries

def analyze_time_entries(entries):
    """
    分析时间条目，计算任务中每个Tag 的总时长
    :param entries: 时间条目列表
    :return: 每个Tag的总时长字典
    """
    tag_durations = {}
    project_durations = {}
    organization_id = get_organization_id()
    tags = get_tags(organization_id)
    for entry in entries:
        if "tags" in entry and entry["tags"]:
            duration = entry["duration"] / 60  # 将秒转换为分钟
            for tag in entry["tags"]:
                tag_name = next ((t["name"] for t in tags if t["id"] == tag), None)
                if tag_name not in tag_durations:
                    tag_durations[tag_name] = 0
                tag_durations[tag_name] += duration
        if "project" in entry and entry["project"]:
            project_name = entry["project"]["name"]
            if project_name not in project_durations:
                project_durations[project_name] = {"duration": 0, "tasks": {}}
            project_durations[project_name]["duration"] += entry["duration"] / 60

            # 将 task 放到对应的 project 下
            if "task" in entry and entry["task"]:
                task_name = entry["task"]["name"]
                if task_name not in project_durations[project_name]["tasks"]:
                    project_durations[project_name]["tasks"][task_name] = 0
                project_durations[project_name]["tasks"][task_name] += entry["duration"] / 60

    return tag_durations, project_durations


def cache_handler(cache_key, data=None, cache_duration=3600,deletable=True):
        """
        处理缓存的读取和写入
        :param cache_key: 缓存键
        :param data: 要写入缓存的数据 (如果为 None，则尝试读取缓存)
        :param cache_duration: 缓存时间（秒）
        :return: 如果是读取操作，返回缓存数据；如果是写入操作，返回 True
        """
        sanitized_cache_key = re.sub(r'[^\w\-_.]', '_', cache_key)
        TMP_PATH = get_cache_dir(deletable)
        cache_file = f".{TMP_PATH}{sanitized_cache_key}_solidtime_cache.json"
        current_time = time.time()

        if data is None:
            # 读取缓存
            try:
                with open(cache_file, "r") as f:
                    file_cache = json.load(f)
                    cached_data = file_cache.get(cache_key, {})
                    timestamp = cached_data.get("timestamp", 0)
                    if current_time - timestamp < cache_duration:
                        return cached_data.get("response")
            except (FileNotFoundError, json.JSONDecodeError):
                return None
        else:
            # 写入缓存
            try:
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                file_cache = {}
                try:
                    with open(cache_file, "r") as f:
                        file_cache = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    file_cache = {}

                file_cache[cache_key] = {"response": data, "timestamp": current_time}
                with open(cache_file, "w") as f:
                    json.dump(file_cache, f)
                return True
            except Exception as e:
                print(f"Error writing cache file: {e}")
                return False

def num_to_emoji(num_str):
    mapping = {'0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣', '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'}
    return ''.join(mapping.get(ch, ch) for ch in str(num_str))
    
def main():
    organization_id = get_organization_id()
    if not organization_id:
        print("Error: 无法获取组织信息")
        return
    total_duration ,total_count ,entries =  summarize_time_entries(get_today_time_entries(organization_id))
    # 数字替换为 emoji


    print(f"⏰**{num_to_emoji(total_duration)}**  🍅**{num_to_emoji(total_count)}**个 | md=true font=Menlo size=13 color=#727475")
    
    tag,project =  analyze_time_entries(entries)
    print(f"---")
    print(f"分类| color=#FF9FF3 font=Menlo size=12")
    for tag_name, duration in tag.items():
        hours, minutes = divmod(duration, 60)
        print(f"🏷️ {tag_name} - {int(hours)} 小时 {int(minutes)} 分钟 | href=''")
    print(f"---")
    print(f"项目 |color=#1DD1A1 font=Menlo size=12")
    for project_name, project_info in project.items():

        duration = project_info["duration"]
        hours, minutes = divmod(duration, 60)
        print(f"🗄️ {project_name} - {int(hours)} 小时 {int(minutes)} 分钟 | href=''")
        for task_name, task_duration in project_info["tasks"].items():
            task_hours, task_minutes = divmod(task_duration, 60)
            print(f"   ✅ {task_name} - {int(task_hours)} 小时 {int(task_minutes)} 分钟 | href=''")
        print(f"---")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        cache_dir = get_cache_dir()
        print(f"清理缓存目录: {cache_dir}")
        try:
            for root, dirs, files in os.walk(cache_dir):
                for file in files:
                    os.remove(os.path.join(root, file))
            print("缓存已清理")
        except Exception as e:
            print(f"清理缓存时出错: {e}")
        sys.exit(0)
    main()