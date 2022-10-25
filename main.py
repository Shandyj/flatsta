from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import sqlite3
import slack
import os
from pathlib import Path
from dotenv import load_dotenv

ExportPayload = []
###################################
# initializes database connection

con = sqlite3.connect("flat.db")
cur = con.cursor()

cur.execute('''CREATE TABLE IF NOT EXISTS flats
                (id integer PRIMARY KEY, title text, price text, description text, url text)''')

########################################
# initializing slack client
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)
client = slack.WebClient(token=os.environ['SLACK_TOKEN'])


with sync_playwright() as p:
    url = 'https://www.zoopla.co.uk/to-rent/property/edinburgh-city-centre/?q=Edinburgh%20City%20Centre%2C%20Edinburgh&beds_min=2&price_frequency=per_month&price_max=1500&radius=3&search_source=refine&view_type=list#listing_62712730'
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(url)

    htmls = page.inner_html('div[data-testid=regular-listings]')

    # debug to read value of output html
    # with open('sample.txt', 'w') as f:
    #    f.write('dict = ' + str(htmls) + '\n')
    soup = BeautifulSoup(htmls, "html.parser")

    # uses first layer of divs as separators for all the listings
    # if blanket div doesnt work   select via div where data-testid="search-result"
    first = soup.div
    # print(first)
    # print("-----------------------------------------------------------")

    #listings = first.find_next_siblings("div")
    listings = soup.select('div[data-testid="search-result"]')

    for list in listings:
        # info about Available date/month
        # span where data-testid="available-from-date"      /text()
        # to select month eg Dec, slit by space and select [-2]
        # *********always use single finder/selector when wating to extract text***********
        ListingMonth = list.select_one(
            'span[data-testid="available-from-date"]').text.split(" ")
        ExtractedMonth = ListingMonth[len(ListingMonth)-2]
        # print(ExtractedMonth)
        # print("***********************************")

        DesiredMonths = ['Dec', 'Jan']

        # if month matches desired month, follow along
        # if any(c in DesiredMonths for c in ExtractedMonth):

        if any(c in ExtractedMonth for c in DesiredMonths):
            # get info about title
            # h2 where data-testid="listing-title"           /text()
            ListingTitle = list.select_one(
                'h2[data-testid="listing-title"]').text

            # get info about price
            # div where data-testid="listing-price"   and first <p element
            # laternative       ListingPrice = list.select_one('p[class="css-1w7anck eq9400e31"]')
            ListingPrice = list.select_one(
                'div[data-testid="listing-price"]').findChild("p", recursive=False).text

            # get info about id and link
            # a where data-testid="listing-details-image-link"  /href()
            ListingLink = list.select_one(
                'a[data-testid="listing-details-image-link"]').attrs['href']
            ListingID = ListingLink.split("/")
            ListingID = ListingID[len(ListingID)-2]
            # prettifying adding zoopla prefix
            ListingLink = "https://www.zoopla.co.uk/to-rent/details/" + ListingID
            print(ListingLink)

            # get infro about location(description)
            # p where data-testid="listing-description"      /text()
            ListingDescription = list.select_one(
                'p[data-testid="listing-description"]').text

            # add all information into array
            ExportPayload.append(
                (ListingID, ListingTitle, ListingPrice, ListingDescription, ListingLink))
    # print(ExportPayload)
    # print(len(ExportPayload))

    # checks if listing exists in databse
    for PayloadIterator in ExportPayload:
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
