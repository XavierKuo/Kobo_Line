## For Line Bot 的套件
from flask import Flask, request, abort

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

## For Kobo 爬蟲的套件
from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time, textwrap

import os

## 以下程式碼開始 ##

# Line Bot 串接
app = Flask(__name__)

configuration = Configuration(access_token=os.getenv('CHANNEL_ACCESS_TOKEN'))
line_handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

# 定義爬蟲函數
def get_today_99(url: str = None, template: str = None) -> str:
    """
    Get the book details of 今日 99 from Kobo Taiwan
    """
    # Set up Selenium WebDriver (ensure you have ChromeDriver installed)
    driver = webdriver.Chrome()  

    # Open the target URL
    if not url:
        url = "https://www.kobo.com/tw/zh"
    driver.get(url)

    # Wait for JavaScript to load (adjust time as needed)
    time.sleep(3)  

    # Get page source after JavaScript has loaded
    html = driver.page_source  

    # Parse with BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # Find the element (Example: First book title)
    today_99 = soup.find("header", class_="spotlight-header").text
    link_tag = soup.find("a", class_="item-link-underlay")
    if link_tag:
        driver.get(link_tag["href"])
        time.sleep(1.5)  
        html = driver.page_source
        book_soup = BeautifulSoup(html, "html.parser")

        # Try to get the book title, author, description, rating, and number of ratings
        try: 
            title = book_soup.find("h1", class_="title").text
        except:
            title = "No title"
        
        try:
            author = book_soup.find("a", class_="contributor-name").text
        except:
            author = "No author"
        
        try:
            description = book_soup.find("div", class_="synopsis-description").text
        except:
            description = "No description"
        
        try:
            rating = book_soup.find("div", class_="rating-average").text
            rating = float(rating)
            n_stars, _ = divmod(rating, 1) 
            stars = "★" * int(n_stars) + "☆" * (5 - int(n_stars))
        except:
            rating = "No rating"
            stars = "No rating"
        
        try:
            n_rate = book_soup.find("span", class_="total-ratings").text
        except:
            n_rate = "No rate"

    if not template:  
        template = textwrap.dedent("""\
        {today}
                                   
        書名：{title}
                                   
        作者: {author}
                                   
        評分: {stars} ({n_rate})
                                   
        簡介: {desc}

        {link}""")
        

    # fill in the template
    output_str = template.format(today=today_99.strip(), 
                                 title=title.strip(), 
                                 author=author.strip(), 
                                 stars=stars.strip(), 
                                 n_rate=n_rate.strip(), 
                                 desc=description.strip(), 
                                 link=link_tag["href"].strip()
                                 )

    # Close the browser
    driver.quit()

    return output_str


# Line Bot 接收與回覆機制
@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

# 訊息事件
@line_handler.add(MessageEvent, message=TextMessageContent)
def message_text(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        # 檢查訊息內容是否為觸發關鍵字
        if event.message.text.lower() in ['99', 'deals']:
            try:
                # 執行爬蟲獲取今日特價書籍資訊
                book_info = get_today_99()
                # 回傳爬蟲結果
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=book_info)]
                    )
                )
            except Exception as e:
                # 如果爬蟲過程出現錯誤，回傳錯誤訊息
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="抱歉，獲取特價書籍資訊時發生錯誤，請稍後再試。")]
                    )
                )

        # 說明
        elif event.message.text.lower() in ['help', '說明']:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="輸入「99」或「deals」可以查詢 Kobo 今日特價書籍")]
                )
            )

        else:
            # 如果不是觸發關鍵字，維持原本的回覆邏輯
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    # messages=[TextMessage(text ='reply message')]
                    messages = [TextMessage(text='WTF')]
                )
            )
            
if __name__ == "__main__":
    app.run()
