CliffNotes crawler: Details and future work
===========================================


Scrapy and selenium
-------------------
Scrapy is the spider engine. Selenium is the webdriver. By default, scrapy
crawl pages using urllib, the default Python HTTP library. There is no way to
replace urllib, but we have tricks to make scrapy and selenium work together:


### Retrieving the page the second time by selenium

This is an example from <http://stackoverflow.com/questions/17975471/selenium-with-scrapy-for-dynamic-page?noredirect=1&lq=1>:

```python
import scrapy
from selenium import webdriver

class ProductSpider(scrapy.Spider):
    name = "product_spider"
    allowed_domains = ['ebay.com']
    start_urls = ['http://www.ebay.com/sch/i.html?_odkw=books&_osacat=0&_trksid=p2045573.m570.l1313.TR0.TRC0.Xpython&_nkw=python&_sacat=0&_from=R40']
    def __init__(self):
        self.driver = webdriver.Firefox()
    def parse(self, response):
        self.driver.get(response.url)
        while True:
            next = self.driver.find_element_by_xpath('//td[@class="pagn-next"]/a')
            try:
                next.click()
                # get the data and write it to scrapy items
            except:
                break
        self.driver.close()
```

This is another example from
<http://stackoverflow.com/questions/10648644/executing-javascript-submit-form-functions-using-scrapy-in-python>

```python
# Snippet imported from snippets.scrapy.org (which no longer works)
from scrapy.contrib.spiders import CrawlSpider, Rule
from scrapy.contrib.linkextractors.sgml import SgmlLinkExtractor
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request

from selenium import selenium

class SeleniumSpider(CrawlSpider):
    name = "SeleniumSpider"
    start_urls = ["http://www.domain.com"]
    rules = (
        Rule(SgmlLinkExtractor(allow=('\.html', )),
        callback='parse_page',follow=True),
    )
    def __init__(self):
        CrawlSpider.__init__(self)
        self.verificationErrors = []
        self.selenium = selenium("localhost", 4444, "*chrome", "http://www.domain.com")
        self.selenium.start()
    def __del__(self):
        self.selenium.stop()
        print self.verificationErrors
        CrawlSpider.__del__(self)
    def parse_page(self, response):
        item = Item()
        hxs = HtmlXPathSelector(response)
        #Do some XPath selection with Scrapy
        hxs.select('//div').extract()
        self.selenium.open(response.url)
        #Wait for javscript to load in Selenium
        time.sleep(2.5)
        #Do some crawling of javascript created content with Selenium
        self.selenium.get_text("//div")
        yield item
```

The concept here is to use the scrapy spider to pull a URL, but when the HTTP
responsed, extract the URL and pull again with selenium. Then work on
selenium's copy instead.


### Crawl pages using selenium, and extract data using scrapy

This the the example from the same link as above. It uses selenium to get page
and simulate user responses. Then uses `browser.page_source` to retrieve the
HTML from selenium and build TextResponse object for scrapy. Afterwards,
extract data using HtmlXPathSelector.

```python
# stripped down BoltBus script - https://github.com/nicodjimenez/bus_catchers
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Response
from scrapy.http import TextResponse
import time

# set dates, origin, destination
cityOrigin, cityDeparture ="Baltimore", "New York"
day_array=[0]
browser = webdriver.Firefox()

# we are going the day of the days of the month from 15,16,...,25
# there is a discrepancy between the index of the calendar days and the day itself: for example day[10] may correspond to Feb 7th
for day in day_array:
    # Create a new instance of the Firefox driver
    browser.get("http://www.boltbus.com")
    # click on "region" tab
    elem_0=browser.find_element_by_id("ctl00_cphM_forwardRouteUC_lstRegion_textBox")
    elem_0.click()
    time.sleep(5)
    # select Northeast
    elem_1=browser.find_element_by_partial_link_text("Northeast")
    elem_1.click()
    time.sleep(5)
    # click on origin city
    elem_2=browser.find_element_by_id("ctl00_cphM_forwardRouteUC_lstOrigin_textBox")
    elem_2.click()
    time.sleep(5)
    # select origin city
    elem_3=browser.find_element_by_partial_link_text(cityOrigin)
    elem_3.click()
    time.sleep(5)
    # click on destination city
    elem_4=browser.find_element_by_id("ctl00_cphM_forwardRouteUC_lstDestination_textBox")
    elem_4.click()
    time.sleep(5)
    # select destination city
    elem_5=browser.find_element_by_partial_link_text(cityDeparture)
    elem_5.click()
    time.sleep(5)
    # click on travel date
    travel_date_elem=browser.find_element_by_id("ctl00_cphM_forwardRouteUC_imageE")
    travel_date_elem.click()
    # gets day rows of table
    date_rows=browser.find_elements_by_class_name("daysrow")
    # select actual day (use variable day)
    # NOTE: you must make sure these day elements are "clickable"
    days=date_rows[0].find_elements_by_xpath("..//td")
    days[day].click()
    time.sleep(3)
    # retrieve actual departure date from browser
    depart_date_elem=browser.find_element_by_id("ctl00_cphM_forwardRouteUC_txtDepartureDate")
    depart_date=str(depart_date_elem.get_attribute("value"))

    # PARSE TABLE

    # convert html to "nice format"
    text_html=browser.page_source.encode('utf-8')
    html_str=str(text_html)
    # this is a hack that initiates a "TextResponse" object (taken from the Scrapy module)
    resp_for_scrapy=TextResponse('none',200,{},html_str,[],None)
    # takes a "TextResponse" object and feeds it to a scrapy function which will convert the raw HTML to a XPath document tree
    hxs=HtmlXPathSelector(resp_for_scrapy)
    # the | sign means "or"
    table_rows=hxs.select('//tr[@class="fareviewrow"] | //tr[@class="fareviewaltrow"]')
    row_ct=len(table_rows)

    for x in xrange(row_ct):
        cur_node_elements=table_rows[x]
        travel_price=cur_node_elements.select('.//td[@class="faresColumn0"]/text()').re("\d{1,3}\.\d\d")

        # I use a mixture of xpath selectors to get me to the right location in the document, and regular expressions to get the exact data

        # actual digits of time
        depart_time_num=cur_node_elements.select('.//td[@class="faresColumn1"]/text()').re("\d{1,2}\:\d\d")
        # AM or PM (time signature)
        depart_time_sig=cur_node_elements.select('.//td[@class="faresColumn1"]/text()').re("[AP][M]")
        # actual digits of time
        arrive_time_num=cur_node_elements.select('.//td[@class="faresColumn2"]/text()').re("\d{1,2}\:\d\d")
        # AM or PM (time signature)
        arrive_time_sig=cur_node_elements.select('.//td[@class="faresColumn2"]/text()').re("[AP][M]")

        print "Depart date: " + depart_date
        print "Depart time: " + depart_time_num[0] + " " + depart_time_sig[0]
        print "Arrive time: " + arrive_time_num[0] + " " + arrive_time_sig[0]
        print "Cost: " + "$" + travel_price[0]
        print "\n"
```

The use of HtmlXPathSelector in scrapy is more obvious in the following
full-featured sample (crawling NYC land parcel from ACRIS, from
<http://stackoverflow.com/questions/16785540/python-data-scraping-with-scrapy/16786934#16786934>):

```python
from scrapy.http import FormRequest
from scrapy.item import Item, Field
from scrapy.selector import HtmlXPathSelector
from scrapy.spider import BaseSpider

class AcrisItem(Item):
    borough = Field()
    block = Field()
    doc_type_name = Field()

class AcrisSpider(BaseSpider):
    name = "acris"
    allowed_domains = ["a836-acris.nyc.gov"]
    start_urls = ['http://a836-acris.nyc.gov/DS/DocumentSearch/DocumentType']

    def parse(self, response):
        hxs = HtmlXPathSelector(response)
        document_classes = hxs.select('//select[@name="combox_doc_doctype"]/option')

        form_token = hxs.select('//input[@name="__RequestVerificationToken"]/@value').extract()[0]
        for document_class in document_classes:
            if document_class:
                doc_type = document_class.select('.//@value').extract()[0]
                doc_type_name = document_class.select('.//text()').extract()[0]
                formdata = {'__RequestVerificationToken': form_token,
                            'hid_selectdate': '7',
                            'hid_doctype': doc_type,
                            'hid_doctype_name': doc_type_name,
                            'hid_max_rows': '10',
                            'hid_ISIntranet': 'N',
                            'hid_SearchType': 'DOCTYPE',
                            'hid_page': '1',
                            'hid_borough': '0',
                            'hid_borough_name': 'ALL BOROUGHS',
                            'hid_ReqID': '',
                            'hid_sort': '',
                            'hid_datefromm': '',
                            'hid_datefromd': '',
                            'hid_datefromy': '',
                            'hid_datetom': '',
                            'hid_datetod': '',
                            'hid_datetoy': '', }
                yield FormRequest(url="http://a836-acris.nyc.gov/DS/DocumentSearch/DocumentTypeResult",
                                  method="POST",
                                  formdata=formdata,
                                  callback=self.parse_page,
                                  meta={'doc_type_name': doc_type_name})

    def parse_page(self, response):
        hxs = HtmlXPathSelector(response)

        rows = hxs.select('//form[@name="DATA"]/table/tbody/tr[2]/td/table/tr')
        for row in rows:
            item = AcrisItem()
            borough = row.select('.//td[2]/div/font/text()').extract()
            block = row.select('.//td[3]/div/font/text()').extract()

            if borough and block:
                item['borough'] = borough[0]
                item['block'] = block[0]
                item['doc_type_name'] = response.meta['doc_type_name']

                yield item
```

and this will be the output of `scrapy runspider spider.py -o output.json`:

```json
{"doc_type_name": "CONDEMNATION PROCEEDINGS ", "borough": "Borough", "block": "Block"}
{"doc_type_name": "CERTIFICATE OF REDUCTION ", "borough": "Borough", "block": "Block"}
{"doc_type_name": "COLLATERAL MORTGAGE ", "borough": "Borough", "block": "Block"}
{"doc_type_name": "CERTIFIED COPY OF WILL ", "borough": "Borough", "block": "Block"}
{"doc_type_name": "CONFIRMATORY DEED ", "borough": "Borough", "block": "Block"}
{"doc_type_name": "CERT NONATTCHMENT FED TAX LIEN ", "borough": "Borough", "block": "Block"}
...
```


Delay
-----
In selenium, sleep time can be made dynamic by explicit or implicit waits
(<http://www.seleniumhq.org/docs/04_webdriver_advanced.jsp>):

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait # available since 2.4.0
from selenium.webdriver.support import expected_conditions as EC # available since 2.26.0

ff = webdriver.Firefox()
ff.get("http://somedomain/url_that_delays_loading")
try:
    element = WebDriverWait(ff, 10).until(EC.presence_of_element_located((By.ID, "myDynamicElement")))
finally:
    ff.quit()
```

In the above WebDriverWait() has timeout of 10 seconds. If the element is
located before timeout, it will be assigned. Otherwise TimeoutException
will be raised. Besides `presence_of_element_located()`, we can have
`element_to_be_clickable()` as well, in same function signature.

WebDriverWait() is also used to wait until a page is loaded (e.g., upon clicking
a link to another page). An element object will become staled when the page is
replaced. Therefore, we can detect for object staleness in waiting for a new
page is being load and rendered:

    WebDriverWait(browser, timeout).until(staleness_of(old_page_element))


Miscellaneous selenium tricks
-----------------------------
<http://stackoverflow.com/questions/27307131/selenium-webdriver-how-do-i-find-all-of-an-elements-attributes>

To find an element after page is load:
    elements = browser.find_elements_by_xpath(...)
	element = elements[0]
Alternatively, we have `find_elements_by_tag_name`, `find_elements_by_class_name`,
`find_elements_by_css_selector`, `find_elements_by_id`, `find_elements_by_link_text`,
`find_elements_by_name`, and `find_elements_by_partial_link_text`. To get the first
element found, use `find_element` instead of `find_elements`.

To find an attribute of an element:
	attribute = element.get_attribute('href')
But to enumerate all attributes, we have to use JavaScript:

```python
attrs = driver.execute_script('''
	var items = {};
	for (index = 0; index < arguments[0].attributes.length; ++index) {
		items[arguments[0].attributes[index].name] = arguments[0].attributes[index].value
	};
	return items;
''', element)
pprint(attrs)
# {u'class': u'topbar-icon icon-site-switcher yes-hover js-site-switcher-button js-gps-track',
#  u'data-gps-track': u'site_switcher.show',
#  u'href': u'//stackexchange.com',
#  u'title': u'A list of all 132 Stack Exchange sites'}
```

For CSS attributes, we need the *computed style*:

```python
browser.execute_script('return window.getComputedStyle(arguments[0])', elem)
# returns:
#   ['-webkit-align-content', '-webkit-align-items', '-webkit-align-self',
#    '-webkit-animation-delay', '-webkit-animation-direction',
#    '-webkit-animation-duration', '-webkit-animation-fill-mode',
#    '-webkit-animation-iteration-count', '-webkit-animation-name',
#    '-webkit-animation-play-state', '-webkit-animation-timing-function',
#    '-webkit-appearance', '-webkit-backface-visibility',
#    '-webkit-background-blend-mode', '-webkit-background-clip',
#    '-webkit-background-composite', '-webkit-background-origin',
#    '-webkit-background-size', '-webkit-blend-mode', '-webkit-border-fit',
#    '-webkit-border-horizontal-spacing', '-webkit-border-image',
#    '-webkit-border-vertical-spacing', '-webkit-box-align',
#    '-webkit-box-decoration-break', '-webkit-box-direction',
#    '-webkit-box-flex', '-webkit-box-flex-group', '-webkit-box-lines',
#    '-webkit-box-ordinal-group', '-webkit-box-orient', '-webkit-box-pack',
#    '-webkit-box-reflect', '-webkit-box-shadow', '-webkit-clip-path',
#    '-webkit-color-correction', '-webkit-column-axis',
#    '-webkit-column-break-after', '-webkit-column-break-before',
#    '-webkit-column-break-inside', '-webkit-column-count',
#    '-webkit-column-gap', '-webkit-column-progression',
#    '-webkit-column-rule-color', '-webkit-column-rule-style',
#    '-webkit-column-rule-width', '-webkit-column-span',
#    '-webkit-column-width', '-webkit-filter', '-webkit-flex-basis',
#    '-webkit-flex-direction', '-webkit-flex-grow', '-webkit-flex-shrink',
#    '-webkit-flex-wrap', '-webkit-flow-from', '-webkit-flow-into',
#    '-webkit-font-kerning', '-webkit-font-smoothing',
#    '-webkit-font-variant-ligatures', '-webkit-grid-after',
#    '-webkit-grid-auto-columns', '-webkit-grid-auto-flow',
#    '-webkit-grid-auto-rows', '-webkit-grid-before',
#    '-webkit-grid-definition-columns', '-webkit-grid-definition-rows',
#    '-webkit-grid-end', '-webkit-grid-start', '-webkit-highlight',
#    '-webkit-hyphenate-character', '-webkit-hyphenate-limit-after',
#    '-webkit-hyphenate-limit-before', '-webkit-hyphenate-limit-lines',
#    '-webkit-hyphens', '-webkit-justify-content', '-webkit-line-align',
#    '-webkit-line-box-contain', '-webkit-line-break', '-webkit-line-clamp',
#    '-webkit-line-grid', '-webkit-line-snap', '-webkit-locale',
#    '-webkit-margin-after-collapse', '-webkit-margin-before-collapse',
#    '-webkit-marquee-direction', '-webkit-marquee-increment',
#    '-webkit-marquee-repetition', '-webkit-marquee-style',
#    '-webkit-mask-box-image', '-webkit-mask-box-image-outset',
#    '-webkit-mask-box-image-repeat', '-webkit-mask-box-image-slice',
#    '-webkit-mask-box-image-source', '-webkit-mask-box-image-width',
#    '-webkit-mask-clip', '-webkit-mask-composite', '-webkit-mask-image',
#    '-webkit-mask-origin', '-webkit-mask-position', '-webkit-mask-repeat',
#    '-webkit-mask-size', '-webkit-nbsp-mode', '-webkit-order',
#    '-webkit-perspective', '-webkit-perspective-origin',
#    '-webkit-print-color-adjust', '-webkit-region-break-after',
#    '-webkit-region-break-before', '-webkit-region-break-inside',
#    '-webkit-region-fragment', '-webkit-rtl-ordering',
#    '-webkit-shape-inside', '-webkit-shape-margin', '-webkit-shape-outside',
#    '-webkit-shape-padding', '-webkit-svg-shadow',
#    '-webkit-tap-highlight-color', '-webkit-text-combine',
#    '-webkit-text-decorations-in-effect', '-webkit-text-emphasis-color',
#    '-webkit-text-emphasis-position', '-webkit-text-emphasis-style',
#    '-webkit-text-fill-color', '-webkit-text-orientation',
#    '-webkit-text-security', '-webkit-text-stroke-color',
#    '-webkit-text-stroke-width', '-webkit-transform',
#    '-webkit-transform-origin', '-webkit-transform-style',
#    '-webkit-transition-delay', '-webkit-transition-duration',
#    '-webkit-transition-property', '-webkit-transition-timing-function',
#    '-webkit-user-drag', '-webkit-user-modify', '-webkit-user-select',
#    '-webkit-wrap-flow', '-webkit-wrap-through', '-webkit-writing-mode',
#    'alignment-baseline', 'background-attachment', 'background-clip',
#    'background-color', 'background-image', 'background-origin',
#    'background-position', 'background-repeat', 'background-size',
#    'baseline-shift', 'border-bottom-color', 'border-bottom-left-radius',
#    'border-bottom-right-radius', 'border-bottom-style',
#    'border-bottom-width', 'border-collapse', 'border-image-outset',
#    'border-image-repeat', 'border-image-slice', 'border-image-source',
#    'border-image-width', 'border-left-color', 'border-left-style',
#    'border-left-width', 'border-right-color', 'border-right-style',
#    'border-right-width', 'border-top-color', 'border-top-left-radius',
#    'border-top-right-radius', 'border-top-style', 'border-top-width',
#    'bottom', 'box-shadow', 'box-sizing', 'buffered-rendering',
#    'caption-side', 'clear', 'clip', 'clip-path', 'clip-rule', 'color',
#    'color-interpolation', 'color-interpolation-filters',
#    'color-rendering', 'cursor', 'direction', 'display',
#    'dominant-baseline', 'empty-cells', 'fill', 'fill-opacity', 'fill-rule',
#    'filter', 'float', 'flood-color', 'flood-opacity', 'font-family',
#    'font-size', 'font-style', 'font-variant', 'font-weight',
#    'glyph-orientation-horizontal', 'glyph-orientation-vertical', 'height',
#    'image-rendering', 'kerning', 'left', 'letter-spacing',
#    'lighting-color', 'line-height', 'list-style-image',
#    'list-style-position', 'list-style-type', 'margin-bottom', 'margin-left',
#    'margin-right', 'margin-top', 'marker-end', 'marker-mid', 'marker-start',
#    'mask', 'mask-type', 'max-height', 'max-width', 'min-height',
#    'min-width', 'opacity', 'orphans', 'outline-color', 'outline-offset',
#    'outline-style', 'outline-width', 'overflow-wrap', 'overflow-x',
#    'overflow-y', 'padding-bottom', 'padding-left', 'padding-right',
#    'padding-top', 'page-break-after', 'page-break-before',
#    'page-break-inside', 'pointer-events', 'position', 'resize', 'right',
#    'shape-rendering', 'speak', 'stop-color', 'stop-opacity', 'stroke',
#    'stroke-dasharray', 'stroke-dashoffset', 'stroke-linecap',
#    'stroke-linejoin', 'stroke-miterlimit', 'stroke-opacity',
#    'stroke-width', 'tab-size', 'table-layout', 'text-align', 'text-anchor',
#    'text-decoration', 'text-indent', 'text-overflow', 'text-rendering',
#    'text-shadow', 'text-transform', 'top', 'transition-delay',
#    'transition-duration', 'transition-property',
#    'transition-timing-function', 'unicode-bidi', 'vector-effect',
#    'vertical-align', 'visibility', 'white-space', 'widows', 'width',
#    'word-break', 'word-spacing', 'word-wrap', 'writing-mode', 'z-index', 'zoom']
browser.execute_script('''
    return window.getComputedStyle(arguments[0]).getPropertyValue("color")
''', elem)
# returns
#    'rgb(34, 34, 34)'
```

Alternatively, read from the element's HTML:
    elem.get_attribute('outerHTML')
or just inside:
	elem.get_attribute('innerHTML')

Selenium/PhantomJS does not provide a rich API but can be complemented by JavaScript.


PhantomJS
---------
PhantomJS has default user-agent string of the following:

    Mozilla/5.0 (Unknown; Linux x86_64) AppleWebKit/538.1 (KHTML, like Gecko) PhantomJS/2.1.1 Safari/538.1

and this can be checked by

    browser.execute_script("return navigator.userAgent")

and can be overridden by setting desired capabilities
`phantomjs.page.settings.userAgent`. PhantomJS has a bug of memory leak that
can be worked around by allowing images to be loaded, the desired
capabilities `phantomjs.page.settings.loadImages`. This is the example:

```python
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
DCAP = dict(DesiredCapabilities.PHANTOMJS)
DCAP.update({
    "phantomjs.page.settings.userAgent":
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/53 (KHTML, like Gecko) Chrome/15.0.87"
   ,"phantomjs.page.settings.loadImages": True
})
browser = webdriver.PhantomJS(desired_capabilities=DCAP)
```

Upon the program terminate, PhantomJS that launched by Selenium will not be
shutdown. It is recommended to do the following to terminate PhantomJS process
and all its children:

```python
import signal
driver.service.process.send_signal(signal.SIGTERM) # kill the specific phantomjs child proc
driver.quit()                                      # quit the node proc
```


lxml
----
We get raw HTML from selenium and pass on to lxml for extracting data. We
construct a DOM tree by

   tree = etree.fromstring(htmlstr,
                           etree.HTMLParser(remove_blank_text=True, remove_comments=True, remove_pis=True))

And to ignore tags (but retain elements inside), we use strip_tags:

   etree.strip_tags(tree, 'span')

In the DOM of lxml.etree, each element has

- `x.text`, the text string right following opening tag
- `x.tail`, the text string right following the closing tag

Text is not a standalone tree node, but part of another node.


Scraping main text
------------------

<http://stackoverflow.com/questions/4672060/web-scraping-how-to-identify-main-content-on-a-webpage>
<https://github.com/chrisspen/webarticle2text/blob/master/webarticle2text/webarticle2text.py>
<http://web.archive.org/web/20080620121103/http://ai-depot.com/articles/the-easy-way-to-extract-useful-text-from-arbitrary-html/>
<https://github.com/kohlschutter/boilerpipe>


Future work
-----------
Creating a Google doc on by script doesn't seem to have many examples available:

- <https://developers.google.com/drive/v2/reference/files/insert#examples>
- <https://developers.google.com/apps-script/reference/document/>

The way that may work is to create a Google AppScript first (which seems to be
the only way to create a new document) and call that AppScript with suitable
argument.

Creating a MS Word document,
see the [python-docx package](https://pypi.python.org/pypi/python-docx)
