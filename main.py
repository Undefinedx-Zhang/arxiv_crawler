import arxiv, datetime, re
import pathlib, datetime, tqdm
import re
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from config import LLM_KEYWORDS, TOP_VENUES, TOP_INSTITUTES


def fetch_recent_papers(days=7, max_results=100):
    """
    获取最近 N 天内发布的文章。
    """
    today = datetime.datetime.utcnow().date()
    start_date = today - datetime.timedelta(days=days)
    
    print(f"Fetching papers from {start_date} to {today}")

    query = "cat:cs.CL OR cat:cs.AI OR cat:stat.ML"
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    results = []
    client = arxiv.Client()
    for result in client.results(search):
        # arxiv.Result.published 是 datetime 类型
        # 筛选出发布日期在指定范围内（大于等于开始日期）的文章
        if result.published.date() >= start_date:
            results.append(result)
    return results

def is_llm_related(text):
    text_lower = text.lower()
    return any(k.lower() in text_lower for k in LLM_KEYWORDS)


def match_venue(comment: str) -> str | None:
    if not comment: return None
    for v in TOP_VENUES:
        if re.search(rf"\b{v}\b", comment, flags=re.I):
            return v
    return None

def match_institute(authors) -> str | None:
    # arxiv 元数据通常不含 affiliation，需在 author.name 中做弱匹配
    for a in authors:
        for inst in TOP_INSTITUTES:
            if inst.lower() in a.name.lower():
                return inst
    return None

def multi_filter(item):
    """
    返回 (bool pass, dict extra)
    """
    # 是否为顶级会议
    venue = match_venue(item.comment or "")
    # 是否为顶级机构
    institute = match_institute(item.authors)
    # 是否为顶级会议或顶级机构
    if venue or institute:
        return True, {"venue": venue, "institute": institute}
    return False, {}



def arxiv_to_bib(result):
    db = BibDatabase()
    entry_key = result.entry_id.split('/')[-1]
    first_author = result.authors[0].name
    year = result.published.year
    entry = {
        "ENTRYTYPE": "article",
        "ID": entry_key,
        "title": f"{{{result.title.strip()}}}",
        "author": " and ".join(a.name for a in result.authors),
        "year": str(year),
        "eprint": entry_key,
        "archivePrefix": "arXiv",
        "primaryClass": result.primary_category
    }
    db.entries = [entry]
    return BibTexWriter().write(db)



def run():
    today = datetime.datetime.utcnow().strftime("%Y%m%d")
    bib_path = pathlib.Path(f"daily_{today}.bib")
    md_path  = pathlib.Path(f"daily_{today}.md")

    papers = fetch_recent_papers(days=7)
    kept, md_lines, bib_strings = [], [], []

    for p in tqdm.tqdm(papers):
        #论文是否与LLM相关（关键词筛选）
        if not is_llm_related(p.title + p.summary):
            continue
        #论文是否在顶会/顶刊上（venue筛选）
        passed, extra = multi_filter(p)
        if not passed:
            continue

        venue = extra.get("venue") or "N/A"
        institute = extra.get("institute") or "N/A"
        print(p)
        first_author = p.authors[0].name
        md_lines.append(
            f"- **{p.title.strip()}**  \n"
            f"  作者: {', '.join(a.name for a in p.authors)}  \n"
            f"  会议/期刊: {venue}  \n"
            f"  第一单位: {institute}  \n"
            f"  arXiv: {p.entry_id}  \n"
        )
        bib_strings.append(arxiv_to_bib(p))

    bib_path.write_text("\n\n".join(bib_strings), encoding="utf-8")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Saved {len(md_lines)} papers.")

if __name__ == "__main__":
    run()
    print("done")