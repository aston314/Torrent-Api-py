import asyncio
import re
import time
import aiohttp
from bs4 import BeautifulSoup
from helper.asyncioPoliciesFix import decorator_asyncio_fix
from helper.html_scraper import Scraper
from constants.base_url import X1337
from constants.headers import HEADER_AIO


class x1337:
    _name = "1337x"
    def __init__(self):
        self.BASE_URL = X1337
        self.LIMIT = None

    @decorator_asyncio_fix
    async def _individual_scrap(self, session, url, obj):
        try:
            async with session.get(url, headers=HEADER_AIO) as res:
                html = await res.text(encoding="ISO-8859-1")
                soup = BeautifulSoup(html, "html.parser")
                try:
                    magnet = soup.select_one(".no-top-radius > div > ul > li > a")[
                        "href"
                    ]
                    uls = soup.find_all("ul", class_="list")[1]
                    lis = uls.find_all("li")[0]
                    imgs = [
                        img["data-original"]
                        for img in (soup.find("div", id="description")).find_all("img")
                        if img["data-original"].endswith((".png", ".jpg", ".jpeg"))
                    ]
                    files = [
                        f.text for f in soup.find("div", id="files").find_all("li")
                    ]
                    if len(imgs) > 0:
                        obj["screenshot"] = imgs
                    obj["category"] = lis.find("span").text
                    obj["files"] = files
                    try:
                        poster = soup.select_one("div.torrent-image img")["src"]
                        if str(poster).startswith("//"):
                            obj["poster"] = "https:" + poster
                        elif str(poster).startswith("/"):
                            obj["poster"] = self.BASE_URL + poster
                    except:
                        ...
                    obj["magnet"] = magnet

                    obj["hash"] = re.search(
                        r"([{a-f\d,A-F\d}]{32,40})\b", magnet
                    ).group(0)
                except IndexError:
                    ...
        except:
            return None

    async def _get_torrent(self, result, session, urls):
        tasks = []
        for idx, url in enumerate(urls):
            for obj in result["data"]:
                if obj["url"] == url:
                    task = asyncio.create_task(
                        self._individual_scrap(session, url, result["data"][idx])
                    )
                    tasks.append(task)
        await asyncio.gather(*tasks)
        return result

    def _parser(self, htmls):
        try:
            for html in htmls:
                soup = BeautifulSoup(html, "html.parser")
                list_of_urls = []
                my_dict = {"data": []}
                trs = soup.select("tbody tr")
                for tr in trs:
                    td = tr.find_all("td")
                    name = td[0].find_all("a")[-1].text
                    if name:
                        url = self.BASE_URL + td[0].find_all("a")[-1]["href"]
                        list_of_urls.append(url)
                        seeders = td[1].text
                        leechers = td[2].text
                        date = td[3].text
                        size = td[4].text.replace(seeders, "")
                        uploader = td[5].find("a").text

                        my_dict["data"].append(
                            {
                                "name": name,
                                "size": size,
                                "date": date,
                                "seeders": seeders,
                                "leechers": leechers,
                                "url": url,
                                "uploader": uploader,
                            }
                        )
                    if len(my_dict["data"]) == self.LIMIT:
                        break
                try:
                    pages = soup.select(".pagination li a")
                    my_dict["current_page"] = int(pages[0].text)
                    tpages = pages[-1].text
                    if tpages == ">>":
                        my_dict["total_pages"] = int(pages[-2].text)
                    else:
                        my_dict["total_pages"] = int(pages[-1].text)
                except:
                    ...
                return my_dict, list_of_urls
        except:
            return None, None

    async def search(self, query, page, limit):
        async with aiohttp.ClientSession() as session:
            self.LIMIT = limit
            start_time = time.time()
            url = self.BASE_URL + "/search/{}/{}/".format(query, page)
            return await self.parser_result(
                start_time, url, session, query=query, page=page
            )

    async def parser_result(self, start_time, url, session, page, query=None):
        htmls = await Scraper().get_all_results(session, url)
        result, urls = self._parser(htmls)
        if result is not None:
            results = await self._get_torrent(result, session, urls)
            results["time"] = time.time() - start_time
            results["total"] = len(results["data"])
            if query is None:
                return results
            while True:
                if len(results["data"]) >= self.LIMIT:
                    results["data"] = results["data"][0 : self.LIMIT]
                    results["total"] = len(results["data"])
                    return results
                page = page + 1
                url = self.BASE_URL + "/search/{}/{}/".format(query, page)
                htmls = await Scraper().get_all_results(session, url)
                result, urls = self._parser(htmls)
                if result is not None:
                    if len(result["data"]) > 0:
                        res = await self._get_torrent(result, session, urls)
                        for obj in res["data"]:
                            results["data"].append(obj)
                        try:
                            results["current_page"] = res["current_page"]
                        except:
                            ...
                        results["time"] = time.time() - start_time
                        results["total"] = len(results["data"])
                    else:
                        break
                else:
                    break
            return results
        return result

    async def trending(self, category, page, limit):
        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            self.LIMIT = limit
            if not category:
                url = self.BASE_URL + "/home/"
            else:
                url = self.BASE_URL + "/popular-{}".format(category.lower())
            return await self.parser_result(start_time, url, session, page)

    async def recent(self, category, page, limit):
        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            self.LIMIT = limit
            if not category:
                url = self.BASE_URL + "/trending"
            else:
                url = self.BASE_URL + "/cat/{}/{}/".format(
                    str(category).capitalize(), page
                )
            return await self.parser_result(start_time, url, session, page)

    async def search_by_category(self, query, category, page, limit):
        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            self.LIMIT = limit
            url = self.BASE_URL + "/category-search/{}/{}/{}/".format(
                query, category.capitalize(), page
            )
            return await self.parser_result(start_time, url, session, page, query)
