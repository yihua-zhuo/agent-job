# 🤖 AI Model & ComfyUI Tracker

自动追踪图片/视频模型动态及 ComfyUI 工作流更新。

## 功能

- 定期抓取主流 AI 模型（图片/视频）的最新动态
- 追踪 ComfyUI 工作流和节点更新
- 支持自定义数据源
- 输出 Markdown 报告 + JSON 数据

## 安装

```bash
pip install -r requirements.txt
```

## 使用

```bash
# 全量扫描
python tracker.py --type all

# 仅图片模型
python tracker.py --type image

# 仅视频模型
python tracker.py --type video

# 仅 ComfyUI
python tracker.py --type comfy

# 输出摘要
python tracker.py --type summary
```

## 配置数据源

编辑 `tracker.py` 中的 `SOURCES` 字典：

```python
SOURCES = {
    "image": [...],   # 图片模型源
    "video": [...],   # 视频模型源
    "comfy": [...]    # ComfyUI 源
}
```

## 输出

- `output/report-YYYY-MM-DD.md` - Markdown 报告
- `output/data-YYYY-MM-DD.json` - JSON 数据
- `tracker.db` - SQLite 数据库

## 定时任务

配合 cron（推荐每6小时或每天）:

```bash
0 */6 * * * cd /home/node/.openclaw/workspace/dev-agent-system/scripts/ai-model-tracker && python tracker.py --type all >> logs/cron.log 2>&1
```
