# 🎓 Scholar Ref Cleaner

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://scholar-rc.streamlit.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

> **Stop citing "Hallucinated" papers.** Verify and auto-correct your AI-generated references with real academic databases.
>
> **拒绝引用“幻觉”文献。** 使用真实学术数据库校验并自动修正 AI 生成的参考文献。

[🇺🇸 English Manual](#-english-manual) | [🇨🇳 中文说明](#-中文说明)

---

## 🇺🇸 English Manual

### 🧐 Why use this tool?

Generative AI (ChatGPT, Claude, DeepSeek) is great for writing, but terrible at citing. It often invents papers that look real but don't exist ("Hallucinations").

**Scholar Ref Cleaner** solves this by checking your citations against **3 global databases** using a "Waterfall Strategy":

1. **Google Scholar**: The most comprehensive coverage.
2. **Semantic Scholar**: High-quality academic graph data.
3. **Crossref**: Official publisher metadata.

### ✨ Key Features

* **🛡️ Hallucination Detection**: Instantly flags papers that don't exist.
* **🔧 Auto-Correction**: Fixes wrong years, slightly off titles, and missing authors.
* **📊 Live Dashboard**: Real-time progress bar, ETA calculator, and live logs.
* **📂 Multi-Format**:
  * **BibTeX (.bib)**: *Recommended.* Direct metadata fix & export.
  * **Word/Text (.docx, .txt)**: Scans text for citations and generates a validation report.

### 🚀 Quick Start Guide

**Step 1: Access the App**
Click the "Open in Streamlit" badge at the top or visit: [https://scholar-rc.streamlit.app/](https://scholar-rc.streamlit.app/)

**Step 2: Upload Your File**

* If you have a `.bib` file (e.g., from ChatGPT conversion), upload it to the **BibTeX Mode** tab.
* If you have a raw manuscript, upload the `.docx` to the **Word Mode** tab.

**Step 3: Watch it Clean**
The tool will process references one by one.

* *Note: If Google Scholar blocks the request (due to high traffic), the system automatically switches to Semantic Scholar. This is normal.*

**Step 4: Download Results**

* **For BibTeX**: Download the `cleaned.bib` file. It is now safe to import into Zotero/Mendeley/LaTeX.
* **For Word**: Download the `report.txt` to see which citations are fake.

### 📊 Understanding the Status

| Status              | Icon | Meaning                                                              | Action                                             |
| :------------------ | :--: | :------------------------------------------------------------------- | :------------------------------------------------- |
| **Verified**  |  ✅  | Found a match with >85% similarity. Metadata auto-corrected.         | Safe to use.                                       |
| **Ambiguous** | ⚠️ | Found a paper with a somewhat similar title (50-85%), but not exact. | **Manual Check Required.**                   |
| **Not Found** |  ❌  | No match found in any database.                                      | **Delete this citation.** It is likely fake. |

---

## 🇨🇳 中文说明

### 🧐 为什么需要这个工具？

生成式 AI（如 ChatGPT、DeepSeek、Kimi）在辅助写作方面表现出色，但它们经常编造看起来很真实但实际上不存在的“幻觉文献”。如果在申请书或论文中引用了这些假文献，将导致严重的学术不端风险。

**Scholar Ref Cleaner** 采用“瀑布流”策略，依次在**三大权威数据库**中核对您的文献：

1. **Google Scholar (谷歌学术)**：覆盖最全，优先检索。
2. **Semantic Scholar**：数据质量高，作为自动备选。
3. **Crossref**：出版商官方数据，最后一道防线。

### ✨ 核心功能

* **🛡️ 幻觉粉碎机**：自动识别并标记不存在的假文献。
* **🔧 智能纠错**：自动修正错误的年份、作者拼写和期刊名称。
* **📊 实时看板**：显示已验证数量、预计剩余时间 (ETA) 和详细处理日志。
* **📂 多格式支持**：
  * **BibTeX (.bib)**：*强烈推荐*。直接生成修正后的 .bib 文件，可导入 LaTeX 或 Zotero。
  * **Word/文本 (.docx, .txt)**：扫描文档中的引文行，生成真伪查验报告。

### 🚀 使用步骤

**第一步：打开工具**
点击页面顶部的 "Open in Streamlit" 徽章，或访问：[https://scholar-rc.streamlit.app/](https://scholar-rc.streamlit.app/)

**第二步：上传文件**

* **BibTeX 模式**（推荐）：将 AI 生成的参考文献转换为 BibTeX 格式后上传。
* **Word/文本模式**：直接上传包含参考文献列表的 `.docx` 文档。

**第三步：自动清洗**
点击 `开始清洗` 按钮。

* *注意：如果谷歌学术在云端被限制访问，系统会自动无缝切换到 Semantic Scholar，请耐心等待。*

**第四步：下载结果**

* **BibTeX**：下载 `cleaned.bib`，这是清洗干净的数据库。
* **Word**：下载 `report.txt`，查看哪些文献是 AI 瞎编的。

### 📊 结果状态解读

| 状态                         | 图标 | 含义                                          | 建议操作                                                       |
| :--------------------------- | :--: | :-------------------------------------------- | :------------------------------------------------------------- |
| **Verified (已验证)**  |  ✅  | 找到匹配项（相似度 >85%），元数据已自动修正。 | **放心使用**，直接引用。                                 |
| **Ambiguous (存疑)**   | ⚠️ | 找到了类似标题的论文，但差异较大。            | **必须人工核对**，可能是不同年份的版本或 AI 记错了标题。 |
| **Not Found (未找到)** |  ❌  | 三大数据库均未检索到。                        | **直接删除**，极大概率为 AI 幻觉。                       |

---

### 🛠️ Local Installation (Optional / 可选本地运行)

If you prefer running this locally to avoid network limits:
如果您希望在本地运行以获得更快的谷歌学术访问速度：

```bash
# 1. Clone repo
git clone https://github.com/libo-huang/scholar-ref-cleaner.git

# 2. Install requirements
pip install -r requirements.txt

# 3. Run App
streamlit run app.py
```


---

### ⚠️ Disclaimer / 免责声明

* **Accuracy**: While this tool queries official databases, it is an automated assistant. **Always perform a final manual check** for critical publications (e.g., NSFC grants, Thesis).
* **Rate Limits**: Searching specifically via Google Scholar may trigger CAPTCHAs or temporary IP bans. This tool is designed to failover gracefully, but speeds may vary.
* **License**: This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

