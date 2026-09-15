#!/usr/bin/env python3
"""
台北榮總醫師科別爬蟲
輸出：{docId: {name, departments: [...]}} JSON

使用方式：
    python vghtpe_doctor_scraper.py
    python vghtpe_doctor_scraper.py --output doctors.json
    python vghtpe_doctor_scraper.py --delay 2.0
"""

import re
import json
import time
import argparse
import logging

from curl_cffi import requests
from bs4 import BeautifulSoup

BASE_URL  = "https://www6.vghtpe.gov.tw/reg"
SECT_URL_RETURN = BASE_URL + "/sectList.do?type=return"
SECT_URL_FIRST  = BASE_URL + "/sectList.do?type=first"
TABLE_URL = BASE_URL + "/opdTimetable.do"
MAX_PAGES = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def make_session():
    sess = requests.Session(impersonate="chrome124")
    sess.headers.update({
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Referer":         "https://www6.vghtpe.gov.tw/reg/home.do",
    })
    return sess


def get_html(sess, url, retries=3):
    for attempt in range(retries):
        try:
            r = sess.get(url, timeout=25)
            if r.status_code == 200:
                return r.text
            log.warning("HTTP %s  %s", r.status_code, url)
        except Exception as e:
            log.warning("第 %d 次失敗 %s: %s", attempt + 1, url, e)
            time.sleep(2 ** attempt)
    return None


def parse_sect_list(html, visit_type="return"):
    soup = BeautifulSoup(html, "html.parser")
    departments = []

    for tbl in soup.find_all("table", class_=lambda c: c and "sect_list" in c):
        th = tbl.find("th")
        category = re.sub(r"\s+", " ", th.get_text(" ", strip=True)) if th else "未分類"

        for a in tbl.find_all("a", href=True):
            href = a["href"]
            dept_name = a.get_text(strip=True)
            m = re.search(r"sec=([^&]+)", href)
            if not m:
                continue
            sec = m.group(1)
            is_ss = "ssTimetable" in href
            if is_ss:
                url = BASE_URL + "/ssTimetable.do?sec=" + sec
            else:
                url = TABLE_URL + "?page=1&type=" + visit_type + "&sec=" + sec

            departments.append({
                "category":   category,
                "dept_name":  dept_name,
                "sec":        sec,
                "url":        url,
                "is_ss":      is_ss,
                "visit_type": visit_type,
            })

    log.info("共解析 %d 個科別 (type=%s)", len(departments), visit_type)
    return departments


# 排班/代診佔位 doc_id
PLACEHOLDER_IDS = {"DOC9995A", "DOC9979K", "DOC9983G", "DOC0079J", "DOC9995"}

def parse_timetable(html, tag_to_dept=None):
    """
    回傳 {doc_id: {"name": name, "tag": tag_or_None}}
    tag_to_dept: 細項標籤 -> 子科別 對照表
    """
    soup = BeautifulSoup(html, "html.parser")
    doctors = {}

    SKIP_TEXTS = {"額滿", "請假休診", "額滿關診", "已逾掛號時間", "@"}

    # 逐個 td 格子解析
    for td in soup.find_all("td"):
        # 找醫師連結
        doc_link = td.find("a", href=re.compile(r"Docpersnr\.action\?tno=DOC"))
        if not doc_link:
            # 排班醫師
            inp = td.find("input", {"name": "regDocName"})
            if inp:
                name_val = inp.get("value", "").strip()
                if name_val.startswith("排班"):
                    if "DOC9995A" not in doctors:
                        doctors["DOC9995A"] = {"name": name_val, "tag": None}
                elif name_val and not td.find("a", href=re.compile(r"Docpersnr")):
                    key = "DOC_TEMP_" + name_val
                    if key not in doctors:
                        doctors[key] = {"name": name_val, "tag": None}
            continue

        m = re.search(r"tno=(DOC[A-Z0-9]+)", doc_link["href"])
        if not m:
            continue
        doc_id   = m.group(1)
        doc_name = doc_link.get_text(strip=True)

        # 找特長標籤（td 裡的文字節點，排除醫師姓名和狀態文字）
        detail_tag = None
        if tag_to_dept:
            for text in td.strings:
                t = text.strip().strip('"').strip()
                if (t and t != doc_name and len(t) > 1
                        and t not in SKIP_TEXTS
                        and not re.match(r"^\d", t)
                        and t in tag_to_dept):
                    detail_tag = t
                    break

        if doc_id not in doctors:
            doctors[doc_id] = {"name": doc_name, "tag": detail_tag}
        elif detail_tag and not doctors[doc_id]["tag"]:
            doctors[doc_id]["tag"] = detail_tag

    return doctors


def scrape_department(sess, dept, delay, tag_to_dept=None):
    found = {}
    sec   = dept["sec"]
    visit_type = dept.get("visit_type", "return")

    for page in range(1, MAX_PAGES + 1):
        if dept["is_ss"]:
            url = BASE_URL + "/ssTimetable.do?sec=" + sec
        else:
            url = TABLE_URL + "?page=" + str(page) + "&type=" + visit_type + "&sec=" + sec

        html = get_html(sess, url)
        time.sleep(delay)

        if not html:
            break

        doctors = parse_timetable(html, tag_to_dept=tag_to_dept)
        if not doctors and page > 1:
            break

        for doc_id, info in doctors.items():
            if doc_id not in found:
                found[doc_id] = info
            elif info.get("tag") and not found[doc_id].get("tag"):
                found[doc_id]["tag"] = info["tag"]

        if dept["is_ss"]:
            break

    result = [{"doc_id": k, "name": v["name"], "tag": v.get("tag")} for k, v in found.items()]
    tagged = [(r["name"], r["tag"]) for r in result if r["tag"]]
    if tagged:
        log.info("  有標籤的醫師：%s", tagged[:5])
    else:
        log.info("  無標籤")
    return result


def build_doctor_map(dept_doctors, tag_to_dept=None, tag_to_cat=None):
    """
    tag_to_dept: 細項標籤 -> 子科別名稱
    tag_to_cat:  子科別名稱 -> 父科別名稱
    """
    doctor_map = {}
    for entry in dept_doctors:
        for doc in entry["doctors"]:
            did  = doc["doc_id"]
            name = doc["name"]
            tag  = doc.get("tag")

            # 優先用標籤決定科別（以 hierarchy 為主）
            if tag and tag_to_dept and tag in tag_to_dept:
                dept_name = tag_to_dept[tag]
                category  = tag_to_cat.get(dept_name, entry["category"]) if tag_to_cat else entry["category"]
            else:
                dept_name = entry["dept_name"]
                category  = entry["category"]

            dept_info = {
                "category":  category,
                "dept_name": dept_name,
                "sec":       entry["sec"],
            }
            is_placeholder = (
                did in PLACEHOLDER_IDS
                or "排班" in name
                or "代診" in name
                or did.startswith("DOC_TEMP_")
            )
            if did not in doctor_map:
                doctor_map[did] = {
                    "name":           name,
                    "is_placeholder": is_placeholder,
                    "departments":    [],
                }
            if dept_info not in doctor_map[did]["departments"]:
                doctor_map[did]["departments"].append(dept_info)
    return doctor_map



# ─── App 科別對應表 ────────────────────────────────────────────────────────────
SEC_TO_APP_DEPT = {
    "001": ("內科", "一般內科"), "101": ("內科", "一般內科"), "201": ("內科", "一般內科"),
    "002": ("內科", "感染科"), "102": ("內科", "感染科"), "202": ("內科", "感染科"),
    "003": ("內科", "心臟內科"), "103": ("內科", "心臟內科"), "203": ("內科", "心臟內科"),
    "004": ("內科", "胃腸肝膽科"), "104": ("內科", "胃腸肝膽科"), "204": ("內科", "胃腸肝膽科"),
    "006": ("內科", "新陳代謝科"), "106": ("內科", "新陳代謝科"), "206": ("內科", "新陳代謝科"),
    "007": ("內科", "腎臟科"), "107": ("內科", "腎臟科"), "207": ("內科", "腎臟科"),
    "012": ("內科", "胸腔內科"), "112": ("內科", "胸腔內科"), "212": ("內科", "胸腔內科"),
    "016": ("內科", "血液腫瘤科"), "116": ("內科", "血液腫瘤科"), "216": ("內科", "血液腫瘤科"),
    "021": ("內科", "過敏免疫風濕"), "121": ("內科", "過敏免疫風濕"), "221": ("內科", "過敏免疫風濕"),
    "030": ("內科", "心臟內科(心律不整特診)"), "130": ("內科", "心臟內科(心律不整特診)"),
    "046": ("內科", "乳醫中心門診"), "146": ("內科", "乳醫中心門診"), "246": ("內科", "乳醫中心門診"),
    "048": ("內科", "腫瘤內科"), "148": ("內科", "腫瘤內科"), "248": ("內科", "腫瘤內科"),
    "055": ("內科", "家庭醫學科(一般門診/戒菸)"), "155": ("內科", "家庭醫學科(一般門診/戒菸)"), "255": ("內科", "家庭醫學科(一般門診/戒菸)"),
    "057": ("內科", "高齡醫學整合門診"), "157": ("內科", "高齡醫學整合門診"), "257": ("內科", "高齡醫學整合門診"),
    "091": ("內科", "家庭醫學科(體檢門診/成人健檢)"), "191": ("內科", "家庭醫學科(體檢門診/成人健檢)"),
    "0CG": ("內科", "職業醫學科"), "1CG": ("內科", "職業醫學科"), "2CG": ("內科", "職業醫學科"),
    "0CF": ("內科", "臨床毒物科"), "1CF": ("內科", "臨床毒物科"), "2CF": ("內科", "臨床毒物科"),
    "0CJ": ("內科", "肺腫瘤中心"), "1CJ": ("內科", "肺腫瘤中心"), "2CJ": ("內科", "肺腫瘤中心"),
    "0DC": ("內科", "糖尿病衛教諮詢門診"), "1DC": ("內科", "糖尿病衛教諮詢門診"),
    "0F8": ("內科", "睡眠醫學中心"), "1F8": ("內科", "睡眠醫學中心"),
    "0G4": ("內科", "內視鏡中心門診"), "1G4": ("內科", "內視鏡中心門診"),
    "0G5": ("內科", "心臟瓣膜門診"), "1G5": ("內科", "心臟瓣膜門診"),
    "0HF": ("內科", "心臟衰竭特別門診"), "1HF": ("內科", "心臟衰竭特別門診"),
    "0HW": ("內科", "內科整合學門診"), "1HW": ("內科", "內科整合學門診"),
    "0MB": ("內科", "新陳代謝科"), "1MB": ("內科", "新陳代謝科"),
    "0MC": ("內科", "二尖瓣膜門診"), "1MC": ("內科", "二尖瓣膜門診"),
    "0MR": ("內科", "神經內科(記憶特別門診)"), "1MR": ("內科", "神經內科(記憶特別門診)"),
    "0MV": ("內科", "心臟內科"), "1MV": ("內科", "心臟內科"),
    "0NA": ("內科", "神經內科(動作障礙特診)"), "1NA": ("內科", "神經內科(動作障礙特診)"),
    "0NB": ("內科", "神經內科(神經遺傳疾病諮詢門診)"), "1NB": ("內科", "神經內科(神經遺傳疾病諮詢門診)"),
    "0ND": ("內科", "神經內科"), "1ND": ("內科", "神經內科"),
    "0NH": ("內科", "神經內科"), "1NH": ("內科", "神經內科"),
    "0NJ": ("內科", "神經內科"), "1NJ": ("內科", "神經內科"),
    "0NK": ("內科", "神經內科"), "1NK": ("內科", "神經內科"),
    "0NN": ("內科", "神經內科"), "1NN": ("內科", "神經內科"),
    "0T4": ("內科", "胰臟癌中心"), "1T4": ("內科", "胰臟癌中心"),
    "0T5": ("外科系", "胃腫瘤醫學中心聯合門診"), "1T5": ("外科系", "胃腫瘤醫學中心聯合門診"),
    "0T6": ("內科", "胃腫瘤醫學中心聯合門診"), "1T6": ("內科", "胃腫瘤醫學中心聯合門診"),
    "0TF": ("內科", "旅遊諮詢門診"), "1TF": ("內科", "旅遊諮詢門診"),
    # 外科系
    "026": ("外科系", "骨科"), "126": ("外科系", "骨科"), "226": ("外科系", "骨科"),
    "037": ("外科系", "運動醫學"), "137": ("外科系", "運動醫學"), "237": ("外科系", "運動醫學"),
    "038": ("外科系", "脊椎外科"), "138": ("外科系", "脊椎外科"), "238": ("外科系", "脊椎外科"),
    "050": ("外科系", "關節重建"), "150": ("外科系", "關節重建"), "250": ("外科系", "關節重建"),
    "053": ("外科系", "骨病科"), "153": ("外科系", "骨病科"), "253": ("外科系", "骨病科"),
    "074": ("婦幼", "兒童骨科"), "174": ("婦幼", "兒童骨科"), "274": ("婦幼", "兒童骨科"),
    "078": ("外科系", "骨折科"), "178": ("外科系", "骨折科"), "278": ("外科系", "骨折科"),
    "0TL": ("外科系", "骨科"), "1TL": ("外科系", "骨科"),
    "0CL": ("外科系", "骨病聯合門診"), "1CL": ("外科系", "骨病聯合門診"),
    "019": ("外科系", "神經外科"), "119": ("外科系", "神經外科"),
    "035": ("外科系", "神經外科"), "135": ("外科系", "神經外科"), "235": ("外科系", "神經外科"),
    "061": ("婦幼", "兒童神經外科"), "161": ("婦幼", "兒童神經外科"), "261": ("婦幼", "兒童神經外科"),
    "0NC": ("外科系", "神經外科"), "1NC": ("外科系", "神經外科"),
    "0NF": ("外科系", "神經外科"), "1NF": ("外科系", "神經外科"),
    "0NG": ("外科系", "神經外科"), "1NG": ("外科系", "神經外科"),
    "0NL": ("外科系", "神經外科"), "1NL": ("外科系", "神經外科"),
    "029": ("外科系", "神經復健"), "129": ("外科系", "神經復健"), "229": ("外科系", "神經復健"),
    "033": ("外科系", "胸腔外科"), "133": ("外科系", "胸腔外科"), "233": ("外科系", "胸腔外科"),
    "034": ("外科系", "心臟外科"), "134": ("外科系", "心臟外科"), "234": ("外科系", "心臟外科"),
    "025": ("外科系", "心臟移植門診"), "125": ("外科系", "心臟移植門診"), "225": ("外科系", "心臟移植門診"),
    "0CB": ("外科系", "先天性心臟病"), "1CB": ("外科系", "先天性心臟病"), "2CB": ("外科系", "先天性心臟病"),
    "0CD": ("外科系", "甲狀腺外科門診"), "1CD": ("外科系", "甲狀腺外科門診"),
    "039": ("外科系", "泌尿外科"), "139": ("外科系", "泌尿外科"), "239": ("外科系", "泌尿外科"),
    "0GC": ("外科系", "泌尿外科"), "1GC": ("外科系", "泌尿外科"),
    "0GH": ("婦幼", "兒童泌尿外科"), "1GH": ("婦幼", "兒童泌尿外科"),
    "044": ("外科系", "直腸外科"), "144": ("外科系", "直腸外科"), "244": ("外科系", "直腸外科"),
    "0WS": ("外科系", "傷造口護理"), "1WS": ("外科系", "傷造口護理"),
    "043": ("外科系", "血管與主動脈"), "143": ("外科系", "血管與主動脈"), "243": ("外科系", "血管與主動脈"),
    "036": ("外科系", "整形外科"), "136": ("外科系", "整形外科"), "236": ("外科系", "整形外科"),
    "0PY": ("外科系", "整形外科(眼整形及顎顏面整形特別門診)"), "1PY": ("外科系", "整形外科(眼整形及顎顏面整形特別門診)"),
    "018": ("外科系", "醫學美容中心"), "118": ("外科系", "醫學美容中心"), "218": ("外科系", "醫學美容中心"),
    "051": ("外科系", "醫學美容中心"), "151": ("外科系", "醫學美容中心"), "251": ("外科系", "醫學美容中心"),
    "0TG": ("外科系", "多元性別手術門診"), "1TG": ("外科系", "多元性別手術門診"),
    "032": ("外科系", "器官移植門診"), "132": ("外科系", "器官移植門診"), "232": ("外科系", "器官移植門診"),
    "0G6": ("外科系", "體重管理醫學中心"), "1G6": ("外科系", "體重管理醫學中心"),
    "0GM": ("外科系", "體重管理醫學中心"), "1GM": ("外科系", "體重管理醫學中心"),
    "0WF": ("外科系", "體重管理醫學中心"), "0WX": ("外科系", "體重管理醫學中心"),
    "059": ("外科系", "一般外科"), "159": ("外科系", "一般外科"), "259": ("外科系", "一般外科"),
    "0TT": ("外科系", "外傷兼疝氣及肝膽胃腸外科"), "2TT": ("外科系", "外傷兼疝氣及肝膽胃腸外科"),
    "073": ("外科系", "急診外傷門診"), "173": ("外科系", "急診外傷門診"), "273": ("外科系", "急診外傷門診"),
    "040": ("外科系", "手外科"), "140": ("外科系", "手外科"), "240": ("外科系", "手外科"),
    "0SS": ("外科系", "乳房疾病門診"), "1SS": ("外科系", "乳房疾病門診"),
    # 婦幼
    "082": ("婦幼", "婦產科"), "182": ("婦幼", "婦產科"), "282": ("婦幼", "婦產科"),
    "063": ("婦幼", "兒童內科"), "163": ("婦幼", "兒童內科"), "263": ("婦幼", "兒童內科"),
    "065": ("婦幼", "兒童神經癲癇"), "165": ("婦幼", "兒童神經癲癇"), "265": ("婦幼", "兒童神經癲癇"),
    "076": ("婦幼", "新生兒科暨健兒門診"), "176": ("婦幼", "新生兒科暨健兒門診"), "276": ("婦幼", "新生兒科暨健兒門診"),
    "070": ("婦幼", "兒童腸胃科"), "170": ("婦幼", "兒童腸胃科"), "270": ("婦幼", "兒童腸胃科"),
    "064": ("婦幼", "兒童心臟"), "164": ("婦幼", "兒童心臟"), "264": ("婦幼", "兒童心臟"),
    "071": ("婦幼", "兒童過敏感染"), "171": ("婦幼", "兒童過敏感染"), "271": ("婦幼", "兒童過敏感染"),
    "067": ("婦幼", "兒童免疫"), "167": ("婦幼", "兒童免疫"), "267": ("婦幼", "兒童免疫"),
    "069": ("婦幼", "兒童血液腫瘤科"), "169": ("婦幼", "兒童血液腫瘤科"), "269": ("婦幼", "兒童血液腫瘤科"),
    "075": ("婦幼", "遺傳分泌暨基因諮詢"), "175": ("婦幼", "遺傳分泌暨基因諮詢"), "275": ("婦幼", "遺傳分泌暨基因諮詢"),
    "062": ("婦幼", "兒童泌尿暨兒童外科"), "162": ("婦幼", "兒童泌尿暨兒童外科"), "262": ("婦幼", "兒童泌尿暨兒童外科"),
    "049": ("婦幼", "兒童牙科"), "149": ("婦幼", "兒童牙科"), "249": ("婦幼", "兒童牙科"),
    "0NP": ("婦幼", "兒童神經疾病"), "1NP": ("婦幼", "兒童神經疾病"),
    "TNG": ("婦幼", "青少年"),
    # 五官科
    "010": ("五官科", "眼科"), "110": ("五官科", "眼科"), "210": ("五官科", "眼科"),
    "0PK": ("五官科", "近視治療特色門診"), "1PK": ("五官科", "近視治療特色門診"),
    "0PX": ("五官科", "近視老花雷射手術自費門診"), "1PX": ("五官科", "近視老花雷射手術自費門診"),
    "052": ("五官科", "耳科"), "152": ("五官科", "耳科"), "252": ("五官科", "耳科"),
    "080": ("五官科", "鼻科"), "180": ("五官科", "鼻科"), "280": ("五官科", "鼻科"),
    "081": ("五官科", "喉科"), "181": ("五官科", "喉科"), "281": ("五官科", "喉科"),
    "009": ("五官科", "牙科"), "109": ("五官科", "牙科"), "209": ("五官科", "牙科"),
    "085": ("五官科", "矯正牙科"), "185": ("五官科", "矯正牙科"), "285": ("五官科", "矯正牙科"),
    "0K2": ("五官科", "口腔顎面外科"), "1K2": ("五官科", "口腔顎面外科"), "2K2": ("五官科", "口腔顎面外科"),
    # 其他科
    "077": ("其他科", "精神科"), "177": ("其他科", "精神科"), "277": ("其他科", "精神科"),
    "028": ("其他科", "身心失眠"), "128": ("其他科", "身心失眠"), "228": ("其他科", "身心失眠"),
    "0SW": ("其他科", "身心失眠(酒癮戒治門診)"), "1SW": ("其他科", "身心失眠(酒癮戒治門診)"),
    "015": ("其他科", "青少年心理"), "115": ("其他科", "青少年心理"), "215": ("其他科", "青少年心理"),
    "0D6": ("其他科", "失智特別門診"), "1D6": ("其他科", "失智特別門診"), "2D6": ("其他科", "失智特別門診"),
    "0G7": ("其他科", "睡眠障礙"), "1G7": ("其他科", "睡眠障礙"),
    "014": ("其他科", "老年精神"), "114": ("其他科", "老年精神"), "214": ("其他科", "老年精神"),
    "0D5": ("其他科", "自費心理諮詢"), "1D5": ("其他科", "自費心理諮詢"),
    "008": ("其他科", "皮膚科"), "108": ("其他科", "皮膚科"), "208": ("其他科", "皮膚科"),
    "083": ("其他科", "中醫內科"), "183": ("其他科", "中醫內科"), "283": ("其他科", "中醫內科"),
    "0AG": ("其他科", "中醫傷科"), "1AG": ("其他科", "中醫傷科"),
    "0AT": ("其他科", "中醫傷科"), "1AT": ("其他科", "中醫傷科"),
    "089": ("其他科", "針灸科"), "189": ("其他科", "針灸科"), "289": ("其他科", "針灸科"),
    "041": ("其他科", "復健醫學"), "141": ("其他科", "復健醫學"), "241": ("其他科", "復健醫學"),
    "0AI": ("其他科", "中西結合健檢"), "1AI": ("其他科", "中西結合健檢"),
    "017": ("其他科", "疼痛控制科"), "117": ("其他科", "疼痛控制科"), "217": ("其他科", "疼痛控制科"),
    "0SK": ("其他科", "麻醉科"), "1SK": ("其他科", "麻醉科"),
    "090": ("其他科", "放射線部診療"), "190": ("其他科", "放射線部診療"), "290": ("其他科", "放射線部診療"),
    "042": ("其他科", "放射腫瘤科"), "142": ("其他科", "放射腫瘤科"), "242": ("其他科", "放射腫瘤科"),
    "0HY": ("其他科", "重粒子治療科"), "1HY": ("其他科", "重粒子治療科"),
    "0N0": ("其他科", "核醫門診"), "1N0": ("其他科", "核醫門診"),
    "056": ("其他科", "營養諮詢"), "156": ("其他科", "營養諮詢"), "256": ("其他科", "營養諮詢"),
    "072": ("其他科", "輔具及功能重建門診"), "172": ("其他科", "輔具及功能重建門診"), "272": ("其他科", "輔具及功能重建門診"),
    "022": ("其他科", "急診內科門診"), "122": ("其他科", "急診內科門診"), "222": ("其他科", "急診內科門診"),
    "0XD": ("其他科", "國際醫療門診"), "1XD": ("其他科", "國際醫療門診"), "2XD": ("其他科", "國際醫療門診"),
    "0G2": ("其他科", "藥師門診"), "1G2": ("其他科", "藥師門診"),
    "0G3": ("其他科", "藥師門診"), "1G3": ("其他科", "藥師門診"),
    "LDC": ("其他科", "肺癌篩檢門診"),
    # 大我門診
    "092": ("大我門診", "大我內科"), "093": ("大我門診", "大我外科"),
    "094": ("大我門診", "大我家醫科"), "095": ("大我門診", "大我眼科"),
    "096": ("大我門診", "大我皮膚科"), "097": ("大我門診", "大外耳鼻喉科"),
    "098": ("大我門診", "大我高齡門診"),
    # 整合門診
    "0JA": ("整合門診", "早發脊柱側彎整合門診"),
    "0IT": ("整合門診", "腦性麻痺整合門診"),
    "0IH": ("整合門診", "兒童脊髓整合門診"),
    "1NR": ("整合門診", "高風險新生兒復健整合"),
    "0JK": ("整合門診", "兒癌長期追蹤整合"),
    "EAR": ("整合門診", "早療評估整合門診"),
    # AI輔助門診
    "0AI": ("AI輔助門診", "AI輔助門診"),
}

CAT_FALLBACK = {
    "內科系":                       "內科",
    "外科系":                       "外科系",
    "婦幼 (18歲以下請掛兒科門診)": "婦幼",
    "五官科":                       "五官科",
    "其他科":                       "其他科",
    "大我門診 (和平東路三段599號)": "大我門診",
    "整合門診":                     "整合門診",
    "AI輔助門診":                   "AI輔助門診",
}

# 神經內科細項 -> 也屬於神經內科主科
NEUROLOGY_SUBS = {
    "神經內科(動作障礙特診)",
    "神經內科(記憶特別門診)",
    "神經內科(神經遺傳疾病諮詢門診)",
}

def convert_to_app_format(doctor_map, hier_subs=None, hier_cat=None):
    """
    將爬蟲輸出的 doctor_map 轉換成 app 科別格式（去除 sec）
    hier_subs: hierarchy 的所有合法子科別 set
    hier_cat:  子科別 -> 父科別 dict（確保 category 正確）
    """
    converted = {}
    for doc_id, info in doctor_map.items():
        seen = set()
        new_depts = []
        for dept in info["departments"]:
            dept_name = dept["dept_name"]
            category  = dept["category"]

            # 如果 dept_name 已經是 hierarchy 的合法子科別，直接用
            # 且用 hier_cat 取正確的 category
            if hier_subs and dept_name in hier_subs:
                correct_cat = hier_cat.get(dept_name, category) if hier_cat else category
                mapped = (correct_cat, dept_name)
            else:
                # fallback：用 sec 對應
                sec_raw = dept.get("sec", "")
                secs = sec_raw.split("-") if sec_raw else []
                mapped = None
                for s in secs:
                    if s in SEC_TO_APP_DEPT:
                        mapped = SEC_TO_APP_DEPT[s]
                        break
                if not mapped:
                    cat = CAT_FALLBACK.get(category, category)
                    mapped = (cat, dept_name)

            if mapped not in seen:
                seen.add(mapped)
                new_depts.append({"category": mapped[0], "dept_name": mapped[1]})

            # 神經內科細項的醫師也屬於神經內科主科
            if mapped[1] in NEUROLOGY_SUBS:
                main = ("內科", "神經內科")
                if main not in seen:
                    seen.add(main)
                    new_depts.append({"category": main[0], "dept_name": main[1]})

        converted[doc_id] = {
            "name":           info["name"],
            "is_placeholder": info.get("is_placeholder", False),
            "departments":    new_depts,
        }
    return converted

# ─── DB 連線設定 ──────────────────────────────────────────────────────────────
import os

DB_CONFIG = {
    "server":   os.environ.get("MEDICHAIN_DB_SERVER", "100.64.116.35,1433"),
    "database": os.environ.get("MEDICHAIN_DB_NAME", "MediChainDB"),
    "username": os.environ.get("MEDICHAIN_DB_USER", "sa"),
    "password": os.environ.get("MEDICHAIN_DB_PASSWORD"),
}

def get_conn():
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']};"
        f"Encrypt=no;"
        f"TrustServerCertificate=yes;"
        f"Connection Timeout=30;"
    )
    import pyodbc
    return pyodbc.connect(conn_str)


def upsert_to_db(doctor_map):
    """將醫師資料 upsert 進 MediChainDB"""
    conn   = get_conn()
    cursor = conn.cursor()

    # ── Step 1: 建立 category_id 對照 ──
    category_ids = {}
    for info in doctor_map.values():
        for dept in info["departments"]:
            cat = dept["category"]
            if cat not in category_ids:
                cursor.execute("""
                    IF NOT EXISTS (SELECT 1 FROM DepartmentCategory WHERE name = ?)
                        INSERT INTO DepartmentCategory (name) VALUES (?)
                """, cat, cat)
                cursor.execute("SELECT category_id FROM DepartmentCategory WHERE name = ?", cat)
                category_ids[cat] = cursor.fetchone()[0]

    conn.commit()
    log.info("DepartmentCategory upsert 完成，共 %d 筆", len(category_ids))

    # ── Step 2: 建立 dept_id 對照 ──
    dept_ids = {}
    for info in doctor_map.values():
        for dept in info["departments"]:
            cat      = dept["category"]
            dept_name = dept["dept_name"]
            key = (cat, dept_name)
            if key not in dept_ids:
                cat_id = category_ids[cat]
                cursor.execute("""
                    IF NOT EXISTS (
                        SELECT 1 FROM Department WHERE category_id = ? AND name = ?
                    )
                    INSERT INTO Department (category_id, name) VALUES (?, ?)
                """, cat_id, dept_name, cat_id, dept_name)
                cursor.execute(
                    "SELECT dept_id FROM Department WHERE category_id = ? AND name = ?",
                    cat_id, dept_name
                )
                dept_ids[key] = cursor.fetchone()[0]

    conn.commit()
    log.info("Department upsert 完成，共 %d 筆", len(dept_ids))

    # ── Step 3: 先把所有醫師標成 is_active=0，之後爬到的再標回 1 ──
    cursor.execute("UPDATE Doctor SET is_active = 0")
    conn.commit()

    # ── Step 4: upsert Doctor ──
    doctor_ids = {}
    for vgh_code, info in doctor_map.items():
        # 跳過代診醫師假 ID
        if vgh_code.startswith("DOC_TEMP_"):
            continue

        is_ph = 1 if info.get("is_placeholder") else 0

        # 先確認是否存在
        cursor.execute("SELECT doctor_id FROM Doctor WHERE vgh_code = ?", vgh_code)
        row = cursor.fetchone()

        if row:
            doctor_ids[vgh_code] = row[0]
            cursor.execute("""
                UPDATE Doctor
                SET name = ?, is_placeholder = ?, is_active = 1, updated_at = GETDATE()
                WHERE vgh_code = ?
            """, info["name"], is_ph, vgh_code)
        else:
            cursor.execute("""
                INSERT INTO Doctor (vgh_code, name, is_placeholder, is_active, updated_at)
                OUTPUT INSERTED.doctor_id
                VALUES (?, ?, ?, 1, GETDATE())
            """, vgh_code, info["name"], is_ph)
            inserted = cursor.fetchone()
            doctor_ids[vgh_code] = inserted[0]

    conn.commit()
    log.info("Doctor upsert 完成，共 %d 筆", len(doctor_ids))

    # ── Step 5: 清空 DoctorDepartment 重新寫入 ──
    cursor.execute("DELETE FROM DoctorDepartment")

    for vgh_code, info in doctor_map.items():
        if vgh_code.startswith("DOC_TEMP_"):
            continue
        doc_id = doctor_ids[vgh_code]
        for dept in info["departments"]:
            key     = (dept["category"], dept["dept_name"])
            dept_id = dept_ids.get(key)
            if dept_id:
                cursor.execute("""
                    IF NOT EXISTS (
                        SELECT 1 FROM DoctorDepartment
                        WHERE doctor_id = ? AND dept_id = ?
                    )
                    INSERT INTO DoctorDepartment (doctor_id, dept_id)
                    VALUES (?, ?)
                """, doc_id, dept_id, doc_id, dept_id)

    conn.commit()
    log.info("DoctorDepartment 寫入完成")
    cursor.close()
    conn.close()
    log.info("DB 寫入全部完成")


def main():
    parser = argparse.ArgumentParser(description="台北榮總醫師科別爬蟲")
    parser.add_argument("--output", default="vghtpe_doctors.json", help="輸出 JSON 檔名")
    parser.add_argument("--delay",  type=float, default=0.2,        help="請求間隔秒數")
    parser.add_argument("--test",   action="store_true",             help="測試模式，只跑前5個科別")
    parser.add_argument("--no-db",  action="store_true",             help="不寫入DB，只輸出JSON方便檢查")
    args = parser.parse_args()

    DELAY = args.delay
    sess  = make_session()

    # 載入 dept_full_hierarchy.json 建立標籤對照
    tag_to_dept = {}
    tag_to_cat  = {}
    try:
        with open("dept_full_hierarchy.json", encoding="utf-8") as f:
            hier = json.load(f)
        for cat, subs in hier.items():
            for sub, details in subs.items():
                tag_to_cat[sub] = cat
                tag_to_dept[sub] = sub
                for detail in details:
                    if detail not in tag_to_dept:
                        tag_to_dept[detail] = sub
        log.info("載入 hierarchy：%d 個標籤對照", len(tag_to_dept))
    except FileNotFoundError:
        log.warning("找不到 dept_full_hierarchy.json，將使用 sec 決定科別")

    log.info("暖機中...")
    get_html(sess, BASE_URL + "/home.do")
    time.sleep(DELAY)

    log.info("抓取科別列表（複診）...")
    sect_html_return = get_html(sess, SECT_URL_RETURN)
    if not sect_html_return:
        log.error("無法取得複診科別列表，程式終止。")
        return
    departments_return = parse_sect_list(sect_html_return, visit_type="return")

    time.sleep(DELAY)

    log.info("抓取科別列表（初診）...")
    sect_html_first = get_html(sess, SECT_URL_FIRST)
    if not sect_html_first:
        log.warning("無法取得初診科別列表，僅使用複診列表繼續")
        departments_first = []
    else:
        departments_first = parse_sect_list(sect_html_first, visit_type="first")

    # 合併去重：以 sec 為 key，複診優先，初診補上複診沒有的 sec
    seen_secs = set()
    departments = []
    for d in departments_return:
        if d["sec"] not in seen_secs:
            seen_secs.add(d["sec"])
            departments.append(d)
    added_from_first = 0
    first_only_secs = []
    for d in departments_first:
        if d["sec"] not in seen_secs:
            seen_secs.add(d["sec"])
            departments.append(d)
            added_from_first += 1
            first_only_secs.append(d)
    log.info("複診科別 %d 個，初診額外補上 %d 個新 sec，合計 %d 個科別",
              len(departments_return), added_from_first, len(departments))

    # 診斷：列出這些「只在初診出現」的 sec，並標註是否已有 app 科別名稱對應
    if first_only_secs:
        print("\n=== 初診新增科別診斷（寫入 DB 前請先檢查名稱是否與現有 Department 一致）===")
        for d in first_only_secs:
            secs = d["sec"].split("-") if "-" in d["sec"] else [d["sec"]]
            mapped_names = [SEC_TO_APP_DEPT[s] for s in secs if s in SEC_TO_APP_DEPT]
            if mapped_names:
                print(f"  sec={d['sec']:<10} 網站顯示=\"{d['dept_name']}\"  -> SEC_TO_APP_DEPT 已對應: {mapped_names}")
            else:
                print(f"  sec={d['sec']:<10} 網站顯示=\"{d['dept_name']}\"  -> ⚠ 尚未在 SEC_TO_APP_DEPT 對應，將直接沿用網站原始名稱")
        print()

    if not departments:
        log.error("科別列表解析失敗。")
        return

    dept_doctors = []

    if args.test:
        departments = departments[:35]
        log.info("測試模式：只跑前 %d 個科別", len(departments))

    total = len(departments)

    for i, dept in enumerate(departments, 1):
        log.info("[%d/%d] %s > %s", i, total, dept["category"], dept["dept_name"])
        doctors = scrape_department(sess, dept, DELAY, tag_to_dept=tag_to_dept)
        log.info("  -> 找到 %d 位醫師", len(doctors))
        dept_doctors.append({
            "category":  dept["category"],
            "dept_name": dept["dept_name"],
            "sec":       dept["sec"],
            "doctors":   doctors,
        })

    doctor_map = build_doctor_map(dept_doctors, tag_to_dept=tag_to_dept, tag_to_cat=tag_to_cat)
    log.info("共找到 %d 位不重複醫師", len(doctor_map))

    # 轉換成 app 科別格式
    # 建立 hierarchy 合法子科別 set
    hier_subs = set()
    hier_cat  = {}  # 子科別 -> 父科別
    try:
        with open("dept_full_hierarchy.json", encoding="utf-8") as _f:
            _hier = json.load(_f)
        for _cat, _subs in _hier.items():
            for _sub in _subs.keys():
                hier_subs.add(_sub)
                hier_cat[_sub] = _cat
    except FileNotFoundError:
        pass

    doctor_map = convert_to_app_format(doctor_map, hier_subs=hier_subs, hier_cat=hier_cat)
    log.info("已轉換為 app 科別格式")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(doctor_map, f, ensure_ascii=False, indent=2)
    log.info("已儲存至 %s", args.output)

    # 寫入 DB
    if args.no_db:
        log.info("--no-db 模式：略過寫入 MediChainDB，僅輸出 JSON 供檢查")
    else:
        log.info("開始寫入 MediChainDB...")
        try:
            upsert_to_db(doctor_map)
        except Exception as e:
            import traceback
            log.error("DB 寫入失敗：%s", e)
            log.error(traceback.format_exc())
            log.info("JSON 已儲存，可手動處理 DB")

    print("\n=== 執行結果 ===")
    print("科別數量：", total)
    print("醫師數量：", len(doctor_map))
    print("輸出檔案：", args.output)

    print("\n前三筆範例：")
    for doc_id, info in list(doctor_map.items())[:3]:
        depts = "、".join(d["dept_name"] for d in info["departments"])
        print("  " + doc_id + "  " + info["name"] + "  ->  " + depts)


if __name__ == "__main__":
    main()


