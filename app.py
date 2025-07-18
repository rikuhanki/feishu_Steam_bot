import os
import re
import json
import requests
import threading
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup

# --- 配置信息 ---
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

app = Flask(__name__)

# --- 通用工具函数 (与之前版本相同) ---

def get_feishu_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("code") == 0:
            print(">>> [Log] 成功获取 tenant_access_token")
            return data.get("tenant_access_token")
        else:
            print(f"!!! [Error] 获取飞书 token 失败: {data}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"!!! [Error] 请求飞书 token 异常: {e}")
        return None

def reply_feishu_message(message_id, content, title="🎮 Steam 游戏分析报告"):
    print(">>> [Log] 准备回复飞书消息...")
    token = get_feishu_tenant_access_token()
    if not token: 
        print("!!! [Error] 因 token 获取失败，无法回复消息")
        return
        
    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
    headers = { "Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8" }
    card_content = {
        "config": {"wide_screen_mode": True},
        "header": { "template": "blue", "title": {"tag": "plain_text", "content": title} },
        "elements": [{"tag": "markdown", "content": content}]
    }
    payload = { "msg_type": "interactive", "content": json.dumps(card_content) }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        print(f">>> [Log] 成功发送飞书消息: {response.json().get('msg')}")
    except Exception as e:
        print(f"!!! [Error] 发送飞书消息失败: {e}")

# --- “游戏评测大师”相关函数 ---

def get_steam_game_data(steam_url):
    try:
        print(f">>> [Log] [游戏模式] 开始抓取 Steam 页面: {steam_url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cookie': 'birthtime=568022401; lastagecheckage=1-January-1990; wants_mature_content=1'
        }
        response = requests.get(steam_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('div', class_='apphub_AppName').text.strip()
        short_desc = soup.find('div', class_='game_description_snippet').text.strip()
        tags = [tag.text.strip() for tag in soup.find_all('a', class_='app_tag')]
        full_desc = soup.find('div', id='game_area_description').get_text(separator='\n', strip=True)
        print(">>> [Log] [游戏模式] 成功抓取 Steam 数据")
        return {"title": title, "short_desc": short_desc, "tags": tags[:10], "full_desc": full_desc[:2000]}
    except Exception as e:
        print(f"!!! [Error] [游戏模式] 抓取 Steam 数据失败: {e}")
        return None

def call_game_review_ai(game_data):
    """【V2 新版】调用 DeepSeek AI 进行更深入的游戏分析"""
    print(">>> [Log] [游戏模式] 正在调用 DeepSeek AI (评测大师模式)...")
    prompt = f"""
    你是一位顶级的游戏行业分析师和资深评测家。请根据以下 Steam 游戏信息，进行深入、全面、专业的分析。

    **游戏名称**: {game_data['title']}
    **游戏标签**: {', '.join(game_data['tags'])}
    **简短介绍**: 
    {game_data['short_desc']}
    **详细介绍**:
    {game_data['full_desc']}

    **你的任务 (请严格按点回复)**:
    1.  **核心玩法**: 用2-3句话总结游戏的核心玩法与特色。
    2.  **亮点 ✨**: 列出这款游戏最吸引人的2-3个优点。
    3.  **槽点 ⛈️**: 列出这款游戏可能存在的2-3个缺点或风险。
    4.  **目标用户与竞品**: 
        - 根据标签和介绍，分析这款游戏主要的目标用户群体是谁？
        - 在当前市场上，有哪些知名的同类竞品？简单对比一下它们的质量和特色。
    5.  **同类游戏市场分析**: 
        - 综合来看，这款游戏所属的品类（比如：肉鸽、模拟经营、开放世界RPG）在Steam上的总体受欢迎程度如何？
        - 玩家对这类游戏通常有哪些期待？（比如：期待高自由度、期待剧情深度、期待玩法创新等）
    6.  **好玩指数**: 综合以上所有信息，给出一个1-10分的好玩指数（请给出整数），并用一句话解释打分理由。

    请严格按照以下格式输出，使用 Markdown 语法：
    ### 核心玩法
    [内容]

    ### 亮点 ✨
    - [内容]
    - [内容]

    ### 槽点 ⛈️
    - [内容]
    - [内容]

    ### 目标用户与竞品
    [内容]
    
    ### 同类游戏市场分析
    [内容]

    ### 好玩指数
    **[分数]/10** - [打分理由]
    """
    url = "https://api.deepseek.com/chat/completions"
    headers = { "Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_API_KEY}" }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": "你是一位顶级的游戏行业分析师和资深评测家。"}, {"role": "user", "content": prompt}],
        "temperature": 0.7, "max_tokens": 2048 # 增加了 token 上限以容纳更丰富的内容
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        data = response.json()
        print(">>> [Log] [游戏模式] 成功获取 DeepSeek AI 分析结果")
        return data['choices'][0]['message']['content']
    except Exception as e:
        print(f"!!! [Error] [游戏模式] 调用 DeepSeek API 失败: {e}")
        return "抱歉，AI 分析服务暂时出了一点小问题..."

def process_game_analysis(steam_url, message_id):
    """处理游戏分析的后台线程任务"""
    print("--- [Log] [游戏模式] 后台线程启动 ---")
    game_data = get_steam_game_data(steam_url)
    if not game_data:
        reply_feishu_message(message_id, f"哎呀，无法从这个链接获取游戏信息，请检查链接是否正确或稍后再试。\n{steam_url}", "处理失败")
        return
    ai_summary = call_game_review_ai(game_data)
    final_content = f"**{game_data['title']}**\n\n" + ai_summary + f"\n\n[前往 Steam 商店页面]({steam_url})"
    reply_feishu_message(message_id, final_content, f"🎮 {game_data['title']} 分析报告")
    print("--- [Log] [游戏模式] 后台线程执行完毕 ---")

# --- “通用AI助手”相关函数 ---

def call_general_ai(user_question):
    """【新功能】调用 DeepSeek AI 回答通用问题"""
    print(">>> [Log] [通用模式] 正在调用 DeepSeek AI (通用助手模式)...")
    url = "https://api.deepseek.com/chat/completions"
    headers = { "Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_API_KEY}" }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": "你是一个乐于助人、知识渊博的通用人工智能助手。"}, {"role": "user", "content": user_question}],
        "temperature": 0.7, "max_tokens": 2048
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        data = response.json()
        print(">>> [Log] [通用模式] 成功获取 DeepSeek AI 回答")
        return data['choices'][0]['message']['content']
    except Exception as e:
        print(f"!!! [Error] [通用模式] 调用 DeepSeek API 失败: {e}")
        return "抱歉，我的大脑暂时出了一点小问题，请稍后再试。"

def process_general_chat(user_question, message_id):
    """处理通用聊天需求的后台线程任务"""
    print("--- [Log] [通用模式] 后台线程启动 ---")
    ai_response = call_general_ai(user_question)
    reply_feishu_message(message_id, ai_response, "🤖 AI 助手")
    print("--- [Log] [通用模式] 后台线程执行完毕 ---")

# --- 主入口与路由 ---

@app.route("/feishu/event", methods=["POST"])
def feishu_event_handler():
    """接收飞书事件的主入口，并根据内容分发任务"""
    data = request.json
    print(f"\n---------- [Log] 收到新请求: {data.get('header', {}).get('event_type')} ----------")

    if "challenge" in data:
        print(">>> [Log] 正在处理 URL 验证...")
        return jsonify({"challenge": data["challenge"]})

    event = data.get("event")
    if not (event and event.get("message")):
        return jsonify({"status": "ignored"})

    message = event.get("message")
    chat_type = message.get("chat_type")
    mentions = message.get("mentions", [])
    message_id = message.get("message_id")

    is_group_at_message = (chat_type == "group" and len(mentions) > 0)
    is_p2p_message = (chat_type == "p2p")
    # 话题组也需要 @
    is_topic_at_message = (chat_type == "topic" and len(mentions) > 0)

    if is_group_at_message or is_p2p_message or is_topic_at_message:
        try:
            content = json.loads(message.get("content", "{}"))
            text_content = content.get("text", "").strip()
            # 移除@机器人本身的内容，得到纯净的用户问题
            for mention in mentions:
                text_content = text_content.replace(mention.get('text', ''), '')
            user_question = text_content.strip()

            match = re.search(r'(https://store\.steampowered\.com/app/\d+)', user_question)
            
            if match:
                # 【分发任务】检测到 Steam 链接，进入游戏评测模式
                print(">>> [Log] 检测到 Steam 链接，进入游戏评测模式")
                steam_url = match.group(0)
                thread = threading.Thread(target=process_game_analysis, args=(steam_url, message_id))
                thread.start()
            elif user_question:
                # 【分发任务】没有检测到链接，但有其他文本，进入通用助手模式
                print(">>> [Log] 未检测到链接，进入通用助手模式")
                thread = threading.Thread(target=process_general_chat, args=(user_question, message_id))
                thread.start()
            else:
                 print(">>> [Log] 消息为空，忽略。")

        except Exception as e:
            print(f"!!! [Error] 处理消息时发生严重错误: {e}")

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
