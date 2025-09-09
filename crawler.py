import logging
import os
from typing import NamedTuple

import dotenv
from steam_item_crawler import SteamItemCrawler

# 加载环境变量（优先读取本地.env配置）
dotenv.load_dotenv()

# 配置日志：显示时间、日志级别和内容，方便排查爬取问题
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # 默认INFO级别，未配置时不报错
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CardCrawlConfig(NamedTuple):
    """Steam集换卡爬取配置：明确存储核心参数，避免混乱"""
    breakpoint_env_var: str  # 断点页码的环境变量名（用于续爬）
    steam_query: str         # Steam市场的集换卡专属查询参数
    output_json: str         # 爬取结果的输出JSON文件名


def get_card_crawl_config() -> CardCrawlConfig:
    """生成Steam集换卡的固定爬取配置（仅聚焦集换卡，无需多类型判断）"""
    return CardCrawlConfig(
        # 断点变量：记录上次爬取到的页码，中断后重启自动续爬
        breakpoint_env_var="LAST_CRAWLED_CARD_PAGE",
        # Steam集换卡查询参数：appid=753是Steam集换卡市场固定ID，筛选普通+闪亮集换卡
        steam_query=(
            "?appid=753&category_753_item_class[]=tag_item_class_2&"
            "category_753_cardborder[]=tag_cardborder_0&"  # 普通集换卡
            "category_753_cardborder[]=tag_cardborder_1"   # 闪亮集换卡
        ),
        # 输出文件：单独存储集换卡数据，避免与其他类型混淆
        output_json="steam_trading_cards.json"
    )


def crawl_steam_trading_cards(config: CardCrawlConfig) -> None:
    """核心功能：执行Steam集换卡爬取任务"""
    logger.info(f"开始爬取Steam集换卡，结果将保存至 {config.output_json}")

    # 读取断点页码：首次爬取默认从第0页开始，续爬从上次中断页码继续
    last_crawled_page = int(os.getenv(config.breakpoint_env_var, "0"))

    try:
        # 初始化集换卡爬虫：参数从环境变量读取，灵活配置
        crawler = SteamItemCrawler(
            steam_api_key=os.getenv("STEAM_API_KEY", ""),  # APIKey可选，空值不影响基础爬取
            batch_size=int(os.getenv("CARD_BATCH_SIZE", "50")),  # 每次爬取50条（默认值可调整）
            env_file=".env"  # 用于更新断点页码的环境文件路径
        )

        # 执行爬取：传递所有必要配置，触发数据采集+续爬+保存
        crawler.enrich_data(
            query_item=config.steam_query,
            last_processed_page=last_crawled_page,
            control_env_variable_processed_page=config.breakpoint_env_var,
            item_type="trading_card",  # 明确标注物品类型为“集换卡”
            output_file=config.output_json
        )

        logger.info(f"Steam集换卡爬取任务完成！数据已保存到 {config.output_json}")

    # 捕获爬取中可能出现的异常（如网络错误、Steam接口异常），避免程序崩溃
    except Exception as e:
        logger.error(f"爬取Steam集换卡时出错：{str(e)}", exc_info=True)


# 程序入口：直接启动集换卡爬取
if __name__ == "__main__":
    crawl_config = get_card_crawl_config()
    crawl_steam_trading_cards(crawl_config)
