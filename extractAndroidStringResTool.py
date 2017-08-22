#!/usr/bin/python
# coding=utf-8

"""
    提取出 Android 项目中硬编码的中文字符串到资源文件中
    如果某个文件不需要抽取，需要在 filterlist.txt 中添加文件名

    使用方法：
    filterlist.txt 是用于过滤文件的, 应与脚本文件放在同一目录

    1. 进入脚本文件所在目录
    2. 执行命令: python extractAndroidStringResTool.py [scanned_dir]

    参数解释:
    scanned_dir : 待扫描的目录(一般是项目根目录)

    后续特性开发:
    1. 支持扫描单文件
    2. 提高资源提取准确性
    3. 支持识别扫描文件所属类性质(Activity/Fragment/Non-Context-Based-Class)
    4. 提高资源 Id 替换成功率

    @author zhanghaifan
"""

import os
import sys
import re
import time
import timeit


pattern1 = re.compile(u"(\"[^\"']*?[\u4e00-\u9fff]+[^']*?\")")
pattern2 = re.compile(u"(\'[^\"']*?[\u4e00-\u9fff]+[^\"]*?\')")

string_res_file_header = "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
string_res_file_start_tag = "<resources>"
string_res_file_close_tag = "</resources>"
string_res_item = "\t<string name=\"%s\">%s</string>\n"

res_id_ref_pattern_java = "getString(R.string.%s)"
res_id_ref_pattern_xml = "\"@string/%s\""
res_id_ref_pattern_unknown = "getString(R.string.%s)"

filter_list_file_name = "filterlist.txt"

# 过滤的文件列表
class_list = []
# 过滤的文件前缀
prefix_list = []
# 过滤的目录
dir_list = []

# 模块自增标记
auto_increment_module = 0

res_file_path_to_value_dict = {}

replace_res_task_list = []

timestamp = int(time.time())


# 执行入口
def scan_dir(path):
    with open(filter_list_file_name, "r") as f:
        lines = f.readlines()

    for line in lines:
        line_info = line.strip()
        if line_info.startswith("#") or len(line_info) == 0:
            continue
        if line_info.startswith("--"):
            prefix_list.append(line_info[2:])
        elif line_info.startswith("**"):
            dir_list.append(line_info[2:])
        else:
            class_list.append(line_info)

    filenames = os.listdir(path)

    for name in filenames:
        file_path = os.path.join(path, name)

        if os.path.isdir(file_path):
            if not check_ignore_dir(name):
                scan_dir(file_path)
        else:
            if not check_ignore_file(name):
                scan_file(file_path)


def check_ignore_dir(dir_name):
    try:
        dir_list.index(dir_name)
        return True
    except ValueError:
        return False


# 判断某文件是否需要被忽略掉(根据后缀或者过滤配置文件来判断)
def check_ignore_file(filename):
    ext = os.path.splitext(filename)[1]
    name = os.path.basename(filename).split(".")[0]

    if ext != ".java" and ext != ".xml":
        return True

    # 匹配前缀列表
    for i in prefix_list:
        if name.startswith(i):
            return True

    try:
        class_list.index(name)
        return True
    # 未找到元素会抛异常
    except ValueError:
        return False


# String 资源元数据类
class StringResMetaData:
    # 被扫描的文件
    file_path = None

    # 被扫描行所在行号
    line_num = 0

    # 被扫描出的中文字符串
    value = []

    # 资源 Id
    res_id = None

    def __init__(self, file_path, line_num, value):
        self.file_path = file_path
        self.line_num = line_num
        self.value = value


# 替换资源任务类
class ReplaceResTask:
    # 资源文件路径
    res_file_path = None

    # 共用资源列表
    common_res_meta_data_list = []

    # 单一资源列表
    unique_res_meta_data_list = []

    # 源头资源列表
    source_res_meta_data_list = []

    # 共用对源头表
    common_to_source_res_meta_data_dict = {}

    def __init__(self, res_file_path, common_res_meta_data_list, unique_res_meta_data_list,
                 source_res_meta_data_list, common_to_source_res_meta_data_dict):
        self.res_file_path = res_file_path
        self.common_res_meta_data_list = common_res_meta_data_list
        self.unique_res_meta_data_list = unique_res_meta_data_list
        self.source_res_meta_data_list = source_res_meta_data_list
        self.common_to_source_res_meta_data_dict = common_to_source_res_meta_data_dict

# 扫描文件
def scan_file(file_path):
    with open(file_path) as f:
        string_meta_data_list = []

        for (num, line) in enumerate(f):
            line = line.strip()

            if line.find("//") != -1:
                line = line.split("//")[0].strip()

            if check_ignore_line(line):
                continue

            match = check_contain_chinese(line)

            if match:
                strings = get_chinese(line)
                line_num = num + 1

                for s in strings:
                    string_meta_data_list.append(StringResMetaData(file_path, line_num, s))

        extract_string(string_meta_data_list, f)


# 判断是否要忽略某一行
def check_ignore_line(line):
    if len(line) == 0 or line.startswith("//") or line.find("*") != -1 or line.startswith("<!"):
        return True
    else:
        return False


# 判断是否包含中文字符
def check_contain_chinese(line):
    decoded_line = line.decode('utf-8')
    for ch in decoded_line:
        if u'\u4e00' <= ch <= u'\u9fff':
            return True
    return False


# 截取每一行文字中的中文字符串
def get_chinese(line):
    decoded_line = line.decode('utf-8')

    if pattern1.search(decoded_line):
        pattern = pattern1
    else:
        pattern = pattern2

    results = pattern.findall(decoded_line)

    return results


# 从被扫描文件中提取出中文字符串
def extract_string(string_meta_data_list, scanned_file):
    if len(string_meta_data_list) == 0:
        return

    string_res_dir = get_string_res_dir(scanned_file)

    if string_res_dir is None:
        return

    string_res_file_path = os.path.join(string_res_dir, "res/values/strings.xml")

    print "extract string from file %s" % scanned_file.name

    if not res_file_path_to_value_dict.has_key(string_res_file_path):
        res_file_path_to_value_dict[string_res_file_path] = {}

    for (i, meta_data) in enumerate(string_meta_data_list):
        if res_file_path_to_value_dict[string_res_file_path].has_key(meta_data.value):
           res_file_path_to_value_dict[string_res_file_path][meta_data.value].append(meta_data)
        else:
           res_file_path_to_value_dict[string_res_file_path][meta_data.value] = []
           res_file_path_to_value_dict[string_res_file_path][meta_data.value].append(meta_data)


# 获取资源文件目录
def get_string_res_dir(file):
    m = re.match(r".*/src/main/", file.name)

    if m is not None:
        return m.group(0)

    return None


def do_replace():
    print "\ndo_replace()......start"

    gen_task_list()

    if len(replace_res_task_list) == 0:
        print "\ndo_replace()......no task"
        print "\ndo_replace()......end"
        return

    for task in replace_res_task_list:
        print "\ndo_replace()......replacing res file", task.res_file_path

        gen_res_id(task)
        replace_string_res_file(task)
        replace_source_file(task)

    print "\ndo_replace()......end"


# 构建 ReplaceResTask 列表
def gen_task_list():
    print "\ngen_task_list()......start"

    global replace_res_task_list

    for res_file_path, value_dict in res_file_path_to_value_dict.items():
        common_res_meta_data_list = []
        unique_res_meta_data_list = []
        source_res_meta_data_list = []
        common_to_source_res_meta_data_dict = {}
        task = ReplaceResTask(res_file_path, common_res_meta_data_list, unique_res_meta_data_list,
                              source_res_meta_data_list, common_to_source_res_meta_data_dict)
        replace_res_task_list.append(task)

        for value, meta_data_list in value_dict.items():
            if len(meta_data_list) == 0:
                continue

            is_common = len(meta_data_list) > 1

            if not is_common:
                unique_res_meta_data_list.append(meta_data_list[0])
                source_res_meta_data_list.append(meta_data_list[0])
            else:
                common_meta_data = StringResMetaData("", -1, meta_data_list[0].value)
                common_res_meta_data_list.append(common_meta_data)
                common_to_source_res_meta_data_dict[common_meta_data] = []

                for meta_data in meta_data_list:
                    source_res_meta_data_list.append(meta_data)
                    common_to_source_res_meta_data_dict[common_meta_data].append(meta_data)
    # Log
    if False:
        for task in replace_res_task_list:
            print "\ntask's res_file_path =", task.res_file_path

            print "\ntask's source_res_meta_data_list......"
            for i in task.source_res_meta_data_list:
                print i.file_path, i.value, i.res_id, i.line_num

            print "\ntask's unique_res_meta_data_list......"
            for i in task.unique_res_meta_data_list:
                print i.file_path, i.value, i.res_id, i.line_num

            print "\ntask's common_res_meta_data_list......"
            for i in task.common_res_meta_data_list:
                print i.file_path, i.value, i.res_id, i.line_num

            print "\ntask's common_to_source_res_meta_data_dict......"
            print task.common_to_source_res_meta_data_dict

    print "\ngen_task_list()......end"


# 在 string 资源文件中生成资源 Id
def replace_string_res_file(task):
    string_res_file_path = task.res_file_path
    content = ""

    try:
        with open(string_res_file_path, "r") as f:
            content = f.read()
    except IOError:
        basedir = os.path.dirname(string_res_file_path)
        if not os.path.exists(basedir):
            os.makedirs(basedir)
        open(string_res_file_path, "a").close()

    if string_res_file_close_tag in content:
        content = content.replace(string_res_file_close_tag, "")

    if not string_res_file_start_tag in content:
        content += string_res_file_start_tag
        content += "\n"

    if len(task.unique_res_meta_data_list) > 0:
        content += "\n"

    for (i, meta_data) in enumerate(task.unique_res_meta_data_list):
        content += string_res_item % (meta_data.res_id, meta_data.value[1:-1].encode("utf-8"))

    if len(task.common_res_meta_data_list) > 0:
        content += "\n"

    for (i, meta_data) in enumerate(task.common_res_meta_data_list):
        content += string_res_item % (meta_data.res_id, meta_data.value[1:-1].encode("utf-8"))

    if not string_res_file_close_tag in content:
        content += string_res_file_close_tag
        content += "\n"

    with open(string_res_file_path, "w") as f:
        f.write(content)

    print "\nreplace_string_res_file()......replaced res file", string_res_file_path


# 在源文件中替换字符串成资源 Id
def replace_source_file(task):
    for (i, meta_data) in enumerate(task.source_res_meta_data_list):
        scanned_file_path = meta_data.file_path

        with open(scanned_file_path, "r") as f:
            lines = f.readlines()

        ext = os.path.splitext(os.path.basename(scanned_file_path))[1]

        if ext == ".java":
            res_id_ref_pattern = res_id_ref_pattern_java
        elif ext == ".xml":
            res_id_ref_pattern = res_id_ref_pattern_xml
        else:
            res_id_ref_pattern = res_id_ref_pattern_unknown

        res_id_ref = res_id_ref_pattern % meta_data.res_id
        lines[meta_data.line_num - 1] = lines[meta_data.line_num - 1].replace(meta_data.value.encode("utf-8"), res_id_ref)

        with open(scanned_file_path, "w") as f:
            f.writelines(lines)

    print "\nreplace_source_file()......replaced res file", task.res_file_path


# 为资源元数据列表中的元素生成资源 Id
def gen_res_id(task):
    print "\ngen_res_id()......start"

    unique_res_meta_data_list = task.unique_res_meta_data_list

    for (i, meta_data) in enumerate(unique_res_meta_data_list):
        meta_data.res_id = "%s_res_id_%s_%s" % (os.path.splitext(os.path.basename(meta_data.file_path))[0],
                str(i), str(timestamp))

    common_res_meta_data_list = task.common_res_meta_data_list

    for (i, meta_data) in enumerate(common_res_meta_data_list):
        meta_data.res_id = "%s_res_id_%s_%s" % (get_common_prefix(task.res_file_path),
                str(i), str(timestamp))

        if task.common_to_source_res_meta_data_dict.has_key(meta_data):
            source_res_meta_data_list = task.common_to_source_res_meta_data_dict[meta_data]

            for source_res_meta_data in source_res_meta_data_list:
                source_res_meta_data.res_id = meta_data.res_id

    if False:
        print "\nprinting common meta_data..."
        for meta_data in task.common_res_meta_data_list:
            print meta_data.file_path
            print meta_data.value, meta_data.res_id

        print "\nprinting unique meta_data..."
        for meta_data in task.unique_res_meta_data_list:
            print meta_data.file_path
            print meta_data.value, meta_data.res_id

        print "\nprinting source meta_data..."
        for meta_data in task.source_res_meta_data_list:
            print meta_data.file_path
            print meta_data.value, meta_data.res_id, meta_data.line_num

    print "\ngen_res_id()......end"


# 获取资源 Id 名称的前缀
def get_common_prefix(file_path):
    m = re.match(r".*/(.*?)/src/main/", file_path)

    if m is not None:
        return m.group(1) + "_common"

    global auto_increment_module

    common_prefix = "common_%d" % auto_increment_module
    auto_increment_module = auto_increment_module + 1

    return common_prefix


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "No argument inputted, please check."
    else:
        workspace_dir = sys.argv[1]

        start = timeit.default_timer()

        scan_dir(workspace_dir)
        do_replace()

        print "\nCosts : ", (timeit.default_timer() - start)
