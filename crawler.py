import sys
from datetime import datetime
import eventlet
import settings
import models
import helpers
from helpers import log
import extractors
import pdb

crawl_time = datetime.now()

pool = eventlet.GreenPool(settings.max_threads) # create a pool of green threads
# GreenPile objects represent chunks of work. In essence a GreenPile is an iterator
# that can be stuffed with work, and the results read out later
pile = eventlet.GreenPile(pool)


def begin_crawl():
    '''
    Initialize everything (except the Postsql database)
    The Postsql database tables are setup by directly executing models.py
    This is essentially step 0
    '''
    # explode out all of our category `start_urls` into subcategories
    with open(settings.start_file, "r") as f:
        # read each url in the start-urls.txt file
        for line in f:
            # Count the number of subcategories found from Starting URL
            subcategory_count = 0

            # remove all leading and trailing whitespace and commented out URLs
            url = line.strip()
            if not url or line.startswith("#"):
                continue

            # Make a request.  This properly parses the url and makes a green request
            # page - <BeautifulSoup> constructed from html
            # html - string of html text from the request
            page, html = helpers.make_request(url)

            # look for subcategory links on this page
            subcategories = page.findAll("div", "bxc-grid__image")  # downward arrow graphics
            subcategories.extend(page.findAll("li", "sub-categories__list__item"))  # carousel hover menu
            sidebar = page.find("div", "browseBox")
            if sidebar:
                subcategories.extend(sidebar.findAll("li"))  # left sidebar

            for subcategory in subcategories:
                link = subcategory.find("a")
                if not link:
                    continue
                link = link["href"]
                subcategory_count += 1
                # Add the subcategory link to Redis
                helpers.enqueue_url(link)
            log("Found {} subcategories on {}".format(subcategory_count, line))


def fetch_listing():
    '''
    This is the root function that green threads call.
    This is essentially step 1 (but step 0 is above!)
    '''
    global crawl_time

    # Pop a random URL from the Redis listing_url_queue
    url = helpers.dequeue_url()
    if not url:
        log("WARNING: No URLs found in the queue. Retrying...")
        pile.spawn(fetch_listing)
        return

    page, html = helpers.make_request(url)
    if not page:
        return
    items = page.findAll("li", "s-result-item")
    log("Found {} items on {}".format(len(items), url))

    for item in items[:settings.max_details_per_listing]:
        product_image = extractors.get_primary_img(item)
        if not product_image:
            log("No product image detected, skipping")
            continue

        product_title = extractors.get_title(item)
        product_url = extractors.get_url(item)
        product_price = extractors.get_price(item)

        product = models.ProductRecord(
            title=product_title,
            product_url=helpers.format_url(product_url),
            listing_url=helpers.format_url(url),
            price=product_price,
            primary_img=product_image,
            crawl_time=crawl_time
        )
        product_id = product.save()
        helpers.download_image(product_image, product_id)

    # add next page to queue
    next_link = page.find("a", id="pagnNextLink")
    if next_link:
        log(" Found 'Next' link on {}: {}".format(url, next_link["href"]))
        helpers.enqueue_url(next_link["href"])
        pile.spawn(fetch_listing)


if __name__ == '__main__':

    if len(sys.argv) > 1 and sys.argv[1] == "start":
        log("Seeding the URL frontier with subcategory URLs")
        begin_crawl()  # put a bunch of subcategory URLs into the queue

    # global time at start
    log("Beginning crawl at {}".format(crawl_time))
    # fetch_listing() is defined above in this file
    # launch a greenthread to call fetch_list()
    # Greenthreads do work in parallel
    # When executed, control is immediately returned to caller
    # Greenthreads run whenever they can
    [pile.spawn(fetch_listing) for _ in range(settings.max_threads)]

    # wait until all greenthreads in the pool are finished working
    pool.waitall()
