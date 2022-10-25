import requests
from bs4 import BeautifulSoup
import sqlite3
import slack
import os
from pathlib import Path
from dotenv import load_dotenv


###################################
# initializes database connection

con = sqlite3.connect("flat.db")
cur = con.cursor()

cur.execute('''CREATE TABLE IF NOT EXISTS flats
                (id integer PRIMARY KEY, title text, price text, description text, url text)''')

########################################
# initializing slack client
env_path = Path('.') / 'dot.env'
load_dotenv(dotenv_path=env_path)
client = slack.WebClient(token=os.environ['SLACK_TOKEN'])

url = 'https://www.zoopla.co.uk/to-rent/property/edinburgh-city-centre/?q=Edinburgh%20City%20Centre%2C%20Edinburgh&beds_min=2&price_frequency=per_month&price_max=1500&radius=3&search_source=refine&view_type=list#listing_62712730'

result = requests.get(url)
soup = BeautifulSoup(result.text, 'html.parser')

listings = soup.select('div[data-testid="search-result"]')

ExportPayload = []

for list in listings:
    ListingMonth = list.select_one('span[data-testid="available-from-date"]')
    if ListingMonth == None:
        print('Error encountered: "None" was found')
        continue
    ListingMonth = ListingMonth.text.split(" ")
    ExtractedMonth = ListingMonth[len(ListingMonth)-2]

    DesiredMonths = ['Dec', 'Jan']

    if any(c in ExtractedMonth for c in DesiredMonths):
        ListingTitle = list.select_one('h2[data-testid="listing-title"]').text

        ListingPrice = list.select_one(
            'div[data-testid="listing-price"]').findChild("p", recursive=False).text

        ListingLink = list.select_one(
            'a[data-testid="listing-details-image-link"]').attrs['href']
        ListingID = ListingLink.split("/")
        ListingID = ListingID[len(ListingID)-2]
        ListingLink = "https://www.zoopla.co.uk/to-rent/details/" + ListingID

        ListingDescription = list.select_one(
            'p[data-testid="listing-description"]').text

        ExportPayload.append(
            (ListingID, ListingTitle, ListingPrice, ListingDescription, ListingLink))
# checks if listing exists in databse
for PayloadIterator in ExportPayload:
    print(PayloadIterator[0] + "is being processed")
    cur.execute("""SELECT id 
                FROM flats
                WHERE id=?""",
                (PayloadIterator[0],))
    result = cur.fetchone()
    if result:
        print(PayloadIterator[0] + " found")
    else:
        cur.execute('''INSERT OR IGNORE INTO flats VALUES
                   (?, ?, ?, ?, ?)''', PayloadIterator)
        print(
            PayloadIterator[0] + " non existent, adding to database and sending notification")
        con.commit()
        ###################################################################################
     # contacting user via slack api
        penis = 'https://google.com'

        FinalPayload = [

            {
                "type": "header",
                "text": {
                        "type": "plain_text",
                        "text": "New Property Found\n{}".format(PayloadIterator[0])
                }
            },
            {
                "type": "section",
                "fields": [
                        {
                            "type": "mrkdwn",
                            "text": "*Name:*\n{}".format(PayloadIterator[1])
                        },
                    {
                            "type": "mrkdwn",
                            "text": "*Find it here:*\n<{}|Click ME>".format(PayloadIterator[4])
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                        {
                            "type": "mrkdwn",
                            "text": "*Price:*\n{}".format(PayloadIterator[2])
                        },
                    {
                            "type": "mrkdwn",
                            "text": "{}".format(PayloadIterator[3])
                    }
                ]
            }

        ]
        FinalPayload = str(FinalPayload)

        client.chat_postMessage(channel="#flathunt", blocks=FinalPayload)
