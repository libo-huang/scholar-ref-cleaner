import streamlit as st
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
import requests
from thefuzz import fuzz
import time
import docx
import io

# --- 页面配置 ---
st.set_page_config(page_title="AI文献幻觉检测与清洗", page_icon="🧹", layout="wide")

st.title("🧹 Scholar Ref Cleaner (Based on Semantic Scholar)")
st.markdown("""
**专治 AI 生成的“幻觉”参考文献。** 上传 BibTeX 或 Word 文件，本工具将调用 Semantic Scholar 官方数据库进行核对：
1. **验证真伪**：检测文献是否存在。
2. **自动修正**：修正错误的年份、作者和期刊名。
3. **输出报告**：下载清洗后的干净数据。
""")

# --- 核心函数：调用 Semantic Scholar API ---
def search_semantic_scholar(query_title):
    """在 Semantic Scholar 中搜索论文"""
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query_title,
        "limit": 1,
        "fields": "title,authors,year,venue,externalIds,url,citationCount"
    }
    try:
        # 注意：未申请 API Key 限制每秒 1 次请求，这里加延迟防止封禁
        time.sleep(1.1) 
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['total'] > 0:
                return data['data'][0]
    except Exception as e:
        return None
    return None

def process_bib_entry(entry):
    """处理单个 Bib 条目"""
    original_title = entry.get('title', '').replace('{', '').replace('}', '').replace('\n', ' ')
    if not original_title:
        return entry, "跳过 (无标题)", 0

    # 搜索
    paper = search_semantic_scholar(original_title)
    
    if not paper:
        entry['note'] = "⚠️ NOT FOUND / HALLUCINATION"
        return entry, "❌ 未找到 (可能是幻觉)", 0

    # 比对标题相似度
    real_title = paper.get('title', '')
    similarity = fuzz.ratio(original_title.lower(), real_title.lower())

    status = ""
    if similarity > 85:
        # 匹配成功，覆盖数据
        entry['title'] = real_title
        entry['year'] = str(paper.get('year', entry.get('year', '')))
        
        # 处理作者
        if 'authors' in paper and paper['authors']:
            author_list = [a['name'] for a in paper['authors']]
            entry['author'] = " and ".join(author_list)
        
        # 处理期刊/会议
        if 'venue' in paper and paper['venue']:
            entry['journal'] = paper['venue']
        
        entry['note'] = "✅ Verified"
        status = f"✅ 已修正 (相似度 {similarity}%)"
    else:
        # 相似度过低，标记警告
        entry['note'] = f"❓ Low Confidence (Match: {real_title})"
        status = f"⚠️ 存疑 (搜到的标题差异大: {real_title})"

    return entry, status, similarity

# --- 侧边栏：使用说明 ---
with st.sidebar:
    st.header("使用指南")
    st.info("""
    1. **BibTeX 模式(推荐)**：
       上传 .bib 文件，输出标准的 .bib 文件，可直接导入 LaTeX/Zotero。
    2. **Word 模式(实验性)**：
       上传 .docx 文件，仅读取其中的文本行进行搜索，输出验证结果文本。
    """)
    st.warning("注意：Semantic Scholar 免费版 API 速度较慢，请耐心等待。")

# --- 主界面逻辑 ---
tab1, tab2 = st.tabs(["BibTeX 文件处理", "Word/文本处理"])

# === TAB 1: BibTeX 处理 ===
with tab1:
    uploaded_file = st.file_uploader("上传 .bib 文件", type="bib")
    
    if uploaded_file is not None:
        # 读取文件
        bib_database = bibtexparser.load(uploaded_file)
        st.write(f"识别到 {len(bib_database.entries)} 条文献，点击下方按钮开始清洗。")
        
        if st.button("开始清洗 (BibTeX)", key="btn_bib"):
            progress_bar = st.progress(0)
            log_area = st.empty()
            
            cleaned_entries = []
            results_data = []

            for i, entry in enumerate(bib_database.entries):
                # 更新进度
                progress_bar.progress((i + 1) / len(bib_database.entries))
                
                # 处理
                title_preview = entry.get('title', 'Unknown')[:30] + "..."
                log_area.text(f"正在处理 [{i+1}/{len(bib_database.entries)}]: {title_preview}")
                
                new_entry, status, score = process_bib_entry(entry)
                cleaned_entries.append(new_entry)
                
                results_data.append({
                    "原标题": entry.get('title'),
                    "状态": status,
                    "修正后年份": new_entry.get('year')
                })

            # 完成处理
            st.success("清洗完成！")
            
            # 展示简报
            st.dataframe(results_data)
            
            # 生成下载
            db = BibDatabase()
            db.entries = cleaned_entries
            writer = BibTexWriter()
            cleaned_bib_str = writer.write(db)
            
            st.download_button(
                label="📥 下载清洗后的 .bib 文件",
                data=cleaned_bib_str,
                file_name="cleaned_references.bib",
                mime="text/plain"
            )

# === TAB 2: Word/文本 处理 ===
with tab2:
    st.markdown("由于 Word 格式复杂，本功能**仅读取文档中的每一段文字**作为标题去搜索，无法直接生成完美格式的 Word，但可以帮你**排查假文献**。")
    uploaded_word = st.file_uploader("上传 .docx 文件", type="docx")
    
    if uploaded_word is not None:
        if st.button("开始验证 (Word)", key="btn_word"):
            doc = docx.Document(uploaded_word)
            full_text = []
            for para in doc.paragraphs:
                if len(para.text) > 20: # 忽略太短的行
                    full_text.append(para.text)
            
            st.write(f"提取到 {len(full_text)} 个可能的引用段落。")
            
            results_txt = "=== 文献验证报告 ===\n\n"
            progress_bar = st.progress(0)
            
            for i, line in enumerate(full_text):
                progress_bar.progress((i + 1) / len(full_text))
                
                # 假设这一行就是包含标题的引用
                # 简单清洗：去掉前面的 [1] 之类的
                clean_line = line.split(']')[-1].strip() if ']' in line else line
                # 截取大概的标题位置（这里比较粗糙，依赖 Semantic Scholar 的强搜索能力）
                
                paper = search_semantic_scholar(clean_line)
                
                if paper:
                    score = fuzz.token_set_ratio(clean_line, paper['title'])
                    if score > 80:
                         results_txt += f"[✅ 真] 原文: {line[:50]}...\n      -> 匹配: {paper['title']} ({paper['year']})\n\n"
                    else:
                         results_txt += f"[⚠️ 存疑] 原文: {line[:50]}...\n      -> 搜到最接近: {paper['title']} (相似度低)\n\n"
                else:
                    results_txt += f"[❌ 幻觉/未找到] {line}\n\n"
            
            st.text_area("验证报告", results_txt, height=300)
            st.download_button(
                label="📥 下载验证报告 (.txt)",
                data=results_txt,
                file_name="verification_report.txt",
                mime="text/plain"
            )
