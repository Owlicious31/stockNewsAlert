import os
import requests
from datetime import date,timedelta
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

STOCK = "TSLA"
COMPANY_NAME = "Tesla Inc"

STOCK_API_KEY = os.getenv("STOCK_API_KEY")
STOCK_API_ENDPOINT = "https://www.alphavantage.co/query"
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_ENDPOINT = "https://newsapi.org/v2/everything"
ACC_SID = os.getenv("TWILIO_ACC_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
PHONE_NUM = os.getenv("TWILIO_PHONE_NUMBER")
RECIPIENT = os.getenv("RECIPIENT_NUMBER")

YESTERDAY:str = str(date.today() - timedelta(days=1)) #The previous day from the current time
OTHER_DAY:str = str(date.today() - timedelta(days=2)) #The day before yesterday from the current time
NUM_ARTICLES:int = 3

def calculate_percent_change(latest:int,previous:int)->float:
    try:
        return round(((latest-previous)/previous) * 100,ndigits=2)
    except ZeroDivisionError:
        raise ZeroDivisionError("Initial value can't be zero.")


def get_stocks(data:dict)->tuple:
    for timestamp in data:
        if timestamp == YESTERDAY:
            yesterday_closing: int = round(float(data[timestamp]["4. close"]))
        if timestamp == OTHER_DAY:
            other_day_closing: int = round(float(data[timestamp]["4. close"]))

    try:
        other_day_closing
    except NameError:
        other_day_closing:int = int(round(float(list(data.values())[1]["4. close"])))

    try:
        yesterday_closing
    except NameError:
        yesterday_closing:int = int(round(float(list(data.values())[0]["4. close"])))

    #Incase yesterday's and the other day's dates aren't in the data their closing values are set as those of the 2 most
    #recent in the data.

    return yesterday_closing,other_day_closing


def get_news()->tuple[list,list]:
    news_api_params:dict = {
        "apikey":NEWS_API_KEY,
        "q":COMPANY_NAME,
        "searchIn":"title,description",
        "from":YESTERDAY,
        "to":OTHER_DAY,
        "sortBy":"popularity",
        "language":"en",
    }

    news_response = requests.get(url=NEWS_API_ENDPOINT,params=news_api_params)
    news_response.raise_for_status()
    news_data = news_response.json()
    news_data = news_data["articles"]

    headlines = [article["title"] for i,article in enumerate(news_data) if i < NUM_ARTICLES]
    descriptions = [article["description"] for i,article in enumerate(news_data) if i < NUM_ARTICLES]

    for description in descriptions:
        try:
            description.replace(description,description[:description.index("…")])
        except ValueError:
            description.replace(description, description[:description.index("...")])

    return headlines,descriptions


def send_mail(is_drop: bool = False, no_change: bool = False)->None:
    info = get_news()
    headlines = info[0]
    descriptions = info[1]
    client = Client(ACC_SID, AUTH_TOKEN)

    for headline, description in zip(headlines, descriptions):
        if is_drop:
            message = client.messages.create(
                body=f"{STOCK}:🔻{percent_change}%.\nHeadline:{headline}.\nBrief:{description}.",
                to=RECIPIENT,
                from_=PHONE_NUM,
            )
        elif not is_drop and not no_change:
            message = client.messages.create(
                body=f"{STOCK}:🔺{percent_change}%.\nHeadline:{headline}.\nBrief:{description}.",
                to=RECIPIENT,
                from_=PHONE_NUM,
            )
        else:
            message = client.messages.create(
                body=f"{STOCK}:No change in stock.\nHeadline:{headline}.\nBrief:{description}.",
                to=RECIPIENT,
                from_=PHONE_NUM,
            )

        if message.status != "queued":
            raise Exception(f"Error while sending message.Message status:{message.status}")
        else:
            print("Message queued.")

stock_api_params = {
    "function":"TIME_SERIES_DAILY",
    "symbol":STOCK,
    "outputsize":"compact",
    "apikey":STOCK_API_KEY,
}

response = requests.get(url=STOCK_API_ENDPOINT,params=stock_api_params)
response.raise_for_status()
stock_data = response.json()
stock_data = stock_data["Time Series (Daily)"]

yesterday_stocks = get_stocks(stock_data)[0]
other_day_stocks = get_stocks(stock_data)[1]

percent_change:float = calculate_percent_change(latest=yesterday_stocks,previous=other_day_stocks)

if percent_change > 0:
    send_mail(is_drop=False)

elif percent_change < 0:
    percent_change = abs(percent_change)
    send_mail(is_drop=True)

else:
    send_mail(no_change=True)

