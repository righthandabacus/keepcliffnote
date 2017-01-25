import logging
import re
import argparse

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import staleness_of
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from lxml import etree

# PhantomJS config, override user agent string and bug workaround
DCAP = dict(DesiredCapabilities.PHANTOMJS)
DCAP.update({
    "phantomjs.page.settings.userAgent":
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/53 (KHTML, like Gecko) Chrome/15.0.87"
   ,"phantomjs.page.settings.loadImages": True
})

###################################
# Helper functions
#

def parse_page(browser):
    # Cliffnote: main text elements all have class litNoteText. Subheadings are
    # in <b>, page title is in <h2>, and main text may contain various mark up
    elems = browser.find_elements_by_xpath("//article[.//p[@class='litNoteText']]")
    if len(elems) != 1:
        return # probably means no more next page
    # inside main body container, filter for children of interest, make HTML and feed to lxml
    rawHtml = ''.join(x.get_attribute('outerHTML')
                      for x in elems[0].find_elements_by_xpath("*")
                      if x.text and ('Bookmark this page' not in x.text))
    # clean up HTML via lxml.etree
    tree = etree.fromstring(rawHtml,
                            etree.HTMLParser(remove_blank_text=True, remove_comments=True, remove_pis=True))
    etree.strip_tags(tree, 'span')
    for x in reversed(tree.xpath("//*")):
        if x.attrib:
            x.attrib.clear()
        if x.text:
            x.text = re.sub(r'\s+', ' ', x.text) # contracting whitespace
        if x.tail:
            x.tail= re.sub(r'\s+', ' ', x.tail) # contracting whitespace
        if len(x): continue
        # remove this element if it is empty, but preserve the tail
        parent = x.getparent()
        if parent is not None and (not x.text or not x.text.strip()):
            if x.tail:
                previous = x.getprevious()
                if previous is not None:
                    previous.tail = re.sub(r'\s+', ' ', (previous.tail or '') + x.tail)
                else:
                    parent.text = re.sub(r'\s+', ' ', (parent.text or '') + x.tail)
            parent.remove(x) # remove empty items

    # Find link to next page
    next_anchor = browser.find_element_by_xpath("//*[contains(@class,'clear-padding-right')]/*[contains(@class,'nav-bttn-filled')]")
    next_link = None
    if next_anchor is not None:
        next_link = next_anchor.get_attribute('href')
        if not next_link or not next_link.startswith('http'):
            # Selenium/PhantomJS converts href into full links on get_attribute() return
            next_link = None
    # Return the parsed tree, link object, and link URL
    return tree, next_anchor, next_link

def parseargs():
    parser = argparse.ArgumentParser(
                description='CliffNotes crawler. Convert multiple pages of a title into one single, cleaned HTML'
               ,formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("url", help="starting URL to crawl, example: https://www.cliffsnotes.com/literature/p/the-prince/book-summary")
    parser.add_argument("-l", dest="limit", type=int, default=50, help="max number of pages to crawl")
    parser.add_argument("-d", dest="debug", action="store_true", default=False, help="debug: to save crawled pages")
    parser.add_argument("-o", dest="output", default="output.html", help="output HTML file name")
    return parser.parse_args()

###################################
# main program
#
def main():
    args = parseargs()
    # Start PhantomJS, crawl page
    pagecount = 1
    browser = webdriver.PhantomJS(desired_capabilities=DCAP)
    logging.info("%d: %s" % (pagecount, args.url))
    browser.get(args.url)
    if args.debug:
        open("page_%d.html" % pagecount,"w").write(str(browser.page_source.encode('utf-8')))
    doctree, next_anchor, next_link = parse_page(browser)
    docbody = doctree.xpath("//body")[0]
    # follow links
    while next_link:
        # click on "next page" link, browser should load next page
        next_anchor.click()
        WebDriverWait(browser, 30).until(staleness_of(next_anchor))
        pagecount += 1
        logging.info("%d: %s" % (pagecount, next_link))
        if args.debug:
            open("page_%d.html" % pagecount,"w").write(str(browser.page_source.encode('utf-8')))
        # parse again, combine tree
        try:
            tree, next_anchor, next_link = parse_page(browser)
        except:
            break
        if tree is not None:
            for x in tree.xpath("//body/*"):
                docbody.append(x)
        # safe guard
        if pagecount >= args.limit:
            break
    # output
    logging.info("Crawled %d pages" % pagecount)
    open(args.output,"w").write(etree.tostring(doctree, pretty_print=True, method="html"))
    # stop PhantomJS
    import signal
    browser.service.process.send_signal(signal.SIGTERM) # kill the specific phantomjs child proc
    browser.quit()     

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO) # debug will be noisy with selenium
    main()

# vim:set nowrap et ts=4 sw=4:
