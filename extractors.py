from HTMLParser import HTMLParser
import numpy as np
import pdb

##############################################################
# Functions to extract useful information from BeautifulSoup #
##############################################################

htmlparser = HTMLParser()

def get_title(item):
    title = item.find("h2", "s-access-title")
    if title:
        return htmlparser.unescape(title.text.encode("utf-8"))
    else:
        return "<missing product title>"


def get_url(item):
    link = item.find("a", "s-access-detail-page")
    if link:
        return link["href"]
    else:
        return "<missing product url>"


def get_price(item):
    # conventional check
    price = item.find("span", "s-price")
    if price:
        return price.text

    # Multi-option check
    price = item.find("span","a-color-base").text
    try:
        #remove $ signs
        price = price.replace('$','')
        #break up into low and high price strings
        prices = price.split('-')
        try:
            prices = [int(x)/100.00 for x in prices]
        except:
            prices = [float(x) for x in prices]
        #return average
        return str(np.mean(prices))
    except:
        pass

    return '<missing price>'


def get_primary_img(item):
    thumb = item.find("img", "s-access-image")
    if thumb:
        src = thumb["src"]

        p1 = src.split("/")
        p2 = p1[-1].split(".")

        base = p2[0]
        ext = p2[-1]

        return "/".join(p1[:-1]) + "/" + base + "." + ext

    return None

