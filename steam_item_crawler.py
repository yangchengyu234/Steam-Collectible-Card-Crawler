import datetime
import dotenv
import json
import logging
import math
import random
import os
import requests
from urllib.parse import quote
from timer import Timer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SteamItemCrawler:
    def __init__(self, steam_api_key, batch_size, env_file_name):
        self.steam_api_key = steam_api_key
        self.batch_size = batch_size
        self.env_file_name = env_file_name
        self.base_url = "https://steamcommunity.com/market/search/render/"
        self.market_base_url = "https://steamcommunity.com/market/listings/"

    def make_steam_request(self, query, max_results):
        params = {
            'query': '',
            'start': 0,
            'count': max_results,
            'search_descriptions': 0,
            'sort_column': 'price',
            'sort_dir': 'asc',
            'appid': 753,
            'currency': 1,
            'norender': 1
        }
        query_parts = query.lstrip('?').split('&')
        for part in query_parts:
            if '=' in part:
                key, value = part.split('=', 1)
                if key == 'category_753_item_class%5B%5D':
                    params['category_753_item_class[]'] = value
                elif key == 'category_753_cardborder%5B%5D':
                    params['category_753_cardborder[]'] = value
                elif key == 'start':
                    params['start'] = int(value)
        
        try:
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"请求Steam API失败：{str(e)}")
            return None

    def enrich_item_list(self, query_item, last_processed_page, control_env_variable_processed_page, type, subtype, file_path):
        total_data = self.make_steam_request(query_item, max_results=1)
        if not total_data or 'total_count' not in total_data:
            logging.error("获取总物品数失败，退出爬取")
            return
        total_items = total_data['total_count']
        total_pages = math.ceil(total_items / self.batch_size)
        logging.info(f"=== 开始爬取：共{total_items}个物品，分{total_pages}页 ===")
        
        page_to_process = last_processed_page + 1
        for i in range(page_to_process * self.batch_size, total_items + self.batch_size, self.batch_size):
            try:
                Timer.pause(random.uniform(10, 30))
            except KeyboardInterrupt:
                logging.info("程序被用户中断，保存当前数据后退出")
                self.save_to_json([], file_path)
                return
                
            current_page = math.ceil(i / self.batch_size)
            dotenv.set_key(self.env_file_name, control_env_variable_processed_page, str(current_page))
            
            batch_start = i
            batch_end = min(i + self.batch_size, total_items)
            logging.info(f"正在爬取第{current_page}/{total_pages}页：物品{batch_start}-{batch_end}")
            
            page_query = f"{query_item}&start={batch_start}"
            page_data = self.make_steam_request(page_query, max_results=self.batch_size)
            if not page_data or 'results' not in page_data:
                logging.error(f"爬取第{current_page}页失败，跳过该页")
                continue
            result_list = page_data['results']
            
            current_page_items = []
            for item in result_list:
                # 提取Steam官方生成的“市场哈希名”（含游戏ID和物品名，已正确编码）
                market_hash_name = item.get('hash_name', '')
                if not market_hash_name:
                    market_hash_name = item.get('name', '').replace(' ', '_')  # 兜底：用物品名生成
                
                # 拼接GitHub示例格式的链接：/753/市场哈希名
                item_market_url = f"{self.market_base_url}753/{quote(market_hash_name)}"
                
                current_page_items.append({
                    'item_market_url': item_market_url,
                    'name': item.get('name', '未知名称'),
                    'type': type,
                    'subtype': subtype,
                    'game_name': item['asset_description'].get('game', '未知游戏'),
                    'game_type': item['asset_description'].get('type', '未知类型'),
                    'fetch_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            
            self.save_to_json(current_page_items, file_path)
        logging.info(f"=== 全部爬取完成，数据保存在{file_path} ===")

    def enrich_data(self, query_item, last_processed_page, control_env_variable_processed_page, type, subtype):
        self.enrich_item_list(query_item, last_processed_page, control_env_variable_processed_page, type, subtype, "steam_all_games_trading_cards.json")

    def save_to_json(self, data, file_path):
        existing_data = []
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                logging.info(f"已读取{file_path}中{len(existing_data)}条历史数据")
            except json.JSONDecodeError:
                logging.warning(f"{file_path}格式错误，将覆盖写入")
        
        combined_data = existing_data + [item for item in data if item not in existing_data]
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(combined_data, f, ensure_ascii=False, indent=2)
            new_count = len(data) if data else 0
            logging.info(f"✅ 数据已保存：新增{new_count}条，总计{len(combined_data)}条\n")
        except Exception as e:
            logging.error(f"保存JSON失败：{e}")

if __name__ == "__main__":
    dotenv.load_dotenv()
    steam_api_key = os.getenv("STEAM_API_KEY")
    if not steam_api_key:
        logging.warning("⚠️ 未找到Steam API Key，爬取公开市场数据无需密钥，继续执行")
    
    QUERY_ITEM = "?category_753_item_class[]=tag_item_class_2&category_753_cardborder[]=tag_cardborder_0&category_753_cardborder[]=tag_cardborder_1&category_753_type%5B%5D=tag_type_0"
    BATCH_SIZE = 50
    ENV_FILE = ".env"
    LAST_PROCESSED_PAGE = int(os.getenv("ALL_GAMES_CARD_PAGE", 0))
    CONTROL_VAR = "ALL_GAMES_CARD_PAGE"
    ITEM_TYPE = "trading_card"
    ITEM_SUBTYPE = "steam_all_games"
    
    crawler = SteamItemCrawler(steam_api_key, BATCH_SIZE, ENV_FILE)
    logging.info("=== Steam全游戏集换卡爬虫启动（生成GitHub格式链接）===\n")
    crawler.enrich_data(QUERY_ITEM, LAST_PROCESSED_PAGE, CONTROL_VAR, ITEM_TYPE, ITEM_SUBTYPE)
    logging.info("=== 爬虫运行结束 ===")
