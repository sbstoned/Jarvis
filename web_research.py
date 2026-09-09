import html
import re
import urllib.parse
from html.parser import HTMLParser

import requests

HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36"}

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts=[]
        self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag.lower() in {"script","style","noscript","svg"}: self.skip+=1
    def handle_endtag(self,tag):
        if tag.lower() in {"script","style","noscript","svg"} and self.skip: self.skip-=1
    def handle_data(self,data):
        if not self.skip:
            s=re.sub(r"\s+"," ",str(data or "")).strip()
            if s:self.parts.append(s)

def visible_text(markup,limit=12000):
    p=TextExtractor()
    try:p.feed(markup)
    except Exception:pass
    return html.unescape(" ".join(p.parts))[:limit]

def search(query,max_results=5,timeout=12):
    q=urllib.parse.quote_plus(str(query or "").strip())
    if not q:return []
    r=requests.get(f"https://html.duckduckgo.com/html/?q={q}",headers=HEADERS,timeout=timeout)
    r.raise_for_status()
    pattern=re.compile(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',re.I|re.S)
    out=[]
    for href,title_html in pattern.findall(r.text):
        title=html.unescape(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",title_html))).strip()
        href=html.unescape(href)
        parsed=urllib.parse.urlparse(href)
        qs=urllib.parse.parse_qs(parsed.query)
        if "uddg" in qs:href=urllib.parse.unquote(qs["uddg"][0])
        if not href.startswith(("http://","https://")):continue
        if any(x["url"]==href for x in out):continue
        out.append({"title":title or href,"url":href})
        if len(out)>=max_results:break
    return out

def fetch_page(url,timeout=12,max_chars=9000):
    r=requests.get(url,headers=HEADERS,timeout=timeout,allow_redirects=True)
    r.raise_for_status()
    ctype=r.headers.get("content-type","").lower()
    if "text/html" not in ctype and "text/plain" not in ctype:return ""
    return visible_text(r.text,max_chars)

def research(query,max_sources=4):
    sources=[]
    for item in search(query,max_results=max_sources+2):
        try:text=fetch_page(item["url"])
        except Exception as exc:text=f"[Could not read page: {exc}]"
        sources.append({"title":item["title"],"url":item["url"],"text":text})
        if len(sources)>=max_sources:break
    return {"query":query,"sources":sources}
