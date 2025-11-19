import requests
from bs4 import BeautifulSoup
import json 
import time
import pandas as pd
import random
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options

# --- 配置信息 ---
URL_LIST_FILENAME = "urls/dialogue_urls_world.csv"
OUTPUT_DIALOGUE_FILENAME = "dialogue/dialogue_data_world.json"
OUTPUT_NARRATIVE_FILENAME = "narration/narrative_data_world.txt"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

CHROME_DRIVER_PATH = r"D:\driverchrome\chromedriver.exe" 

# --- 选择器定义 ---
DIALOGUE_AREA_CLASS = "obc-tmpl-interactiveDialogue"
DIALOGUE_NODE_CLASS = "content-box"
EXPAND_BUTTON_SELECTOR = f'.{DIALOGUE_AREA_CLASS} .obc-tmpl__expand-text'


# --- 核心提取函数 ---
def fetch_and_parse_dialogue_selenium(driver, url, dialogue_title, wait):
    """
    使用 Selenium 访问单个对话URL，等待JS加载完毕，并提取对话文本。
    返回: (dialogue_list, narrative_list)
    """
    dialogue_list = []
    narrative_list = []

    try:
        print(f"正在请求对话页面: {dialogue_title}")
        driver.get(url)
        time.sleep(1)

        # 尝试等待主要容器出现（结构 A）
        # 如果是结构 B 页面，这里会超时，我们需要捕获异常并继续解析
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, DIALOGUE_AREA_CLASS)))

            # 点击所有“展开”按钮（仅在结构 A 存在时尝试）
            clicked_buttons = set()
            try:
                expand_buttons = driver.find_elements(By.XPATH,
                    "//div[contains(@class,'obc-tmpl-interactiveDialogue')]"
                    "//*[contains(text(),'展开') or contains(@class,'obc-tmpl__expand-text')]"
                )

                for btn in expand_buttons:
                    btn_id = id(btn)
                    if btn_id in clicked_buttons:
                        continue
                    try:
                        driver.execute_script("arguments[0].click();", btn)
                        clicked_buttons.add(btn_id)
                        time.sleep(0.3)  # 等待 DOM 刷新
                    except Exception:
                        pass
            except Exception:
                print("页面没有可展开按钮或点击失败，继续解析已渲染内容")
        
        except TimeoutException:
            # 如果等待超时，说明页面可能没有 interactiveDialogue 模块（可能是结构 B），不视为错误，继续解析
            print("未检测到交互式对话容器 (Timeout)，尝试直接解析页面结构...")
            time.sleep(1) # 等待，确保结构 B 加载完成

        # 获取渲染后的完整 HTML
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # ----------- 结构 B: obc-tmpl-fold + 剧情对话标题 -----------
        # 优先尝试结构 B
        fold_modules = soup.find_all("div", class_="obc-tmpl-fold")
        for module in fold_modules:
            # 检查标题是否为“剧情对话”
            is_target_module = False
            
            # 1. 尝试查找标准的标题容器
            title_div = module.find("div", class_="obc-tmpl-fold__title")
            if title_div:
                # 标题容器里包含“剧情对话”
                if "剧情对话" in title_div.get_text(strip=True):
                    is_target_module = True
            else:
                # 2. 如果没有标题容器，回退到查找第一个 span
                title_span = module.find("span")
                if title_span and "剧情对话" in title_span.get_text(strip=True):
                    is_target_module = True
            
            if not is_target_module:
                continue

            # 找所有 <p>
            paragraphs = module.find_all("p")
            for p in paragraphs:
                text = p.get_text(strip=True)
                if not text:
                    continue

                if "：" in text:
                    speaker, t = text.split("：", 1)
                    dialogue_list.append({
                        "source_title": dialogue_title,
                        "speaker": speaker.strip(),
                        "text": t.strip()
                    })
                else:
                    narrative_list.append(f"[{dialogue_title}] {text}")

        # ----------- 结构 A: obc-tmpl-interactiveDialogue -----------
        # 如果结构 B 没有提取到内容，则尝试结构 A
        if not dialogue_list and not narrative_list:
            print("结构 B 未提取到内容，尝试使用结构 A")
            interactive_containers = soup.find_all("div", class_=DIALOGUE_AREA_CLASS)
            for container in interactive_containers:
                content_boxes = container.find_all("div", class_=DIALOGUE_NODE_CLASS)
                for box in content_boxes:
                    for p_tag in box.find_all("p"):
                        text = p_tag.get_text(strip=True)
                        if not text:
                            continue
                        if "：" in text:
                            speaker, t = text.split("：", 1)
                            dialogue_list.append({
                                "source_title": dialogue_title,
                                "speaker": speaker.strip(),
                                "text": t.strip()
                            })
                        else:
                            narrative_list.append(f"[{dialogue_title}] {text}")

        print(f"页面 [{dialogue_title}] 成功提取 {len(dialogue_list)} 条对话，{len(narrative_list)} 条旁白。")

    except Exception as e:
        print(f"访问或解析页面失败 (WebDriver/超时错误): {url} - 错误类型: {type(e).__name__}")

    return dialogue_list, narrative_list

# --- 修改 JSON + TXT 导出 ---
def main_extraction():
    """启动 Selenium，读取 URL 列表并开始对话提取"""
    url_error = []
    if not os.path.exists(URL_LIST_FILENAME):
        print(f"未找到 URL 列表文件 {URL_LIST_FILENAME}")
        return

    url_df = pd.read_csv(URL_LIST_FILENAME)
    all_extracted_dialogues = [] 
    all_extracted_narratives = [] 
    
    # --- 启动 Selenium 驱动 ---
    try:
        service = Service(executable_path=CHROME_DRIVER_PATH)
        driver = webdriver.Chrome(service=service)
        wait = WebDriverWait(driver, 10)
        driver.set_page_load_timeout(10)
    except Exception as e:
        print(f"启动 Selenium 失败: {e}")
        return

    print(f"--- 准备开始从 {len(url_df)} 个URL中提取对话 ---")
    
    try:
        for index, row in url_df.iterrows():
            url = row['url']
            title = row['title']
            
            dialogues, narratives = fetch_and_parse_dialogue_selenium(driver, url, title, wait)
            
            if not dialogues and not narratives:
                print(f"页面提取失败，加入 url_error: {url}")
                url_error.append(url)
            else:
                if dialogues:
                    all_extracted_dialogues.extend(dialogues)
                if narratives:
                    all_extracted_narratives.extend(narratives)

            
            delay = random.uniform(0.2, 0.5) 
            print(f"-> 等待 {delay:.2f} 秒后继续爬取下一个 URL...")
            time.sleep(delay)

    except Exception as e:
        print(f"\n主循环中断: {e}")
        
    finally:
        driver.quit()

    # --- 导出文件 ---
    print("-" * 30)
    print(f"爬取完成！共计 {len(all_extracted_dialogues)} 条对话，{len(all_extracted_narratives)} 条旁白。")
    
    try:
        with open(OUTPUT_DIALOGUE_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(all_extracted_dialogues, f, ensure_ascii=False, indent=4)
        print(f"对话数据已成功写入 JSON 文件: {OUTPUT_DIALOGUE_FILENAME}")
    except Exception as e:
        print(f"保存对话数据到JSON失败: {e}")
        
    try:
        with open(OUTPUT_NARRATIVE_FILENAME, 'w', encoding='utf-8') as f:
            f.write('\n'.join(all_extracted_narratives))
        print(f"旁白/特殊文本已成功写入 TXT 文件: {OUTPUT_NARRATIVE_FILENAME}")
    except Exception as e:
        print(f"保存旁白数据到TXT失败: {e}")

    print("\n===== 提取失败的 URL 列表 =====")
    for u in url_error:
        print(u)

    if url_error:
        # 检查文件是否存在且有内容，以便决定是否添加换行符
        has_content = os.path.exists("url_error.txt") and os.path.getsize("url_error.txt") > 0
        
        with open("url_error.txt", "a", encoding="utf-8") as f:
            if has_content:
                f.write("\n")
            f.write("\n".join(url_error))
        print("失败URL已追加写入 url_error.txt")
    else:
        print("本次运行没有失败的 URL。")

TEST_URL = "https://baike.mihoyo.com/ys/obc/content/504413/detail?bbs_presentation_style=no_header"
TEST_TITLE = "为我敞开心扉"

def test_single_page_extraction():
    """专门测试结构 B 页面（obc-tmpl-fold + 剧情对话）"""
    # --- 启动 Selenium ---
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.page_load_strategy = 'normal'  # 保证页面完全加载

    service = Service(executable_path=CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        print(f"正在请求页面: {TEST_TITLE}")
        print(f"URL: {TEST_URL}")
        driver.get(TEST_URL)
        time.sleep(3)  # 增加等待时间，确保加载完成

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        dialogue_list = []
        narrative_list = []

        # 找所有 obc-tmpl-fold
        fold_modules = soup.find_all("div", class_="obc-tmpl-fold")
        print(f"调试: 找到 {len(fold_modules)} 个 obc-tmpl-fold 模块")

        for i, module in enumerate(fold_modules):
            # 检查标题是否为“剧情对话”
            is_target_module = False
            title_text_debug = "N/A"
            
            # 逻辑同上
            title_div = module.find("div", class_="obc-tmpl-fold__title")
            if title_div:
                title_text_debug = title_div.get_text(strip=True)
                if "剧情对话" in title_text_debug:
                    is_target_module = True
            else:
                title_span = module.find("span")
                if title_span:
                    title_text_debug = title_span.get_text(strip=True)
                    if "剧情对话" in title_text_debug:
                        is_target_module = True
            
            print(f"调试: 模块 {i+1} 标题: '{title_text_debug}' -> 是否目标: {is_target_module}")

            if not is_target_module:
                continue

            paragraphs = module.find_all("p")
            print(f"调试: 目标模块中找到 {len(paragraphs)} 个 <p> 标签")

            for p in paragraphs:
                text = p.get_text(strip=True)
                if not text:
                    continue

                if "：" in text:
                    speaker, t = text.split("：", 1)
                    dialogue_list.append({
                        "source_title": TEST_TITLE,
                        "speaker": speaker.strip(),
                        "text": t.strip()
                    })
                else:
                    narrative_list.append(f"[{TEST_TITLE}] {text}")

        print(f"\n提取完成: {len(dialogue_list)} 条对话，{len(narrative_list)} 条旁白")
        if dialogue_list:
            print("第一条对话:", dialogue_list[0])
        if narrative_list:
            print("第一条旁白:", narrative_list[0])

    finally:
        driver.quit()

if __name__ == "__main__":
    test_single_page_extraction()
    # main_extraction()