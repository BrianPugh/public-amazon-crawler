import os
import random
from datetime import datetime
from urlparse import urlparse
import redis
from BeautifulSoup import BeautifulSoup
from requests.exceptions import RequestException
import settings
import urllib
import pdb

import eventlet
# import_patched imports a module in a greened manner
# The module's use of networking libraries will use Eventlet's
# green versions instead.
requests = eventlet.import_patched('requests.__init__')
time = eventlet.import_patched('time')


# cumulative counter of number of requests made
num_requests = 0

# Connect to Redis Server
redis = redis.StrictRedis(host=settings.redis_host, port=settings.redis_port, db=settings.redis_db)

def download_image(url, name):
    '''
    Download image from URL
    '''
    _, img_ext = os.path.splitext(url)
    save_name = os.path.join(settings.image_dir, str(name)+img_ext)
    urllib.urlretrieve(url, save_name)

def make_request(url, return_soup=True):
    '''
    Used during initial setup

    Returns:
        page - <BeautifulSoup Obj>
        html - <String>
    '''
    # Properly reformat the URL for request
    url = format_url(url)

    # Skip redirect URLs
    if "picassoRedirect" in url:
        return None

    # Global counter of number of requests made so far
    global num_requests
    if num_requests >= settings.max_requests:
        raise Exception("Reached the max number of requests: {}".format(settings.max_requests))

    #dictionary of parsed http and https proxy socks5
    proxies = get_proxy()

    # (try) to make a request
    try:
        # Get a response object.  This contains all the information we need!
        # Attributes:
        # text - Guesses encoding and has the stored text
        # encoding - encoding used (automatically smartly guesses)
        # content - access response body as bytes
        # json - json decoding (if dealing with json data)
        # raw - raw socket response.  Make sure stream=true during get() call
        # status_code - response status_code.  200 is a good response.
        r = requests.get(url, headers=settings.headers, proxies=proxies)
    except RequestException:
        log("WARNING: Request for {} failed, trying again.".format(url))
        # try request again, recursively
        return make_request(url)

    # Recording that a successful request has been made to the global counter
    num_requests += 1

    if r.status_code != 200:
        os.system('say "Got non-200 Response"')
        log("WARNING: Got a {} status code for URL: {}".format(r.status_code, url))
        return None

    if return_soup:
        return BeautifulSoup(r.text), r.text
    else:
        return r


def format_url(url):
    '''
    Prepares a url.
    Make sure amazon URLs aren't relative, and strip unnecessary
    query args (to reduce the chance of them tracking the crawler!)
    '''
    # Parse URL into general structure components of a URL
    # The important parts are taken in subsequent lines
    u = urlparse(url)
    scheme = u.scheme or "https"
    host = u.netloc or "www.amazon.com"
    path = u.path

    # Remove non-approved query arguments from URL
    if not u.query:
        query = ""
    else:
        query = "?"
        for piece in u.query.split("&"):
            try:
                k, v = piece.split("=", 1)
                if k in settings.allowed_params:
                    query += "{k}={v}&".format(**locals())
            except:
                pass
        query = query[:-1]
    # replace things in {} with the strings in variables of the same name
    return "{scheme}://{host}{path}{query}".format(**locals())


def log(msg):
    '''
    Global logging function
    '''
    if settings.log_stdout:
        try:
            print "{}: {}".format(datetime.now(), msg)
        except UnicodeEncodeError:
            pass  # squash logging errors in case of non-ascii text


def get_proxy():
    '''
    Choose a proxy server to use for this request.
    settings.proxies must be populated or no proxy will be used.

    Returns:
        Proxy dictionary of keys {http, https}
    '''
    if not settings.proxies or len(settings.proxies) == 0:
        return None

    proxy_ip = random.choice(settings.proxies)
    # Parse the Proxy URL
    proxy_url = "socks5://{user}:{passwd}@{ip}:{port}/".format(
        user=settings.proxy_user,
        passwd=settings.proxy_pass,
        ip=proxy_ip,
        port=settings.proxy_port,
    )
    return {
        "http": proxy_url,
        "https": proxy_url
    }


def enqueue_url(u):
    '''
    Add the url to the Redis listing_url_queue
    '''
    url = format_url(u)
    return redis.sadd("listing_url_queue", url)


def dequeue_url():
    '''
    Removes and returns (pops) one *random* url from the listing_url_queue
    '''
    return redis.spop("listing_url_queue")


if __name__ == '__main__':
    # test proxy server IP masking
    r = make_request('https://api.ipify.org?format=json', return_soup=False)
    print r.text
    pdb.set_trace()
