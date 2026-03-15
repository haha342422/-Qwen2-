# -Qwen2-
基于Qwen2搭建公文关键信息提取流程，实现公文内容的提取和分类，以及公文数据库的搭建。通过提示词工程优化，使特定格式文档字段提取准确率提升；结合PaddleOCR完成复杂排版文档的识别与后处理。
# 功能特点
- 📄 支持多种公文格式上传（PDF/图片）
- 🔍 OCR识别 + 大模型关键字段提取
- 🏷️ 自动分类与结果结构化展示

## 项目截图
![系统主界面](https://github.com/user-attachments/assets/8277cda0-ef12-47b3-89df-f6c005d52c99)
![识别结果示例](https://github.com/user-attachments/assets/75ab7fd5-ad3b-4165-8b4d-21ca7b891948)

## 技术栈
- 前端：HTML/CSS/JavaScript
- 后端：Python + Flask
- AI模型：Qwen2 + PaddleOCR
