import streamlit as st
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
import requests
from scholarly import scholarly, ProxyGenerator
from thefuzz import fuzz
import time
import docx
import random

# --- 页面配置 ---
st.set_page_config(page_title="AI文献强力清洗机 (GS优先版)", page_icon="🧬", layout="wide")

st.title("🧬 Scholar Ref Cleaner (Google Scholar First)")
st.markdown("""
**策略逻辑**：
1. 🥇 **优先尝试 Google Scholar** (权威，但容易触发验证码/封锁)。
2. 🥈 **自动降级 Semantic Scholar** (若 Google 失败或被封，自动切换此源，速度快且稳定)。
3. 🥉 **自动比对与清洗** (修正年份、作者、期刊)。

*注：部署在云端服务器时，Google Scholar 极易触发反爬机制，此时会自动切换到 Semantic Scholar。*
""")

# --- 全局变量 ---
# 用于记录 Google Scholar 是否已经挂了，如果挂了后续直接跳过，节省时间
if 'gs_blocked' not in st.session_state:
    st.session_state.gs_blocked = False

# --- 核心函数：Google Scholar ---
def search_google_scholar(query_title):
    """
    尝试从 Google Scholar 获取数据
    返回: (paper_data_dict, success_bool)
    """
    if st.session_state.gs_blocked:
        return None, False

    try:
        # 随机休眠，降低封号风险
        time.sleep(random.uniform(1.0, 3.0))
        
        # 搜索
        search_query = scholarly.search_pubs(query_title)
        paper = next(search_query) # 获取第一个结果，如果没有会抛出 StopIteration
        
        # 提取数据 (Scholarly 返回的格式比较深，需要提取)
        bib = paper.get('bib', {})
        
        # 简单的格式标准化
        result = {
            'title': bib.get('title'),
            'year': bib.get('pub_year'),
            'author': " and ".join(bib.get('author', [])), # GS返回的是列表，转为BibTeX字符串
            'journal': bib.get('venue'),
            'url': paper.get('pub_url'),
            'source': 'Google Scholar 🟢'
        }
        return result, True

    except StopIteration:
        # 没搜到
        return None, False
    except Exception as e:
        # 遇到验证码、网络错误等
        # print(f"GS Error: {e}") # 调试用
        return None, False

# --- 核心函数：Semantic Scholar ---
def search_semantic_scholar(query_title):
    """
    作为备用数据源
    """
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query_title,
        "limit": 1,
        "fields": "title,authors,year,venue,externalIds,url"
    }
    try:
        # 避免 API 速率限制
        time.sleep(0.5) 
        response = requests.get(base_url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data['total'] > 0:
                item = data['data'][0]
                
                # 格式标准化
                author_list = [a['name'] for a in item.get('authors', [])]
                result = {
                    'title': item.get('title'),
                    'year': item.get('year'),
                    'author': " and ".join(author_list),
                    'journal': item.get('venue'),
                    'url': item.get('url'),
                    'source': 'Semantic Scholar 🔵'
                }
                return result, True
    except Exception as e:
        return None, False
    return None, False

# --- 统一调度函数 ---
def unified_search(query_title):
    """
    级联搜索：GS -> SS
    """
    # 1. 尝试 Google Scholar
    if not st.session_state.gs_blocked:
        res, found = search_google_scholar(query_title)
        if found:
            return res
        else:
            # 如果没找到，或者是被封了导致没结果，这里无法精确区分
            # 为了稳健，只要 GS 没返回有效数据，就去 SS 查
            pass
    
    # 2. 尝试 Semantic Scholar (Fallback)
    res, found = search_semantic_scholar(query_title)
    if found:
        return res
        
    return None

# --- 处理逻辑 ---
def process_bib_entry(entry):
    original_title = entry.get('title', '').replace('{', '').replace('}', '').replace('\n', ' ')
    if not original_title:
        return entry, "跳过 (无标题)", 0, "None"

    # 调用统一搜索
    paper = unified_search(original_title)
    
    if not paper:
        entry['note'] = "⚠️ NOT FOUND / HALLUCINATION"
        return entry, "❌ 未找到 (可能是幻觉)", 0, "None"

    # 比对标题相似度
    real_title = paper.get('title', '')
    similarity = fuzz.ratio(original_title.lower(), real_title.lower())

    status = ""
    source_tag = paper['source']
    
    if similarity > 80:
        # 匹配成功，覆盖数据
        entry['title'] = real_title
        if paper.get('year'): entry['year'] = str(paper['year'])
        if paper.get('author'): entry['author'] = paper['author']
        if paper.get('journal'): entry['journal'] = paper['journal']
        
        entry['note'] = f"Verified by {paper['source']}"
        status = f"✅ 已修正 ({similarity}%)"
    else:
        entry['note'] = f"❓ Low Confidence (Match: {real_title})"
        status = f"⚠️ 存疑 (差异大: {real_title})"

    return entry, status, similarity, source_tag

# --- 界面逻辑 ---

tab1, tab2 = st.tabs(["BibTeX 文件处理", "Word/文本处理"])

# === TAB 1: BibTeX ===
with tab1:
    uploaded_file = st.file_uploader("上传 .bib 文件", type="bib")
    
    if uploaded_file is not None:
        bib_database = bibtexparser.load(uploaded_file)
        st.info(f"共加载 {len(bib_database.entries)} 条文献。如果文献较多，Google Scholar 可能会变慢。")
        
        if st.button("开始清洗 (BibTeX)", key="btn_bib"):
            progress_bar = st.progress(0)
            log_area = st.empty()
            
            cleaned_entries = []
            results_data = []

            for i, entry in enumerate(bib_database.entries):
                progress_bar.progress((i + 1) / len(bib_database.entries))
                
                title_preview = entry.get('title', 'Unknown')[:30] + "..."
                log_area.text(f"处理中 [{i+1}/{len(bib_database.entries)}]: {title_preview}")
                
                new_entry, status, score, source = process_bib_entry(entry)
                cleaned_entries.append(new_entry)
                
                results_data.append({
                    "原标题": entry.get('title')[:30]+"...",
                    "数据源": source,
                    "状态": status,
                    "修正年份": new_entry.get('year')
                })

            st.success("处理完成！请查看下方列表确认数据源。")
            st.dataframe(results_data)
            
            db = BibDatabase()
            db.entries = cleaned_entries
            writer = BibTexWriter()
            cleaned_bib_str = writer.write(db)
            
            st.download_button("📥 下载清洗后的 .bib", cleaned_bib_str, "cleaned_gs_priority.bib")

# === TAB 2: Word/Text ===
with tab2:
    st.markdown("上传 Word 文档，将逐行提取文本，优先去 Google Scholar 验证是否存在。")
    uploaded_word = st.file_uploader("上传 .docx 文件", type="docx")
    
    if uploaded_word is not None:
        if st.button("开始验证 (Word)", key="btn_word"):
            doc = docx.Document(uploaded_word)
            full_text = [p.text for p in doc.paragraphs if len(p.text) > 20]
            
            st.write(f"提取到 {len(full_text)} 个段落，开始验证...")
            
            report_lines = []
            progress_bar = st.progress(0)
            
            for i, line in enumerate(full_text):
                progress_bar.progress((i + 1) / len(full_text))
                
                # 简单清洗
                clean_line = line.split(']')[-1].strip() if ']' in line else line
                
                paper = unified_search(clean_line)
                
                report_lines.append(f"原文: {line[:60]}...")
                if paper:
                    score = fuzz.token_set_ratio(clean_line, paper['title'])
                    if score > 80:
                         report_lines.append(f"   [{paper['source']}] ✅ 匹配: {paper['title']} ({paper.get('year')})")
                    else:
                         report_lines.append(f"   [{paper['source']}] ⚠️ 存疑: {paper['title']}")
                else:
                    report_lines.append("   [❌] 未找到/幻觉")
                report_lines.append("-" * 30)
            
            result_text = "\n".join(report_lines)
            st.text_area("验证报告", result_text, height=400)
            st.download_button("📥 下载报告", result_text, "verification_report.txt")
