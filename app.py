import streamlit as st
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
import requests
from thefuzz import fuzz
from scholarly import scholarly, ProxyGenerator
import time
import docx
import random

# --- 页面配置 ---
st.set_page_config(page_title="超级文献清洗机 (GS优先版)", page_icon="🧬", layout="wide")

st.title("🧬 Scholar Ref Cleaner (Multi-Source)")
st.markdown("""
**多源融合清洗策略：**
1. 🥇 **Google Scholar**: 优先尝试（数据最准，但易被云端封锁）。
2. 🥈 **Semantic Scholar**: 自动降级备选（速度快，API稳定）。
3. 🥉 **Crossref**: 最终兜底（全球最大DOI数据库）。
""")

# --- 核心搜索模块 ---

def search_google_scholar(query_title):
    """策略1：尝试 Google Scholar"""
    try:
        # 随机休眠模拟人类，防止秒封（但在云端依然很难存活）
        time.sleep(random.uniform(1, 3)) 
        
        search_query = scholarly.search_pubs(query_title)
        # 获取第一个结果，如果无结果会抛出 StopIteration
        result = next(search_query) 
        
        # 格式化数据以统一标准
        bib = result['bib']
        return {
            'title': bib.get('title'),
            'year': bib.get('pub_year'),
            'author': " and ".join(bib.get('author', [])),
            'journal': bib.get('venue'),
            'source': 'Google Scholar'
        }
    except StopIteration:
        return None # 没搜到
    except Exception as e:
        # 包含网络错误、验证码拦截等所有异常
        print(f"Google Scholar Failed: {e}") 
        return None

def search_semantic_scholar(query_title):
    """策略2：尝试 Semantic Scholar"""
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query_title,
        "limit": 1,
        "fields": "title,authors,year,venue"
    }
    try:
        # 避免触发 API 速率限制
        time.sleep(1.0) 
        response = requests.get(base_url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data['total'] > 0:
                paper = data['data'][0]
                # 格式化
                authors = [a['name'] for a in paper.get('authors', [])]
                return {
                    'title': paper.get('title'),
                    'year': paper.get('year'),
                    'author': " and ".join(authors),
                    'journal': paper.get('venue'),
                    'source': 'Semantic Scholar'
                }
    except Exception:
        return None
    return None

def search_crossref(query_title):
    """策略3：尝试 Crossref (兜底)"""
    base_url = "https://api.crossref.org/works"
    params = {
        "query.bibliographic": query_title,
        "rows": 1
    }
    try:
        response = requests.get(base_url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            items = data['message']['items']
            if items:
                paper = items[0]
                # 格式化
                title_list = paper.get('title', [])
                title = title_list[0] if title_list else ""
                
                # Crossref的时间格式比较复杂
                year = ""
                if 'published-print' in paper:
                    year = paper['published-print']['date-parts'][0][0]
                elif 'created' in paper:
                    year = paper['created']['date-parts'][0][0]
                
                authors = []
                if 'author' in paper:
                    for a in paper['author']:
                        authors.append(f"{a.get('given','')} {a.get('family','')}")
                
                container = paper.get('container-title', [])
                journal = container[0] if container else ""

                return {
                    'title': title,
                    'year': str(year),
                    'author': " and ".join(authors),
                    'journal': journal,
                    'source': 'Crossref'
                }
    except Exception:
        return None
    return None

def waterfall_search(query_title):
    """瀑布流调度器"""
    # 1. 优先 Google
    res = search_google_scholar(query_title)
    if res: return res
    
    # 2. 失败则 Semantic
    res = search_semantic_scholar(query_title)
    if res: return res
    
    # 3. 失败则 Crossref
    res = search_crossref(query_title)
    if res: return res
    
    return None

def process_bib_entry(entry):
    """处理单个 Bib 条目"""
    original_title = entry.get('title', '').replace('{', '').replace('}', '').replace('\n', ' ')
    if not original_title:
        return entry, "跳过 (无标题)", 0, "None"

    # 执行瀑布流搜索
    paper = waterfall_search(original_title)
    
    if not paper:
        entry['note'] = "⚠️ NOT FOUND / HALLUCINATION"
        return entry, "❌ 未找到 (可能是幻觉)", 0, "None"

    # 比对
    real_title = paper.get('title', '')
    similarity = fuzz.ratio(original_title.lower(), real_title.lower())
    source_used = paper.get('source', 'Unknown')

    status = ""
    if similarity > 80: # 稍微放宽阈值，因为不同数据库标点不同
        entry['title'] = real_title
        if paper.get('year'): entry['year'] = str(paper['year'])
        if paper.get('author'): entry['author'] = paper['author']
        if paper.get('journal'): entry['journal'] = paper['journal']
        
        entry['note'] = f"Verified by {source_used}"
        status = f"✅ 已修正 (源: {source_used})"
    else:
        entry['note'] = f"❓ Low Confidence (Match: {real_title})"
        status = f"⚠️ 存疑 (源: {source_used}, 差异大)"

    return entry, status, similarity, source_used

# --- 界面逻辑 ---
uploaded_file = st.file_uploader("上传 .bib 文件", type="bib")

if uploaded_file is not None:
    bib_database = bibtexparser.load(uploaded_file)
    if st.button("开始多源清洗"):
        progress_bar = st.progress(0)
        log_area = st.empty()
        cleaned_entries = []
        results_data = []

        for i, entry in enumerate(bib_database.entries):
            progress_bar.progress((i + 1) / len(bib_database.entries))
            log_area.text(f"正在处理 [{i+1}/{len(bib_database.entries)}] - 正在轮询各大数据库...")
            
            new_entry, status, score, source = process_bib_entry(entry)
            cleaned_entries.append(new_entry)
            
            results_data.append({
                "原标题": entry.get('title')[:30]+"...",
                "状态": status,
                "数据源": source,
                "修正年份": new_entry.get('year')
            })

        st.success("处理完成！")
        st.dataframe(results_data)
        
        db = BibDatabase()
        db.entries = cleaned_entries
        writer = BibTexWriter()
        st.download_button("📥 下载清洗后的 .bib", writer.write(db), "cleaned.bib")
