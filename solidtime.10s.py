#!/usr/bin/python3
# filepath: /Users/wang/Library/Mobile Documents/com~apple~CloudDocs/swiftbar/solidtime/solidtime.1s.py

# <xbar.title>SolidTime Timer Status</xbar.title>
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

def get_active_time_entry():
    """获取当前是否存在正在计时的任务"""
    response = api_request("/users/me/time-entries/active", use_cache=False)
    # 记录请求时间为小时:分钟格式
    global REQUEST_TIME
    REQUEST_TIME = time.strftime("%H:%M:%S", time.localtime())
    if "error" in response:
        return None
    return response.get("data")

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

def format_time_entry(entry,task,duration):
    """格式化时间条目为Alfred URL"""
    # 格式化开始时间为 "2025年05月15日 12:51"
    start_time = time.strptime(entry['start'], "%Y-%m-%dT%H:%M:%SZ")
    # 将UTC时间转换为本地时间
    utc_start_time = calendar.timegm(start_time)
    local_start_time = time.localtime(utc_start_time)
    formatted_start_time = time.strftime("%Y年%m月%d日 %H:%M", local_start_time)

    # 获取当前时间并格式化为 "13:11"
    current_time = time.strftime("%H:%M", time.localtime())
    timeText = f"【用时】\n\n{formatted_start_time} - {current_time} 持续：{duration}"
    argument = {
        "title": task,
        "subtitle": f"{entry.get('description', '')}\n\n{timeText}\n\n【总结】：\n",
        "type": "SOLIDTIME_TIME_ENTRY",
        "stprojectid": entry.get("project_id"),
        "sttaskid": entry.get("task_id"),
        "sttimeentryid": entry.get("id"),
    }
    # 使用 urllib.parse.quote 进行标准 URL 编码（包括处理特殊字符、换行）
    argument_json = json.dumps(argument, ensure_ascii=False, separators=(',', ':'))
    encoded_argument = urllib.parse.quote(argument_json, safe='')

    # 构造 Alfred Trigger URL
    return f"alfred://runtrigger/com.pazer.timeentry/timeentry/?argument={encoded_argument}"

def format_project_arg(title,project_id):
    argument = {
        "title": title,
        "type": "SOLIDTIME_PROJECT",
        "stprojectid": project_id,
    }
    # 使用 urllib.parse.quote 进行标准 URL 编码（包括处理特殊字符、换行）
    argument_json = json.dumps(argument, ensure_ascii=False, separators=(',', ':'))
    encoded_argument = urllib.parse.quote(argument_json, safe='')

    # 构造 Alfred Trigger URL
    return f"alfred://runtrigger/com.pazer.timeentry/timeentry/?argument={encoded_argument}"


# {
#     "title": "📜工具",
#     "subtitle": " 📅485391小时前 耗时:不到1分钟 【目标】：\n\n【预期时间】：\n\n\nSolidTime 流程中加入重复上一次任务的功能；\n\nAlfred 流程；\n\nSwiftBar 按钮",
#     "type": "SOLIDTIME_HISTORY",
#     "sttaskid": "f0718da3-54cc-4d26-9ff6-d66780daa159",
#     "stprojectid": "02d8297d-3544-43d7-90ed-4d6db604c5dc"
# }
def format_history_arg(title,task_id,project_id):
    argument = {
        "title": title,
        "type": "SOLIDTIME_HISTORY",
        "sttaskid": task_id,
        "stprojectid": project_id,
    }
    # 使用 urllib.parse.quote 进行标准 URL 编码（包括处理特殊字符、换行）
    argument_json = json.dumps(argument, ensure_ascii=False, separators=(',', ':'))
    encoded_argument = urllib.parse.quote(argument_json, safe='')

    # 构造 Alfred Trigger URL
    return f"alfred://runtrigger/com.pazer.timeentry/timeentry/?argument={encoded_argument}"

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
    
def main():
    organization_id = get_organization_id()
    if not organization_id:
        print("Error: 无法获取组织信息")
        return
    active_entry = get_active_time_entry()
    if active_entry:
        active_cache_key = "active_entry" + active_entry["task_id"]
        result = cache_handler(active_cache_key, None, 60*60)
        if result is None:
            tasks = get_tasks(active_entry["project_id"], organization_id) 
            # 根据entry 的 task_id 获取任务
            if active_entry:
                result = {}  # Initialize result as an empty dictionary
                for task in tasks:
                    if task["id"] == active_entry["task_id"]:
                        result["task_name"] = task['name']
                        result["description"] = active_entry['description']
                        break
            result["start_time"] = active_entry["start"]
        elapsed = int((time.time() - calendar.timegm(time.strptime(result["start_time"], "%Y-%m-%dT%H:%M:%SZ"))) / 60)
        hours, minutes = divmod(elapsed, 60)
        duration = ""
        if hours > 0:
            duration = f"⌛️ {hours} 小时 {minutes} 分钟"
        else:
            duration = f"⌛️ {minutes} 分钟"
        
        argument = format_time_entry(active_entry, result["task_name"], duration)
        cache_handler(active_cache_key, result, 60*60)
        active_entry["title"] = result["task_name"]
        cache_handler("recent_entry", active_entry, deletable=False)
        bash_command = f"bash='open' param1={argument} {BASH_COMMOND_STRING}"
        tooltip = result['description']
        print(f"🎯 {result['task_name']} {duration} ")

        print(f"📝 任务描述 | {result['description']}")
        print(f"---")
        print(f"🟥 停止计时 | {bash_command}") 
    else:
        result = cache_handler("projects", None, 60*60)
        
        if result is None:
            projects = get_projects(organization_id)
            result = projects
            cache_handler("projects", result, 60*60)
        project_list = []
        for project in result:
            project_name = project['name']
            project_id = project['id']
            arg = format_project_arg(project_name, project_id)
            project_list.append(f"📁 {project_name} | bash='open' param1={arg} {BASH_COMMOND_STRING}")
        
        print(f"📁 项目列表")
        print(f"---")
        recentItem = cache_handler("recent_entry", None, 3600*60,deletable=False)
        if recentItem:
            herf = format_history_arg(recentItem['title'], recentItem['task_id'], recentItem['project_id'])
            print(f"🔄 {recentItem['title']} | bash='open' param1={herf} {BASH_COMMOND_STRING}")
            print(f"---")
        else:
            print(f"🔄 最近任务 ")
            print(f"---")
        for project_entry in project_list:
            print(project_entry)
        print(f"---")


        print(f"🏢 PazerStudio | href='https://pazergame.com'")
    print(f"---")
    TMP_PATH = get_cache_dir()
    print(f"🧹 清除缓存 | bash='rm' param1='-rf' param2='{TMP_PATH}'refresh=true terminal=false ")
    print(f"last time: {REQUEST_TIME}")

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