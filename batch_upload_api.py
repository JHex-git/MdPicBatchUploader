import os
import re
import requests
import json
from tqdm import tqdm
from time import sleep

# config
MAX_TRY_TIME = 10
TRY_INTERVAL = 60 # 2MSL一般是240，只要MAX_TRY_TIME * TRY_INTERVAL >= 2MSL一般就可以重新传成功

target = input('请输入要进行批量上传图片并替换链接的md文件的路径(含文件名)\n')
port = input('请输入PicGo监听的端口(如果不清楚，请查看README.md)\n')

regex = r'.*\!\[.+\]\((.*)\).*'
regex_tag = r'.*<img src="(.*?)".*'
regex_replace = r'(.*?\!\[.*?\]\()(.*?)(\))(.*)'
regex_tag_replace = r'(.*?<img src=")(.*?)(".*?/>)(.*)'
file_path = os.path.abspath(target)
result_path = file_path + '.output.md'
log_path = result_path + '.log'

if os.path.exists(result_path):
    print(f'{result_path} exists, please move it elsewhere first')
    exit(0)
else:
    with open(result_path, 'w', encoding='utf-8'):
        pass
if os.path.exists(log_path):
    print(f'{log_path} already exits, please move it elsewhere first')
    exit(0)

print('looking for all the file links to be replaced...')
# find all the local files to be replaced
local_files = []
remote_files = []
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

    for line in lines:
        result = re.findall(regex, line, re.S)
        if (len(result) != 0):
            local_files.extend(result)
        result = re.findall(regex_tag, line, re.S)
        if (len(result) != 0):
            local_files.extend(result)
local_files = set(local_files) # 去重


print('uploading...')
local2remote = {} # 本地名和远程地址的映射关系

with open(log_path, 'w', encoding='utf-8') as log:
    for file in tqdm(local_files):
        data = {'list': [file]}
        data = json.dumps(data)
        content_length = len(data)
        try_times = 0
        while try_times < MAX_TRY_TIME:
            try_times += 1
            post_result = requests.post(
                url="http://127.0.0.1:" + port + "/upload",
                headers={
                    "Host": "127.0.0.1:" + port,
                    "Connection": "keep-alive",
                    "Content-Length": str(content_length),
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Typora/0.9.98 Chrome/83.0.4103.122 Electron/9.3.4 Safari/537.36",
                    "Content-Type": "text/plain;charset=UTF-8",
                    "Accept": "*/*",
                    "Sec-Fetch-Site": "cross-site",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Dest": "empty",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "zh-CN"
                },
                data=data
                )
            post_result = json.loads(post_result.text)
            remote = post_result.get('result', None)
            if remote == None:
                print(f'fail to upload {file}')
                if try_times < MAX_TRY_TIME:
                    print(f'try again after {TRY_INTERVAL} seconds')
                    sleep(TRY_INTERVAL)
                    print(f'start upload again, {try_times + 1}/{MAX_TRY_TIME}')
                else:
                    print(f'can not upload {file}, please check if there is existing file on the remote')
                    log.write(f'fail to upload {file}, message is {post_result.get("message", None)}\n')
            else:
                local2remote.update({file: remote[0]})
                break
    
    print('replacing...')
    with open(result_path, 'w', encoding='utf-8') as result:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            index = 0
            for line in lines:
                remaining = line
                origin_index = index
                data = ''

                while remaining != '':
                    match_result = re.match(regex_replace, remaining, re.S)
                    if match_result != None:
                        remote = local2remote.get(match_result.group(2), None)
                        if remote != None:
                            data += match_result.group(1) + remote + match_result.group(3)
                            remaining = match_result.group(4)
                            index += 1
                        else:
                            data += match_result.group(1) + match_result.group(2) + match_result.group(3)
                            remaining = match_result.group(4)
                    else:
                        data += remaining
                        remaining = ''

                remaining = data
                data = ''
                while remaining != '':
                    match_result = re.match(regex_tag_replace, remaining, re.S)
                    if match_result != None:
                        remote = local2remote.get(match_result.group(2), None)
                        if remote != None:
                            data += match_result.group(1) + remote + match_result.group(3)
                            remaining = match_result.group(4)
                            index += 1
                        else:
                            data += match_result.group(1) + match_result.group(2) + match_result.group(3)
                            remaining = match_result.group(4)
                    else:
                        data += remaining
                        remaining = ''

                if origin_index != index:
                    log.write(f'replace "{line}" with {data}\n')
                result.write(data)
print('Done! Check the log file to see whether some pictures has been dealt wrongly!')
