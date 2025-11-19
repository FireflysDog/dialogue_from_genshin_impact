from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import time
import csv
import requests.compat
import os

# --- 配置信息 ---
TARGET_URL = "https://baike.mihoyo.com/ys/obc/channel/map/189/43?bbs_presentation_style=no_header&visit_device=pc"
OUTPUT_FILENAME = "urls/dialogue_urls_timed.csv"
CHROME_DRIVER_PATH = r"D:\driverchrome\chromedriver.exe"
# --- 选择器定义 ---
# 1. 点击“任务类型”筛选框（使用绝对XPath）
CLICK_TASK_TYPE_XPATH = '/html/body/div[1]/div/div/div[2]/div[2]/div/div[1]/div[2]/ul/li/div/div[1]/div[2]/div/div[1]/div'

# 2. 点击目标任务
DEMON_TASK_OPTION_XPATH = '//li[@class="el-select-dropdown__item"]//span[text()="限时任务"]' 

# 3. 包含所有链接列表的父容器 Class Name (用于等待内容加载)
URL_CONTAINER_CLASS = "position-list__list" 

# 4. 目标链接元素的选择器
LINK_SELECTOR = 'li a' 


# --- 核心爬取函数 ---

def scrape_dialogue_urls():
    """执行点击、等待、并提取所有对话URL"""
    
    service = Service(executable_path=CHROME_DRIVER_PATH)
    
    try:
        driver = webdriver.Chrome(service=service) 
    except Exception as e:
        print(f"启动 Chrome 失败：{e}")
        return []

    print("启动浏览器，打开目标页面")
    driver.get(TARGET_URL) 
    print("页面加载中")
    wait = WebDriverWait(driver, 20)
    dialogue_urls = []

    try:
        # --- 点击“任务类型”打开下拉菜单 ---
        print("正在定位并点击任务类型筛选框")
        task_type_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, CLICK_TASK_TYPE_XPATH))
        )
        driver.execute_script("arguments[0].click();", task_type_button) 
        
        # --- 点击任务选项 --
        print("正在定位并点击下拉菜单中的目标选项...")
        demon_task_option = wait.until(
            EC.element_to_be_clickable((By.XPATH, DEMON_TASK_OPTION_XPATH))
        )
        driver.execute_script("arguments[0].click();", demon_task_option)
        time.sleep(1)
        # --- 等待新的 URL 列表加载 ---
        print(f"等待URL列表加载 (Class: {URL_CONTAINER_CLASS})...")
        list_container = wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, URL_CONTAINER_CLASS))
        )
        if not list_container:
            print("未找到包含链接的列表容器")
            return []
        else:
            print("准备提取链接")
        # 提取所有链接
        print("开始遍历列表提取URL")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f'.{URL_CONTAINER_CLASS} {LINK_SELECTOR}')))
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, f'.{URL_CONTAINER_CLASS} li.position-list__item')
            )
        )
        
        # 重新获取链接元素
        link_elements = list_container.find_elements(By.CSS_SELECTOR, LINK_SELECTOR)
        
        for link_element in link_elements:
            href = link_element.get_attribute('href')
            title = link_element.get_attribute('title')
            
            if href:
                full_url = requests.compat.urljoin(TARGET_URL, href)
                dialogue_urls.append({'title': title, 'url': full_url})
        
        print(f"成功提取 {len(dialogue_urls)} 个对话链接。")

    except Exception as e:
        print(f"爬取过程中发生错误: {e}")
        
    finally:
        driver.quit() 
        
    return dialogue_urls

# --- 数据保存函数 ---

def save_urls_to_csv(data_list, filename):
    if not data_list:
        return
        
    fieldnames = ['title', 'url'] 
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader() 
            writer.writerows(data_list)
        print(f"-> 已成功将所有链接写入 {filename}")
    except Exception as e:
        print(f"保存数据到CSV失败: {e}")


# --- 主运行逻辑 ---
if __name__ == "__main__":
    print("=== 开始爬取对话 URL ===")
    url_list = scrape_dialogue_urls()
    
    if url_list:
        save_urls_to_csv(url_list, OUTPUT_FILENAME)
        
    print("成功")